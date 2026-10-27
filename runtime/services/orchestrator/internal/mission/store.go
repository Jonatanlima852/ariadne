package mission

import (
	"fmt"
	"sync"

	"google.golang.org/protobuf/proto"

	pb "ariadne/runtime/gen/go/contract/v1"
)

// Store guarda o estado observável de cada missão. O Runner salva uma cópia
// a cada transição, então GetMission enxerga a missão enquanto ela roda.
type Store interface {
	Save(*pb.MissionResult) error
	Get(missionID string) (*pb.MissionResult, error)
}

type InMemoryStore struct {
	mu       sync.RWMutex
	missions map[string]*pb.MissionResult
}

func NewInMemoryStore() *InMemoryStore {
	return &InMemoryStore{missions: make(map[string]*pb.MissionResult)}
}

func (s *InMemoryStore) Save(result *pb.MissionResult) error {
	if result == nil || result.MissionId == "" {
		return fmt.Errorf("mission result and mission_id are required")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.missions[result.MissionId] = proto.Clone(result).(*pb.MissionResult)
	return nil
}

func (s *InMemoryStore) Get(missionID string) (*pb.MissionResult, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	result, exists := s.missions[missionID]
	if !exists {
		return nil, fmt.Errorf("mission not found: %s", missionID)
	}
	return proto.Clone(result).(*pb.MissionResult), nil
}
