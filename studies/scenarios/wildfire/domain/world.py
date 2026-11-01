"""Mundo do incêndio florestal: grade discreta, fogo, vento, drones, bases e rádio.

Tudo aqui é determinístico e puro: ``step`` recebe um estado e uma lista de
ações e devolve um estado novo, sem tocar no original. O executor da missão,
os drones BDI e a análise usam as mesmas funções; não há oráculo separado.

Convenções:

- células são textos ``"x,y"``; x cresce para leste (direita), y para sul
  (baixo); ``"0,0"`` é o canto noroeste;
- uma rodada da missão é um tique; a ordem dentro do tique é ações dos
  drones, drones perdidos, avanço do fogo, incremento do tique, eventos;
- alguns fatos só existem no rádio (base fora de serviço, estrutura a
  proteger). O estado não os reflete; ``truth_at`` os recompõe da agenda do
  caso, e só o executor e a análise a consultam.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy

DIRECTIONS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
LATERAL = {'N': ('E', 'W'), 'S': ('E', 'W'), 'E': ('N', 'S'), 'W': ('N', 'S')}
MAX_INTENSITY = 3
ACTIONS = ('move', 'drop', 'resupply', 'hold')
DEFAULT_RULES = {'speed': 4, 'battery_capacity': 40, 'water_capacity': 4, 'drop_power': 3, 'recharge': 20}


# --- células ---------------------------------------------------------------

def cell(x, y) -> str:
    return f'{int(x)},{int(y)}'


def coords(value) -> tuple[int, int]:
    """``"x,y"`` (ou ``[x, y]``) para inteiros; levanta ValueError se malformado."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    if isinstance(value, str):
        parts = value.replace('(', '').replace(')', '').replace(' ', '').split(',')
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    raise ValueError(f'cell must be "x,y": {value!r}')


def normalize_cell(value) -> str:
    return cell(*coords(value))


def in_bounds(state, xy) -> bool:
    x, y = xy
    return 0 <= x < int(state['width']) and 0 <= y < int(state['height'])


def manhattan(a, b) -> int:
    (ax, ay), (bx, by) = coords(a), coords(b)
    return abs(ax - bx) + abs(ay - by)


def chebyshev(a, b) -> int:
    (ax, ay), (bx, by) = coords(a), coords(b)
    return max(abs(ax - bx), abs(ay - by))


def neighbor(c, direction) -> str:
    x, y = coords(c)
    dx, dy = DIRECTIONS[direction]
    return cell(x + dx, y + dy)


def neighbors4(state, c) -> list[str]:
    return [neighbor(c, d) for d in ('N', 'E', 'S', 'W') if in_bounds(state, coords(neighbor(c, d)))]


def base_cells(state) -> dict[str, str]:
    return {base['at']: bid for bid, base in state['bases'].items()}


def passable(state, c) -> bool:
    """Um drone pode sobrevoar tudo, exceto obstáculos e o exterior da grade."""
    return in_bounds(state, coords(c)) and c not in set(state['obstacles'])


def flammable(state, c) -> bool:
    return (in_bounds(state, coords(c)) and c not in set(state['obstacles']) and c not in set(state['ash'])
            and c not in base_cells(state) and c not in state['fires'])


def shortest_path(state, origin, target) -> list[str] | None:
    """Busca em largura na grade (4 vizinhos) evitando obstáculos.

    Devolve as células depois da origem até o alvo, inclusive; ``[]`` quando
    origem e alvo coincidem; ``None`` quando não há caminho.
    """
    origin, target = normalize_cell(origin), normalize_cell(target)
    if not passable(state, target):
        return None
    if origin == target:
        return []
    previous = {origin: None}
    queue = deque([origin])
    while queue:
        current = queue.popleft()
        for nxt in neighbors4(state, current):
            if nxt in previous or not passable(state, nxt):
                continue
            previous[nxt] = current
            if nxt == target:
                path, node = [], nxt
                while node != origin:
                    path.append(node)
                    node = previous[node]
                return path[::-1]
            queue.append(nxt)
    return None


def distance(state, origin, target) -> float:
    path = shortest_path(state, origin, target)
    return float('inf') if path is None else len(path)


# --- estado inicial e verdade oculta ---------------------------------------

