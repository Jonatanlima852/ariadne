package workflow

import (
	"fmt"
	"sync"

	"google.golang.org/protobuf/proto"

	pb "ariadne/runtime/gen/go/contract/v1"
)

type Store interface {
	Create(*pb.WorkflowResult) error
	Get(runID string) (*pb.WorkflowResult, error)
	MarkRunning(runID string) error
	SaveStep(runID string, step *pb.WorkflowStepResult) error
	Complete(runID string, result *pb.WorkflowResult) error
}

func (s *InMemoryStore) MarkRunning(runID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	result, exists := s.runs[runID]
	if !exists {
		return fmt.Errorf("workflow run not found: %s", runID)
	}
	result.Status = pb.WorkflowStatus_WORKFLOW_STATUS_RUNNING
	return nil
}

type InMemoryStore struct {
	mu   sync.RWMutex
	runs map[string]*pb.WorkflowResult
}

func NewInMemoryStore() *InMemoryStore {
	return &InMemoryStore{runs: make(map[string]*pb.WorkflowResult)}
}

func (s *InMemoryStore) Create(result *pb.WorkflowResult) error {
	if result == nil || result.RunId == "" {
		return fmt.Errorf("workflow result and run_id are required")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.runs[result.RunId]; exists {
		return fmt.Errorf("workflow run already exists: %s", result.RunId)
	}
	s.runs[result.RunId] = proto.Clone(result).(*pb.WorkflowResult)
	return nil
}

func (s *InMemoryStore) Get(runID string) (*pb.WorkflowResult, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	result, exists := s.runs[runID]
	if !exists {
		return nil, fmt.Errorf("workflow run not found: %s", runID)
	}
	return proto.Clone(result).(*pb.WorkflowResult), nil
}

func (s *InMemoryStore) SaveStep(runID string, step *pb.WorkflowStepResult) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	result, exists := s.runs[runID]
	if !exists {
		return fmt.Errorf("workflow run not found: %s", runID)
	}
	result.StepResults = append(result.StepResults, proto.Clone(step).(*pb.WorkflowStepResult))
	result.Status = pb.WorkflowStatus_WORKFLOW_STATUS_RUNNING
	return nil
}

func (s *InMemoryStore) Complete(runID string, result *pb.WorkflowResult) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.runs[runID]; !exists {
		return fmt.Errorf("workflow run not found: %s", runID)
	}
	s.runs[runID] = proto.Clone(result).(*pb.WorkflowResult)
	return nil
}
