package planning

import (
	"context"
	"testing"

	"google.golang.org/protobuf/types/known/structpb"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/orchestrator/internal/workflow"
)

type plannerExecutor struct {
	output   map[string]any
	received *pb.Task
}

func (e *plannerExecutor) Execute(_ context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	e.received = task
	output, _ := structpb.NewStruct(e.output)
	return &pb.TaskResult{Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Output: output}, nil
}

func validPlanOutput() map[string]any {
	return map[string]any{"workflow_id": "route", "final_step_id": "explain", "steps": []any{
		map[string]any{"step_id": "route", "type": "PLAN_ROUTE", "goal": "route", "payload": map[string]any{"origin": "A", "destination": "D"}, "required_capabilities": []any{"route-planning"}, "depends_on": []any{}, "input_bindings": []any{}, "bdi_goal": "ir de A para D"},
		map[string]any{"step_id": "explain", "type": "EXPLANATION", "goal": "explain", "payload": map[string]any{}, "required_capabilities": []any{"explanation"}, "depends_on": []any{"route"}, "input_bindings": []any{map[string]any{"source_step_id": "route", "source_path": "output", "target_field": "bdi_result"}}, "bdi_goal": ""},
	}}
}

func TestPlannerConvertsAndValidatesStructuredOutput(t *testing.T) {
	executor := &plannerExecutor{output: validPlanOutput()}
	planner := New(executor, workflow.NewValidator(workflow.DefaultValidationLimits()))
	definition, failure := planner.Plan(context.Background(), &pb.Task{TaskId: "root", Goal: "route", RequiredCapabilities: []string{Capability}})
	if failure != nil {
		t.Fatalf("failure = %v", failure)
	}
	if definition.FinalStepId != "explain" || len(definition.Steps) != 2 {
		t.Fatalf("definition = %v", definition)
	}
	if executor.received.Type != "WORKFLOW_PLANNING" || executor.received.ParentTaskId != "root" {
		t.Fatalf("planner task = %v", executor.received)
	}
	if definition.Steps[0].TaskTemplate.Bdi.Goal != "ir de A para D" {
		t.Fatalf("bdi extension = %v", definition.Steps[0].TaskTemplate.Bdi)
	}
}

func TestPlannerRejectsInvalidOrRecursiveOutput(t *testing.T) {
	output := validPlanOutput()
	output["unexpected"] = true
	planner := New(&plannerExecutor{output: output}, workflow.NewValidator(workflow.DefaultValidationLimits()))
	if definition, failure := planner.Plan(context.Background(), &pb.Task{}); definition != nil || failure == nil || failure.Code != pb.ErrorCode_ERROR_CODE_INVALID_TASK {
		t.Fatalf("definition=%v failure=%v", definition, failure)
	}
	output = validPlanOutput()
	output["steps"].([]any)[0].(map[string]any)["required_capabilities"] = []any{Capability}
	planner = New(&plannerExecutor{output: output}, workflow.NewValidator(workflow.DefaultValidationLimits()))
	if definition, failure := planner.Plan(context.Background(), &pb.Task{}); definition != nil || failure == nil {
		t.Fatalf("definition=%v failure=%v", definition, failure)
	}
}

func TestIsPlanningTaskRequiresExplicitSingleEntryCapability(t *testing.T) {
	if !IsPlanningTask(&pb.Task{RequiredCapabilities: []string{Capability}}) {
		t.Fatal("planning task not detected")
	}
	if IsPlanningTask(&pb.Task{Type: "WORKFLOW_PLANNING", RequiredCapabilities: []string{Capability}}) {
		t.Fatal("recursive planner task detected")
	}
	if IsPlanningTask(&pb.Task{RequiredCapabilities: []string{Capability, "other"}}) {
		t.Fatal("ambiguous task detected")
	}
}
