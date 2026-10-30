"""Planejador LLM da configuração cooperativa (capacidade ``mission-planning``).

O modelo decide o que o laço não sabe decidir: quais pedidos atacar agora (em
paralelo), com que veículo e depósito sugeridos, quando replanejar após
incidentes e quando declarar a missão concluída. A parte determinística do
agente converte essa decisão no ``PlannerResponse`` do contrato: um passo
``plan-delivery`` por pedido (snapshot do estado + pedido + sugestões) e um
passo ``execute`` que depende de todos e recebe as propostas por bindings.
"""
import json
import threading
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ariadne_sdk import LlmAgent, PlannerRequest, PlannerResponse, Prompt, TaskResult
from ariadne_sdk.llm import LlmCapability
from studies.scenarios.logistics.v2.domain.world import RULES
from studies.scenarios.logistics.v3.agents.common import DemoClient, demo_enabled, llm_runtime, mark_demo
from studies.scenarios.logistics.v3.domain.adapters import (
    DELIVERY_CAPABILITY, EXECUTE_STEP_ID, PLANNER_CAPABILITY, all_delivered, delivery_step,
    execute_step, metrics, pending_orders, restore_integers, state_snapshot,
)

MAX_DELIVERY_STEPS = 9  # o validador do orquestrador aceita 10 passos; um é o execute


