package workflow

import (
	"context"
	"testing"

	pb "ariadne/runtime/gen/go/contract/v1"
)

type cancellableExecutor struct{ started chan struct{} }

func (e *cancellableExecutor) Execute(ctx context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	close(e.started)
	<-ctx.Done()
	return nil, &pb.ErrorInfo{Code: pb.ErrorCode_ERROR_CODE_TIMEOUT, Message: ctx.Err().Error()}
}

type releasableExecutor struct {
	started chan struct{}
	release chan struct{}
}

func (e *releasableExecutor) Execute(_ context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	close(e.started)
	<-e.release
	return &pb.TaskResult{TaskId: task.TaskId, Status: pb.TaskStatus_TASK_STATUS_COMPLETED}, nil
}

func TestAsyncRunnerStartsGetsAndCompletesWorkflow(t *testing.T) {
	store := NewInMemoryStore()
	executor := &releasableExecutor{started: make(chan struct{}), release: make(chan struct{})}
	engine := NewEngine(executor, NewValidator(DefaultValidationLimits()), store, nil)
	runner := NewAsyncRunner(engine, store)
	runID, failure := runner.Start(&pb.Task{}, &pb.WorkflowDefinition{FinalStepId: "only", Steps: []*pb.WorkflowStep{step("only", "echo")}})
	if failure != nil || runID == "" {
		t.Fatalf("run_id=%q failure=%v", runID, failure)
	}
	<-executor.started
	runner.mu.RLock()
	done := runner.active[runID].done
	runner.mu.RUnlock()
	close(executor.release)
	<-done
	result, failure := runner.Get(runID)
	if failure != nil || result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED {
		t.Fatalf("result=%v failure=%v", result, failure)
	}
}

func TestAsyncRunnerCancelsActiveWorkflow(t *testing.T) {
	executor := &cancellableExecutor{started: make(chan struct{})}
	store := NewInMemoryStore()
	engine := NewEngine(executor, NewValidator(DefaultValidationLimits()), store, nil)
	runner := NewAsyncRunner(engine, store)
	runID, failure := runner.Start(&pb.Task{}, &pb.WorkflowDefinition{FinalStepId: "only", Steps: []*pb.WorkflowStep{step("only", "echo")}})
	if failure != nil {
		t.Fatal(failure)
	}
	<-executor.started
	result, failure := runner.Cancel(runID)
	if failure != nil {
		t.Fatal(failure)
	}
	if result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_CANCELLED || result.StepResults[0].Status != pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_CANCELLED {
		t.Fatalf("result = %v", result)
	}
}

func TestAsyncRunnerRejectsInvalidDefinitionBeforeStarting(t *testing.T) {
	store := NewInMemoryStore()
	runner := NewAsyncRunner(NewEngine(&engineExecutor{}, NewValidator(DefaultValidationLimits()), store, nil), store)
	runID, failure := runner.Start(&pb.Task{}, &pb.WorkflowDefinition{})
	if runID != "" || failure == nil || failure.Code != pb.ErrorCode_ERROR_CODE_INVALID_TASK {
		t.Fatalf("run_id=%q failure=%v", runID, failure)
	}
}
