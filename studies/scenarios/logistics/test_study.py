import json
import os
import runpy
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.scenarios.logistics.data import load_case, load_cases, load_world
from studies.scenarios.logistics.domain import plan_mission
from studies.scenarios.logistics.evaluate import evaluate_run, summarize, main as evaluate


class FakeClient:
    """Apenas teste: simula respostas estruturadas sem acessar o provedor."""
    @property
    def responses(self):
        return self

    def parse(self, *, text_format, input, **kwargs):
        request = input[-1]["content"]
        case = next(case for case in load_cases() if case["request"] in request)
        if text_format.__name__ == "LogisticsInterpretation":
            data = {"mission": case["mission"]}
        else:
            plan = plan_mission(load_world(), case["mission"])
            actions = [{"type": action["type"], "origin": action.get("from", ""),
                        "destination": action.get("to", ""), "location": action.get("location", "")}
                       for action in plan["actions"]]
            data = {"feasible": plan["feasible"], "actions": actions, "rejection_reason": plan["rejection_reason"]}
        return type("Response", (), {"output_parsed": text_format(**data), "usage": None})()


class StudyTests(unittest.TestCase):
    def make_run(self, directory, case_id, *, completed=True, repeat=1):
        case, world = load_case(case_id), load_world()
        manifest = {"repeat": repeat, "metadata": {"study": "logistics", "strategy": "bdi-only",
                                                    "case": case, "world": world}}
        (directory / "manifest.json").write_text(json.dumps(manifest))
        record = {"sample": 1, "status": "WORKFLOW_STATUS_COMPLETED" if completed else "RPC_FAILED",
                  "client_duration_ms": 1, "steps": {"execute": {"result": {
                      "output": plan_mission(world, case["mission"]) if completed else {}}}}}
        (directory / "results.jsonl").write_text(json.dumps(record) + "\n")

    def test_offline_evaluation_keeps_runtime_failures_invalid_on_impossible_missions(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.make_run(directory, "impossible-deadline", completed=False, repeat=2)
            rows = evaluate_run(directory)
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(not row["evaluation"]["valid"] for row in rows))
            self.assertTrue(all(row["runtime_error"] for row in rows))
            self.assertIsNone(rows[1]["latency_ms"])
            self.assertEqual(summarize(rows)[0]["consistency_rate"], 0)

    def test_correct_rejection_and_single_observation_consistency(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.make_run(directory, "impossible-deadline")
            rows = evaluate_run(directory)
            self.assertTrue(rows[0]["evaluation"]["correct_rejection"])
            self.assertTrue(rows[0]["evaluation"]["optimal"])
            self.assertIsNone(summarize(rows)[0]["consistency_rate"])
            output = directory / "evaluation"
            self.assertEqual(evaluate([str(directory), "--output", str(output)]), 0)
            self.assertIn("N/A", (output / "logistics-quality.svg").read_text())
            self.assertTrue((output / "logistics-summary.csv").is_file())

    def test_all_strategy_descriptions_have_labels_and_share_domain(self):
        from ariadne_sdk.execution import load_scenario
        source = Path(__file__).with_name("scenario.py")
        for strategy in ("bdi-only", "llm-only", "hybrid"):
            with patch.dict(os.environ, {"LOGISTICS_STRATEGY": strategy}), patch("openai.OpenAI", return_value=FakeClient()):
                scenario = load_scenario(source)
            self.assertEqual(scenario.metadata["strategy"], strategy)
            self.assertEqual(scenario.metadata["world"], load_world())
            steps = scenario.definition()
            self.assertEqual(len(steps), 2 if strategy == "hybrid" else 1)
            if strategy == "hybrid":
                self.assertEqual(steps[1]["input_bindings"][0]["source_path"], "output.mission")

    def test_sdk_planner_matches_reference_on_all_cases_and_variations(self):
        from ariadne_sdk import Task
        from studies.scenarios.logistics.agents.mission_planner import mission_planner
        agent = mission_planner()
        world = load_world()
        for case in load_cases():
            for deadline in (1, case["mission"]["deadline_minutes"], 30):
                with self.subTest(case=case["id"], deadline=deadline):
                    mission = {**case["mission"], "deadline_minutes": deadline}
                    result = agent.handle(Task(task_id="test", goal=case["request"],
                                               payload={"world": world, "mission": mission}))
                    self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
                    self.assertEqual(result.output, plan_mission(world, mission))
                    self.assertEqual(result.metadata["selected_plan"], "safe_logistics_mission")

    def test_llm_adapter_preserves_structured_plan_and_interpretation(self):
        from ariadne_sdk import Task
        from studies.scenarios.logistics.agents.mission_assistant import MissionAssistant
        agent = MissionAssistant(openai_client=FakeClient(), model="test-only")
        case = load_case("avoid-contamination")
        for capability in ("logistics-plan", "logistics-interpret"):
            result = agent.handle(Task(task_id="test", goal=case["request"],
                                       required_capabilities=(capability,), payload={"world": load_world()}))
            self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
            if capability == "logistics-plan":
                self.assertTrue(result.output["feasible"])
            else:
                self.assertEqual(result.output["mission"], case["mission"])

    def test_legacy_agents_reuse_moved_implementations(self):
        from ariadne_sdk import Task
        from ariadne_sdk import BdiAgent
        from studies.scenarios.logistics.agents.mission_assistant import MissionAssistant
        root = Path(__file__).resolve().parents[3]
        with patch.object(sys, "path", [str(root / "studies/agents/route-planner"), *sys.path]):
            namespace = runpy.run_path(str(root / "studies/agents/route-planner/main.py"))
        agent_class = namespace["RoutePlanningAgent"]
        self.assertTrue(issubclass(agent_class, BdiAgent))
        result = agent_class().handle(Task(task_id="route", goal="Ir de A para D",
                                         payload={"origin": "A", "destination": "D"}))
        self.assertEqual(result.output["route"], ["A", "B", "D"])
        case, world = load_case("avoid-contamination"), load_world()
        result = agent_class().handle(Task(task_id="logistics", goal=case["request"],
                                           payload={"mission": case["mission"], "world": world}))
        self.assertEqual(result.output, plan_mission(world, case["mission"]))
        llm_class = runpy.run_path(str(root / "studies/agents/planner-explainer/main.py"))["PlannerExplainerAgent"]
        self.assertTrue(issubclass(llm_class, MissionAssistant))
        agent = llm_class(openai_client=FakeClient())
        self.assertEqual(set(agent._handlers), {"explanation", "task-decomposition", "logistics-plan", "logistics-interpret"})

    @unittest.skipUnless(os.getenv("ARIADNE_TEST_RUNTIME_DIR"), "requires real local runtime binaries")
    def test_hybrid_through_runtime_with_explicit_fake_provider(self):
        from ariadne_sdk.execution import run_experiment
        experiment = Path(__file__).with_name("scenario.py").resolve()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "fake_hybrid.py"
            source.write_text(
                "import os\nfrom unittest.mock import patch\n"
                "from studies.scenarios.logistics.test_study import FakeClient\n"
                "from ariadne_sdk.execution import load_scenario\n"
                "with patch.dict(os.environ, {'LOGISTICS_STRATEGY':'hybrid', 'LOGISTICS_CASE':'avoid-contamination', 'LLM_MODEL':'test-only'}), "
                "patch('openai.OpenAI', return_value=FakeClient()):\n"
                f"    scenario = load_scenario({str(experiment)!r})\n"
                "    scenario.agents[0]._openai = FakeClient()\n"
            )
            run, summary = run_experiment(source, output_root=directory / "runs",
                                          runtime_dir=os.environ["ARIADNE_TEST_RUNTIME_DIR"])
            self.assertEqual(summary["status"], "COMPLETED")
            rows = evaluate_run(run)
            self.assertTrue(rows[0]["evaluation"]["valid"])
            self.assertTrue(rows[0]["interpretation_exact"])
            self.assertEqual(rows[0]["model"], "test-only")


if __name__ == "__main__":
    unittest.main()
