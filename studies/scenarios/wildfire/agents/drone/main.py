"""Drone bombeiro BDI deliberativo: uma tarefa, um drone, um tique, uma ação.

As crenças nascem do payload (snapshot do mundo, o próprio drone, a ordem do
comandante e as crenças compartilhadas do comando) e das observações feitas
pelos planos. O objetivo é ``act(drone=...)``. Os planos têm condição de
contexto sobre as crenças e custo fixo, que define a precedência:

1. ``stand_down``: drone perdido ou offline, nada a fazer;
2. ``hold_ordered``: o comandante mandou aguardar;
3. ``resupply_here``: está numa base utilizável e precisa de água ou bateria, ou
   nenhum alvo é seguro com a carga atual;
4. ``return_to_base``: a reserva de bateria mandou voltar, a água acabou, o
   comandante mandou voltar/reabastecer, ou não há alvo seguro e recarregar
   amplia o raio de ação;
5. ``attack_target``: há fogo perto do alvo ordenado (``attack``/``protect``);
6. ``guard_target``: ordem ``protect`` sem fogo perto: posiciona-se no alvo;
7. ``attack_nearest``: há fogo alcançável com segurança (células prioritárias
   primeiro);
8. ``hold_position``: reserva.

A reserva de bateria é condição de contexto: o drone nunca escolhe um alvo
de onde não consiga voltar a uma base utilizável. Bases que o comandante
marcou como mortas (``command.disabled_bases``) não contam; essa é a ponte
entre o rádio, lido pelo LLM, e a deliberação do BDI.
"""
from collections.abc import MutableMapping

from ariadne_sdk import BdiAgent, GoalPlan, SearchProblem, TaskResult, achieve, act, observe, uniform_cost_search
from ariadne_sdk.plans import InputError
from studies.scenarios.wildfire.domain.adapters import DRONE_CAPABILITY, normalize_command, normalize_order, restore_integers
from studies.scenarios.wildfire.domain.world import base_cells, chebyshev, neighbors4, passable, usable_base_cells

MARGIN = 1          # células de folga na reserva de bateria
ATTACK_RADIUS = 2   # ordem attack: fogo até esta distância do alvo conta como "o alvo"
PROTECT_RADIUS = 4  # ordem protect: fogo até esta distância da estrutura é a ameaça


# --- percepção: payload vira crenças iniciais -------------------------------

def beliefs_from_task(task):
    payload = restore_integers(dict(task.payload))
    state, drone_id = payload.get('state'), str(payload.get('drone') or '')
    if not isinstance(state, dict) or 'drones' not in state or 'fires' not in state:
        raise InputError('drone task requires payload.state and payload.drone')
    if drone_id not in state['drones']:
        raise InputError(f'unknown drone {drone_id!r} in payload.state')
    order = normalize_order(payload.get('order'))
    command = normalize_command(payload.get('command'))
    me_at = state['drones'][drone_id]['at']
    usable = usable_base_cells(state, disabled=command['disabled_bases'])
    return {'world': WorldView(state), 'me': drone_id, 'drone': dict(state['drones'][drone_id]),
            'objective': order['objective'], 'target': order['target'], 'note': order['note'],
            'disabled_bases': command['disabled_bases'], 'priority_cells': command['priority_cells'],
            'rules': dict(state['rules']),
            # Uma busca em largura por tarefa a partir do drone e de cada base utilizável:
            # todas as perguntas de distância e reserva viram consultas a esses mapas.
            'reach': DistanceMap(distance_map(state, me_at)),
            'base_reach': {bid: DistanceMap(distance_map(state, at)) for at, bid in usable.items()},
            'base_at': {bid: at for at, bid in usable.items()}}


def goal_from_task(task):
    drone_id = task.payload.get('drone') if isinstance(task.payload, dict) else None
    if not drone_id:
        raise InputError('payload.drone is required to form the goal act(drone)')
    return {'name': 'act', 'drone': str(drone_id)}


class WorldView(MutableMapping):
    """Snapshot do mundo como crença: funciona como o dict do estado, mas o
    rastro BDI mostra só um resumo em vez do JSON inteiro (um dict seria
    serializado por completo pelo SDK)."""

    def __init__(self, state):
        self._data = dict(state)

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

    def __str__(self):
        drones = self._data.get('drones', {})
        return (f"world(t={self._data.get('tick')}, fires={len(self._data.get('fires', {}))}, "
                f"ash={len(self._data.get('ash', []))}, "
                f"drones_ok={sum(1 for d in drones.values() if d.get('condition') == 'ok')})")

    __repr__ = __str__


