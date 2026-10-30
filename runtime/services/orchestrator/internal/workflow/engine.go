package workflow

import (
	"context"
	"sync"
	"time"

	"github.com/google/uuid"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
)

type TaskExecutor interface {
	Execute(context.Context, *pb.Task) (*pb.TaskResult, *pb.ErrorInfo)
}
type EventLogger interface{ Log(events.Event) }

type EngineOptions struct {
	MaxParallelism int
	TotalTimeout   time.Duration
}

func DefaultEngineOptions() EngineOptions {
	return EngineOptions{MaxParallelism: 4, TotalTimeout: 30 * time.Second}
}

type Engine struct {
	executor  TaskExecutor
	validator *Validator
	store     Store
	logger    EventLogger
	options   EngineOptions
}

func NewEngine(executor TaskExecutor, validator *Validator, store Store, logger EventLogger) *Engine {
	return NewEngineWithOptions(executor, validator, store, logger, DefaultEngineOptions())
}

func NewEngineWithOptions(executor TaskExecutor, validator *Validator, store Store, logger EventLogger, options EngineOptions) *Engine {
	defaults := DefaultEngineOptions()
	if options.MaxParallelism <= 0 {
		options.MaxParallelism = defaults.MaxParallelism
	}
	if options.TotalTimeout <= 0 {
		options.TotalTimeout = defaults.TotalTimeout
	}
	return &Engine{executor: executor, validator: validator, store: store, logger: logger, options: options}
}

type stepExecution struct {
	step   *pb.WorkflowStep
	task   *pb.Task
	result *pb.WorkflowStepResult
}

func (e *Engine) Execute(parent context.Context, root *pb.Task, definition *pb.WorkflowDefinition) (*pb.WorkflowResult, *pb.ErrorInfo) {
	return e.execute(parent, root, definition, "", nil)
}

