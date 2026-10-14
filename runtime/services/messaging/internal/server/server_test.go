package server

import (
	"context"
	"net"
	"sync"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/test/bufconn"
	"google.golang.org/protobuf/types/known/timestamppb"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
	"ariadne/runtime/services/messaging/internal/broker"
)

type memoryLogger struct {
	mu     sync.Mutex
	events []events.Event
	logged chan struct{}
}

func (l *memoryLogger) Log(event events.Event) {
	l.mu.Lock()
	l.events = append(l.events, event)
	l.mu.Unlock()
	l.logged <- struct{}{}
}

func TestMessagingServicePublishesStreamsAndCorrelates(t *testing.T) {
	listener := bufconn.Listen(1024 * 1024)
	grpcServer := grpc.NewServer()
	logger := &memoryLogger{logged: make(chan struct{}, 2)}
	pb.RegisterMessagingServiceServer(grpcServer, New(broker.New(), logger))
	go grpcServer.Serve(listener)
	defer grpcServer.Stop()
	connection, err := grpc.NewClient("passthrough:///bufnet", grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return listener.Dial() }))
	if err != nil {
		t.Fatal(err)
	}
	defer connection.Close()
	client := pb.NewMessagingServiceClient(connection)
	stream, err := client.StreamMessages(context.Background(), &pb.StreamMessagesRequest{ReceiverId: "agent-b"})
	if err != nil {
		t.Fatal(err)
	}
	message := &pb.MessageEnvelope{MessageId: "message-1", ConversationId: "conversation-1", CorrelationId: "correlation-1", SenderId: "agent-a", ReceiverId: "agent-b", Type: pb.MessageType_MESSAGE_TYPE_REQUEST, Timestamp: timestamppb.Now(), Trace: &pb.TraceContext{TraceId: "trace-1"}, TaskId: "task-1"}
	response, err := client.PublishMessage(context.Background(), &pb.PublishMessageRequest{Message: message})
	if err != nil {
		t.Fatal(err)
	}
	if !response.Ack.Accepted {
		t.Fatalf("ack = %v", response.Ack)
	}
	received, err := stream.Recv()
	if err != nil {
		t.Fatal(err)
	}
	if received.MessageId != message.MessageId || received.Trace.TraceId != "trace-1" || received.CorrelationId != "correlation-1" {
		t.Fatalf("received = %v", received)
	}
	<-logger.logged
	<-logger.logged
	logger.mu.Lock()
	defer logger.mu.Unlock()
	if len(logger.events) != 2 {
		t.Fatalf("events = %v", logger.events)
	}
	types := map[string]bool{logger.events[0].Type: true, logger.events[1].Type: true}
	if !types["MESSAGE_SENT"] || !types["MESSAGE_RECEIVED"] {
		t.Fatalf("events = %v", logger.events)
	}
}
