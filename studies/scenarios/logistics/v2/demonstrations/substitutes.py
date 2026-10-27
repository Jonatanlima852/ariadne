"""Explicit deterministic substitutes for integration demonstrations only."""
import json
from types import SimpleNamespace
from ariadne_sdk import LlmAgent
from studies.scenarios.logistics.v2.domain.planning import allocation_key
from studies.scenarios.logistics.v2.agents.inventory_manager.main import inventory
from studies.scenarios.logistics.v2.agents.resource_allocator.main import allocate
from studies.scenarios.logistics.v2.agents.route_planner.main import route
from studies.scenarios.logistics.v2.agents.energy_manager.main import energy_search


def deterministic(role, context):
    """Integration fixture, not a baseline or a model-quality measurement."""
    if role == 'OrderInterpreter':
        return {'orders': json.loads(context['fixture_orders_json'])}
    if role == 'MissionDecomposer':
        s = context['state']
        orders = [o for o in context['requirements']['orders'] if o['id'] not in s['deliveries']]
        orders.sort(key=lambda o: (-o['priority'], o['deadline'], o['id']))
        return {'order_ids': [o['id'] for o in orders], 'dependencies': [
            {'task': 'resource', 'requires': ['inventory']},
            {'task': 'route', 'requires': ['resource']},
            {'task': 'energy', 'requires': ['route']},
            {'task': 'validation', 'requires': ['energy']},
            {'task': 'execution', 'requires': ['validation']}],
            'explanation': 'Deterministic integration fixture: priority then deadline.'}
    if role == 'IncidentAnalyst':
        return {'affected_orders': [k for k in context['state']['orders'] if k not in context['state']['deliveries']],
                'review': ['inventory', 'resource', 'route', 'energy'],
                'explanation': 'Deterministic integration fixture: reassess remaining work.'}
    if role == 'OperationsReporter':
        m = context['metrics']
        return {'explanation': f"Demonstração de integração: {m['delivered']}/{m['total_orders']} entregues; {m['on_time']} no prazo. {context['stop_reason']}"}
    s = context['state']
    ids = sorted((k for k in s['orders'] if k not in s['deliveries']),
                 key=lambda k: (-s['orders'][k]['priority'], s['orders'][k]['deadline']))
    d = {'mission': {'order_ids': ids}, 'excluded': []}
    for _ in range(40):
        d['inventory'] = inventory(s, d)
        d['allocation'] = allocate(s, d)
        d['route'] = route(s, d)
        d['energy'] = energy_search(s, d)
        if d['energy']['actions'] or not d['allocation']['choice']:
            break
        d['excluded'].append(allocation_key(d['allocation']['choice']))
    actions = []
    for a in d['energy']['actions']:
        a = dict(a)
        a['origin'], a['destination'] = a.pop('from', None), a.pop('to', None)
        for key in ('order', 'depot', 'source_vehicle'):
            a.setdefault(key, None)
        actions.append(a)
    return {'actions': actions, 'explanation': 'Deterministic fixture uses symbolic policies; not a Single LLM benchmark.'}


class DemoClient:
    def __init__(self):
        self.responses = self

    def parse(self, *, model, input, text_format):
        role = input[0]['content'].splitlines()[0].split('=', 1)[1]
        value = deterministic(role, json.loads(input[1]['content']))
        return SimpleNamespace(output_parsed=text_format.model_validate(value), usage=None)


class DemoLlmAgent(LlmAgent):
    def handle(self, task):
        result = super().handle(task)
        result.metadata.update(provider='deterministic-integration-substitute', model='no-real-model')
        return result
