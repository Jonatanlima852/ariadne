package store

import (
	"fmt"
	"sort"
	"sync"
	"time"

	"google.golang.org/protobuf/types/known/timestamppb"
	pb "ariadne/runtime/gen/go/contract/v1"
)

// AgentStore mantém os agentes registrados em memória.
type AgentStore struct {
	mu            sync.RWMutex
	agents        map[string]*pb.AgentDescriptor
	healthByAgent map[string]HealthRecord
}

// HealthRecord guarda o estado de saúde recebido pelo Registry.
// LastHeartbeatAt usa o relógio do Registry, não o timestamp do agente.
type HealthRecord struct {
	LastHeartbeatAt  time.Time
	CurrentTaskCount int32
	Load             float64
	Details          string
}

// HealthTransition descreve uma mudança de estado produzida pelo detector.
type HealthTransition struct {
	AgentID string
	From    pb.AgentStatus
	To      pb.AgentStatus
}

func New() *AgentStore {
	return &AgentStore{
		agents:        make(map[string]*pb.AgentDescriptor),
		healthByAgent: make(map[string]HealthRecord),
	}
}

func (st *AgentStore) Save(agent *pb.AgentDescriptor) {
	st.mu.Lock()
	defer st.mu.Unlock()

	now := timestamppb.New(time.Now())
	if _, exists := st.agents[agent.AgentId]; !exists {
		agent.CreatedAt = now
	}
	agent.UpdatedAt = now
	st.agents[agent.AgentId] = agent
	st.healthByAgent[agent.AgentId] = HealthRecord{LastHeartbeatAt: time.Now()}
}

func (st *AgentStore) Delete(agentID string) error {
	st.mu.Lock()
	defer st.mu.Unlock()

	if _, exists := st.agents[agentID]; !exists {
		return fmt.Errorf("agent %q not found", agentID)
	}
	delete(st.agents, agentID)
	delete(st.healthByAgent, agentID)
	return nil
}

func (st *AgentStore) Get(agentID string) (*pb.AgentDescriptor, error) {
	st.mu.RLock()
	defer st.mu.RUnlock()

	agent, exists := st.agents[agentID]
	if !exists {
		return nil, fmt.Errorf("agent %q not found", agentID)
	}
	return agent, nil
}

// List retorna todos os agentes que satisfazem o filtro.
// Se requiredCapabilities estiver vazio, retorna todos os agentes não-DEAD.
func (st *AgentStore) List(requiredCapabilities []string, statusFilter pb.AgentStatus) []*pb.AgentDescriptor {
	st.mu.RLock()
	defer st.mu.RUnlock()

	var result []*pb.AgentDescriptor
	for _, agent := range st.agents {
		if agent.Status == pb.AgentStatus_AGENT_STATUS_DEAD {
			continue
		}
		if statusFilter != pb.AgentStatus_AGENT_STATUS_UNKNOWN && agent.Status != statusFilter {
			continue
		}
		if !hasAllCapabilities(agent, requiredCapabilities) {
			continue
		}
		result = append(result, agent)
	}
	sort.Slice(result, func(i, j int) bool {
		return result[i].AgentId < result[j].AgentId
	})
	return result
}

func (st *AgentStore) UpdateHealth(health *pb.HealthStatus) error {
	st.mu.Lock()
	defer st.mu.Unlock()

	agent, exists := st.agents[health.AgentId]
	if !exists {
		return fmt.Errorf("agent %q not found", health.AgentId)
	}
	now := time.Now()
	agent.Status = health.Status
	agent.CurrentTaskCount = health.CurrentTaskCount
	agent.Load = health.Load
	agent.UpdatedAt = timestamppb.New(now)
	st.healthByAgent[health.AgentId] = HealthRecord{
		LastHeartbeatAt:  now,
		CurrentTaskCount: health.CurrentTaskCount,
		Load:             health.Load,
		Details:          health.Details,
	}
	return nil
}

func (st *AgentStore) GetHealth(agentID string) (HealthRecord, error) {
	st.mu.RLock()
	defer st.mu.RUnlock()

	health, exists := st.healthByAgent[agentID]
	if !exists {
		return HealthRecord{}, fmt.Errorf("agent %q not found", agentID)
	}
	return health, nil
}

// DetectFailures aplica os timeouts usando o instante recebido do chamador.
// O parâmetro explícito facilita testes determinísticos sem sleeps.
func (st *AgentStore) DetectFailures(now time.Time, suspectedTimeout, deadTimeout time.Duration) []HealthTransition {
	st.mu.Lock()
	defer st.mu.Unlock()

	var transitions []HealthTransition
	for agentID, agent := range st.agents {
		health, exists := st.healthByAgent[agentID]
		if !exists {
			continue
		}

		elapsed := now.Sub(health.LastHeartbeatAt)
		target := agent.Status
		switch {
		case elapsed > deadTimeout:
			target = pb.AgentStatus_AGENT_STATUS_DEAD
		case elapsed > suspectedTimeout && agent.Status != pb.AgentStatus_AGENT_STATUS_DEAD:
			target = pb.AgentStatus_AGENT_STATUS_SUSPECTED
		}

		if target == agent.Status {
			continue
		}
		previous := agent.Status
		agent.Status = target
		agent.UpdatedAt = timestamppb.New(now)
		transitions = append(transitions, HealthTransition{
			AgentID: agentID,
			From:    previous,
			To:      target,
		})
	}
	return transitions
}

// hasAllCapabilities verifica se o agente possui todas as capabilities pedidas.
func hasAllCapabilities(agent *pb.AgentDescriptor, required []string) bool {
	if len(required) == 0 {
		return true
	}
	have := make(map[string]bool, len(agent.Capabilities))
	for _, cap := range agent.Capabilities {
		have[cap.CapabilityId] = true
	}
	for _, req := range required {
		if !have[req] {
			return false
		}
	}
	return true
}
