"""Formatos de ações e missões exigidos das respostas linguísticas."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


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