def initial_state(case) -> dict:
    """Estado autoritativo no tique 0, a partir da descrição do caso."""
    rules = {**DEFAULT_RULES, **dict(case.get('rules') or {})}
    bases = {bid: {'at': normalize_cell(at), 'active': True} for bid, at in case['bases'].items()}
    order = list(bases)
    drones = {}
    for index in range(int(case['drones'])):
        base = bases[order[index % len(order)]]
        drones[f'd{index + 1}'] = {'at': base['at'], 'battery': rules['battery_capacity'],
                                   'water': rules['water_capacity'], 'condition': 'ok'}
    fires = {normalize_cell(c): int(i) for c, i in case['fires'].items()}
    structures = {normalize_cell(c): {'name': name, 'condition': 'intact'} for c, name in (case.get('structures') or {}).items()}
    for c in structures:
        if c in fires:
            structures[c]['condition'] = 'burning'
    return {'tick': 0, 'width': int(case['width']), 'height': int(case['height']), 'horizon': int(case['horizon']),
            'wind': {'toward': case['wind']['toward'], 'speed': int(case['wind']['speed'])},
            'fires': fires, 'ash': [], 'obstacles': sorted(normalize_cell(c) for c in case.get('obstacles') or []),
            'structures': structures, 'bases': bases, 'drones': drones,
            'radio': [{'tick': 0, 'text': case['briefing']}] if case.get('briefing') else [],
            'rules': rules,
            'counters': {'accepted': 0, 'rejected': 0, 'idle': 0, 'drops': 0, 'extinguished': 0, 'moved_cells': 0}}


def truth_at(case, tick) -> dict:
    """Fatos anunciados só pelo rádio até ``tick``: bases mortas e estruturas ocultas."""
    disabled, hidden = [], {}
    for event in case.get('events') or []:
        if int(event['tick']) > int(tick):
            continue
        effects = event.get('effects') or {}
        disabled.extend(effects.get('disable_bases') or [])
        hidden.update({normalize_cell(c): name for c, name in (effects.get('hidden_structures') or {}).items()})
    return {'disabled_bases': sorted(set(disabled)), 'hidden_structures': hidden}


def usable_base_cells(state, truth=None, disabled=()) -> dict[str, str]:
    """Células de base onde reabastecer: ativas no estado e fora das listas de mortas."""
    dead = set(disabled) | set((truth or {}).get('disabled_bases') or [])
    return {base['at']: bid for bid, base in state['bases'].items() if base.get('active', True) and bid not in dead}


# --- ações dos drones ------------------------------------------------------

def _reject(entry, reason):
    return {**entry, 'status': 'rejected', 'reason': reason}


def apply_action(state, truth, action) -> dict:
    """Aplica uma ação no estado (mutação) e devolve o registro dela."""
    drone_id = str(action.get('drone', ''))
    kind = str(action.get('action', '')).lower()
    entry = {'drone': drone_id, 'action': kind, 'target': action.get('target')}
    drone = state['drones'].get(drone_id)
    if drone is None:
        return _reject(entry, f'unknown drone {drone_id}')
    if drone['condition'] != 'ok':
        return _reject(entry, f'drone {drone_id} is {drone["condition"]} and ignores orders')
    if kind not in ACTIONS:
        return _reject(entry, f'unknown action {kind!r}; use move, drop, resupply or hold')
    rules = state['rules']
    if kind == 'hold':
        return {**entry, 'status': 'applied'}
    if kind == 'resupply':
        usable = usable_base_cells(state, truth)
        here = base_cells(state).get(drone['at'])
        if here is None:
            return _reject(entry, f'{drone_id} is not on a base cell')
        if drone['at'] not in usable:
            return _reject(entry, f'base {here} is out of service (announced on the radio)')
        drone['water'] = rules['water_capacity']
        drone['battery'] = min(rules['battery_capacity'], drone['battery'] + rules['recharge'])
        return {**entry, 'status': 'applied', 'base': here, 'battery': drone['battery'], 'water': drone['water']}
    try:
        target = normalize_cell(action.get('target'))
    except ValueError:
        return _reject(entry, f'{kind} requires target "x,y"')
    entry['target'] = target
    if kind == 'drop':
        if drone['water'] <= 0:
            return _reject(entry, f'{drone_id} has no water')
        if drone['battery'] <= 0:
            return _reject(entry, f'{drone_id} has no battery')
        if chebyshev(drone['at'], target) > 1:
            return _reject(entry, f'{target} is not adjacent to {drone_id} at {drone["at"]}')
        if target not in state['fires']:
            return _reject(entry, f'no fire at {target}')
        drone['water'] -= 1
        drone['battery'] -= 1
        state['counters']['drops'] += 1
        remaining = state['fires'][target] - rules['drop_power']
        if remaining <= 0:
            del state['fires'][target]
            state['counters']['extinguished'] += 1
            if target in state['structures'] and state['structures'][target]['condition'] != 'burned':
                state['structures'][target]['condition'] = 'intact'
        else:
            state['fires'][target] = remaining
        return {**entry, 'status': 'applied', 'intensity_after': max(remaining, 0), 'extinguished': remaining <= 0}
    # move
    if drone['battery'] <= 0:
        return _reject(entry, f'{drone_id} has no battery')
    if target == drone['at']:
        return _reject(entry, f'{drone_id} is already at {target}')
    path = shortest_path(state, drone['at'], target)
    if path is None:
        return _reject(entry, f'no path from {drone["at"]} to {target} (out of the grid or obstacle)')
    steps = min(rules['speed'], drone['battery'], len(path))
    drone['at'] = path[steps - 1]
    drone['battery'] -= steps
    state['counters']['moved_cells'] += steps
    return {**entry, 'status': 'applied', 'moved_to': drone['at'], 'cells': steps,
            'arrived': drone['at'] == target, 'battery': drone['battery']}


