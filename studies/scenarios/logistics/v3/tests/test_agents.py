"""Agentes da v3 sem runtime, sem Docker e sem LLM: domínio, deliberação,
executor, planejadores substitutos e o laço imitado em processo."""
import os
import unittest
from unittest.mock import patch

from ariadne_sdk import PlannerResponse, Task
from studies.scenarios.logistics.v2.domain.world import execute, initial
from studies.scenarios.logistics.v3.agents.delivery.main import make_agent as delivery_agent
from studies.scenarios.logistics.v3.agents.execute.main import make_agent as execute_agent
from studies.scenarios.logistics.v3.agents.planner.main import make_agent as planner_agent
from studies.scenarios.logistics.v3.agents.single_llm.main import make_agent as single_llm_agent
from studies.scenarios.logistics.v3.domain.adapters import (
    DELIVERY_CAPABILITY, EXECUTE_CAPABILITY, EXECUTE_STEP_ID, PLANNER_CAPABILITY, SINGLE_LLM_CAPABILITY,
    WorldView, delivery_step, execute_step, mission_context, mission_goal, order_view, restore_integers,
)
from studies.scenarios.logistics.v3.domain.cases import case_reference, find_case, incidents_for, load_cases
from studies.scenarios.logistics.v3.mission import episode_metrics, mission_for
from studies.scenarios.logistics.v3.tests.fake_loop import run_mission


def delivery_task(state, order_id, **hints):
    step = delivery_step(order_view(state, order_id), state, **hints)
    return Task(task_id=f'deliver-{order_id}', goal=step['goal'], type=step['type'], payload=step['payload'],
                required_capabilities=(DELIVERY_CAPABILITY,), bdi={'goal': step['bdi_goal']})


def planner_task(case, planner, *, context=None, history=()):
    payload = {'mission_id': 'm1', 'goal': mission_goal(case), 'round': len(history) + 1,
               'context': context or mission_context(case), 'history': list(history),
               'available_capabilities': [{'capability_id': DELIVERY_CAPABILITY, 'agent_count': 3},
                                          {'capability_id': EXECUTE_CAPABILITY, 'agent_count': 1}],
               'limits': {'max_rounds': 20, 'max_parallel': 3}}
    return Task(task_id='plan', goal=payload['goal'], type='MISSION_PLANNING', payload=payload,
                required_capabilities=tuple(planner.capabilities))


class DomainAdapterTests(unittest.TestCase):
    def test_cases_come_from_v2_datasets_and_incidents_stay_out_of_the_context(self):
        cases = load_cases('all')
        self.assertEqual(len(cases), 20)
        case = find_case('road-block')
        context = mission_context(case)
        self.assertNotIn('incidents', context)
        self.assertNotIn('incidents', context['state'])
        self.assertEqual(incidents_for(case_reference(case)), case['incidents'])
        self.assertIn('Pedido o1', mission_goal(case))
        with self.assertRaises(ValueError):
            load_cases('basic', ['missing'])

    def test_restore_integers_undoes_struct_doubles(self):
        self.assertEqual(restore_integers({'a': 65.0, 'b': [1.5, 2.0], 'c': True}), {'a': 65, 'b': [1.5, 2], 'c': True})

    def test_world_view_adds_history_and_summarizes(self):
        state = initial(find_case('easy'))
        view = WorldView({key: value for key, value in state.items() if key != 'history'})
        self.assertEqual(view['history'], [])
        self.assertIn('pending=1', str(view))
        self.assertFalse(execute(view.snapshot(), [])['reason'])

    def test_execute_step_binds_each_delivery_output_into_proposals(self):
        state = initial(find_case('easy'))
        step = execute_step(state, case_reference(find_case('easy')), delivery_step_ids=['deliver-o1'])
        self.assertEqual(step['depends_on'], ['deliver-o1'])
        self.assertEqual(step['input_bindings'], [{'source_step_id': 'deliver-o1', 'source_path': 'output',
                                                   'target_field': 'proposals.deliver-o1'}])
        self.assertNotIn('history', delivery_step(order_view(state, 'o1'), state)['payload']['state'])


