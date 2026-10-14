"""Executor local de descrições Python sobre os serviços Go reais."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import signal
import subprocess
import sys
import time
import uuid

import grpc

from contract.v1 import contract_pb2 as pb, contract_pb2_grpc as rpc
from ariadne_sdk.agent import Agent
from ariadne_sdk.evidence import EventLog, utc_now, write_json
from ariadne_sdk.provenance import capture
from ariadne_sdk.scenario import Scenario
from ariadne_sdk.client import RuntimeClient

SERVICES = ("registry", "orchestrator", "messaging")


def import_roots(source):
    """Permite descrições em pacotes Python sem sys.path no experimento."""
    directory = Path(source).resolve().parent
    root = directory
    while (root / "__init__.py").is_file():
        root = root.parent
    return list(dict.fromkeys((str(directory), str(root))))


def load_scenario(source):
    """Carrega a variável pública `scenario`; não invoca callbacks de execução."""
    source = Path(source).resolve(strict=True)
    previous_path = sys.path[:]
    try:
        sys.path[:0] = import_roots(source)
        namespace = runpy.run_path(str(source), run_name="__ariadne_experiment__")
    finally:
        sys.path[:] = previous_path
    scenario = namespace.get("scenario")
    if not isinstance(scenario, Scenario) or scenario.tasks is None:
        raise ValueError("declare scenario = Scenario(agents=[...], tasks=[...])")
    if not scenario.agents or any(not isinstance(agent, Agent) for agent in scenario.agents):
        raise ValueError("scenario.agents must contain Agent instances")
    ids = [agent.agent_id for agent in scenario.agents]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("agents must have nonempty, unique names or agent_ids")
    if any(not agent.capabilities for agent in scenario.agents):
        raise ValueError("each agent must declare capabilities")
    steps = scenario.definition()
    json.dumps(scenario.metadata, allow_nan=False)
    capabilities = {capability for agent in scenario.agents for capability in agent.capabilities}
    missing = {capability for step in steps for capability in step["capabilities"]} - capabilities
    if missing:
        raise ValueError("no declared agent provides: " + ", ".join(sorted(missing)))
    if scenario.name == "experiment":
        scenario.name = source.stem
    artifacts = []
    for value in (*scenario.artifacts, source):
        path = Path(value)
        path = (path if path.is_absolute() else source.parent / path).resolve(strict=True)
        if not path.is_file() or path.name == ".env" or path.name.startswith(".env."):
            raise ValueError(f"artifact must be a regular, non-credential file: {path}")
        artifacts.append(path)
    # Preserva a origem quando outro arquivo reutiliza uma descrição carregada.
    scenario.artifacts = tuple(dict.fromkeys(artifacts))
    return scenario


class Processes:
    """Possui somente os processos desta execução, incluindo startup parcial."""

    def __init__(self, directory, events=None):
        self.directory = directory
        self.children = []
        self.events = events

    def start(self, command, name, *, env=None, cwd=None):
        with (self.directory / f"{name}.log").open("ab") as output:
            child = subprocess.Popen(
                command, stdout=output, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, env=env, cwd=cwd,
                start_new_session=(os.name == "posix"),
            )
        self.children.append((name, child))
        if self.events:
            self.events.emit("PROCESS_STARTED", process=name, pid=child.pid)
        return child

    def check(self):
        for name, child in self.children:
            if child.poll() is not None:
                raise RuntimeError(f"{name} exited with {child.returncode}; see {name}.log")

    @staticmethod
    def signal(child, signum):
        try:
            if os.name == "posix":
                os.killpg(child.pid, signum)
            elif child.poll() is None:
                child.terminate() if signum == signal.SIGTERM else child.kill()
        except ProcessLookupError:
            pass

    def stop(self):
        # Agents unregister while Registry is still alive.
        for _, child in reversed(self.children):
            forced = False
            if child.poll() is None:
                self.signal(child, signal.SIGTERM)
                try:
                    child.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    forced = True
                    self.signal(child, signal.SIGKILL)
                    child.wait(timeout=3)
            # Reap any subprocesses left in the managed process group.
            if os.name == "posix":
                self.signal(child, signal.SIGKILL)
            if self.events:
                self.events.emit("PROCESS_STOPPED", pid=child.pid, exit_code=child.returncode, forced=forced)


def wait_ready(processes, path, timeout, *, agent=False):
    deadline = time.monotonic() + timeout
    while not path.exists():
        processes.check()
        if time.monotonic() >= deadline:
            raise TimeoutError(f"startup timed out waiting for {path.name}")
        time.sleep(0.05)
    address = json.loads(path.read_text())["address"] if agent else path.read_text().strip()
    with grpc.insecure_channel(address) as channel:
        ready = grpc.channel_ready_future(channel)
        try:
            while True:
                processes.check()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"gRPC not ready: {address}")
                try:
                    ready.result(timeout=min(0.2, remaining))
                    return address
                except grpc.FutureTimeoutError:
                    pass
        finally:
            ready.cancel()


def build_runtime(source, destination, processes):
    if shutil.which("go") is None:
        raise RuntimeError("Go is required to prepare the runtime; alternatively use --runtime-dir")
    destination.mkdir(parents=True, exist_ok=True)
    for service in SERVICES:
        binary = destination / f"ariadne-{service}"
        child = processes.start(
            ["go", "build", "-o", str(binary), f"./services/{service}/cmd"],
            "build", cwd=source,
        )
        try:
            code = child.wait(timeout=300)
        except subprocess.TimeoutExpired as error:
            raise TimeoutError("Go build timed out; see build.log") from error
        if code:
            raise RuntimeError("could not build Go runtime; see build.log")
        processes.children.remove(("build", child))


def run_experiment(source, *, output_root, runtime_dir=None, runtime_source=None,
                   ready_timeout=30, task_timeout=60, repeat=1, execution_id=None):
    source = Path(source).resolve(strict=True)
    scenario = load_scenario(source)
    provenance = capture(source, scenario.artifacts)
    execution_id = execution_id or ("ariadne-" + uuid.uuid4().hex)
    if not execution_id.startswith("ariadne-") or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for c in execution_id):
        raise ValueError("invalid execution_id")
    directory = Path(output_root).resolve() / execution_id
    directory.mkdir(parents=True)
    print(f"Experimento: {scenario.name}\nEvidências: {directory}", flush=True)
    events = EventLog(directory / "execution.jsonl", execution_id=directory.name)
    processes = Processes(directory, events)
    started = time.monotonic()
    summary = {"scenario": scenario.name, "started_at": utc_now(), "status": "RUNNING"}
    definition = scenario.definition()
    manifest = {
        "schema_version": 1, "execution_id": directory.name, "backend": "local-processes",
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "python": sys.version, "platform": platform.platform(), "contract_version": "1.0.0",
        "repeat": repeat, "ready_timeout_seconds": ready_timeout, "rpc_timeout_seconds": task_timeout,
        "metadata": scenario.metadata,
        "provenance": provenance,
        "agents": [{"agent_id": agent.agent_id, "capabilities": agent.capabilities}
                   for agent in scenario.agents], "steps": definition,
    }
    write_json(directory / "manifest.json", manifest)
    # Keep the authored description with its evidence; never copy environment files.
    shutil.copyfile(source, directory / "experiment.py")
    (directory / "scenario").write_text(scenario.name + "\n")
    (directory / "status").write_text("RUNNING\n")
    (directory / "environment").write_text("starting\n")
    write_json(directory / "summary.json", summary)
    (directory / "backend").write_text("local-processes\n")
    latest = directory.parent.parent / f"latest.{directory.name}"
    latest.write_text(directory.name + "\n")
    latest.replace(directory.parent.parent / "latest")
    events.emit("EXPERIMENT_STARTED")
    try:
        if runtime_source is not None:
            runtime_source = Path(runtime_source).resolve(strict=True)
            runtime_dir = Path(output_root).resolve().parent / "bin"
            print("Preparando runtime Go (cache de compilação reutilizado)…", flush=True)
            build_runtime(runtime_source, runtime_dir, processes)
        if runtime_dir is None:
            raise ValueError("provide --runtime-dir or ARIADNE_RUNTIME_DIR with ariadne-registry, ariadne-orchestrator, ariadne-messaging")
        runtime_dir = Path(runtime_dir).resolve(strict=True)
        binaries = {service: runtime_dir / f"ariadne-{service}" for service in SERVICES}
        for binary in binaries.values():
            if not binary.is_file() or not os.access(binary, os.X_OK):
                raise ValueError(f"runtime executable not found: {binary}")
        manifest["binaries_sha256"] = {
            name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in binaries.items()
        }
        addresses = {}
        for service, binary in binaries.items():
            ready_file = directory / f"{service}.ready"
            env = {**os.environ, "ARIADNE_JSON_LOGS": "1", "ARIADNE_READY_FILE": str(ready_file)}
            if service == "registry":
                env["REGISTRY_ADDR"] = "127.0.0.1:0"
            else:
                env["REGISTRY_ADDR"] = addresses["registry"]
                env[f"{service.upper()}_ADDR"] = "127.0.0.1:0"
                env["EVENTS_PATH"] = str(directory / ("events.jsonl" if service == "orchestrator" else "message-events.jsonl"))
            processes.start([str(binary)], service, env=env)
            addresses[service] = wait_ready(processes, ready_file, ready_timeout)
        manifest["addresses"] = addresses
        write_json(directory / "manifest.json", manifest)
        env = {**os.environ, **{f"{name.upper()}_ADDR": addr for name, addr in addresses.items()}}
        for index, agent in enumerate(scenario.agents):
            processes.start([
                sys.executable, "-m", "ariadne_sdk.worker", str(source), str(index),
                addresses["registry"], str(directory),
            ], f"agent-{index + 1}", env=env)
            endpoint = wait_ready(processes, directory / f"agent-{index + 1}.ready", ready_timeout, agent=True)
            with grpc.insecure_channel(addresses["registry"]) as channel:
                registered = rpc.RegistryServiceStub(channel).GetAgent(
                    pb.GetAgentRequest(agent_id=agent.agent_id), timeout=ready_timeout,
                ).agent
            if (registered.endpoint.address != endpoint or
                    set(agent.capabilities) != {c.capability_id for c in registered.capabilities}):
                raise RuntimeError(f"registration differs from declaration: {agent.agent_id}")
        manifest["processes"] = [{"name": name, "pid": child.pid} for name, child in processes.children]
        write_json(directory / "manifest.json", manifest)
        (directory / "environment").write_text("running\n")
        events.emit("EXPERIMENT_READY", addresses=addresses)
        print("Runtime e agentes prontos. Executando cenário…", flush=True)
        failed = False
        for sample in range(1, repeat + 1):
            processes.check()
            with RuntimeClient(scenario.name, addresses["orchestrator"]) as client:
                events.emit("SAMPLE_STARTED", sample=sample, trace_id=client.trace_id)
                sample_start = time.perf_counter()
                try:
                    result = client.submit_workflow(
                        scenario.name, steps=definition, final_step_id=definition[-1]["step_id"],
                        rpc_timeout=task_timeout,
                    )
                    record = result.to_dict()
                    failed = failed or result.status != "WORKFLOW_STATUS_COMPLETED"
                except KeyboardInterrupt:
                    events.emit("SAMPLE_CANCELLED", sample=sample, trace_id=client.trace_id)
                    raise
                except Exception as error:
                    record = {"status": "RPC_FAILED", "trace_id": client.trace_id, "error": str(error)}
                    failed = True
                record.update(sample=sample, client_duration_ms=(time.perf_counter() - sample_start) * 1000)
                with (directory / "results.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                write_json(directory / "result.json", record)
                events.emit("SAMPLE_FINISHED", sample=sample, trace_id=client.trace_id, status=record["status"])
                print(f"Amostra {sample}/{repeat}: {record['status']}", flush=True)
                if "output" in record:
                    preview = json.dumps(record["output"], ensure_ascii=False)
                    print("Resultado: " + (preview if len(preview) <= 500 else preview[:500] + "…"), flush=True)
        summary["status"] = "FAILED" if failed else "COMPLETED"
    except KeyboardInterrupt:
        summary.update(status="CANCELLED", error="execution interrupted")
    except Exception as error:
        summary.update(status="FAILED", error=str(error), error_type=type(error).__name__)
    finally:
        events.emit("EXPERIMENT_STOPPING", status=summary["status"])
        # Finish cleanup even if another Ctrl+C arrives.
        handlers = {sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            processes.stop()
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
        (directory / "environment").write_text("stopped\n")
        summary.update(completed_at=utc_now(), elapsed_ms=(time.monotonic() - started) * 1000)
        write_json(directory / "summary.json", summary)
        (directory / "status").write_text(summary["status"] + "\n")
        events.emit("EXPERIMENT_FINISHED", **summary)
    print(f"Estado: {summary['status']}\nEvidências: {directory}", flush=True)
    if summary.get("error"):
        print(summary["error"], file=sys.stderr)
    return directory, summary
