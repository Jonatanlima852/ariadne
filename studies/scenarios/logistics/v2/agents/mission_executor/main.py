"""MissionExecutor: beliefs, desire and explicit SDK plans."""
from ariadne_sdk import BdiAgent, Input, Plan
from studies.scenarios.logistics.v2.domain.world import execute
from studies.scenarios.logistics.v2.agents.common import serve


def mission_execute(s, d):
    if not d['plan']['approved']:
        return {'state': s, 'reason': 'supervisor requested revision', 'incidents': []}
    return execute(s, d['plan']['actions'], d['incidents'])


def make_agent(**options):
    configuration = dict(name='MissionExecutor', capabilities=['logistics-v2-MissionExecutor'],
                         beliefs=Input('state'), desire=Input(),
                         plans=[Plan('execute_until_incident_or_error', execute=mission_execute)])
    return BdiAgent(**(configuration | options))


if __name__ == '__main__':
    serve(make_agent)
