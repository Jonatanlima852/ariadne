"""Missão declarada em um arquivo de experimento e evidência gravada pelo executor."""
import json
from pathlib import Path
import tempfile
import unittest

from ariadne_sdk import Mission, MissionLimits, RuntimeClient, Scenario, Step
from ariadne_sdk.execution import load_scenario, run_mission_sample
from test_mission import FakeMissionOrchestrator


class DeclarativeMissionTests(unittest.TestCase):
    def test_scenario_with_mission_has_no_steps_and_validates(self):
        mission = Mission(goal="Entregar o pedido", context={"orders": ["o-1"]}, limits={"max_rounds": 4})
        scenario = Scenario(agents=[], mission=mission)
        self.assertEqual(scenario.definition(), [])
        self.assertEqual(mission.to_dict()["limits"]["max_rounds"], 4)
        self.assertEqual(mission.to_dict()["planner_capability"], "mission-planning")
        with self.assertRaisesRegex(ValueError, "not both"):
            Scenario(mission=mission, tasks=[Step("echo", "x")]).definition()
        with self.assertRaisesRegex(ValueError, "Mission.goal"):
            Scenario(mission=Mission(goal="")).definition()
        with self.assertRaisesRegex(ValueError, "unknown mission limit"):
            Scenario(mission=Mission(goal="g", limits={"rounds": 1})).definition()

    def test_load_scenario_requires_planner_agent_and_records_mission(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "mission_experiment.py"
            source.write_text(
                "from ariadne_sdk import Agent, Mission, Scenario\n"
                "scenario = Scenario(agents=[Agent(name='picker', capabilities=['picking'])], "
                "mission=Mission(goal='Entregar', context={'orders': 1}))\n"
            )
            with self.assertRaisesRegex(ValueError, "mission-planning"):
                load_scenario(source)
            source.write_text(
                "from ariadne_sdk import Agent, Mission, Scenario\n"
                "def plan(task): return {'action': 'PLANNER_ACTION_DONE', 'output': {'ok': True}}\n"
                "scenario = Scenario(agents=[Agent(name='planner', capabilities=['mission-planning'], handler=plan)], "
                "mission=Mission(goal='Entregar', context={'orders': 1}))\n"
            )
            scenario = load_scenario(source)
            self.assertEqual(scenario.name, "mission_experiment")
            self.assertEqual(scenario.definition(), [])
            self.assertEqual(scenario.mission.goal, "Entregar")

    def test_run_mission_sample_forwards_declaration_and_saves_contract_json(self):
        stub = FakeMissionOrchestrator()
        mission = Mission(goal="Entregar", context={"orders": ["o-1"]}, limits=MissionLimits(max_rounds=2),
                          retry_policy={"max_attempts": 3}, metadata={"case": "c1"})
        client = RuntimeClient("declarative", orchestrator_stub=stub)
        result = run_mission_sample(client, mission, rpc_timeout=7)
        _, request, timeout = stub.requests[0]
        self.assertEqual(timeout, 7)
        self.assertEqual(request.mission.goal, "Entregar")
        self.assertEqual(request.mission.limits.max_rounds, 2)
        self.assertEqual(request.mission.default_retry_policy.max_attempts, 3)
        with tempfile.TemporaryDirectory() as directory:
            saved = json.loads(result.save(Path(directory) / "mission-result.json").read_text())
        self.assertEqual(saved["request"]["context"], {"orders": ["o-1"]})
        self.assertEqual(len(saved["rounds"]), 2)


if __name__ == "__main__":
    unittest.main()
