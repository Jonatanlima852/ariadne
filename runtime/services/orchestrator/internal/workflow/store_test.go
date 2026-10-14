package workflow

import (
	"testing"

	pb "ariadne/runtime/gen/go/contract/v1"
)

func TestInMemoryStoreReturnsIndependentCopies(t *testing.T) {
	store := NewInMemoryStore()
	created := &pb.WorkflowResult{RunId: "run-1", WorkflowId: "workflow-1"}
	if err := store.Create(created); err != nil {
		t.Fatal(err)
	}
	created.WorkflowId = "mutated"

	stored, err := store.Get("run-1")
	if err != nil {
		t.Fatal(err)
	}
	if stored.WorkflowId != "workflow-1" {
		t.Fatalf("workflow_id = %q", stored.WorkflowId)
	}
	stored.WorkflowId = "mutated-again"
	storedAgain, _ := store.Get("run-1")
	if storedAgain.WorkflowId != "workflow-1" {
		t.Fatal("Get exposed mutable store state")
	}
}
