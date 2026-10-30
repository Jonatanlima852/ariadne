"""Agente de entrega BDI deliberativo: uma tarefa, um pedido, um ciclo de deliberação.

As crenças nascem do payload (snapshot do mundo, pedido, sugestões do
planejador) e das observações feitas pelos planos. O objetivo é
``deliver(order=...)``. Os planos têm condição de contexto sobre as crenças e
corpos que observam, agem (buscas da v2) e adotam o sub-objetivo ``reach``.
O resultado é uma proposta de ações que o executor aplica; o agente nunca
altera o estado autoritativo.
"""
from ariadne_sdk import BdiAgent, GoalPlan, TaskResult, achieve, act, observe
from ariadne_sdk.plans import InputError
from studies.scenarios.logistics.v2.agents.energy_manager.main import energy_search
from studies.scenarios.logistics.v2.domain.planning import energy_to_charger, path
from studies.scenarios.logistics.v2.domain.world import edge, execute, weight
from studies.scenarios.logistics.v3.domain.adapters import DELIVERY_CAPABILITY, WorldView, pending_orders, restore_integers


class Infeasible(Exception):
    """Inviabilidade do domínio (não é defeito): o plano falha e outro é tentado."""


# --- percepção: payload vira crenças iniciais -------------------------------

def beliefs_from_task(task):
    payload = restore_integers(dict(task.payload))
    if not isinstance(payload.get('state'), dict) or not isinstance(payload.get('order'), dict):
        raise InputError('delivery task requires payload.state and payload.order')
    order = payload['order']
    if not order.get('id'):
        raise InputError('payload.order requires an id')
    return {'world': WorldView(payload['state']), 'order': order['id'],
            'destination': order.get('destination'), 'items': dict(order.get('items') or {}),
            'deadline': order.get('deadline'), 'priority': order.get('priority'),
            'vehicle_hint': payload.get('vehicle') or None, 'depot_hint': payload.get('depot') or None}


def goal_from_task(task):
    order = task.payload.get('order') if isinstance(task.payload, dict) else None
    if not isinstance(order, dict) or not order.get('id'):
        raise InputError('payload.order.id is required to form the goal deliver(order)')
    return {'name': 'deliver', 'order': order['id']}


# --- consultas puras sobre as crenças ---------------------------------------

def holder(world, oid):
    for vid, vehicle in world['vehicles'].items():
        if oid in vehicle['cargo']:
            return vid
    return None


def known_order(world, oid):
    return oid in world['orders'] and oid not in world['deliveries']


def fits(world, vid, oid):
    vehicle = world['vehicles'][vid]
    load = sum(weight(world, other) for other in vehicle['cargo'])
    return load + (0 if oid in vehicle['cargo'] else weight(world, oid)) <= vehicle['capacity']


def available_vehicles(world, oid):
    return [vid for vid, v in world['vehicles'].items() if v['available'] and fits(world, vid, oid)]


def depots_with_stock(world, oid):
    order = world['orders'][oid]
    return [did for did, depot in world['depots'].items()
            if all(depot['stock'].get(sku, 0) >= qty for sku, qty in order['items'].items())]


def leg(world, origin, target):
    """Nós e minutos do caminho aberto mais curto (busca de custo uniforme da v2)."""
    if origin == target:
        return [], 0
    return path(world, origin, target)


def leg_energy(world, origin, nodes):
    total, current = 0, origin
    for node in nodes:
        total += edge(world, current, node)['energy']
        current = node
    return total


def reserve_for(world, oid):
    """Energia que deve sobrar após entregar: alcançar um carregador, se há mais pedidos.

    É a política ``lean-v1`` da v2: sem reserva, um veículo termina a entrega
    sem bateria para a próxima e fica preso.
    """
    if len(pending_orders(world)) <= 1 or not world['charging_locations']:
        return 0
    reserve = energy_to_charger(world, world['orders'][oid]['destination'])
    return 0 if reserve == float('inf') else reserve


def ranked(candidates, vehicle_hint):
    """Sugestão do planejador primeiro; depois menor tempo; depois id estável."""
    return sorted(candidates, key=lambda c: (c['vehicle'] != vehicle_hint, c['minutes'], c['vehicle'], c.get('depot', '')))


