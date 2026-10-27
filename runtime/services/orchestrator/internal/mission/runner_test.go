package mission

import (
	"context"
	"strings"
	"sync"
	"testing"
	"time"

	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/types/known/structpb"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
	"ariadne/runtime/services/orchestrator/internal/workflow"
)

// missionExecutor substitui o executor real: tarefas MISSION_PLANNING
// consomem respostas roteirizadas; as demais completam com {"step": goal}.
type missionExecutor struct {
	mu           sync.Mutex
	responses    []map[string]any
	requests     []*pb.PlannerRequest
	plannerTasks []*pb.Task
	stepTasks    []*pb.Task
	failGoal     string
	blockPlanner bool
	onStep       func(context.Context, *pb.Task) (*pb.TaskResult, *pb.ErrorInfo)
}

func (e *missionExecutor) Execute(ctx context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	if task.Type == PlannerTaskType {
		return e.plan(ctx, task)
	}
	e.mu.Lock()
	e.stepTasks = append(e.stepTasks, task)
	e.mu.Unlock()
	if e.onStep != nil {
		return e.onStep(ctx, task)
	}
	if task.Goal == e.failGoal {
		return &pb.TaskResult{TaskId: task.TaskId, AgentId: "worker-fail", Status: pb.TaskStatus_TASK_STATUS_FAILED, Trace: task.Trace,
			Error: &pb.ErrorInfo{Code: pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, Message: "step exploded"}}, nil
	}
	output, _ := structpb.NewStruct(map[string]any{"step": task.Goal})
	return &pb.TaskResult{TaskId: task.TaskId, AgentId: "worker-" + task.Goal, Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Trace: task.Trace, Output: output}, nil
}

func (e *missionExecutor) plan(ctx context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	e.mu.Lock()
	e.plannerTasks = append(e.plannerTasks, task)
	request := decodePlannerRequest(task.Payload)
	e.requests = append(e.requests, request)
	index := len(e.requests) - 1
	e.mu.Unlock()
	if e.blockPlanner {
		<-ctx.Done()
		return nil, &pb.ErrorInfo{Code: pb.ErrorCode_ERROR_CODE_TIMEOUT, Message: ctx.Err().Error()}
	}
	if index >= len(e.responses) {
		index = len(e.responses) - 1
	}
	output, err := structpb.NewStruct(e.responses[index])
	if err != nil {
		panic(err)
	}
	return &pb.TaskResult{TaskId: task.TaskId, AgentId: "planner-1", Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Trace: task.Trace, Output: output}, nil
}

func decodePlannerRequest(payload *structpb.Struct) *pb.PlannerRequest {
	encoded, err := protojson.Marshal(payload)
	if err != nil {
		panic(err)
	}
	request := &pb.PlannerRequest{}
	if err := (protojson.UnmarshalOptions{DiscardUnknown: false}).Unmarshal(encoded, request); err != nil {
		panic(err)
	}
	return request
}

type fakeDiscoverer struct{ agents []*pb.AgentDescriptor }

func (d fakeDiscoverer) Discover(context.Context, []string) ([]*pb.AgentDescriptor, error) {
	return d.agents, nil
}

type memoryLogger struct {
	mu     sync.Mutex
	events []events.Event
}

func (l *memoryLogger) Log(event events.Event) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.events = append(l.events, event)
}

func agent(id string, capabilities ...string) *pb.AgentDescriptor {
	descriptor := &pb.AgentDescriptor{AgentId: id, Endpoint: &pb.AgentEndpoint{Address: id + ":6000"}}
	for _, capability := range capabilities {
		descriptor.Capabilities = append(descriptor.Capabilities, &pb.Capability{CapabilityId: capability, Name: "name-" + capability, Description: "desc-" + capability})
	}
	return descriptor
}

func defaultAgents() []*pb.AgentDescriptor {
	return []*pb.AgentDescriptor{agent("planner-1", "mission-planning"), agent("worker-a", "echo"), agent("worker-b", "echo", "route-planning")}
}

