"""Confere os limites entre dados, agentes de demonstração e domínio."""
import contextlib
import importlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ariadne_sdk import Task
from studies.scenarios.logistics.v2.benchmarks.run import main
from studies.scenarios.logistics.v2.domain.world import execute, initial, validate_case

ROOT = Path(__file__).resolve().parents[1]


class LogisticsIntegrationTests(unittest.TestCase):
    def test_all_suites_load_before_runtime_connection(self):
        for filename in ("basic.json", "stress.json"):
            for case in json.loads((ROOT / "datasets" / filename).read_text()):
                with self.subTest(case=case["id"]):
                    validate_case(case)
        with patch("grpc.insecure_channel") as channel, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(["--suite", "all", "--cases", "unknown-layout-check"])
        self.assertEqual(error.exception.code, 2)
        channel.assert_not_called()

    def test_every_agent_can_be_declared_in_demo_mode_without_credentials(self):
        with patch.dict("os.environ", {"LOGISTICS_V2_DEMO": "1"}, clear=True):
            for source in (ROOT / "agents").glob("*/main.py"):
                with self.subTest(agent=source.parent.name):
                    module = importlib.import_module(
                        "studies.scenarios.logistics.v2.agents." + source.parent.name + ".main")
                    agent = module.make_agent()
                    self.assertTrue(agent.capabilities)

    def test_demo_proposal_passes_schema_mapping_and_world_transitions(self):
        from studies.scenarios.logistics.v2.agents.single_llm.main import make_agent
        case = json.loads((ROOT / "datasets/basic.json").read_text())[0]
        state = initial(case)
        result = make_agent(demo=True).handle(Task(
            task_id="demo-integration", goal="Plan a delivery", required_capabilities=["logistics-v2-SingleLLM"],
            payload={"state": state}))
        self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
        self.assertEqual(result.metadata["provider"], "deterministic-integration-substitute")
        self.assertTrue(result.output["actions"])
        outcome = execute(state, result.output["actions"], case["incidents"])
        self.assertFalse(outcome["reason"])
        self.assertGreater(len(outcome["state"]["deliveries"]), 0)
        self.assertFalse(state["deliveries"])
