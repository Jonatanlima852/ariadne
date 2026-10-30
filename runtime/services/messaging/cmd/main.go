package main

import (
	"log/slog"
	"net"
	"os"

	"google.golang.org/grpc"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
	"ariadne/runtime/services/internal/startup"
	"ariadne/runtime/services/messaging/internal/broker"
	messageServer "ariadne/runtime/services/messaging/internal/server"
)

func main() {
	startup.ConfigureLogging()
	address := os.Getenv("MESSAGING_ADDR")
	if address == "" {
		address = ":50053"
	}
	eventsPath := os.Getenv("EVENTS_PATH")
	if eventsPath == "" {
		eventsPath = "experiments/results/message-events.jsonl"
	}
	logger, err := events.NewLogger(eventsPath)
	if err != nil {
		slog.Error("failed to open events file", "err", err)
		os.Exit(1)
	}
	defer logger.Close()
	listener, err := net.Listen("tcp", address)
	if err != nil {
		slog.Error("failed to listen", "err", err)
		os.Exit(1)
	}
	grpcServer := grpc.NewServer(grpc.MaxRecvMsgSize(64 << 20)) // resultados de missão e históricos passam de 4 MB
	pb.RegisterMessagingServiceServer(grpcServer, messageServer.New(broker.New(), logger))
	slog.Info("messaging service started", "addr", address)
	if err := startup.Ready(listener.Addr().String()); err != nil {
		slog.Error("failed to publish address", "err", err)
		os.Exit(1)
	}
	if err := grpcServer.Serve(listener); err != nil {
		slog.Error("server stopped", "err", err)
		os.Exit(1)
	}
}
