package workflow

import (
	"fmt"
	"regexp"
	"strings"

	"google.golang.org/protobuf/encoding/protojson"

	pb "ariadne/runtime/gen/go/contract/v1"
)

type ValidationLimits struct {
	MaxSteps        int
	MaxDepth        int
	MaxPayloadBytes int
}

func DefaultValidationLimits() ValidationLimits {
	return ValidationLimits{MaxSteps: 10, MaxDepth: 5, MaxPayloadBytes: 64 * 1024}
}

type Validator struct{ limits ValidationLimits }

func NewValidator(limits ValidationLimits) *Validator {
	defaults := DefaultValidationLimits()
	if limits.MaxSteps <= 0 {
		limits.MaxSteps = defaults.MaxSteps
	}
	if limits.MaxDepth <= 0 {
		limits.MaxDepth = defaults.MaxDepth
	}
	if limits.MaxPayloadBytes <= 0 {
		limits.MaxPayloadBytes = defaults.MaxPayloadBytes
	}
	return &Validator{limits: limits}
}

func (v *Validator) Validate(definition *pb.WorkflowDefinition) error {
	if definition == nil {
		return fmt.Errorf("workflow definition is required")
	}
	if len(definition.Steps) == 0 {
		return fmt.Errorf("workflow must contain at least one step")
	}
	if len(definition.Steps) > v.limits.MaxSteps {
		return fmt.Errorf("workflow exceeds maximum of %d steps", v.limits.MaxSteps)
	}

	steps := make(map[string]*pb.WorkflowStep, len(definition.Steps))
	for _, step := range definition.Steps {
		if step == nil || step.StepId == "" {
			return fmt.Errorf("step_id is required")
		}
		if _, exists := steps[step.StepId]; exists {
			return fmt.Errorf("duplicate step_id: %s", step.StepId)
		}
		if err := v.validateTemplate(step.StepId, step.TaskTemplate); err != nil {
			return err
		}
		steps[step.StepId] = step
	}

	if definition.FinalStepId == "" {
		return fmt.Errorf("final_step_id is required")
	}
	if _, exists := steps[definition.FinalStepId]; !exists {
		return fmt.Errorf("final step does not exist: %s", definition.FinalStepId)
	}

	for _, step := range definition.Steps {
		seenDependencies := map[string]bool{}
		for _, dependency := range step.DependsOn {
			if _, exists := steps[dependency]; !exists {
				return fmt.Errorf("step %s depends on unknown step %s", step.StepId, dependency)
			}
			if seenDependencies[dependency] {
				return fmt.Errorf("step %s repeats dependency %s", step.StepId, dependency)
			}
			seenDependencies[dependency] = true
		}
	}

	depths := map[string]int{}
	visiting := map[string]bool{}
	var depth func(string) (int, error)
	depth = func(stepID string) (int, error) {
		if visiting[stepID] {
			return 0, fmt.Errorf("workflow contains a cycle at step %s", stepID)
		}
		if cached, exists := depths[stepID]; exists {
			return cached, nil
		}
		visiting[stepID] = true
		value := 1
		for _, dependency := range steps[stepID].DependsOn {
			dependencyDepth, err := depth(dependency)
			if err != nil {
				return 0, err
			}
			if dependencyDepth+1 > value {
				value = dependencyDepth + 1
			}
		}
		visiting[stepID] = false
		depths[stepID] = value
		return value, nil
	}

	for stepID := range steps {
		value, err := depth(stepID)
		if err != nil {
			return err
		}
		if value > v.limits.MaxDepth {
			return fmt.Errorf("workflow exceeds maximum depth of %d", v.limits.MaxDepth)
		}
	}

	for _, step := range definition.Steps {
		ancestors := collectAncestors(step.StepId, steps, map[string]bool{})
		for _, binding := range step.InputBindings {
			if err := validateBinding(step.StepId, binding, steps, ancestors); err != nil {
				return err
			}
		}
	}
	return nil
}

func (v *Validator) validateTemplate(stepID string, task *pb.Task) error {
	if task == nil {
		return fmt.Errorf("step %s requires task_template", stepID)
	}
	if len(task.RequiredCapabilities) == 0 {
		return fmt.Errorf("step %s requires at least one capability", stepID)
	}
	for _, capability := range task.RequiredCapabilities {
		if capability == "" {
			return fmt.Errorf("step %s contains an empty capability", stepID)
		}
		if capability == "task-decomposition" {
			return fmt.Errorf("step %s cannot recursively request task-decomposition", stepID)
		}
	}
	if task.TaskId != "" || task.ParentTaskId != "" || task.AssignedAgentId != "" ||
		task.Attempt != 0 || task.Status != pb.TaskStatus_TASK_STATUS_UNKNOWN || task.CreatedAt != nil ||
		(task.Trace != nil && (task.Trace.TraceId != "" || task.Trace.SpanId != "" || task.Trace.ParentSpanId != "" || task.Trace.CorrelationId != "")) {
		return fmt.Errorf("step %s task_template defines operational fields", stepID)
	}
	if task.Bdi != nil && task.Bdi.IntentionId != "" {
		return fmt.Errorf("step %s task_template defines operational intention_id", stepID)
	}
	if task.Payload != nil {
		encoded, err := protojson.Marshal(task.Payload)
		if err != nil {
			return fmt.Errorf("step %s payload is invalid: %w", stepID, err)
		}
		if len(encoded) > v.limits.MaxPayloadBytes {
			return fmt.Errorf("step %s payload exceeds %d bytes", stepID, v.limits.MaxPayloadBytes)
		}
	}
	return nil
}

func collectAncestors(stepID string, steps map[string]*pb.WorkflowStep, result map[string]bool) map[string]bool {
	for _, dependency := range steps[stepID].DependsOn {
		if result[dependency] {
			continue
		}
		result[dependency] = true
		collectAncestors(dependency, steps, result)
	}
	return result
}

var targetFieldPattern = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_.-]*$`)

var reservedTargets = map[string]bool{
	"task_id": true, "agent_id": true, "assigned_agent_id": true,
	"trace": true, "trace_id": true, "status": true, "attempt": true,
	"retry_policy": true, "selection_policy": true, "parent_task_id": true,
}

func validateBinding(stepID string, binding *pb.ResultBinding, steps map[string]*pb.WorkflowStep, ancestors map[string]bool) error {
	if binding == nil {
		return fmt.Errorf("step %s contains an empty binding", stepID)
	}
	if _, exists := steps[binding.SourceStepId]; !exists {
		return fmt.Errorf("step %s binding references unknown step %s", stepID, binding.SourceStepId)
	}
	if !ancestors[binding.SourceStepId] {
		return fmt.Errorf("step %s binding source %s is not a dependency", stepID, binding.SourceStepId)
	}
	if !allowedSourcePath(binding.SourcePath) {
		return fmt.Errorf("step %s binding path is not allowed: %s", stepID, binding.SourcePath)
	}
	if !targetFieldPattern.MatchString(binding.TargetField) {
		return fmt.Errorf("step %s binding target is invalid: %s", stepID, binding.TargetField)
	}
	root := strings.Split(binding.TargetField, ".")[0]
	if reservedTargets[root] {
		return fmt.Errorf("step %s binding targets operational field: %s", stepID, binding.TargetField)
	}
	return nil
}

func allowedSourcePath(path string) bool {
	return path == "output" || strings.HasPrefix(path, "output.") ||
		path == "metadata" || strings.HasPrefix(path, "metadata.") ||
		path == "status" || path == "agent_id"
}
