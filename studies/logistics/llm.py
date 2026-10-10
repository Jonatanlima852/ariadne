"""Agente linguístico do estudo; prompts e schemas preservados."""
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from tg_sdk import LlmAgent, Prompt, llm_capability


class LogisticsAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "PICK_UP_PACKAGE", "PICK_UP_KEY", "RECHARGE", "UNLOCK_DOOR",
        "MOVE", "DELIVER_PACKAGE",
    ]
    origin: str = ""
    destination: str = ""
    location: str = ""


class LogisticsPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feasible: bool
    actions: list[LogisticsAction]
    rejection_reason: str = ""


class LogisticsMission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str
    forbidden_locations: list[str]
    required_locations: list[str]
    minimum_final_battery: int = Field(ge=0, le=100)
    deadline_minutes: int = Field(gt=0)


class LogisticsInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission: LogisticsMission


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


class LogisticsLlmAgent(LlmAgent):
    capabilities = ["logistics-plan", "logistics-interpret"]
    default_agent_id = "llm-agent-01"

    @llm_capability(
        "logistics-plan",
        output_schema=LogisticsPlan,
        result_mapper=normalize_logistics_plan,
    )
    def logistics_plan(self, goal, context):
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

    @llm_capability("logistics-interpret", output_schema=LogisticsInterpretation)
    def logistics_interpret(self, goal, context):
        return Prompt(
            system=(
                "Extract the logistics mission literally. Valid locations are A through "
                "H. Do not plan actions and do not weaken constraints. Percent battery "
                "maps to minimum_final_battery. If no forbidden/required places are "
                "stated, use empty lists. Return the explicit destination and deadline."
            ),
            user=goal,
        )
