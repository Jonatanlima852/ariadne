import logging
import os
import sys

from google.protobuf import struct_pb2, timestamp_pb2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../sdk/python/src"))

from contract.v1 import contract_pb2
from ariadne_sdk import Agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [echo-agent] %(message)s",
)
log = logging.getLogger(__name__)


def _now():
    ts = timestamp_pb2.Timestamp()
    ts.GetCurrentTime()
    return ts


class EchoAgent(Agent):
    """Agente mínimo: devolve o goal da task como resultado."""

    def execute_task(self, task):
        log.info("task received task_id=%s goal=%s", task.task_id, task.goal)

        output = struct_pb2.Struct()
        output.update({"echo": task.goal})

        return contract_pb2.TaskResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=contract_pb2.TASK_STATUS_COMPLETED,
            completed_at=_now(),
            trace=task.trace,
            output=output,
        )


def main():
    agent_id = os.getenv("AGENT_ID", "echo-agent-01")
    host = os.getenv("AGENT_HOST", "localhost")
    port = int(os.getenv("AGENT_PORT", "60052"))
    registry_addr = os.getenv("REGISTRY_ADDR", "localhost:50051")
    capability = os.getenv("CAPABILITY", "echo")
    reported_load = os.getenv("REPORTED_LOAD")

    agent = EchoAgent(
        agent_id=agent_id,
        name=f"Echo Agent ({agent_id})",
        capabilities=[capability],
        host=host,
        port=port,
        registry_addr=registry_addr,
        runtime="python-sdk-echo",
        reported_load=(
            float(reported_load) if reported_load is not None else None
        ),
    )
    agent.run()


if __name__ == "__main__":
    main()
