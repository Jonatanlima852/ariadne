"""InventoryManager: beliefs, desire and explicit SDK plans."""
from ariadne_sdk import BdiAgent, Input, Plan
from studies.scenarios.logistics.v2.domain.world import weight
from studies.scenarios.logistics.v2.agents.common import serve


def inventory(s, desire):
    options = []
    ids = desire['mission']['order_ids']
    ranks = {oid: i for i, oid in enumerate(ids)}
    for oid in ids:
        if oid not in s['orders'] or oid in s['deliveries']:
            continue
        o = s['orders'][oid]
        held = [(vid, v) for vid, v in s['vehicles'].items() if oid in v['cargo']]
        sources = ([{'source_vehicle': vid, 'location': v['location']} for vid, v in held]
                   if held else [{'depot': did, 'location': d['location']} for did, d in s['depots'].items()
                                 if all(d['stock'].get(k, 0) >= q for k, q in o['items'].items())])
        for source in sources:
            options.append({'order': oid, 'rank': ranks[oid], **source})
    return {'options': options, 'explanation': 'Stock checked; held cargo must be continued or recovered.'}


def make_agent(**options):
    configuration = dict(name='InventoryManager', capabilities=['logistics-v2-InventoryManager'],
                         beliefs=Input('state'), desire=Input(),
                         plans=[Plan('available_stock_or_held_cargo', execute=inventory)])
    return BdiAgent(**(configuration | options))


if __name__ == '__main__':
    serve(make_agent)
