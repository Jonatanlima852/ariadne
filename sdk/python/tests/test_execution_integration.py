"""Integração real opt-in: TG_TEST_RUNTIME_DIR=/.../.tg/bin python -m unittest ..."""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

RUNTIME = os.getenv("TG_TEST_RUNTIME_DIR")
ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(RUNTIME, "set TG_TEST_RUNTIME_DIR to run real Go/Python integration")
class ExecutionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def command(self, source, *options):
        return [sys.executable, "-m", "tg_sdk", "run", str(source),
                "--runtime-dir", str(Path(RUNTIME).resolve()),
                "--output", str(self.directory / "runs"), *options]

    def execute(self, source, *options, expected=0):
        completed = subprocess.run(self.command(source, *options), cwd=self.directory,
                                   capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, expected, completed.stdout + completed.stderr)
        run = next((self.directory / "runs").iterdir())
        self.assertEqual((run / "environment").read_text().strip(), "stopped")
        manifest = json.loads((run / "manifest.json").read_text())
        for address in manifest.get("addresses", {}).values():
            host, port = address.rsplit(":", 1)
            with self.assertRaises(OSError):
                with socket.create_connection((host, int(port)), timeout=0.2):
                    pass
        for process in manifest.get("processes", []):
            with self.assertRaises(ProcessLookupError):
                os.kill(process["pid"], 0)
        return run

    def test_workflow_from_external_directory_repeats_and_preserves_traces(self):
        source = self.directory / "external.py"
        source.write_text((ROOT / "examples/workflow.py").read_text())
        run = self.execute(source, "--repeat", "2")
        results = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines()]
        self.assertEqual(len(results), 2)
        self.assertNotEqual(results[0]["trace_id"], results[1]["trace_id"])
        self.assertTrue(all(result["output"] == {"text": "OLÁ, AGENTES!"} for result in results))
        records = [json.loads(line) for line in (run / "agent-2.jsonl").read_text().splitlines()]
        inputs = [r["task"] for r in records if r["type"] == "AGENT_TASK_STARTED"]
        self.assertEqual(inputs[0]["payload"], {"text": "Olá, agentes!"})
        self.assertTrue(all(r["duration_ms"] >= 0 for r in records if r["type"] == "AGENT_TASK_FINISHED"))
        self.assertFalse(list(run.glob("*.svg")))

    def test_timeout_reassigns_and_logs_both_agents(self):
        run = self.execute(ROOT / "examples/recovery.py")
        result = json.loads((run / "result.json").read_text())
        self.assertEqual(result["steps"]["step_1"]["result"]["agent_id"], "b-healthy")
        events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
        self.assertIn("TASK_TIMEOUT", [event["type"] for event in events])
        self.assertIn("TASK_REASSIGNED", [event["type"] for event in events])
        self.assertTrue((run / "agent-1.jsonl").is_file())
        self.assertTrue((run / "agent-2.jsonl").is_file())

    def test_bdi_subclass_uses_same_executor(self):
        run = self.execute(ROOT / "examples/bdi.py")
        result = json.loads((run / "result.json").read_text())
        self.assertEqual(result["output"], {"route": ["A", "B", "D"]})
        self.assertEqual(result["steps"]["step_1"]["result"]["metadata"]["selected_plan"], "via_b")

    def test_domain_exception_is_preserved_as_failed_result(self):
        source = self.directory / "failure.py"
        source.write_text(
            "from tg_sdk import Agent, Scenario, Step\n"
            "def reject(task): raise ValueError('invalid mission')\n"
            "scenario = Scenario(agents=[Agent(name='bad', capabilities=['test'], handler=reject)], "
            "tasks=[Step('test', 'reject')])\n"
        )
        run = self.execute(source, expected=1)
        result = json.loads((run / "result.json").read_text())
        self.assertEqual(result["status"], "WORKFLOW_STATUS_FAILED")
        self.assertIn("invalid mission", (run / "agent-1.jsonl").read_text())

    def test_partial_startup_failure_cleans_runtime(self):
        source = self.directory / "startup_failure.py"
        source.write_text(
            "from tg_sdk import Agent, Scenario, Step\n"
            "class Broken(Agent):\n"
            "    capabilities = ['test']\n"
            "    def start(self): raise RuntimeError('startup rejected')\n"
            "scenario = Scenario(agents=[Broken()], tasks=[Step('test', 'reject')])\n"
        )
        run = self.execute(source, expected=1)
        self.assertIn("startup rejected", (run / "agent-1.log").read_text())
        self.assertEqual(json.loads((run / "summary.json").read_text())["status"], "FAILED")

    def test_sigint_cancels_and_cleans_all_processes(self):
        source = self.directory / "interrupt.py"
        source.write_text(
            "import time\nfrom tg_sdk import Agent, Scenario, Step\n"
            "def slow(task): time.sleep(30); return {}\n"
            "scenario = Scenario(agents=[Agent(name='slow', capabilities=['test'], handler=slow)], "
            "tasks=[Step('test', 'wait')])\n"
        )
        with (self.directory / "console.log").open("w") as output:
            child = subprocess.Popen(self.command(source), stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                records = list((self.directory / "runs").glob("*/agent-1.jsonl"))
                if records and "AGENT_TASK_STARTED" in records[0].read_text():
                    break
                if child.poll() is not None:
                    self.fail((self.directory / "console.log").read_text())
                time.sleep(0.05)
            else:
                self.fail("agent did not receive task before timeout")
            child.send_signal(signal.SIGINT)
            self.assertEqual(child.wait(timeout=15), 130)
            run = records[0].parent
            self.assertEqual((run / "status").read_text().strip(), "CANCELLED")
            manifest = json.loads((run / "manifest.json").read_text())
            for process in manifest["processes"]:
                with self.assertRaises(ProcessLookupError):
                    os.kill(process["pid"], 0)
        finally:
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
                child.wait(timeout=15)

    def test_two_simultaneous_experiments_have_distinct_ports(self):
        command = self.command(ROOT / "examples/echo.py")
        with (self.directory / "parallel.log").open("w") as output:
            children = [subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT) for _ in range(2)]
        try:
            for child in children:
                self.assertEqual(child.wait(timeout=45), 0, (self.directory / "parallel.log").read_text())
            manifests = [json.loads(path.read_text()) for path in (self.directory / "runs").glob("*/manifest.json")]
            self.assertEqual(len(manifests), 2)
            self.assertTrue(set(manifests[0]["addresses"].values()).isdisjoint(manifests[1]["addresses"].values()))
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=15)


if __name__ == "__main__":
    unittest.main()
