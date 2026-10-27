"""Agentes do cenário de rotas, sem runtime: deliberação BDI e planejador de missão."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ariadne_sdk import PlannerResponse, Task
from studies.scenarios.routing.agents.planner_explainer.main import planner_explainer
from studies.scenarios.routing.agents.planner_explainer.substitute import PROVIDER
from studies.scenarios.routing.agents.route_planner.main import route_planner
from studies.scenarios.routing.mission import CONTEXT, GOAL


def planner_request(**overrides):
    request = {"mission_id": "m-1", "goal": GOAL, "round": 1, "context": CONTEXT, "history": [],
               "available_capabilities": [{"capability_id": "route-planning", "agent_count": 1},
                                          {"capability_id": "explanation", "agent_count": 1}],
               "limits": {"max_rounds": 3}}
    request.update(overrides)
    return Task(task_id=f"plan-{request['round']}", goal=GOAL, type="MISSION_PLANNING",
                payload=request, required_capabilities=("mission-planning",))


def completed_round(route_output, explanation_output):
    return [{"round": 1, "action": "PLANNER_ACTION_PLAN", "status": "WORKFLOW_STATUS_COMPLETED",
             "step_results": [
                 {"step_id": "route", "status": "WORKFLOW_STEP_STATUS_COMPLETED",
                  "result": {"output": route_output, "metadata": {"selected_plan": "via_intermediate"}}},
                 {"step_id": "explain", "status": "WORKFLOW_STEP_STATUS_COMPLETED",
                  "result": {"output": explanation_output}}]}]


class RoutePlannerTests(unittest.TestCase):
    def test_deliberates_from_task_scoped_beliefs_and_returns_the_trace(self):
        agent = route_planner()
        self.assertEqual(agent.capabilities, ["route-planning"])
        result = agent.handle(Task(task_id="route", goal="Ir de A para D",
                                   payload={"origin": "A", "destination": "D"}))
        self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
        self.assertEqual(result.output["route"], ["A", "B", "D"])
        self.assertEqual(result.output["distance"], 25)
        self.assertEqual(result.metadata["selected_plan"], "via_intermediate")
        trace = result.metadata["bdi_trace"]
        self.assertEqual((trace["final_status"], trace["cycle_count"]), ("achieved", 3))
        first = trace["cycles"][0]
        self.assertIn('origin="A"', first["beliefs_added"])
        self.assertEqual((first["goal"], first["selected_plan"], first["action"]),
                         ("plan_route", "via_intermediate", "act(find_route)"))
        self.assertEqual([cycle["action"] for cycle in trace["cycles"][1:]], ["observe(stops=1)", "return"])
        self.assertEqual(result.bdi["trace"]["cycle_count"], 3)

    def test_graph_and_stop_limit_come_from_the_payload(self):
        agent = route_planner()
        direct = agent.handle(Task(task_id="direct", goal="x", payload={"origin": "A", "destination": "D", "max_stops": 0}))
        self.assertEqual((direct.metadata["selected_plan"], direct.output["route"], direct.output["distance"]),
                         ("direct_route", ["A", "D"], 30))
        custom = agent.handle(Task(task_id="custom", goal="x", payload={
            "origin": "X", "destination": "Y", "graph": {"X": {"Z": 1, "Y": 5}, "Z": {"Y": 1}}}))
        self.assertEqual((custom.output["route"], custom.output["distance"]), (["X", "Z", "Y"], 2))

    def test_fails_when_no_plan_applies_or_the_task_is_incomplete(self):
        agent = route_planner()
        unknown = agent.handle(Task(task_id="unknown", goal="x", payload={"origin": "Z", "destination": "D"}))
        self.assertEqual((unknown.status, unknown.error_code), ("TASK_STATUS_FAILED", "ERROR_CODE_EXECUTION_FAILED"))
        self.assertEqual(unknown.metadata["bdi_trace"]["final_status"], "no_applicable_plan")
        incomplete = agent.handle(Task(task_id="incomplete", goal="x", payload={"origin": "A"}))
        self.assertEqual((incomplete.status, incomplete.error_code), ("TASK_STATUS_FAILED", "ERROR_CODE_INVALID_TASK"))


class PlannerExplainerTests(unittest.TestCase):
    def test_substitute_plans_route_then_explain_and_finishes_from_history(self):
        with patch.dict(os.environ, {"AGENT_ID": "custom-planner", "AGENT_PORT": "61234", "ROUTING_DEMO": "1"}):
            agent = planner_explainer()
        self.assertEqual((agent.agent_id, agent.port), ("custom-planner", 61234))
        self.assertEqual(agent.capabilities, ["mission-planning", "explanation"])

        first = agent.handle(planner_request())
        self.assertEqual(first.status, "TASK_STATUS_COMPLETED")
        self.assertEqual(first.metadata["provider"], PROVIDER)
        response = PlannerResponse.from_output(first.output)
        self.assertEqual(response.action, "PLAN")
        route, explain = response.plan["steps"]
        self.assertEqual((route["step_id"], route["required_capabilities"]), ("route", ["route-planning"]))
        self.assertEqual(route["payload"]["origin"], "A")
        self.assertEqual(route["payload"]["graph"]["A"]["B"], 10)
        self.assertEqual((explain["required_capabilities"], explain["depends_on"]), (["explanation"], ["route"]))
        self.assertEqual(explain["input_bindings"][0], {"source_step_id": "route", "source_path": "output", "target_field": "route"})
        self.assertEqual(response.plan["final_step_id"], "explain")

        history = completed_round({"route": ["A", "B", "D"], "distance": 25}, {"explanation": "Via B"})
        second = agent.handle(planner_request(round=2, history=history))
        self.assertEqual(PlannerResponse.from_output(second.output).action, "DONE")
        self.assertEqual(second.output["output"], {"route": ["A", "B", "D"], "distance": 25, "explanation": "Via B"})

        history[0]["step_results"][0]["status"] = "WORKFLOW_STEP_STATUS_FAILED"
        aborted = agent.handle(planner_request(round=2, history=history))
        self.assertEqual(PlannerResponse.from_output(aborted.output).action, "ABORT")

    def test_explanation_prompt_carries_the_bound_route_and_rejects_invalid_answers(self):
        from studies.scenarios.routing.agents.planner_explainer.response_models import Explanation
        explanation = {"explanation": "Via B", "reasoning_summary": "Menor distância", "confidence": 0.9}
        requests = []

        def parse(**request):
            requests.append(request)
            return SimpleNamespace(output_parsed=request["text_format"](**explanation), usage=None)

        agent = planner_explainer(demo=False, openai_client=SimpleNamespace(responses=SimpleNamespace(parse=parse)))
        task = Task(task_id="explain", goal="Explique", required_capabilities=("explanation",),
                    payload={"route": {"route": ["A", "B", "D"], "distance": 25}, "selected_plan": "via_intermediate"})
        result = agent.handle(task)
        self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
        self.assertEqual(result.output, explanation)
        self.assertIs(requests[-1]["text_format"], Explanation)
        self.assertIn('"route": ["A", "B", "D"]', requests[-1]["input"][1]["content"])
        explanation["confidence"] = 2
        self.assertEqual(agent.handle(task).status, "TASK_STATUS_FAILED")
