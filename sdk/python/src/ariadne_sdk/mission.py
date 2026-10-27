"""Missões: declaração, resultado e protocolo do planejador (contrato 2.0.0).

Uma missão é um objetivo que o cliente não sabe decompor. O orquestrador pede
um plano a um agente com a capacidade ``mission-planning``, executa o plano
como workflow, devolve o resultado ao planejador e repete até ``DONE`` ou
``ABORT``. Este módulo não depende de Pydantic nem de OpenAI: ele serve ao
cliente (``RuntimeClient.run_mission``), ao executor declarativo
(``Scenario(mission=...)``) e a qualquer agente que implemente o planejador.

Todo JSON produzido aqui usa os nomes de campo do proto (snake_case), o mesmo
formato que o orquestrador Go emite e aceita (protojson com ``UseProtoNames``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from google.protobuf import json_format

from contract.v1 import contract_pb2
from ariadne_sdk.models import TaskResult, mapping_to_struct, struct_to_dict

DEFAULT_PLANNER_CAPABILITY = "mission-planning"
PLANNER_ACTIONS = ("PLAN", "DONE", "ABORT")

# Chaves aceitas pelo decodificador Go (planning/planner.go, DisallowUnknownFields).
_PLAN_KEYS = {"workflow_id", "final_step_id", "steps"}
_STEP_KEYS = {
    "step_id", "type", "goal", "payload", "required_capabilities",
    "depends_on", "input_bindings", "bdi_goal",
}
_BINDING_KEYS = {"source_step_id", "source_path", "target_field"}


def message_to_dict(message) -> dict[str, Any]:
    """JSON do contrato com nomes do proto, como o Go escreve."""
    return json_format.MessageToDict(message, preserving_proto_field_name=True)


def _dict_from_json_text(value: str, label: str) -> dict[str, Any]:
    text = (value or "").strip()
    if not text:
        return {}
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} must be a JSON object: {error}") from error
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must decode to a JSON object")
    return decoded


# ---------------------------------------------------------------------------
# Declaração (lado do cliente)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionLimits:
    """Limites do laço; zero deixa o orquestrador aplicar o padrão."""

    max_rounds: int = 0
    max_parallel: int = 0
    round_deadline_ms: int = 0
    planner_deadline_ms: int = 0
    mission_deadline_ms: int = 0

    @classmethod
    def coerce(cls, value) -> "MissionLimits":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            unknown = set(value) - set(cls.__dataclass_fields__)
            if unknown:
                raise ValueError("unknown mission limit: " + ", ".join(sorted(unknown)))
            return cls(**{key: int(item) for key, item in value.items()})
        raise TypeError("limits must be MissionLimits or a mapping")

    def to_proto(self) -> contract_pb2.MissionLimits:
        for name in self.__dataclass_fields__:
            number = getattr(self, name)
            if isinstance(number, bool) or not isinstance(number, int) or number < 0:
                raise ValueError(f"mission limit {name} must be a non-negative integer")
        return contract_pb2.MissionLimits(
            max_rounds=self.max_rounds,
            max_parallel=self.max_parallel,
            round_deadline_ms=self.round_deadline_ms,
            planner_deadline_ms=self.planner_deadline_ms,
            mission_deadline_ms=self.mission_deadline_ms,
        )

    def to_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass
class Mission:
    """Uma missão declarada em um arquivo de experimento.

    Diferente de ``Step``, não há DAG: o planejador decide os passos em cada
    rodada. ``./ariadne run`` envia ``RunMission`` e preserva o
    ``MissionResult`` em ``mission-result.json`` nas evidências.
    """

    goal: str
    context: dict[str, Any] = field(default_factory=dict)
    limits: MissionLimits | Mapping[str, int] | None = None
    planner_capability: str = DEFAULT_PLANNER_CAPABILITY
    retry_policy: Mapping[str, Any] | None = None
    selection_policy: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "Mission":
        if not isinstance(self.goal, str) or not self.goal.strip():
            raise ValueError("Mission.goal must be a non-empty string")
        if not isinstance(self.context, dict) or not isinstance(self.metadata, dict):
            raise ValueError("Mission.context and Mission.metadata must be dictionaries")
        json.dumps(self.context, allow_nan=False)
        json.dumps(self.metadata, allow_nan=False)
        if not isinstance(self.planner_capability, str) or not self.planner_capability:
            raise ValueError("Mission.planner_capability must be a non-empty string")
        MissionLimits.coerce(self.limits).to_proto()
        _retry_policy(self.retry_policy)
        if self.selection_policy is not None:
            _selection_policy_value(self.selection_policy)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "context": dict(self.context),
            "limits": MissionLimits.coerce(self.limits).to_dict(),
            "planner_capability": self.planner_capability,
            "retry_policy": dict(self.retry_policy or {}),
            "selection_policy": self.selection_policy,
            "metadata": dict(self.metadata),
        }


def _selection_policy_value(value) -> int:
    name = str(value).upper()
    if not name.startswith("SELECTION_POLICY_"):
        name = f"SELECTION_POLICY_{name}"
    try:
        return contract_pb2.SelectionPolicy.Value(name)
    except ValueError as error:
        raise ValueError(f"unknown selection policy: {value}") from error


def _retry_policy(value) -> contract_pb2.RetryPolicy | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("retry_policy must be a mapping")
    unknown = set(value) - {"max_attempts", "backoff_ms", "exclude_failed_agent"}
    if unknown:
        raise ValueError("unknown retry policy field: " + ", ".join(sorted(unknown)))
    return contract_pb2.RetryPolicy(
        max_attempts=int(value.get("max_attempts", 1)),
        backoff_ms=int(value.get("backoff_ms", 0)),
        exclude_failed_agent=bool(value.get("exclude_failed_agent", False)),
    )


def build_mission_request(
    goal, *, context=None, limits=None, planner_capability=DEFAULT_PLANNER_CAPABILITY,
    retry_policy=None, selection_policy=None, metadata=None, mission_id=None, trace=None,
) -> contract_pb2.MissionRequest:
    """Monta ``MissionRequest`` a partir de valores Python."""
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("mission goal must be a non-empty string")
    request = contract_pb2.MissionRequest(
        mission_id=mission_id or "",
        goal=goal,
        context=mapping_to_struct(context),
        planner_capability=planner_capability or DEFAULT_PLANNER_CAPABILITY,
        limits=MissionLimits.coerce(limits).to_proto(),
        metadata=mapping_to_struct(metadata),
    )
    policy = _retry_policy(retry_policy)
    if policy is not None:
        request.default_retry_policy.CopyFrom(policy)
    if selection_policy is not None:
        request.default_selection_policy = _selection_policy_value(selection_policy)
    if trace is not None:
        request.trace.CopyFrom(trace)
    return request


# ---------------------------------------------------------------------------
# Resultado (lado do cliente)
# ---------------------------------------------------------------------------


def _datetime(message, has: bool):
    return message.ToDatetime(tzinfo=timezone.utc) if has else None


def _duration_ms(start, end):
    if start is None or end is None:
        return None
    return (end - start).total_seconds() * 1000


class MissionStep:
    """Um passo executado numa rodada: ``task`` é a entrada, ``result`` a saída."""

    def __init__(self, message: contract_pb2.WorkflowStepResult):
        self.raw = message
        self.step_id = message.step_id
        self.status = contract_pb2.WorkflowStepStatus.Name(message.status)
        self.task = message_to_dict(message.task) if message.HasField("task") else {}
        self.result = message_to_dict(message.result) if message.HasField("result") else {}
        self.task_result = TaskResult.from_proto(message.result) if message.HasField("result") else None
        self.agent_id = self.task_result.agent_id if self.task_result else ""
        self.output = dict(self.task_result.output) if self.task_result else {}
        self.error = self.task_result.error_message if self.task_result else None

    def to_dict(self) -> dict[str, Any]:
        return message_to_dict(self.raw)


class MissionRound:
    """Uma rodada: chamada ao planejador seguida (em PLAN) de um workflow."""

    def __init__(self, message: contract_pb2.MissionRound):
        self.raw = message
        self.round = message.round
        self.planner_agent_id = message.planner_agent_id
        self.action = contract_pb2.PlannerAction.Name(message.action)
        self.planner_summary = message.planner_summary
        self.plan = message_to_dict(message.plan) if message.HasField("plan") else {}
        self.plan_steps = [
            {
                "step_id": step.step_id,
                "goal": step.task_template.goal,
                "required_capabilities": list(step.task_template.required_capabilities),
                "depends_on": list(step.depends_on),
            }
            for step in message.plan.steps
        ] if message.HasField("plan") else []
        self.result = message.result if message.HasField("result") else None
        self.workflow_status = (
            contract_pb2.WorkflowStatus.Name(message.result.status)
            if message.HasField("result") else None
        )
        self.steps = [MissionStep(step) for step in message.result.step_results] \
            if message.HasField("result") else []
        self.context_after = (
            struct_to_dict(message.context_after) if message.HasField("context_after") else {}
        )
        self.started_at = _datetime(message.started_at, message.HasField("started_at"))
        self.completed_at = _datetime(message.completed_at, message.HasField("completed_at"))
        self.duration_ms = _duration_ms(self.started_at, self.completed_at)
        self.planner_result = (
            TaskResult.from_proto(message.planner_result)
            if message.HasField("planner_result") else None
        )
        self.planner_response = dict(self.planner_result.output) if self.planner_result else {}

    @property
    def step(self) -> dict[str, MissionStep]:
        return {item.step_id: item for item in self.steps}

    def to_dict(self) -> dict[str, Any]:
        return message_to_dict(self.raw)


@dataclass(frozen=True)
class PlannerCall:
    """Entrada e saída de uma chamada ao planejador, como JSON do contrato."""

    round: int
    planner_agent_id: str
    action: str
    request: dict[str, Any]
    response: dict[str, Any]
    result: TaskResult | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round,
            "planner_agent_id": self.planner_agent_id,
            "action": self.action,
            "request": self.request,
            "response": self.response,
        }


class MissionResult:
    """Resultado de ``RunMission``/``GetMission``/``CancelMission``.

    ``to_dict`` devolve o ``MissionResult`` do contrato (nomes do proto) mais
    duas chaves do SDK: ``request`` (o ``MissionRequest`` enviado, quando
    conhecido) e ``planner_calls`` (``PlannerRequest``/``PlannerResponse`` de
    cada rodada). O visualizador em ``tools/mission-viewer`` lê esse arquivo.
    """

    def __init__(self, message: contract_pb2.MissionResult, request: contract_pb2.MissionRequest | None = None):
        self.raw = message
        self.request = request
        self.mission_id = message.mission_id
        self.status = contract_pb2.MissionStatus.Name(message.status)
        self.output = struct_to_dict(message.output) if message.HasField("output") else {}
        self.context = struct_to_dict(message.context) if message.HasField("context") else {}
        self.rounds = [MissionRound(item) for item in message.rounds]
        self.error = message.error.message if message.HasField("error") else None
        self.error_code = (
            contract_pb2.ErrorCode.Name(message.error.code) if message.HasField("error") else None
        )
        self.trace_id = message.trace.trace_id
        self.root_task_id = message.root_task_id
        self.created_at = _datetime(message.created_at, message.HasField("created_at"))
        self.completed_at = _datetime(message.completed_at, message.HasField("completed_at"))
        self.duration_ms = _duration_ms(self.created_at, self.completed_at)

    @property
    def goal(self) -> str:
        return self.request.goal if self.request is not None else ""

    @property
    def final_round(self) -> MissionRound | None:
        return self.rounds[-1] if self.rounds else None

    @property
    def completed(self) -> bool:
        return self.raw.status == contract_pb2.MISSION_STATUS_COMPLETED

    def assert_completed(self) -> "MissionResult":
        if not self.completed:
            raise AssertionError(
                f"mission {self.mission_id} did not complete: {self.error or self.status}"
            )
        return self

    def assert_agent_used(self, agent_id) -> "MissionResult":
        used = {step.agent_id for item in self.rounds for step in item.steps}
        used |= {item.planner_agent_id for item in self.rounds}
        if agent_id not in used:
            raise AssertionError(f"agent was not used: {agent_id}")
        return self

    @property
    def planner_calls(self) -> list[PlannerCall]:
        """Reconstrói o ``PlannerRequest`` de cada rodada e decodifica a resposta.

        O contrato guarda a resposta (``planner_result.output``), mas não a
        requisição; ela é remontada a partir do objetivo, do contexto anterior
        e do histórico. ``available_capabilities`` não é preservado pelo
        ``MissionResult`` e fica vazio.
        """
        calls = []
        context = struct_to_dict(self.request.context) if (
            self.request is not None and self.request.HasField("context")
        ) else {}
        history: list[contract_pb2.RoundSummary] = []
        for item in self.rounds:
            request = contract_pb2.PlannerRequest(
                mission_id=self.mission_id,
                goal=self.goal,
                round=item.round,
                context=mapping_to_struct(context),
                history=list(history),
            )
            if self.request is not None and self.request.HasField("limits"):
                request.limits.CopyFrom(self.request.limits)
            calls.append(PlannerCall(
                round=item.round,
                planner_agent_id=item.planner_agent_id,
                action=item.action,
                request=message_to_dict(request),
                response=dict(item.planner_response),
                result=item.planner_result,
            ))
            summary = contract_pb2.RoundSummary(
                round=item.round, action=item.raw.action, planner_summary=item.planner_summary,
            )
            if item.result is not None:
                summary.status = item.result.status
                summary.step_results.extend(item.result.step_results)
            history.append(summary)
            if item.raw.HasField("context_after"):
                context = item.context_after
        return calls

    def to_dict(self) -> dict[str, Any]:
        document = message_to_dict(self.raw)
        if self.request is not None:
            document["request"] = message_to_dict(self.request)
        document["planner_calls"] = [call.to_dict() for call in self.planner_calls]
        return document

    def save(self, path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination


# ---------------------------------------------------------------------------
# Protocolo do planejador (lado do agente)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannerRequest:
    """``PlannerRequest`` do contrato, decodificado do payload da tarefa."""

    mission_id: str = ""
    goal: str = ""
    round: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    available_capabilities: list[dict[str, Any]] = field(default_factory=list)
    limits: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "PlannerRequest":
        """Valida o payload contra o contrato; campos desconhecidos são rejeitados."""
        if not isinstance(payload, Mapping):
            raise ValueError("planner request payload must be an object")
        try:
            message = json_format.ParseDict(dict(payload), contract_pb2.PlannerRequest())
        except json_format.ParseError as error:
            raise ValueError(f"invalid planner request: {error}") from error
        return cls.from_proto(message)

    @classmethod
    def from_proto(cls, message: contract_pb2.PlannerRequest) -> "PlannerRequest":
        document = message_to_dict(message)
        return cls(
            mission_id=message.mission_id,
            goal=message.goal,
            round=message.round,
            context=document.get("context", {}),
            history=document.get("history", []),
            available_capabilities=document.get("available_capabilities", []),
            limits=document.get("limits", {}),
        )

    @property
    def capability_ids(self) -> list[str]:
        return [item.get("capability_id", "") for item in self.available_capabilities]

    @property
    def last_round(self) -> dict[str, Any] | None:
        return self.history[-1] if self.history else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "goal": self.goal,
            "round": self.round,
            "context": dict(self.context),
            "history": list(self.history),
            "available_capabilities": list(self.available_capabilities),
            "limits": dict(self.limits),
        }


def plan_step(
    step_id, capability, goal, *, payload=None, depends_on=(), input_bindings=(),
    type="MISSION_STEP", bdi_goal="",
) -> dict[str, Any]:
    """Um passo no formato JSON aceito pelo orquestrador."""
    capabilities = [capability] if isinstance(capability, str) else list(capability)
    return {
        "step_id": step_id,
        "type": type,
        "goal": goal,
        "payload": dict(payload or {}),
        "required_capabilities": capabilities,
        "depends_on": list(depends_on),
        "input_bindings": [dict(binding) for binding in input_bindings],
        "bdi_goal": bdi_goal,
    }


def _normalize_action(value) -> str:
    name = str(value or "").upper().removeprefix("PLANNER_ACTION_")
    if name not in PLANNER_ACTIONS:
        raise ValueError(f"planner action must be one of {', '.join(PLANNER_ACTIONS)}: {value!r}")
    return name


def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Confere a forma do plano que o Go decodifica; devolve uma cópia normalizada."""
    if not isinstance(plan, Mapping):
        raise ValueError("plan must be an object")
    unknown = set(plan) - _PLAN_KEYS
    if unknown:
        raise ValueError("plan has unknown fields: " + ", ".join(sorted(unknown)))
    steps = plan.get("steps")
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)) or not steps:
        raise ValueError("plan requires a non-empty list of steps")
    normalized_steps, ids = [], []
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            raise ValueError(f"plan step {index} must be an object")
        unknown = set(step) - _STEP_KEYS
        if unknown:
            raise ValueError(f"plan step {index} has unknown fields: " + ", ".join(sorted(unknown)))
        step_id = step.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            raise ValueError(f"plan step {index} requires step_id")
        if step_id in ids:
            raise ValueError(f"duplicate step_id: {step_id}")
        ids.append(step_id)
        capabilities = step.get("required_capabilities")
        if (not isinstance(capabilities, Sequence) or isinstance(capabilities, str)
                or not capabilities or any(not isinstance(c, str) or not c for c in capabilities)):
            raise ValueError(f"plan step {step_id} requires required_capabilities")
        if not isinstance(step.get("goal", ""), str):
            raise ValueError(f"plan step {step_id} goal must be a string")
        payload = step.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ValueError(f"plan step {step_id} payload must be an object")
        bindings = []
        for binding in step.get("input_bindings", ()):
            if not isinstance(binding, Mapping) or set(binding) != _BINDING_KEYS:
                raise ValueError(f"plan step {step_id} has an invalid input binding")
            bindings.append({key: str(binding[key]) for key in sorted(_BINDING_KEYS)})
        normalized_steps.append({
            "step_id": step_id,
            "type": str(step.get("type") or "MISSION_STEP"),
            "goal": step.get("goal", ""),
            "payload": dict(payload),
            "required_capabilities": list(capabilities),
            "depends_on": [str(item) for item in step.get("depends_on", ())],
            "input_bindings": bindings,
            "bdi_goal": str(step.get("bdi_goal", "") or ""),
        })
    for step in normalized_steps:
        for dependency in step["depends_on"] + [b["source_step_id"] for b in step["input_bindings"]]:
            if dependency not in ids:
                raise ValueError(f"plan step {step['step_id']} depends on unknown step {dependency}")
    final_step_id = plan.get("final_step_id") or ids[-1]
    if final_step_id not in ids:
        raise ValueError(f"final_step_id refers to unknown step {final_step_id}")
    normalized = {
        "workflow_id": str(plan.get("workflow_id") or ""),
        "final_step_id": final_step_id,
        "steps": normalized_steps,
    }
    json.dumps(normalized, allow_nan=False)
    return normalized


