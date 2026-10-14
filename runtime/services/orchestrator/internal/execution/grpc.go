package execution

import (
	"context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "ariadne/runtime/gen/go/contract/v1"
)

type GRPCDiscoverer struct{ RegistryAddr string }

func (d GRPCDiscoverer) Discover(ctx context.Context, capabilities []string) ([]*pb.AgentDescriptor, error) {
	conn, err := grpc.NewClient(d.RegistryAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, err
	}
	defer conn.Close()
	response, err := pb.NewRegistryServiceClient(conn).DiscoverAgents(ctx, &pb.DiscoverAgentsRequest{
		RequiredCapabilities: capabilities,
	})
	if err != nil {
		return nil, err
	}
	return response.Agents, nil
}

type GRPCRunner struct{}

func (GRPCRunner) Execute(ctx context.Context, agent *pb.AgentDescriptor, task *pb.Task) (*pb.TaskResult, error) {
	conn, err := grpc.NewClient(agent.Endpoint.Address, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, err
	}
	defer conn.Close()
	response, err := pb.NewAgentServiceClient(conn).ExecuteTask(ctx, &pb.ExecuteTaskRequest{Task: task})
	if err != nil {
		return nil, err
	}
	return response.Result, nil
}
