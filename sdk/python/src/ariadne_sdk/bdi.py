from collections.abc import Mapping
from copy import deepcopy

from ariadne_sdk.agent import Agent
from ariadne_sdk.models import Task, TaskResult
from ariadne_sdk.plans import Input, InputError, Plan, checked_cost, resolve_input


def plan(_method=None, *, name=None, priority=0):
    """Marca um método como plano BDI descoberto automaticamente."""
    def decorate(method):
        method._ariadne_bdi_plan = {
            "name": name or method.__name__,
            "priority": priority,
        }
        return method

    if _method is None:
        return decorate
    return decorate(_method)


class BdiAgent(Agent):
    """Agente BDI declarativo, ou classe base para a API histórica.

    Prefira BdiAgent(beliefs=Input('world'), desire=Input('mission'),
    plans=[Plan('solve', execute=solve)], ...). Callbacks recebem
    (beliefs, desire); apenas o plano selecionado é executado. Entradas são
    cópias por tarefa, sem revisão persistente de crenças ou loop autônomo.

    A API histórica de subclasses raciocina no estilo BDI
    (Beliefs, Desires, Intentions).

    Generaliza o ciclo comum a esse tipo de agente — extrair o desejo da
    task, escolher um plano de uma biblioteca com base nas crenças, e
    devolver o resultado com o plano escolhido e o raciocínio — para que
    subclasses só precisem fornecer:

      beliefs       → a base de crenças do agente (qualquer estrutura;
                       é repassada como está para os planos)
      plan_library  → lista ordenada de planos: funções (desire, beliefs)
                       -> dict com {"name", "reasoning_summary", "output"}
                       ou None se o plano não se aplica
      extract_desire(task) → devolve o desejo extraído da task, ou None
                       se a task não contiver as informações necessárias
    """

    def __init__(self, *args, beliefs=None, desire=None, plans=None, plan_library=None, **kwargs):
        if plans is not None and plan_library is not None:
            raise ValueError("use plans or legacy plan_library, not both")
        if plans is None and desire is not None:
            raise ValueError("declarative desire requires plans")
        super().__init__(*args, **kwargs)
        self.plans = tuple(plans) if plans is not None else None
        if self.plans is not None:
            if not self.plans or any(not isinstance(item, Plan) for item in self.plans):
                raise ValueError("plans must contain at least one Plan")
            if len({item.name for item in self.plans}) != len(self.plans):
                raise ValueError("plan names must be unique")
        self._desire_source = Input() if desire is None else desire
        declared_beliefs = getattr(type(self), "beliefs", {})
        self.beliefs = (
            dict(declared_beliefs)
            if beliefs is None and isinstance(declared_beliefs, dict)
            else (declared_beliefs if beliefs is None else beliefs)
        )
        self.plan_library = (
            [] if self.plans is not None
            else list(self._declared_plans() if plan_library is None else plan_library)
        )

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
                candidates.append(((cost is None, cost if cost is not None else 0,
                                    -candidate.priority, index), candidate))

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
        return self._completed_result(task, {
            "name": selected.name,
            "reasoning_summary": "plano selecionado por custo, prioridade e ordem de declaração",
            "output": dict(output),
        }, evaluated)

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

    def _declared_plans(self):
        declared = []
        for attribute_name in dir(self):
            method = getattr(self, attribute_name)
            metadata = getattr(method, "_ariadne_bdi_plan", None)
            if metadata is not None:
                declared.append((metadata["priority"], attribute_name, method, metadata))
        declared.sort(key=lambda item: (-item[0], item[1]))

        wrapped = []
        for _, _, method, metadata in declared:
            def invoke(desire, beliefs, method=method, metadata=metadata):
                candidate = method(desire, beliefs)
                if candidate is None:
                    return None
                candidate = dict(candidate)
                candidate.setdefault("name", metadata["name"])
                candidate.setdefault(
                    "reasoning_summary",
                    f"plano {metadata['name']} aplicável",
                )
                if "output" not in candidate:
                    reserved = {"name", "cost", "reasoning_summary"}
                    output = {
                        key: value
                        for key, value in candidate.items()
                        if key not in reserved
                    }
                    candidate = {
                        key: value
                        for key, value in candidate.items()
                        if key in reserved
                    }
                    candidate["output"] = output
                return candidate
            invoke._ariadne_plan_name = metadata["name"]
            invoke._ariadne_plan_priority = metadata["priority"]
            wrapped.append(invoke)
        return wrapped

    # --- pontos de extensão: subclasses devem sobrescrever ---

    def extract_desire(self, task):
        """Lê o desejo do agente a partir da task (ex.: campos do payload,
        ou — quando presente — task.bdi.goal).

        Devolve o desejo (qualquer estrutura que os planos entendam) ou
        None se a task não tiver as informações necessárias.
        """
        raise NotImplementedError("subclasses devem implementar extract_desire")

    def desire(self, task):
        """Alias amigável preferido pela API pública."""
        return self.extract_desire(task)

    def merge_external_beliefs(self, beliefs_text):
        """Hook opcional: interpreta task.bdi.beliefs (texto livre,
        formato decidido por quem o preencheu) e mescla em self.beliefs.

        Existe para permitir que outro agente do sistema — um agente LLM,
        por exemplo — entregue crenças prontas através do contrato comum
        (BdiExtension.beliefs), demonstrando troca estruturada de
        raciocínio entre agentes heterogêneos.

        Por padrão não faz nada: o formato de beliefs é específico de
        cada agente, então a interpretação fica a cargo da subclasse.
        """

    # --- consumo opcional de Task.bdi (BdiExtension) ---

    def _apply_external_bdi(self, task: Task):
        """Se a task chegar com BdiExtension preenchida, dá à subclasse
        a chance de incorporar as crenças externas antes de deliberar."""
        beliefs = task.bdi.get("beliefs")
        if beliefs:
            self.merge_external_beliefs(beliefs)

    # --- comportamento genérico de seleção e execução ---

    def deliberate(self, desire):
        """Avalia todos os planos aplicáveis da biblioteca e escolhe a
        intenção do agente — o melhor entre eles, não o primeiro.

        Cada plano pode opcionalmente trazer um campo numérico "cost"
        (quanto menor, melhor — ex.: distância, tempo, número de passos).
        Se algum plano aplicável tiver "cost", vence o de menor custo.
        Caso nenhum traga "cost", mantemos o critério mais simples — o
        primeiro aplicável, na ordem da biblioteca — para não forçar
        planos sem noção de custo a competir entre si.

        Devolve None se nenhum plano se aplicar.
        """
        applicable = []
        evaluated = []
        for plan_fn in self.plan_library:
            candidate = plan_fn(desire, self.beliefs)
            name = getattr(plan_fn, "_ariadne_plan_name", plan_fn.__name__)
            if candidate is None:
                evaluated.append({"name": name, "applicable": False})
                continue
            applicable.append(candidate)
            evaluated.append({
                "name": candidate.get("name", name),
                "applicable": True,
                "cost": candidate.get("cost"),
                "reasoning_summary": candidate.get("reasoning_summary", ""),
            })

        if not applicable:
            return None, evaluated

        with_cost = [plan for plan in applicable if plan.get("cost") is not None]
        if with_cost:
            return min(with_cost, key=lambda plan: plan["cost"]), evaluated

        return applicable[0], evaluated

    def select_plan(self, desire):
        """Compatibilidade: devolve somente o plano escolhido."""
        selected, _ = self.deliberate(desire)
        return selected

    def handle(self, task: Task) -> TaskResult:
        if self.plans is not None:
            return self._handle_declared(task)
        self._apply_external_bdi(task)

        # Subclasses novas implementam desire(); as antigas continuam
        # compatíveis sobrescrevendo extract_desire().
        if type(self).desire is not BdiAgent.desire:
            desire = self.desire(task)
        else:
            desire = self.extract_desire(task)
        if desire is None:
            return self._failed_result(
                task,
                code="ERROR_CODE_INVALID_TASK",
                message="não foi possível extrair o desejo da task (payload incompleto)",
                retryable=False,
            )

        plan, evaluated = self.deliberate(desire)
        if plan is None:
            return self._failed_result(
                task,
                code="ERROR_CODE_EXECUTION_FAILED",
                message="nenhum plano da biblioteca se aplica a esse desejo",
                retryable=False,
            )

        return self._completed_result(task, plan, evaluated)

    def execute_task(self, task):
        """Compatibilidade temporária com chamadas locais baseadas em protobuf."""
        friendly = task if isinstance(task, Task) else Task.from_proto(task)
        result = self.handle(friendly)
        return result if isinstance(task, Task) else result.to_proto()

    # --- montagem do TaskResult ---

    def _completed_result(self, task, plan, evaluated):
        metadata_fields = {
            "selected_plan": plan["name"],
            "reasoning_summary": plan["reasoning_summary"],
            "evaluated_plans": evaluated,
        }
        # se quem submeteu a task já trouxe um intention_id (BdiExtension),
        # devolvemos o mesmo identificador — permite correlacionar a
        # intenção combinada entre agentes através do contrato comum
        if task.bdi.get("intention_id"):
            metadata_fields["intention_id"] = task.bdi["intention_id"]

        return TaskResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status="TASK_STATUS_COMPLETED",
            trace=task.trace,
            output=plan.get("output", {}),
            metadata=metadata_fields,
        )

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