def direct_candidates(world, oid, depots, vehicle_hint):
    """Veículo + depósito com rota aberta e bateria suficiente sem recarga."""
    destination = world['orders'][oid]['destination']
    reserve = reserve_for(world, oid)
    found = []
    for vid in available_vehicles(world, oid):
        vehicle = world['vehicles'][vid]
        for did in depots:
            source = world['depots'][did]['location']
            first, m1 = leg(world, vehicle['location'], source)
            second, m2 = leg(world, source, destination)
            if first is None or second is None:
                continue
            energy = leg_energy(world, vehicle['location'], first) + leg_energy(world, source, second)
            if energy + reserve <= vehicle['battery']:
                found.append({'vehicle': vid, 'depot': did, 'minutes': m1 + m2 + 2, 'energy': energy, 'reserve': reserve})
    return ranked(found, vehicle_hint)


def rescue_candidates(world, oid, vehicle_hint):
    """Veículos disponíveis que alcançam o veículo indisponível e depois o destino."""
    carrier = holder(world, oid)
    pickup = world['vehicles'][carrier]['location']
    destination = world['orders'][oid]['destination']
    reserve = reserve_for(world, oid)
    found = []
    for vid in available_vehicles(world, oid):
        if vid == carrier:
            continue
        vehicle = world['vehicles'][vid]
        first, m1 = leg(world, vehicle['location'], pickup)
        second, m2 = leg(world, pickup, destination)
        if first is None or second is None:
            continue
        energy = leg_energy(world, vehicle['location'], first) + leg_energy(world, pickup, second)
        found.append({'vehicle': vid, 'source_vehicle': carrier, 'minutes': m1 + m2 + 2,
                      'energy': energy, 'energy_ok': energy + reserve <= vehicle['battery']})
    return ranked(found, vehicle_hint)


def move(vid, origin, nodes):
    actions, current = [], origin
    for node in nodes:
        actions.append({'type': 'MOVE', 'vehicle': vid, 'from': current, 'to': node})
        current = node
    return actions


# --- ações (act): buscas e simulação reutilizando o domínio da v2 -----------

def simulate(world, actions):
    """Pré-visualiza as ações no snapshot; rejeição vira Infeasible."""
    outcome = execute(world.snapshot(), actions)
    if outcome['reason']:
        raise Infeasible(f"preview rejected: {outcome['reason']}")
    return {'predicted_minutes': outcome['state']['time'], 'preview_ok': True}


def energy_route(world, candidate, oid):
    """Busca da v2 com recarga e desvio; devolve as ações ou levanta Infeasible."""
    # Carga já a bordo: energy_search parte do estágio 1 e nunca usa o LOAD, mas monta a
    # ação de carga mesmo assim; por isso 'depot' precisa existir (None) nesse caso.
    choice = {'order': oid, 'vehicle': candidate['vehicle'],
              'location': candidate['location'], **({'source_vehicle': candidate['source_vehicle']}
                                                   if candidate.get('source_vehicle') else {'depot': candidate.get('depot')})}
    # 'lean-v1' mantém acesso a um carregador após a entrega quando restam pedidos.
    result = energy_search(world, {'route': {'choice': choice, 'actions': []}, 'policy': 'lean-v1'})
    if not result['actions']:
        raise Infeasible(f"no energy-feasible route for {candidate['vehicle']}")
    return {'energy_actions': len(result['actions']), 'route_reason': result['reason'], '_actions': result['actions']}


def proposal(beliefs, goal, name, vid, actions, extra):
    world, oid = beliefs['world'], goal.params['order']
    deadline = world['orders'][oid]['deadline']
    minutes = beliefs.get('predicted_minutes')
    return {'feasible': True, 'order': oid, 'vehicle': vid, 'actions': actions, 'plan': name,
            'predicted_minutes': minutes, 'predicted_on_time': minutes is not None and minutes <= deadline,
            **extra}


# --- planos para deliver(order) ---------------------------------------------

def ctx_continue(b, g):
    w, oid = b['world'], g.params['order']
    carrier = holder(w, oid)
    return (known_order(w, oid) and carrier is not None and w['vehicles'][carrier]['available']
            and leg(w, w['vehicles'][carrier]['location'], w['orders'][oid]['destination'])[0] is not None)


def cost_continue(b, g):
    w, oid = b['world'], g.params['order']
    carrier = holder(w, oid)
    return leg(w, w['vehicles'][carrier]['location'], w['orders'][oid]['destination'])[1] + 1


def continue_with_cargo(b, g):
    w, oid = b['world'], g.params['order']
    carrier = holder(w, oid)
    yield observe(carrier=carrier, cargo_state='loaded')
    route = yield achieve('reach', vehicle=carrier, origin=w['vehicles'][carrier]['location'],
                          location=w['orders'][oid]['destination'])
    actions = route['actions'] + [{'type': 'DELIVER', 'vehicle': carrier, 'order': oid}]
    yield act(simulate, w, actions)
    return proposal(b, g, 'continue_with_cargo', carrier, actions, {'source': 'cargo'})