class DistanceMap(WorldView):
    """Distâncias de uma origem a cada célula alcançável; resumo curto no rastro."""

    def __str__(self):
        return f'distances({len(self._data)} cells)'

    __repr__ = __str__


def distance_map(state, origin):
    """Busca em largura a partir de ``origin`` sobre as células sobrevoáveis."""
    found = {origin: 0}
    queue = [origin]
    for current in queue:
        for nxt in neighbors4(state, current):
            if nxt not in found and passable(state, nxt):
                found[nxt] = found[current] + 1
                queue.append(nxt)
    return found


# --- consultas puras sobre as crenças ---------------------------------------

INF = float('inf')


def me(b):
    return b['drone']['at']


def reach(b, c):
    return b['reach'].get(c, INF)


def nearest_base(b, origin=None):
    """(distância, célula, id) da base utilizável mais próxima do drone ou de ``origin``."""
    found = []
    for bid, at in b['base_at'].items():
        d = reach(b, at) if origin is None else b['base_reach'][bid].get(origin, INF)
        if d != INF:
            found.append((d, at, bid))
    return min(found) if found else None


def on_usable_base(b):
    return me(b) in set(b['base_at'].values())


def must_return(b):
    """Reserva: a bateria mal chega à base mais próxima."""
    nearest = nearest_base(b)
    return nearest is not None and b['drone']['battery'] <= nearest[0] + MARGIN


def safe(b, target):
    """Dá para chegar ao lado do alvo, soltar água e ainda voltar a uma base utilizável."""
    battery = b['drone']['battery']
    there = reach(b, target)
    if there == INF:
        return False
    cost = max(there - 1, 0) + 1  # para ao lado da célula e solta a água
    back = nearest_base(b, origin=target)
    if back is None:
        return battery >= cost
    return battery >= cost + back[0] + MARGIN


def crowd(b, c):
    """Quantos outros drones ativos com água estão tão perto de ``c`` quanto este
    (desempate pelo id). É o posto deste drone na fila por aquela célula."""
    mine = (chebyshev(me(b), c), b['me'])
    return sum(1 for other, info in b['world']['drones'].items()
               if other != b['me'] and info.get('condition') == 'ok' and int(info.get('water', 0)) > 0
               and (chebyshev(info['at'], c), other) < mine)


def candidate_fires(b, center=None, radius=None):
    """Focos alcançáveis com segurança, na ordem em que este drone os prefere.

    A ordem base é prioridade, distância e intensidade. Depois, a convenção de
    posto: os drones deliberam em paralelo sem se falar, mas veem as mesmas
    posições; se ``r`` outros drones estão tão perto do melhor foco quanto
    este, este cede e começa pelo ``r``-ésimo seguinte. Dois drones que saem
    da mesma base pegam, assim, focos diferentes sem trocar mensagens.
    """
    priority = set(b['priority_cells'])
    found = []
    for c, intensity in b['world']['fires'].items():
        if center is not None and chebyshev(center, c) > radius:
            continue
        if not safe(b, c):
            continue
        found.append((0 if c in priority else 1, reach(b, c), -int(intensity), c))
    ordered = [item[3] for item in sorted(found)]
    if len(ordered) > 1:
        rank = min(crowd(b, ordered[0]), len(ordered) - 1)
        ordered = ordered[rank:] + ordered[:rank]
    return ordered


