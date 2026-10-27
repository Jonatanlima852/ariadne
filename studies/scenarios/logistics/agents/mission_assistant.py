"""Capacidades logísticas reutilizáveis, sem subclasse de agente."""
import json
from ariadne_sdk import LlmAgent, LlmCapability, Prompt
from studies.scenarios.logistics.agents.mission_models import LogisticsPlan, LogisticsInterpretation


def normalize_logistics_plan(plan):
    actions = []
    for declared in plan.actions:
        action = {"type": declared.type}
        if declared.type == "MOVE":
            action.update({"from": declared.origin, "to": declared.destination})
        elif declared.location:
            action["location"] = declared.location
        actions.append(action)
    return {
        "feasible": plan.feasible,
        "actions": actions,
        "rejection_reason": plan.rejection_reason,
    }


def logistics_plan(goal, context):
    return Prompt(
        system=(
            "You are the sole planner for a logistics robot. Produce a complete "
            "executable action sequence from the supplied world JSON and natural "
            "request. Respect graph edges, energy, elapsed minutes, forbidden and "
            "required locations, the locked F door, package/key locations, final "
            "battery and deadline. MOVE uses origin/destination; other actions use "
            "location. Never invent an edge. If no valid sequence exists, set "
            "feasible=false and return no actions. Do not assume an external "
            "validator or symbolic planner will repair your answer."
        ),
        user=(
            f"Natural request: {goal}\n"
            f"World JSON: {json.dumps(context.get('world'), sort_keys=True)}"
        ),
    )

def logistics_interpret(goal, context):
    return Prompt(
        system=(
            "Extract the logistics mission literally. Valid locations are A through "
            "H. Do not plan actions and do not weaken constraints. Percent battery "
            "maps to minimum_final_battery. If no forbidden/required places are "
            "stated, use empty lists. Return the explicit destination and deadline."
        ),
        user=goal,
    )


def mission_capabilities():
    return [
        LlmCapability("logistics-plan", logistics_plan, LogisticsPlan, normalize_logistics_plan),
        LlmCapability("logistics-interpret", logistics_interpret, LogisticsInterpretation),
    ]


def mission_assistant(**options):
    configuration = dict(name="mission-assistant", agent_id="mission-assistant-01",
                         handlers=mission_capabilities())
    return LlmAgent(**(configuration | options))