func planStep(id, goal string, dependsOn ...string) map[string]any {
	depends := make([]any, 0, len(dependsOn))
	for _, dependency := range dependsOn {
		depends = append(depends, dependency)
	}
	return map[string]any{
		"step_id": id, "type": "WORK", "goal": goal, "payload": map[string]any{"from": "planner"},
		"required_capabilities": []any{"echo"}, "depends_on": depends, "input_bindings": []any{}, "bdi_goal": "",
	}
}

func planResponse(summary string, contextUpdate map[string]any, finalStep string, steps ...map[string]any) map[string]any {
	declared := make([]any, 0, len(steps))
	for _, step := range steps {
		declared = append(declared, step)
	}
	response := map[string]any{
		"action":  "PLAN",
		"plan":    map[string]any{"workflow_id": "round-plan", "final_step_id": finalStep, "steps": declared},
		"summary": summary,
	}
	if contextUpdate != nil {
		response["context_update"] = contextUpdate
	}
	return response
}

func doneResponse(output map[string]any) map[string]any {
	return map[string]any{"action": "DONE", "output": output, "summary": "finished"}
}

func newRunner(executor *missionExecutor, logger EventLogger) *Runner {
	return New(Dependencies{Executor: executor, Discoverer: fakeDiscoverer{agents: defaultAgents()}, Missions: NewInMemoryStore(), Logger: logger})
}

func request(goal string) *pb.MissionRequest {
	return &pb.MissionRequest{MissionId: "m-1", Goal: goal, Trace: &pb.TraceContext{TraceId: "trace-1", SpanId: "span-root"}}
}