def adjacent_fire(b, candidates):
    """Entre os candidatos adjacentes, o que cabe a este drone pela convenção de vizinhança.

    Todos os drones vizinhos (até duas células, com água) correm o mesmo
    algoritmo sobre os mesmos dados: em ordem de id, cada um recebe a melhor
    célula em chamas adjacente a ele que ainda não foi tomada, numa ordenação
    canônica (prioridade, intensidade, célula). Como a ordenação não depende
    de quem olha, dois vizinhos não escolhem a mesma célula.
    """
    allowed = {c for c in candidates if chebyshev(me(b), c) <= 1}
    if not allowed:
        return None
    world, priority = b['world'], set(b['priority_cells'])
    peers = sorted((other for other, info in world['drones'].items()
                    if info.get('condition') == 'ok' and int(info.get('water', 0)) > 0
                    and chebyshev(info['at'], me(b)) <= 2), key=lambda d: (len(d), d))
    taken, assignment = set(), {}
    for peer in peers:
        at = world['drones'][peer]['at']
        cells = sorted((c for c, i in world['fires'].items() if chebyshev(at, c) <= 1 and c not in taken),
                       key=lambda c: (0 if c in priority else 1, -int(world['fires'][c]), c))
        if cells:
            assignment[peer] = cells[0]
            taken.add(cells[0])
    chosen = assignment.get(b['me'])
    return chosen if chosen in allowed else None


def has_water(b):
    return int(b['drone']['water']) > 0


def full_battery(b):
    return int(b['drone']['battery']) >= b['rules']['battery_capacity']


def needs_supplies(b):
    r = b['rules']
    return int(b['drone']['water']) < r['water_capacity'] or int(b['drone']['battery']) <= r['battery_capacity'] // 2


def should_resupply(b):
    """Numa base utilizável: falta água ou metade da bateria, ou nenhum alvo é seguro
    com a carga atual e recarregar amplia o raio de ação."""
    if not on_usable_base(b) or b['objective'] == 'hold':
        return False
    return needs_supplies(b) or (not candidate_fires(b) and not full_battery(b))


def should_return(b):
    """Volta quando a reserva manda, a água acabou, o comandante ordenou, ou não há alvo
    seguro e a bateria não está cheia (recarregar amplia o raio de ação)."""
    if on_usable_base(b) or nearest_base(b) is None:
        return False
    if must_return(b) or not has_water(b) or b['objective'] in ('return', 'resupply'):
        return True
    return not candidate_fires(b) and not full_battery(b)


# --- ações (act) -------------------------------------------------------------

def search_path(world, origin, target):
    """Busca de custo uniforme do SDK na grade, evitando obstáculos."""
    result = uniform_cost_search(SearchProblem(
        initial=origin,
        actions=lambda c: [n for n in neighbors4(world, c) if passable(world, n)],
        transition=lambda c, n: n,
        is_goal=lambda c: c == target,
    ))
    if not result.found:
        raise ValueError(f'no path from {origin} to {target}')
    return {'path_length': len(result.actions), 'expanded': result.expanded, '_path': list(result.actions)}


def decision(b, plan, action, target=None, **extra):
    return {'drone': b['me'], 'action': action, 'target': target, 'plan': plan, 'objective': b['objective'], **extra}


# --- planos para act(drone) --------------------------------------------------

def stand_down(b, g):
    return decision(b, 'stand_down', 'hold', reason=f"drone is {b['drone']['condition']}")


def resupply_here(b, g):
    yield observe(on_base=base_cells(b['world']).get(me(b)))
    why = ('less than full water or half battery' if needs_supplies(b)
           else 'no safe target with the current battery; recharging to extend the reach')
    return decision(b, 'resupply_here', 'resupply', reason=f'on a usable base: {why}')


def return_to_base(b, g):
    nearest = nearest_base(b)
    why = ('ordered to return' if b['objective'] in ('return', 'resupply') else
           'no water left' if not has_water(b) else
           'battery reserve reached' if must_return(b) else 'no safe target; recharging to extend the reach')
    yield observe(base_cell=nearest[1], base=nearest[2], base_distance=nearest[0], why=why)
    yield achieve('reach', target=nearest[1])
    return decision(b, 'return_to_base', 'move', nearest[1], reason=why)


def ctx_attack_target(b, g):
    if b['objective'] not in ('attack', 'protect') or not b['target'] or not has_water(b):
        return False
    radius = ATTACK_RADIUS if b['objective'] == 'attack' else PROTECT_RADIUS
    return bool(candidate_fires(b, center=b['target'], radius=radius))


def attack_target(b, g):
    radius = ATTACK_RADIUS if b['objective'] == 'attack' else PROTECT_RADIUS
    return (yield from attack(b, 'attack_target', candidate_fires(b, center=b['target'], radius=radius)))


def ctx_attack_nearest(b, g):
    return has_water(b) and bool(candidate_fires(b))


