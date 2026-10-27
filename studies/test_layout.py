"""Regressões da reorganização: imports isolados e entradas executáveis."""
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ariadne_sdk import Task
from ariadne_sdk.execution import load_scenario

ROOT = Path(__file__).resolve().parents[1]


class StudyLayoutTests(unittest.TestCase):
    def test_deterministic_scenarios_load_in_one_process(self):
        for name in ("basic_task", "sequential_workflow", "failure_reassignment", "meeting", "agent_selection"):
            with self.subTest(name=name):
                scenario = load_scenario(ROOT / "studies/scenarios" / name / "scenario.py")
                self.assertTrue(scenario.definition())
                self.assertTrue(scenario.agents)

    def test_bdi_packages_do_not_share_bare_beliefs_imports(self):
        from studies.scenarios.routing.agents.route_planner.main import route_planner
        from studies.scenarios.meeting.agents.meeting_scheduler.main import MeetingSchedulerAgent
        from studies.scenarios.meeting.agents.meeting_scheduler.plans import PLAN_LIBRARY
        planner = route_planner()
        scheduler = MeetingSchedulerAgent(plan_library=PLAN_LIBRARY)
        result = planner.handle(Task(task_id="route", goal="route", payload={"origin": "A", "destination": "D"}))
        self.assertEqual(result.output["route"], ["A", "B", "D"])
        self.assertEqual(result.metadata["bdi_trace"]["final_status"], "achieved")
        result = scheduler.handle(Task(task_id="meeting", goal="meeting", payload={
            "participants": ["alice", "bob"], "duration_hours": 1, "preferred_start_hour": 13}))
        self.assertEqual(result.status, "TASK_STATUS_COMPLETED")

    def test_logistics_container_factories_keep_domain_and_environment(self):
        from studies.scenarios.logistics.agents.serve import make_agent
        with patch.dict(os.environ, {"AGENT_ID": "test-agent", "AGENT_HOST": "test-host", "AGENT_PORT": "61234"}):
            planner, assistant = make_agent("planner"), make_agent("assistant")
        self.assertEqual(planner.capabilities, ["logistics-execution"])
        self.assertEqual(set(assistant.capabilities), {"logistics-plan", "logistics-interpret"})
        self.assertEqual(planner.agent_id, "test-agent")
        self.assertEqual(assistant.port, 61234)
        self.assertEqual(planner.host, "test-host")

    def test_split_benchmark_exports_without_provider(self):
        from tools.benchmarking import run_benchmark
        from types import SimpleNamespace
        client = unittest.mock.MagicMock()
        client.__enter__.return_value = client
        result = SimpleNamespace(agent_id="basic-agent", status="TASK_STATUS_COMPLETED")
        result.assert_completed = lambda: result
        client.submit.return_value = result
        module = importlib.import_module("studies.scenarios.basic_task.benchmarks.run")
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"BENCHMARK_OUTPUT_DIR": temporary}), \
                patch("ariadne_sdk.RuntimeClient", return_value=client), patch("tools.benchmarking.time.sleep"):
            run_benchmark(module.__file__, module.collect)
            data = json.loads((Path(temporary) / "results.json").read_text())
            self.assertEqual(data["summary"][0]["runs"], 10)
            self.assertEqual(set(data["raw"]), {"A"})
            self.assertTrue((Path(temporary) / "summary.csv").is_file())
            self.assertFalse((Path(temporary) / "message-count.svg").exists())
