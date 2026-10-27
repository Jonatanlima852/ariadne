package server

import (
	"context"
	"sync"
	"testing"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/structpb"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/orchestrator/internal/mission"
)

// missionTaskExecutor responde DONE na primeira chamada ao planejador, ou
// bloqueia até o contexto ser cancelado quando block é verdadeiro.
type missionTaskExecutor struct {
	mu      sync.Mutex
	block   bool
	started chan struct{}
	calls   int
}

func (e *missionTaskExecutor) Execute(ctx context.Context, task *pb.Task) (*pb.TaskResult, *pb.ErrorInfo) {
	e.mu.Lock()
	e.calls++
	e.mu.Unlock()
	if e.block {
		if e.started != nil {
			close(e.started)
			e.started = nil
		}
		<-ctx.Done()
		return nil, &pb.ErrorInfo{Code: pb.ErrorCode_ERROR_CODE_TIMEOUT, Message: ctx.Err().Error()}
	}
	output, _ := structpb.NewStruct(map[string]any{"action": "DONE", "output": map[string]any{"answer": 42}})
	return &pb.TaskResult{TaskId: task.TaskId, AgentId: "planner", Status: pb.TaskStatus_TASK_STATUS_COMPLETED, Output: output}, nil
}

type missionDiscoverer struct{}

func (missionDiscoverer) Discover(context.Context, []string) ([]*pb.AgentDescriptor, error) {
	return []*pb.AgentDescriptor{{AgentId: "planner", Capabilities: []*pb.Capability{{CapabilityId: "mission-planning"}}}}, nil
}

func missionServer(executor *missionTaskExecutor) *OrchestratorServer {
	runner := mission.New(mission.Dependencies{Executor: executor, Discoverer: missionDiscoverer{}, Missions: mission.NewInMemoryStore()})
	return &OrchestratorServer{missions: mission.NewAsyncRunner(runner)}
}

func TestRunMissionReturnsCompletedResult(t *testing.T) {
	server := missionServer(&missionTaskExecutor{})
	response, err := server.RunMission(context.Background(), &pb.RunMissionRequest{Mission: &pb.MissionRequest{Goal: "answer everything"}})
	if err != nil {
		t.Fatal(err)
	}
	if response.Error != nil || response.Result == nil || response.Result.Status != pb.MissionStatus_MISSION_STATUS_COMPLETED {
		t.Fatalf("response = %v", response)
	}
	if response.Result.Output.Fields["answer"].GetNumberValue() != 42 || len(response.Result.Rounds) != 1 || response.Result.MissionId == "" {
		t.Fatalf("result = %v", response.Result)
	}
	// A missão síncrona também fica visível em GetMission.
	fetched, err := server.GetMission(context.Background(), &pb.GetMissionRequest{MissionId: response.Result.MissionId})
	if err != nil || fetched.Error != nil || fetched.Result.Status != pb.MissionStatus_MISSION_STATUS_COMPLETED {
		t.Fatalf("fetched=%v err=%v", fetched, err)
	}
}

func TestMissionRPCsValidateRequests(t *testing.T) {
	server := missionServer(&missionTaskExecutor{})
	cases := []struct {
		name string
		call func() error
	}{
		{"run without mission", func() error { _, err := server.RunMission(context.Background(), &pb.RunMissionRequest{}); return err }},
		{"run without goal", func() error {
			_, err := server.RunMission(context.Background(), &pb.RunMissionRequest{Mission: &pb.MissionRequest{}})
			return err
		}},
		{"start without goal", func() error {
			_, err := server.StartMission(context.Background(), &pb.StartMissionRequest{Mission: &pb.MissionRequest{}})
			return err
		}},
		{"get without id", func() error { _, err := server.GetMission(context.Background(), &pb.GetMissionRequest{}); return err }},
		{"cancel without id", func() error {
			_, err := server.CancelMission(context.Background(), &pb.CancelMissionRequest{})
			return err
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if err := tc.call(); status.Code(err) != codes.InvalidArgument {
				t.Fatalf("err = %v", err)
			}
		})
	}
	response, err := server.GetMission(context.Background(), &pb.GetMissionRequest{MissionId: "missing"})
	if err != nil || response.Error == nil || response.Error.Code != pb.ErrorCode_ERROR_CODE_INVALID_TASK {
		t.Fatalf("missing mission = %v err=%v", response, err)
	}
}

func TestStartGetAndCancelMission(t *testing.T) {
	executor := &missionTaskExecutor{block: true, started: make(chan struct{})}
	started := executor.started
	server := missionServer(executor)
	start, err := server.StartMission(context.Background(), &pb.StartMissionRequest{Mission: &pb.MissionRequest{MissionId: "async-1", Goal: "wait"}})
	if err != nil || start.Error != nil || start.MissionId != "async-1" {
		t.Fatalf("start=%v err=%v", start, err)
	}
	select {
	case <-started:
	case <-time.After(time.Second):
		t.Fatal("planner never started")
	}
	snapshot, err := server.GetMission(context.Background(), &pb.GetMissionRequest{MissionId: "async-1"})
	if err != nil || snapshot.Error != nil || snapshot.Result.Status != pb.MissionStatus_MISSION_STATUS_PLANNING {
		t.Fatalf("snapshot=%v err=%v", snapshot, err)
	}
	cancelled, err := server.CancelMission(context.Background(), &pb.CancelMissionRequest{MissionId: "async-1"})
	if err != nil || cancelled.Error != nil || cancelled.Result.Status != pb.MissionStatus_MISSION_STATUS_CANCELLED {
		t.Fatalf("cancelled=%v err=%v", cancelled, err)
	}
	// Reiniciar o mesmo mission_id é rejeitado: o store já o conhece.
	again, err := server.StartMission(context.Background(), &pb.StartMissionRequest{Mission: &pb.MissionRequest{MissionId: "async-1", Goal: "wait"}})
	if err != nil || again.Error == nil || again.Error.Code != pb.ErrorCode_ERROR_CODE_INVALID_TASK {
		t.Fatalf("duplicate start = %v err=%v", again, err)
	}
}
