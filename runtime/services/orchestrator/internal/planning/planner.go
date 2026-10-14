package planning

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/structpb"

	pb "ariadne/runtime/gen/go/contract/v1"
)

const Capability = "task-decomposition"

type TaskExecutor interface {
	Execute(context.Context, *pb.Task) (*pb.TaskResult, *pb.ErrorInfo)
}
type DefinitionValidator interface {
	Validate(*pb.WorkflowDefinition) error
}

type Planner struct {
	executor  TaskExecutor
	validator DefinitionValidator
}

func New(executor TaskExecutor, validator DefinitionValidator) *Planner {
	return &Planner{executor: executor, validator: validator}
}

type planDocument struct {
	WorkflowID  string     `json:"workflow_id"`
	FinalStepID string     `json:"final_step_id"`
	Steps       []planStep `json:"steps"`
}
type planStep struct {
	StepID               string         `json:"step_id"`
	Type                 string         `json:"type"`
	Goal                 string         `json:"goal"`
	Payload              map[string]any `json:"payload"`
	RequiredCapabilities []string       `json:"required_capabilities"`
	DependsOn            []string       `json:"depends_on"`
	InputBindings        []planBinding  `json:"input_bindings"`
	BDIGoal              string         `json:"bdi_goal"`
}
type planBinding struct {
	SourceStepID string `json:"source_step_id"`
	SourcePath   string `json:"source_path"`
	TargetField  string `json:"target_field"`
}

func (p *Planner) Plan(ctx context.Context, root *pb.Task) (*pb.WorkflowDefinition, *pb.ErrorInfo) {
	if root == nil {
		return nil, planningError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "root task is required")
	}
	plannerTask := proto.Clone(root).(*pb.Task)
	plannerTask.TaskId = uuid.NewString()
	plannerTask.ParentTaskId = root.TaskId
	plannerTask.AssignedAgentId = ""
	plannerTask.Attempt = 0
	plannerTask.RequiredCapabilities = []string{Capability}
	plannerTask.Type = "WORKFLOW_PLANNING"
	plannerTask.Metadata = planningMetadata(root.Metadata)
	result, failure := p.executor.Execute(ctx, plannerTask)
	if failure != nil {
		return nil, failure
	}
	if result == nil || result.Status != pb.TaskStatus_TASK_STATUS_COMPLETED || result.Output == nil {
		return nil, planningError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, "planner did not return a completed structured output")
	}
	definition, err := decodeDefinition(result.Output)
	if err != nil {
		return nil, planningError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "invalid planner output: "+err.Error())
	}
	if err := p.validator.Validate(definition); err != nil {
		return nil, planningError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "planner workflow rejected: "+err.Error())
	}
	return definition, nil
}

func planningMetadata(existing *structpb.Struct) *structpb.Struct {
	values := map[string]any{}
	if existing != nil {
		for key, value := range existing.AsMap() {
			values[key] = value
		}
	}
	values["workflow_max_steps"] = 10
	values["workflow_max_depth"] = 5
	values["workflow_max_expansions"] = 1
	metadata, _ := structpb.NewStruct(values)
	return metadata
}

func decodeDefinition(output *structpb.Struct) (*pb.WorkflowDefinition, error) {
	encoded, err := json.Marshal(output.AsMap())
	if err != nil {
		return nil, err
	}
	var document planDocument
	decoder := json.NewDecoder(bytes.NewReader(encoded))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&document); err != nil {
		return nil, err
	}
	definition := &pb.WorkflowDefinition{WorkflowId: document.WorkflowID, FinalStepId: document.FinalStepID}
	for _, declared := range document.Steps {
		payload, err := structpb.NewStruct(declared.Payload)
		if err != nil {
			return nil, fmt.Errorf("step %s payload: %w", declared.StepID, err)
		}
		step := &pb.WorkflowStep{StepId: declared.StepID, DependsOn: declared.DependsOn, TaskTemplate: &pb.Task{Type: declared.Type, Goal: declared.Goal, Payload: payload, RequiredCapabilities: declared.RequiredCapabilities}}
		if declared.BDIGoal != "" {
			step.TaskTemplate.Bdi = &pb.BdiExtension{Goal: declared.BDIGoal}
		}
		for _, binding := range declared.InputBindings {
			step.InputBindings = append(step.InputBindings, &pb.ResultBinding{SourceStepId: binding.SourceStepID, SourcePath: binding.SourcePath, TargetField: binding.TargetField})
		}
		definition.Steps = append(definition.Steps, step)
	}
	return definition, nil
}

func planningError(code pb.ErrorCode, message string) *pb.ErrorInfo {
	return &pb.ErrorInfo{Code: code, Message: message}
}

func IsPlanningTask(task *pb.Task) bool {
	if task == nil || len(task.RequiredCapabilities) != 1 {
		return false
	}
	return task.RequiredCapabilities[0] == Capability && task.Type != "WORKFLOW_PLANNING"
}
