import unittest
from datetime import datetime, timezone

from contract.v1 import contract_pb2
from ariadne_sdk import Agent, Task, TaskResult


def build_agent(agent_type):
    return agent_type(
        agent_id="agent-1",
        name="Agent",
        capabilities=["test"],
        host="localhost",
        port=1,
        registry_addr="localhost:50051",
    )


class FriendlyAgent(Agent):
    def handle(self, task):
        return TaskResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status="TASK_STATUS_COMPLETED",
            output={"received": task.payload["value"]},
            trace=task.trace,
        )


class InvalidAgent(Agent):
    def handle(self, task):
        raise ValueError("entrada inválida")


class TimeoutAgent(Agent):
    def handle(self, task):
        raise TimeoutError("tempo esgotado")


class TaskModelTests(unittest.TestCase):
    def test_task_round_trip_preserves_domain_fields(self):
        task = Task(
            task_id="task-1",
            type="PLAN_ROUTE",
            goal="Ir de A para D",
            payload={"origin": "A", "options": ["B", "C"]},
            required_capabilities=("route-planning",),
            trace={"trace_id": "trace-1", "correlation_id": "run-1"},
            priority=3,
            selection_policy="ROUND_ROBIN",
            parent_task_id="root-1",
            attempt=2,
            metadata={"source": "test"},
            bdi={"goal": "chegar em D", "intention_id": "intent-1"},
        )

        converted = Task.from_proto(task.to_proto())

        self.assertEqual(converted, task)
        self.assertIsInstance(converted.payload, dict)
        self.assertEqual(converted.payload["options"], ["B", "C"])
        self.assertEqual(
            converted.selection_policy,
            "SELECTION_POLICY_ROUND_ROBIN",
        )

    def test_result_round_trip_preserves_success(self):
        completed_at = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        result = TaskResult(
            task_id="task-1",
            agent_id="agent-1",
            status="TASK_STATUS_COMPLETED",
            output={"route": ["A", "B", "D"]},
            metadata={"selected_plan": "via_b"},
            trace={"trace_id": "trace-1"},
            completed_at=completed_at,
        )

        converted = TaskResult.from_proto(result.to_proto())

        self.assertEqual(converted, result)

    def test_result_round_trip_preserves_error(self):
        result = TaskResult(
            task_id="task-2",
            agent_id="agent-1",
            status="TASK_STATUS_FAILED",
            error_code="ERROR_CODE_INVALID_TASK",
            error_message="payload inválido",
            retryable=False,
            trace={"trace_id": "trace-2"},
        )

        converted = TaskResult.from_proto(result.to_proto())

        self.assertEqual(converted.error_code, "ERROR_CODE_INVALID_TASK")
        self.assertEqual(converted.error_message, "payload inválido")
        self.assertFalse(converted.retryable)

    def test_result_rejects_unknown_status(self):
        result = TaskResult(
            task_id="task-3",
            agent_id="agent-1",
            status="NOT_A_STATUS",
        )

        with self.assertRaisesRegex(ValueError, "invalid task result status"):
            result.to_proto()

    def test_from_proto_accepts_existing_contract_message(self):
        raw = contract_pb2.Task(task_id="legacy", goal="compatibilidade")

        task = Task.from_proto(raw)

        self.assertEqual(task.task_id, "legacy")
        self.assertEqual(task.payload, {})


class AgentModelAdapterTests(unittest.TestCase):
    def make_raw_task(self):
        return Task(
            task_id="task-friendly",
            goal="test",
            payload={"value": 42},
            trace={"trace_id": "trace-friendly"},
        ).to_proto()

    def test_new_agent_api_receives_and_returns_public_models(self):
        result = build_agent(FriendlyAgent)._execute_contract_task(
            self.make_raw_task()
        )

        self.assertEqual(result.status, contract_pb2.TASK_STATUS_COMPLETED)
        self.assertEqual(result.output["received"], 42)

    def test_value_error_maps_to_invalid_task(self):
        result = build_agent(InvalidAgent)._execute_contract_task(
            self.make_raw_task()
        )

        self.assertEqual(result.error.code, contract_pb2.ERROR_CODE_INVALID_TASK)
        self.assertFalse(result.error.retryable)

    def test_timeout_maps_to_retryable_timeout(self):
        result = build_agent(TimeoutAgent)._execute_contract_task(
            self.make_raw_task()
        )

        self.assertEqual(result.error.code, contract_pb2.ERROR_CODE_TIMEOUT)
        self.assertTrue(result.error.retryable)


if __name__ == "__main__":
    unittest.main()


class TaskResultAttemptsTests(unittest.TestCase):
    def test_from_proto_exposes_attempts_and_declared_kind(self):
        from contract.v1 import contract_pb2
        from google.protobuf import timestamp_pb2

        started = timestamp_pb2.Timestamp(seconds=1_700_000_000)
        completed = timestamp_pb2.Timestamp(seconds=1_700_000_002)
        message = contract_pb2.TaskResult(
            task_id="t1", agent_id="healthy", status=contract_pb2.TASK_STATUS_COMPLETED,
            agent_kind=contract_pb2.AGENT_KIND_BDI,
            attempts=[
                contract_pb2.TaskAttempt(
                    attempt=1, agent_id="slow", agent_kind=contract_pb2.AGENT_KIND_DETERMINISTIC,
                    started_at=started, completed_at=completed,
                    outcome=contract_pb2.ATTEMPT_OUTCOME_TIMEOUT,
                    error=contract_pb2.ErrorInfo(code=contract_pb2.ERROR_CODE_TIMEOUT, message="late", retryable=True),
                ),
                contract_pb2.TaskAttempt(
                    attempt=2, agent_id="healthy", agent_kind=contract_pb2.AGENT_KIND_BDI,
                    outcome=contract_pb2.ATTEMPT_OUTCOME_COMPLETED,
                ),
            ],
        )

        result = TaskResult.from_proto(message)

        self.assertEqual(result.agent_kind, "bdi")
        self.assertEqual([a["attempt"] for a in result.attempts], [1, 2])
        first = result.attempts[0]
        self.assertEqual(first["agent_id"], "slow")
        self.assertEqual(first["agent_kind"], "deterministic")
        self.assertEqual(first["outcome"], "timeout")
        self.assertEqual(first["error"]["code"], "ERROR_CODE_TIMEOUT")
        self.assertTrue(first["started_at"].startswith("2023-11-14"))
        self.assertIsNone(result.attempts[1]["error"])
        self.assertEqual(result.attempts[1]["outcome"], "completed")

    def test_agent_kind_defaults_to_unknown(self):
        from contract.v1 import contract_pb2

        result = TaskResult.from_proto(contract_pb2.TaskResult(task_id="t", status=contract_pb2.TASK_STATUS_COMPLETED))
        self.assertEqual(result.agent_kind, "unknown")
        self.assertEqual(result.attempts, [])
