"""Declarações de etapas, sem execução nem dependência de infraestrutura."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any


@dataclass(frozen=True)
class OutputRef:
    step: Step
    path: tuple[str, ...] = ()

    def __getitem__(self, key):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError("output references require simple string field names")
        return OutputRef(self.step, self.path + (key,))


@dataclass(eq=False)
class Step:
    """Uma tarefa declarada. Referências a outputs criam dependências."""

    capability: str
    goal: str
    payload: dict[str, Any] = field(default_factory=dict)
    name: str | None = None
    depends_on: tuple[Step, ...] = ()
    deadline_ms: int = 0
    max_attempts: int = 1
    backoff_ms: int = 0
    exclude_failed_agent: bool = False
    selection_policy: str = "FIRST_AVAILABLE"

    @property
    def output(self):
        return OutputRef(self)


def compile_steps(tasks):
    """Traduz referências para o contrato de workflow já usado pelo runtime."""
    if not tasks or any(not isinstance(step, Step) for step in tasks):
        raise ValueError("scenario.tasks must contain at least one Step")
    if len({id(step) for step in tasks}) != len(tasks):
        raise ValueError("the same Step cannot occur twice")
    names = {step: step.name or f"step_{i + 1}" for i, step in enumerate(tasks)}
    if len(set(names.values())) != len(names):
        raise ValueError("step names must be unique")
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", name) for name in names.values()):
        raise ValueError("step names must be simple identifiers")
    compiled = []
    for step in tasks:
        if not step.capability or not isinstance(step.goal, str):
            raise ValueError("each Step requires a capability and a string goal")
        if step.deadline_ms < 0 or step.backoff_ms < 0 or step.max_attempts < 1:
            raise ValueError("invalid timeout or retry policy")
        dependencies = list(step.depends_on)
        bindings = []

        def visit(value, path=()):
            if isinstance(value, OutputRef):
                if value.step not in names:
                    raise ValueError("output refers to a Step outside this scenario")
                if not path:
                    raise ValueError("put output references inside a payload field")
                if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in path):
                    raise ValueError("binding targets require simple field names")
                dependencies.append(value.step)
                bindings.append({
                    "source_step_id": names[value.step],
                    "source_path": ".".join(("output",) + value.path),
                    "target_field": ".".join(path),
                })
                return None
            if isinstance(value, dict):
                if any(not isinstance(key, str) for key in value):
                    raise ValueError("payload keys must be strings")
                return {key: visit(item, path + (key,)) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                # The frozen contract supports object paths, not array indexing.
                def has_ref(item):
                    if isinstance(item, OutputRef):
                        return True
                    if isinstance(item, dict):
                        return any(has_ref(v) for v in item.values())
                    return isinstance(item, (list, tuple)) and any(has_ref(v) for v in item)
                if has_ref(value):
                    raise ValueError("output references inside arrays are not supported")
                return list(value)
            return value

        if not isinstance(step.payload, dict):
            raise ValueError("Step.payload must be a dictionary")
        payload = visit(step.payload)
        json.dumps(payload, allow_nan=False)
        if any(dependency not in names for dependency in dependencies):
            raise ValueError("dependency refers to a Step outside this scenario")
        compiled.append({
            "step_id": names[step], "goal": step.goal,
            "capabilities": [step.capability], "payload": payload,
            "depends_on": list(dict.fromkeys(names[d] for d in dependencies)),
            "input_bindings": bindings, "deadline_ms": step.deadline_ms,
            "max_attempts": step.max_attempts, "backoff_ms": step.backoff_ms,
            "exclude_failed_agent": step.exclude_failed_agent,
            "selection_policy": step.selection_policy,
        })
    graph = {item["step_id"]: item["depends_on"] for item in compiled}
    visited, active = set(), set()

    def check(name):
        if name in active:
            raise ValueError("scenario contains a dependency cycle")
        if name in visited:
            return
        active.add(name)
        for dependency in graph[name]:
            check(dependency)
        active.remove(name)
        visited.add(name)

    for name in graph:
        check(name)
    return compiled
