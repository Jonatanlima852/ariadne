"""Testes do ciclo de vida do shell, sem daemon Docker ou chamadas externas."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
FAKE_DOCKER = r'''
import json, os, signal, sys, time
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['FAKE_CALLS'], 'a') as f:
    f.write(json.dumps(args) + '\n')
if args == ['info']:
    sys.exit(int(os.getenv('FAKE_DAEMON_FAIL', '0')))
if args[:2] == ['compose', 'version']:
    print(os.getenv('FAKE_VERSION', '2.39.2'))
    sys.exit(0)
command = next(a for a in args if a in ('config','build','up','run','logs','cp','down'))
project = args[args.index('-p') + 1]
control_file = Path(args[args.index('-f') + 1])
if command == 'down':
    control_file.parent.joinpath('fake-stopped').touch()
    sys.exit(int(os.getenv('FAKE_DOWN_FAIL', '0')))
if command == 'logs':
    print('services for ' + project)
elif command == 'cp':
    if os.getenv('FAKE_COPY_FAIL'): sys.exit(1)
    Path(args[-1]).write_text('{"type":"TASK_COMPLETED"}\n')
elif command == 'config':
    sys.exit(int(os.getenv('FAKE_CONFIG_FAIL', '0')))
elif command in ('build', 'run'):
    directory = Path(os.environ['TG_RUN_DIR'])
    directory.joinpath('fake-' + command).touch()
    if os.getenv('FAKE_HOLD') == command:
        while not directory.joinpath('fake-stopped').exists(): time.sleep(0.02)
    if os.getenv('FAKE_FAIL') == command:
        print('controlled failure')
        sys.exit(7)
    if command == 'run':
        directory.joinpath('result.json').write_text('{"status":"COMPLETED"}\n')
        print('Cenário aprovado pelo Docker falso')
'''


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tg tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo with spaces"
        self.root.mkdir()
        shutil.copy2(ROOT / "tg", self.root / "tg")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        docker = self.bin / "docker"
        docker.write_text(f"#!{sys.executable}\n" + FAKE_DOCKER)
        docker.chmod(0o755)
        self.calls = self.root / "calls.jsonl"
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "FAKE_CALLS": str(self.calls)}
        for key in ("TG_ENV_FILE", "TG_READY_TIMEOUT", "TG_SCENARIO_TIMEOUT", "TG_RUNS_DIR"):
            self.env.pop(key, None)

    def command(self, *args, **extra):
        return subprocess.run([str(self.root / "tg"), *args], env={**self.env, **extra},
                              cwd=self.temp.name, capture_output=True, text=True, timeout=15)

    def latest(self):
        return self.root / ".tg/runs" / (self.root / ".tg/latest").read_text().strip()

    def recorded(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_help_does_not_require_docker(self):
        self.assertEqual(self.command("help").returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_local_status_and_logs_work_offline_by_latest_id_and_path(self):
        directory = self.root / ".tg/runs/tg-local"
        directory.mkdir(parents=True)
        for name, value in {"status": "FAILED", "scenario": "logistics", "environment": "stopped",
                            "backend": "local-processes", "agent-1.jsonl": '{"type":"AGENT_ERROR"}',
                            "execution.jsonl": '{"type":"EXPERIMENT_FINISHED"}'}.items():
            (directory / name).write_text(value + "\n")
        (self.root / ".tg/latest").write_text(directory.name + "\n")
        for identifier in ((), (directory.name,), (str(directory),)):
            status = self.command("status", *identifier, FAKE_DAEMON_FAIL="1")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Backend: local-processes", status.stdout)
            self.assertIn("Estado: FAILED", status.stdout)
            logs = self.command("logs", *identifier, FAKE_DAEMON_FAIL="1")
            self.assertEqual(logs.returncode, 0, logs.stderr)
            self.assertIn("AGENT_ERROR", logs.stdout)
        self.assertFalse(self.calls.exists())

    def test_local_stop_does_not_call_docker(self):
        directory = self.root / ".tg/runs/tg-active-local"
        directory.mkdir(parents=True)
        for name, value in {"status": "RUNNING", "scenario": "test", "environment": "running"}.items():
            (directory / name).write_text(value + "\n")
        stopped = self.command("stop", directory.name)
        self.assertNotEqual(stopped.returncode, 0)
        self.assertIn("Ctrl+C", stopped.stderr)
        self.assertFalse(self.calls.exists())

    def test_doctor_is_read_only_and_checks_compose_version(self):
        self.assertEqual(self.command("doctor").returncode, 0)
        self.assertFalse((self.root / ".tg").exists())
        self.assertNotEqual(self.command("doctor", FAKE_VERSION="2.23.0").returncode, 0)
        self.assertNotEqual(self.command("doctor", FAKE_DAEMON_FAIL="1").returncode, 0)

    def test_success_exports_before_cleanup_and_logs_work_offline(self):
        result = self.command("demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        directory = self.latest()
        self.assertEqual((directory / "status").read_text().strip(), "COMPLETED")
        self.assertEqual((directory / "environment").read_text().strip(), "stopped")
        self.assertTrue((directory / "events.jsonl").exists())
        calls = self.recorded()
        down = next(i for i, c in enumerate(calls) if 'down' in c)
        cp = next(i for i, c in enumerate(calls) if 'cp' in c)
        self.assertLess(cp, down)
        self.assertIn('--volumes', calls[down])
        projects = {c[c.index('-p') + 1] for c in calls if '-p' in c}
        self.assertEqual(projects, {directory.name.lower()})
        count = len(calls)
        self.assertEqual(self.command("logs", FAKE_DAEMON_FAIL="1").returncode, 0)
        self.assertEqual(len(self.recorded()), count)

    def test_keep_then_stop_is_idempotent_and_scoped_to_run(self):
        self.assertEqual(self.command("demo", "--keep").returncode, 0)
        first = self.latest()
        self.assertEqual((first / 'environment').read_text().strip(), 'running')
        self.assertFalse(any('down' in c for c in self.recorded()))
        self.assertEqual(self.command("scenario", "messaging-basic", "--keep").returncode, 0)
        second = self.latest()
        self.assertNotEqual(first.name, second.name)
        self.assertEqual(self.command("stop", first.name).returncode, 0)
        downs = [c for c in self.recorded() if 'down' in c]
        self.assertEqual({c[c.index('-p') + 1] for c in downs}, {first.name.lower()})
        self.assertEqual((second / 'environment').read_text().strip(), 'running')
        before = len(self.recorded())
        self.assertEqual(self.command("stop", first.name).returncode, 0)
        self.assertEqual(len(self.recorded()), before)

    def test_failure_preserves_diagnostics_and_cleans_up(self):
        for phase in ('build', 'run'):
            with self.subTest(phase=phase):
                result = self.command('demo', FAKE_FAIL=phase)
                self.assertNotEqual(result.returncode, 0)
                directory = self.latest()
                self.assertEqual((directory / 'status').read_text().strip(), 'FAILED')
                self.assertEqual((directory / 'environment').read_text().strip(), 'stopped')
                log = 'build.log' if phase == 'build' else 'runner.log'
                self.assertIn('controlled failure', (directory / log).read_text())

    def test_export_failure_preserves_volume(self):
        self.command('demo', FAKE_COPY_FAIL='1')
        downs = [c for c in self.recorded() if 'down' in c]
        self.assertTrue(downs)
        self.assertNotIn('--volumes', downs[-1])

    def test_cleanup_failure_is_visible_and_can_be_retried(self):
        self.assertNotEqual(self.command('demo', FAKE_DOWN_FAIL='1').returncode, 0)
        self.assertEqual((self.latest() / 'environment').read_text().strip(), 'cleanup-failed')
        self.assertEqual(self.command('stop').returncode, 0)

    def test_rejects_unknown_scenarios_paths_and_invalid_timeouts(self):
        for args in [('scenario', 'unknown'), ('stop', '../../foreign'), ('demo', 'extra')]:
            self.assertNotEqual(self.command(*args).returncode, 0)
        self.assertNotEqual(self.command('demo', TG_READY_TIMEOUT='0').returncode, 0)
        self.assertNotEqual(self.command('doctor', 'heterogeneous-route', TG_ENV_FILE='missing').returncode, 0)

    def test_stop_during_build_prevents_starting_services(self):
        with subprocess.Popen([str(self.root / 'tg'), 'demo'], env={**self.env, 'FAKE_HOLD': 'build'},
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if list((self.root / '.tg').glob('runs/*/fake-build')): break
                time.sleep(0.02)
            else:
                process.kill()
                self.fail('build did not start')
            self.assertEqual(self.command('stop').returncode, 0)
            process.communicate(timeout=10)
            self.assertNotEqual(process.returncode, 0)
        self.assertFalse(any('up' in c for c in self.recorded()))
        self.assertEqual((self.latest() / 'status').read_text().strip(), 'CANCELLED')

    def test_signal_cleans_up_and_preserves_cancelled_status(self):
        with subprocess.Popen([str(self.root / 'tg'), 'demo'], env={**self.env, 'FAKE_HOLD': 'run'},
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if list((self.root / '.tg').glob('runs/*/fake-run')): break
                time.sleep(0.02)
            else:
                process.kill()
                self.fail('run did not start')
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=10)
            self.assertNotEqual(process.returncode, 0)
        self.assertEqual((self.latest() / 'status').read_text().strip(), 'CANCELLED')
        self.assertEqual((self.latest() / 'environment').read_text().strip(), 'stopped')


if __name__ == '__main__':
    unittest.main()