func TestRunnerBuildsPlannerRequestWithGroupedCapabilitiesAndGrowingHistory(t *testing.T) {
	executor := &missionExecutor{responses: []map[string]any{
		planResponse("do one step", nil, "s1", planStep("s1", "first")),
		doneResponse(map[string]any{"ok": true}),
	}}
	result, failure := newRunner(executor, nil).Run(context.Background(), request("deliver"))
	if failure != nil || result.Status != pb.MissionStatus_MISSION_STATUS_COMPLETED {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if len(executor.requests) != 2 {
		t.Fatalf("planner calls = %d", len(executor.requests))
	}
	first := executor.requests[0]
	if first.MissionId != "m-1" || first.Goal != "deliver" || first.Round != 1 || len(first.History) != 0 {
		t.Fatalf("first request = %v", first)
	}
	if first.Limits.MaxRounds != 10 || first.Limits.MaxParallel != 4 || first.Limits.RoundDeadlineMs != 30000 || first.Limits.PlannerDeadlineMs != 120000 {
		t.Fatalf("limits = %v", first.Limits)
	}
	capabilities := first.AvailableCapabilities
	if len(capabilities) != 3 || capabilities[0].CapabilityId != "echo" || capabilities[0].AgentCount != 2 ||
		capabilities[1].CapabilityId != "mission-planning" || capabilities[1].AgentCount != 1 ||
		capabilities[2].CapabilityId != "route-planning" || capabilities[2].AgentCount != 1 || capabilities[2].Name != "name-route-planning" {
		t.Fatalf("capabilities = %v", capabilities)
	}
	second := executor.requests[1]
	if second.Round != 2 || len(second.History) != 1 {
		t.Fatalf("second request = %v", second)
	}
	history := second.History[0]
	if history.Round != 1 || history.Action != pb.PlannerAction_PLANNER_ACTION_PLAN || history.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED || history.PlannerSummary != "do one step" {
		t.Fatalf("history = %v", history)
	}
	if len(history.StepResults) != 1 || history.StepResults[0].Result.AgentId != "worker-first" || history.StepResults[0].Task == nil || history.StepResults[0].Task.Payload.Fields["from"].GetStringValue() != "planner" {
		t.Fatalf("history step results = %v", history.StepResults)
	}
	if second.Context.Fields["step"].GetStringValue() != "first" {
		t.Fatalf("second context = %v", second.Context)
	}
}

func TestRunnerCompletesAfterPlanAndDoneMergingContext(t *testing.T) {
	initial, _ := structpb.NewStruct(map[string]any{"a": 1.0, "b": 1.0})
	executor := &missionExecutor{responses: []map[string]any{
		planResponse("plan", map[string]any{"b": 2.0, "c": 3.0}, "s1", planStep("s1", "work")),
		doneResponse(map[string]any{"final": true}),
	}}
	req := request("deliver")
	req.Context = initial
	req.DefaultRetryPolicy = &pb.RetryPolicy{MaxAttempts: 2}
	req.DefaultSelectionPolicy = pb.SelectionPolicy_SELECTION_POLICY_ROUND_ROBIN

	result, failure := newRunner(executor, nil).Run(context.Background(), req)

	if failure != nil || result.Status != pb.MissionStatus_MISSION_STATUS_COMPLETED || result.Error != nil {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if result.MissionId != "m-1" || result.RootTaskId != "mission-m-1" || result.Trace.TraceId != "trace-1" || result.CreatedAt == nil || result.CompletedAt == nil {
		t.Fatalf("identity = %v", result)
	}
	if !result.Output.Fields["final"].GetBoolValue() {
		t.Fatalf("output = %v", result.Output)
	}
	got := result.Context.AsMap()
	if got["a"] != 1.0 || got["b"] != 2.0 || got["c"] != 3.0 || got["step"] != "work" {
		t.Fatalf("context = %v", got)
	}
	if len(result.Rounds) != 2 {
		t.Fatalf("rounds = %d", len(result.Rounds))
	}
	first := result.Rounds[0]
	if first.Round != 1 || first.Action != pb.PlannerAction_PLANNER_ACTION_PLAN || first.PlannerAgentId != "planner-1" || first.PlannerSummary != "plan" ||
		first.Plan == nil || first.Plan.FinalStepId != "s1" || first.Result == nil || first.Result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED ||
		first.PlannerResult == nil || first.StartedAt == nil || first.CompletedAt == nil || first.ContextAfter.AsMap()["step"] != "work" {
		t.Fatalf("round 1 = %v", first)
	}
	second := result.Rounds[1]
	if second.Round != 2 || second.Action != pb.PlannerAction_PLANNER_ACTION_DONE || second.Plan != nil || second.Result != nil {
		t.Fatalf("round 2 = %v", second)
	}
	// Tarefa do planejador: tipo, capacidade, prazo, pai, trace e políticas padrão.
	planner := executor.plannerTasks[0]
	if planner.Type != "MISSION_PLANNING" || planner.RequiredCapabilities[0] != "mission-planning" || planner.DeadlineMs != 120000 ||
		planner.ParentTaskId != "mission-m-1" || planner.Trace.TraceId != "trace-1" || planner.Trace.ParentSpanId != "span-root" ||
		planner.RetryPolicy.MaxAttempts != 2 || planner.SelectionPolicy != pb.SelectionPolicy_SELECTION_POLICY_ROUND_ROBIN {
		t.Fatalf("planner task = %v", planner)
	}
	// Passos sem política herdam as políticas padrão da missão.
	step := executor.stepTasks[0]
	if step.ParentTaskId != "mission-m-1" || step.RetryPolicy.MaxAttempts != 2 || step.SelectionPolicy != pb.SelectionPolicy_SELECTION_POLICY_ROUND_ROBIN || step.Trace.TraceId != "trace-1" {
		t.Fatalf("step task = %v", step)
	}
	if first.Result.StepResults[0].Task == nil || first.Result.StepResults[0].Task.TaskId != step.TaskId {
		t.Fatalf("materialized task on step result = %v", first.Result.StepResults[0].Task)
	}
}

func TestRunnerAbortsWhenPlannerAborts(t *testing.T) {
	executor := &missionExecutor{responses: []map[string]any{{"action": "ABORT", "reason": "goal impossible", "summary": "giving up"}}}
	result, failure := newRunner(executor, nil).Run(context.Background(), request("deliver"))
	if failure != nil || result.Status != pb.MissionStatus_MISSION_STATUS_ABORTED {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if result.Error == nil || result.Error.Message != "goal impossible" || len(result.Rounds) != 1 || result.Rounds[0].Action != pb.PlannerAction_PLANNER_ACTION_ABORT {
		t.Fatalf("result = %v", result)
	}
}

func TestRunnerFeedsInvalidResponsesBackAndAbortsAfterThree(t *testing.T) {
	unknownField := planResponse("bad", nil, "s1", planStep("s1", "work"))
	unknownField["unexpected"] = true
	noSteps := map[string]any{"action": "PLAN", "plan": map[string]any{"workflow_id": "x", "final_step_id": "s1", "steps": []any{}}}
	doneWithoutOutput := map[string]any{"action": "DONE"}
	cases := []struct {
		name      string
		responses []map[string]any
		status    pb.MissionStatus
		rounds    int
	}{
		{"recovers after one invalid response", []map[string]any{unknownField, doneResponse(map[string]any{"ok": true})}, pb.MissionStatus_MISSION_STATUS_COMPLETED, 2},
		{"aborts after three consecutive invalid responses", []map[string]any{unknownField, noSteps, doneWithoutOutput, doneResponse(map[string]any{})}, pb.MissionStatus_MISSION_STATUS_ABORTED, 3},
		{"counter resets after a valid plan", []map[string]any{unknownField, noSteps, planResponse("ok", nil, "s1", planStep("s1", "work")), unknownField, doneResponse(map[string]any{})}, pb.MissionStatus_MISSION_STATUS_COMPLETED, 5},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			executor := &missionExecutor{responses: tc.responses}
			result, failure := newRunner(executor, nil).Run(context.Background(), request("deliver"))
			if failure != nil || result.Status != tc.status || len(result.Rounds) != tc.rounds {
				t.Fatalf("result=%v failure=%v", result, failure)
			}
			feedback := executor.requests[1].History[0]
			if feedback.Status != pb.WorkflowStatus_WORKFLOW_STATUS_FAILED || !strings.Contains(feedback.PlannerSummary, "invalid planner response") || !strings.Contains(feedback.PlannerSummary, "unexpected") {
				t.Fatalf("feedback = %v", feedback)
			}
			if result.Status == pb.MissionStatus_MISSION_STATUS_ABORTED && (result.Error.Code != pb.ErrorCode_ERROR_CODE_INVALID_TASK || !strings.Contains(result.Error.Message, "3 consecutive")) {
				t.Fatalf("error = %v", result.Error)
			}
		})
	}
}

func TestRunnerFailsWhenMaxRoundsExhausted(t *testing.T) {
	executor := &missionExecutor{responses: []map[string]any{planResponse("again", nil, "s1", planStep("s1", "work"))}}
	req := request("deliver")
	req.Limits = &pb.MissionLimits{MaxRounds: 2}
	result, failure := newRunner(executor, nil).Run(context.Background(), req)
	if failure != nil || result.Status != pb.MissionStatus_MISSION_STATUS_FAILED || result.Error.Code != pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if len(result.Rounds) != 2 || len(executor.requests) != 2 || executor.requests[1].Limits.MaxRounds != 2 {
		t.Fatalf("rounds=%d planner calls=%d", len(result.Rounds), len(executor.requests))
	}
}

func TestRunnerKeepsGoingAfterStepFailure(t *testing.T) {
	executor := &missionExecutor{failGoal: "broken", responses: []map[string]any{
		planResponse("try", map[string]any{"attempted": true}, "s2", planStep("s1", "broken"), planStep("s2", "after", "s1")),
		doneResponse(map[string]any{"recovered": true}),
	}}
	result, failure := newRunner(executor, nil).Run(context.Background(), request("deliver"))
	if failure != nil || result.Status != pb.MissionStatus_MISSION_STATUS_COMPLETED {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	history := executor.requests[1].History[0]
	if history.Status != pb.WorkflowStatus_WORKFLOW_STATUS_FAILED || len(history.StepResults) != 2 {
		t.Fatalf("history = %v", history)
	}
	failed, skipped := history.StepResults[0], history.StepResults[1]
	if failed.Status != pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_FAILED || failed.Result.Error.Message != "step exploded" || failed.Result.AgentId != "worker-fail" {
		t.Fatalf("failed step = %v", failed)
	}
	if skipped.Status != pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_SKIPPED {
		t.Fatalf("skipped step = %v", skipped)
	}
	got := result.Context.AsMap()
	if got["attempted"] != true || got["step"] != nil {
		t.Fatalf("context after failed round = %v", got)
	}
	if result.Rounds[0].Result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_FAILED {
		t.Fatalf("round result = %v", result.Rounds[0].Result)
	}
}

func TestRunnerRespectsMaxParallelPerMission(t *testing.T) {
	started, release := make(chan string, 3), make(chan struct{})
	var mu sync.Mutex
	current, maximum := 0, 0
	executor := &missionExecutor{responses: []map[string]any{
		planResponse("fan out", nil, "c", planStep("a", "a"), planStep("b", "b"), planStep("c", "c")),
		doneResponse(map[string]any{}),
	}}
	executor.onStep = func(ctx context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
		mu.Lock()
		current++
		if current > maximum {
			maximum = current
		}
		mu.Unlock()
		started <- task.Goal
		select {
		case <-release:
		case <-ctx.Done():
		}
		mu.Lock()
		current--
		mu.Unlock()
		return &pb.TaskResult{TaskId: task.TaskId, AgentId: "parallel", Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Output: &structpb.Struct{}}, nil
	}
	req := request("deliver")
	req.Limits = &pb.MissionLimits{MaxParallel: 2, RoundDeadlineMs: 5000}
	done := make(chan *pb.MissionResult, 1)
	go func() { result, _ := newRunner(executor, nil).Run(context.Background(), req); done <- result }()
	for i := 0; i < 2; i++ {
		select {
		case <-started:
		case <-time.After(time.Second):
			t.Fatal("independent steps did not start concurrently")
		}
	}
	select {
	case goal := <-started:
		t.Fatalf("third step %q started above max_parallel", goal)
	case <-time.After(50 * time.Millisecond):
	}
	release <- struct{}{}
	release <- struct{}{}
	select {
	case <-started:
	case <-time.After(time.Second):
		t.Fatal("third step did not start")
	}
	release <- struct{}{}
	result := <-done
	mu.Lock()
	defer mu.Unlock()
	if maximum != 2 || result.Status != pb.MissionStatus_MISSION_STATUS_COMPLETED {
		t.Fatalf("maximum=%d status=%v", maximum, result.Status)
	}
}

func TestRunnerTimesOutOnMissionDeadline(t *testing.T) {
	executor := &missionExecutor{blockPlanner: true}
	req := request("deliver")
	req.Limits = &pb.MissionLimits{MissionDeadlineMs: 30}
	result, failure := newRunner(executor, nil).Run(context.Background(), req)
	if failure != nil || result.Status != pb.MissionStatus_MISSION_STATUS_TIMEOUT || result.Error.Code != pb.ErrorCode_ERROR_CODE_TIMEOUT {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if len(result.Rounds) != 1 || result.Rounds[0].PlannerSummary != "planner interrupted" || result.CompletedAt == nil {
		t.Fatalf("rounds = %v", result.Rounds)
	}
}

func TestRunnerRejectsMissionWithoutGoal(t *testing.T) {
	result, failure := newRunner(&missionExecutor{}, nil).Run(context.Background(), &pb.MissionRequest{})
	if result != nil || failure == nil || failure.Code != pb.ErrorCode_ERROR_CODE_INVALID_TASK {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
}

func TestRunnerGeneratesMissionIdAndTraceWhenEmpty(t *testing.T) {
	executor := &missionExecutor{responses: []map[string]any{doneResponse(map[string]any{})}}
	result, failure := newRunner(executor, nil).Run(context.Background(), &pb.MissionRequest{Goal: "deliver"})
	if failure != nil || result.MissionId == "" || result.Trace.TraceId == "" || result.RootTaskId != "mission-"+result.MissionId {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if executor.plannerTasks[0].Trace.TraceId != result.Trace.TraceId || executor.plannerTasks[0].Trace.CorrelationId != result.MissionId {
		t.Fatalf("planner trace = %v", executor.plannerTasks[0].Trace)
	}
}

func TestAsyncRunnerStartsGetsAndCancelsMission(t *testing.T) {
	executor := &missionExecutor{blockPlanner: true}
	async := NewAsyncRunner(newRunner(executor, nil))
	missionID, failure := async.Start(&pb.MissionRequest{Goal: "deliver"})
	if failure != nil || missionID == "" {
		t.Fatalf("mission_id=%q failure=%v", missionID, failure)
	}
	snapshot, failure := async.Get(missionID)
	if failure != nil || snapshot.MissionId != missionID || snapshot.CompletedAt != nil {
		t.Fatalf("snapshot=%v failure=%v", snapshot, failure)
	}
	if snapshot.Status != pb.MissionStatus_MISSION_STATUS_CREATED && snapshot.Status != pb.MissionStatus_MISSION_STATUS_PLANNING {
		t.Fatalf("status while running = %v", snapshot.Status)
	}
	deadline := time.After(time.Second)
	for {
		executor.mu.Lock()
		calls := len(executor.plannerTasks)
		executor.mu.Unlock()
		if calls == 1 {
			break
		}
		select {
		case <-deadline:
			t.Fatal("planner never called")
		case <-time.After(5 * time.Millisecond):
		}
	}
	result, failure := async.Cancel(missionID)
	if failure != nil || result.Status != pb.MissionStatus_MISSION_STATUS_CANCELLED || result.CompletedAt == nil {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	again, failure := async.Get(missionID)
	if failure != nil || again.Status != pb.MissionStatus_MISSION_STATUS_CANCELLED {
		t.Fatalf("get after cancel = %v failure=%v", again, failure)
	}
	if _, failure := async.Get("missing"); failure == nil {
		t.Fatal("unknown mission did not fail")
	}
	if _, failure := async.Start(&pb.MissionRequest{}); failure == nil || failure.Code != pb.ErrorCode_ERROR_CODE_INVALID_TASK {
		t.Fatalf("start without goal = %v", failure)
	}
}

func TestRunnerEmitsMissionEventsInOrder(t *testing.T) {
	logger := &memoryLogger{}
	executor := &missionExecutor{responses: []map[string]any{
		planResponse("plan", nil, "s1", planStep("s1", "work")),
		doneResponse(map[string]any{}),
	}}
	result, _ := newRunner(executor, logger).Run(context.Background(), request("deliver"))
	expected := []string{
		"MISSION_CREATED", "MISSION_ROUND_STARTED", "MISSION_PLANNED", "MISSION_ROUND_COMPLETED",
		"MISSION_ROUND_STARTED", "MISSION_PLANNED", "MISSION_ROUND_COMPLETED", "MISSION_COMPLETED",
	}
	var got []string
	var rounds []int32
	sawWorkflow := false
	for _, event := range logger.events {
		if strings.HasPrefix(event.Type, "MISSION_") {
			got = append(got, event.Type)
			rounds = append(rounds, event.Round)
			if event.MissionID != "m-1" || event.TaskID != "mission-m-1" || event.TraceID != "trace-1" {
				t.Fatalf("mission event = %+v", event)
			}
			continue
		}
		if strings.HasPrefix(event.Type, "WORKFLOW_") {
			sawWorkflow = true
			if event.TaskID != result.RootTaskId {
				t.Fatalf("workflow event not linked to root task: %+v", event)
			}
		}
	}
	if strings.Join(got, ",") != strings.Join(expected, ",") {
		t.Fatalf("events = %v", got)
	}
	if rounds[0] != 0 || rounds[1] != 1 || rounds[4] != 2 || rounds[7] != 2 {
		t.Fatalf("rounds = %v", rounds)
	}
	if !sawWorkflow {
		t.Fatal("workflow events were not emitted for the round")
	}
	planned := logger.events[2]
	if planned.AgentID != "planner-1" || !strings.Contains(planned.Details, "action=PLAN") {
		t.Fatalf("planned event = %+v", planned)
	}
}

func TestDecodePlannerResponseAcceptsEnumSpellings(t *testing.T) {
	cases := []struct {
		name   string
		action any
		want   pb.PlannerAction
		errors bool
	}{
		{"short upper", "DONE", pb.PlannerAction_PLANNER_ACTION_DONE, false},
		{"short lower", "abort", pb.PlannerAction_PLANNER_ACTION_ABORT, false},
		{"full name", "PLANNER_ACTION_PLAN", pb.PlannerAction_PLANNER_ACTION_PLAN, false},
		{"number", 2.0, pb.PlannerAction_PLANNER_ACTION_DONE, false},
		{"unknown", "RETRY", pb.PlannerAction_PLANNER_ACTION_UNKNOWN, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			output, _ := structpb.NewStruct(map[string]any{"action": tc.action})
			response, _, err := decodePlannerResponse(output)
			if (err != nil) != tc.errors {
				t.Fatalf("err = %v", err)
			}
			if err == nil && response.Action != tc.want {
				t.Fatalf("action = %v", response.Action)
			}
		})
	}
}

func TestMergeStructReplacesShallowKeys(t *testing.T) {
	base, _ := structpb.NewStruct(map[string]any{"keep": 1.0, "nested": map[string]any{"a": 1.0, "b": 2.0}})
	update, _ := structpb.NewStruct(map[string]any{"nested": map[string]any{"a": 9.0}, "new": "x"})
	merged := mergeStruct(base, update).AsMap()
	if merged["keep"] != 1.0 || merged["new"] != "x" {
		t.Fatalf("merged = %v", merged)
	}
	nested := merged["nested"].(map[string]any)
	if nested["a"] != 9.0 || nested["b"] != nil {
		t.Fatalf("nested replaced shallowly = %v", nested)
	}
	if base.Fields["new"] != nil {
		t.Fatal("base mutated")
	}
	if mergeStruct(nil, nil).Fields == nil {
		t.Fatal("merge of nil must produce an empty struct")
	}
}

func TestRunnerUsesValidatorLimitsFromDependencies(t *testing.T) {
	validator := workflow.NewValidator(workflow.ValidationLimits{MaxSteps: 1})
	executor := &missionExecutor{responses: []map[string]any{
		planResponse("too many", nil, "b", planStep("a", "a"), planStep("b", "b")),
		doneResponse(map[string]any{}),
	}}
	runner := New(Dependencies{Executor: executor, Discoverer: fakeDiscoverer{agents: defaultAgents()}, Validator: validator})
	result, failure := runner.Run(context.Background(), request("deliver"))
	if failure != nil || result.Status != pb.MissionStatus_MISSION_STATUS_COMPLETED || len(result.Rounds) != 2 {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if !strings.Contains(result.Rounds[0].PlannerSummary, "plan rejected") || result.Rounds[0].Plan == nil {
		t.Fatalf("round 1 = %v", result.Rounds[0])
	}
}