class DeliveryAgentTests(unittest.TestCase):
    def test_direct_delivery_is_chosen_with_a_visible_trace(self):
        state = initial(find_case('easy'))
        result = delivery_agent().handle(delivery_task(state, 'o1'))
        self.assertEqual(result.status, 'TASK_STATUS_COMPLETED')
        self.assertEqual(result.metadata['selected_plan'], 'direct_delivery')
        trace = result.metadata['bdi_trace']
        self.assertEqual(trace['final_status'], 'achieved')
        self.assertGreaterEqual(trace['cycle_count'], 5)
        self.assertIn('reach(', ''.join(cycle['goal'] for cycle in trace['cycles']))
        self.assertTrue(result.output['feasible'])
        self.assertEqual([a['type'] for a in result.output['actions']], ['LOAD', 'MOVE', 'DELIVER'])
        outcome = execute(state, result.output['actions'])
        self.assertFalse(outcome['reason'])
        self.assertIn('o1', outcome['state']['deliveries'])

    def test_recharge_plan_when_battery_is_short(self):
        state = initial(find_case('recharge'))
        result = delivery_agent().handle(delivery_task(state, 'o1'))
        self.assertEqual(result.metadata['selected_plan'], 'recharge_then_deliver')
        self.assertIn('RECHARGE', [a['type'] for a in result.output['actions']])
        self.assertFalse(execute(state, result.output['actions'])['reason'])

    def test_transfer_from_disabled_vehicle_after_breakdown(self):
        case = find_case('vehicle-loss')
        state = execute(initial(case), [{'type': 'LOAD', 'vehicle': 'van1', 'order': 'o1', 'depot': 'north'}])['state']
        state['vehicles']['van1']['available'] = False
        result = delivery_agent().handle(delivery_task(state, 'o1', vehicle='van2'))
        self.assertEqual(result.metadata['selected_plan'], 'transfer_from_disabled_vehicle')
        self.assertEqual(result.output['vehicle'], 'van2')
        self.assertIn('TRANSFER', [a['type'] for a in result.output['actions']])
        self.assertFalse(execute(state, result.output['actions'])['reason'])

    def test_infeasible_order_completes_with_no_applicable_plan(self):
        state = initial(find_case('capacity-impossible'))
        result = delivery_agent().handle(delivery_task(state, 'o1'))
        self.assertEqual(result.status, 'TASK_STATUS_COMPLETED')
        self.assertFalse(result.output['feasible'])
        self.assertEqual(result.output['final_status'], 'no_applicable_plan')
        self.assertTrue(result.metadata['infeasible'])
        self.assertIn('nenhum plano', result.output['reason'])

    def test_invalid_payload_fails_the_task(self):
        result = delivery_agent().handle(Task(task_id='x', goal='deliver', payload={'order': {'id': 'o1'}},
                                              required_capabilities=(DELIVERY_CAPABILITY,)))
        self.assertEqual(result.status, 'TASK_STATUS_FAILED')
        self.assertEqual(result.error_code, 'ERROR_CODE_INVALID_TASK')


class ExecuteAgentTests(unittest.TestCase):
    def run_execute(self, case, state, proposals):
        payload = {'state': state, 'case': case_reference(case), 'proposals': proposals,
                   'order_sequence': list(proposals)}
        # Agent.handle devolve o mapping do handler; o SDK o embrulha em TaskResult ao servir.
        return execute_agent().handle(Task(task_id='exec', goal='execute', payload=payload,
                                           required_capabilities=(EXECUTE_CAPABILITY,)))

    def test_applies_valid_and_rejects_invalid_proposals(self):
        case = find_case('easy')
        state = initial(case)
        good = delivery_agent().handle(delivery_task(state, 'o1')).output
        bad = {'feasible': True, 'order': 'o1', 'actions': [{'type': 'MOVE', 'vehicle': 'van2', 'from': 'A', 'to': 'B'}]}
        output = self.run_execute(case, state, {'bad': bad, 'good': good})
        applied = {item['step_id']: item for item in output['applied']}
        self.assertEqual(applied['bad']['status'], 'rejected')
        self.assertEqual(applied['good']['status'], 'applied')
        self.assertTrue(output['all_delivered'])
        self.assertEqual(output['metrics']['rejected_actions'], 1)
        self.assertEqual(output['state']['history'][0]['accepted'], False)

    def test_fires_incidents_before_the_next_action_and_stops(self):
        case = find_case('road-block')
        state = initial(case)
        proposal = delivery_agent().handle(delivery_task(state, 'o1')).output
        output = self.run_execute(case, state, {'deliver-o1': proposal})
        self.assertEqual(len(output['incidents']), 1)
        self.assertEqual(output['state']['accepted_actions'], case['incidents'][0]['after_actions'])
        self.assertEqual(output['feedback']['reason'], 'incident requires revision')
        self.assertEqual(output['applied'][0]['status'], 'incident')

    def test_skips_infeasible_proposals_and_requires_state(self):
        case = find_case('easy')
        output = self.run_execute(case, initial(case), {'deliver-o1': {'feasible': False, 'order': 'o1', 'actions': [], 'reason': 'none'}})
        self.assertEqual(output['applied'][0]['status'], 'skipped')
        with self.assertRaises(ValueError):
            execute_agent().handle(Task(task_id='e', goal='x', payload={}, required_capabilities=(EXECUTE_CAPABILITY,)))


