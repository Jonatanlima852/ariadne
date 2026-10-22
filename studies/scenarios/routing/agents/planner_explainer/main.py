"""Compõe capacidades reutilizáveis; o SDK administra o agente e o provedor."""
import os


from ariadne_sdk import LlmAgent
from studies.scenarios.routing.agents.planner_explainer.workflow_capabilities import workflow_capabilities


def planner_explainer(**options):
    handlers = workflow_capabilities()
    configuration = dict(
        agent_id=os.getenv("AGENT_ID", "planner-explainer-01"),
        name=os.getenv("AGENT_NAME", "Planner and Explainer"),
        port=int(os.getenv("AGENT_PORT", "60056")),
        capabilities=[handler.name for handler in handlers],
        handlers=handlers,
    )
    return LlmAgent.from_env(**(configuration | options))


if __name__ == "__main__":
    planner_explainer().run()
