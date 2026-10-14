import json
import tempfile
import unittest
from pathlib import Path

from contract.v1 import contract_pb2
from ariadne_sdk import RuntimeClient, TaskResult


def response(*, task_id, agent_id, metadata=None, output=None):
    result = TaskResult(
        task_id=task_id,
        agent_id=agent_id,
        status="TASK_STATUS_COMPLETED",
        metadata=metadata or {},
        output=output or {},
        trace={"trace_id": "replaced-by-request"},
    ).to_proto()
    return contract_pb2.SubmitTaskResponse(result=result)


class FakeOrchestrator:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def SubmitTask(self, request):
        self.requests.append(request)
        reply = self.replies.pop(0)
        reply.result.task_id = request.task.task_id
        reply.result.trace.CopyFrom(request.task.trace)
        return reply


class FakeWorkflowOrchestrator:
    def __init__(self):
        self.request = None

    def SubmitWorkflow(self, request):
        self.request = request
        step_result = TaskResult(
            task_id="task-final",
            agent_id="agent-final",
            status="TASK_STATUS_COMPLETED",
            output={"answer": "done"},
            trace={"trace_id": request.root_task.trace.trace_id},
        ).to_proto()
        return contract_pb2.SubmitWorkflowResponse(
            result=contract_pb2.WorkflowResult(
                workflow_id=request.workflow.workflow_id,
                run_id="run-1",
                root_task_id=request.root_task.task_id,
                status=contract_pb2.WORKFLOW_STATUS_COMPLETED,
                step_results=[contract_pb2.WorkflowStepResult(
                    step_id="finish",
                    status=contract_pb2.WORKFLOW_STEP_STATUS_COMPLETED,
                    result=step_result,
                )],
                output=step_result.output,
                trace=request.root_task.trace,
            )
        )

    def StartWorkflow(self, request):
        self.request = request
        return contract_pb2.StartWorkflowResponse(run_id="run-async")

    def GetWorkflow(self, request):
        return contract_pb2.GetWorkflowResponse(result=contract_pb2.WorkflowResult(
            workflow_id="async", run_id=request.run_id,
            status=contract_pb2.WORKFLOW_STATUS_RUNNING,
        ))

    def CancelWorkflow(self, request):
        return contract_pb2.CancelWorkflowResponse(result=contract_pb2.WorkflowResult(
            workflow_id="async", run_id=request.run_id,
            status=contract_pb2.WORKFLOW_STATUS_CANCELLED,
        ))


class FakeAutomaticWorkflowOrchestrator:
    def SubmitTask(self, request):
        task_result = TaskResult(
            task_id="route-task", agent_id="bdi-1",
            status="TASK_STATUS_COMPLETED",
            metadata={"selected_plan": "via_intermediate"},
            output={"route": ["A", "B", "D"], "distance": 25},
        ).to_proto()
        return contract_pb2.SubmitTaskResponse(
            workflow_result=contract_pb2.WorkflowResult(
                workflow_id="automatic", run_id="run-auto",
                root_task_id=request.task.task_id,
                status=contract_pb2.WORKFLOW_STATUS_COMPLETED,
                step_results=[contract_pb2.WorkflowStepResult(
                    step_id="route",
                    status=contract_pb2.WORKFLOW_STEP_STATUS_COMPLETED,
                    result=task_result,
                )],
                output=task_result.output,
                trace=request.task.trace,
            )
        )


