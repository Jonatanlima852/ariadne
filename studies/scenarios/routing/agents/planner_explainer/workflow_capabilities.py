"""Prompts e conversão das respostas; o SDK executa as chamadas LLM."""
import json
from ariadne_sdk import LlmCapability, Prompt
from .response_models import Explanation, WorkflowDraft


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


def decompose(goal, context):
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

def explain(goal, context):
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



def workflow_capabilities():
    return [
        LlmCapability("task-decomposition", decompose, WorkflowDraft, normalize_workflow),
        LlmCapability("explanation", explain, Explanation),
    ]
