import logging
import os
import random
import sys
import time

from google.protobuf import timestamp_pb2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../sdk/python/src"))

from contract.v1 import contract_pb2
from ariadne_sdk import Agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [execution-simulator] %(message)s",
)
log = logging.getLogger(__name__)


def _now():
    ts = timestamp_pb2.Timestamp()
    ts.GetCurrentTime()
    return ts


class ExecutionSimulatorAgent(Agent):
    def __init__(self, delay_ms, fail_rate, **kwargs):
        super().__init__(**kwargs)
        self.delay_ms = delay_ms
        self.fail_rate = fail_rate

    def execute_task(self, task):
        log.info("task received task_id=%s goal=%s", task.task_id, task.goal)

        time.sleep(self.delay_ms / 1000)

        if random.random() < self.fail_rate:
            log.warning("task failed (intentional) task_id=%s", task.task_id)
            result = contract_pb2.TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=contract_pb2.TASK_STATUS_FAILED,
                completed_at=_now(),
                trace=task.trace,
                error=contract_pb2.ErrorInfo(
                    code=contract_pb2.ERROR_CODE_EXECUTION_FAILED,
                    message="intentional failure (fail_rate)",
                    retryable=True,
                ),
            )
        else:
            log.info("task completed task_id=%s", task.task_id)
            result = contract_pb2.TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=contract_pb2.TASK_STATUS_COMPLETED,
                completed_at=_now(),
                trace=task.trace,
            )

        return result


def main():
    agent_id = os.getenv("AGENT_ID", "execution-simulator-01")
    host = os.getenv("AGENT_HOST", "localhost")
    port = int(os.getenv("AGENT_PORT", "60051"))
    registry_addr = os.getenv("REGISTRY_ADDR", "localhost:50051")
    capability = os.getenv("CAPABILITY", "echo")
    delay_ms = int(os.getenv("DELAY_MS", "100"))
    fail_rate = float(os.getenv("FAIL_RATE", "0.0"))
    reported_load = os.getenv("REPORTED_LOAD")

    agent = ExecutionSimulatorAgent(
        agent_id=agent_id,
        name=f"Execution Simulator ({agent_id})",
        capabilities=[capability],
        host=host,
        port=port,
        registry_addr=registry_addr,
        runtime="python-mock",
        delay_ms=delay_ms,
        fail_rate=fail_rate,
        reported_load=(
            float(reported_load) if reported_load is not None else None
        ),
    )
    agent.run()


if __name__ == "__main__":
    main()