func (e *Engine) execute(parent context.Context, root *pb.Task, definition *pb.WorkflowDefinition, requestedRunID string, created func()) (*pb.WorkflowResult, *pb.ErrorInfo) {
	if root == nil {
		return nil, workflowError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "root_task is required", false)
	}
	if err := e.validator.Validate(definition); err != nil {
		return nil, workflowError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, err.Error(), false)
	}
	ctx, cancel := context.WithTimeout(parent, e.options.TotalTimeout)
	defer cancel()
	ensureRootIdentity(root)
	workflowID := definition.WorkflowId
	if workflowID == "" {
		workflowID = uuid.NewString()
	}
	runID := requestedRunID
	if runID == "" {
		runID = uuid.NewString()
	}
	result := &pb.WorkflowResult{WorkflowId: workflowID, RunId: runID, RootTaskId: root.TaskId, Status: pb.WorkflowStatus_WORKFLOW_STATUS_CREATED, Trace: proto.Clone(root.Trace).(*pb.TraceContext), CreatedAt: timestamppb.Now()}
	if err := e.store.Create(result); err != nil {
		return nil, workflowError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, err.Error(), true)
	}
	if created != nil {
		created()
	}
	e.log(result, root.TaskId, "WORKFLOW_CREATED", "", "", 0)
	e.log(result, root.TaskId, "WORKFLOW_VALIDATED", "", "", 0)
	result.Status = pb.WorkflowStatus_WORKFLOW_STATUS_RUNNING
	if err := e.store.MarkRunning(result.RunId); err != nil {
		return nil, workflowError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, err.Error(), true)
	}
	e.log(result, root.TaskId, "WORKFLOW_STARTED", "", "", 0)

	statuses := make(map[string]pb.WorkflowStepStatus, len(definition.Steps))
	stepResults := make(map[string]*pb.WorkflowStepResult, len(definition.Steps))
	for _, step := range definition.Steps {
		statuses[step.StepId] = pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_PENDING
	}

	for len(stepResults) < len(definition.Steps) {
		progress := false
		for _, step := range definition.Steps {
			if statuses[step.StepId] != pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_PENDING {
				continue
			}
			if dependencyFailed(step, statuses) {
				skipped := &pb.WorkflowStepResult{StepId: step.StepId, Status: pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_SKIPPED}
				statuses[step.StepId], stepResults[step.StepId] = skipped.Status, skipped
				_ = e.store.SaveStep(result.RunId, skipped)
				e.log(result, root.TaskId, "STEP_SKIPPED", step.StepId, "", 0)
				progress = true
			}
		}
		ready := make([]*pb.WorkflowStep, 0)
		for _, step := range definition.Steps {
			if statuses[step.StepId] == pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_PENDING && dependenciesHaveStatus(step, statuses, pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_COMPLETED) {
				statuses[step.StepId] = pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_READY
				ready = append(ready, step)
				e.log(result, root.TaskId, "STEP_READY", step.StepId, "", 0)
			}
		}
		if len(ready) == 0 {
			if progress {
				continue
			}
			break
		}
		for start := 0; start < len(ready); start += e.options.MaxParallelism {
			end := start + e.options.MaxParallelism
			if end > len(ready) {
				end = len(ready)
			}
			batch := ready[start:end]
			executions := make(chan stepExecution, len(batch))
			var wait sync.WaitGroup
			for _, step := range batch {
				statuses[step.StepId] = pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_RUNNING
				wait.Add(1)
				go func(step *pb.WorkflowStep) {
					defer wait.Done()
					task, bindingErr := materializeTask(root, result.RunId, step, stepResults)
					if bindingErr != nil {
						failure := workflowError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, bindingErr.Error(), false)
						executions <- stepExecution{step: step, result: &pb.WorkflowStepResult{StepId: step.StepId, Status: pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_FAILED, Result: failedTaskResult(&pb.Task{Trace: root.Trace}, failure)}}
						return
					}
					e.log(result, task.TaskId, "TASK_CREATED", step.StepId, "", 0)
					e.log(result, task.TaskId, "STEP_STARTED", step.StepId, "", 0)
					startedAt := timestamppb.Now()
					taskResult, failure := e.executor.Execute(ctx, task)
					stepResult := classifyStepResult(step.StepId, task, taskResult, failure, ctx.Err())
					if stepResult.Result != nil {
						if stepResult.Result.StartedAt == nil {
							stepResult.Result.StartedAt = startedAt
						}
						if stepResult.Result.CompletedAt == nil {
							stepResult.Result.CompletedAt = timestamppb.Now()
						}
					}
					executions <- stepExecution{step: step, task: task, result: stepResult}
				}(step)
			}
			wait.Wait()
			close(executions)
			for execution := range executions {
				stepResult := execution.result
				statuses[execution.step.StepId], stepResults[execution.step.StepId] = stepResult.Status, stepResult
				_ = e.store.SaveStep(result.RunId, stepResult)
				taskID, agentID, attempt := root.TaskId, "", int32(0)
				if execution.task != nil {
					taskID, attempt = execution.task.TaskId, execution.task.Attempt
				}
				if stepResult.Result != nil {
					agentID = stepResult.Result.AgentId
				}
				eventType := "STEP_FAILED"
				if stepResult.Status == pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_COMPLETED {
					eventType = "STEP_COMPLETED"
				}
				if stepResult.Status == pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_CANCELLED {
					eventType = "STEP_CANCELLED"
				}
				e.log(result, taskID, eventType, execution.step.StepId, agentID, attempt)
			}
			if ctx.Err() != nil {
				break
			}
		}
		if ctx.Err() != nil {
			break
		}
	}

	if ctx.Err() != nil {
		for _, step := range definition.Steps {
			if _, exists := stepResults[step.StepId]; !exists {
				cancelled := &pb.WorkflowStepResult{StepId: step.StepId, Status: pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_CANCELLED}
				stepResults[step.StepId] = cancelled
				_ = e.store.SaveStep(result.RunId, cancelled)
			}
		}
		if parent.Err() == context.Canceled {
			result.Status = pb.WorkflowStatus_WORKFLOW_STATUS_CANCELLED
			result.Error = workflowError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, "workflow execution cancelled", false)
		} else {
			result.Status = pb.WorkflowStatus_WORKFLOW_STATUS_TIMEOUT
			result.Error = workflowError(pb.ErrorCode_ERROR_CODE_TIMEOUT, "workflow execution timed out", false)
		}
	} else if failed := firstFailed(definition, stepResults); failed != nil {
		result.Status = pb.WorkflowStatus_WORKFLOW_STATUS_FAILED
		if failed.Result != nil {
			result.Error = failed.Result.Error
		}
		if result.Error == nil {
			result.Error = workflowError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, "workflow step failed", false)
		}
	} else {
		final := stepResults[definition.FinalStepId]
		if final == nil || final.Result == nil {
			return nil, workflowError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, "final step did not produce a result", false)
		}
		result.Status, result.Output = pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED, final.Result.Output
	}
	result.StepResults, result.CompletedAt = orderedResults(definition, stepResults), timestamppb.Now()
	if err := e.store.Complete(result.RunId, result); err != nil {
		return nil, workflowError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, err.Error(), true)
	}
	eventType := "WORKFLOW_COMPLETED"
	if result.Status == pb.WorkflowStatus_WORKFLOW_STATUS_FAILED {
		eventType = "WORKFLOW_FAILED"
	}
	if result.Status == pb.WorkflowStatus_WORKFLOW_STATUS_TIMEOUT {
		eventType = "WORKFLOW_TIMEOUT"
	}
	if result.Status == pb.WorkflowStatus_WORKFLOW_STATUS_CANCELLED {
		eventType = "WORKFLOW_CANCELLED"
	}
	e.log(result, root.TaskId, eventType, definition.FinalStepId, "", 0)
	return result, nil
}