class PlannerSubstituteTests(unittest.TestCase):
    def test_cooperative_substitute_plans_one_delivery_step_per_order_plus_execute(self):
        case = find_case('two-orders')
        planner = planner_agent(demo=True)
        self.assertEqual(planner.capabilities, [PLANNER_CAPABILITY])
        result = planner.handle(planner_task(case, planner))
        self.assertEqual(result.status, 'TASK_STATUS_COMPLETED', result.error_message)
        self.assertEqual(result.metadata['provider'], 'deterministic-integration-substitute')
        response = PlannerResponse.from_output(result.output)
        self.assertEqual(response.action, 'PLAN')
        steps = {step['step_id']: step for step in response.plan['steps']}
        self.assertEqual(set(steps), {'deliver-o1', 'deliver-o2', EXECUTE_STEP_ID})
        self.assertEqual(steps['deliver-o1']['required_capabilities'], [DELIVERY_CAPABILITY])
        self.assertEqual(steps['deliver-o1']['payload']['order']['id'], 'o1')
        self.assertEqual(sorted(steps[EXECUTE_STEP_ID]['depends_on']), ['deliver-o1', 'deliver-o2'])
        self.assertEqual(response.plan['final_step_id'], EXECUTE_STEP_ID)
        vehicles = {steps[s]['payload'].get('vehicle') for s in ('deliver-o1', 'deliver-o2')}
        self.assertEqual(len(vehicles), 2)

    def test_cooperative_planner_answers_done_without_a_model_when_all_delivered(self):
        case = find_case('easy')
        planner = planner_agent(demo=True)
        state = initial(case)
        state['deliveries'] = {'o1': {'time': 5, 'on_time': True, 'vehicle': 'van1'}}
        context = {**mission_context(case), 'state': state}
        result = planner.handle(planner_task(case, planner, context=context))
        self.assertEqual(result.metadata['shortcut'], 'all_delivered')
        response = PlannerResponse.from_output(result.output)
        self.assertEqual(response.action, 'DONE')
        self.assertEqual(response.output['metrics']['delivered'], 1)

    def test_single_llm_substitute_plans_one_execute_step_with_inline_actions(self):
        case = find_case('easy')
        planner = single_llm_agent(demo=True)
        self.assertEqual(planner.capabilities, [SINGLE_LLM_CAPABILITY])
        result = planner.handle(planner_task(case, planner))
        self.assertEqual(result.status, 'TASK_STATUS_COMPLETED', result.error_message)
        response = PlannerResponse.from_output(result.output)
        self.assertEqual(response.action, 'PLAN')
        self.assertEqual([step['step_id'] for step in response.plan['steps']], [EXECUTE_STEP_ID])
        step = response.plan['steps'][0]
        self.assertEqual(step['required_capabilities'], [EXECUTE_CAPABILITY])
        self.assertTrue(step['payload']['proposals']['single-llm']['actions'])
        self.assertEqual(step['input_bindings'], [])

    def test_invalid_planner_request_fails_without_calling_a_model(self):
        planner = planner_agent(demo=True)
        result = planner.handle(Task(task_id='p', goal='x', payload={'unknown': 1}, required_capabilities=(PLANNER_CAPABILITY,)))
        self.assertEqual(result.status, 'TASK_STATUS_FAILED')
        self.assertEqual(result.error_code, 'ERROR_CODE_INVALID_TASK')

    def test_agents_declare_in_demo_mode_from_the_environment(self):
        with patch.dict(os.environ, {'LOGISTICS_V3_DEMO': '1'}, clear=True):
            self.assertEqual(planner_agent().runtime, 'logistics-v3-demo')
            self.assertEqual(single_llm_agent().runtime, 'logistics-v3-demo')
            self.assertEqual(delivery_agent().capabilities, [DELIVERY_CAPABILITY])
            self.assertEqual(execute_agent().capabilities, [EXECUTE_CAPABILITY])


