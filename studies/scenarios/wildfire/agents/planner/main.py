"""Comandante LLM da configuração cooperativa (capacidade ``mission-planning``).

O modelo decide o que o laço não sabe decidir: a meta de cada drone nesta
rodada (atacar, proteger, reabastecer, voltar, aguardar ou automático) e as
crenças compartilhadas que só o rádio informa (bases fora de serviço, células
prioritárias). A parte determinística do agente converte essa decisão no
``PlannerResponse`` do contrato: um passo ``drone-<id>`` por drone ativo
(snapshot + ordem + crenças) e um passo ``world`` que depende de todos e
recebe as ações por bindings.

``WILDFIRE_COMMAND_EVERY`` (padrão 1) é a cadência: com N > 1, o modelo só é
chamado na rodada 1, quando há novidade (rádio, rejeição, drone perdido,
falha) ou a cada N rodadas; nas demais as ordens anteriores valem (ordens
permanentes) e nenhum modelo é chamado.
"""
import json
import os
import re
import threading
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ariadne_sdk import LlmAgent, PlannerRequest, PlannerResponse, Prompt, TaskResult
from ariadne_sdk.llm import LlmCapability
from studies.scenarios.wildfire.agents.common import DemoClient, demo_enabled, llm_runtime, mark_demo
from studies.scenarios.wildfire.domain.adapters import (
    MAX_DRONE_STEPS, OBJECTIVES, PLANNER_CAPABILITY, WORLD_STEP_ID, active_drones, drone_step, last_round_report,
    normalize_command, normalize_order, planner_view, restore_integers, world_step,
)
from studies.scenarios.wildfire.domain.world import chebyshev, describe_rules, distance, is_done, metrics


class DroneOrder(BaseModel):
    model_config = ConfigDict(extra='forbid')
    drone: str
    objective: Literal['auto', 'attack', 'protect', 'resupply', 'return', 'hold']
    target: str | None = Field(description='Cell "x,y" for attack (burning cell) or protect (structure cell); otherwise null')
    note: str = Field(description='Short rationale')


class CommandBeliefs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    disabled_bases: list[str] = Field(description='Base ids the radio declared out of service; drones never use them')
    priority_cells: list[str] = Field(description='Cells "x,y" to extinguish or protect first')
    hazards: str = Field(description='One line about current hazards, or empty')


class CommandDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['PLAN', 'DONE', 'ABORT']
    summary: str = Field(description='One sentence about the decision')
    reason: str = Field(description='Required for ABORT, otherwise empty')
    orders: list[DroneOrder] = Field(description='For PLAN: at most one order per active drone; omitted drones act on auto')
    beliefs: CommandBeliefs


INSTRUCTION = (
    'You are the incident commander of a wildfire drone squadron. You do NOT pilot drones. Each round you read '
    'the map (fires with intensity, ash, bases, drones with battery and water) and the radio, and you give each '
    'active drone ONE objective: attack (target = a burning cell), protect (target = a structure cell to keep '
    'safe), resupply, return, hold, or auto (the drone picks the nearest safe fire by itself). Each drone is a '
    'deliberative BDI agent: it plans its own path around obstacles, keeps a battery reserve to reach a usable '
    'base, resupplies when empty and treats your beliefs as facts. Put in disabled_bases every base the radio '
    'declared out of service (telemetry still shows it active; drones would be rejected or lost there) and in '
    'priority_cells the cells to protect or extinguish first (for instance a hospital announced on the radio). '
    'Drones only know telemetry plus your beliefs and orders: whatever exists only in the radio must be '
    'translated by you. A deterministic world then applies every action, spreads the fire and reports accepted '
    'and rejected actions; a rejection means a wrong belief or an impossible order. Spread drones across fronts, '
    'send them where the fire threatens structures and where it will spread (downwind), and do not idle drones '
    'with water. Answer DONE only when no fire is left or the horizon is reached; ABORT only if the data is '
    'inconsistent.'
)


