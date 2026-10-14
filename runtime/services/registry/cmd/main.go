package main

import (
	"log/slog"
	"net"
	"os"
	"time"

	"google.golang.org/grpc"
	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/startup"
	"ariadne/runtime/services/registry/internal/server"
	"ariadne/runtime/services/registry/internal/store"
)

func main() {
	startup.ConfigureLogging()
	addr := os.Getenv("REGISTRY_ADDR")
	if addr == "" {
		addr = ":50051"
	}

	lis, err := net.Listen("tcp", addr)
	if err != nil {
		slog.Error("failed to listen", "addr", addr, "err", err)
		os.Exit(1)
	}

	scanInterval := durationEnv("FAILURE_SCAN_INTERVAL", time.Second)
	suspectedTimeout := durationEnv("SUSPECTED_TIMEOUT", 10*time.Second)
	deadTimeout := durationEnv("DEAD_TIMEOUT", 20*time.Second)
	if scanInterval <= 0 || suspectedTimeout <= 0 || deadTimeout <= suspectedTimeout {
		slog.Error("invalid failure detector configuration",
			"scan_interval", scanInterval,
			"suspected_timeout", suspectedTimeout,
			"dead_timeout", deadTimeout,
		)
		os.Exit(1)
	}

	agentStore := store.New()
	go runFailureDetector(agentStore, scanInterval, suspectedTimeout, deadTimeout)

	grpcServer := grpc.NewServer()
	pb.RegisterRegistryServiceServer(grpcServer, server.New(agentStore))

	slog.Info("registry service started",
		"addr", addr,
		"failure_scan_interval", scanInterval,
		"suspected_timeout", suspectedTimeout,
		"dead_timeout", deadTimeout,
	)
	if err := startup.Ready(lis.Addr().String()); err != nil {
		slog.Error("failed to publish address", "err", err)
		os.Exit(1)
	}
	if err := grpcServer.Serve(lis); err != nil {
		slog.Error("server stopped", "err", err)
		os.Exit(1)
	}
}

func durationEnv(name string, fallback time.Duration) time.Duration {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	duration, err := time.ParseDuration(value)
	if err != nil {
		slog.Error("invalid duration", "variable", name, "value", value, "err", err)
		os.Exit(1)
	}
	return duration
}

func runFailureDetector(agentStore *store.AgentStore, interval, suspectedTimeout, deadTimeout time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for now := range ticker.C {
		for _, transition := range agentStore.DetectFailures(now, suspectedTimeout, deadTimeout) {
			event := "AGENT_SUSPECTED"
			if transition.To == pb.AgentStatus_AGENT_STATUS_DEAD {
				event = "AGENT_DEAD"
			}
			slog.Warn("health transition",
				"event", event,
				"agent_id", transition.AgentID,
				"previous", transition.From.String(),
				"current", transition.To.String(),
			)
		}
	}
}
