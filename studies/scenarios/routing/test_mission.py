"""Integração real da missão de rotas em contêineres: ARIADNE_TEST_DOCKER=1.

Usa o substituto determinístico (ROUTING_DEMO=1); nenhuma chamada LLM é feita.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from studies.scenarios.routing.mission import check_mission

ROOT = Path(__file__).resolve().parents[3]
DOCKER = os.getenv("ARIADNE_TEST_DOCKER")


@unittest.skipUnless(DOCKER, "set ARIADNE_TEST_DOCKER=1 to run the real Docker integration")
class RoutingMissionIntegrationTests(unittest.TestCase):
    def test_mission_plans_routes_explains_and_finishes_in_two_rounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed = subprocess.run(
                [sys.executable, "-m", "ariadne_sdk", "run", "studies/scenarios/routing/scenario.py",
                 "--output", temporary],
                cwd=ROOT, capture_output=True, text=True, timeout=300,
                env={**os.environ, "ROUTING_DEMO": "1"},
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            run = next(Path(temporary).iterdir())
            manifest = json.loads((run / "manifest.json").read_text())
            saved = json.loads((run / "mission-result.json").read_text())

        self.assertEqual(manifest["mission"]["context"]["origin"], "A")
        check_mission(saved)
        first, second = saved["rounds"]
        self.assertEqual((first["action"], first["planner_agent_id"]), ("PLANNER_ACTION_PLAN", "planner-explainer-01"))
        steps = {step["step_id"]: step for step in first["result"]["step_results"]}
        self.assertEqual(steps["route"]["task"]["payload"]["origin"], "A")
        self.assertEqual(steps["route"]["result"]["agent_id"], "route-planner-01")
        self.assertEqual(steps["route"]["result"]["bdi"]["trace"]["cycle_count"], 3)
        # The binding delivered the BDI output and plan name to the explanation step.
        self.assertEqual(steps["explain"]["task"]["payload"]["route"]["route"], ["A", "B", "D"])
        self.assertEqual(steps["explain"]["task"]["payload"]["selected_plan"], "via_intermediate")
        self.assertEqual(steps["explain"]["result"]["agent_id"], "planner-explainer-01")
        self.assertEqual(second["action"], "PLANNER_ACTION_DONE")
        self.assertEqual(saved["planner_calls"][1]["request"]["history"][0]["step_results"][0]["step_id"], "route")


if __name__ == "__main__":
    unittest.main()
