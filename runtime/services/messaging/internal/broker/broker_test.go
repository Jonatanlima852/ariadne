package broker

import (
	"testing"
	"time"

	"google.golang.org/protobuf/types/known/timestamppb"

	pb "ariadne/runtime/gen/go/contract/v1"
)

func validMessage(id string) *pb.MessageEnvelope {
	return &pb.MessageEnvelope{MessageId: id, ConversationId: "conversation", CorrelationId: "correlation", SenderId: "agent-a", ReceiverId: "agent-b", Type: pb.MessageType_MESSAGE_TYPE_INFORM, Timestamp: timestamppb.Now(), Trace: &pb.TraceContext{TraceId: "trace"}}
}

func TestBrokerDeliversQueuedAndLiveMessagesInOrder(t *testing.T) {
	messageBroker := New()
	if err := messageBroker.Publish(validMessage("queued")); err != nil {
		t.Fatal(err)
	}
	messages, cancel, err := messageBroker.Subscribe("agent-b")
	if err != nil {
		t.Fatal(err)
	}
	defer cancel()
	if err := messageBroker.Publish(validMessage("live")); err != nil {
		t.Fatal(err)
	}
	if first, second := <-messages, <-messages; first.MessageId != "queued" || second.MessageId != "live" {
		t.Fatalf("messages = %s, %s", first.MessageId, second.MessageId)
	}
}

func TestBrokerRejectsInvalidExpiredAndDuplicateSubscriptions(t *testing.T) {
	messageBroker := New()
	if err := messageBroker.Publish(&pb.MessageEnvelope{}); err == nil {
		t.Fatal("invalid message accepted")
	}
	expired := validMessage("expired")
	expired.Timestamp = timestamppb.New(time.Now().Add(-time.Second))
	expired.TtlMs = 1
	if err := messageBroker.Publish(expired); err == nil {
		t.Fatal("expired message accepted")
	}
	_, cancel, err := messageBroker.Subscribe("agent-b")
	if err != nil {
		t.Fatal(err)
	}
	defer cancel()
	if _, _, err := messageBroker.Subscribe("agent-b"); err == nil {
		t.Fatal("duplicate subscription accepted")
	}
}
