"""Todo scenario.py dos estudos carrega e descreve agentes e tarefas sem iniciar nada."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from ariadne_sdk.execution import load_scenario

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = sorted((ROOT / "studies/scenarios").glob("**/scenario.py"))
# Substitutos determinísticos: a declaração não deve depender de credencial.
DEMO = {"ROUTING_DEMO": "1", "LOGISTICS_V3_DEMO": "1", "LLM_MODEL": "test-only"}


class ScenarioDeclarationsTest(unittest.TestCase):
    def test_every_scenario_loads(self):
        self.assertGreaterEqual(len(SCENARIOS), 11)
        for source in SCENARIOS:
            with self.subTest(scenario=str(source.relative_to(ROOT))), patch.dict(os.environ, DEMO):
                scenario = load_scenario(source)
                self.assertTrue(scenario.agents)
                self.assertTrue(scenario.definition() or scenario.mission is not None)
