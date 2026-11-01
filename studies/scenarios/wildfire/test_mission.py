"""Integração real do wildfire em contêineres: ARIADNE_TEST_DOCKER=1.

Usa os substitutos determinísticos (WILDFIRE_DEMO=1); nenhuma chamada LLM é feita.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from studies.scenarios.wildfire.mission import Settings, check_mission, episode_metrics

ROOT = Path(__file__).resolve().parents[3]
DOCKER = os.getenv('ARIADNE_TEST_DOCKER')


@unittest.skipUnless(DOCKER, 'set ARIADNE_TEST_DOCKER=1 to run the real Docker integration')
class WildfireMissionIntegrationTests(unittest.TestCase):
    def run_case(self, case_id, configuration):
        settings = Settings(case_id=case_id, configuration=configuration, demo=True)
        with tempfile.TemporaryDirectory() as temporary:
            completed = subprocess.run(
                [sys.executable, '-m', 'ariadne_sdk', 'run', 'studies/scenarios/wildfire/scenario.py',
                 '--output', temporary, '--timeout', '600'],
                cwd=ROOT, capture_output=True, text=True, timeout=900,
                env={**os.environ, 'WILDFIRE_DEMO': '1', 'WILDFIRE_CASE': case_id, 'WILDFIRE_CONFIGURATION': configuration},
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            run = next(Path(temporary).iterdir())
            manifest = json.loads((run / 'manifest.json').read_text())
            saved = json.loads((run / 'mission-result.json').read_text())
        self.assertEqual(manifest['metadata']['case'], case_id)
        check_mission(saved, settings)
        return episode_metrics(saved, case=settings.case, configuration=configuration, demo=True)

    def test_single_fire_hybrid_contains_the_fire_with_bdi_steps_in_parallel(self):
        row = self.run_case('single-fire', 'ariadne')
        self.assertEqual(row['result'], 'contained')
        self.assertEqual(row['max_parallel_steps'], 2)
        self.assertGreater(row['bdi_cycles'], 0)

    def test_single_fire_pilot_runs_one_world_step_per_round(self):
        row = self.run_case('single-fire', 'single-llm')
        self.assertEqual(row['max_parallel_steps'], 0)
        self.assertEqual(row['bdi_cycles'], 0)


if __name__ == '__main__':
    unittest.main()