class ScenarioTests(unittest.TestCase):

    def test_ask_returns_automatically_planned_workflow(self):
        scenario = RuntimeClient(
            "automatic", entry_capability="task-decomposition",
            orchestrator_stub=FakeAutomaticWorkflowOrchestrator(),
        )

        result = scenario.ask("Planeje uma rota de A para D")

        result.assert_completed().assert_agent_kind_used("bdi")
        self.assertEqual(result.output["distance"], 25)
        self.assertEqual(result.run_id, "run-auto")

    def test_run_submits_declared_entry_and_returns_report(self):
        stub = FakeOrchestrator([
            response(
                task_id="ignored",
                agent_id="llm-1",
                metadata={"provider": "openai"},
                output={"answer": "ok"},
            )
        ])
        scenario = RuntimeClient(
            "single-entry",
            entry_capability="task-decomposition",
            orchestrator_stub=stub,
        )

        report = scenario.run("Planeje uma rota")

        report.assert_completed().assert_agent_used("llm-1")
        report.assert_agent_kind_used("llm")
        self.assertEqual(report.output, {"answer": "ok"})
        self.assertEqual(
            list(stub.requests[0].task.required_capabilities),
            ["task-decomposition"],
        )
        self.assertEqual(stub.requests[0].task.trace.trace_id, scenario.trace_id)

    def test_report_asserts_multiple_agent_kinds_and_saves_json(self):
        stub = FakeOrchestrator([
            response(
                task_id="one", agent_id="llm-1",
                metadata={"provider": "openai"},
            ),
            response(
                task_id="two", agent_id="bdi-1",
                metadata={"selected_plan": "via_b"},
            ),
        ])
        scenario = RuntimeClient("heterogeneous", orchestrator_stub=stub)
        scenario.submit("decompose", goal="goal", capabilities=["decompose"])
        scenario.submit("route", goal="route", capabilities=["route"])

        report = scenario.report()
        report.assert_completed()
        report.assert_agent_kind_used("llm").assert_agent_kind_used("bdi")
        self.assertEqual(len(report.events), 4)
        self.assertTrue(all(
            event["trace_id"] == scenario.trace_id for event in report.events
        ))

        with tempfile.TemporaryDirectory() as directory:
            path = report.save(Path(directory) / "report.json")
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(saved["status"], "COMPLETED")
        self.assertEqual(saved["trace_id"], scenario.trace_id)
        self.assertEqual(set(saved["results"]), {"decompose", "route"})

    def test_submit_forwards_timeout_and_retry_policy(self):
        stub = FakeOrchestrator([
            response(task_id="one", agent_id="healthy")
        ])
        scenario = RuntimeClient("retry", orchestrator_stub=stub)

        scenario.submit(
            "recover",
            goal="test",
            capabilities=["echo"],
            deadline_ms=50,
            max_attempts=3,
            backoff_ms=10,
            exclude_failed_agent=True,
            selection_policy="least_loaded",
        )

        task = stub.requests[0].task
        self.assertEqual(task.deadline_ms, 50)
        self.assertEqual(task.retry_policy.max_attempts, 3)
        self.assertEqual(task.retry_policy.backoff_ms, 10)
        self.assertTrue(task.retry_policy.exclude_failed_agent)
        self.assertEqual(
            task.selection_policy,
            contract_pb2.SELECTION_POLICY_LEAST_LOADED,
        )

    def test_run_requires_entry_capability(self):
        scenario = RuntimeClient("invalid", orchestrator_stub=FakeOrchestrator([]))

        with self.assertRaisesRegex(ValueError, "entry_capability"):
            scenario.run("goal")

    def test_submit_workflow_uses_python_values_and_returns_aggregate(self):
        stub = FakeWorkflowOrchestrator()
        scenario = RuntimeClient("workflow", orchestrator_stub=stub)

        result = scenario.submit_workflow(
            "Execute duas etapas",
            workflow_id="workflow-1",
            final_step_id="finish",
            steps=[
                {
                    "step_id": "start",
                    "goal": "start",
                    "capabilities": ["echo"],
                },
                {
                    "step_id": "finish",
                    "goal": "finish",
                    "required_capabilities": ["echo"],
                    "depends_on": ["start"],
                },
            ],
        )

        result.assert_completed()
        self.assertEqual(result.output, {"answer": "done"})
        self.assertEqual(result.steps["finish"]["result"].agent_id, "agent-final")
        self.assertEqual(stub.request.workflow.steps[1].depends_on, ["start"])
        self.assertEqual(stub.request.root_task.trace.trace_id, scenario.trace_id)

    def test_async_workflow_start_get_and_cancel(self):
        stub = FakeWorkflowOrchestrator()
        scenario = RuntimeClient("async", orchestrator_stub=stub)
        declaration = [{
            "step_id": "only", "goal": "work", "capabilities": ["echo"],
        }]

        run_id = scenario.start_workflow(
            "work", steps=declaration, final_step_id="only",
        )
        running = scenario.get_workflow(run_id)
        cancelled = scenario.cancel_workflow(run_id)

        self.assertEqual(run_id, "run-async")
        self.assertEqual(running.status, "WORKFLOW_STATUS_RUNNING")
        self.assertEqual(cancelled.status, "WORKFLOW_STATUS_CANCELLED")


if __name__ == "__main__":
    unittest.main()
