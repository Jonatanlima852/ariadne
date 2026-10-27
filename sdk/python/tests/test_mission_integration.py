"""Integração real opt-in da missão: ARIADNE_TEST_RUNTIME_DIR=/.../.ariadne/bin."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNTIME = os.getenv("ARIADNE_TEST_RUNTIME_DIR")

EXPERIMENT = '''
from ariadne_sdk import Agent, Mission, PlannerRequest, PlannerResponse, Scenario, plan_step


def plan(task):
    """Planejador determinístico: um passo de eco na rodada 1, DONE na rodada 2."""
    request = PlannerRequest.from_payload(task.payload)
    if not request.history:
        return PlannerResponse.make_plan(
            [plan_step("say", "echo", "Repita o texto", payload={"text": request.context["text"]})],
            summary="one echo step", context_update={"stage": "echo"},
        ).to_output()
    last = request.history[-1]
    echoed = last["step_results"][0]["result"]["output"]["text"]
    return PlannerResponse.done(
        {"echoed": echoed, "rounds": request.round, "capabilities": request.capability_ids},
        summary="echo finished",
    ).to_output()


planner = Agent(name="planner", capabilities=["mission-planning"], handler=plan)
echo = Agent(name="echo", capabilities=["echo"], handler=lambda task: {"text": task.payload["text"].upper()})
scenario = Scenario(
    agents=[planner, echo],
    mission=Mission(goal="Repetir o texto em maiúsculas", context={"text": "olá, missão"}, limits={"max_rounds": 3}),
)
'''


@unittest.skipUnless(RUNTIME, "set ARIADNE_TEST_RUNTIME_DIR to run real Go/Python integration")
class MissionIntegrationTests(unittest.TestCase):
    def test_declared_mission_runs_two_rounds_and_saves_contract_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "mission_experiment.py"
            source.write_text(EXPERIMENT)
            completed = subprocess.run(
                [sys.executable, "-m", "ariadne_sdk", "run", str(source),
                 "--runtime-dir", str(Path(RUNTIME).resolve()), "--output", str(directory / "runs")],
                cwd=directory, capture_output=True, text=True, timeout=90,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            run = next((directory / "runs").iterdir())
            manifest = json.loads((run / "manifest.json").read_text())
            self.assertEqual(manifest["mission"]["goal"], "Repetir o texto em maiúsculas")
            self.assertEqual(manifest["steps"], [])
            saved = json.loads((run / "mission-result.json").read_text())
            record = json.loads((run / "result.json").read_text())

        self.assertEqual(saved["status"], "MISSION_STATUS_COMPLETED")
        self.assertEqual(record["status"], "MISSION_STATUS_COMPLETED")
        self.assertEqual(saved["output"]["echoed"], "OLÁ, MISSÃO")
        self.assertEqual(saved["output"]["rounds"], 2)
        self.assertIn("echo", saved["output"]["capabilities"])
        # context_update of round 1 and the final step output are merged into the context.
        self.assertEqual(saved["context"]["stage"], "echo")
        self.assertEqual(saved["context"]["text"], "OLÁ, MISSÃO")
        self.assertEqual(saved["root_task_id"], "mission-" + saved["mission_id"])
        first, second = saved["rounds"]
        self.assertEqual((first["round"], first["action"], first["planner_agent_id"]), (1, "PLANNER_ACTION_PLAN", "planner"))
        step = first["result"]["step_results"][0]
        self.assertEqual(step["step_id"], "say")
        self.assertEqual(step["status"], "WORKFLOW_STEP_STATUS_COMPLETED")
        self.assertEqual(step["task"]["payload"], {"text": "olá, missão"})
        self.assertEqual(step["task"]["required_capabilities"], ["echo"])
        self.assertEqual(step["result"]["output"], {"text": "OLÁ, MISSÃO"})
        self.assertEqual(step["result"]["agent_id"], "echo")
        self.assertEqual(second["action"], "PLANNER_ACTION_DONE")
        self.assertEqual(second["planner_result"]["output"]["action"], "DONE")
        calls = saved["planner_calls"]
        self.assertEqual(calls[0]["request"]["context"], {"text": "olá, missão"})
        self.assertEqual(calls[1]["request"]["context"]["stage"], "echo")
        self.assertEqual(calls[1]["request"]["history"][0]["step_results"][0]["result"]["output"], {"text": "OLÁ, MISSÃO"})
        self.assertEqual(calls[1]["response"]["output"]["echoed"], "OLÁ, MISSÃO")


if __name__ == "__main__":
    unittest.main()
