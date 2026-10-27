package mission

import (
	"context"
	"sync"

	"google.golang.org/protobuf/proto"

	pb "ariadne/runtime/gen/go/contract/v1"
)

type activeMission struct {
	cancel context.CancelFunc
	done   chan struct{}
}

// AsyncRunner conduz missões que sobrevivem ao RPC que as iniciou, no mesmo
// padrão do workflow.AsyncRunner: a goroutine roda o laço, o Store guarda o
// estado e o cancelamento é cooperativo via context.
type AsyncRunner struct {
	runner *Runner
	mu     sync.RWMutex
	active map[string]activeMission
}

func NewAsyncRunner(runner *Runner) *AsyncRunner {
	return &AsyncRunner{runner: runner, active: make(map[string]activeMission)}
}

// Run executa a missão de forma síncrona (RunMission), preso ao contexto do
// RPC: se o cliente desistir, o laço é cancelado cooperativamente.
func (a *AsyncRunner) Run(ctx context.Context, request *pb.MissionRequest) (*pb.MissionResult, *pb.ErrorInfo) {
	return a.runner.Run(ctx, request)
}

// Start valida a requisição, registra a missão como CREATED e devolve o
// mission_id assim que ela estiver visível no Store.
func (a *AsyncRunner) Start(request *pb.MissionRequest) (string, *pb.ErrorInfo) {
	if failure := validateRequest(request); failure != nil {
		return "", failure
	}
	request = proto.Clone(request).(*pb.MissionRequest)
	ensureIdentity(request)
	missionID := request.MissionId

	ctx, cancel := context.WithCancel(context.Background())
	done, created := make(chan struct{}), make(chan struct{})
	failed := make(chan *pb.ErrorInfo, 1)
	a.mu.Lock()
	a.active[missionID] = activeMission{cancel: cancel, done: done}
	a.mu.Unlock()

	go func() {
		defer close(done)
		_, failure := a.runner.run(ctx, request, func() { close(created) })
		if failure != nil {
			failed <- failure
		}
		a.mu.Lock()
		delete(a.active, missionID)
		a.mu.Unlock()
	}()

	select {
	case <-created:
		return missionID, nil
	case failure := <-failed:
		cancel()
		return "", failure
	}
}

func (a *AsyncRunner) Get(missionID string) (*pb.MissionResult, *pb.ErrorInfo) {
	if missionID == "" {
		return nil, missionError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "mission_id is required")
	}
	if a.runner.deps.Missions == nil {
		return nil, missionError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, "mission store is not configured")
	}
	result, err := a.runner.deps.Missions.Get(missionID)
	if err != nil {
		return nil, missionError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, err.Error())
	}
	return result, nil
}

// Cancel interrompe uma missão ativa e espera o laço encerrar antes de
// devolver o resultado final (CANCELLED). Missões já encerradas apenas
// devolvem o que está no Store.
func (a *AsyncRunner) Cancel(missionID string) (*pb.MissionResult, *pb.ErrorInfo) {
	a.mu.RLock()
	run, active := a.active[missionID]
	a.mu.RUnlock()
	if !active {
		return a.Get(missionID)
	}
	run.cancel()
	<-run.done
	return a.Get(missionID)
}
