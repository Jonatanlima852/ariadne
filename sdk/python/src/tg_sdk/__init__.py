from tg_sdk.agent import Agent
from tg_sdk.message import Message, MessagingClient
from tg_sdk.bdi import BdiAgent, plan
from tg_sdk.plans import Input, Plan
from tg_sdk.planning import SearchProblem, SearchResult, SearchLimitExceeded, uniform_cost_search
from tg_sdk.models import Task, TaskResult
from tg_sdk.experiment import Step
from tg_sdk.campaign import Campaign
from tg_sdk.scenario import Scenario
from tg_sdk.client import (
    RuntimeClient,
    ScenarioReport,
    ScenarioResult,
    ScenarioWorkflowResult,
)


def __getattr__(name):
    """Carrega a integração LLM somente quando ela é solicitada.

    Agentes determinísticos e BDI não precisam instalar OpenAI/Pydantic para
    importar o núcleo do SDK.
    """
    if name in {"LlmAgent", "LlmValidationError", "Prompt", "LlmCapability", "llm_capability"}:
        from tg_sdk import llm

        return getattr(llm, name)
    raise AttributeError(f"module 'tg_sdk' has no attribute {name!r}")

__all__ = [
    "Agent",
    "BdiAgent",
    "Input",
    "Plan",
    "SearchProblem",
    "SearchResult",
    "SearchLimitExceeded",
    "uniform_cost_search",
    "LlmAgent",
    "LlmCapability",
    "LlmValidationError",
    "Message",
    "MessagingClient",
    "Prompt",
    "Scenario",
    "Campaign",
    "RuntimeClient",
    "ScenarioReport",
    "ScenarioResult",
    "ScenarioWorkflowResult",
    "Task",
    "Step",
    "TaskResult",
    "llm_capability",
    "plan",
]