def planner_prompt(request):
    state = restore_integers(request.context.get('state') or {})
    return Prompt(system=f'ROLE=Commander\n{INSTRUCTION}\n{describe_rules(state)}',
                  user=json.dumps(planner_view(request, with_command=True), ensure_ascii=False))


def done_response(request, summary):
    context = restore_integers(request.context)
    state = context['state']
    measured = context.get('metrics') or metrics(state)
    return PlannerResponse.done({'metrics': measured, 'tick': state['tick'], 'burned': len(state['ash']),
                                 'fires_remaining': len(state['fires']), 'summary': summary}, summary=summary)


def shortcut(request):
    """Decisões que não exigem o modelo: sem fogo, ou horizonte atingido."""
    state = restore_integers(request.context.get('state') or {})
    if not state:
        return None
    if not state['fires']:
        return done_response(request, 'all fires are out'), 'all_fires_out'
    if is_done(state):
        return done_response(request, f"horizon of {state['horizon']} ticks reached"), 'horizon_reached'
    return None


def news(request):
    """Houve novidade desde a última chamada ao modelo? Rádio, rejeição, perda ou falha."""
    report = last_round_report(request)
    if report is None:
        return True
    return bool(report['radio'] or report['rejected'] or report['lost_drones'] or report['failures'])


def plan_from_orders(request, orders, command, *, summary, warnings=(), context_update=None):
    """Passos do plano a partir de ordens já normalizadas por drone."""
    context = restore_integers(request.context)
    state = context['state']
    active = active_drones(state)
    warnings = list(warnings)
    if len(active) > MAX_DRONE_STEPS:
        warnings.append(f'{len(active) - MAX_DRONE_STEPS} drone(s) without a step this round: at most '
                        f'{MAX_DRONE_STEPS} drone steps per plan')
        active = active[:MAX_DRONE_STEPS]
    steps = [drone_step(state, drone_id, orders.get(drone_id) or {}, command) for drone_id in active]
    ids = [step['step_id'] for step in steps]
    steps.append(world_step(state, context['case'], drone_step_ids=ids))
    update = {'command': command, 'orders': {d: orders.get(d) or normalize_order({}) for d in active},
              'last_plan': {'round': request.round, 'warnings': warnings, 'summary': summary}, **(context_update or {})}
    return PlannerResponse.make_plan(steps, final_step_id=WORLD_STEP_ID, workflow_id=f'wildfire-round-{request.round}',
                                     summary=summary, context_update=update)


def build_response(request, decision):
    """Decisão validada do modelo -> PlannerResponse do contrato."""
    if decision.action == 'ABORT':
        return PlannerResponse.abort(decision.reason or decision.summary, summary=decision.summary).to_output()
    if decision.action == 'DONE':
        decided = shortcut(request)
        if decided is not None:
            return decided[0].to_output()
        # O modelo quis parar com fogo ativo e tiques restantes: o mundo continua; registra e segue.
        return plan_from_orders(request, {}, normalize_command(decision.beliefs.model_dump()),
                                summary='model answered DONE with fires left; drones continue on auto',
                                warnings=['DONE ignored: fires remain before the horizon'],
                                context_update={'command_round': request.round}).to_output()
    state = restore_integers(request.context['state'])
    active = set(active_drones(state))
    orders, warnings = {}, []
    for order in decision.orders:
        if order.drone not in active:
            warnings.append(f'ignored order for unknown, lost or offline drone {order.drone}')
            continue
        if order.drone in orders:
            warnings.append(f'ignored repeated order for {order.drone}')
            continue
        orders[order.drone] = normalize_order(order.model_dump())
    command = normalize_command(decision.beliefs.model_dump())
    return plan_from_orders(request, orders, command, summary=decision.summary, warnings=warnings,
                            context_update={'command_round': request.round}).to_output()