class FakeLoopTests(unittest.TestCase):
    """O laço imitado reproduz bindings, dependências e mesclagem do contexto."""

    EXPECTED = {'easy': 1, 'two-orders': 2, 'one-vehicle': 2, 'recharge': 1, 'priority-deadlines': 3,
                'road-block': 2, 'vehicle-loss': 2, 'capacity-impossible': 1, 'combined-incidents': 3}

    def run_case(self, case_id, configuration):
        case = find_case(case_id)
        planner = planner_agent(demo=True) if configuration == 'ariadne-v3' else single_llm_agent(demo=True)
        agents = {DELIVERY_CAPABILITY: delivery_agent(), EXECUTE_CAPABILITY: execute_agent()}
        return run_mission(planner, agents, mission_goal(case), mission_context(case))

    def test_basic_cases_complete_in_both_configurations(self):
        for case_id, delivered in self.EXPECTED.items():
            for configuration in ('ariadne-v3', 'single-llm-v3'):
                with self.subTest(case=case_id, configuration=configuration):
                    status, context, rounds, _ = self.run_case(case_id, configuration)
                    self.assertEqual(status, 'COMPLETED')
                    self.assertEqual(len(context['state']['deliveries']), delivered)
                    self.assertLessEqual(len(rounds), 6)

    def test_incident_flows_through_the_context_and_triggers_a_transfer(self):
        status, context, rounds, planner_results = self.run_case('vehicle-loss', 'ariadne-v3')
        self.assertEqual(status, 'COMPLETED')
        self.assertEqual(rounds[0]['step_results'][-1]['result']['output']['incidents'][0]['type'], 'unavailable')
        plans = [step['result']['metadata'].get('selected_plan') for item in rounds for step in item['step_results']]
        self.assertIn('transfer_from_disabled_vehicle', plans)
        self.assertFalse(context['state']['vehicles']['van1']['available'])
        self.assertEqual(PlannerResponse.from_output(planner_results[-1].output).action, 'DONE')

    def test_mission_declaration_and_metrics(self):
        case = find_case('easy')
        mission = mission_for(case, 'ariadne-v3').validate()
        self.assertEqual(mission.limits.max_parallel, 3)
        self.assertEqual(mission.retry_policy['exclude_failed_agent'], True)
        with self.assertRaises(ValueError):
            mission_for(case, 'ariadne')
        status, context, rounds, _ = self.run_case('easy', 'ariadne-v3')
        document = {'status': 'MISSION_STATUS_COMPLETED', 'context': context, 'output': {'summary': 'ok'},
                    'created_at': '2026-10-27T10:00:00Z', 'completed_at': '2026-10-27T10:00:02.500Z',
                    'rounds': [{'round': 1, 'action': 'PLANNER_ACTION_PLAN', 'result': {'step_results': r['step_results']},
                                'planner_result': {'metadata': {'provider': 'openai', 'usage': {'input_tokens': 10, 'output_tokens': 5}}}}
                               for r in rounds]}
        row = episode_metrics(document, case=case, configuration='ariadne-v3', demo=False)
        self.assertEqual((row['delivered'], row['total_orders'], row['result']), (1, 1, 'complete'))
        self.assertEqual((row['llm_calls'], row['input_tokens'], row['output_tokens']), (1, 10, 5))
        self.assertGreater(row['bdi_cycles'], 0)
        self.assertEqual(row['parallel_steps_per_round'], [1])
        self.assertEqual(row['wall_seconds'], 2.5)
        self.assertEqual(row['reassignments'], 0)


if __name__ == '__main__':
    unittest.main()
