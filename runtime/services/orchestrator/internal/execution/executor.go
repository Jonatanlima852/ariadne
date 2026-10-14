package execution

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
	"ariadne/runtime/services/orchestrator/internal/selection"
)

type Discoverer interface {
	Discover(context.Context, []string) ([]*pb.AgentDescriptor, error)
}

type Runner interface {
	Execute(context.Context, *pb.AgentDescriptor, *pb.Task) (*pb.TaskResult, error)
}

type EventLogger interface {
	Log(events.Event)
}

type Executor struct {
	discoverer     Discoverer
	runner         Runner
	logger         EventLogger
	defaultTimeout time.Duration
	selector       *selection.Selector
}

func New(discoverer Discoverer, runner Runner, logger EventLogger, defaultTimeout time.Duration) *Executor {
	if defaultTimeout <= 0 {
		defaultTimeout = 30 * time.Second
	}
	return &Executor{
		discoverer: discoverer, runner: runner, logger: logger,
		defaultTimeout: defaultTimeout, selector: selection.New(),
	}
}

// Execute executa uma task com timeout, retry e redescoberta entre tentativas.
// O segundo retorno representa falhas operacionais sem TaskResult do agente.
func (e *Executor) Execute(ctx context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	maxAttempts, backoff, excludeFailed := retryConfiguration(task)
	excluded := map[string]bool{}
	var lastErr error
	lastWasTimeout := false

	for attempt := int32(1); attempt <= maxAttempts; attempt++ {
		agents, err := e.discoverer.Discover(ctx, task.RequiredCapabilities)
		if err != nil {
			return nil, operationalError(pb.ErrorCode_ERROR_CODE_AGENT_UNAVAILABLE, "registry discovery failed", true)
		}
		agents = availableAgents(agents, excluded)
		if len(agents) == 0 {
			if attempt == 1 {
				return nil, operationalError(pb.ErrorCode_ERROR_CODE_CAPABILITY_NOT_FOUND, "no compatible agent found", false)
			}
			return nil, operationalError(pb.ErrorCode_ERROR_CODE_AGENT_UNAVAILABLE, "no alternative compatible agent found", false)
		}

		agent := e.selector.Select(task.SelectionPolicy, agents)
		attemptTask := proto.Clone(task).(*pb.Task)
		attemptTask.Attempt = attempt
		attemptTask.AssignedAgentId = agent.AgentId
		task.Attempt = attempt
		task.AssignedAgentId = agent.AgentId

		eventType := "TASK_ASSIGNED"
		if attempt > 1 {
			eventType = "TASK_REASSIGNED"
		}
		e.log(task, eventType, agent.AgentId, fmt.Sprintf("attempt=%d", attempt))

		attemptCtx, cancel := context.WithTimeout(ctx, executionTimeout(task, e.defaultTimeout))
		result, err := e.runner.Execute(attemptCtx, agent, attemptTask)
		cancel()

		lastWasTimeout = isTimeout(err)
		if lastWasTimeout {
			lastErr = err
			e.log(task, "TASK_TIMEOUT", agent.AgentId, fmt.Sprintf("attempt=%d", attempt))
		} else if err != nil {
			lastErr = err
			e.log(task, "TASK_FAILED", agent.AgentId, fmt.Sprintf("attempt=%d error=%s", attempt, err))
		} else if result == nil {
			lastErr = errors.New("agent returned no result")
			e.log(task, "TASK_FAILED", agent.AgentId, fmt.Sprintf("attempt=%d error=no result", attempt))
		} else if result.Status == pb.TaskStatus_TASK_STATUS_COMPLETED {
			e.log(task, "TASK_COMPLETED", agent.AgentId, fmt.Sprintf("attempt=%d", attempt))
			return result, nil
		} else {
			e.log(task, "TASK_FAILED", agent.AgentId, fmt.Sprintf("attempt=%d", attempt))
			if result.Error == nil || !result.Error.Retryable || attempt == maxAttempts {
				return result, nil
			}
			lastErr = errors.New(result.Error.Message)
		}

		if attempt == maxAttempts {
			break
		}
		if excludeFailed {
			excluded[agent.AgentId] = true
		}
		if err := waitBackoff(ctx, backoff); err != nil {
			return nil, operationalError(pb.ErrorCode_ERROR_CODE_TIMEOUT, err.Error(), true)
		}
	}

	if lastWasTimeout {
		return nil, operationalError(pb.ErrorCode_ERROR_CODE_TIMEOUT, "agent execution timed out", true)
	}
	message := "agent execution failed"
	if lastErr != nil {
		message = lastErr.Error()
	}
	return nil, operationalError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, message, true)
}

func retryConfiguration(task *pb.Task) (int32, time.Duration, bool) {
	if task.RetryPolicy == nil {
		return 1, 0, false
	}
	maxAttempts := task.RetryPolicy.MaxAttempts
	if maxAttempts <= 0 {
		maxAttempts = 1
	}
	return maxAttempts, time.Duration(task.RetryPolicy.BackoffMs) * time.Millisecond, task.RetryPolicy.ExcludeFailedAgent
}

func executionTimeout(task *pb.Task, fallback time.Duration) time.Duration {
	if task.DeadlineMs > 0 {
		return time.Duration(task.DeadlineMs) * time.Millisecond
	}
	return fallback
}

func availableAgents(agents []*pb.AgentDescriptor, excluded map[string]bool) []*pb.AgentDescriptor {
	available := make([]*pb.AgentDescriptor, 0, len(agents))
	for _, agent := range agents {
		if agent != nil && !excluded[agent.AgentId] {
			available = append(available, agent)
		}
	}
	return available
}

func isTimeout(err error) bool {
	return errors.Is(err, context.DeadlineExceeded) || status.Code(err) == codes.DeadlineExceeded
}

func waitBackoff(ctx context.Context, duration time.Duration) error {
	if duration <= 0 {
		return nil
	}
	timer := time.NewTimer(duration)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

func operationalError(code pb.ErrorCode, message string, retryable bool) *pb.ErrorInfo {
	return &pb.ErrorInfo{Code: code, Message: message, Retryable: retryable}
}

func (e *Executor) log(task *pb.Task, eventType, agentID, details string) {
	if e.logger == nil {
		return
	}
	traceID := ""
	if task.Trace != nil {
		traceID = task.Trace.TraceId
	}
	e.logger.Log(events.Event{
		EventID: uuid.NewString(), TaskID: task.TaskId, Type: eventType,
		AgentID: agentID, TraceID: traceID, Details: details,
	})
}