func classifyStepResult(stepID string, task *pb.Task, taskResult *pb.TaskResult, failure *pb.ErrorInfo, contextError error) *pb.WorkflowStepResult {
	status := pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_FAILED
	if contextError != nil {
		status = pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_CANCELLED
		failure = workflowError(pb.ErrorCode_ERROR_CODE_TIMEOUT, contextError.Error(), false)
	}
	if failure != nil {
		// Preserva o resultado sintetizado pelo executor (com as tentativas)
		// quando ele existe; só fabrica um quando nada foi despachado.
		if taskResult == nil {
			taskResult = failedTaskResult(task, failure)
		} else {
			taskResult.Status = pb.TaskStatus_TASK_STATUS_FAILED
			if taskResult.Error == nil {
				taskResult.Error = failure
			}
			if contextError != nil {
				taskResult.Error = failure
			}
		}
	}
	if contextError == nil && taskResult != nil && taskResult.Status == pb.TaskStatus_TASK_STATUS_COMPLETED {
		status = pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_COMPLETED
	}
	// Task carrega a tarefa como foi enviada ao agente (payload já resolvido
	// pelos bindings, attempt e assigned_agent_id preenchidos pelo executor).
	return &pb.WorkflowStepResult{StepId: stepID, Status: status, Result: taskResult, Task: task}
}

func dependencyFailed(step *pb.WorkflowStep, statuses map[string]pb.WorkflowStepStatus) bool {
	for _, id := range step.DependsOn {
		status := statuses[id]
		if status == pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_FAILED || status == pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_SKIPPED || status == pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_CANCELLED {
			return true
		}
	}
	return false
}
func dependenciesHaveStatus(step *pb.WorkflowStep, statuses map[string]pb.WorkflowStepStatus, expected pb.WorkflowStepStatus) bool {
	for _, id := range step.DependsOn {
		if statuses[id] != expected {
			return false
		}
	}
	return true
}
func orderedResults(definition *pb.WorkflowDefinition, results map[string]*pb.WorkflowStepResult) []*pb.WorkflowStepResult {
	ordered := make([]*pb.WorkflowStepResult, 0, len(definition.Steps))
	for _, step := range topologicalOrder(definition) {
		if result := results[step.StepId]; result != nil {
			ordered = append(ordered, result)
		}
	}
	return ordered
}
func firstFailed(definition *pb.WorkflowDefinition, results map[string]*pb.WorkflowStepResult) *pb.WorkflowStepResult {
	for _, step := range topologicalOrder(definition) {
		if result := results[step.StepId]; result != nil && result.Status == pb.WorkflowStepStatus_WORKFLOW_STEP_STATUS_FAILED {
			return result
		}
	}
	return nil
}

func ensureRootIdentity(root *pb.Task) {
	if root.TaskId == "" {
		root.TaskId = uuid.NewString()
	}
	if root.Trace == nil {
		root.Trace = &pb.TraceContext{}
	}
	if root.Trace.TraceId == "" {
		root.Trace.TraceId = uuid.NewString()
	}
}
func materializeTask(root *pb.Task, runID string, step *pb.WorkflowStep, results map[string]*pb.WorkflowStepResult) (*pb.Task, error) {
	task := proto.Clone(step.TaskTemplate).(*pb.Task)
	if err := applyBindings(task, step.InputBindings, results); err != nil {
		return nil, err
	}
	task.TaskId, task.ParentTaskId = uuid.NewString(), root.TaskId
	task.Status, task.CreatedAt = pb.TaskStatus_TASK_STATUS_CREATED, timestamppb.Now()
	task.Trace = &pb.TraceContext{TraceId: root.Trace.TraceId, SpanId: uuid.NewString(), ParentSpanId: root.Trace.SpanId, CorrelationId: runID}
	return task, nil
}
func topologicalOrder(definition *pb.WorkflowDefinition) []*pb.WorkflowStep {
	completed := map[string]bool{}
	ordered := make([]*pb.WorkflowStep, 0, len(definition.Steps))
	for len(ordered) < len(definition.Steps) {
		for _, step := range definition.Steps {
			if completed[step.StepId] || !dependenciesCompleted(step, completed) {
				continue
			}
			ordered, completed[step.StepId] = append(ordered, step), true
		}
	}
	return ordered
}
func dependenciesCompleted(step *pb.WorkflowStep, completed map[string]bool) bool {
	for _, dependency := range step.DependsOn {
		if !completed[dependency] {
			return false
		}
	}
	return true
}
func failedTaskResult(task *pb.Task, failure *pb.ErrorInfo) *pb.TaskResult {
	return &pb.TaskResult{TaskId: task.TaskId, Status: pb.TaskStatus_TASK_STATUS_FAILED, CompletedAt: timestamppb.Now(), Trace: task.Trace, Error: failure}
}
func workflowError(code pb.ErrorCode, message string, retryable bool) *pb.ErrorInfo {
	return &pb.ErrorInfo{Code: code, Message: message, Retryable: retryable}
}
func (e *Engine) log(result *pb.WorkflowResult, taskID, eventType, stepID, agentID string, attempt int32) {
	if e.logger == nil {
		return
	}
	e.logger.Log(events.Event{EventID: uuid.NewString(), TaskID: taskID, Type: eventType, AgentID: agentID, TraceID: result.Trace.TraceId, WorkflowID: result.WorkflowId, RunID: result.RunId, StepID: stepID, Attempt: attempt})
}
