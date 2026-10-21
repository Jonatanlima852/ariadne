import logging
import os
import sys

from google.protobuf import timestamp_pb2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../sdk/python/src"))

from contract.v1 import contract_pb2
from ariadne_sdk import Agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [failing-agent] %(message)s",
)
log = logging.getLogger(__name__)


def _now():
    ts = timestamp_pb2.Timestamp()
    ts.GetCurrentTime()
    return ts


class FailingAgent(Agent):
    """Agente que sempre falha — útil para testar a reação do orchestrator."""

    def execute_task(self, task):
        log.warning("task received task_id=%s — falhando de propósito", task.task_id)

        return contract_pb2.TaskResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=contract_pb2.TASK_STATUS_FAILED,
            completed_at=_now(),
            trace=task.trace,
            error=contract_pb2.ErrorInfo(
                code=contract_pb2.ERROR_CODE_EXECUTION_FAILED,
                message="this agent always fails (FailingAgent)",
                retryable=True,
            ),
        )


def main():
    agent_id = os.getenv("AGENT_ID", "failing-agent-01")
    host = os.getenv("AGENT_HOST", "localhost")
    port = int(os.getenv("AGENT_PORT", "60053"))
    registry_addr = os.getenv("REGISTRY_ADDR", "localhost:50051")
    capability = os.getenv("CAPABILITY", "echo")

    agent = FailingAgent(
        agent_id=agent_id,
        name=f"Failing Agent ({agent_id})",
        capabilities=[capability],
        host=host,
        port=port,
        registry_addr=registry_addr,
        runtime="python-sdk-failing",
    )
    agent.run()


if __name__ == "__main__":
    main()
