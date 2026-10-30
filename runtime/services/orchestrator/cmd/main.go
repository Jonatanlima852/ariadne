package main

import (
	"log/slog"
	"net"
	"os"
	"time"

	"google.golang.org/grpc"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
	"ariadne/runtime/services/internal/startup"
	"ariadne/runtime/services/orchestrator/internal/server"
)

func main() {
	startup.ConfigureLogging()
	addr := os.Getenv("ORCHESTRATOR_ADDR")
	if addr == "" {
		addr = ":50052"
	}
	registryAddr := os.Getenv("REGISTRY_ADDR")
	if registryAddr == "" {
		registryAddr = "localhost:50051"
	}
	eventsPath := os.Getenv("EVENTS_PATH")
	if eventsPath == "" {
		eventsPath = "experiments/results/events.jsonl"
	}
	executionTimeout := 30 * time.Second
	if configured := os.Getenv("EXECUTION_TIMEOUT"); configured != "" {
		parsed, err := time.ParseDuration(configured)
		if err != nil || parsed <= 0 {
			slog.Error("invalid EXECUTION_TIMEOUT", "value", configured)
			os.Exit(1)
		}
		executionTimeout = parsed
	}

	logger, err := events.NewLogger(eventsPath)
	if err != nil {
		slog.Error("failed to open events file", "path", eventsPath, "err", err)
		os.Exit(1)
	}
	defer logger.Close()

	lis, err := net.Listen("tcp", addr)
	if err != nil {
		slog.Error("failed to listen", "addr", addr, "err", err)
		os.Exit(1)
	}

	grpcServer := grpc.NewServer(grpc.MaxRecvMsgSize(64 << 20)) // resultados de missão e históricos passam de 4 MB
	pb.RegisterOrchestratorServiceServer(grpcServer, server.New(registryAddr, logger, executionTimeout))

	slog.Info("orchestrator service started", "addr", addr, "registry", registryAddr, "execution_timeout", executionTimeout)
	if err := startup.Ready(lis.Addr().String()); err != nil {
		slog.Error("failed to publish address", "err", err)
		os.Exit(1)
	}
	if err := grpcServer.Serve(lis); err != nil {
		slog.Error("server stopped", "err", err)
		os.Exit(1)
	}
}
