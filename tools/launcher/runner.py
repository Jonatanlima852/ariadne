"""Prontidão e execução dos cenários dentro da rede Docker da execução."""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import runpy
import signal
import sys
import time
import traceback
from datetime import datetime, timezone

import grpc
from contract.v1 import contract_pb2 as pb, contract_pb2_grpc as rpc

ROOT = Path(__file__).resolve().parents[2]
AGENTS = {
    "demo": {"mock-agent-01": "echo"},
    "workflow-sequential": {"workflow-echo": "echo"},
    "failure-reassignment": {"a-slow": "recovery-test", "b-healthy": "recovery-test"},
    "messaging-basic": {},
    "heterogeneous-route": {"bdi-agent-01": "route-planning", "llm-agent-01": "task-decomposition"},
    "logistics-mission": {"bdi-agent-01": "logistics-execution", "llm-agent-01": "logistics-interpret"},
}


def wait_for_agents(stub, expected, *, timeout, clock=time.monotonic, sleep=time.sleep,
                    connect=None):
    """Espera todos os agentes, incluindo capacidade, estado e endpoint utilizável."""
    deadline = clock() + timeout
    pending = dict(expected)
    while pending:
        for agent_id, capability in list(pending.items()):
            remaining = deadline - clock()
            if remaining <= 0:
                break
            try:
                agent = stub.GetAgent(pb.GetAgentRequest(agent_id=agent_id), timeout=min(1, remaining)).agent
                capabilities = {item.capability_id for item in agent.capabilities}
                if (agent.agent_id == agent_id
                        and agent.status in (pb.AGENT_STATUS_ALIVE, pb.AGENT_STATUS_BUSY)
                        and capability in capabilities
                        and agent.endpoint.address):
                    if connect is not None:
                        connect(agent.endpoint.address, max(0.01, deadline - clock()))
                    del pending[agent_id]
            except (grpc.RpcError, grpc.FutureTimeoutError, TimeoutError):
                pass
        if not pending:
            return
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError("Agentes não ficaram prontos: " + ", ".join(sorted(pending)))
        sleep(min(0.5, remaining))


def wait_for_channel(address, timeout):
    with grpc.insecure_channel(address) as channel:
        future = grpc.channel_ready_future(channel)
        try:
            future.result(timeout=timeout)
        finally:
            future.cancel()


def ready(scenario, timeout):
    deadline = time.monotonic() + timeout
    if scenario == "messaging-basic":
        wait_for_channel(os.environ["MESSAGING_ADDR"], timeout)
        return
    registry = os.environ["REGISTRY_ADDR"]
    wait_for_channel(registry, timeout)
    wait_for_channel(os.environ["ORCHESTRATOR_ADDR"], max(0.01, deadline - time.monotonic()))
    with grpc.insecure_channel(registry) as channel:
        wait_for_agents(
            rpc.RegistryServiceStub(channel), AGENTS[scenario],
            timeout=max(0.01, deadline - time.monotonic()),
            connect=lambda address, remaining: wait_for_channel(address, min(1, remaining)),
        )


def demo():
    from ariadne_sdk import RuntimeClient

    with RuntimeClient("demo", os.environ["ORCHESTRATOR_ADDR"]) as scenario:
        result = scenario.submit(
            "echo", goal="Teste ponta a ponta", capabilities=["echo"],
        ).assert_completed()
        if result.agent_id != "mock-agent-01":
            raise AssertionError(f"Agente inesperado: {result.agent_id}")
        scenario.report().save(os.environ["SCENARIO_REPORT_PATH"])
        print(f"Tarefa concluída por {result.agent_id}; trace_id={scenario.trace_id}")


def timed_out(_signal, _frame):
    raise TimeoutError("Tempo limite do cenário excedido; consulte os logs dos serviços.")


def main():
    scenario = sys.argv[1]
    if scenario not in AGENTS:
        raise SystemExit("Cenário desconhecido")
    directory = Path(os.environ["SCENARIO_REPORT_PATH"]).parent
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    summary = {"scenario": scenario, "started_at": datetime.now(timezone.utc).isoformat()}
    code = 1
    signal.signal(signal.SIGALRM, timed_out)
    try:
        print("Verificando endpoints e agentes registrados…", flush=True)
        ready(scenario, int(os.getenv("ARIADNE_READY_TIMEOUT", "90")))
        print("Prontidão confirmada. Executando e verificando o resultado…", flush=True)
        signal.alarm(int(os.getenv("ARIADNE_SCENARIO_TIMEOUT", "180")))
        with (directory / "scenario.log").open("w", encoding="utf-8") as output:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                if scenario == "demo":
                    demo()
                else:
                    runpy.run_path(str(ROOT / "studies/scenarios" / {"workflow-sequential": "sequential_workflow", "failure-reassignment": "failure_reassignment", "messaging-basic": "messaging", "heterogeneous-route": "heterogeneous_route", "logistics-mission": "logistics"}[scenario] / "docker/scenario.py"), run_name="__main__")
        summary["status"] = "COMPLETED"
        code = 0
        print(f"Cenário aprovado: {scenario}")
        print("Resultado estruturado: result.json; saída detalhada: scenario.log")
    except Exception as error:
        summary.update(status="FAILED", error=str(error) or type(error).__name__)
        traceback.print_exc()
        print("Falha: " + summary["error"], file=sys.stderr)
    finally:
        signal.alarm(0)
        summary["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
