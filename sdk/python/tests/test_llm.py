import unittest

from google.protobuf import struct_pb2
from pydantic import BaseModel, ConfigDict

from contract.v1 import contract_pb2
from ariadne_sdk import LlmAgent, Prompt, llm_capability


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class UnsafeOutput(BaseModel):
    value: str
    task_id: str


class _FakeResponses:
    def __init__(self, parsed, usage=None):
        self.parsed = parsed
        self.usage = usage
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return type(
            "Response",
            (),
            {"output_parsed": self.parsed, "usage": self.usage},
        )()


class _FakeOpenAI:
    def __init__(self, parsed, usage=None):
        self.responses = _FakeResponses(parsed, usage)


class StructuredAgent(LlmAgent):
    capabilities = ["structured"]

    @llm_capability("structured", output_schema=StrictOutput)
    def structured(self, goal, context):
        return Prompt(system="Return the value.", user=goal)


class UnsafeAgent(LlmAgent):
    capabilities = ["structured"]

    @llm_capability("structured", output_schema=UnsafeOutput)
    def structured(self, goal, context):
        return Prompt(system="Return the value.", user=goal)


def make_task():
    payload = struct_pb2.Struct()
    payload.update({"input": "A"})
    return contract_pb2.Task(
        task_id="task-llm",
        goal="Extract A",
        payload=payload,
        required_capabilities=["structured"],
        trace=contract_pb2.TraceContext(trace_id="trace-llm"),
    )


class OpenAiLlmTests(unittest.TestCase):
    def build_agent(self, parsed, usage=None, agent_type=StructuredAgent):
        client = _FakeOpenAI(parsed, usage)
        agent = agent_type(
            agent_id="llm",
            name="LLM",
            capabilities=["structured"],
            host="localhost",
            port=60000,
            registry_addr="localhost:50051",
            model="test-model",
            openai_client=client,
        )
        return agent, client

    def test_uses_responses_parse_with_declared_schema(self):
        agent, client = self.build_agent(StrictOutput(value="A"))

        result = agent.execute_task(make_task())

        self.assertEqual(result.status, contract_pb2.TASK_STATUS_COMPLETED)
        self.assertEqual(result.output["value"], "A")
        self.assertGreaterEqual(result.metadata["latency_ms"], 0)
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertIs(call["text_format"], StrictOutput)

    def test_missing_structured_output_returns_stable_failure(self):
        agent, _ = self.build_agent(None)

        result = agent.execute_task(make_task())

        self.assertEqual(result.status, contract_pb2.TASK_STATUS_FAILED)
        self.assertIn("structured output", result.error.message)
        self.assertFalse(result.error.retryable)

    def test_records_provider_usage_when_available(self):
        agent, _ = self.build_agent(
            StrictOutput(value="A"),
            usage={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
        )

        result = agent.execute_task(make_task())

        self.assertEqual(result.metadata["usage"]["input_tokens"], 10)
        self.assertEqual(result.metadata["usage"]["total_tokens"], 14)

    def test_rejects_operational_fields_from_model_output(self):
        agent, _ = self.build_agent(
            UnsafeOutput(value="A", task_id="injected"),
            agent_type=UnsafeAgent,
        )

        result = agent.execute_task(make_task())

        self.assertEqual(result.status, contract_pb2.TASK_STATUS_FAILED)
        self.assertIn("operational field", result.error.message)
        self.assertNotEqual(result.task_id, "injected")


if __name__ == "__main__":
    unittest.main()
