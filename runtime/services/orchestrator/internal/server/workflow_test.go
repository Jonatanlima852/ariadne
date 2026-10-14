package server

import (
	"context"
	"testing"

	"google.golang.org/protobuf/types/known/structpb"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/orchestrator/internal/planning"
	"ariadne/runtime/services/orchestrator/internal/workflow"
)

type workflowTaskExecutor struct{}

func (workflowTaskExecutor) Execute(_ context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	output, _ := structpb.NewStruct(map[string]any{"goal": task.Goal})
	return &pb.TaskResult{
		TaskId: task.TaskId, AgentId: "fake-agent",
		Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Trace: task.Trace, Output: output,
	}, nil
}

type automaticWorkflowExecutor struct{ calls int }

func (e *automaticWorkflowExecutor) Execute(_ context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	e.calls++
	var output *structpb.Struct
	if task.Type == "WORKFLOW_PLANNING" {
		output, _ = structpb.NewStruct(map[string]any{
			"workflow_id": "auto", "final_step_id": "work",
			"steps": []any{map[string]any{
				"step_id": "work", "type": "WORK", "goal": "execute planned work",
				"payload": map[string]any{}, "required_capabilities": []any{"echo"},
				"depends_on": []any{}, "input_bindings": []any{}, "bdi_goal": "",
			}},
		})
	} else {
		output, _ = structpb.NewStruct(map[string]any{"planned": true})
	}
	return &pb.TaskResult{TaskId: task.TaskId, AgentId: "fake", Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Output: output}, nil
}

func TestSubmitTaskAutomaticallyPlansExplicitDecompositionCapability(t *testing.T) {
	executor := &automaticWorkflowExecutor{}
	validator := workflow.NewValidator(workflow.DefaultValidationLimits())
	server := &OrchestratorServer{
		planner:  planning.New(executor, validator),
		workflow: workflow.NewEngine(executor, validator, workflow.NewInMemoryStore(), nil),
	}
	response, err := server.SubmitTask(context.Background(), &pb.SubmitTaskRequest{Task: &pb.Task{
		Goal: "plan this", RequiredCapabilities: []string{planning.Capability},
	}})
	if err != nil {
		t.Fatal(err)
	}
	if response.WorkflowResult == nil || response.WorkflowResult.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED {
		t.Fatalf("response = %v", response)
	}
	if response.Result != nil || executor.calls != 2 {
		t.Fatalf("response=%v calls=%d", response, executor.calls)
	}
}

func TestSubmitWorkflowExecutesExplicitWorkflow(t *testing.T) {
	engine := workflow.NewEngine(
		workflowTaskExecutor{},
		workflow.NewValidator(workflow.DefaultValidationLimits()),
		workflow.NewInMemoryStore(),
		nil,
	)
	server := &OrchestratorServer{workflow: engine}
	request := &pb.SubmitWorkflowRequest{
		RootTask: &pb.Task{TaskId: "root", Trace: &pb.TraceContext{TraceId: "trace"}},
		Workflow: &pb.WorkflowDefinition{
			WorkflowId: "test-workflow", FinalStepId: "only",
			Steps: []*pb.WorkflowStep{{
				StepId:       "only",
				TaskTemplate: &pb.Task{Goal: "execute", RequiredCapabilities: []string{"echo"}},
			}},
		},
	}

	response, err := server.SubmitWorkflow(context.Background(), request)

	if err != nil {
		t.Fatal(err)
	}
	if response.Result == nil || response.Result.Status != pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED {
		t.Fatalf("response = %v", response)
	}
	if response.Result.Output.Fields["goal"].GetStringValue() != "execute" {
		t.Fatalf("output = %v", response.Result.Output)
	}
}

func TestSubmitWorkflowReturnsValidationError(t *testing.T) {
	server := &OrchestratorServer{workflow: workflow.NewEngine(
		workflowTaskExecutor{}, workflow.NewValidator(workflow.DefaultValidationLimits()), workflow.NewInMemoryStore(), nil,
	)}

	response, err := server.SubmitWorkflow(context.Background(), &pb.SubmitWorkflowRequest{
		RootTask: &pb.Task{}, Workflow: &pb.WorkflowDefinition{},
	})

	if err != nil {
		t.Fatal(err)
	}
	if response.Error == nil || response.Error.Code != pb.ErrorCode_ERROR_CODE_INVALID_TASK {
		t.Fatalf("response = %v", response)
	}
}
