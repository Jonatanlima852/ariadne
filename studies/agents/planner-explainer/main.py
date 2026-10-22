import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../sdk/python/src"))

from pydantic import BaseModel, ConfigDict, Field

from ariadne_sdk import Prompt, llm_capability
from studies.scenarios.logistics.agents.mission_assistant import MissionAssistant


class ResultBindingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_step_id: str
    source_path: str
    target_field: str


class WorkflowStepDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    type: str
    goal: str
    payload_json: str = Field(description="JSON object serialized as a string")
    required_capabilities: list[str] = Field(min_length=1)
    depends_on: list[str]
    input_bindings: list[ResultBindingDraft]
    bdi_goal: str = ""


class WorkflowDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str
    final_step_id: str
    steps: list[WorkflowStepDraft] = Field(min_length=1, max_length=10)


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str
    reasoning_summary: str
    confidence: float = Field(ge=0.0, le=1.0)


def normalize_workflow(plan):
    steps = []
    for step in plan.steps:
        payload = json.loads(step.payload_json)
        if not isinstance(payload, dict):
            raise ValueError("payload_json must decode to an object")
        steps.append(
            {
                "step_id": step.step_id,
                "type": step.type,
                "goal": step.goal,
                "payload": payload,
                "required_capabilities": step.required_capabilities,
                "depends_on": step.depends_on,
                "input_bindings": [
                    binding.model_dump() for binding in step.input_bindings
                ],
                "bdi_goal": step.bdi_goal,
            }
        )
    return {
        "workflow_id": plan.workflow_id,
        "final_step_id": plan.final_step_id,
        "steps": steps,
    }


class PlannerExplainerAgent(MissionAssistant):
    capabilities = [
        "task-decomposition", "explanation", "logistics-plan",
        "logistics-interpret",
    ]
    default_agent_id = "planner-explainer-01"
    default_name = "Planner and Explainer"
    default_port = 60056

    @llm_capability(
        "task-decomposition",
        output_schema=WorkflowDraft,
        result_mapper=normalize_workflow,
    )
    def decompose(self, goal, context):
        return Prompt(
            system=(
                "Create a finite executable workflow DAG. Capabilities are short "
                "stable IDs such as route-planning, meeting-scheduling, echo, "
                "or explanation. Never use task-decomposition inside a step. "
                "For route requests, create exactly a route-planning step with "
                "step_id route followed by an explanation step with step_id "
                "explain, and make explain the final_step_id. Put origin and "
                "destination in the first "
                "payload_json, set bdi_goal, and bind its complete output to "
                "bdi_result plus metadata to bdi_metadata in the explanation "
                "payload. Bindings may read output, metadata, status or agent_id. "
                "Use at most 10 steps and depth 5. Never create operational IDs."
            ),
            user=goal,
        )

    @llm_capability("explanation", output_schema=Explanation)
    def explain(self, goal, context):
        return Prompt(
            system=(
                "Explain the supplied result clearly in Portuguese. Treat the "
                "context as authoritative: do not alter route, distance, or "
                "selected plan values. Return only a public reasoning summary."
            ),
            user=(
                f"Objetivo: {goal}\n"
                f"Contexto JSON: {json.dumps(context, ensure_ascii=False)}"
            ),
        )



if __name__ == "__main__":
    PlannerExplainerAgent.from_env().run()
