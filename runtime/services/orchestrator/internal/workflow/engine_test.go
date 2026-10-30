package workflow

import (
	"context"
	"sync"
	"testing"
	"time"

	"google.golang.org/protobuf/types/known/structpb"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
)

type engineExecutor struct {
	mu     sync.Mutex
	calls  []*pb.Task
	failAt string
}

func (e *engineExecutor) Execute(_ context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	e.mu.Lock()
	e.calls = append(e.calls, task)
	e.mu.Unlock()
	if task.Goal == e.failAt {
		failure := &pb.ErrorInfo{Code: pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, Message: "step failed"}
		return &pb.TaskResult{
			TaskId: task.TaskId, AgentId: "agent-fail",
			Status: pb.TaskStatus_TASK_STATUS_FAILED, Trace: task.Trace, Error: failure,
		}, nil
	}
	output, _ := structpb.NewStruct(map[string]any{"step": task.Goal})
	return &pb.TaskResult{
		TaskId: task.TaskId, AgentId: "agent-" + task.Goal,
		Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Trace: task.Trace, Output: output,
	}, nil
}

type engineLogger struct{ events []events.Event }

func (l *engineLogger) Log(event events.Event) { l.events = append(l.events, event) }

func sequentialDefinition() *pb.WorkflowDefinition {
	first := step("first", "echo")
	second := step("second", "echo")
	second.DependsOn = []string{"first"}
	// Ordem reversa prova que o engine respeita dependências, não a posição.
	return &pb.WorkflowDefinition{
		WorkflowId:  "workflow-1",
		Steps:       []*pb.WorkflowStep{second, first},
		FinalStepId: "second",
	}
}

func TestEngineExecutesSequentialWorkflowAndAggregatesFinalOutput(t *testing.T) {
	executor := &engineExecutor{}
	store := NewInMemoryStore()
	logger := &engineLogger{}
	engine := NewEngine(executor, NewValidator(DefaultValidationLimits()), store, logger)
	root := &pb.Task{TaskId: "root-1", Trace: &pb.TraceContext{TraceId: "trace-1", SpanId: "root-span"}}

	result, failure := engine.Execute(context.Background(), root, sequentialDefinition())

	if failure != nil {
		t.Fatalf("failure = %v", failure)
	}
	if result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED {
		t.Fatalf("status = %v", result.Status)
	}
	if len(executor.calls) != 2 || executor.calls[0].Goal != "first" || executor.calls[1].Goal != "second" {
		t.Fatalf("execution order = %#v", executor.calls)
	}
	for _, task := range executor.calls {
		if task.ParentTaskId != "root-1" || task.Trace.TraceId != "trace-1" || task.Trace.ParentSpanId != "root-span" || task.Trace.CorrelationId != result.RunId {
			t.Fatalf("materialized task correlation = %+v", task)
		}
	}
	if result.Output.Fields["step"].GetStringValue() != "second" {
		t.Fatalf("output = %v", result.Output)
	}
	for _, stepResult := range result.StepResults {
		if stepResult.Result.StartedAt == nil || stepResult.Result.CompletedAt == nil {
			t.Fatalf("step timestamps = %v", stepResult.Result)
		}
		if stepResult.Task == nil || stepResult.Task.ParentTaskId != "root-1" || stepResult.Task.TaskId != stepResult.Result.TaskId || stepResult.Task.Goal != stepResult.StepId {
			t.Fatalf("materialized task on step result = %v", stepResult.Task)
		}
	}
	stored, err := store.Get(result.RunId)
	if err != nil || stored.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED || len(stored.StepResults) != 2 {
		t.Fatalf("stored = %v err=%v", stored, err)
	}
	if logger.events[0].Type != "WORKFLOW_CREATED" || logger.events[len(logger.events)-1].Type != "WORKFLOW_COMPLETED" {
		t.Fatalf("events = %#v", logger.events)
	}
}