class Item(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sku: str
    quantity: int


class Assignment(BaseModel):
    """Um pedido a atacar nesta rodada, como o planejador o entendeu."""
    model_config = ConfigDict(extra='forbid')
    order_id: str
    destination: str
    items: list[Item]
    priority: int
    deadline: int
    vehicle: str | None = Field(description='Suggested vehicle id or null')
    depot: str | None = Field(description='Suggested depot id or null')
    rationale: str


class CooperativePlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['PLAN', 'DONE', 'ABORT']
    summary: str = Field(description='One sentence about the decision')
    reason: str = Field(description='Required for ABORT, otherwise empty')
    assignments: list[Assignment] = Field(description='For PLAN: orders to attack now, in parallel; otherwise empty')


INSTRUCTION = (
    'You are the mission planner of a logistics team. You do NOT emit vehicle actions. '
    'Each round you decide which outstanding orders to attack NOW, in parallel, one per '
    'assignment. Each assignment is delegated to a deliberative delivery agent that plans a '
    'full action sequence (route, load/transfer, recharge, deliver) for that single order from '
    'the current state; then a deterministic executor applies all proposals sequentially in '
    'the order you list them. Proposals share the same vehicles and stock, so assign DISTINCT '
    'vehicles and do not exceed the number of available vehicles nor the number of delivery '
    'agents. Suggested vehicle/depot are preferences; agents may deviate when infeasible. '
    'Use the report of the previous round: delivered orders, rejected actions, infeasible '
    'reports (with reason) and incidents (road blocks, vehicle breakdowns). After an incident '
    'replan: reassign stranded cargo to another vehicle (transfer), route around blocks. '
    'Prioritize higher priority and earlier deadlines. Interpret the natural-language requests '
    'yourself: order_id, destination, items (sku/quantity), priority and deadline must match them. '
    'Answer DONE when all orders are delivered, or when every outstanding order has been reported '
    'infeasible and nothing changed. Answer ABORT only if the data is inconsistent.'
)


def last_round_report(request):
    """Resumo da rodada anterior a partir do histórico do contrato."""
    if not request.history:
        return None
    last = request.history[-1]
    report = {'round': last.get('round'), 'action': last.get('action'), 'workflow_status': last.get('status'),
              'planner_summary': last.get('planner_summary', ''), 'deliveries': [], 'infeasible': [],
              'rejected': [], 'incidents': [], 'skipped': [], 'accepted_actions': 0}
    for item in last.get('step_results', []):
        result = item.get('result') or {}
        output = result.get('output') or {}
        status = item.get('status', '')
        if item.get('step_id') == EXECUTE_STEP_ID:
            for applied in output.get('applied', []):
                report['accepted_actions'] += int(applied.get('accepted') or 0)
                if applied.get('delivered'):
                    report['deliveries'].append(applied['order'])
                if applied.get('rejected'):
                    report['rejected'].append({'order': applied['order'], 'reason': applied.get('reason')})
                if applied.get('status') == 'skipped':
                    report['skipped'].append({'order': applied['order'], 'reason': applied.get('reason')})
            report['incidents'] = output.get('incidents', [])
            if not status.endswith('COMPLETED'):
                report['execute_failure'] = (result.get('error') or {}).get('message', status)
        elif 'feasible' in output and not output['feasible']:
            report['infeasible'].append({'order': output.get('order'), 'reason': output.get('reason'),
                                         'agent': result.get('agent_id')})
        elif not status.endswith('COMPLETED'):
            report['infeasible'].append({'step': item.get('step_id'), 'status': status,
                                         'reason': (result.get('error') or {}).get('message', '')})
    return report


def rounds_since_progress(request):
    """Relatórios das rodadas finais sem entrega, incidente ou ação aceita."""
    trailing = []
    for index in range(len(request.history), 0, -1):
        partial = PlannerRequest(history=request.history[:index])
        report = last_round_report(partial)
        if report is None or report['action'] != 'PLANNER_ACTION_PLAN' or 'execute_failure' in report:
            break
        if report['deliveries'] or report['incidents'] or report['accepted_actions']:
            break
        trailing.append(report)
    return trailing


def infeasible_since_progress(request):
    orders = []
    for report in rounds_since_progress(request):
        for item in report['infeasible']:
            if item.get('order') and item['order'] not in orders:
                orders.append(item['order'])
    return orders


def planner_view(request):
    """O que o modelo lê: estado compacto, pedidos e o relatório da rodada anterior."""
    state = restore_integers(request.context.get('state') or {})
    capabilities = {c.get('capability_id'): c.get('agent_count', 0) for c in request.available_capabilities}
    orders = {}
    for oid, order in state.get('orders', {}).items():
        delivery = state.get('deliveries', {}).get(oid)
        held = next((vid for vid, v in state['vehicles'].items() if oid in v.get('cargo', [])), None)
        orders[oid] = {'destination': order['destination'], 'items': order['items'], 'priority': order['priority'],
                       'deadline': order['deadline'], 'delivered': delivery is not None,
                       'delivered_at': delivery['time'] if delivery else None, 'held_by': held}
    return {'round': request.round, 'max_rounds': request.limits.get('max_rounds'),
            'max_parallel': request.limits.get('max_parallel'),
            'delivery_agents_alive': capabilities.get(DELIVERY_CAPABILITY, 0),
            'requests': request.context.get('requests', []),
            'world': {k: v for k, v in state_snapshot(state).items() if k not in ('orders', 'deliveries')},
            'orders': orders, 'pending_orders': pending_orders(state) if state else [],
            'last_round': last_round_report(request),
            'infeasible_since_last_progress': infeasible_since_progress(request),
            'previous_rounds': [{'round': r.get('round'), 'summary': r.get('planner_summary', '')}
                                for r in request.history[:-1]]}


def build_response(request, decision):
    """Decisão validada do modelo -> PlannerResponse do contrato."""
    state = restore_integers(request.context['state'])
    pending = pending_orders(state)
    if decision.action == 'ABORT':
        return PlannerResponse.abort(decision.reason or decision.summary, summary=decision.summary).to_output()
    if decision.action == 'DONE':
        return done_response(state, decision.summary).to_output()
    warnings, steps, ids, seen = [], [], [], set()
    for assignment in decision.assignments:
        oid = assignment.order_id
        if oid not in state['orders'] or oid not in pending or oid in seen:
            warnings.append(f'ignored assignment for unknown, delivered or repeated order {oid}')
            continue
        if len(ids) >= MAX_DELIVERY_STEPS:
            warnings.append(f'assignment for {oid} deferred: at most {MAX_DELIVERY_STEPS} delivery steps per round')
            continue
        seen.add(oid)
        order = {'id': oid, 'destination': assignment.destination,
                 'items': {item.sku: item.quantity for item in assignment.items},
                 'priority': assignment.priority, 'deadline': assignment.deadline}
        step = delivery_step(order, state, vehicle=assignment.vehicle, depot=assignment.depot)
        steps.append(step)
        ids.append(step['step_id'])
    if not steps:
        return done_response(state, decision.summary + ' (no valid assignment; ' + '; '.join(warnings) + ')').to_output()
    steps.append(execute_step(state, request.context['case'], delivery_step_ids=ids))
    plan = {'round': request.round, 'assignments': [a.model_dump() for a in decision.assignments], 'warnings': warnings}
    return PlannerResponse.make_plan(steps, final_step_id=EXECUTE_STEP_ID, workflow_id=f'logistics-v3-round-{request.round}',
                                     summary=decision.summary, context_update={'last_plan': plan}).to_output()


def done_response(state, summary):
    return PlannerResponse.done({'metrics': metrics(state), 'delivered': sorted(state['deliveries']),
                                 'pending': pending_orders(state), 'summary': summary}, summary=summary)


def shortcut(request):
    """Decisões que não exigem o modelo: tudo entregue, ou nada mudou e tudo é inviável."""
    state = restore_integers(request.context.get('state') or {})
    if not state:
        return None
    if all_delivered(state):
        return done_response(state, 'all orders delivered'), 'all_delivered'
    trailing = rounds_since_progress(request)
    if trailing and not any(report['rejected'] for report in trailing):
        infeasible = set(infeasible_since_progress(request))
        if infeasible and set(pending_orders(state)) <= infeasible:
            return done_response(state, 'no feasible work remains: every outstanding order was reported infeasible'), 'no_feasible_work'
    return None


def substitute_plan(view):
    """Política fixa para a demonstração sem credenciais (não é um benchmark)."""
    pending = view['pending_orders']
    if not pending:
        return {'action': 'DONE', 'summary': 'demo: nothing pending', 'reason': '', 'assignments': []}
    orders = view['orders']
    world = view['world']
    pending = sorted(pending, key=lambda oid: (-orders[oid]['priority'], orders[oid]['deadline'], oid))
    vehicles = sorted(vid for vid, v in world['vehicles'].items() if v.get('available', True))
    infeasible = set(view.get('infeasible_since_last_progress') or [])
    pending = [oid for oid in pending if oid not in infeasible] or pending
    limit = max(1, min(len(vehicles) or 1, view.get('delivery_agents_alive') or 1, view.get('max_parallel') or 1))
    assignments = []
    for index, oid in enumerate(pending[:limit]):
        order = orders[oid]
        held = order.get('held_by')
        assignments.append({'order_id': oid, 'destination': order['destination'],
                            'items': [{'sku': k, 'quantity': q} for k, q in order['items'].items()],
                            'priority': order['priority'], 'deadline': order['deadline'],
                            'vehicle': held if held in vehicles else (vehicles[index % len(vehicles)] if vehicles else None),
                            'depot': None, 'rationale': 'deterministic substitute: priority, deadline, distinct vehicles'})
    return {'action': 'PLAN', 'summary': f'demo: attack {len(assignments)} order(s) in parallel', 'reason': '',
            'assignments': assignments}


class CooperativePlanner(LlmAgent):
    runtime_name = 'logistics-v3-llm'

    def __init__(self, demo=None, **options):
        self.demo = demo_enabled(demo)
        self._local = threading.local()
        options.setdefault('name', 'planner')
        options.setdefault('runtime', llm_runtime(self.demo))
        if self.demo:
            options.setdefault('openai_client', DemoClient())
        elif options.get('openai_client') is None:
            from openai import OpenAI
            options['openai_client'] = OpenAI(max_retries=0, timeout=90)
        super().__init__(handlers=[LlmCapability(PLANNER_CAPABILITY, self._prompt, CooperativePlan, self._mapper)],
                         **options)

    def _prompt(self, goal, payload):
        request = self._local.request
        return Prompt(system=f'ROLE=CooperativePlanner\n{INSTRUCTION}\n{RULES}',
                      user=json.dumps(planner_view(request), ensure_ascii=False))

    def _mapper(self, decision):
        return build_response(self._local.request, decision)

    def handle(self, task):
        try:
            request = PlannerRequest.from_payload(task.payload)
        except ValueError as error:
            return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_FAILED',
                              trace=task.trace, error_code='ERROR_CODE_INVALID_TASK', error_message=str(error))
        decided = shortcut(request)
        if decided is not None:
            response, why = decided
            return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_COMPLETED',
                              trace=task.trace, output=response.to_output(),
                              metadata={'provider': 'none', 'shortcut': why, 'model': self.model})
        self._local.request = request
        result = super().handle(task)
        return mark_demo(result) if self.demo else result


def make_agent(**options):
    return CooperativePlanner(**options)
