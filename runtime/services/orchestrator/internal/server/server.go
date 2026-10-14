package server

import (
	"context"
	"log/slog"
	"time"

	"github.com/google/uuid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
	"ariadne/runtime/services/orchestrator/internal/execution"
	"ariadne/runtime/services/orchestrator/internal/planning"
	"ariadne/runtime/services/orchestrator/internal/workflow"
)

type OrchestratorServer struct {
	pb.UnimplementedOrchestratorServiceServer
	logger   *events.Logger
	executor *execution.Executor
	workflow *workflow.Engine
	planner  *planning.Planner
	async    *workflow.AsyncRunner
}

func New(registryAddr string, logger *events.Logger, timeout ...time.Duration) *OrchestratorServer {
	defaultTimeout := 30 * time.Second
	if len(timeout) > 0 {
		defaultTimeout = timeout[0]
	}
	taskExecutor := execution.New(
		execution.GRPCDiscoverer{RegistryAddr: registryAddr},
		execution.GRPCRunner{},
		logger,
		defaultTimeout,
	)
	validator := workflow.NewValidator(workflow.DefaultValidationLimits())
	store := workflow.NewInMemoryStore()
	engine := workflow.NewEngine(taskExecutor, validator, store, logger)
	return &OrchestratorServer{
		logger:   logger,
		executor: taskExecutor,
		workflow: engine,
		planner:  planning.New(taskExecutor, validator),
		async:    workflow.NewAsyncRunner(engine, store),
	}
}

func (srv *OrchestratorServer) StartWorkflow(_ context.Context, req *pb.StartWorkflowRequest) (*pb.StartWorkflowResponse, error) {
	if req == nil || req.RootTask == nil {
		return nil, status.Error(codes.InvalidArgument, "root_task is required")
	}
	if req.Workflow == nil {
		return nil, status.Error(codes.InvalidArgument, "workflow is required")
	}
	runID, failure := srv.async.Start(req.RootTask, req.Workflow)
	if failure != nil {
		return &pb.StartWorkflowResponse{Error: failure}, nil
	}
	return &pb.StartWorkflowResponse{RunId: runID}, nil
}

func (srv *OrchestratorServer) GetWorkflow(_ context.Context, req *pb.GetWorkflowRequest) (*pb.GetWorkflowResponse, error) {
	if req == nil || req.RunId == "" {
		return nil, status.Error(codes.InvalidArgument, "run_id is required")
	}
	result, failure := srv.async.Get(req.RunId)
	if failure != nil {
		return &pb.GetWorkflowResponse{Error: failure}, nil
	}
	return &pb.GetWorkflowResponse{Result: result}, nil
}

func (srv *OrchestratorServer) CancelWorkflow(_ context.Context, req *pb.CancelWorkflowRequest) (*pb.CancelWorkflowResponse, error) {
	if req == nil || req.RunId == "" {
		return nil, status.Error(codes.InvalidArgument, "run_id is required")
	}
	result, failure := srv.async.Cancel(req.RunId)
	if failure != nil {
		return &pb.CancelWorkflowResponse{Result: result, Error: failure}, nil
	}
	return &pb.CancelWorkflowResponse{Result: result}, nil
}

func (srv *OrchestratorServer) SubmitTask(ctx context.Context, req *pb.SubmitTaskRequest) (*pb.SubmitTaskResponse, error) {
	task := req.Task
	if task == nil {
		return nil, status.Error(codes.InvalidArgument, "task is required")
	}

	// garante IDs presentes
	if task.TaskId == "" {
		task.TaskId = uuid.NewString()
	}
	if task.Trace == nil {
		task.Trace = &pb.TraceContext{TraceId: uuid.NewString()}
	}

	slog.Info("task received", "task_id", task.TaskId, "goal", task.Goal)
	if srv.logger != nil {
		srv.logger.Log(events.Event{
			EventID: uuid.NewString(),
			TaskID:  task.TaskId,
			Type:    "TASK_CREATED",
			TraceID: task.Trace.TraceId,
		})
	}
	if planning.IsPlanningTask(task) {
		definition, failure := srv.planner.Plan(ctx, task)
		if failure != nil {
			slog.Warn("workflow planning failed", "task_id", task.TaskId, "code", failure.Code, "error", failure.Message)
			return &pb.SubmitTaskResponse{Error: failure}, nil
		}
		result, failure := srv.workflow.Execute(ctx, task, definition)
		if failure != nil {
			return &pb.SubmitTaskResponse{Error: failure}, nil
		}
		return &pb.SubmitTaskResponse{WorkflowResult: result}, nil
	}

	result, failure := srv.executor.Execute(ctx, task)
	if failure != nil {
		slog.Warn("task execution failed", "task_id", task.TaskId, "code", failure.Code, "error", failure.Message)
		return &pb.SubmitTaskResponse{Error: failure}, nil
	}

	slog.Info("task finished", "task_id", task.TaskId, "agent_id", result.AgentId, "status", result.Status, "attempt", task.Attempt)
	return &pb.SubmitTaskResponse{Result: result}, nil
}

func (srv *OrchestratorServer) SubmitWorkflow(ctx context.Context, req *pb.SubmitWorkflowRequest) (*pb.SubmitWorkflowResponse, error) {
	if req == nil || req.RootTask == nil {
		return nil, status.Error(codes.InvalidArgument, "root_task is required")
	}
	if req.Workflow == nil {
		return nil, status.Error(codes.InvalidArgument, "workflow is required")
	}

	result, failure := srv.workflow.Execute(ctx, req.RootTask, req.Workflow)
	if failure != nil {
		slog.Warn("workflow rejected", "root_task_id", req.RootTask.TaskId, "code", failure.Code, "error", failure.Message)
		return &pb.SubmitWorkflowResponse{Error: failure}, nil
	}
	slog.Info("workflow finished", "workflow_id", result.WorkflowId, "run_id", result.RunId, "status", result.Status)
	return &pb.SubmitWorkflowResponse{Result: result}, nil
}
