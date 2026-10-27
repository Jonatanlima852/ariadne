"""API pública para executar, correlacionar e verificar cenários."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import grpc

from contract.v1 import contract_pb2, contract_pb2_grpc
from ariadne_sdk.mission import (
    DEFAULT_PLANNER_CAPABILITY,
    MissionResult,
    build_mission_request,
)
from ariadne_sdk.models import TaskResult, mapping_to_struct, struct_to_dict


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _selection_policy_value(value):
    name = str(value or "FIRST_AVAILABLE").upper()
    if not name.startswith("SELECTION_POLICY_"):
        name = f"SELECTION_POLICY_{name}"
    try:
        return contract_pb2.SelectionPolicy.Value(name)
    except ValueError as error:
        raise ValueError(f"unknown selection policy: {value}") from error


class ScenarioResult:
    def __init__(self, result):
        self.raw = result
        self.value = TaskResult.from_proto(result)
        self.task_id = self.value.task_id
        self.agent_id = self.value.agent_id
        self.status = self.value.status
        self.output = dict(self.value.output)
        self.metadata = dict(self.value.metadata)
        self.error = self.value.error_message

    @property
    def agent_kind(self):
        if self.metadata.get("agent_kind"):
            return str(self.metadata["agent_kind"]).lower()
        if self.metadata.get("provider"):
            return "llm"
        if self.metadata.get("selected_plan"):
            return "bdi"
        return "generic"

    def assert_completed(self):
        if self.raw.status != contract_pb2.TASK_STATUS_COMPLETED:
            raise AssertionError(
                f"task {self.task_id} did not complete: {self.error or self.status}"
            )
        return self

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "agent_kind": self.agent_kind,
            "status": self.status,
            "output": self.output,
            "metadata": self.metadata,
            "error": self.error,
        }


@dataclass
class ScenarioReport:
    name: str
    trace_id: str
    results: Mapping[str, ScenarioResult]
    events: list[dict[str, Any]]

    @property
    def final_result(self):
        return next(reversed(self.results.values()), None)

    @property
    def output(self):
        return self.final_result.output if self.final_result else {}

    def assert_completed(self):
        if not self.results:
            raise AssertionError("scenario did not execute any step")
        for step, result in self.results.items():
            try:
                result.assert_completed()
            except AssertionError as error:
                raise AssertionError(f"step {step}: {error}") from error
        return self

    def assert_agent_used(self, agent_id):
        if not any(result.agent_id == agent_id for result in self.results.values()):
            raise AssertionError(f"agent was not used: {agent_id}")
        return self

    def assert_agent_kind_used(self, kind):
        normalized = kind.lower()
        if not any(result.agent_kind == normalized for result in self.results.values()):
            raise AssertionError(f"agent kind was not used: {kind}")
        return self

    def to_dict(self):
        statuses = [result.status for result in self.results.values()]
        status = (
            "COMPLETED"
            if statuses and all(value == "TASK_STATUS_COMPLETED" for value in statuses)
            else "FAILED"
        )
        return {
            "scenario": self.name,
            "trace_id": self.trace_id,
            "status": status,
            "results": {
                step: result.to_dict() for step, result in self.results.items()
            },
            "events": list(self.events),
        }

    def save(self, path):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination


class ScenarioWorkflowResult:
    def __init__(self, result):
        self.raw = result
        self.workflow_id = result.workflow_id
        self.run_id = result.run_id
        self.root_task_id = result.root_task_id
        self.status = contract_pb2.WorkflowStatus.Name(result.status)
        self.trace_id = result.trace.trace_id
        self.output = (
            struct_to_dict(result.output) if result.HasField("output") else {}
        )
        self.error = result.error.message if result.HasField("error") else None
        self.duration_ms = self._duration_ms(
            result.created_at if result.HasField("created_at") else None,
            result.completed_at if result.HasField("completed_at") else None,
        )
        self.steps = {}
        for step in result.step_results:
            task_result = (
                ScenarioResult(step.result) if step.HasField("result") else None
            )
            self.steps[step.step_id] = {
                "status": contract_pb2.WorkflowStepStatus.Name(step.status),
                "result": task_result,
                "duration_ms": self._duration_ms(
                    step.result.started_at
                    if step.HasField("result")
                    and step.result.HasField("started_at") else None,
                    step.result.completed_at
                    if step.HasField("result")
                    and step.result.HasField("completed_at") else None,
                ),
            }

    @staticmethod
    def _duration_ms(start, end):
        if start is None or end is None:
            return None
        return (end.ToDatetime() - start.ToDatetime()).total_seconds() * 1000

    def assert_completed(self):
        if self.raw.status != contract_pb2.WORKFLOW_STATUS_COMPLETED:
            raise AssertionError(
                f"workflow {self.workflow_id} did not complete: "
                f"{self.error or self.status}"
            )
        return self

    def assert_agent_kind_used(self, kind):
        normalized = kind.lower()
        if not any(
            value["result"] and value["result"].agent_kind == normalized
            for value in self.steps.values()
        ):
            raise AssertionError(f"agent kind was not used: {kind}")
        return self

    def to_dict(self):
        return {
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "root_task_id": self.root_task_id,
            "trace_id": self.trace_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "steps": {
                step_id: {
                    "status": value["status"],
                    "result": (
                        value["result"].to_dict() if value["result"] else None
                    ),
                    "duration_ms": value["duration_ms"],
                }
                for step_id, value in self.steps.items()
            },
        }

    def save(self, path):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination


class RuntimeClient:
    """Cliente de cenário com trace compartilhado e valores Python.

    ``submit`` envia uma task ou uma entrada que o orchestrator expande em
    workflow. ``run`` e ``ask`` enviam uma única entrada.
    """

    def __init__(
        self,
        name="experiment",
        orchestrator_addr="localhost:50052",
        *,
        entry_capability=None,
        orchestrator_stub=None,
    ):
        self.name = name
        self.entry_capability = entry_capability
        self.trace_id = str(uuid.uuid4())
        self._channel = None
        if orchestrator_stub is None:
            self._channel = grpc.insecure_channel(orchestrator_addr)
            orchestrator_stub = contract_pb2_grpc.OrchestratorServiceStub(
                self._channel
            )
        self._stub = orchestrator_stub
        self.results = {}
        self.workflows = {}
        self.missions = {}
        self._mission_requests = {}
        self.events = []

    def _event(self, event_type, step, **details):
        self.events.append({
            "type": event_type,
            "scenario": self.name,
            "step": step,
            "trace_id": self.trace_id,
            "timestamp": _utc_now(),
            **details,
        })

    def submit(
        self,
        step,
        *,
        goal,
        capabilities,
        task_type="SCENARIO_STEP",
        payload=None,
        bdi_goal=None,
        intention_id=None,
        deadline_ms=0,
        max_attempts=1,
        backoff_ms=0,
        exclude_failed_agent=False,
        selection_policy="FIRST_AVAILABLE",
    ):
        task = contract_pb2.Task(
            task_id=str(uuid.uuid4()),
            type=task_type,
            goal=goal,
            payload=mapping_to_struct(payload),
            required_capabilities=list(capabilities),
            selection_policy=_selection_policy_value(selection_policy),
            deadline_ms=deadline_ms,
            retry_policy=contract_pb2.RetryPolicy(
                max_attempts=max_attempts,
                backoff_ms=backoff_ms,
                exclude_failed_agent=exclude_failed_agent,
            ),
            trace=contract_pb2.TraceContext(
                trace_id=self.trace_id,
                correlation_id=self.name,
            ),
        )
        if bdi_goal or intention_id:
            task.bdi.CopyFrom(contract_pb2.BdiExtension(
                goal=bdi_goal or "",
                intention_id=intention_id or str(uuid.uuid4()),
            ))

        self._event("STEP_SUBMITTED", step, task_id=task.task_id)
        response = self._stub.SubmitTask(contract_pb2.SubmitTaskRequest(task=task))
        if response.HasField("error") and response.error.message:
            self._event(
                "STEP_REJECTED", step, task_id=task.task_id,
                error=response.error.message,
            )
            raise RuntimeError(f"{step}: {response.error.message}")

        if response.HasField("workflow_result"):
            result = ScenarioWorkflowResult(response.workflow_result)
            self.workflows[step] = result
            self._event(
                "WORKFLOW_FINISHED", step, task_id=task.task_id,
                run_id=result.run_id, status=result.status,
            )
            return result

        result = ScenarioResult(response.result)
        self.results[step] = result
        self._event(
            "STEP_FINISHED", step, task_id=result.task_id,
            agent_id=result.agent_id, status=result.status,
        )
        return result

    def run(self, goal, *, payload=None, task_type="NATURAL_LANGUAGE"):
        if not self.entry_capability:
            raise ValueError("RuntimeClient.run requires entry_capability")
        result = self.submit(
            "entry", goal=goal, capabilities=[self.entry_capability],
            task_type=task_type, payload=payload,
        )
        if isinstance(result, ScenarioWorkflowResult):
            return result
        return self.report()

    ask = run

    def submit_workflow(
        self,
        goal,
        *,
        steps,
        final_step_id,
        workflow_id=None,
        task_type="WORKFLOW",
        payload=None,
        rpc_timeout=None,
    ):
        request = self._workflow_request(
            goal, steps=steps, final_step_id=final_step_id,
            workflow_id=workflow_id, task_type=task_type, payload=payload,
        )
        root_task_id = request.root_task.task_id
        self._event("WORKFLOW_SUBMITTED", "workflow", task_id=root_task_id)
        options = {} if rpc_timeout is None else {"timeout": rpc_timeout}
        response = self._stub.SubmitWorkflow(request, **options)
        if response.HasField("error") and response.error.message:
            self._event(
                "WORKFLOW_REJECTED", "workflow", task_id=root_task_id,
                error=response.error.message,
            )
            raise RuntimeError(f"workflow: {response.error.message}")
        result = ScenarioWorkflowResult(response.result)
        self._event(
            "WORKFLOW_FINISHED", "workflow", task_id=root_task_id,
            run_id=result.run_id, status=result.status,
        )
        return result

    def start_workflow(
        self, goal, *, steps, final_step_id, workflow_id=None,
        task_type="WORKFLOW", payload=None,
    ):
        request = self._workflow_request(
            goal, steps=steps, final_step_id=final_step_id,
            workflow_id=workflow_id, task_type=task_type, payload=payload,
        )
        response = self._stub.StartWorkflow(contract_pb2.StartWorkflowRequest(
            root_task=request.root_task, workflow=request.workflow,
        ))
        if response.HasField("error") and response.error.message:
            raise RuntimeError(f"workflow: {response.error.message}")
        self._event(
            "WORKFLOW_STARTED", "workflow",
            task_id=request.root_task.task_id, run_id=response.run_id,
        )
        return response.run_id

    def get_workflow(self, run_id):
        response = self._stub.GetWorkflow(
            contract_pb2.GetWorkflowRequest(run_id=run_id)
        )
        if response.HasField("error") and response.error.message:
            raise RuntimeError(f"workflow: {response.error.message}")
        return ScenarioWorkflowResult(response.result)

    def cancel_workflow(self, run_id):
        response = self._stub.CancelWorkflow(
            contract_pb2.CancelWorkflowRequest(run_id=run_id)
        )
        if response.HasField("error") and response.error.message:
            raise RuntimeError(f"workflow: {response.error.message}")
        return ScenarioWorkflowResult(response.result)

    def _workflow_request(
        self, goal, *, steps, final_step_id, workflow_id=None,
        task_type="WORKFLOW", payload=None,
    ):
        root_task_id = str(uuid.uuid4())
        root = contract_pb2.Task(
            task_id=root_task_id,
            type=task_type,
            goal=goal,
            payload=mapping_to_struct(payload),
            trace=contract_pb2.TraceContext(
                trace_id=self.trace_id,
                correlation_id=self.name,
            ),
        )
        workflow_steps = []
        for declared in steps:
            bindings = [
                contract_pb2.ResultBinding(
                    source_step_id=binding["source_step_id"],
                    source_path=binding["source_path"],
                    target_field=binding["target_field"],
                )
                for binding in declared.get("input_bindings", [])
            ]
            workflow_steps.append(contract_pb2.WorkflowStep(
                step_id=declared["step_id"],
                task_template=contract_pb2.Task(
                    type=declared.get("type", "WORKFLOW_STEP"),
                    goal=declared["goal"],
                    payload=mapping_to_struct(declared.get("payload")),
                    required_capabilities=list(
                        declared.get(
                            "required_capabilities",
                            declared.get("capabilities", []),
                        )
                    ),
                    deadline_ms=declared.get("deadline_ms", 0),
                    selection_policy=_selection_policy_value(
                        declared.get("selection_policy", "FIRST_AVAILABLE")
                    ),
                    retry_policy=contract_pb2.RetryPolicy(
                        max_attempts=declared.get("max_attempts", 1),
                        backoff_ms=declared.get("backoff_ms", 0),
                        exclude_failed_agent=declared.get(
                            "exclude_failed_agent", False
                        ),
                    ),
                ),
                depends_on=list(declared.get("depends_on", [])),
                input_bindings=bindings,
            ))

        return contract_pb2.SubmitWorkflowRequest(
            root_task=root,
            workflow=contract_pb2.WorkflowDefinition(
                workflow_id=workflow_id or str(uuid.uuid4()),
                steps=workflow_steps,
                final_step_id=final_step_id,
            ),
        )

    def run_mission(
        self,
        goal,
        *,
        context=None,
        limits=None,
        planner_capability=DEFAULT_PLANNER_CAPABILITY,
        retry_policy=None,
        selection_policy=None,
        metadata=None,
        mission_id=None,
        rpc_timeout=None,
    ):
        """Executa uma missão até o fim e devolve ``MissionResult``.

        O orquestrador pede o plano a um agente com ``planner_capability``,
        executa cada rodada e repete até ``DONE``, ``ABORT`` ou um limite.
        """
        request = self._mission_request(
            goal, context=context, limits=limits, planner_capability=planner_capability,
            retry_policy=retry_policy, selection_policy=selection_policy,
            metadata=metadata, mission_id=mission_id,
        )
        self._event("MISSION_SUBMITTED", "mission", mission_id=request.mission_id)
        options = {} if rpc_timeout is None else {"timeout": rpc_timeout}
        response = self._stub.RunMission(
            contract_pb2.RunMissionRequest(mission=request), **options
        )
        if response.HasField("error") and response.error.message:
            self._event(
                "MISSION_REJECTED", "mission", mission_id=request.mission_id,
                error=response.error.message,
            )
            raise RuntimeError(f"mission: {response.error.message}")
        result = MissionResult(response.result, request)
        self.missions[result.mission_id] = result
        self._event(
            "MISSION_FINISHED", "mission", mission_id=result.mission_id,
            status=result.status, rounds=len(result.rounds),
        )
        return result

    def start_mission(
        self,
        goal,
        *,
        context=None,
        limits=None,
        planner_capability=DEFAULT_PLANNER_CAPABILITY,
        retry_policy=None,
        selection_policy=None,
        metadata=None,
        mission_id=None,
    ):
        """Inicia a missão sem esperar; consulte com ``get_mission``."""
        request = self._mission_request(
            goal, context=context, limits=limits, planner_capability=planner_capability,
            retry_policy=retry_policy, selection_policy=selection_policy,
            metadata=metadata, mission_id=mission_id,
        )
        response = self._stub.StartMission(
            contract_pb2.StartMissionRequest(mission=request)
        )
        if response.HasField("error") and response.error.message:
            raise RuntimeError(f"mission: {response.error.message}")
        self._mission_requests[response.mission_id] = request
        self._event("MISSION_STARTED", "mission", mission_id=response.mission_id)
        return response.mission_id

    def get_mission(self, mission_id):
        response = self._stub.GetMission(
            contract_pb2.GetMissionRequest(mission_id=mission_id)
        )
        if response.HasField("error") and response.error.message:
            raise RuntimeError(f"mission: {response.error.message}")
        return MissionResult(response.result, self._mission_requests.get(mission_id))

    def cancel_mission(self, mission_id):
        response = self._stub.CancelMission(
            contract_pb2.CancelMissionRequest(mission_id=mission_id)
        )
        if response.HasField("error") and response.error.message:
            raise RuntimeError(f"mission: {response.error.message}")
        self._event("MISSION_CANCELLED", "mission", mission_id=mission_id)
        return MissionResult(response.result, self._mission_requests.get(mission_id))

    def _mission_request(self, goal, *, mission_id=None, **options):
        return build_mission_request(
            goal,
            mission_id=mission_id or str(uuid.uuid4()),
            trace=contract_pb2.TraceContext(
                trace_id=self.trace_id,
                correlation_id=self.name,
            ),
            **options,
        )

    def report(self):
        return ScenarioReport(
            name=self.name,
            trace_id=self.trace_id,
            results=dict(self.results),
            events=list(self.events),
        )

    def close(self):
        if self._channel is not None:
            self._channel.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
