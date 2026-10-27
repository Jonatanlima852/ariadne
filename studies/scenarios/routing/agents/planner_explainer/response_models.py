"""Formato validado da explicação. A decisão do planejador usa ``PlannerDecision`` do SDK."""
from pydantic import BaseModel, ConfigDict, Field


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str
    reasoning_summary: str
    confidence: float = Field(ge=0.0, le=1.0)
