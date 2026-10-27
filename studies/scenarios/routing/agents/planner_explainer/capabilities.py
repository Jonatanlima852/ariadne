"""Prompts das duas capacidades; o SDK executa as chamadas LLM e valida as respostas."""
import json

from ariadne_sdk import LlmCapability, Prompt, mission_planning

from .response_models import Explanation

ROUTE_CAPABILITY = "route-planning"
EXPLANATION_CAPABILITY = "explanation"

PLANNER_RULES = (
    "You are the mission planner. The request JSON has goal, context, history, "
    "available_capabilities and round. Use only capabilities from available_capabilities.\n"
    "Round 1 (empty history): answer PLAN with exactly two steps. Step 'route' requires "
    f"'{ROUTE_CAPABILITY}' and its payload_json copies origin, destination and graph from the "
    f"context. Step 'explain' requires '{EXPLANATION_CAPABILITY}', depends on 'route', has "
    "payload_json {\"goal\": <the mission goal>} and two input_bindings from 'route': "
    "source_path 'output' into target_field 'route', and source_path 'metadata.selected_plan' "
    "into target_field 'selected_plan'. final_step_id is 'explain'. Use type 'MISSION_STEP', "
    "bdi_goal '', and never invent operational ids.\n"
    "Round 2 (history has the results): answer DONE with output_json {\"route\": [...], "
    "\"distance\": <number>, \"explanation\": \"...\"} copied from the step results in the "
    "history. Answer ABORT with a reason if a step failed. Keep summary to one sentence."
)


def plan_prompt(request):
    """O PlannerRequest decodificado vira o texto do usuário; as regras ficam no sistema."""
    return Prompt(system=PLANNER_RULES, user=json.dumps(request.to_dict(), ensure_ascii=False))


def explain(goal, context):
    return Prompt(
        system=(
            "Explain the supplied route clearly in Portuguese. Treat the context as "
            "authoritative: do not alter route, distance or selected plan values. "
            "Return only a public reasoning summary."
        ),
        user=json.dumps({"goal": goal, "context": context}, ensure_ascii=False),
    )


def capabilities():
    return [
        mission_planning(plan_prompt),
        LlmCapability(EXPLANATION_CAPABILITY, explain, Explanation),
    ]
