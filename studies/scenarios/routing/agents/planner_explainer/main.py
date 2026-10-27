"""Planejador de missão e explicador: duas capacidades LLM em um agente do SDK.

``ROUTING_DEMO=1`` (ou ``demo=True``) troca o provedor pelo substituto
determinístico; o restante do agente é o mesmo.
"""
import os

from ariadne_sdk import LlmAgent

from studies.scenarios.routing.agents.planner_explainer.capabilities import capabilities


def planner_explainer(demo=None, **options):
    if demo is None:
        demo = os.getenv("ROUTING_DEMO", "0") == "1"
    handlers = capabilities()
    configuration = dict(
        agent_id=os.getenv("AGENT_ID", "planner-explainer-01"),
        name=os.getenv("AGENT_NAME", "Planner and Explainer"),
        port=int(os.getenv("AGENT_PORT", "60056")),
        capabilities=[handler.name for handler in handlers],
        handlers=handlers,
    )
    if demo:
        from studies.scenarios.routing.agents.planner_explainer.substitute import DemoClient, DemoLlmAgent
        configuration.update(openai_client=DemoClient(), runtime="python-sdk-demo")
        return DemoLlmAgent.from_env(**(configuration | options))
    return LlmAgent.from_env(**(configuration | options))


if __name__ == "__main__":
    planner_explainer().run()
