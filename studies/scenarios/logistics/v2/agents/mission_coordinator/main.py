"""MissionCoordinator: deterministic revision and mission ordering for the lean hybrid."""
from ariadne_sdk import BdiAgent, Input, Plan
from studies.scenarios.logistics.v2.agents.common import serve


def coordinate(state, desire):
    pending = [oid for oid in state['orders'] if oid not in state['deliveries']]
    held = {oid for vehicle in state['vehicles'].values() for oid in vehicle['cargo']}
    pending.sort(key=lambda oid: (oid not in held, -state['orders'][oid]['priority'],
                                 state['orders'][oid]['deadline'], oid))
    return {'order_ids': pending, 'dependencies': [],
            'explanation': 'Continue or recover held cargo, then priority, deadline and stable order ID.',
            'revision_reason': desire.get('feedback', {}).get('reason', '')}


def make_agent(**options):
    configuration = dict(name='MissionCoordinator', capabilities=['logistics-v2-MissionCoordinator'],
                         beliefs=Input('state'), desire=Input(),
                         plans=[Plan('revise_from_current_beliefs', execute=coordinate)])
    return BdiAgent(**(configuration | options))


if __name__ == '__main__':
    serve(make_agent)
