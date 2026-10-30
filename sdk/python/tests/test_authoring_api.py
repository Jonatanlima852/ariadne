import os
import unittest
from unittest.mock import patch

from google.protobuf import struct_pb2
from pydantic import BaseModel

from contract.v1 import contract_pb2
from ariadne_sdk import BdiAgent, GoalPlan, Input, LlmAgent, Prompt, llm_capability


def task(*capabilities, payload=None):
    data = struct_pb2.Struct()
    data.update(payload or {})
    return contract_pb2.Task(
        task_id="task-1",
        goal="test",
        payload=data,
        required_capabilities=capabilities,
        trace=contract_pb2.TraceContext(trace_id="trace-1"),
    )


class ExampleBdiAgent(BdiAgent):
    """Subclasse só para configuração (from_env); o raciocínio é dos GoalPlans."""

    capabilities = ["choose"]

    def __init__(self, **options):
        super().__init__(
            beliefs=lambda received: {"best": "B", "destination": received.payload["destination"]},
            goal="choose",
            plans=[
                GoalPlan("expensive", lambda beliefs, goal: {"choice": "A"}, goal="choose", cost=10),
                GoalPlan("cheap", lambda beliefs, goal: {"choice": beliefs["best"]}, goal="choose", cost=1),
            ],
            **options,
        )


class Explanation(BaseModel):
    text: str
    context: dict


class _FakeResponses:
    def parse(self, *, text_format, **kwargs):
        parsed = text_format(text="test", context={"route": "A-D"})
        return type("FakeResponse", (), {"output_parsed": parsed})()


class FakeOpenAI:
    responses = _FakeResponses()


class ExampleLlmAgent(LlmAgent):
    capabilities = ["explain"]

    @llm_capability("explain", output_schema=Explanation)
    def explain(self, goal, context):
        return Prompt(system="Explain.", user=goal)


class AuthoringApiTests(unittest.TestCase):
    def test_bdi_selects_lowest_cost_goal_plan_and_reports_the_trace(self):
        agent = ExampleBdiAgent(
            agent_id="bdi",
            name="BDI",
            capabilities=ExampleBdiAgent.capabilities,
            host="localhost",
            port=1,
            registry_addr="localhost:50051",
        )

        result = agent.execute_task(task("choose", payload={"destination": "D"}))

        self.assertEqual(result.status, contract_pb2.TASK_STATUS_COMPLETED)
        self.assertEqual(result.metadata["selected_plan"], "cheap")
        self.assertEqual(result.output["choice"], "B")
        self.assertEqual(result.bdi.trace.cycle_count, 1)
        self.assertEqual(result.bdi.trace.cycles[0].selected_plan, "cheap")

    def test_bdi_requires_plans_of_one_kind(self):
        with self.assertRaises(ValueError):
            BdiAgent(name="none", capabilities=["x"])
        with self.assertRaises(ValueError):
            BdiAgent(name="mixed", capabilities=["x"], beliefs=Input(), desire=Input(),
                     plans=[GoalPlan("g", lambda b, g: {})])

    def test_llm_dispatches_capability_and_builds_contract_result(self):
        agent = ExampleLlmAgent(
            agent_id="llm",
            name="LLM",
            capabilities=ExampleLlmAgent.capabilities,
            host="localhost",
            port=2,
            registry_addr="localhost:50051",
            openai_client=FakeOpenAI(),
            model="test-model",
        )

        result = agent.execute_task(task("explain", payload={"route": "A-D"}))

        self.assertEqual(result.status, contract_pb2.TASK_STATUS_COMPLETED)
        self.assertEqual(result.output["text"], "test")
        self.assertEqual(result.metadata["provider"], "openai")
        self.assertEqual(result.metadata["model"], "test-model")

    def test_from_env_uses_declared_capabilities_and_runtime_configuration(self):
        with patch.dict(
            os.environ,
            {
                "AGENT_ID": "configured-agent",
                "AGENT_PORT": "61234",
                "REGISTRY_ADDR": "registry:50051",
            },
            clear=False,
        ):
            agent = ExampleBdiAgent.from_env()

        self.assertEqual(agent.agent_id, "configured-agent")
        self.assertEqual(agent.port, 61234)
        self.assertEqual(agent.capabilities, ["choose"])


if __name__ == "__main__":
    unittest.main()


class AgentKindDescriptorTests(unittest.TestCase):
    def test_descriptor_declares_kind_per_agent_family(self):
        from contract.v1 import contract_pb2
        from ariadne_sdk import Agent, BdiAgent, GoalPlan
        from ariadne_sdk.agent import agent_kind_name

        plain = Agent(agent_id="det", capabilities=["echo"], handler=lambda goal, payload: {})
        bdi = BdiAgent(agent_id="bdi", capabilities=["x"], plans=[GoalPlan("p", lambda b, g: {"ok": True}, goal="g")])
        hybrid = Agent(agent_id="hyb", capabilities=["echo"], handler=lambda goal, payload: {}, kind="hybrid")

        self.assertEqual(plain.build_descriptor().kind, contract_pb2.AGENT_KIND_DETERMINISTIC)
        self.assertEqual(bdi.build_descriptor().kind, contract_pb2.AGENT_KIND_BDI)
        self.assertEqual(hybrid.build_descriptor().kind, contract_pb2.AGENT_KIND_HYBRID)
        self.assertEqual(agent_kind_name("AGENT_KIND_LLM"), "llm")
        with self.assertRaises(ValueError):
            agent_kind_name("oracle")