def apply_actions(state, truth, actions) -> list[dict]:
    """Uma ação por drone; repetições são rejeitadas; drones sem ação ficam ociosos."""
    report, seen = [], set()
    for action in actions or []:
        if not isinstance(action, dict):
            report.append({'drone': '', 'action': '', 'status': 'rejected', 'reason': 'action must be an object'})
            continue
        drone_id = str(action.get('drone', ''))
        if drone_id in seen:
            report.append(_reject({'drone': drone_id, 'action': action.get('action'), 'target': action.get('target')},
                                  f'second action for {drone_id} in the same tick'))
            continue
        seen.add(drone_id)
        report.append(apply_action(state, truth, action))
    for drone_id, drone in state['drones'].items():
        if drone_id not in seen and drone['condition'] == 'ok':
            report.append({'drone': drone_id, 'action': 'hold', 'target': None, 'status': 'idle',
                           'reason': 'no action for this drone'})
    for entry in report:
        state['counters'][entry['status'] if entry['status'] in ('rejected', 'idle') else 'accepted'] += 1
    return report


def ground_lost_drones(state, truth) -> list[str]:
    usable = usable_base_cells(state, truth)
    lost = []
    for drone_id, drone in state['drones'].items():
        if drone['condition'] == 'ok' and drone['battery'] <= 0 and drone['at'] not in usable:
            drone['condition'] = 'lost'
            lost.append(drone_id)
    return lost


# --- fogo ------------------------------------------------------------------

def spread_thresholds(wind) -> dict[str, int]:
    """Intensidade mínima para acender cada vizinho, conforme o vento."""
    toward, speed = wind['toward'], int(wind['speed'])
    laterals = LATERAL[toward]
    if speed <= 0:
        return {d: MAX_INTENSITY for d in DIRECTIONS}
    if speed == 1:
        return {toward: 2, laterals[0]: 3, laterals[1]: 3, OPPOSITE[toward]: MAX_INTENSITY + 1}
    return {toward: 1, laterals[0]: 3, laterals[1]: 3, OPPOSITE[toward]: MAX_INTENSITY + 1}


def advance_fire(state) -> dict:
    """Um tique de fogo: cresce, vira cinzas e se espalha. Mutação do estado."""
    thresholds = spread_thresholds(state['wind'])
    ignite, ashed, grown = set(), [], {}
    for c, intensity in sorted(state['fires'].items()):
        for direction, needed in thresholds.items():
            if intensity >= needed:
                nxt = neighbor(c, direction)
                if flammable(state, nxt):
                    ignite.add(nxt)
        if intensity >= MAX_INTENSITY:
            ashed.append(c)
        else:
            grown[c] = intensity + 1
    for c in sorted(ignite):
        grown.setdefault(c, 1)
    state['fires'] = grown
    burned = []
    for c in ashed:
        state['ash'].append(c)
        if c in state['structures']:
            state['structures'][c]['condition'] = 'burned'
            burned.append(c)
    state['ash'] = sorted(set(state['ash']))
    for c, structure in state['structures'].items():
        if structure['condition'] != 'burned':
            structure['condition'] = 'burning' if c in state['fires'] else 'intact'
    return {'ignited': sorted(ignite), 'ash': ashed, 'structures_burned': burned}


# --- eventos ---------------------------------------------------------------

