package server

import (
	"context"

	"github.com/google/uuid"
	"google.golang.org/grpc"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
	"ariadne/runtime/services/messaging/internal/broker"
)

type EventLogger interface{ Log(events.Event) }

type Server struct {
	pb.UnimplementedMessagingServiceServer
	broker *broker.Broker
	logger EventLogger
}

func New(messageBroker *broker.Broker, logger EventLogger) *Server {
	return &Server{broker: messageBroker, logger: logger}
}

func (s *Server) PublishMessage(_ context.Context, request *pb.PublishMessageRequest) (*pb.PublishMessageResponse, error) {
	message := request.GetMessage()
	if err := s.broker.Publish(message); err != nil {
		return &pb.PublishMessageResponse{Ack: &pb.MessageAck{MessageId: message.GetMessageId(), Error: &pb.ErrorInfo{Code: pb.ErrorCode_ERROR_CODE_MESSAGE_DELIVERY_FAILED, Message: err.Error()}}}, nil
	}
	s.log(message, "MESSAGE_SENT")
	return &pb.PublishMessageResponse{Ack: &pb.MessageAck{MessageId: message.MessageId, Accepted: true}}, nil
}

func (s *Server) StreamMessages(request *pb.StreamMessagesRequest, stream grpc.ServerStreamingServer[pb.MessageEnvelope]) error {
	messages, cancel, err := s.broker.Subscribe(request.GetReceiverId())
	if err != nil {
		return err
	}
	defer cancel()
	for {
		select {
		case <-stream.Context().Done():
			return nil
		case message := <-messages:
			if err := stream.Send(message); err != nil {
				return err
			}
			s.log(message, "MESSAGE_RECEIVED")
		}
	}
}

func (s *Server) log(message *pb.MessageEnvelope, eventType string) {
	if s.logger == nil || message == nil {
		return
	}
	s.logger.Log(events.Event{EventID: uuid.NewString(), TaskID: message.TaskId, Type: eventType, AgentID: message.ReceiverId, TraceID: message.Trace.GetTraceId(), Details: "message_id=" + message.MessageId})
}
