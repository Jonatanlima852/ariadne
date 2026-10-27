from ariadne_sdk.agent import Agent
from ariadne_sdk.message import Message, MessagingClient
from ariadne_sdk.bdi import BdiAgent, plan
from ariadne_sdk.plans import Input, Plan
from ariadne_sdk.planning import SearchProblem, SearchResult, SearchLimitExceeded, uniform_cost_search
from ariadne_sdk.models import Task, TaskResult
from ariadne_sdk.experiment import Step
from ariadne_sdk.campaign import Campaign
from ariadne_sdk.scenario import Scenario
from ariadne_sdk.client import (
    RuntimeClient,
    ScenarioReport,
    ScenarioResult,
    ScenarioWorkflowResult,
)


_DELIBERATION = {
    "BeliefBase", "Deliberation", "DeliberationResult", "Goal", "GoalFailure", "GoalPlan",
    "achieve", "act", "forget", "observe",
}


def __getattr__(name):
    """Carrega a integração LLM somente quando ela é solicitada.

    Agentes determinísticos e BDI não precisam instalar OpenAI/Pydantic para
    importar o núcleo do SDK.
    """
    if name in {"LlmAgent", "LlmValidationError", "Prompt", "LlmCapability", "llm_capability"}:
        from ariadne_sdk import llm

        return getattr(llm, name)
    if name in _DELIBERATION:
        from ariadne_sdk import deliberation

        return getattr(deliberation, name)
    raise AttributeError(f"module 'ariadne_sdk' has no attribute {name!r}")

__all__ = [
    "Agent",
    "BdiAgent",
    "BeliefBase",
    "Deliberation",
    "DeliberationResult",
    "Goal",
    "GoalFailure",
    "GoalPlan",
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
    "achieve",
    "act",
    "forget",
    "llm_capability",
    "observe",
    "plan",
]