@dataclass
class PlannerResponse:
    """Resposta do planejador em valores Python, validada antes de virar saída.

    Regras do contrato: ``PLAN`` exige um plano com ao menos um passo;
    ``DONE`` exige ``output``; ``ABORT`` exige ``reason``.
    """

    action: str
    plan: Mapping[str, Any] | None = None
    output: Mapping[str, Any] = field(default_factory=dict)
    context_update: Mapping[str, Any] = field(default_factory=dict)
    summary: str = ""
    reason: str = ""

    @classmethod
    def make_plan(cls, steps, *, final_step_id=None, workflow_id="", summary="", context_update=None):
        """Atalho para ``PLAN`` a partir de passos (ver ``plan_step``)."""
        plan = {"workflow_id": workflow_id, "final_step_id": final_step_id or "", "steps": list(steps)}
        return cls("PLAN", plan=plan, summary=summary, context_update=dict(context_update or {}))

    @classmethod
    def done(cls, output, *, summary="", context_update=None):
        return cls("DONE", output=dict(output), summary=summary, context_update=dict(context_update or {}))

    @classmethod
    def abort(cls, reason, *, summary=""):
        return cls("ABORT", reason=reason, summary=summary or reason)

    def validate(self) -> "PlannerResponse":
        self.action = _normalize_action(self.action)
        for name in ("output", "context_update"):
            if not isinstance(getattr(self, name), Mapping):
                raise ValueError(f"planner {name} must be an object")
        if not isinstance(self.summary, str) or not isinstance(self.reason, str):
            raise ValueError("planner summary and reason must be strings")
        if self.action == "PLAN":
            if self.plan is None:
                raise ValueError("PLAN requires a plan with at least one step")
            self.plan = validate_plan(self.plan)
        elif self.action == "DONE":
            if not self.output:
                raise ValueError("DONE requires a non-empty output")
        elif not self.reason.strip():
            raise ValueError("ABORT requires a reason")
        json.dumps(dict(self.output), allow_nan=False)
        json.dumps(dict(self.context_update), allow_nan=False)
        return self

    def to_output(self) -> dict[str, Any]:
        """``PlannerResponse`` como JSON para ``TaskResult.output``.

        O orquestrador aceita ``action`` como ``PLAN``/``DONE``/``ABORT``
        (ou o nome completo do enum) e rejeita qualquer outra chave; chaves
        não usadas são omitidas em vez de enviadas como ``null``.
        """
        self.validate()
        document: dict[str, Any] = {"action": self.action}
        if self.action == "PLAN":
            document["plan"] = self.plan
        if self.output:
            document["output"] = dict(self.output)
        if self.context_update:
            document["context_update"] = dict(self.context_update)
        if self.summary:
            document["summary"] = self.summary
        if self.reason:
            document["reason"] = self.reason
        return document

    @classmethod
    def from_output(cls, output: Mapping[str, Any]) -> "PlannerResponse":
        """Lê a saída de um planejador (por exemplo, de um ``MissionResult``)."""
        if not isinstance(output, Mapping):
            raise ValueError("planner output must be an object")
        unknown = set(output) - {"action", "plan", "output", "context_update", "summary", "reason"}
        if unknown:
            raise ValueError("planner output has unknown fields: " + ", ".join(sorted(unknown)))
        return cls(
            action=_normalize_action(output.get("action")),
            plan=output.get("plan"),
            output=dict(output.get("output") or {}),
            context_update=dict(output.get("context_update") or {}),
            summary=str(output.get("summary") or ""),
            reason=str(output.get("reason") or ""),
        ).validate()


def planner_response_from_json(action, *, plan=None, output_json="", context_update_json="",
                               summary="", reason="") -> dict[str, Any]:
    """Monta a saída do planejador quando objetos chegam como texto JSON.

    Saídas estruturadas de LLM não aceitam objetos livres; o modelo devolve
    ``output`` e ``context_update`` serializados, e aqui eles voltam a ser
    objetos antes da validação.
    """
    return PlannerResponse(
        action=action,
        plan=plan,
        output=_dict_from_json_text(output_json, "output_json"),
        context_update=_dict_from_json_text(context_update_json, "context_update_json"),
        summary=summary,
        reason=reason,
    ).to_output()
