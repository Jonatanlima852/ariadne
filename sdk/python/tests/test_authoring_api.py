import os
import unittest
from unittest.mock import patch

from google.protobuf import struct_pb2
from pydantic import BaseModel

from contract.v1 import contract_pb2
from ariadne_sdk import BdiAgent, LlmAgent, Prompt, llm_capability, plan


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
    capabilities = ["choose"]
    beliefs = {"best": "B"}

    def desire(self, received):
        return {"destination": received.payload["destination"]}

    @plan(name="expensive")
    def expensive(self, desire, beliefs):
        return {
            "cost": 10,
            "reasoning_summary": "mais caro",
            "choice": "A",
        }

    @plan(name="cheap")
    def cheap(self, desire, beliefs):
        return {
            "cost": 1,
            "reasoning_summary": "menor custo",
            "choice": beliefs["best"],
        }


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
    def test_bdi_discovers_decorated_plans_and_selects_lowest_cost(self):
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
        evaluated = list(result.metadata["evaluated_plans"])
        self.assertEqual([item["name"] for item in evaluated], ["cheap", "expensive"])
        self.assertTrue(all(item["applicable"] for item in evaluated))

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
