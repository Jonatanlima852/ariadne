package workflow

import (
	"fmt"
	"strings"

	"google.golang.org/protobuf/types/known/structpb"

	pb "ariadne/runtime/gen/go/contract/v1"
)

func applyBindings(task *pb.Task, bindings []*pb.ResultBinding, results map[string]*pb.WorkflowStepResult) error {
	if len(bindings) == 0 {
		return nil
	}
	if task.Payload == nil {
		task.Payload = &structpb.Struct{Fields: map[string]*structpb.Value{}}
	}
	for _, binding := range bindings {
		stepResult := results[binding.SourceStepId]
		if stepResult == nil || stepResult.Result == nil {
			return fmt.Errorf("binding source %s has no result", binding.SourceStepId)
		}
		value, err := resolveSource(stepResult.Result, binding.SourcePath)
		if err != nil {
			return fmt.Errorf("binding %s -> %s: %w", binding.SourcePath, binding.TargetField, err)
		}
		setPayloadPath(task.Payload, strings.Split(binding.TargetField, "."), value)
	}
	return nil
}

func resolveSource(result *pb.TaskResult, path string) (*structpb.Value, error) {
	switch path {
	case "status":
		return structpb.NewStringValue(result.Status.String()), nil
	case "agent_id":
		return structpb.NewStringValue(result.AgentId), nil
	case "output":
		return structpb.NewStructValue(cloneStruct(result.Output)), nil
	case "metadata":
		return structpb.NewStructValue(cloneStruct(result.Metadata)), nil
	}
	parts := strings.Split(path, ".")
	var current *structpb.Value
	if len(parts) > 1 && parts[0] == "output" && result.Output != nil {
		current = result.Output.Fields[parts[1]]
	}
	if len(parts) > 1 && parts[0] == "metadata" && result.Metadata != nil {
		current = result.Metadata.Fields[parts[1]]
	}
	if current == nil {
		return nil, fmt.Errorf("source path %s does not exist", path)
	}
	for _, part := range parts[2:] {
		object := current.GetStructValue()
		if object == nil || object.Fields[part] == nil {
			return nil, fmt.Errorf("source path %s does not exist", path)
		}
		current = object.Fields[part]
	}
	return cloneValue(current), nil
}

func setPayloadPath(payload *structpb.Struct, parts []string, value *structpb.Value) {
	fields := payload.Fields
	for _, part := range parts[:len(parts)-1] {
		var next *structpb.Struct
		if existing := fields[part]; existing != nil {
			next = existing.GetStructValue()
		}
		if next == nil {
			next = &structpb.Struct{Fields: map[string]*structpb.Value{}}
			fields[part] = structpb.NewStructValue(next)
		}
		fields = next.Fields
	}
	fields[parts[len(parts)-1]] = cloneValue(value)
}

func cloneStruct(value *structpb.Struct) *structpb.Struct {
	if value == nil {
		return &structpb.Struct{Fields: map[string]*structpb.Value{}}
	}
	copy, _ := structpb.NewStruct(value.AsMap())
	return copy
}
func cloneValue(value *structpb.Value) *structpb.Value {
	copy, _ := structpb.NewValue(value.AsInterface())
	return copy
}
