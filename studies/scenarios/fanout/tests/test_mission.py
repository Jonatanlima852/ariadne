"""Integração real com os binários Go (ARIADNE_TEST_RUNTIME_DIR): paralelismo e reatribuição.

Sem LLM e sem Docker. K=4, N=8, contador lento ligado: a missão deve
completar, um passo deve estourar o prazo no contador lento e terminar em
outro contador, e o rastro deve estar completo.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from studies.scenarios.fanout.agents import FLAKY_AGENT_ID
from studies.scenarios.fanout.analysis import analyze_sample, read_jsonl
from studies.scenarios.fanout.mission import Settings, check_mission

ROOT = Path(__file__).resolve().parents[4]
RUNTIME = os.getenv("ARIADNE_TEST_RUNTIME_DIR")


@unittest.skipUnless(RUNTIME, "set ARIADNE_TEST_RUNTIME_DIR to run real Go/Python integration")
class FanoutMissionIntegrationTests(unittest.TestCase):
    def test_parallel_maps_with_timeout_and_reassignment(self):
        settings = Settings(workers=4, shards=8, flaky=True, step_deadline_ms=1500, work_ms=300)
        with tempfile.TemporaryDirectory() as temporary:
            completed = subprocess.run(
                [sys.executable, "-m", "ariadne_sdk", "run", "studies/scenarios/fanout/scenario.py",
                 "--runtime-dir", str(Path(RUNTIME).resolve()), "--output", temporary, "--timeout", "120"],
                cwd=ROOT, capture_output=True, text=True, timeout=180,
                env={**os.environ, "FANOUT_WORKERS": "4", "FANOUT_SHARDS": "8", "FANOUT_FLAKY": "1",
                     "FANOUT_STEP_DEADLINE_MS": "1500", "FANOUT_WORK_MS": "300"},
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            run = next(Path(temporary).iterdir())
            manifest = json.loads((run / "manifest.json").read_text())
            saved = json.loads((run / "mission-result.json").read_text())
            events = read_jsonl(run / "events.jsonl")

        self.assertEqual(manifest["mission"]["limits"]["max_parallel"], 4)
        self.assertEqual(manifest["metadata"]["flaky_delay_ms"], 4500)
        check_mission(saved, settings)
        sample = analyze_sample(saved, events, manifest["metadata"])
        self.assertEqual(sample["status"], "COMPLETED")
        self.assertEqual(sample["map_steps_completed"], 8)
        self.assertEqual(sample["steps_completed"], 9)
        # Paralelismo: com K=4 há quatro passos de mapa em execução ao mesmo tempo.
        self.assertGreaterEqual(sample["map_concurrency_peak"], 2)
        self.assertGreater(sample["map_parallelism_factor"], 1.0)
        # Reatribuição: a tentativa 1 no contador lento estourou o prazo; a tentativa 2 foi para outro contador.
        reassigned = sample["reassignments"]["steps"]
        self.assertGreaterEqual(len(reassigned), 1)
        for entry in reassigned:
            self.assertEqual(entry["first_agent"], FLAKY_AGENT_ID)
            self.assertNotEqual(entry["final_agent"], FLAKY_AGENT_ID)
            self.assertEqual(entry["attempts"], 2)
        types = {event["type"] for event in events}
        self.assertIn("TASK_TIMEOUT", types)
        self.assertIn("TASK_REASSIGNED", types)
        self.assertEqual(sample["reassignments"]["events"], len(reassigned))
        for row in sample["recovery"]:
            self.assertGreater(row["timeout_detection_ms"], 1400)
            self.assertGreaterEqual(row["recovery_ms"], 0)
            self.assertLess(row["recovery_ms"], 1000)
        self.assertEqual(sample["completeness"]["missing"], [])
        self.assertEqual(sample["completeness"]["ratio"], 1.0)
        self.assertEqual(saved["output"]["reassigned_steps"], [entry["step_id"] for entry in reassigned])


if __name__ == "__main__":
    unittest.main()