def fire_events(state, case) -> list[dict]:
    """Eventos agendados para o tique atual: rádio no estado, efeitos visíveis aplicados.

    A saída leva só o rádio; os efeitos de rádio (base morta, estrutura
    oculta) não aparecem aqui nem no estado, para que nenhum planejador os
    receba em forma estruturada.
    """
    fired = []
    for event in case.get('events') or []:
        if int(event['tick']) != int(state['tick']):
            continue
        effects = event.get('effects') or {}
        if effects.get('wind'):
            state['wind'] = {'toward': effects['wind']['toward'], 'speed': int(effects['wind']['speed'])}
        for drone_id in effects.get('offline_drones') or []:
            if drone_id in state['drones'] and state['drones'][drone_id]['condition'] == 'ok':
                state['drones'][drone_id]['condition'] = 'offline'
        if event.get('radio'):
            state['radio'].append({'tick': int(state['tick']), 'text': event['radio']})
        fired.append({'tick': int(state['tick']), 'radio': event.get('radio', '')})
    return fired


# --- um tique completo -----------------------------------------------------

def step(state, actions, case) -> dict:
    """Aplica as ações, avança o fogo e dispara os eventos; devolve o relatório."""
    state = deepcopy(state)
    truth = truth_at(case, state['tick'])
    applied = apply_actions(state, truth, actions)
    lost = ground_lost_drones(state, truth)
    fire = advance_fire(state)
    state['tick'] = int(state['tick']) + 1
    events = fire_events(state, case)
    return {'state': state, 'tick': state['tick'], 'applied': applied, 'lost': lost, 'fire': fire,
            'events': events, 'metrics': metrics(state, case), 'fires_remaining': len(state['fires']),
            'done': is_done(state)}


def is_done(state) -> bool:
    return not state['fires'] or int(state['tick']) >= int(state['horizon'])


# --- métricas --------------------------------------------------------------

def structure_condition(state, c) -> str:
    if c in set(state['ash']):
        return 'burned'
    if c in state['fires']:
        return 'burning'
    return 'intact'


def metrics(state, case=None) -> dict:
    """Números do estado; com o caso, inclui as estruturas que só o rádio anunciou."""
    structures = {c: {'name': s['name'], 'condition': s['condition'], 'hidden': False} for c, s in state['structures'].items()}
    if case is not None:
        for c, name in truth_at(case, state['tick'])['hidden_structures'].items():
            structures.setdefault(c, {'name': name, 'condition': structure_condition(state, c), 'hidden': True})
    drones = state['drones'].values()
    return {'tick': int(state['tick']), 'burned': len(state['ash']), 'burning': len(state['fires']),
            'intensity_total': sum(state['fires'].values()),
            'structures_burned': sum(1 for s in structures.values() if s['condition'] == 'burned'),
            'structures_total': len(structures), 'structures': structures,
            'drones_ok': sum(1 for d in drones if d['condition'] == 'ok'),
            'drones_lost': sum(1 for d in drones if d['condition'] == 'lost'),
            'drones_offline': sum(1 for d in drones if d['condition'] == 'offline'),
            **{key: int(value) for key, value in state['counters'].items()}}


# --- regras em texto, para os prompts --------------------------------------

def describe_rules(state) -> str:
    r = state['rules']
    return (
        f"WORLD RULES. Grid {state['width']}x{state['height']}; cells are \"x,y\" with x growing EAST (right) "
        f"and y growing SOUTH (down); \"0,0\" is the north-west corner. One round = one tick. "
        "FIRE: each burning cell has intensity 1-3; intensity grows by 1 per tick; a cell at intensity 3 "
        "becomes ASH at the next tick (permanent loss). Fire spreads one cell DOWNWIND (wind.toward) when "
        "intensity >= 2 (>= 1 when wind speed is 2), to the two LATERAL cells when intensity >= 3, "
        "and never upwind. Obstacles, ash and base cells "
        "never burn; structures burn like vegetation and are lost when their cell becomes ash. "
        f"DRONES: 'move' with target \"x,y\" flies up to {r['speed']} cells per tick along a path that avoids "
        "obstacles, 1 battery per cell (a farther target moves "
        f"{r['speed']} cells toward it); 'drop' with target on the drone's own cell or an adjacent cell "
        f"(8 neighbours) spends 1 water and 1 battery and lowers that cell's intensity by {r['drop_power']} "
        "(the target must be burning); 'resupply' works only on an ACTIVE base cell: water back to "
        f"{r['water_capacity']}, battery +{r['recharge']} (max {r['battery_capacity']}); 'hold' does nothing. "
        "A drone that reaches 0 battery outside an active base is LOST. Lost or offline drones ignore orders. "
        "RADIO: some facts exist only in the radio messages (for example a base out of service or a structure "
        "to protect); telemetry does not reflect them, and acting against them is rejected by the world."
    )
