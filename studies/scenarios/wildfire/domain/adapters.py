"""Adaptadores do mundo ao laço de missão (contrato 2.0.0).

Aqui ficam só as conversões que o laço exige: objetivo e contexto da missão,
snapshot para os drones, passos de plano com bindings, a vista que os dois
planejadores LLM leem e a normalização de números que atravessam ``Struct``.
O mundo em si está em ``world.py``.
"""
from copy import deepcopy

from ariadne_sdk import plan_step
from studies.scenarios.wildfire.domain.cases import case_reference
from studies.scenarios.wildfire.domain.world import initial_state, normalize_cell

PLANNER_CAPABILITY = 'mission-planning'
SINGLE_LLM_CAPABILITY = 'wildfire-single-llm'
DRONE_CAPABILITY = 'wildfire-drone'
WORLD_CAPABILITY = 'wildfire-world'
WORLD_STEP_ID = 'world'
MAX_DRONE_STEPS = 9  # o validador do orquestrador aceita 10 passos; um é o mundo
OBJECTIVES = ('auto', 'attack', 'protect', 'resupply', 'return', 'hold')
EMPTY_COMMAND = {'disabled_bases': [], 'priority_cells': [], 'hazards': ''}


def restore_integers(value):
    """``google.protobuf.Struct`` só tem double: 30 volta como 30.0. Desfaz isso."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {key: restore_integers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [restore_integers(item) for item in value]
    return value


def drone_step_id(drone_id):
    return f'drone-{drone_id}'


def mission_goal(case):
    return (f"Conter o incêndio florestal '{case['title']}' numa grade {case['width']}x{case['height']} com "
            f"{case['drones']} drones em {case['horizon']} tiques: apagar os focos, minimizar as células que viram "
            'cinzas, proteger estruturas, não perder drones e obedecer ao rádio.')


def mission_context(case):
    """Contexto inicial: estado autoritativo, referência do caso e crenças vazias do comando.

    A agenda de eventos NÃO entra aqui; o executor a dispara a partir do caso.
    """
    return {'case': case_reference(case), 'state': initial_state(case),
            'command': dict(EMPTY_COMMAND), 'orders': {}}


def state_snapshot(state):
    """O que um drone precisa ver: sem rádio nem contadores (bytes por passo)."""
    return {key: deepcopy(value) for key, value in state.items() if key not in ('radio', 'counters')}


def drone_order(drone_id):
    """``d2`` antes de ``d10``: mapas protobuf não preservam a ordem de inserção."""
    digits = ''.join(ch for ch in drone_id if ch.isdigit())
    return (int(digits) if digits else 0, drone_id)


def active_drones(state):
    return sorted((drone_id for drone_id, drone in state['drones'].items() if drone.get('condition') == 'ok'),
                  key=drone_order)


def normalize_order(order):
    """Ordem do comandante para um drone, validada e com células normalizadas."""
    order = dict(order or {})
    objective = str(order.get('objective') or 'auto').lower()
    if objective not in OBJECTIVES:
        objective = 'auto'
    target = order.get('target')
    try:
        target = normalize_cell(target) if target not in (None, '', 'null') else None
    except ValueError:
        target = None
    return {'objective': objective, 'target': target, 'note': str(order.get('note') or '')[:200]}


def normalize_command(command):
    command = dict(command or {})
    cells = []
    for item in command.get('priority_cells') or []:
        try:
            cells.append(normalize_cell(item))
        except ValueError:
            continue
    return {'disabled_bases': [str(item) for item in command.get('disabled_bases') or []],
            'priority_cells': cells, 'hazards': str(command.get('hazards') or '')[:300]}


def drone_step(state, drone_id, order, command):
    """Passo ``drone-<id>`` para um agente BDI: snapshot + drone + ordem + crenças do comando."""
    payload = {'state': state_snapshot(state), 'drone': drone_id, 'order': normalize_order(order),
               'command': normalize_command(command)}
    goal = f"Decidir a ação do drone {drone_id} no tique {state['tick']}"
    return plan_step(drone_step_id(drone_id), DRONE_CAPABILITY, goal, payload=payload,
                     type='DRONE_DECISION', bdi_goal='act')


def world_step(state, case_ref, *, drone_step_ids=(), actions=None, step_id=WORLD_STEP_ID):
    """Passo final: aplica as ações (por binding ou inline) e avança o mundo um tique."""
    payload = {'state': deepcopy(state), 'case': dict(case_ref), 'order_sequence': list(drone_step_ids)}
    bindings = [{'source_step_id': sid, 'source_path': 'output', 'target_field': f'actions.{sid}'}
                for sid in drone_step_ids]
    if actions is not None:
        payload['actions'] = {'pilot': {'actions': list(actions)}}
        payload['order_sequence'] = ['pilot']
    return plan_step(step_id, WORLD_CAPABILITY, f"Aplicar as ações e avançar o mundo para o tique {state['tick'] + 1}",
                     payload=payload, depends_on=list(drone_step_ids), input_bindings=bindings, type='WORLD_TICK')


# --- o que os planejadores leem --------------------------------------------

def last_round_report(request):
    """Relatório da rodada anterior lido do histórico do contrato: ações, rádio, perdas."""
    if not request.history:
        return None
    last = request.history[-1]
    report = {'round': last.get('round'), 'workflow_status': last.get('status'),
              'planner_summary': last.get('planner_summary', ''), 'applied': [], 'rejected': [], 'idle': [],
              'lost_drones': [], 'ignited': 0, 'new_ash': 0, 'radio': [], 'failures': []}
    for item in last.get('step_results', []):
        result = item.get('result') or {}
        output = result.get('output') or {}
        status = item.get('status', '')
        if item.get('step_id') == WORLD_STEP_ID:
            for entry in output.get('applied', []):
                bucket = {'applied': 'applied', 'rejected': 'rejected', 'idle': 'idle'}.get(entry.get('status'))
                if bucket:
                    report[bucket].append({k: v for k, v in entry.items() if k != 'status'})
            report['lost_drones'] = list(output.get('lost') or [])
            fire = output.get('fire') or {}
            report['ignited'] = int(fire.get('ignited') or 0)
            report['new_ash'] = int(fire.get('ash') or 0)
            report['radio'] = [event.get('radio', '') for event in output.get('events', []) if event.get('radio')]
            if not status.endswith('COMPLETED'):
                report['failures'].append({'step': WORLD_STEP_ID, 'status': status,
                                           'reason': (result.get('error') or {}).get('message', '')})
        elif not status.endswith('COMPLETED'):
            report['failures'].append({'step': item.get('step_id'), 'status': status,
                                       'reason': (result.get('error') or {}).get('message', '')})
    return report


def planner_view(request, *, with_command=False):
    """Vista compacta e idêntica para o comandante e para o piloto.

    Nunca inclui ``metrics`` nem efeitos estruturados dos eventos: fatos de
    rádio chegam só como texto, em ``radio``.
    """
    context = restore_integers(request.context)
    state = context.get('state') or {}
    drones = {}
    for drone_id, drone in state.get('drones', {}).items():
        base = next((bid for bid, b in state['bases'].items() if b['at'] == drone['at']), None)
        drones[drone_id] = {**drone, 'on_base': base}
    view = {'tick': state.get('tick'), 'horizon': state.get('horizon'),
            'remaining_ticks': max(int(state.get('horizon', 0)) - int(state.get('tick', 0)), 0),
            'grid': {'width': state.get('width'), 'height': state.get('height')}, 'wind': state.get('wind'),
            'rules': state.get('rules'),
            'fires': [{'cell': c, 'intensity': i} for c, i in sorted(state.get('fires', {}).items())],
            'ash': list(state.get('ash', [])), 'obstacles': list(state.get('obstacles', [])),
            'structures': state.get('structures', {}), 'bases': state.get('bases', {}), 'drones': drones,
            'radio': list(state.get('radio', [])), 'last_round': last_round_report(request),
            'previous_rounds': [{'round': r.get('round'), 'summary': r.get('planner_summary', '')}
                                for r in request.history[:-1]]}
    if with_command:
        view['previous_command'] = context.get('command') or dict(EMPTY_COMMAND)
        view['previous_orders'] = context.get('orders') or {}
    return view
