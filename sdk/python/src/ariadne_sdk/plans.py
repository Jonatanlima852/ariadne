"""Declarações BDI: entradas e planos independentes do transporte."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import math
from numbers import Real
from typing import Any, Callable


_MISSING = object()


class InputError(ValueError):
    """Um campo obrigatório não foi recebido."""


@dataclass(frozen=True, init=False)
class Input:
    """Campo do payload: Input('world'), Input('mission', 'destination').

    Input() usa o payload inteiro. default é usado apenas quando falta o campo,
    nunca para substituir valores presentes como False, 0, None ou {}.
    """

    path: tuple[str, ...]
    default: Any

    def __init__(self, *path, default=_MISSING):
        if any(not isinstance(part, str) or not part for part in path):
            raise ValueError("Input path must contain non-empty string keys")
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "default", default)

    def resolve(self, task):
        value = task.payload
        for part in self.path:
            if not isinstance(value, Mapping) or part not in value:
                if self.default is not _MISSING:
                    return deepcopy(self.default)
                raise InputError(f"missing payload input: {'.'.join(self.path)}")
            value = value[part]
        return deepcopy(value)


def resolve_input(source, task):
    """Resolve seletores, funções Task -> valor e valores literais."""
    if isinstance(source, Input):
        return source.resolve(task)
    if callable(source):
        return deepcopy(source(task))
    return deepcopy(source)


def checked_cost(value):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError("plan cost must be a finite number")
    return value


@dataclass(frozen=True)
class Plan:
    """Callbacks recebem (beliefs, desire); when/cost devem ser puros.

    Planos com custo têm preferência sobre fallbacks sem custo. Menor custo
    vence; empates usam maior priority, depois a ordem de declaração.
    execute é chamado apenas para o escolhido e retorna um Mapping.
    """

    name: str
    execute: Callable[[Any, Any], Mapping]
    when: Callable[[Any, Any], bool] | None = None
    cost: Real | Callable[[Any, Any], Real] | None = None
    priority: int = 0

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Plan requires a non-empty name")
        if not callable(self.execute):
            raise TypeError("Plan.execute must be callable")
        if self.when is not None and not callable(self.when):
            raise TypeError("Plan.when must be callable")
        if self.cost is not None and not callable(self.cost):
            checked_cost(self.cost)
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise TypeError("Plan.priority must be an integer")
