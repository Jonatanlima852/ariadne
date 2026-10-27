package server

import (
	"context"
	"testing"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/registry/internal/store"
)

func registration(version string) *pb.RegisterAgentRequest {
	return &pb.RegisterAgentRequest{Agent: &pb.AgentDescriptor{AgentId: "agent", ContractVersion: version}}
}

func TestRegisterAgentAcceptsCompatibleContractMajor(t *testing.T) {
	response, err := New(store.New()).RegisterAgent(context.Background(), registration("2.1.3"))
	if err != nil || !response.Success {
		t.Fatalf("response=%v error=%v", response, err)
	}
}

func TestRegisterAgentRejectsMissingOrUnsupportedContractVersion(t *testing.T) {
	for _, version := range []string{"", "0.1.0", "1.0.0", "3.0.0", "invalid"} {
		_, err := New(store.New()).RegisterAgent(context.Background(), registration(version))
		if status.Code(err) != codes.FailedPrecondition {
			t.Fatalf("version %q error = %v", version, err)
		}
	}
}
