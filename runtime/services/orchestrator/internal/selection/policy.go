package selection

import (
	"math/rand"
	"sort"
	"strings"
	"sync"
	"time"

	pb "ariadne/runtime/gen/go/contract/v1"
)

// Selector guarda apenas o cursor necessário ao ROUND_ROBIN. A chave do
// cursor representa o conjunto compatível devolvido pelo Registry.
type Selector struct {
	mu      sync.Mutex
	cursors map[string]uint64
	random  *rand.Rand
}

func New() *Selector {
	return &Selector{cursors: make(map[string]uint64), random: rand.New(rand.NewSource(time.Now().UnixNano()))}
}

func (s *Selector) Select(policy pb.SelectionPolicy, agents []*pb.AgentDescriptor) *pb.AgentDescriptor {
	if len(agents) == 0 {
		return nil
	}
	switch policy {
	case pb.SelectionPolicy_SELECTION_POLICY_ROUND_ROBIN:
		return s.roundRobin(agents)
	case pb.SelectionPolicy_SELECTION_POLICY_LEAST_LOADED:
		return LeastLoaded(agents)
	case pb.SelectionPolicy_SELECTION_POLICY_RANDOM:
		s.mu.Lock()
		selected := agents[s.random.Intn(len(agents))]
		s.mu.Unlock()
		return selected
	default:
		return FirstAvailable(agents)
	}
}

func (s *Selector) roundRobin(agents []*pb.AgentDescriptor) *pb.AgentDescriptor {
	ids := make([]string, 0, len(agents))
	byID := make(map[string]*pb.AgentDescriptor, len(agents))
	for _, agent := range agents {
		ids = append(ids, agent.AgentId)
		byID[agent.AgentId] = agent
	}
	sort.Strings(ids)
	key := strings.Join(ids, "\x00")
	s.mu.Lock()
	index := s.cursors[key] % uint64(len(ids))
	s.cursors[key]++
	s.mu.Unlock()
	return byID[ids[index]]
}

// FirstAvailable preserva o baseline: o Registry já fornece ordem estável.
func FirstAvailable(agents []*pb.AgentDescriptor) *pb.AgentDescriptor {
	if len(agents) == 0 {
		return nil
	}
	return agents[0]
}

// LeastLoaded usa load, depois quantidade de tasks e agent_id como desempates.
func LeastLoaded(agents []*pb.AgentDescriptor) *pb.AgentDescriptor {
	if len(agents) == 0 {
		return nil
	}
	selected := agents[0]
	for _, candidate := range agents[1:] {
		if candidate.Load < selected.Load ||
			(candidate.Load == selected.Load && candidate.CurrentTaskCount < selected.CurrentTaskCount) ||
			(candidate.Load == selected.Load && candidate.CurrentTaskCount == selected.CurrentTaskCount && candidate.AgentId < selected.AgentId) {
			selected = candidate
		}
	}
	return selected
}
