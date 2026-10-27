"""ResourceAllocator: beliefs, desire and explicit SDK plans."""
from ariadne_sdk import BdiAgent, Input, Plan
from studies.scenarios.logistics.v2.domain.world import weight
from studies.scenarios.logistics.v2.domain.planning import path, allocation_key
from studies.scenarios.logistics.v2.agents.common import serve


def allocate(s, desire):
    candidates = []
    for option in desire['inventory']['options']:
        for vid, v in s['vehicles'].items():
            if not v['available']:
                continue
            oid = option['order']
            load = sum(weight(s, x) for x in v['cargo'])
            if load + (0 if oid in v['cargo'] else weight(s, oid)) > v['capacity']:
                continue
            source = option.get('source_vehicle')
            if source and source != vid and s['vehicles'][source]['available']:
                continue
            first, c1 = path(s, v['location'], option['location'])
            second, c2 = path(s, option['location'], s['orders'][oid]['destination'])
            candidate = {**option, 'vehicle': vid}
            if first is None or second is None or allocation_key(candidate) in desire.get('excluded', []):
                continue
            candidates.append((option['rank'], c1 + c2, vid, candidate))
    candidates.sort(key=lambda row: row[:3])
    return {'choice': candidates[0][3] if candidates else {},
            'explanation': 'Mission order, capacity, availability, reachable source and travel time.'}


def make_agent(**options):
    configuration = dict(name='ResourceAllocator', capabilities=['logistics-v2-ResourceAllocator'],
                         beliefs=Input('state'), desire=Input(),
                         plans=[Plan('available_capable_reachable_vehicle', execute=allocate)])
    return BdiAgent(**(configuration | options))


if __name__ == '__main__':
    serve(make_agent)
