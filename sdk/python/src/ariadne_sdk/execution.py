"""Executor de descrições Python: serviços Go e agentes em contêineres Docker."""

from __future__ import annotations

from collections.abc import MutableMapping
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import signal
import sys
import time
import uuid

import grpc

from contract.v1 import contract_pb2 as pb, contract_pb2_grpc as rpc
from ariadne_sdk.agent import Agent
from ariadne_sdk.compose import SERVICES, Compose, compose_document, forwarded_names, repository_root
from ariadne_sdk.evidence import EventLog, utc_now, write_json
from ariadne_sdk.provenance import capture
from ariadne_sdk.scenario import Scenario
from ariadne_sdk.client import RuntimeClient


def import_roots(source):
    """Permite descrições em pacotes Python sem sys.path no experimento."""
    directory = Path(source).resolve().parent
    root = directory
    while (root / "__init__.py").is_file():
        root = root.parent
    return list(dict.fromkeys((str(directory), str(root))))


class _EnvironmentRecorder(MutableMapping):
    """Anota quais variáveis a descrição consultou, para repassá-las aos contêineres."""

    def __init__(self, target):
        self.target, self.read = target, set()

    def __getitem__(self, key):
        self.read.add(key)
        return self.target[key]

    def get(self, key, default=None):
        self.read.add(key)
        return self.target.get(key, default)

    def __contains__(self, key):
        self.read.add(key)
        return key in self.target

    def __setitem__(self, key, value):
        self.target[key] = value

    def __delitem__(self, key):
        del self.target[key]

    def __iter__(self):
        return iter(self.target)

    def __len__(self):
        return len(self.target)

    def copy(self):
        return dict(self.target)


def load_scenario(source):
    """Carrega a variável pública `scenario`; não invoca callbacks de execução."""
    source = Path(source).resolve(strict=True)
    previous_path = sys.path[:]
    recorder = _EnvironmentRecorder(os.environ)
    os.environ = recorder
    try:
        sys.path[:0] = import_roots(source)
        namespace = runpy.run_path(str(source), run_name="__ariadne_experiment__")
    finally:
        os.environ = recorder.target
        sys.path[:] = previous_path
    scenario = namespace.get("scenario")
    if not isinstance(scenario, Scenario) or scenario.tasks is None:
        raise ValueError("declare scenario = Scenario(agents=[...], tasks=[...]) or Scenario(agents=[...], mission=Mission(...))")
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
    required = {capability for step in steps for capability in step["capabilities"]}
    if scenario.mission is not None:
        # The planner decides the other capabilities at run time; only it is known now.
        required.add(scenario.mission.planner_capability)
    missing = required - capabilities
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
    scenario.environment = tuple(sorted(name for name in recorder.read if isinstance(name, str) and name in os.environ))
    return scenario


def wait_ready(compose, path, timeout, *, address=None):
    """Espera o arquivo de prontidão escrito pelo contêiner e, depois, o canal gRPC."""
    deadline = time.monotonic() + timeout
    checked = time.monotonic()
    while not path.exists():
        if time.monotonic() - checked >= 1:
            compose.check()
            checked = time.monotonic()
        if time.monotonic() >= deadline:
            compose.check()
            raise TimeoutError(f"startup timed out waiting for {path.name}")
        time.sleep(0.05)
    address = address or json.loads(path.read_text())["address"]
    with grpc.insecure_channel(address) as channel:
        ready = grpc.channel_ready_future(channel)
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"gRPC not ready: {address}")
                try:
                    ready.result(timeout=min(0.5, remaining))
                    return address
                except grpc.FutureTimeoutError:
                    compose.check()
        finally:
            ready.cancel()


def run_mission_sample(client, mission, *, rpc_timeout=None):
    """Envia a missão declarada pelo cliente de cenário e devolve ``MissionResult``."""
    return client.run_mission(
        mission.goal, context=mission.context, limits=mission.limits,
        planner_capability=mission.planner_capability, retry_policy=mission.retry_policy,
        selection_policy=mission.selection_policy, metadata=mission.metadata,
        rpc_timeout=rpc_timeout,
    )