func TestEngineStopsOnFailureAndSkipsDependents(t *testing.T) {
	executor := &engineExecutor{failAt: "first"}
	engine := NewEngine(executor, NewValidator(DefaultValidationLimits()), NewInMemoryStore(), nil)

	result, failure := engine.Execute(context.Background(), &pb.Task{}, sequentialDefinition())

	if failure != nil {
		t.Fatalf("operational failure = %v", failure)
	}
	if result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_FAILED {
		t.Fatalf("status = %v", result.Status)
	}
	if len(executor.calls) != 1 {
		t.Fatalf("executor calls = %d", len(executor.calls))
	}
	if len(result.StepResults) != 2 || result.StepResults[1].Status != pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_SKIPPED {
		t.Fatalf("step results = %v", result.StepResults)
	}
}

type bindingExecutor struct{ received *pb.Task }

func (e *bindingExecutor) Execute(_ context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	if task.Goal == "plan" {
		output, _ := structpb.NewStruct(map[string]any{"route": map[string]any{"next": "BDI"}})
		metadata, _ := structpb.NewStruct(map[string]any{"confidence": 0.9})
		return &pb.TaskResult{TaskId: task.TaskId, AgentId: "planner", Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Output: output, Metadata: metadata}, nil
	}
	e.received = task
	output, _ := structpb.NewStruct(map[string]any{"ok": true})
	return &pb.TaskResult{TaskId: task.TaskId, AgentId: "worker", Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Output: output}, nil
}

func TestEngineResolvesBindingsIntoNestedPayload(t *testing.T) {
	definition := validWorkflow()
	definition.Steps[1].InputBindings = append(definition.Steps[1].InputBindings,
		&pb.ResultBinding{SourceStepId: "plan", SourcePath: "metadata.confidence", TargetField: "context.confidence"},
		&pb.ResultBinding{SourceStepId: "plan", SourcePath: "agent_id", TargetField: "planner_agent"},
	)
	executor := &bindingExecutor{}
	engine := NewEngine(executor, NewValidator(DefaultValidationLimits()), NewInMemoryStore(), nil)

	result, failure := engine.Execute(context.Background(), &pb.Task{}, definition)

	if failure != nil || result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if got := executor.received.Payload.Fields["route_result"].GetStructValue().Fields["next"].GetStringValue(); got != "BDI" {
		t.Fatalf("bound route = %q", got)
	}
	if got := executor.received.Payload.Fields["context"].GetStructValue().Fields["confidence"].GetNumberValue(); got != 0.9 {
		t.Fatalf("bound confidence = %v", got)
	}
	if got := executor.received.Payload.Fields["planner_agent"].GetStringValue(); got != "planner" {
		t.Fatalf("bound agent = %q", got)
	}
	// O resultado do passo guarda a tarefa materializada: payload com bindings resolvidos.
	if got := result.StepResults[1].Task.Payload.Fields["route_result"].GetStructValue().Fields["next"].GetStringValue(); got != "BDI" {
		t.Fatalf("step result task payload = %v", result.StepResults[1].Task)
	}
}

type parallelExecutor struct {
	started          chan string
	release          chan struct{}
	mu               sync.Mutex
	current, maximum int
}

func (e *parallelExecutor) Execute(ctx context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	e.mu.Lock()
	e.current++
	if e.current > e.maximum {
		e.maximum = e.current
	}
	e.mu.Unlock()
	e.started <- task.Goal
	select {
	case <-e.release:
	case <-ctx.Done():
	}
	e.mu.Lock()
	e.current--
	e.mu.Unlock()
	output, _ := structpb.NewStruct(map[string]any{"step": task.Goal})
	return &pb.TaskResult{TaskId: task.TaskId, AgentId: "parallel", Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Output: output}, nil
}

