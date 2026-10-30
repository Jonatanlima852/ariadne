"""EnergyManager: beliefs, desire and explicit SDK plans."""
from ariadne_sdk import BdiAgent, Input, Plan
from ariadne_sdk import SearchProblem, uniform_cost_search
from studies.scenarios.logistics.v2.domain.world import edge, execute
from studies.scenarios.logistics.v2.domain.planning import energy_to_charger
from studies.scenarios.logistics.v2.domain.graph import _edges
from studies.scenarios.logistics.v2.agents.common import serve


def energy_direct(s, d):
    outcome = execute(s, d['route']['actions'])
    if outcome['reason']:
        return False
    c = d['route']['choice']
    if d.get('policy') != 'lean-v1' or not c:
        return True
    after = outcome['state']
    vehicle = after['vehicles'][c['vehicle']]
    return (len(after['deliveries']) == len(after['orders'])
            or vehicle['battery'] >= energy_to_charger(after, vehicle['location']))


def energy_search(s, d):
    r, c = d['route'], d['route']['choice']
    if not c:
        return r
    vid, oid = c['vehicle'], c['order']
    v = s['vehicles'][vid]
    reserve = d.get('policy') == 'lean-v1' and len(s['orders']) - len(s['deliveries']) > 1
    destination = s['orders'][oid]['destination']
    reserve_energy = energy_to_charger(s, destination) if reserve else 0
    initial = (v['location'], v['battery'], 1 if oid in v['cargo'] else 0)
    load = {'type': 'TRANSFER' if c.get('source_vehicle') else 'LOAD', 'vehicle': vid, 'order': oid,
            **({'source_vehicle': c['source_vehicle']} if c.get('source_vehicle') else {'depot': c['depot']})}
    def actions(state):
        loc, battery, stage = state
        if stage == 2:
            return []
        result = []
        if stage == 0 and loc == c['location']:
            result.append(load)
        if stage == 1 and loc == s['orders'][oid]['destination']:
            result.append({'type': 'DELIVER', 'vehicle': vid, 'order': oid})
        if loc in s['charging_locations'] and battery < v['battery_capacity']:
            result.append({'type': 'RECHARGE', 'vehicle': vid})
        for e in _edges(s).values():
            if e['from'] == loc and edge(s, loc, e['to']) and battery >= e['energy']:
                result.append({'type': 'MOVE', 'vehicle': vid, 'from': loc, 'to': e['to']})
        return result
    def transition(state, a):
        loc, battery, stage = state
        if a['type'] == 'MOVE':
            return (a['to'], battery - edge(s, loc, a['to'])['energy'], stage)
        if a['type'] == 'RECHARGE':
            return (loc, v['battery_capacity'], stage)
        return (loc, battery, stage + 1)
    def cost(state, a, after):
        if a['type'] == 'MOVE':
            return edge(s, state[0], after[0])['minutes']
        return s['recharge_minutes'] if a['type'] == 'RECHARGE' else 1
    result = uniform_cost_search(SearchProblem(initial=initial, actions=actions,
        transition=transition, is_goal=lambda x: x[2] == 2 and x[1] >= reserve_energy,
        cost=cost), max_expansions=10000)
    return {'choice': c, 'actions': list(result.actions) if result.found else [],
            'reason': ('energy-aware route retaining access to a charger' if reserve else 'energy-aware route with charging')
                      if result.found else 'no energy-feasible route'}


def make_agent(**options):
    configuration = dict(name='EnergyManager', capabilities=['logistics-v2-EnergyManager'],
                         beliefs=Input('state'), desire=Input(),
                         plans=[Plan('direct_autonomy', when=energy_direct, cost=0, execute=lambda s, d: d['route']),
               Plan('search_recharge_and_detour', execute=energy_search)])
    return BdiAgent(**(configuration | options))


if __name__ == '__main__':
    serve(make_agent)