def run_experiment(source, *, output_root, ready_timeout=60, task_timeout=60, repeat=1, execution_id=None):
    source = Path(source).resolve(strict=True)
    scenario = load_scenario(source)
    provenance = capture(source, scenario.artifacts)
    execution_id = execution_id or ("ariadne-" + uuid.uuid4().hex)
    if not execution_id.startswith("ariadne-") or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for c in execution_id):
        raise ValueError("invalid execution_id")
    root = repository_root()
    directory = Path(output_root).resolve() / execution_id
    directory.mkdir(parents=True)
    print(f"Experimento: {scenario.name}\nEvidências: {directory}", flush=True)
    events = EventLog(directory / "execution.jsonl", execution_id=directory.name)
    compose = Compose(directory, execution_id.lower(), events)
    started = time.monotonic()
    summary = {"scenario": scenario.name, "started_at": utc_now(), "status": "RUNNING"}
    definition = scenario.definition()
    manifest = {
        "schema_version": 2, "execution_id": directory.name, "backend": "docker-compose",
        "compose_project": compose.project, "repository_root": str(root),
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "python": sys.version, "platform": platform.platform(), "contract_version": "2.0.0",
        "repeat": repeat, "ready_timeout_seconds": ready_timeout, "rpc_timeout_seconds": task_timeout,
        "metadata": scenario.metadata,
        "provenance": provenance,
        "agents": [{"agent_id": agent.agent_id, "capabilities": agent.capabilities, "service": f"agent-{index + 1}"}
                   for index, agent in enumerate(scenario.agents)], "steps": definition,
        "mission": scenario.mission.to_dict() if scenario.mission is not None else None,
        "forwarded_environment": forwarded_names(scenario),
    }
    write_json(directory / "manifest.json", manifest)
    # Keep the authored description with its evidence; never copy environment files.
    shutil.copyfile(source, directory / "experiment.py")
    (directory / "scenario").write_text(scenario.name + "\n")
    (directory / "status").write_text("RUNNING\n")
    (directory / "environment").write_text("starting\n")
    write_json(directory / "summary.json", summary)
    (directory / "backend").write_text("docker-compose\n")
    latest = directory.parent.parent / f"latest.{directory.name}"
    latest.write_text(directory.name + "\n")
    latest.replace(directory.parent.parent / "latest")
    events.emit("EXPERIMENT_STARTED")
    services = [*SERVICES, *(f"agent-{index + 1}" for index in range(len(scenario.agents)))]
    try:
        manifest["compose_version"] = Compose.available()
        compose.write(compose_document(root=root, directory=directory, source=source, scenario=scenario))
        print("Preparando imagens (a primeira vez pode demorar)…", flush=True)
        compose.build()
        print("Iniciando serviços e agentes em contêineres…", flush=True)
        compose.up(*SERVICES)
        addresses = {}
        for service in SERVICES:
            published = compose.port(service, {"registry": 50051, "orchestrator": 50052, "messaging": 50053}[service])
            addresses[service] = wait_ready(compose, directory / f"{service}.ready", ready_timeout, address=published)
        manifest["addresses"] = addresses
        write_json(directory / "manifest.json", manifest)
        compose.up(*(f"agent-{index + 1}" for index in range(len(scenario.agents))))
        for index, agent in enumerate(scenario.agents):
            ready_file = directory / f"agent-{index + 1}.ready"
            deadline = time.monotonic() + ready_timeout
            checked = time.monotonic()
            while not ready_file.exists():
                if time.monotonic() - checked >= 1:
                    compose.check()
                    checked = time.monotonic()
                if time.monotonic() >= deadline:
                    compose.check()
                    raise TimeoutError(f"startup timed out waiting for {ready_file.name}")
                time.sleep(0.05)
            endpoint = json.loads(ready_file.read_text())["address"]
            with grpc.insecure_channel(addresses["registry"]) as channel:
                registered = rpc.RegistryServiceStub(channel).GetAgent(
                    pb.GetAgentRequest(agent_id=agent.agent_id), timeout=ready_timeout,
                ).agent
            if (registered.endpoint.address != endpoint or
                    set(agent.capabilities) != {c.capability_id for c in registered.capabilities}):
                raise RuntimeError(f"registration differs from declaration: {agent.agent_id}")
        manifest["images"] = compose.images()
        write_json(directory / "manifest.json", manifest)
        (directory / "environment").write_text("running\n")
        events.emit("EXPERIMENT_READY", addresses=addresses)
        print("Runtime e agentes prontos. Executando cenário…", flush=True)
        failed = False
        for sample in range(1, repeat + 1):
            compose.check()
            with RuntimeClient(scenario.name, addresses["orchestrator"]) as client:
                events.emit("SAMPLE_STARTED", sample=sample, trace_id=client.trace_id)
                sample_start = time.perf_counter()
                try:
                    if scenario.mission is not None:
                        result = run_mission_sample(client, scenario.mission, rpc_timeout=task_timeout)
                        record = result.to_dict()
                        # The contract JSON alone is what tools/mission-viewer reads.
                        result.save(directory / "mission-result.json")
                        failed = failed or result.status != "MISSION_STATUS_COMPLETED"
                    else:
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
            if compose.file.is_file():
                compose.save_logs(services)
                if compose.down() == 0:
                    (directory / "environment").write_text("stopped\n")
                else:
                    (directory / "environment").write_text("cleanup-failed\n")
                    summary.setdefault("error", f"could not remove containers; run: ./ariadne stop {directory.name}")
            else:
                (directory / "environment").write_text("stopped\n")
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
        write_json(directory / "manifest.json", manifest)
        summary.update(completed_at=utc_now(), elapsed_ms=(time.monotonic() - started) * 1000)
        write_json(directory / "summary.json", summary)
        (directory / "status").write_text(summary["status"] + "\n")
        events.emit("EXPERIMENT_FINISHED", **summary)
    print(f"Estado: {summary['status']}\nEvidências: {directory}", flush=True)
    if summary.get("error"):
        print(summary["error"], file=sys.stderr)
    return directory, summary