def attack_nearest(b, g):
    return (yield from attack(b, 'attack_nearest', candidate_fires(b)))


def attack(b, plan, candidates):
    """Solta água numa célula vizinha que cabe a este drone; senão voa ao melhor candidato."""
    world = b['world']
    fire = adjacent_fire(b, candidates)
    if fire is not None:
        yield observe(target_fire=fire, intensity=world['fires'][fire], priority=fire in set(b['priority_cells']))
        return decision(b, plan, 'drop', fire, reason=f'adjacent to burning cell {fire}')
    remote = [c for c in candidates if chebyshev(me(b), c) > 1]
    if not remote:
        return decision(b, plan, 'hold', None, reason='adjacent cells are covered by closer drones this tick')
    fire = remote[0]
    yield observe(target_fire=fire, intensity=world['fires'][fire], priority=fire in set(b['priority_cells']),
                  contested_by=crowd(b, fire))
    yield achieve('reach', target=fire)
    return decision(b, plan, 'move', fire, reason=f'flying toward burning cell {fire}')


def ctx_guard_target(b, g):
    return (b['objective'] == 'protect' and b['target'] is not None and chebyshev(me(b), b['target']) > 1
            and safe(b, b['target']))


def guard_target(b, g):
    yield observe(guard=b['target'])
    yield achieve('reach', target=b['target'])
    return decision(b, 'guard_target', 'move', b['target'], reason='no fire near the protected cell yet; taking position')


def hold_position(b, g):
    reason = ('ordered to hold' if b['objective'] == 'hold' else 'no safe burning cell within reach'
              if has_water(b) else 'no usable base to resupply')
    return decision(b, 'hold_position', 'hold', reason=reason)


# --- sub-objetivo reach(target) ---------------------------------------------

def ctx_reach(b, g):
    return reach(b, g.params['target']) != INF


def shortest_path_plan(b, g):
    found = yield act(search_path, b['world'], me(b), g.params['target'])
    return {'path': found['_path'], 'length': found['path_length']}


PLANS = [
    GoalPlan('stand_down', stand_down, goal='act', context=lambda b, g: b['drone']['condition'] != 'ok', cost=0),
    GoalPlan('hold_ordered', hold_position, goal='act', context=lambda b, g: b['objective'] == 'hold', cost=1),
    GoalPlan('resupply_here', resupply_here, goal='act', context=lambda b, g: should_resupply(b), cost=2),
    GoalPlan('return_to_base', return_to_base, goal='act', context=lambda b, g: should_return(b), cost=3),
    GoalPlan('attack_target', attack_target, goal='act', context=ctx_attack_target, cost=4),
    GoalPlan('guard_target', guard_target, goal='act', context=ctx_guard_target, cost=5),
    GoalPlan('attack_nearest', attack_nearest, goal='act', context=ctx_attack_nearest, cost=6),
    GoalPlan('hold_position', hold_position, goal='act'),
    GoalPlan('shortest_path', shortest_path_plan, goal='reach', context=ctx_reach),
]


class DroneAgent(BdiAgent):
    """BdiAgent cujo desfecho sem decisão é ``hold``, não uma falha.

    O engine pula os dependentes de um passo FAILED e o laço só mescla a
    saída de workflows COMPLETED: se um drone falhasse, o passo ``world``
    seria pulado e a rodada inteira se perderia. Por isso qualquer problema
    vira ``COMPLETED`` com ``hold`` e o motivo, preservando o rastro.
    """

    def handle(self, task):
        result = super().handle(task)
        if result.status != 'TASK_STATUS_FAILED':
            return result
        drone_id = str(task.payload.get('drone') or '') if isinstance(task.payload, dict) else ''
        metadata = {**result.metadata, 'fallback': True, 'fallback_reason': result.error_message}
        return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_COMPLETED',
                          trace=task.trace, metadata=metadata, bdi=result.bdi,
                          output={'drone': drone_id, 'action': 'hold', 'target': None, 'plan': 'fallback',
                                  'reason': result.error_message, 'error_type': result.metadata.get('error_type', '')})


def make_agent(**options):
    configuration = dict(name='drone', capabilities=[DRONE_CAPABILITY],
                         beliefs=beliefs_from_task, goal=goal_from_task, plans=PLANS, max_cycles=40)
    return DroneAgent(**(configuration | options))
