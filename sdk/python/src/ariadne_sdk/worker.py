"""Processo de um agente declarado em um arquivo de experimento."""

import argparse
import logging
import os
from pathlib import Path
import signal
import sys
import threading

from google.protobuf.json_format import MessageToDict

from ariadne_sdk.evidence import EventLog, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("index", type=int)
    parser.add_argument("registry")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    stopped = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())

    from ariadne_sdk.execution import import_roots, load_scenario
    sys.path[:0] = import_roots(args.source)
    scenario = load_scenario(args.source)
    agent = scenario.agents[args.index]
    # O executor informa o nome do serviço Compose e a porta fixa do contêiner.
    agent.host = os.getenv("ARIADNE_AGENT_HOST", "127.0.0.1")
    agent.port = int(os.getenv("ARIADNE_AGENT_PORT", "0"))
    agent.registry_addr = args.registry
    agent.listen_host = "127.0.0.1" if agent.host == "127.0.0.1" else "[::]"
    events = EventLog(
        args.directory / f"agent-{args.index + 1}.jsonl",
        execution_id=args.directory.name, agent_id=agent.agent_id,
    )

    def task_event(event_type, task, result=None, **fields):
        fields.update(
            task_id=task.task_id, trace_id=task.trace.trace_id,
            parent_task_id=task.parent_task_id, attempt=task.attempt,
        )
        if result is None:
            fields["task"] = MessageToDict(task, preserving_proto_field_name=True)
        else:
            fields["result"] = MessageToDict(result, preserving_proto_field_name=True)
        events.emit(event_type, **fields)

    agent.event_sink = task_event
    events.emit("AGENT_STARTING", capabilities=agent.capabilities)
    try:
        if stopped.is_set():
            return 130
        agent.start()
        endpoint = f"{agent.host}:{agent.port}"
        events.emit("AGENT_READY", endpoint=endpoint)
        write_json(args.directory / f"agent-{args.index + 1}.ready", {"address": endpoint, "agent_id": agent.agent_id})
        stopped.wait()
    except Exception as error:
        events.emit("AGENT_ERROR", error=str(error), error_type=type(error).__name__)
        raise
    finally:
        agent.stop()
        events.emit("AGENT_STOPPED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
