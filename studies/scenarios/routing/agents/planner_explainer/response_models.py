"""Formatos validados das respostas de decomposição e explicação."""
from pydantic import BaseModel, ConfigDict, Field


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


