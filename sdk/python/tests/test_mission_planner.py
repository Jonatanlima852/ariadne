"""Planejador de missão como capacidade LLM: decisão validada vira PlannerResponse."""
import unittest

from pydantic import ValidationError

from contract.v1 import contract_pb2
from ariadne_sdk import LlmAgent, PlannerDecision, PlannerRequest, Prompt, Task, mission_planning
from ariadne_sdk.llm import PlanDraft, PlanStepDraft, decision_to_response


class _FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"output_parsed": self.parsed, "usage": None})()


class _FakeOpenAI:
    def __init__(self, parsed):
        self.responses = _FakeResponses(parsed)


REQUEST = {
    "mission_id": "m-1", "goal": "Entregar o pedido o-1", "round": 1,
    "context": {"warehouse": "W1"},
    "available_capabilities": [{"capability_id": "picking", "agent_count": 1}],
    "limits": {"max_rounds": 3},
}


def plan_decision(**overrides):
    values = dict(
        action="PLAN", summary="pick first", reason="",
        plan=PlanDraft(workflow_id="wf", final_step_id="pick", steps=[PlanStepDraft(
            step_id="pick", type="MISSION_STEP", goal="pick o-1", payload_json='{"order": "o-1"}',
            required_capabilities=["picking"], depends_on=[], input_bindings=[],
        )]),
        output_json="", context_update_json='{"stage": "picking"}',
    )
    values.update(overrides)
    return PlannerDecision(**values)


class PlannerDecisionTests(unittest.TestCase):
    def test_plan_decision_becomes_contract_response(self):
        output = decision_to_response(plan_decision())
        self.assertEqual(output["action"], "PLAN")
        step = output["plan"]["steps"][0]
        self.assertEqual(step["payload"], {"order": "o-1"})
        self.assertEqual(step["required_capabilities"], ["picking"])
        self.assertEqual(output["context_update"], {"stage": "picking"})
        self.assertEqual(output["summary"], "pick first")

    def test_done_and_abort_decisions(self):
        done = decision_to_response(plan_decision(action="DONE", plan=None, output_json='{"delivered": true}'))
        self.assertEqual(done["output"], {"delivered": True})
        self.assertNotIn("plan", done)
        abort = decision_to_response(plan_decision(action="ABORT", plan=None, reason="no picker alive"))
        self.assertEqual(abort["reason"], "no picker alive")

    def test_invalid_decisions_are_rejected(self):
        cases = (
            (dict(action="PLAN", plan=None), "requires a plan"),
            (dict(action="DONE", plan=None, output_json=""), "DONE requires"),
            (dict(action="DONE", plan=None, output_json="[1, 2]"), "JSON object"),
            (dict(action="ABORT", plan=None, reason=""), "ABORT requires"),
            (dict(plan=PlanDraft(workflow_id="wf", final_step_id="pick", steps=[PlanStepDraft(
                step_id="pick", type="MISSION_STEP", goal="g", payload_json="not json",
                required_capabilities=["picking"], depends_on=[], input_bindings=[])])), "payload_json"),
        )
        for overrides, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                decision_to_response(plan_decision(**overrides))
        with self.assertRaises(ValidationError):
            PlannerDecision(action="RETRY", summary="", reason="", plan=None, output_json="", context_update_json="")
        with self.assertRaises(ValidationError):
            plan_decision(extra_field=1)


class MissionPlanningAgentTests(unittest.TestCase):
    def build_agent(self, parsed, prompt):
        client = _FakeOpenAI(parsed)
        agent = LlmAgent(
            agent_id="planner", name="Planner", handlers=[mission_planning(prompt)],
            host="localhost", port=1, registry_addr="localhost:50051",
            model="test-model", openai_client=client,
        )
        return agent, client

    def test_prompt_receives_decoded_request_and_output_is_contract_json(self):
        seen = []

        def prompt(request):
            seen.append(request)
            return Prompt(system="Plan.", user=f"{request.goal} with {request.capability_ids}")

        agent, client = self.build_agent(plan_decision(), prompt)
        self.assertEqual(agent.capabilities, ["mission-planning"])
        result = agent.handle(Task("t-plan", "Entregar o pedido o-1", type="MISSION_PLANNING",
                                   payload=REQUEST, required_capabilities=("mission-planning",)))
        self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
        self.assertIsInstance(seen[0], PlannerRequest)
        self.assertEqual(seen[0].capability_ids, ["picking"])
        self.assertEqual(client.responses.calls[0]["input"][1]["content"], "Entregar o pedido o-1 with ['picking']")
        self.assertIs(client.responses.calls[0]["text_format"], PlannerDecision)
        self.assertEqual(result.output["action"], "PLAN")
        self.assertEqual(result.output["plan"]["steps"][0]["step_id"], "pick")
        self.assertEqual(result.metadata["provider"], "openai")

    def test_invalid_request_payload_fails_without_calling_the_model(self):
        agent, client = self.build_agent(plan_decision(), lambda request: Prompt("Plan.", request.goal))
        result = agent.handle(Task("t", "goal", payload={**REQUEST, "unexpected": 1},
                                   required_capabilities=("mission-planning",)))
        self.assertEqual(result.status, "TASK_STATUS_FAILED")
        self.assertIn("invalid planner request", result.error_message)
        self.assertFalse(result.retryable)
        self.assertEqual(client.responses.calls, [])

    def test_invalid_decision_fails_as_validation_error(self):
        agent, _ = self.build_agent(plan_decision(action="DONE", plan=None, output_json=""),
                                    Prompt("Plan.", "static"))
        result = agent.execute_task(Task("t", "goal", payload=REQUEST,
                                         required_capabilities=("mission-planning",)).to_proto())
        self.assertEqual(result.status, contract_pb2.TASK_STATUS_FAILED)
        self.assertIn("DONE requires", result.error.message)

    def test_custom_capability_name(self):
        capability = mission_planning(Prompt("Plan.", "x"), capability="logistics-planning")
        self.assertEqual(capability.name, "logistics-planning")
        with self.assertRaisesRegex(TypeError, "prompt"):
            mission_planning("not a prompt")


if __name__ == "__main__":
    unittest.main()