func TestEngineRunsIndependentBranchesWithConfiguredLimit(t *testing.T) {
	executor := &parallelExecutor{started: make(chan string, 3), release: make(chan struct{})}
	definition := &pb.WorkflowDefinition{FinalStepId: "final", Steps: []*pb.WorkflowStep{step("a", "echo"), step("b", "echo"), step("final", "echo")}}
	definition.Steps[2].DependsOn = []string{"a", "b"}
	engine := NewEngineWithOptions(executor, NewValidator(DefaultValidationLimits()), NewInMemoryStore(), nil, EngineOptions{MaxParallelism: 2, TotalTimeout: time.Second})
	done := make(chan *pb.WorkflowResult, 1)
	go func() { result, _ := engine.Execute(context.Background(), &pb.Task{}, definition); done <- result }()
	for i := 0; i < 2; i++ {
		select {
		case <-executor.started:
		case <-time.After(time.Second):
			t.Fatal("independent branches did not start concurrently")
		}
	}
	executor.mu.Lock()
	maximum := executor.maximum
	executor.mu.Unlock()
	if maximum != 2 {
		t.Fatalf("maximum parallelism = %d", maximum)
	}
	executor.release <- struct{}{}
	executor.release <- struct{}{}
	select {
	case <-executor.started:
	case <-time.After(time.Second):
		t.Fatal("final step did not start")
	}
	executor.release <- struct{}{}
	if result := <-done; result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED {
		t.Fatalf("status = %v", result.Status)
	}
}

func TestEngineContinuesIndependentBranchAndSkipsFailedDescendant(t *testing.T) {
	executor := &engineExecutor{failAt: "a"}
	a, b, blocked := step("a", "echo"), step("b", "echo"), step("blocked", "echo")
	blocked.DependsOn = []string{"a"}
	definition := &pb.WorkflowDefinition{Steps: []*pb.WorkflowStep{a, b, blocked}, FinalStepId: "b"}
	result, failure := NewEngine(executor, NewValidator(DefaultValidationLimits()), NewInMemoryStore(), nil).Execute(context.Background(), &pb.Task{}, definition)
	if failure != nil || result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_FAILED {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if len(executor.calls) != 2 {
		t.Fatalf("executor calls = %d", len(executor.calls))
	}
	if result.StepResults[2].Status != pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_SKIPPED {
		t.Fatalf("blocked status = %v", result.StepResults[2].Status)
	}
}

// Fila de prontos: um passo lento não segura os demais. Com paralelismo 2 e
// quatro passos independentes, a conclusão de b deve liberar c enquanto a
// ainda executa (nas ondas com barreira, c só começava depois de a).
func TestEngineDispatchesNextReadyStepWhileAnotherIsStillRunning(t *testing.T) {
	executor := &parallelExecutor{started: make(chan string, 8), release: make(chan struct{})}
	definition := &pb.WorkflowDefinition{FinalStepId: "final", Steps: []*pb.WorkflowStep{step("slow", "echo"), step("b", "echo"), step("c", "echo"), step("final", "echo")}}
	definition.Steps[3].DependsOn = []string{"slow", "b", "c"}
	engine := NewEngineWithOptions(executor, NewValidator(DefaultValidationLimits()), NewInMemoryStore(), nil, EngineOptions{MaxParallelism: 2, TotalTimeout: 5 * time.Second})
	done := make(chan *pb.WorkflowResult, 1)
	go func() { result, _ := engine.Execute(context.Background(), &pb.Task{}, definition); done <- result }()
	expectStarted := func(want string) {
		t.Helper()
		select {
		case got := <-executor.started:
			if got != want {
				t.Fatalf("started %q, want %q", got, want)
			}
		case <-time.After(time.Second):
			t.Fatalf("step %q did not start", want)
		}
	}
	// slow e b partem juntos em goroutines distintas; a ordem em que sinalizam é indefinida.
	first := map[string]bool{}
	for len(first) < 2 {
		select {
		case got := <-executor.started:
			first[got] = true
		case <-time.After(time.Second):
			t.Fatalf("first wave did not start: %v", first)
		}
	}
	if !first["slow"] || !first["b"] {
		t.Fatalf("first wave = %v, want slow and b", first)
	}
	executor.release <- struct{}{} // libera slow ou b (o primeiro a ler release é indefinido; ambos aguardam)
	expectStarted("c")             // c começa com slow ainda em execução
	executor.mu.Lock()
	maximum := executor.maximum
	executor.mu.Unlock()
	if maximum != 2 {
		t.Fatalf("maximum parallelism = %d, want 2", maximum)
	}
	executor.release <- struct{}{}
	executor.release <- struct{}{}
	expectStarted("final")
	executor.release <- struct{}{}
	if result := <-done; result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED {
		t.Fatalf("status = %v", result.Status)
	}
}
