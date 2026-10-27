from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace

from ariadne_sdk.agent import Agent
from ariadne_sdk.deliberation import (
    STATUS_CYCLE_LIMIT, STATUS_NO_APPLICABLE_PLAN, Deliberation, Goal, GoalPlan, rank_key,
)
from ariadne_sdk.models import Task, TaskResult
from ariadne_sdk.plans import Input, InputError, Plan, checked_cost, resolve_input


class BdiAgent(Agent):
    """Agente BDI do SDK, em um de dois modos escolhidos pelo tipo dos planos.

    Deliberativo: BdiAgent(beliefs=Input('state'), goal='deliver',
    plans=[GoalPlan('direct', body=..., context=..., cost=...)], max_cycles=100).
    As crenças nascem do payload (ou de uma função Task -> mapping) e das
    observações feitas pelo plano; morrem com a tarefa. O ciclo perceber,
    revisar, optar, selecionar, agir e observar roda até o objetivo ser
    alcançado, não haver plano aplicável ou o limite de ciclos. O rastro vai
    em metadata['bdi_trace'] e em TaskResult.bdi. goal aceita um nome, Input
    ou função Task -> Goal; sem goal, usa task.bdi.goal ou task.goal.

    Declarativo: BdiAgent(beliefs=Input('world'), desire=Input('mission'),
    plans=[Plan('solve', when=..., cost=..., execute=solve)]). Callbacks
    recebem (beliefs, desire); apenas o plano selecionado é executado, em um
    único ciclo. Entradas são cópias por tarefa, sem revisão de crenças.

    Não se misturam Plan e GoalPlan na mesma biblioteca.
    """

    def __init__(self, *args, beliefs=None, desire=None, plans=None, goal=None, max_cycles=100, **kwargs):
        if plans is None:
            raise ValueError("BdiAgent requires plans: a list of Plan or of GoalPlan")
        super().__init__(*args, **kwargs)
        self.plans = tuple(plans)
        self._deliberation = None
        if self.plans and all(isinstance(item, GoalPlan) for item in self.plans):
            if desire is not None:
                raise ValueError("GoalPlan libraries take goal, not desire")
            self._deliberation = Deliberation(self.plans, max_cycles=max_cycles)
        elif not self.plans or any(not isinstance(item, Plan) for item in self.plans):
            raise ValueError("plans must contain at least one Plan, or only GoalPlan items")
        elif len({item.name for item in self.plans}) != len(self.plans):
            raise ValueError("plan names must be unique")
        if goal is not None and self._deliberation is None:
            raise ValueError("goal applies to GoalPlan libraries; use desire with Plan")
        self._goal_source = goal
        self._desire_source = Input() if desire is None else desire
        if beliefs is None:
            beliefs = Input() if self._deliberation is not None else {}
        self.beliefs = beliefs

    def handle(self, task: Task) -> TaskResult:
        if self._deliberation is not None:
            return self._handle_deliberative(task)
        return self._handle_declared(task)

    def execute_task(self, task):
        """Compatibilidade com chamadas locais baseadas em protobuf."""
        friendly = task if isinstance(task, Task) else Task.from_proto(task)
        result = self.handle(friendly)
        return result if isinstance(task, Task) else result.to_proto()

    # --- API declarativa: um ciclo, apenas o plano escolhido executa ---

    def _handle_declared(self, task):
        # Não escrever crenças recebidas em self: tarefas podem ser concorrentes.
        try:
            beliefs = resolve_input(self.beliefs, task)
            desire = resolve_input(self._desire_source, task)
        except InputError as exc:
            return self._failed_result(task, "ERROR_CODE_INVALID_TASK", str(exc), False)

        candidates, evaluated = [], []
        for index, candidate in enumerate(self.plans):
            try:
                applicable = candidate.when is None or bool(candidate.when(beliefs, desire))
                cost = None
                if applicable and candidate.cost is not None:
                    cost = checked_cost(candidate.cost(beliefs, desire) if callable(candidate.cost) else candidate.cost)
            except Exception as exc:
                evaluated.append({"name": candidate.name, "error": str(exc)})
                return self._declared_failure(task, exc, evaluated, "evaluation")
            evaluated.append({"name": candidate.name, "applicable": applicable,
                              "cost": cost, "priority": candidate.priority})
            if applicable:
                candidates.append((rank_key(cost, candidate.priority, index), candidate))

        if not candidates:
            result = self._failed_result(task, "ERROR_CODE_EXECUTION_FAILED",
                                         "nenhum plano da biblioteca se aplica a esse desejo", False)
            result.metadata.update({"evaluated_plans": evaluated})
            return result

        _, selected = min(candidates, key=lambda item: item[0])
        # Avaliação e efeitos são fases distintas. Nenhum outro execute é chamado.
        try:
            output = selected.execute(deepcopy(beliefs), deepcopy(desire))
            if not isinstance(output, Mapping):
                raise TypeError(f"plan {selected.name!r} must return a Mapping")
        except Exception as exc:
            return self._declared_failure(task, exc, evaluated, "execution", selected.name)
        metadata = {
            "selected_plan": selected.name,
            "reasoning_summary": "plano selecionado por custo, prioridade e ordem de declaração",
            "evaluated_plans": evaluated,
        }
        # Um intention_id recebido em Task.bdi volta no resultado para correlação.
        if task.bdi.get("intention_id"):
            metadata["intention_id"] = task.bdi["intention_id"]
        return TaskResult(task_id=task.task_id, agent_id=self.agent_id,
                          status="TASK_STATUS_COMPLETED", trace=task.trace,
                          output=dict(output), metadata=metadata)

    def _declared_failure(self, task, error, evaluated, phase, selected=None):
        code = ("ERROR_CODE_INVALID_TASK" if isinstance(error, ValueError)
                else "ERROR_CODE_TIMEOUT" if isinstance(error, TimeoutError)
                else "ERROR_CODE_EXECUTION_FAILED")
        result = self._failed_result(task, code, str(error) or type(error).__name__, isinstance(error, TimeoutError))
        result.metadata.update({"evaluated_plans": evaluated, "failure_phase": phase,
                                "error_type": type(error).__name__})
        if selected is not None:
            result.metadata["selected_plan"] = selected
        if task.bdi.get("intention_id"):
            result.metadata["intention_id"] = task.bdi["intention_id"]
        return result

    # --- ciclo de deliberação com escopo de uma tarefa ---

    def _resolve_goal(self, task):
        source = self._goal_source
        if source is None:
            value = task.bdi.get("goal") or task.goal
            if not value:
                raise InputError("task has no goal: set Task.goal, Task.bdi.goal or BdiAgent(goal=...)")
        elif isinstance(source, str):
            value = source
        else:
            value = resolve_input(source, task)
        try:
            return Goal.coerce(value)
        except (TypeError, ValueError) as exc:
            raise InputError(str(exc)) from exc

    def _handle_deliberative(self, task):
        try:
            beliefs = resolve_input(self.beliefs, task)
            if not isinstance(beliefs, Mapping):
                raise InputError("beliefs must resolve to a mapping of initial beliefs")
            goal = self._resolve_goal(task)
        except InputError as exc:
            return self._failed_result(task, "ERROR_CODE_INVALID_TASK", str(exc), False)

        outcome = self._deliberation.run(goal, beliefs)
        summary = (f"objetivo {goal} {outcome.status} em {outcome.cycle_count} ciclo(s)"
                   + (f"; plano {outcome.selected_plan}" if outcome.selected_plan else ""))
        metadata = {"reasoning_summary": summary, "goals": list(outcome.goals),
                    "bdi_trace": outcome.trace()}
        if outcome.selected_plan:
            metadata["selected_plan"] = outcome.selected_plan
        if task.bdi.get("intention_id"):
            metadata["intention_id"] = task.bdi["intention_id"]
        bdi = {key: value for key, value in {
            "goal": str(goal), "selected_plan": outcome.selected_plan,
            "intention_id": task.bdi.get("intention_id", ""), "reasoning_summary": summary,
            "goals": list(outcome.goals), "trace": outcome.trace(),
        }.items() if value}

        if outcome.achieved:
            return TaskResult(task_id=task.task_id, agent_id=self.agent_id,
                              status="TASK_STATUS_COMPLETED", trace=task.trace,
                              output=outcome.output, metadata=metadata, bdi=bdi)
        error = outcome.error
        code, retryable = "ERROR_CODE_EXECUTION_FAILED", False
        if outcome.status == STATUS_NO_APPLICABLE_PLAN:
            message = f"nenhum plano aplicável ao objetivo {goal}"
        elif outcome.status == STATUS_CYCLE_LIMIT:
            message = f"limite de {self._deliberation.max_cycles} ciclos atingido sem alcançar {goal}"
        else:
            code = ("ERROR_CODE_INVALID_TASK" if isinstance(error, ValueError)
                    else "ERROR_CODE_TIMEOUT" if isinstance(error, TimeoutError)
                    else "ERROR_CODE_EXECUTION_FAILED")
            message = f"objetivo {goal} falhou" + (f": {error}" if error else "")
            retryable = isinstance(error, TimeoutError)
            if error is not None:
                metadata["error_type"] = type(error).__name__
        result = self._failed_result(task, code, message, retryable)
        result.metadata.update(metadata)
        return replace(result, bdi=bdi)

    def _failed_result(self, task, code, message, retryable):
        return TaskResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status="TASK_STATUS_FAILED",
            trace=task.trace,
            error_code=code,
            error_message=message,
            retryable=retryable,
        )
