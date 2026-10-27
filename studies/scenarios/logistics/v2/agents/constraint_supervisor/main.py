"""ConstraintSupervisor: beliefs, desire and explicit SDK plans."""
from ariadne_sdk import BdiAgent, Input, Plan
from studies.scenarios.logistics.v2.domain.world import execute
from studies.scenarios.logistics.v2.agents.common import serve


def supervise(s, d):
    proposal = d['energy']
    preview = execute(s, proposal['actions'])
    approved = not preview['reason'] and len(preview['state']['deliveries']) > len(s['deliveries'])
    return {**proposal, 'approved': approved,
            'reason': preview['reason'] or proposal['reason'],
            'predicted_time': preview['state']['time']}


def make_agent(**options):
    configuration = dict(name='ConstraintSupervisor', capabilities=['logistics-v2-ConstraintSupervisor'],
                         beliefs=Input('state'), desire=Input(),
                         plans=[Plan('validate_all_effects', execute=supervise)])
    return BdiAgent(**(configuration | options))


if __name__ == '__main__':
    serve(make_agent)