def ctx_transfer(b, g):
    w, oid = b['world'], g.params['order']
    carrier = holder(w, oid)
    return (known_order(w, oid) and carrier is not None and not w['vehicles'][carrier]['available']
            and any(c['energy_ok'] for c in rescue_candidates(w, oid, b.get('vehicle_hint'))))


def cost_transfer(b, g):
    w, oid = b['world'], g.params['order']
    return min(c['minutes'] for c in rescue_candidates(w, oid, b.get('vehicle_hint')) if c['energy_ok'])


def transfer_from_disabled_vehicle(b, g):
    w, oid = b['world'], g.params['order']
    carrier = holder(w, oid)
    chosen = [c for c in rescue_candidates(w, oid, b.get('vehicle_hint')) if c['energy_ok']][0]
    rescuer, pickup = chosen['vehicle'], w['vehicles'][carrier]['location']
    yield observe(disabled_vehicle=carrier, rescuer=rescuer, pickup=pickup)
    first = yield achieve('reach', vehicle=rescuer, origin=w['vehicles'][rescuer]['location'], location=pickup)
    second = yield achieve('reach', vehicle=rescuer, origin=pickup, location=w['orders'][oid]['destination'])
    actions = (first['actions'] + [{'type': 'TRANSFER', 'vehicle': rescuer, 'order': oid, 'source_vehicle': carrier}]
               + second['actions'] + [{'type': 'DELIVER', 'vehicle': rescuer, 'order': oid}])
    yield act(simulate, w, actions)
    return proposal(b, g, 'transfer_from_disabled_vehicle', rescuer, actions,
                    {'source_vehicle': carrier, 'source': 'transfer'})


def depots_for(b, g, other):
    """Depósitos considerados: o sugerido (ou todos sem sugestão) ou os demais."""
    w, oid = b['world'], g.params['order']
    stocked = depots_with_stock(w, oid)
    hint = b.get('depot_hint')
    if hint is None:
        return [] if other else stocked
    return [d for d in stocked if d != hint] if other else [d for d in stocked if d == hint]


def unloaded(b, g):
    w, oid = b['world'], g.params['order']
    return known_order(w, oid) and holder(w, oid) is None


def make_direct(name, other_depot):
    def context(b, g):
        if not unloaded(b, g):
            return False
        if other_depot and direct_candidates(b['world'], g.params['order'], depots_for(b, g, False), b.get('vehicle_hint')):
            return False
        return bool(direct_candidates(b['world'], g.params['order'], depots_for(b, g, other_depot), b.get('vehicle_hint')))

    def cost(b, g):
        return direct_candidates(b['world'], g.params['order'], depots_for(b, g, other_depot), b.get('vehicle_hint'))[0]['minutes']

    def body(b, g):
        w, oid = b['world'], g.params['order']
        chosen = direct_candidates(w, oid, depots_for(b, g, other_depot), b.get('vehicle_hint'))[0]
        vid, did = chosen['vehicle'], chosen['depot']
        source = w['depots'][did]['location']
        yield observe(vehicle=vid, depot=did, trip_energy=chosen['energy'],
                      hint_followed=(vid == b.get('vehicle_hint')) if b.get('vehicle_hint') else None)
        first = yield achieve('reach', vehicle=vid, origin=w['vehicles'][vid]['location'], location=source)
        second = yield achieve('reach', vehicle=vid, origin=source, location=w['orders'][oid]['destination'])
        actions = (first['actions'] + [{'type': 'LOAD', 'vehicle': vid, 'order': oid, 'depot': did}]
                   + second['actions'] + [{'type': 'DELIVER', 'vehicle': vid, 'order': oid}])
        yield act(simulate, w, actions)
        return proposal(b, g, name, vid, actions, {'depot': did, 'source': 'depot'})

    return GoalPlan(name, body, goal='deliver', context=context, cost=cost)


def ctx_recharge(b, g):
    w, oid = b['world'], g.params['order']
    if not known_order(w, oid) or not w['charging_locations'] or not available_vehicles(w, oid):
        return False
    carrier = holder(w, oid)
    if carrier is not None:
        return w['vehicles'][carrier]['available'] or len(available_vehicles(w, oid)) > 1
    return bool(depots_with_stock(w, oid))


