import os
import unittest
from unittest.mock import patch
from studies.scenarios.routing.agents.route_planner.main import RoutePlanningAgent
from studies.scenarios.routing.agents.planner_explainer.main import planner_explainer


class RoutingTests(unittest.TestCase):
    def test_route_planner_owns_only_routing(self):
        from ariadne_sdk import Task
        agent = RoutePlanningAgent()
        self.assertEqual(agent.capabilities, ["route-planning"])
        result = agent.handle(Task(task_id="route", goal="Ir de A para D",
                                   payload={"origin": "A", "destination": "D"}))
        self.assertEqual(result.output["route"], ["A", "B", "D"])
        self.assertEqual(result.output["distance"], 25)

    def test_composed_workflow_and_explanation_with_fake_provider(self):
        from ariadne_sdk import Task
        from types import SimpleNamespace
        factory = planner_explainer
        draft = {"workflow_id": "route-workflow", "final_step_id": "route", "steps": [{
            "step_id": "route", "type": "TASK", "goal": "Ir de A para D",
            "payload_json": '{"origin":"A","destination":"D"}',
            "required_capabilities": ["route-planning"], "depends_on": [], "input_bindings": [],
        }]}
        explanation = {"explanation": "Via B", "reasoning_summary": "Menor distância", "confidence": 0.9}
        requests = []

        def parse(**request):
            requests.append(request)
            schema = request["text_format"]
            value = draft if schema.__name__ == "WorkflowDraft" else explanation
            return SimpleNamespace(output_parsed=schema(**value), usage=None)

        with patch.dict(os.environ, {"AGENT_ID": "custom-planner", "AGENT_PORT": "61234"}):
            agent = factory(openai_client=SimpleNamespace(responses=SimpleNamespace(parse=parse)))
        self.assertEqual(agent.agent_id, "custom-planner")
        self.assertEqual(agent.port, 61234)
        task = Task(task_id="test", goal="Ir de A para D", required_capabilities=("task-decomposition",))
        result = agent.handle(task)
        self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
        self.assertEqual(result.output["steps"][0]["payload"], {"origin": "A", "destination": "D"})
        result = agent.handle(Task(task_id="explain", goal="Explique", required_capabilities=("explanation",),
                                   payload={"route": ["A", "B", "D"]}))
        self.assertEqual(result.output, explanation)
        self.assertIn('"route": ["A", "B", "D"]', requests[-1]["input"][1]["content"])
        draft["steps"][0]["payload_json"] = "[]"
        self.assertEqual(agent.handle(task).status, "TASK_STATUS_FAILED")
        explanation["confidence"] = 2
        self.assertEqual(agent.handle(Task(task_id="bad", goal="Explique",
                                          required_capabilities=("explanation",))).status, "TASK_STATUS_FAILED")

