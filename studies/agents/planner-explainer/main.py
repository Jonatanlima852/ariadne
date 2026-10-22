"""Compõe capacidades reutilizáveis; o SDK administra o agente e o provedor."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../sdk/python/src"))

from ariadne_sdk import LlmAgent
from workflow_capabilities import workflow_capabilities
from studies.scenarios.logistics.agents.mission_assistant import mission_capabilities


def planner_explainer(**options):
    handlers = [*workflow_capabilities(), *mission_capabilities()]
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
