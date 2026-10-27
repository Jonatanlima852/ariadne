"""RoutePlanner: beliefs, desire and explicit SDK plans."""
from ariadne_sdk import BdiAgent, Input, Plan
from studies.scenarios.logistics.v2.domain.planning import path
from studies.scenarios.logistics.v2.agents.common import serve


def route(s, desire):
    c = desire['allocation']['choice']
    if not c:
        return {'choice': {}, 'actions': [], 'reason': 'no stock/vehicle/route candidate'}
    v = s['vehicles'][c['vehicle']]
    actions, current = [], v['location']
    def leg(target):
        nonlocal current
        nodes, _ = path(s, current, target)
        if nodes is None:
            raise ValueError('route became unreachable')
        for node in nodes:
            actions.append({'type': 'MOVE', 'vehicle': c['vehicle'], 'from': current, 'to': node})
            current = node
    leg(c['location'])
    if c['order'] not in v['cargo']:
        actions.append({'type': 'TRANSFER' if c.get('source_vehicle') else 'LOAD',
                        'vehicle': c['vehicle'], 'order': c['order'],
                        **({'source_vehicle': c['source_vehicle']} if c.get('source_vehicle') else {'depot': c['depot']})})
    leg(s['orders'][c['order']]['destination'])
    actions.append({'type': 'DELIVER', 'vehicle': c['vehicle'], 'order': c['order']})
    return {'choice': c, 'actions': actions, 'reason': 'shortest open route, before energy check'}


def make_agent(**options):
    configuration = dict(name='RoutePlanner', capabilities=['logistics-v2-RoutePlanner'],
                         beliefs=Input('state'), desire=Input(),
                         plans=[Plan('shortest_open_connections', execute=route)])
    return BdiAgent(**(configuration | options))


if __name__ == '__main__':
    serve(make_agent)
