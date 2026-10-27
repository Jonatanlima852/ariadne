"""Authoritative transitions. Neither reports nor proposed plans complete orders."""
from copy import deepcopy
import math

from studies.scenarios.logistics.domain.simulation import _edges


RULES = """Sequential simulation; time is global in minutes. Every edge is BIDIRECTIONAL
unless explicitly marked bidirectional=false; a single listed edge permits travel
in BOTH directions by default. Each action names type and
vehicle. MOVE names from/to and consumes edge minutes, energy and distance.
LOAD names order/depot; loads the WHOLE order at its depot (1 minute), consuming
stock; capacity is sum(quantity * item_weights). DELIVER names order; requires
whole cargo and correct destination (1 minute). RECHARGE only at charging_locations,
restores battery_capacity in recharge_minutes. TRANSFER names order/source_vehicle;
recovers whole cargo from an unavailable vehicle at the same location (1 minute).
Unavailable vehicles cannot act. Deadlines are soft: late deliveries count separately.
Incidents fire BEFORE an action once accepted_actions >= after_actions, independently
of rejected proposals. Future incidents are not disclosed until they fire.
Stop and reconsider on an incident. No actions invent edges.
Orders cannot be split across depots/vehicles. Finite positive integer quantities.
"""


def initial(case):
    s = deepcopy(case['world'])
    s.update(time=0, accepted_actions=0, distance=0, energy=0, deliveries={},
             blocked=[], incidents_seen=[], history=[])
    s['orders'] = {o['id']: deepcopy(o) for o in case['orders']}
    for v in s['vehicles'].values():
        v.setdefault('available', True)
        v.setdefault('cargo', [])
    return s


def weight(s, order):
    return sum(q * s['item_weights'][item] for item, q in s['orders'][order]['items'].items())


def edge(s, origin, destination):
    if [origin, destination] in s['blocked']:
        return None
    return _edges(s).get((origin, destination))


def incidents(s, schedule):
    fired = []
    for i, event in enumerate(schedule):
        if i in s['incidents_seen'] or s['accepted_actions'] < event['after_actions']:
            continue
        if event['type'] == 'block':
            s['blocked'].extend([event['edge'], list(reversed(event['edge']))])
        elif event['type'] == 'unavailable':
            s['vehicles'][event['vehicle']]['available'] = False
        else:
            raise ValueError('unknown incident')
        s['incidents_seen'].append(i)
        fired.append(deepcopy(event))
        s['history'].append({'incident': deepcopy(event), 'time': s['time']})
    return fired


def apply(s, action):
    """Validate first, mutate atomically only on success; record every rejection."""
    error, duration, distance, energy = None, 1, 0, 0
    a = action if isinstance(action, dict) else {}
    kind, vehicle = a.get('type'), a.get('vehicle')
    v = s['vehicles'].get(vehicle)
    order = a.get('order')
    o = s['orders'].get(order)
    if not v or not v['available']:
        error = 'vehicle unknown or unavailable'
    elif kind == 'MOVE':
        e = edge(s, a.get('from'), a.get('to'))
        if a.get('from') != v['location'] or e is None:
            error = 'origin mismatch, missing or blocked edge'
        elif v['battery'] < e['energy']:
            error = 'insufficient battery'
        else:
            duration, distance, energy = e['minutes'], e.get('distance', e['minutes']), e['energy']
    elif kind == 'RECHARGE':
        if v['location'] not in s['charging_locations'] or v['battery'] >= v['battery_capacity']:
            error = 'no charger or battery already full'
        duration = s['recharge_minutes']
    elif not o or order in s['deliveries']:
        error = 'unknown or already delivered order'
    elif kind == 'LOAD':
        depot = s['depots'].get(a.get('depot'))
        held = any(order in other['cargo'] for other in s['vehicles'].values())
        if not depot or depot['location'] != v['location'] or held:
            error = 'depot location mismatch or cargo already assigned'
        elif any(depot['stock'].get(k, 0) < q for k, q in o['items'].items()):
            error = 'insufficient stock'
        elif sum(weight(s, x) for x in v['cargo']) + weight(s, order) > v['capacity']:
            error = 'capacity exceeded'
    elif kind == 'TRANSFER':
        source = s['vehicles'].get(a.get('source_vehicle'))
        if (not source or source['available'] or source['location'] != v['location']
                or order not in source['cargo']):
            error = 'cargo recovery requires colocated unavailable source'
        elif sum(weight(s, x) for x in v['cargo']) + weight(s, order) > v['capacity']:
            error = 'capacity exceeded'
    elif kind == 'DELIVER':
        if order not in v['cargo'] or v['location'] != o['destination']:
            error = 'cargo absent or wrong destination'
    else:
        error = 'unknown action'
    record = {'action': deepcopy(action), 'accepted': error is None,
              'reason': error, 'time_before': s['time']}
    if error is None:
        if kind == 'MOVE':
            v['location'], v['battery'] = a['to'], v['battery'] - energy
        elif kind == 'RECHARGE':
            v['battery'] = v['battery_capacity']
        elif kind == 'LOAD':
            for k, q in o['items'].items():
                s['depots'][a['depot']]['stock'][k] -= q
            v['cargo'].append(order)
        elif kind == 'TRANSFER':
            s['vehicles'][a['source_vehicle']]['cargo'].remove(order)
            v['cargo'].append(order)
        elif kind == 'DELIVER':
            v['cargo'].remove(order)
            s['deliveries'][order] = {'time': s['time'] + duration,
                                      'on_time': s['time'] + duration <= o['deadline'],
                                      'vehicle': vehicle}
        s['time'] += duration
        s['distance'] += distance
        s['energy'] += energy
        s['accepted_actions'] += 1
    record['time_after'] = s['time']
    s['history'].append(record)
    return error


def execute(state, actions, schedule=(), max_actions=200):
    s = deepcopy(state)
    reason, fired = '', []
    for action in actions[:max_actions]:
        fired = incidents(s, schedule)
        if fired:
            reason = 'incident requires revision'
            break
        reason = apply(s, action) or ''
        if reason:
            break
    return {'state': s, 'reason': reason, 'incidents': fired}


def validate_case(case):
    s = initial(case)
    nodes = {e[k] for e in s['edges'] for k in ('from', 'to')}
    def positive(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0
    assert len(s['orders']) == len(case['orders']) and s['orders']
    for o in s['orders'].values():
        assert o['destination'] in nodes and positive(o['deadline']) and o['items']
        assert all(k in s['item_weights'] and isinstance(q, int) and not isinstance(q, bool) and q > 0 for k, q in o['items'].items())
    assert all(positive(x) for x in s['item_weights'].values())
    for v in s['vehicles'].values():
        assert v['location'] in nodes and positive(v['capacity'])
        assert 0 <= v['battery'] <= v['battery_capacity'] and positive(v['battery_capacity'])
    for d in s['depots'].values():
        assert d['location'] in nodes
        assert all(k in s['item_weights'] and isinstance(q, int) and q >= 0 for k, q in d['stock'].items())
    for e in s['edges']:
        assert all(positive(e[k]) for k in ('minutes', 'energy', 'distance'))
    assert set(s['charging_locations']) <= nodes and positive(s['recharge_minutes'])
    for event in case['incidents']:
        assert isinstance(event['after_actions'], int) and event['after_actions'] >= 0
        assert event['type'] in ('block', 'unavailable')
        if event['type'] == 'block':
            assert tuple(event['edge']) in _edges(s)
        else:
            assert event['vehicle'] in s['vehicles']
    return s
