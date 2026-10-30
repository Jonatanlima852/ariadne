package execution

import (
	"context"
	"errors"
	"testing"
	"time"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
)

type fakeDiscoverer struct {
	agents []*pb.AgentDescriptor
	calls  int
}

func (f *fakeDiscoverer) Discover(context.Context, []string) ([]*pb.AgentDescriptor, error) {
	f.calls++
	return f.agents, nil
}

type runnerCall struct {
	agentID string
	attempt int32
}

type fakeRunner struct {
	calls []runnerCall
	run   func(context.Context, *pb.AgentDescriptor, *pb.Task) (*pb.TaskResult, error)
}

func (f *fakeRunner) Execute(ctx context.Context, agent *pb.AgentDescriptor, task *pb.Task) (*pb.TaskResult, error) {
	f.calls = append(f.calls, runnerCall{agentID: agent.AgentId, attempt: task.Attempt})
	return f.run(ctx, agent, task)
}

type memoryLogger struct{ events []events.Event }

func (l *memoryLogger) Log(event events.Event) { l.events = append(l.events, event) }

func descriptor(id string) *pb.AgentDescriptor {
	return &pb.AgentDescriptor{
		AgentId:  id,
		Endpoint: &pb.AgentEndpoint{Address: id + ":6000"},
	}
}

func retryTask() *pb.Task {
	return &pb.Task{
		TaskId: "task-1", Goal: "test", RequiredCapabilities: []string{"echo"},
		Trace:       &pb.TraceContext{TraceId: "trace-1"},
		DeadlineMs:  5,
		RetryPolicy: &pb.RetryPolicy{MaxAttempts: 2, ExcludeFailedAgent: true},
	}
}

func eventTypes(logger *memoryLogger) []string {
	types := make([]string, 0, len(logger.events))
	for _, event := range logger.events {
		types = append(types, event.Type)
	}
	return types
}

func TestExecutorReassignsAfterTimeout(t *testing.T) {
	discoverer := &fakeDiscoverer{agents: []*pb.AgentDescriptor{descriptor("slow"), descriptor("healthy")}}
	runner := &fakeRunner{}
	runner.run = func(ctx context.Context, agent *pb.AgentDescriptor, task *pb.Task) (*pb.TaskResult, error) {
		if agent.AgentId == "slow" {
			<-ctx.Done()
			return nil, ctx.Err()
		}
		return &pb.TaskResult{
			TaskId: task.TaskId, AgentId: agent.AgentId,
			Status: pb.TaskStatus_TASK_STATUS_COMPLETED,
		}, nil
	}
	logger := &memoryLogger{}

	result, failure := New(discoverer, runner, logger, time.Second).Execute(context.Background(), retryTask())

	if failure != nil {
		t.Fatalf("unexpected failure: %v", failure)
	}
	if result.AgentId != "healthy" {
		t.Fatalf("agent = %q, want healthy", result.AgentId)
	}
	if len(runner.calls) != 2 || runner.calls[0] != (runnerCall{"slow", 1}) || runner.calls[1] != (runnerCall{"healthy", 2}) {
		t.Fatalf("calls = %#v", runner.calls)
	}
	wantEvents := []string{"TASK_ASSIGNED", "TASK_TIMEOUT", "TASK_REASSIGNED", "TASK_COMPLETED"}
	gotEvents := eventTypes(logger)
	for index := range wantEvents {
		if gotEvents[index] != wantEvents[index] {
			t.Fatalf("events = %v, want %v", gotEvents, wantEvents)
		}
	}
	if discoverer.calls != 2 {
		t.Fatalf("discovery calls = %d, want 2", discoverer.calls)
	}
	if len(result.Attempts) != 2 {
		t.Fatalf("attempts = %d, want 2", len(result.Attempts))
	}
	first, second := result.Attempts[0], result.Attempts[1]
	if first.Attempt != 1 || first.AgentId != "slow" || first.Outcome != pb.AttemptOutcome_ATTEMPT_OUTCOME_TIMEOUT || first.Error == nil {
		t.Fatalf("first attempt = %v", first)
	}
	if second.Attempt != 2 || second.AgentId != "healthy" || second.Outcome != pb.AttemptOutcome_ATTEMPT_OUTCOME_COMPLETED || second.Error != nil {
		t.Fatalf("second attempt = %v", second)
	}
	if first.StartedAt == nil || first.CompletedAt == nil || second.StartedAt.AsTime().Before(first.CompletedAt.AsTime()) {
		t.Fatalf("attempt intervals are not ordered: %v %v", first, second)
	}
}

func TestExecutorReturnsSynthesizedResultWithAttemptsWhenAllTimeOut(t *testing.T) {
	bdi := descriptor("bdi-1")
	bdi.Kind = pb.AgentKind_AGENT_KIND_BDI
	discoverer := &fakeDiscoverer{agents: []*pb.AgentDescriptor{descriptor("slow"), bdi}}
	runner := &fakeRunner{run: func(ctx context.Context, agent *pb.AgentDescriptor, task *pb.Task) (*pb.TaskResult, error) {
		<-ctx.Done()
		return nil, ctx.Err()
	}}

	result, failure := New(discoverer, runner, &memoryLogger{}, time.Second).Execute(context.Background(), retryTask())

	if failure == nil || failure.Code != pb.ErrorCode_ERROR_CODE_TIMEOUT {
		t.Fatalf("failure = %v, want timeout", failure)
	}
	if result == nil || result.Status != pb.TaskStatus_TASK_STATUS_TIMEOUT || len(result.Attempts) != 2 {
		t.Fatalf("result = %v", result)
	}
	if result.AgentId != "bdi-1" || result.AgentKind != pb.AgentKind_AGENT_KIND_BDI {
		t.Fatalf("final agent = %q kind %v", result.AgentId, result.AgentKind)
	}
	for _, attempt := range result.Attempts {
		if attempt.Outcome != pb.AttemptOutcome_ATTEMPT_OUTCOME_TIMEOUT {
			t.Fatalf("attempt %d outcome = %v", attempt.Attempt, attempt.Outcome)
		}
	}
	if result.Attempts[1].AgentKind != pb.AgentKind_AGENT_KIND_BDI {
		t.Fatalf("second attempt kind = %v", result.Attempts[1].AgentKind)
	}
}

