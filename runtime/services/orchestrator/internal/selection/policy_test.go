package selection

import (
	"sync"
	"testing"

	pb "ariadne/runtime/gen/go/contract/v1"
)

func agent(id string, load float64, tasks int32) *pb.AgentDescriptor {
	return &pb.AgentDescriptor{AgentId: id, Load: load, CurrentTaskCount: tasks}
}

func TestSelectorPreservesFirstAvailableDefault(t *testing.T) {
	selected := New().Select(pb.SelectionPolicy_SELECTION_POLICY_FIRST_AVAILABLE, []*pb.AgentDescriptor{agent("b", 1, 2), agent("a", 0, 0)})
	if selected.AgentId != "b" {
		t.Fatalf("selected = %s", selected.AgentId)
	}
}

func TestRoundRobinCyclesInDeterministicAgentOrder(t *testing.T) {
	selector := New()
	agents := []*pb.AgentDescriptor{agent("c", 0, 0), agent("a", 0, 0), agent("b", 0, 0)}
	want := []string{"a", "b", "c", "a", "b"}
	for index, expected := range want {
		if got := selector.Select(pb.SelectionPolicy_SELECTION_POLICY_ROUND_ROBIN, agents).AgentId; got != expected {
			t.Fatalf("selection %d = %s, want %s", index, got, expected)
		}
	}
}

func TestRoundRobinIsSafeUnderConcurrentSelection(t *testing.T) {
	selector := New()
	agents := []*pb.AgentDescriptor{agent("a", 0, 0), agent("b", 0, 0)}
	counts := map[string]int{}
	var countsMu sync.Mutex
	var wait sync.WaitGroup
	for range 100 {
		wait.Add(1)
		go func() {
			defer wait.Done()
			id := selector.Select(pb.SelectionPolicy_SELECTION_POLICY_ROUND_ROBIN, agents).AgentId
			countsMu.Lock()
			counts[id]++
			countsMu.Unlock()
		}()
	}
	wait.Wait()
	if counts["a"] != 50 || counts["b"] != 50 {
		t.Fatalf("counts = %v", counts)
	}
}

func TestLeastLoadedUsesStableTieBreakers(t *testing.T) {
	agents := []*pb.AgentDescriptor{agent("busy", 0.8, 1), agent("b", 0.2, 1), agent("a", 0.2, 1), agent("more-tasks", 0.2, 3)}
	if selected := New().Select(pb.SelectionPolicy_SELECTION_POLICY_LEAST_LOADED, agents); selected.AgentId != "a" {
		t.Fatalf("selected = %s", selected.AgentId)
	}
}

func TestRandomSelectsCompatibleAgent(t *testing.T) {
	agents := []*pb.AgentDescriptor{agent("a", 0, 0), agent("b", 0, 0)}
	selected := New().Select(pb.SelectionPolicy_SELECTION_POLICY_RANDOM, agents)
	if selected != agents[0] && selected != agents[1] {
		t.Fatalf("selected = %v", selected)
	}
}