def recharge_then_deliver(b, g):
    w, oid = b['world'], g.params['order']
    hint = b.get('vehicle_hint')
    carrier = holder(w, oid)
    candidates = []
    for vid in available_vehicles(w, oid):
        if carrier is None:
            for did in depots_with_stock(w, oid):
                candidates.append({'vehicle': vid, 'depot': did, 'location': w['depots'][did]['location'], 'minutes': 0})
        elif carrier == vid:
            candidates.append({'vehicle': vid, 'location': w['vehicles'][vid]['location'], 'minutes': 0, 'held': True})
        elif not w['vehicles'][carrier]['available']:
            candidates.append({'vehicle': vid, 'source_vehicle': carrier,
                               'location': w['vehicles'][carrier]['location'], 'minutes': 0})
    yield observe(charging_locations=list(w['charging_locations']), candidates=len(candidates))
    last = None
    for candidate in ranked(candidates, hint):
        try:
            found = yield act(energy_route, w, candidate, oid)
        except Infeasible as error:
            last = error
            continue
        actions = found['_actions']
        if candidate.get('held'):
            # energy_search parte do pedido já carregado: só rota, recarga e entrega.
            actions = [a for a in actions if a['type'] != 'LOAD']
        yield act(simulate, w, actions)
        extra = {'source': 'transfer' if candidate.get('source_vehicle') else 'cargo' if candidate.get('held') else 'depot'}
        if candidate.get('depot'):
            extra['depot'] = candidate['depot']
        if candidate.get('source_vehicle'):
            extra['source_vehicle'] = candidate['source_vehicle']
        return proposal(b, g, 'recharge_then_deliver', candidate['vehicle'], actions, extra)
    raise Infeasible(str(last) if last else 'no candidate vehicle for an energy-aware route')


# --- sub-objetivo reach(vehicle, origin, location) ---------------------------

def ctx_reach(b, g):
    return leg(b['world'], g.params['origin'], g.params['location'])[0] is not None


def search_path(world, origin, target):
    nodes, minutes = leg(world, origin, target)
    return {'route': [origin, *nodes], 'route_minutes': minutes, '_nodes': nodes}


def shortest_open_path(b, g):
    found = yield act(search_path, b['world'], g.params['origin'], g.params['location'])
    return {'actions': move(g.params['vehicle'], g.params['origin'], found['_nodes']), 'minutes': found['route_minutes']}


PLANS = [
    GoalPlan('continue_with_cargo', continue_with_cargo, goal='deliver', context=ctx_continue, cost=cost_continue),
    GoalPlan('transfer_from_disabled_vehicle', transfer_from_disabled_vehicle, goal='deliver',
             context=ctx_transfer, cost=cost_transfer),
    make_direct('direct_delivery', other_depot=False),
    make_direct('load_from_other_depot', other_depot=True),
    GoalPlan('recharge_then_deliver', recharge_then_deliver, goal='deliver', context=ctx_recharge),
    GoalPlan('shortest_open_path', shortest_open_path, goal='reach', context=ctx_reach),
]

class DeliveryAgent(BdiAgent):
    """BdiAgent deliberativo cujo desfecho sem proposta é uma resposta, não uma falha.

    O engine de workflow pula os dependentes de um passo FAILED e o laço só
    mescla a saída de workflows COMPLETED: se uma entrega inviável falhasse a
    tarefa, o passo ``execute`` seria pulado e a rodada inteira se perderia.
    Por isso qualquer deliberação que terminou sem alcançar o objetivo
    (``no_applicable_plan``, falha de domínio ``Infeasible``/``GoalFailure``,
    limite de ciclos ou mesmo um defeito do agente) vira ``COMPLETED`` com
    ``feasible=false``, preservando o rastro, o motivo e ``error_type`` para
    o planejador. Só um payload inválido (sem deliberação) continua FAILED.
    """

    def handle(self, task):
        result = super().handle(task)
        trace = result.metadata.get('bdi_trace') or {}
        if result.status == 'TASK_STATUS_FAILED' and trace:
            order = (task.payload.get('order') or {}).get('id', '')
            metadata = {**result.metadata, 'infeasible': True, 'infeasible_reason': result.error_message}
            return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_COMPLETED',
                              trace=task.trace, metadata=metadata, bdi=result.bdi,
                              output={'feasible': False, 'order': order, 'actions': [],
                                      'reason': result.error_message, 'final_status': trace.get('final_status'),
                                      'error_type': result.metadata.get('error_type', '')})
        return result


def make_agent(**options):
    configuration = dict(name='delivery', capabilities=[DELIVERY_CAPABILITY],
                         beliefs=beliefs_from_task, goal=goal_from_task, plans=PLANS, max_cycles=80)
    return DeliveryAgent(**(configuration | options))
