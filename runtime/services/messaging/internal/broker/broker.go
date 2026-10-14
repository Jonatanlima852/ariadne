package broker

import (
	"fmt"
	"sync"
	"time"

	"google.golang.org/protobuf/proto"

	pb "ariadne/runtime/gen/go/contract/v1"
)

type Broker struct {
	mu          sync.Mutex
	backlog     map[string][]*pb.MessageEnvelope
	subscribers map[string]chan *pb.MessageEnvelope
}

func New() *Broker {
	return &Broker{backlog: make(map[string][]*pb.MessageEnvelope), subscribers: make(map[string]chan *pb.MessageEnvelope)}
}

func (b *Broker) Publish(message *pb.MessageEnvelope) error {
	if err := Validate(message, time.Now()); err != nil {
		return err
	}
	copy := proto.Clone(message).(*pb.MessageEnvelope)
	b.mu.Lock()
	defer b.mu.Unlock()
	if subscriber := b.subscribers[copy.ReceiverId]; subscriber != nil {
		select {
		case subscriber <- copy:
			return nil
		default:
			return fmt.Errorf("receiver stream is congested: %s", copy.ReceiverId)
		}
	}
	b.backlog[copy.ReceiverId] = append(b.backlog[copy.ReceiverId], copy)
	return nil
}

func (b *Broker) Subscribe(receiverID string) (<-chan *pb.MessageEnvelope, func(), error) {
	if receiverID == "" {
		return nil, nil, fmt.Errorf("receiver_id is required")
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if _, exists := b.subscribers[receiverID]; exists {
		return nil, nil, fmt.Errorf("receiver already has an active stream: %s", receiverID)
	}
	queued := b.backlog[receiverID]
	channel := make(chan *pb.MessageEnvelope, len(queued)+64)
	for _, message := range queued {
		if Validate(message, time.Now()) == nil {
			channel <- message
		}
	}
	delete(b.backlog, receiverID)
	b.subscribers[receiverID] = channel
	var once sync.Once
	cancel := func() {
		once.Do(func() {
			b.mu.Lock()
			if b.subscribers[receiverID] == channel {
				delete(b.subscribers, receiverID)
			}
			b.mu.Unlock()
		})
	}
	return channel, cancel, nil
}

func Validate(message *pb.MessageEnvelope, now time.Time) error {
	if message == nil {
		return fmt.Errorf("message is required")
	}
	if message.MessageId == "" {
		return fmt.Errorf("message_id is required")
	}
	if message.SenderId == "" {
		return fmt.Errorf("sender_id is required")
	}
	if message.ReceiverId == "" {
		return fmt.Errorf("receiver_id is required")
	}
	if message.Type == pb.MessageType_MESSAGE_TYPE_UNKNOWN {
		return fmt.Errorf("message type is required")
	}
	if message.Trace == nil || message.Trace.TraceId == "" {
		return fmt.Errorf("trace.trace_id is required")
	}
	if message.Timestamp == nil {
		return fmt.Errorf("timestamp is required")
	}
	if err := message.Timestamp.CheckValid(); err != nil {
		return fmt.Errorf("timestamp is invalid: %w", err)
	}
	if message.TtlMs > 0 && now.After(message.Timestamp.AsTime().Add(time.Duration(message.TtlMs)*time.Millisecond)) {
		return fmt.Errorf("message ttl expired")
	}
	return nil
}