func TestExecutorRetriesRetryableTaskResult(t *testing.T) {
	discoverer := &fakeDiscoverer{agents: []*pb.AgentDescriptor{descriptor("failing"), descriptor("healthy")}}
	runner := &fakeRunner{}
	runner.run = func(ctx context.Context, agent *pb.AgentDescriptor, task *pb.Task) (*pb.TaskResult, error) {
		if agent.AgentId == "failing" {
			return &pb.TaskResult{
				TaskId: task.TaskId, AgentId: agent.AgentId,
				Status: pb.TaskStatus_TASK_STATUS_FAILED,
				Error:  &pb.ErrorInfo{Message: "retry me", Retryable: true},
			}, nil
		}
		return &pb.TaskResult{TaskId: task.TaskId, AgentId: agent.AgentId, Status: pb.TaskStatus_TASK_STATUS_COMPLETED}, nil
	}

	result, failure := New(discoverer, runner, nil, time.Second).Execute(context.Background(), retryTask())

	if failure != nil || result.Status != pb.TaskStatus_TASK_STATUS_COMPLETED {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
}

func TestExecutorDoesNotRetryWithoutPolicy(t *testing.T) {
	discoverer := &fakeDiscoverer{agents: []*pb.AgentDescriptor{descriptor("broken"), descriptor("unused")}}
	runner := &fakeRunner{run: func(context.Context, *pb.AgentDescriptor, *pb.Task) (*pb.TaskResult, error) {
		return nil, errors.New("connection lost")
	}}
	task := retryTask()
	task.RetryPolicy = nil

	_, failure := New(discoverer, runner, nil, time.Second).Execute(context.Background(), task)

	if failure == nil || failure.Code != pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED {
		t.Fatalf("failure = %v", failure)
	}
	if len(runner.calls) != 1 {
		t.Fatalf("calls = %d, want 1", len(runner.calls))
	}
}

func TestExecutorReturnsNonRetryableAgentFailure(t *testing.T) {
	discoverer := &fakeDiscoverer{agents: []*pb.AgentDescriptor{descriptor("agent")}}
	runner := &fakeRunner{run: func(_ context.Context, agent *pb.AgentDescriptor, task *pb.Task) (*pb.TaskResult, error) {
		return &pb.TaskResult{
			TaskId: task.TaskId, AgentId: agent.AgentId,
			Status: pb.TaskStatus_TASK_STATUS_FAILED,
			Error:  &pb.ErrorInfo{Message: "invalid", Retryable: false},
		}, nil
	}}

	result, failure := New(discoverer, runner, nil, time.Second).Execute(context.Background(), retryTask())

	if failure != nil || result.Error.Message != "invalid" {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
	if len(runner.calls) != 1 {
		t.Fatalf("calls = %d, want 1", len(runner.calls))
	}
}

func TestExecutorAppliesRoundRobinAcrossTasks(t *testing.T) {
	discoverer := &fakeDiscoverer{agents: []*pb.AgentDescriptor{descriptor("b"), descriptor("a")}}
	runner := &fakeRunner{run: func(_ context.Context, agent *pb.AgentDescriptor, task *pb.Task) (*pb.TaskResult, error) {
		return &pb.TaskResult{TaskId: task.TaskId, AgentId: agent.AgentId, Status: pb.TaskStatus_TASK_STATUS_COMPLETED}, nil
	}}
	executor := New(discoverer, runner, nil, time.Second)
	for range 3 {
		task := retryTask()
		task.SelectionPolicy = pb.SelectionPolicy_SELECTION_POLICY_ROUND_ROBIN
		if _, failure := executor.Execute(context.Background(), task); failure != nil {
			t.Fatal(failure)
		}
	}
	if got := []string{runner.calls[0].agentID, runner.calls[1].agentID, runner.calls[2].agentID}; got[0] != "a" || got[1] != "b" || got[2] != "a" {
		t.Fatalf("agents = %v", got)
	}
}

func TestExecutorAppliesLeastLoadedFromDiscoveryState(t *testing.T) {
	busy, idle := descriptor("busy"), descriptor("idle")
	busy.Load, busy.CurrentTaskCount = 0.9, 3
	idle.Load, idle.CurrentTaskCount = 0.1, 1
	discoverer := &fakeDiscoverer{agents: []*pb.AgentDescriptor{busy, idle}}
	runner := &fakeRunner{run: func(_ context.Context, agent *pb.AgentDescriptor, task *pb.Task) (*pb.TaskResult, error) {
		return &pb.TaskResult{TaskId: task.TaskId, AgentId: agent.AgentId, Status: pb.TaskStatus_TASK_STATUS_COMPLETED}, nil
	}}
	task := retryTask()
	task.SelectionPolicy = pb.SelectionPolicy_SELECTION_POLICY_LEAST_LOADED
	result, failure := New(discoverer, runner, nil, time.Second).Execute(context.Background(), task)
	if failure != nil || result.AgentId != "idle" {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
}
