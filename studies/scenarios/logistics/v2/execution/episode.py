"""Small episode controller. Decisions go through registered runtime agents."""
import json
import time
from ariadne_sdk import RuntimeClient, Step
from ariadne_sdk.experiment import compile_steps
from studies.scenarios.logistics.v2.domain.planning import allocation_key
from studies.scenarios.logistics.v2.domain.world import initial, execute, incidents


def metrics(s):
    return {'delivered': len(s['deliveries']), 'total_orders': len(s['orders']),
            'on_time': sum(d['on_time'] for d in s['deliveries'].values()),
            'rejected_actions': sum(h.get('accepted') is False for h in s['history']),
            'distance': s['distance'], 'energy_consumed': s['energy'],
            'simulation_minutes': s['time'], 'accepted_actions': s['accepted_actions']}


class Episode:
    def __init__(self, client, case, strategy, *, demo=False, max_rounds=20, model=None):
        self.client, self.case, self.strategy = client, case, strategy
        self.demo, self.max_rounds = demo, max_rounds
        self.model = model
        self.calls, self.workflows = [], []

    def remember(self, role, result):
        record = {'role': role, **result.to_dict()}
        self.calls.append(record)
        result.assert_completed()
        if role in ('SingleLLM', 'OrderInterpreter', 'MissionDecomposer', 'IncidentAnalyst', 'OperationsReporter'):
            provider = result.metadata.get('provider')
            expected = 'deterministic-integration-substitute' if self.demo else 'openai'
            if provider != expected or (not self.demo and self.model and result.metadata.get('model') != self.model):
                raise ValueError(f'{role}: remote provider/model differs from requested configuration')
        return result.output

    def ask(self, role, payload):
        result = self.client.submit(str(len(self.calls)), goal=role,
            capabilities=['logistics-v2-' + role], payload=payload, deadline_ms=120000)
        return self.remember(role, result)

    def planning(self, state, mission, excluded):
        common = {'state': state, 'mission': mission, 'excluded': excluded}
        if getattr(self, 'policy', None):
            common['policy'] = self.policy
        stock = Step('logistics-v2-InventoryManager', 'Choose stock sources', name='inventory', payload=common)
        vehicle = Step('logistics-v2-ResourceAllocator', 'Allocate a vehicle', name='resource',
                       payload={**common, 'inventory': stock.output})
        route = Step('logistics-v2-RoutePlanner', 'Route via selected source', name='route',
                     payload={**common, 'allocation': vehicle.output})
        energy = Step('logistics-v2-EnergyManager', 'Check autonomy and recharge', name='energy',
                      payload={**common, 'route': route.output})
        approve = Step('logistics-v2-ConstraintSupervisor', 'Validate concrete effects', name='validation',
                       payload={**common, 'energy': energy.output})
        steps = [stock, vehicle, route, energy, approve]
        # Use decomposed dependencies in addition to indispensable domain bindings.
        by_name = {s.name: s for s in steps}
        for dependency in mission.get('dependencies', []):
            step = by_name.get(dependency['task'])
            if step:
                step.depends_on = tuple(by_name[k] for k in dependency['requires'] if k in by_name and k != step.name)
        result = self.client.submit_workflow('Plan next delivery', steps=compile_steps(steps),
                                             final_step_id='validation', rpc_timeout=35)
        self.workflows.append(result.to_dict())
        for role, step in zip(['InventoryManager', 'ResourceAllocator', 'RoutePlanner',
                               'EnergyManager', 'ConstraintSupervisor'], steps):
            item = result.steps.get(step.name, {}).get('result')
            if item:
                self.remember(role, item)
        result.assert_completed()
        return result.output

    def run(self):
        started = time.perf_counter()
        s, feedback, excluded, mission = initial(self.case), {}, [], None
        reason, rounds, infrastructure_error = '', 0, None
        try:
            requirements = None
            if self.strategy == 'ariadne':
                payload = {'requests': [o['request'] for o in self.case['orders']],
                           'locations': sorted({e[k] for e in s['edges'] for k in ('from', 'to')})}
                if self.demo:
                    payload['fixture_orders_json'] = json.dumps([
                        {**{k: o[k] for k in ('id', 'destination', 'priority', 'deadline')},
                         'items': [{'sku': k, 'quantity': v} for k, v in o['items'].items()]}
                        for o in self.case['orders']])
                requirements = self.ask('OrderInterpreter', payload)
                extracted = {o['id']: {**o, 'items': {x['sku']: x['quantity'] for x in o['items']}}
                             for o in requirements['orders']}
                expected = {k: {f: o[f] for f in ('id', 'destination', 'priority', 'deadline', 'items')}
                            for k, o in s['orders'].items()}
                if extracted != expected or len(requirements['orders']) != len(expected):
                    raise ValueError('interpretation differs from authoritative order requirements')
            for rounds in range(1, self.max_rounds + 1):
                if len(s['deliveries']) == len(s['orders']):
                    reason = 'all orders delivered'
                    break
                fired = incidents(s, self.case['incidents'])
                if fired:
                    feedback = {'incidents': fired, 'reason': 'incident requires revision'}
                if self.strategy == 'single-llm':
                    proposal = self.ask('SingleLLM', {'state': s, 'requests': [o['request'] for o in self.case['orders']],
                        'feedback': feedback,
                        'round': rounds, 'remaining_rounds': self.max_rounds - rounds})
                    if not proposal['actions']:
                        reason = proposal['explanation'] or 'no further actions proposed'
                        break
                    outcome = execute(s, proposal['actions'], self.case['incidents'])
                else:
                    analysis = None
                    if feedback.get('incidents') or feedback.get('reason'):
                        analysis = self.ask('IncidentAnalyst', {'state': s, 'feedback': feedback})
                    if mission is None or analysis:
                        mission = self.ask('MissionDecomposer', {'state': s, 'requirements': requirements,
                            'analysis': analysis})
                        pending = set(s['orders']) - set(s['deliveries'])
                        if set(mission['order_ids']) != pending or len(mission['order_ids']) != len(pending):
                            raise ValueError('decomposition must include each outstanding order once')
                    plan = self.planning(s, mission, excluded)
                    if not plan['approved']:
                        if plan['choice']:
                            excluded.append(allocation_key(plan['choice']))
                            feedback = {'reason': plan['reason'], 'rejected_choice': plan['choice']}
                            continue
                        reason = 'no remaining stock/vehicle/route candidate'
                        break
                    outcome = self.ask('MissionExecutor', {'state': s, 'plan': plan,
                                                          'incidents': self.case['incidents']})
                progressed = outcome['state']['accepted_actions'] > s['accepted_actions']
                s, feedback = outcome['state'], {'reason': outcome['reason'], 'incidents': outcome['incidents']}
                if progressed or outcome['incidents']:
                    excluded = []
                if len(s['deliveries']) == len(s['orders']):
                    reason = 'all orders delivered'
                    break
            else:
                reason = 'revision round limit reached'
        except Exception as error:
            infrastructure_error = f'{type(error).__name__}: {error}'
            reason = infrastructure_error
        measured = metrics(s)
        explanation = reason
        before_report_seconds = time.perf_counter() - started
        report_started = time.perf_counter()
        if self.strategy == 'ariadne' and infrastructure_error is None:
            try:
                explanation = self.ask('OperationsReporter', {'state': s, 'metrics': measured,
                    'stop_reason': reason, 'decisions': [{'role': c['role'], 'output': c['output']}
                    for c in self.calls if c['role'] != 'MissionExecutor']})['explanation']
            except Exception as error:
                infrastructure_error = f'reporter: {type(error).__name__}: {error}'
        real_calls = [c for c in self.calls if c['role'] in
                      ('SingleLLM', 'OrderInterpreter', 'MissionDecomposer', 'IncidentAnalyst', 'OperationsReporter') and not self.demo]
        usage = [c.get('metadata', {}).get('usage', {}) for c in real_calls]
        return {'case': self.case['id'], 'configuration': self.strategy,
                'execution_kind': 'deterministic-integration-demo' if self.demo else 'real-llm',
                **measured, 'wall_seconds': round(time.perf_counter() - started, 4),
                'wall_seconds_before_report': round(before_report_seconds, 4),
                'reporting_seconds': round(time.perf_counter() - report_started, 4) if self.strategy == 'ariadne' else 0,
                'llm_calls': len(real_calls),
                'input_tokens': sum(u.get('input_tokens', 0) for u in usage) if usage and all('input_tokens' in u for u in usage) else None,
                'output_tokens': sum(u.get('output_tokens', 0) for u in usage) if usage and all('output_tokens' in u for u in usage) else None,
                'rounds': rounds, 'result': 'error' if infrastructure_error else 'complete' if measured['delivered'] == measured['total_orders'] else 'partial',
                'stop_reason': reason, 'explanation': explanation, 'error': infrastructure_error,
                'state': s, 'calls': self.calls, 'workflows': self.workflows}
