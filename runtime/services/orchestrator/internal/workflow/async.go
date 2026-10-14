package workflow

import (
	"context"
	"sync"

	"github.com/google/uuid"
	"google.golang.org/protobuf/proto"

	pb "ariadne/runtime/gen/go/contract/v1"
)

type activeRun struct {
	cancel context.CancelFunc
	done   chan struct{}
}

// AsyncRunner owns the lifecycle of workflows that outlive their starting RPC.
// State remains behind Store so a durable implementation can replace memory later.
type AsyncRunner struct {
	engine *Engine
	store  Store
	mu     sync.RWMutex
	active map[string]activeRun
}

func NewAsyncRunner(engine *Engine, store Store) *AsyncRunner {
	return &AsyncRunner{engine: engine, store: store, active: make(map[string]activeRun)}
}

func (r *AsyncRunner) Start(root *pb.Task, definition *pb.WorkflowDefinition) (string, *pb.ErrorInfo) {
	if root == nil {
		return "", workflowError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "root_task is required", false)
	}
	if err := r.engine.validator.Validate(definition); err != nil {
		return "", workflowError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, err.Error(), false)
	}
	runID := uuid.NewString()
	ctx, cancel := context.WithCancel(context.Background())
	done, created := make(chan struct{}), make(chan struct{})
	failed := make(chan *pb.ErrorInfo, 1)
	r.mu.Lock()
	r.active[runID] = activeRun{cancel: cancel, done: done}
	r.mu.Unlock()
	rootCopy := proto.Clone(root).(*pb.Task)
	definitionCopy := proto.Clone(definition).(*pb.WorkflowDefinition)
	go func() {
		defer close(done)
		_, failure := r.engine.execute(ctx, rootCopy, definitionCopy, runID, func() { close(created) })
		if failure != nil {
			failed <- failure
		}
		r.mu.Lock()
		delete(r.active, runID)
		r.mu.Unlock()
	}()
	select {
	case <-created:
		return runID, nil
	case failure := <-failed:
		cancel()
		return "", failure
	}
}

func (r *AsyncRunner) Get(runID string) (*pb.WorkflowResult, *pb.ErrorInfo) {
	if runID == "" {
		return nil, workflowError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "run_id is required", false)
	}
	result, err := r.store.Get(runID)
	if err != nil {
		return nil, workflowError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, err.Error(), false)
	}
	return result, nil
}

func (r *AsyncRunner) Cancel(runID string) (*pb.WorkflowResult, *pb.ErrorInfo) {
	r.mu.RLock()
	run, active := r.active[runID]
	r.mu.RUnlock()
	if !active {
		result, failure := r.Get(runID)
		if failure != nil {
			return nil, failure
		}
		return result, nil
	}
	run.cancel()
	<-run.done
	return r.Get(runID)
}