def substitute_command(view):
    """Política fixa para a demonstração sem credenciais (não é um benchmark).

    Lê o rádio com expressões regulares simples só para exercitar o caminho
    das crenças: bases "FORA DE SERVIÇO"/"explodiu" e um "hospital ... (x,y)".
    """
    text = ' '.join(item.get('text', '') for item in view.get('radio', []))
    # Só a base citada ANTES de "FORA DE SERVIÇO"/"explodiu" na mesma frase; a base
    # recomendada ("usar a base SUL B2") vem depois e continua utilizável.
    disabled = sorted(set(re.findall(r'\b(B\d+)\b[^.;]*?(?:FORA DE SERVIÇO|explodiu)', text)))
    hospital = re.search(r'hospital[^()]*\((\d+),\s*(\d+)\)', text)
    priority = [f'{hospital.group(1)},{hospital.group(2)}'] if hospital else []
    fires = [item['cell'] for item in view.get('fires', [])]
    orders = []
    drones = [d for d, info in sorted(view.get('drones', {}).items()) if info.get('condition') == 'ok']
    for index, drone_id in enumerate(drones):
        at = view['drones'][drone_id]['at']
        if priority and index == 0:
            orders.append({'drone': drone_id, 'objective': 'protect', 'target': priority[0],
                           'note': 'deterministic substitute: protect the cell the radio announced'})
        elif fires and index == 1:
            target = min(fires, key=lambda c: (chebyshev(at, c), c))
            orders.append({'drone': drone_id, 'objective': 'attack', 'target': target,
                           'note': 'deterministic substitute: attack the nearest burning cell'})
        else:
            orders.append({'drone': drone_id, 'objective': 'auto', 'target': None,
                           'note': 'deterministic substitute: the drone picks its own target'})
    return {'action': 'PLAN', 'summary': f'demo: {len(orders)} order(s), {len(disabled)} base(s) disabled by radio',
            'reason': '', 'orders': orders,
            'beliefs': {'disabled_bases': disabled, 'priority_cells': priority, 'hazards': ''}}


class Commander(LlmAgent):
    runtime_name = 'wildfire-llm'

    def __init__(self, demo=None, command_every=None, **options):
        self.demo = demo_enabled(demo)
        self.command_every = max(1, int(command_every if command_every is not None
                                        else os.getenv('WILDFIRE_COMMAND_EVERY', '1') or 1))
        self._local = threading.local()
        options.setdefault('name', 'commander')
        options.setdefault('runtime', llm_runtime(self.demo))
        if self.demo:
            options.setdefault('openai_client', DemoClient())
        super().__init__(handlers=[LlmCapability(PLANNER_CAPABILITY, self._prompt, CommandDecision, self._mapper)],
                         **options)

    def _client(self):
        """Cliente OpenAI criado na primeira execução, não na declaração: validar o
        cenário (``./ariadne check``) não exige credencial. Sem retentativas do
        cliente: a política de retry é a do runtime."""
        with self._client_lock:
            if self._openai is None:
                from openai import OpenAI
                self._openai = OpenAI(max_retries=0, timeout=120)
            return self._openai

    def _prompt(self, goal, payload):
        return planner_prompt(self._local.request)

    def _mapper(self, decision):
        return build_response(self._local.request, decision)

    def _without_model(self, task, response, why):
        return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_COMPLETED',
                          trace=task.trace, output=response.to_output(),
                          metadata={'provider': 'none', 'shortcut': why, 'model': self.model})

    def handle(self, task):
        try:
            request = PlannerRequest.from_payload(task.payload)
        except ValueError as error:
            return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_FAILED',
                              trace=task.trace, error_code='ERROR_CODE_INVALID_TASK', error_message=str(error))
        decided = shortcut(request)
        if decided is not None:
            return self._without_model(task, *decided)
        context = restore_integers(request.context)
        last_call = int(context.get('command_round') or 0)
        if (self.command_every > 1 and request.history and last_call
                and request.round - last_call < self.command_every and not news(request)):
            orders = {d: normalize_order(o) for d, o in (context.get('orders') or {}).items()}
            response = plan_from_orders(request, orders, normalize_command(context.get('command')),
                                        summary=f'standing orders from round {last_call}')
            return self._without_model(task, response, 'standing_orders')
        self._local.request = request
        result = super().handle(task)
        return mark_demo(result) if self.demo else result


def make_agent(**options):
    return Commander(**options)
