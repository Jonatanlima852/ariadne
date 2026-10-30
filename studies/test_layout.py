"""Regressões da reorganização: imports isolados e entradas executáveis."""
from pathlib import Path
import unittest

from ariadne_sdk import Task
from ariadne_sdk.execution import load_scenario

ROOT = Path(__file__).resolve().parents[1]


class StudyLayoutTests(unittest.TestCase):
    def test_deterministic_scenarios_load_in_one_process(self):
        for name in ("basic_task", "sequential_workflow", "failure_reassignment", "meeting", "agent_selection", "messaging"):
            with self.subTest(name=name):
                scenario = load_scenario(ROOT / "studies/scenarios" / name / "scenario.py")
                self.assertTrue(scenario.definition())
                self.assertTrue(scenario.agents)

    def test_bdi_packages_do_not_share_bare_beliefs_imports(self):
        from studies.scenarios.routing.agents.route_planner.main import route_planner
        from studies.scenarios.meeting.agents.meeting_scheduler.main import meeting_scheduler
        planner = route_planner()
        scheduler = meeting_scheduler()
        result = planner.handle(Task(task_id="route", goal="route", payload={"origin": "A", "destination": "D"}))
        self.assertEqual(result.output["route"], ["A", "B", "D"])
        self.assertEqual(result.metadata["bdi_trace"]["final_status"], "achieved")
        result = scheduler.handle(Task(task_id="meeting", goal="meeting", payload={
            "participants": ["alice", "bob"], "duration_hours": 1, "preferred_start_hour": 13}))
        self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
