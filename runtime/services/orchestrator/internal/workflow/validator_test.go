package workflow

import (
	"strings"
	"testing"

	"google.golang.org/protobuf/types/known/structpb"

	pb "ariadne/runtime/gen/go/contract/v1"
)

func step(id string, capabilities ...string) *pb.WorkflowStep {
	return &pb.WorkflowStep{
		StepId: id,
		TaskTemplate: &pb.Task{
			Goal: id, RequiredCapabilities: capabilities,
		},
	}
}

func validWorkflow() *pb.WorkflowDefinition {
	plan := step("plan", "route-planning")
	explain := step("explain", "explanation")
	explain.DependsOn = []string{"plan"}
	explain.InputBindings = []*pb.ResultBinding{{
		SourceStepId: "plan", SourcePath: "output.route", TargetField: "route_result",
	}}
	return &pb.WorkflowDefinition{
		WorkflowId: "route", Steps: []*pb.WorkflowStep{plan, explain}, FinalStepId: "explain",
	}
}

func requireInvalid(t *testing.T, definition *pb.WorkflowDefinition, contains string) {
	t.Helper()
	err := NewValidator(DefaultValidationLimits()).Validate(definition)
	if err == nil || !strings.Contains(err.Error(), contains) {
		t.Fatalf("error = %v, want containing %q", err, contains)
	}
}

func TestValidatorAcceptsValidDAGAndBinding(t *testing.T) {
	if err := NewValidator(DefaultValidationLimits()).Validate(validWorkflow()); err != nil {
		t.Fatalf("Validate() error = %v", err)
	}
}

func TestValidatorRejectsDuplicateStep(t *testing.T) {
	definition := validWorkflow()
	definition.Steps = append(definition.Steps, step("plan", "echo"))
	requireInvalid(t, definition, "duplicate step_id")
}

func TestValidatorRejectsUnknownDependency(t *testing.T) {
	definition := validWorkflow()
	definition.Steps[1].DependsOn = []string{"missing"}
	requireInvalid(t, definition, "unknown step")
}

func TestValidatorRejectsCycle(t *testing.T) {
	definition := validWorkflow()
	definition.Steps[0].DependsOn = []string{"explain"}
	requireInvalid(t, definition, "cycle")
}

func TestValidatorRejectsBindingFromNonDependency(t *testing.T) {
	definition := validWorkflow()
	independent := step("independent", "echo")
	definition.Steps = append(definition.Steps, independent)
	definition.Steps[1].InputBindings[0].SourceStepId = "independent"
	requireInvalid(t, definition, "is not a dependency")
}

func TestValidatorRejectsForbiddenBindingPath(t *testing.T) {
	definition := validWorkflow()
	definition.Steps[1].InputBindings[0].SourcePath = "error.details"
	requireInvalid(t, definition, "path is not allowed")
}

func TestValidatorRejectsOperationalBindingTarget(t *testing.T) {
	definition := validWorkflow()
	definition.Steps[1].InputBindings[0].TargetField = "assigned_agent_id"
	requireInvalid(t, definition, "operational field")
}

func TestValidatorRejectsOperationalTaskFields(t *testing.T) {
	definition := validWorkflow()
	definition.Steps[0].TaskTemplate.TaskId = "injected"
	requireInvalid(t, definition, "operational fields")
}

func TestValidatorRejectsRecursivePlanner(t *testing.T) {
	definition := validWorkflow()
	definition.Steps[0].TaskTemplate.RequiredCapabilities = []string{"task-decomposition"}
	requireInvalid(t, definition, "recursively")
}

func TestValidatorRejectsStepAndDepthLimits(t *testing.T) {
	definition := &pb.WorkflowDefinition{FinalStepId: "step-3"}
	for index := 1; index <= 3; index++ {
		current := step("step-"+string(rune('0'+index)), "echo")
		if index > 1 {
			current.DependsOn = []string{"step-" + string(rune('0'+index-1))}
		}
		definition.Steps = append(definition.Steps, current)
	}
	validator := NewValidator(ValidationLimits{MaxSteps: 3, MaxDepth: 2})
	if err := validator.Validate(definition); err == nil || !strings.Contains(err.Error(), "maximum depth") {
		t.Fatalf("depth error = %v", err)
	}

	definition = validWorkflow()
	definition.Steps = append(definition.Steps, step("extra", "echo"))
	validator = NewValidator(ValidationLimits{MaxSteps: 2, MaxDepth: 5})
	if err := validator.Validate(definition); err == nil || !strings.Contains(err.Error(), "maximum of 2 steps") {
		t.Fatalf("step limit error = %v", err)
	}
}

func TestValidatorRejectsPayloadLimit(t *testing.T) {
	definition := validWorkflow()
	payload, err := structpb.NewStruct(map[string]any{"large": strings.Repeat("x", 100)})
	if err != nil {
		t.Fatal(err)
	}
	definition.Steps[0].TaskTemplate.Payload = payload
	validator := NewValidator(ValidationLimits{MaxPayloadBytes: 20})
	if err := validator.Validate(definition); err == nil || !strings.Contains(err.Error(), "payload exceeds") {
		t.Fatalf("payload error = %v", err)
	}
}
