"""Ciclo de deliberação BDI com escopo de uma tarefa.

Crenças nascem do payload da tarefa e das observações feitas durante a
execução; morrem com a tarefa. Planos têm um objetivo que atendem (gatilho),
uma condição de contexto sobre as crenças, custo, prioridade e um corpo. O
corpo pode ser uma função simples (um passo) ou um gerador que produz passos:
observe(...), forget(...), achieve(...) e act(...). Cada ciclo executa um
passo da intenção corrente e registra o que mudou.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
import inspect
import json
from numbers import Real
from typing import Any, Callable

from ariadne_sdk.plans import checked_cost


STATUS_ACHIEVED = "achieved"
STATUS_NO_APPLICABLE_PLAN = "no_applicable_plan"
STATUS_CYCLE_LIMIT = "cycle_limit"
STATUS_FAILED = "failed"

OUTCOME_CONTINUE = "continue"


def render(value) -> str:
    """Representação compacta e estável de um valor para o rastro."""
    try:
        return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)


def render_belief(key, value) -> str:
    return key if value is True else f"{key}={render(value)}"


class BeliefBase(MutableMapping):
    """Base de crenças de uma tarefa: um mapping que registra o que mudou.

    add/revise acrescentam ou substituem; remove apaga. Cada mudança fica
    pendente em texto (``chave=valor``) até drain_changes(), que o ciclo de
    deliberação chama ao fim de cada ciclo para preencher o rastro.
    """

    def __init__(self, initial=None):
        self._facts: dict[str, Any] = {}
        self._added: list[str] = []
        self._removed: list[str] = []
        if initial:
            self.revise(initial)

    def __getitem__(self, key):
        return self._facts[key]

    def __setitem__(self, key, value):
        self.add(key, value)

    def __delitem__(self, key):
        if key not in self._facts:
            raise KeyError(key)
        self.remove(key)

    def __iter__(self):
        return iter(self._facts)

    def __len__(self):
        return len(self._facts)

    def __repr__(self):
        return f"BeliefBase({self._facts!r})"

    def add(self, key, value=True):
        if not isinstance(key, str) or not key:
            raise TypeError("belief keys must be non-empty strings")
        if key in self._facts:
            try:
                unchanged = self._facts[key] == value
            except Exception:
                unchanged = False
            if unchanged:
                return
            self._removed.append(render_belief(key, self._facts[key]))
        self._facts[key] = value
        self._added.append(render_belief(key, value))

    def remove(self, key):
        """Apaga uma crença; chaves ausentes são ignoradas."""
        if key in self._facts:
            self._removed.append(render_belief(key, self._facts.pop(key)))

    def revise(self, facts=None, **named):
        """Incorpora várias crenças de uma vez (mapping e/ou nomeadas)."""
        if facts is not None and not isinstance(facts, Mapping):
            raise TypeError("beliefs must be revised from a mapping")
        for key, value in {**dict(facts or {}), **named}.items():
            self.add(key, value)

    def snapshot(self) -> dict[str, Any]:
        return dict(self._facts)

    def drain_changes(self) -> tuple[list[str], list[str]]:
        """Devolve (adicionadas, removidas) desde a última chamada e zera."""
        added, removed = self._added, self._removed
        self._added, self._removed = [], []
        return added, removed


@dataclass(frozen=True)
class Goal:
    """Objetivo a alcançar: nome (casado com GoalPlan.goal) e parâmetros."""

    name: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Goal requires a non-empty name")
        if not isinstance(self.params, Mapping):
            raise TypeError("Goal params must be a mapping")
        object.__setattr__(self, "params", dict(self.params))

    def __str__(self):
        if not self.params:
            return self.name
        inside = ", ".join(f"{key}={render(value)}" for key, value in self.params.items())
        return f"{self.name}({inside})"

    @classmethod
    def coerce(cls, value) -> "Goal":
        """Aceita Goal, string ou mapping {"name": ..., "params": {...}}."""
        if isinstance(value, Goal):
            return value
        if isinstance(value, str):
            return cls(value)
        if isinstance(value, Mapping) and "name" in value:
            params = value.get("params")
            if params is None:
                params = {key: item for key, item in value.items() if key != "name"}
            return cls(value["name"], params)
        raise TypeError("goal must be a Goal, a string or a mapping with 'name'")


class GoalFailure(Exception):
    """Um sub-objetivo falhou; é lançado dentro do corpo do plano pai."""

    def __init__(self, goal: Goal, reason: str, cause: BaseException | None = None):
        super().__init__(f"goal {goal} {reason}" + (f": {cause}" if cause else ""))
        self.goal = goal
        self.reason = reason
        self.cause = cause


# --- passos que um corpo de plano pode produzir com yield ---

@dataclass(frozen=True)
class Observe:
    facts: Mapping[str, Any]

    def describe(self):
        inside = ", ".join(render_belief(key, value) for key, value in self.facts.items())
        return f"observe({inside})"


@dataclass(frozen=True)
class Forget:
    keys: tuple[str, ...]

    def describe(self):
        return f"forget({', '.join(self.keys)})"


@dataclass(frozen=True)
class Achieve:
    goal: Goal

    def describe(self):
        return f"achieve({self.goal})"


@dataclass(frozen=True)
class Act:
    action: Callable[..., Any]
    args: tuple = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)

    def describe(self):
        name = getattr(self.action, "__name__", None) or type(self.action).__name__
        return f"act({name})"


Step = Observe | Forget | Achieve | Act


def observe(facts=None, **named) -> Observe:
    """Passo: incorpora crenças (percepção explícita do plano)."""
    if facts is not None and not isinstance(facts, Mapping):
        raise TypeError("observe expects a mapping or keyword beliefs")
    return Observe({**dict(facts or {}), **named})


def forget(*keys: str) -> Forget:
    """Passo: remove crenças pelo nome."""
    if not keys or any(not isinstance(key, str) for key in keys):
        raise TypeError("forget expects belief names")
    return Forget(tuple(keys))


def achieve(goal, **params) -> Achieve:
    """Passo: adota um sub-objetivo; o valor do yield é o resultado dele."""
    if params and not isinstance(goal, str):
        raise TypeError("achieve accepts params only with a goal name")
    return Achieve(Goal(goal, params) if isinstance(goal, str) else Goal.coerce(goal))


def act(action, *args, **kwargs) -> Act:
    """Passo: executa uma ação; um retorno mapping vira crenças observadas."""
    if not callable(action):
        raise TypeError("act expects a callable")
    return Act(action, args, kwargs)


@dataclass(frozen=True)
class GoalPlan:
    """Plano da biblioteca: gatilho (goal), contexto, custo, prioridade e corpo.

    body(beliefs, goal) devolve um mapping (plano de um passo) ou um gerador
    que produz passos e, ao final, devolve o resultado com return. context e
    cost recebem (beliefs, goal) e devem ser puros. Sem goal, o gatilho é o
    próprio name.
    """

    name: str
    body: Callable[[BeliefBase, Goal], Any]
    goal: str | None = None
    context: Callable[[BeliefBase, Goal], bool] | None = None
    cost: Real | Callable[[BeliefBase, Goal], Real] | None = None
    priority: int = 0

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("GoalPlan requires a non-empty name")
        if not callable(self.body):
            raise TypeError("GoalPlan.body must be callable")
        if self.goal is None:
            object.__setattr__(self, "goal", self.name)
        elif not isinstance(self.goal, str) or not self.goal.strip():
            raise ValueError("GoalPlan.goal must be a non-empty string")
        if self.context is not None and not callable(self.context):
            raise TypeError("GoalPlan.context must be callable")
        if self.cost is not None and not callable(self.cost):
            checked_cost(self.cost)
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise TypeError("GoalPlan.priority must be an integer")


def rank_key(cost, priority, index):
    """Menor custo vence; sem custo é fallback; empates: prioridade, ordem."""
    return (cost is None, cost if cost is not None else 0, -priority, index)


@dataclass(frozen=True)
class DeliberationResult:
    status: str
    output: Any
    goals: tuple[str, ...]
    cycles: tuple[dict, ...]
    selected_plan: str
    error: BaseException | None = None

    @property
    def achieved(self) -> bool:
        return self.status == STATUS_ACHIEVED

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)

    def trace(self) -> dict:
        """Formato de BdiTrace do contrato (e de metadata["bdi_trace"])."""
        return {"cycles": [dict(cycle) for cycle in self.cycles],
                "cycle_count": self.cycle_count, "final_status": self.status}


@dataclass
class _Intention:
    """Uma entrada da pilha de intenções: objetivo e plano em execução."""

    goal: Goal
    plan: GoalPlan | None = None
    generator: Any = None
    tried: list[str] = field(default_factory=list)
    resume: tuple = ("send", None)  # ("send", valor) | ("throw", exc) | ("step", passo)
    last_error: BaseException | None = None


class Deliberation:
    """Executa o ciclo perceber, revisar, optar, selecionar, agir, observar."""

    def __init__(self, plans, *, max_cycles: int = 100):
        self.plans = tuple(plans)
        if not self.plans or any(not isinstance(item, GoalPlan) for item in self.plans):
            raise ValueError("plans must contain at least one GoalPlan")
        if len({item.name for item in self.plans}) != len(self.plans):
            raise ValueError("plan names must be unique")
        if isinstance(max_cycles, bool) or not isinstance(max_cycles, int) or max_cycles < 1:
            raise ValueError("max_cycles must be a positive integer")
        self.max_cycles = max_cycles

    def options(self, goal: Goal, beliefs: BeliefBase, exclude=()) -> list[GoalPlan]:
        """Planos aplicáveis ao objetivo, do mais ao menos preferido."""
        ranked = []
        for index, plan in enumerate(self.plans):
            if plan.goal != goal.name or plan.name in exclude:
                continue
            if plan.context is not None and not plan.context(beliefs, goal):
                continue
            cost = None
            if plan.cost is not None:
                cost = checked_cost(plan.cost(beliefs, goal) if callable(plan.cost) else plan.cost)
            ranked.append((rank_key(cost, plan.priority, index), plan))
        ranked.sort(key=lambda item: item[0])
        return [plan for _, plan in ranked]

    def run(self, goal, beliefs=None) -> DeliberationResult:
        return _Run(self, Goal.coerce(goal),
                    beliefs if isinstance(beliefs, BeliefBase) else BeliefBase(beliefs)).execute()


class _Run:
    """Estado de uma deliberação: pilha de intenções, rastro e desfecho."""

    def __init__(self, engine: Deliberation, goal: Goal, beliefs: BeliefBase):
        self.engine = engine
        self.beliefs = beliefs
        self.stack = [_Intention(goal)]
        self.goals = [str(goal)]
        self.cycles: list[dict] = []
        self.status: str | None = None
        self.output = None
        self.error: BaseException | None = None
        self.top_plan = ""

    def execute(self) -> DeliberationResult:
        while self.status is None:
            if len(self.cycles) >= self.engine.max_cycles:
                self.status = STATUS_CYCLE_LIMIT
                break
            self.cycle()
        return DeliberationResult(self.status, self.output, tuple(self.goals),
                                  tuple(self.cycles), self.top_plan, self.error)

    def cycle(self):
        frame = self.stack[-1]
        record = {"goal": str(frame.goal), "selected_plan": frame.plan.name if frame.plan else "",
                  "action": "", "outcome": OUTCOME_CONTINUE}
        if frame.plan is None:
            self.select(frame, record)
        if frame.plan is not None and record["outcome"] == OUTCOME_CONTINUE:
            self.step(frame, record)
        added, removed = self.beliefs.drain_changes()
        self.cycles.append({"cycle": len(self.cycles) + 1, "beliefs_added": added,
                            "beliefs_removed": removed, **record})

    # --- gerar opções e selecionar a intenção ---

    def select(self, frame: _Intention, record: dict):
        try:
            options = self.engine.options(frame.goal, self.beliefs, exclude=frame.tried)
        except Exception as error:
            record["action"] = f"evaluate -> {type(error).__name__}: {error}"
            record["outcome"] = STATUS_FAILED
            self.error = error
            self.status = STATUS_FAILED
            return
        if options:
            frame.plan, frame.generator, frame.resume = options[0], None, ("send", None)
            record["selected_plan"] = frame.plan.name
            if frame is self.stack[0]:
                self.top_plan = frame.plan.name
            return
        reason = STATUS_FAILED if frame.tried else STATUS_NO_APPLICABLE_PLAN
        record["outcome"] = reason
        self.fail_goal(frame, reason)

    def fail_goal(self, frame: _Intention, reason: str):
        self.stack.pop()
        if not self.stack:
            self.status, self.error = reason, frame.last_error
            return
        self.stack[-1].resume = ("throw", GoalFailure(frame.goal, reason, frame.last_error))

    # --- executar um passo da intenção corrente ---

    def step(self, frame: _Intention, record: dict):
        try:
            if frame.generator is None:
                produced = frame.plan.body(self.beliefs, frame.goal)
                if not inspect.isgenerator(produced):
                    record["action"] = "return"
                    self.achieve(frame, produced, record)
                    return
                frame.generator = produced
                step = produced.send(None)
            else:
                mode, value = frame.resume
                step = (value if mode == "step" else frame.generator.throw(value) if mode == "throw"
                        else frame.generator.send(value))
        except StopIteration as stop:
            record["action"] = "return"
            self.achieve(frame, stop.value, record)
            return
        except Exception as error:
            record["action"] = "resume" if frame.generator is not None else "body"
            self.plan_failed(frame, error, record)
            return
        self.perform(frame, step, record)

    def perform(self, frame: _Intention, step, record: dict):
        if not isinstance(step, (Observe, Forget, Achieve, Act)):
            record["action"] = f"yield {type(step).__name__}"
            self.plan_failed(frame, TypeError(
                f"plan {frame.plan.name!r} yielded {type(step).__name__}; "
                "use observe, forget, achieve or act"), record)
            return
        record["action"] = step.describe()
        frame.resume = ("send", None)
        if isinstance(step, Observe):
            self.beliefs.revise(step.facts)
        elif isinstance(step, Forget):
            for key in step.keys:
                self.beliefs.remove(key)
        elif isinstance(step, Achieve):
            self.stack.append(_Intention(step.goal))
            self.goals.append(str(step.goal))
        else:
            self.perform_action(frame, step, record)

    def perform_action(self, frame: _Intention, step: Act, record: dict):
        try:
            value = step.action(*step.args, **step.kwargs)
        except Exception as error:
            record["action"] += f" raised {type(error).__name__}: {error}"
            # A exceção vai para o corpo do plano; se ele não a tratar, o plano falha.
            try:
                frame.resume = ("step", frame.generator.throw(error))
            except StopIteration as stop:
                record["action"] = record["action"].replace(" raised ", " handled ", 1) + ", return"
                self.achieve(frame, stop.value, record)
            except Exception as unhandled:
                self.plan_failed(frame, unhandled, record)
            else:
                record["action"] = record["action"].replace(" raised ", " handled ", 1)
            return
        if isinstance(value, Mapping):
            self.beliefs.revise(value)
        frame.resume = ("send", value)

    # --- desfechos de um plano ---

    def achieve(self, frame: _Intention, value, record: dict):
        if frame is self.stack[0] and value is not None and not isinstance(value, Mapping):
            self.plan_failed(frame, TypeError(f"plan {frame.plan.name!r} must return a Mapping"), record)
            return
        record["outcome"] = STATUS_ACHIEVED
        self.stack.pop()
        if not self.stack:
            self.status, self.output = STATUS_ACHIEVED, dict(value or {})
            return
        self.stack[-1].resume = ("send", value)

    def plan_failed(self, frame: _Intention, error: BaseException, record: dict):
        record["action"] += f" -> {type(error).__name__}: {error}"
        record["outcome"] = STATUS_FAILED
        frame.tried.append(frame.plan.name)
        frame.plan, frame.generator, frame.resume, frame.last_error = None, None, ("send", None), error
