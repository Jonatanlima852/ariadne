"""Adaptadores do domínio da v2 para o laço de missão (contrato 2.0.0).

Nada do mundo é reescrito: ``initial``, ``execute``, ``incidents`` e
``metrics`` vêm da v2. Aqui ficam apenas as conversões que o laço exige:
objetivo e contexto da missão, snapshots para os agentes, passos de plano
com bindings e a normalização de números que atravessam ``Struct``.
"""
from collections.abc import MutableMapping
from copy import deepcopy

from ariadne_sdk import plan_step
from studies.scenarios.logistics.v2.domain.world import initial
from studies.scenarios.logistics.v2.execution.episode import metrics as _metrics

PLANNER_CAPABILITY = 'mission-planning'
SINGLE_LLM_CAPABILITY = 'logistics-v3-single-llm'
DELIVERY_CAPABILITY = 'logistics-v3-delivery'
EXECUTE_CAPABILITY = 'logistics-v3-execute'
EXECUTE_STEP_ID = 'execute'


def restore_integers(value):
    """``google.protobuf.Struct`` só tem double: 65 volta como 65.0. Desfaz isso."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {key: restore_integers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [restore_integers(item) for item in value]
    return value


def mission_goal(case):
    requests = [order['request'] for order in case['orders']]
    return ('Atender todos os pedidos abaixo no mundo logístico descrito no contexto, '
            'respeitando estoque, capacidade, energia, conexões, prioridade e prazos.\n'
            + '\n'.join(f'- {text}' for text in requests))


def mission_context(case):
    """Contexto inicial: estado autoritativo da v2 e referência do caso.

    A agenda de incidentes NÃO entra aqui; ela é disparada pelo executor.
    """
    return {'case': {'id': case['id'], 'suite': case.get('suite', 'basic')},
            'requests': [order['request'] for order in case['orders']],
            'state': initial(case)}


def metrics(state):
    return restore_integers(_metrics(state))


def pending_orders(state):
    return [oid for oid in state['orders'] if oid not in state['deliveries']]


def all_delivered(state):
    return not pending_orders(state)


def state_snapshot(state):
    """Estado sem o histórico: é o que os agentes de entrega precisam ver."""
    return {key: deepcopy(value) for key, value in state.items() if key != 'history'}


def order_view(state, order_id):
    order = state['orders'][order_id]
    return {'id': order_id, 'destination': order['destination'], 'items': dict(order['items']),
            'priority': order['priority'], 'deadline': order['deadline']}


def delivery_step(order, state, *, vehicle=None, depot=None, step_id=None):
    """Passo ``plan-delivery`` para um agente BDI: snapshot + pedido + sugestões."""
    payload = {'state': state_snapshot(state), 'order': dict(order)}
    if vehicle:
        payload['vehicle'] = vehicle
    if depot:
        payload['depot'] = depot
    return plan_step(step_id or f"deliver-{order['id']}", DELIVERY_CAPABILITY,
                     f"Planejar a entrega do pedido {order['id']}", payload=payload,
                     type='PLAN_DELIVERY', bdi_goal='deliver')


def execute_step(state, case_reference, *, delivery_step_ids=(), proposals=None, step_id=EXECUTE_STEP_ID):
    """Passo final: aplica as propostas (por binding ou inline) no estado autoritativo."""
    payload = {'state': deepcopy(state), 'case': dict(case_reference),
               'order_sequence': list(delivery_step_ids)}
    bindings = [{'source_step_id': sid, 'source_path': 'output', 'target_field': f'proposals.{sid}'}
                for sid in delivery_step_ids]
    if proposals:
        payload['proposals'] = {key: dict(value) for key, value in proposals.items()}
        payload['order_sequence'] = list(delivery_step_ids) + [k for k in proposals if k not in delivery_step_ids]
    return plan_step(step_id, EXECUTE_CAPABILITY, 'Aplicar as propostas no estado autoritativo',
                     payload=payload, depends_on=list(delivery_step_ids), input_bindings=bindings,
                     type='EXECUTE_ROUND')


class WorldView(MutableMapping):
    """Estado do mundo como crença: funciona como o dict da v2, mas o rastro
    BDI mostra só um resumo em vez do JSON inteiro."""

    def __init__(self, state):
        self._data = deepcopy(dict(state))
        # O snapshot enviado aos agentes omite o histórico; as transições da v2 o exigem.
        self._data.setdefault('history', [])

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def snapshot(self):
        return deepcopy(self._data)

    def __str__(self):
        vehicles = self._data.get('vehicles', {})
        return (f"world(t={self._data.get('time', 0)}, vehicles={len(vehicles)}, "
                f"available={sum(1 for v in vehicles.values() if v.get('available', True))}, "
                f"pending={len(pending_orders(self._data))}, blocked={len(self._data.get('blocked', []))})")

    __repr__ = __str__
