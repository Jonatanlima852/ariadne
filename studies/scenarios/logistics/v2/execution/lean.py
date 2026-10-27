"""Lean hybrid: one LLM interpretation followed by independently deployed BDI agents.

This is a separate experimental configuration. The original ten-agent pipeline
and its observations remain available as ``ariadne``.
"""
import json
import time
from studies.scenarios.logistics.v2.execution.episode import Episode, metrics
from studies.scenarios.logistics.v2.domain.planning import allocation_key
from studies.scenarios.logistics.v2.domain.world import initial, incidents


class LeanEpisode(Episode):
    policy = 'lean-v1'

    def run(self):
        started = time.perf_counter()
        state, feedback, excluded = initial(self.case), {}, []
        reason, rounds, error = '', 0, None
        try:
            payload = {'requests': [o['request'] for o in self.case['orders']],
                       'locations': sorted({e[k] for e in state['edges'] for k in ('from', 'to')})}
            if self.demo:
                payload['fixture_orders_json'] = json.dumps([
                    {**{k: o[k] for k in ('id', 'destination', 'priority', 'deadline')},
                     'items': [{'sku': k, 'quantity': v} for k, v in o['items'].items()]}
                    for o in self.case['orders']])
            requirements = self.ask('OrderInterpreter', payload)
            extracted = {o['id']: {**o, 'items': {x['sku']: x['quantity'] for x in o['items']}}
                         for o in requirements['orders']}
            expected = {k: {f: o[f] for f in ('id', 'destination', 'priority', 'deadline', 'items')}
                        for k, o in state['orders'].items()}
            if extracted != expected or len(requirements['orders']) != len(expected):
                raise ValueError('interpretation differs from authoritative order requirements')
            for rounds in range(1, self.max_rounds + 1):
                if len(state['deliveries']) == len(state['orders']):
                    reason = 'all orders delivered'
                    break
                fired = incidents(state, self.case['incidents'])
                if fired:
                    feedback = {'incidents': fired, 'reason': 'incident requires revision'}
                mission = self.ask('MissionCoordinator', {'state': state, 'requirements': requirements,
                                                          'feedback': feedback})
                plan = self.planning(state, mission, excluded)
                if not plan['approved']:
                    if plan['choice']:
                        excluded.append(allocation_key(plan['choice']))
                        feedback = {'reason': plan['reason'], 'rejected_choice': plan['choice']}
                        continue
                    reason = 'no remaining stock/vehicle/route candidate'
                    break
                outcome = self.ask('MissionExecutor', {'state': state, 'plan': plan,
                                                       'incidents': self.case['incidents']})
                progressed = outcome['state']['accepted_actions'] > state['accepted_actions']
                state, feedback = outcome['state'], {'reason': outcome['reason'], 'incidents': outcome['incidents']}
                if progressed or outcome['incidents']:
                    excluded = []
                if len(state['deliveries']) == len(state['orders']):
                    reason = 'all orders delivered'
                    break
            else:
                reason = 'revision round limit reached'
        except Exception as failure:
            error = f'{type(failure).__name__}: {failure}'
            reason = error
        measured = metrics(state)
        real_calls = [c for c in self.calls if c['role'] == 'OrderInterpreter' and not self.demo]
        usage = [c.get('metadata', {}).get('usage', {}) for c in real_calls]
        elapsed = round(time.perf_counter() - started, 4)
        return {'case': self.case['id'], 'configuration': self.strategy,
                'execution_kind': 'deterministic-integration-demo' if self.demo else 'real-llm',
                'policy': self.policy, **measured, 'wall_seconds': elapsed,
                'wall_seconds_before_report': elapsed, 'reporting_seconds': 0,
                'llm_calls': len(real_calls),
                'input_tokens': sum(u['input_tokens'] for u in usage) if usage and all('input_tokens' in u for u in usage) else None,
                'output_tokens': sum(u['output_tokens'] for u in usage) if usage and all('output_tokens' in u for u in usage) else None,
                'rounds': rounds, 'result': 'error' if error else 'complete' if measured['delivered'] == measured['total_orders'] else 'partial',
                'stop_reason': reason,
                'explanation': f"{measured['delivered']}/{measured['total_orders']} entregues; {measured['on_time']} no prazo. {reason}",
                'error': error, 'state': state, 'calls': self.calls, 'workflows': self.workflows}
