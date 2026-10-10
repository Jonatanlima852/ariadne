from tg_sdk.agent import Agent
from tg_sdk.message import Message, MessagingClient
from tg_sdk.bdi import BdiAgent, plan
from tg_sdk.models import Task, TaskResult
from tg_sdk.experiment import Step
from tg_sdk.scenario import (
    Scenario,
    ScenarioReport,
    ScenarioResult,
    ScenarioWorkflowResult,
)


def __getattr__(name):
    """Carrega a integração LLM somente quando ela é solicitada.

    Agentes determinísticos e BDI não precisam instalar OpenAI/Pydantic para
    importar o núcleo do SDK.
    """
    if name in {"LlmAgent", "LlmValidationError", "Prompt", "llm_capability"}:
        from tg_sdk import llm

        return getattr(llm, name)
    raise AttributeError(f"module 'tg_sdk' has no attribute {name!r}")

__all__ = [
    "Agent",
    "BdiAgent",
    "LlmAgent",
    "LlmValidationError",
    "Message",
    "MessagingClient",
    "Prompt",
    "Scenario",
    "ScenarioReport",
    "ScenarioResult",
    "ScenarioWorkflowResult",
    "Task",
    "Step",
    "TaskResult",
    "llm_capability",
    "plan",
]
