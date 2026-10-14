"""Modelos Python públicos e conversões do contrato protobuf."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from google.protobuf import json_format, struct_pb2, timestamp_pb2

from contract.v1 import contract_pb2


def mapping_to_struct(value: Mapping[str, Any] | None) -> struct_pb2.Struct:
    """Converte um mapping Python em ``google.protobuf.Struct``."""
    message = struct_pb2.Struct()
    message.update(dict(value or {}))
    return message


def struct_to_dict(value: struct_pb2.Struct) -> dict[str, Any]:
    """Converte ``Struct`` em um dict independente e mutável."""
    return json_format.MessageToDict(value)


def _timestamp(value: datetime | None = None) -> timestamp_pb2.Timestamp:
    message = timestamp_pb2.Timestamp()
    if value is None:
        message.GetCurrentTime()
    else:
        message.FromDatetime(value)
    return message


def _trace_to_dict(trace: contract_pb2.TraceContext) -> dict[str, str]:
    return {key: value for key, value in {
        "trace_id": trace.trace_id,
        "span_id": trace.span_id,
        "parent_span_id": trace.parent_span_id,
        "correlation_id": trace.correlation_id,
    }.items() if value}


def _non_empty_fields(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value not in ("", 0)}


def _trace_from_mapping(value: Mapping[str, str]) -> contract_pb2.TraceContext:
    return contract_pb2.TraceContext(
        trace_id=value.get("trace_id", ""),
        span_id=value.get("span_id", ""),
        parent_span_id=value.get("parent_span_id", ""),
        correlation_id=value.get("correlation_id", ""),
    )


def _selection_policy_value(value: str) -> int:
    name = value.upper()
    if not name.startswith("SELECTION_POLICY_"):
        name = f"SELECTION_POLICY_{name}"
    return contract_pb2.SelectionPolicy.Value(name)


@dataclass(frozen=True)
class Task:
    """Task amigável para código de domínio, sem tipos protobuf."""

    task_id: str
    goal: str
    type: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()
    trace: Mapping[str, str] = field(default_factory=dict)
    priority: int = 0
    deadline_ms: int = 0
    parent_task_id: str = ""
    attempt: int = 0
    selection_policy: str = "SELECTION_POLICY_FIRST_AVAILABLE"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    bdi: Mapping[str, Any] = field(default_factory=dict)
    llm: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        name = self.selection_policy.upper()
        if not name.startswith("SELECTION_POLICY_"):
            name = f"SELECTION_POLICY_{name}"
        contract_pb2.SelectionPolicy.Value(name)
        object.__setattr__(self, "selection_policy", name)

    @classmethod
    def from_proto(cls, message: contract_pb2.Task) -> "Task":
        return cls(
            task_id=message.task_id,
            type=message.type,
            goal=message.goal,
            payload=(
                struct_to_dict(message.payload)
                if message.HasField("payload")
                else {}
            ),
            required_capabilities=tuple(message.required_capabilities),
            trace=_trace_to_dict(message.trace),
            priority=message.priority,
            deadline_ms=message.deadline_ms,
            parent_task_id=message.parent_task_id,
            attempt=message.attempt,
            selection_policy=contract_pb2.SelectionPolicy.Name(
                message.selection_policy
            ),
            metadata=(
                struct_to_dict(message.metadata)
                if message.HasField("metadata")
                else {}
            ),
            bdi=_non_empty_fields(
                goal=message.bdi.goal,
                beliefs=message.bdi.beliefs,
                selected_plan=message.bdi.selected_plan,
                intention_id=message.bdi.intention_id,
                reasoning_summary=message.bdi.reasoning_summary,
            )
            if message.HasField("bdi")
            else {},
            llm=_non_empty_fields(
                provider=message.llm.provider,
                model=message.llm.model,
                prompt=message.llm.prompt,
                system_instruction=message.llm.system_instruction,
                temperature=message.llm.temperature,
                max_tokens=message.llm.max_tokens,
                confidence=message.llm.confidence,
                explanation=message.llm.explanation,
                reasoning_summary=message.llm.reasoning_summary,
            )
            if message.HasField("llm")
            else {},
        )

    def to_proto(self) -> contract_pb2.Task:
        message = contract_pb2.Task(
            task_id=self.task_id,
            type=self.type,
            goal=self.goal,
            payload=mapping_to_struct(self.payload),
            required_capabilities=list(self.required_capabilities),
            trace=_trace_from_mapping(self.trace),
            priority=self.priority,
            deadline_ms=self.deadline_ms,
            parent_task_id=self.parent_task_id,
            attempt=self.attempt,
            selection_policy=_selection_policy_value(self.selection_policy),
            metadata=mapping_to_struct(self.metadata),
        )
        if self.bdi:
            message.bdi.CopyFrom(contract_pb2.BdiExtension(**dict(self.bdi)))
        if self.llm:
            message.llm.CopyFrom(contract_pb2.LlmExtension(**dict(self.llm)))
        return message


@dataclass(frozen=True)
class TaskResult:
    """Resultado público do SDK, independente de protobuf."""

    task_id: str
    agent_id: str
    status: str
    output: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    trace: Mapping[str, str] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    completed_at: datetime | None = None

    @classmethod
    def from_proto(cls, message: contract_pb2.TaskResult) -> "TaskResult":
        error = message.error if message.HasField("error") else None
        return cls(
            task_id=message.task_id,
            agent_id=message.agent_id,
            status=contract_pb2.TaskStatus.Name(message.status),
            output=(
                struct_to_dict(message.output)
                if message.HasField("output")
                else {}
            ),
            metadata=(
                struct_to_dict(message.metadata)
                if message.HasField("metadata")
                else {}
            ),
            trace=_trace_to_dict(message.trace),
            error_code=(contract_pb2.ErrorCode.Name(error.code) if error else None),
            error_message=(error.message if error else None),
            retryable=(error.retryable if error else False),
            completed_at=(
                message.completed_at.ToDatetime(tzinfo=timezone.utc)
                if message.HasField("completed_at")
                else None
            ),
        )

    def to_proto(self) -> contract_pb2.TaskResult:
        try:
            status = contract_pb2.TaskStatus.Value(self.status)
        except ValueError as error:
            raise ValueError(f"invalid task result status: {self.status}") from error

        message = contract_pb2.TaskResult(
            task_id=self.task_id,
            agent_id=self.agent_id,
            status=status,
            completed_at=_timestamp(self.completed_at),
            trace=_trace_from_mapping(self.trace),
            output=mapping_to_struct(self.output),
            metadata=mapping_to_struct(self.metadata),
        )
        if self.error_code or self.error_message:
            try:
                code = contract_pb2.ErrorCode.Value(
                    self.error_code or "ERROR_CODE_UNKNOWN"
                )
            except ValueError as error:
                raise ValueError(f"invalid error code: {self.error_code}") from error
            message.error.CopyFrom(
                contract_pb2.ErrorInfo(
                    code=code,
                    message=self.error_message or "",
                    retryable=self.retryable,
                )
            )
        return message
