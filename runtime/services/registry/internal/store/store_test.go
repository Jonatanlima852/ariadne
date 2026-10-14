package store

import (
	"testing"
	"time"

	pb "ariadne/runtime/gen/go/contract/v1"
)

func testAgent(agentID string) *pb.AgentDescriptor {
	return &pb.AgentDescriptor{
		AgentId: agentID,
		Status:  pb.AgentStatus_AGENT_STATUS_ALIVE,
		Capabilities: []*pb.Capability{
			{CapabilityId: "echo"},
		},
	}
}

func TestDetectFailuresTransitionsAndExcludesDeadAgent(t *testing.T) {
	agentStore := New()
	agentStore.Save(testAgent("agent-1"))

	health, err := agentStore.GetHealth("agent-1")
	if err != nil {
		t.Fatalf("GetHealth() error = %v", err)
	}

	suspectedAt := health.LastHeartbeatAt.Add(11 * time.Second)
	transitions := agentStore.DetectFailures(
		suspectedAt,
		10*time.Second,
		20*time.Second,
	)
	if len(transitions) != 1 {
		t.Fatalf("suspected transitions = %d, want 1", len(transitions))
	}
	if transitions[0].To != pb.AgentStatus_AGENT_STATUS_SUSPECTED {
		t.Fatalf("transition target = %s, want SUSPECTED", transitions[0].To)
	}

	agents := agentStore.List([]string{"echo"}, pb.AgentStatus_AGENT_STATUS_UNKNOWN)
	if len(agents) != 1 {
		t.Fatalf("suspected agent discovery count = %d, want 1", len(agents))
	}

	deadAt := health.LastHeartbeatAt.Add(21 * time.Second)
	transitions = agentStore.DetectFailures(
		deadAt,
		10*time.Second,
		20*time.Second,
	)
	if len(transitions) != 1 {
		t.Fatalf("dead transitions = %d, want 1", len(transitions))
	}
	if transitions[0].From != pb.AgentStatus_AGENT_STATUS_SUSPECTED ||
		transitions[0].To != pb.AgentStatus_AGENT_STATUS_DEAD {
		t.Fatalf("transition = %s -> %s, want SUSPECTED -> DEAD",
			transitions[0].From, transitions[0].To)
	}

	agents = agentStore.List([]string{"echo"}, pb.AgentStatus_AGENT_STATUS_UNKNOWN)
	if len(agents) != 0 {
		t.Fatalf("dead agent discovery count = %d, want 0", len(agents))
	}
}

func TestHeartbeatRecoversDeadAgentAndStoresMetrics(t *testing.T) {
	agentStore := New()
	agentStore.Save(testAgent("agent-1"))

	initialHealth, err := agentStore.GetHealth("agent-1")
	if err != nil {
		t.Fatalf("GetHealth() error = %v", err)
	}
	agentStore.DetectFailures(
		initialHealth.LastHeartbeatAt.Add(21*time.Second),
		10*time.Second,
		20*time.Second,
	)

	err = agentStore.UpdateHealth(&pb.HealthStatus{
		AgentId:          "agent-1",
		Status:           pb.AgentStatus_AGENT_STATUS_ALIVE,
		CurrentTaskCount: 2,
		Load:             0.75,
		Details:          "recovered",
	})
	if err != nil {
		t.Fatalf("UpdateHealth() error = %v", err)
	}

	agent, err := agentStore.Get("agent-1")
	if err != nil {
		t.Fatalf("Get() error = %v", err)
	}
	if agent.Status != pb.AgentStatus_AGENT_STATUS_ALIVE {
		t.Fatalf("agent status = %s, want ALIVE", agent.Status)
	}
	if agent.CurrentTaskCount != 2 || agent.Load != 0.75 {
		t.Fatalf("descriptor load = count %d load %.2f", agent.CurrentTaskCount, agent.Load)
	}

	health, err := agentStore.GetHealth("agent-1")
	if err != nil {
		t.Fatalf("GetHealth() error = %v", err)
	}
	if health.CurrentTaskCount != 2 || health.Load != 0.75 || health.Details != "recovered" {
		t.Fatalf("health = %+v, metrics were not preserved", health)
	}
	if !health.LastHeartbeatAt.After(initialHealth.LastHeartbeatAt) {
		t.Fatal("last heartbeat was not refreshed")
	}
}

func TestDeleteRemovesHealthRecord(t *testing.T) {
	agentStore := New()
	agentStore.Save(testAgent("agent-1"))

	if err := agentStore.Delete("agent-1"); err != nil {
		t.Fatalf("Delete() error = %v", err)
	}
	if _, err := agentStore.GetHealth("agent-1"); err == nil {
		t.Fatal("GetHealth() after Delete() error = nil, want not found")
	}
}

func TestListReturnsDeterministicAgentOrder(t *testing.T) {
	agentStore := New()
	agentStore.Save(testAgent("b-agent"))
	agentStore.Save(testAgent("a-agent"))

	agents := agentStore.List([]string{"echo"}, pb.AgentStatus_AGENT_STATUS_UNKNOWN)

	if len(agents) != 2 || agents[0].AgentId != "a-agent" || agents[1].AgentId != "b-agent" {
		t.Fatalf("agent order = %v, want [a-agent b-agent]", []string{agents[0].AgentId, agents[1].AgentId})
	}
}
