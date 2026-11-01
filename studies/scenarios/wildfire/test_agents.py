"""Agentes do wildfire sem runtime: drone BDI, mundo, comandante, piloto e o laço em processo.

Usa os substitutos determinísticos (``demo=True``); nenhuma chamada LLM é feita.
"""
import json
from pathlib import Path
import tempfile
import unittest

from ariadne_sdk import PlannerResponse, Task
from studies.scenarios.wildfire import analysis
from studies.scenarios.wildfire.agents.drone.main import make_agent as drone_agent
from studies.scenarios.wildfire.agents.planner.main import make_agent as commander_agent
from studies.scenarios.wildfire.agents.single_llm.main import make_agent as pilot_agent
from studies.scenarios.wildfire.agents.world.main import make_agent as world_agent
from studies.scenarios.wildfire.domain.adapters import WORLD_STEP_ID, mission_context, mission_goal
from studies.scenarios.wildfire.domain.cases import find_case
from studies.scenarios.wildfire.domain.world import initial_state
from studies.scenarios.wildfire.loop import MAX_STEP_PAYLOAD_BYTES, simulate
from studies.scenarios.wildfire.mission import (
    CONFIGURATIONS, Settings, agents_for, check_mission, episode_metrics, limits, mission_for, settings_from_env,
)


def drone_task(state, drone_id, order=None, command=None):
    return Task(task_id='t', goal='act', payload={'state': state, 'drone': drone_id, 'order': order or {}, 'command': command or {}})


def planner_task(case, configuration, context=None, history=(), round_number=1):
    request = {'mission_id': 'm-1', 'goal': mission_goal(case), 'round': round_number,
               'context': context or mission_context(case), 'history': list(history),
               'available_capabilities': [{'capability_id': 'wildfire-drone', 'agent_count': 4}],
               'limits': limits(case).to_dict()}
    return Task(task_id=f'plan-{round_number}', goal=request['goal'], type='MISSION_PLANNING', payload=request,
                required_capabilities=(CONFIGURATIONS[configuration],))


class DroneTests(unittest.TestCase):
    def setUp(self):
        self.agent = drone_agent()
        self.case = find_case('three-fronts')
        self.state = initial_state(self.case)

    def decide(self, mutate=None, drone='d1', **kw):
        state = json.loads(json.dumps(self.state))
        if mutate:
            mutate(state)
        result = self.agent.handle(drone_task(state, drone, **kw))
        self.assertEqual(result.status, 'TASK_STATUS_COMPLETED')
        self.assertEqual(result.output['drone'], drone)
        return result

    def test_fresh_drone_attacks_a_fire_and_leaves_a_trace(self):
        result = self.decide()
        self.assertEqual(result.metadata['selected_plan'], 'attack_nearest')
        self.assertEqual(result.output['action'], 'move')
        self.assertIn(result.output['target'], self.state['fires'])
        trace = result.metadata['bdi_trace']
        self.assertEqual(trace['final_status'], 'achieved')
        self.assertTrue(any(cycle['action'].startswith('act(search_path') for cycle in trace['cycles']))
        self.assertTrue(any('world(t=0' in belief for belief in trace['cycles'][0]['beliefs_added']),
                        'the world belief is summarised, not dumped')

    def test_two_drones_on_the_same_base_pick_different_fires(self):
        first = self.decide(drone='d1').output['target']
        second = self.decide(drone='d3').output['target']
        self.assertNotEqual(first, second)

    def test_adjacent_drone_drops_water(self):
        result = self.decide(lambda s: s['drones']['d1'].update(at='5,9'))
        self.assertEqual((result.output['action'], result.output['target']), ('drop', '4,9'))

    def test_reserve_and_water_send_the_drone_back(self):
        low = self.decide(lambda s: s['drones']['d1'].update(at='8,8', battery=7))
        self.assertEqual((low.metadata['selected_plan'], low.output['action'], low.output['target']), ('return_to_base', 'move', '13,13'))
        dry = self.decide(lambda s: s['drones']['d1'].update(at='8,8', water=0))
        self.assertEqual(dry.metadata['selected_plan'], 'return_to_base')
        self.assertIn('no water', dry.output['reason'])

    def test_resupplies_on_a_usable_base_and_avoids_bases_the_commander_disabled(self):
        here = self.decide(lambda s: s['drones']['d1'].update(water=1))
        self.assertEqual((here.metadata['selected_plan'], here.output['action']), ('resupply_here', 'resupply'))
        other = self.decide(lambda s: s['drones']['d1'].update(at='8,8', water=0), command={'disabled_bases': ['B1']})
        self.assertEqual(other.output['target'], '13,13', 'B1 is closer but the radio killed it')
        none = self.decide(lambda s: s['drones']['d1'].update(at='8,8', water=0), command={'disabled_bases': ['B1', 'B2']})
        self.assertEqual((none.metadata['selected_plan'], none.output['action']), ('hold_position', 'hold'))

    def test_orders_from_the_commander(self):
        hold = self.decide(order={'objective': 'hold'})
        self.assertEqual((hold.metadata['selected_plan'], hold.output['action']), ('hold_ordered', 'hold'))
        back = self.decide(lambda s: s['drones']['d1'].update(at='8,8'), order={'objective': 'return'})
        self.assertEqual(back.metadata['selected_plan'], 'return_to_base')
        attack = self.decide(order={'objective': 'attack', 'target': '12,11'})
        self.assertEqual((attack.metadata['selected_plan'], attack.output['target']), ('attack_target', '12,11'))
        guard = self.decide(lambda s: s['fires'].clear() or s['fires'].update({'14,2': 1}),
                            order={'objective': 'protect', 'target': '4,13'})
        self.assertEqual((guard.metadata['selected_plan'], guard.output['target']), ('guard_target', '4,13'))
        # Célula prioritária: vai ao drone mais próximo dela (d2, em B2); d4, na mesma base, cede e pega outra.
        priority = self.decide(drone='d2', command={'priority_cells': ['12,11']})
        self.assertEqual(priority.output['target'], '12,11')
        yielded = self.decide(drone='d4', command={'priority_cells': ['12,11']})
        self.assertNotEqual(yielded.output['target'], '12,11')
        far = self.decide(drone='d1', command={'priority_cells': ['12,11']})
        self.assertNotEqual(far.output['target'], '12,11', 'd1 is farther than both B2 drones and yields the cell')

    def test_offline_lost_and_invalid_payloads_still_complete_with_hold(self):
        offline = self.decide(lambda s: s['drones']['d1'].update(condition='offline'))
        self.assertEqual((offline.metadata['selected_plan'], offline.output['action']), ('stand_down', 'hold'))
        broken = self.agent.handle(Task(task_id='t', goal='act', payload={'state': {}, 'drone': 'd1'}))
        self.assertEqual(broken.status, 'TASK_STATUS_COMPLETED')
        self.assertEqual((broken.output['action'], broken.output['plan']), ('hold', 'fallback'))
        self.assertTrue(broken.metadata['fallback'])


class WorldAgentTests(unittest.TestCase):
    def test_applies_bound_decisions_in_order_and_reports_only_the_radio(self):
        case = find_case('hospital-alert')
        state = initial_state(case)
        state['tick'] = 4
        state['drones']['d1'].update(at='9,2')
        payload = {'state': state, 'case': {'id': case['id'], 'drones': case['drones']},
                   'order_sequence': ['drone-d1', 'drone-d2'],
                   'actions': {'drone-d1': {'drone': 'd1', 'action': 'drop', 'target': '9,3'},
                               'drone-d2': {'drone': 'd2', 'action': 'move', 'target': '8,10'}}}
        result = world_agent().handle(Task(task_id='w', goal='world', payload=payload))
        self.assertEqual(result['tick'], 5)
        self.assertEqual([entry['drone'] for entry in result['applied']][:2], ['d1', 'd2'])
        self.assertTrue(result['applied'][0]['extinguished'])
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(set(result['events'][0]), {'tick', 'radio'}, 'effects never leave the executor')
        self.assertEqual(result['state']['wind'], {'toward': 'E', 'speed': 1})
        self.assertTrue(result['state']['bases']['B1']['active'], 'telemetry keeps the dead base active')
        self.assertTrue(result['metrics']['structures']['12,3']['hidden'])

    def test_pilot_actions_inline(self):
        case = find_case('single-fire')
        state = initial_state(case)
        payload = {'state': state, 'case': {'id': case['id'], 'drones': 2}, 'order_sequence': ['pilot'],
                   'actions': {'pilot': {'actions': [{'drone': 'd1', 'action': 'move', 'target': '6,6'},
                                                     {'drone': 'd2', 'action': 'fly', 'target': '6,6'}]}}}
        result = world_agent().handle(Task(task_id='w', goal='world', payload=payload))
        self.assertEqual([entry['status'] for entry in result['applied']], ['applied', 'rejected'])
        self.assertEqual(result['state']['drones']['d1']['at'], '5,1', 'four cells east along the BFS path')

    def test_rejects_payload_without_state(self):
        with self.assertRaises(ValueError):
            world_agent().handle(Task(task_id='w', goal='world', payload={'case': {'id': 'single-fire'}}))


class PlannerTests(unittest.TestCase):
    def test_commander_demo_builds_drone_steps_and_a_world_step_with_bindings(self):
        case = find_case('three-fronts')
        result = commander_agent(demo=True).handle(planner_task(case, 'ariadne'))
        self.assertEqual(result.status, 'TASK_STATUS_COMPLETED')
        self.assertEqual(result.metadata['provider'], 'deterministic-integration-substitute')
        response = PlannerResponse.from_output(result.output).validate()
        self.assertEqual(response.action, 'PLAN')
        steps = {step['step_id']: step for step in response.plan['steps']}
        self.assertEqual(set(steps), {'drone-d1', 'drone-d2', 'drone-d3', 'drone-d4', WORLD_STEP_ID})
        world = steps[WORLD_STEP_ID]
        self.assertEqual(sorted(world['depends_on']), ['drone-d1', 'drone-d2', 'drone-d3', 'drone-d4'])
        self.assertEqual(world['input_bindings'][0]['target_field'], 'actions.drone-d1')
        self.assertEqual(steps['drone-d1']['bdi_goal'], 'act')
        self.assertIn('order', steps['drone-d1']['payload'])
        self.assertEqual(response.context_update['command']['disabled_bases'], [])
        self.assertIn('d1', response.context_update['orders'])

    def test_commander_demo_reads_the_radio_into_beliefs(self):
        case = find_case('hospital-alert')
        context = mission_context(case)
        context['state']['tick'] = 5
        context['state']['radio'].append({'tick': 5, 'text': case['events'][0]['radio']})
        result = commander_agent(demo=True).handle(planner_task(case, 'ariadne', context=context, round_number=6))
        response = PlannerResponse.from_output(result.output)
        self.assertEqual(response.context_update['command']['disabled_bases'], ['B1'])
        self.assertEqual(response.context_update['command']['priority_cells'], ['12,3'])
        self.assertEqual(response.context_update['orders']['d1']['objective'], 'protect')

    def test_shortcuts_answer_done_without_a_model(self):
        case = find_case('single-fire')
        for configuration, agent in (('ariadne', commander_agent(demo=True)), ('single-llm', pilot_agent(demo=True))):
            context = mission_context(case)
            context['state']['fires'] = {}
            result = agent.handle(planner_task(case, configuration, context=context))
            self.assertEqual(result.metadata['shortcut'], 'all_fires_out')
            self.assertEqual(PlannerResponse.from_output(result.output).action, 'DONE')
            context = mission_context(case)
            context['state']['tick'] = case['horizon']
            result = agent.handle(planner_task(case, configuration, context=context))
            self.assertEqual(result.metadata['shortcut'], 'horizon_reached')

    def test_pilot_demo_builds_one_world_step_with_inline_actions(self):
        case = find_case('three-fronts')
        result = pilot_agent(demo=True).handle(planner_task(case, 'single-llm'))
        response = PlannerResponse.from_output(result.output).validate()
        self.assertEqual([step['step_id'] for step in response.plan['steps']], [WORLD_STEP_ID])
        actions = response.plan['steps'][0]['payload']['actions']['pilot']['actions']
        self.assertEqual(sorted(item['drone'] for item in actions), ['d1', 'd2', 'd3', 'd4'])

    def test_standing_orders_skip_the_model_when_nothing_changed(self):
        case = find_case('three-fronts')
        agent = commander_agent(demo=True, command_every=3)
        first = PlannerResponse.from_output(agent.handle(planner_task(case, 'ariadne')).output)
        context = {**mission_context(case), **first.context_update}
        context['state']['tick'] = 1
        quiet = [{'round': 1, 'action': 'PLANNER_ACTION_PLAN', 'status': 'WORKFLOW_STATUS_COMPLETED', 'planner_summary': '',
                  'step_results': [{'step_id': WORLD_STEP_ID, 'status': 'WORKFLOW_STEP_STATUS_COMPLETED',
                                    'result': {'output': {'applied': [], 'events': [], 'lost': [], 'fire': {}}}}]}]
        second = agent.handle(planner_task(case, 'ariadne', context=context, history=quiet, round_number=2))
        self.assertEqual(second.metadata['shortcut'], 'standing_orders')
        noisy = json.loads(json.dumps(quiet))
        noisy[0]['step_results'][0]['result']['output']['events'] = [{'tick': 1, 'radio': 'novidade'}]
        third = agent.handle(planner_task(case, 'ariadne', context=context, history=noisy, round_number=2))
        self.assertNotIn('shortcut', third.metadata)


class LocalLoopTests(unittest.TestCase):
    def test_settings_from_env(self):
        settings = settings_from_env({'WILDFIRE_CASE': 'storm', 'WILDFIRE_CONFIGURATION': 'single-llm', 'WILDFIRE_DEMO': '1',
                                      'WILDFIRE_DRONES': '3', 'WILDFIRE_DRONE_AGENTS': '2', 'WILDFIRE_COMMAND_EVERY': '2'})
        self.assertEqual((settings.case['drones'], settings.drone_agents, settings.command_every, settings.demo), (3, 2, 2, True))
        self.assertEqual(settings.to_dict()['execution_kind'], 'deterministic-integration-demo')
        self.assertEqual([agent.name for agent in agents_for(settings)], ['pilot', 'world'])
        self.assertEqual(len(agents_for(Settings(drone_agents=2))), 4)
        with self.assertRaises(ValueError):
            Settings(configuration='bdi-only')
        mission = mission_for(settings.case, 'single-llm')
        self.assertEqual(mission.limits.max_parallel, 3)
        self.assertLess(len(json.dumps(mission.context)), MAX_STEP_PAYLOAD_BYTES)

    def test_single_fire_is_contained_by_the_commander_and_drones(self):
        settings = Settings(case_id='single-fire', configuration='ariadne', demo=True)
        document = check_mission(simulate(settings), settings)
        row = episode_metrics(document, case=settings.case, configuration='ariadne', demo=True)
        self.assertEqual(row['result'], 'contained')
        self.assertEqual(row['fires_remaining'], 0)
        self.assertLess(row['ticks'], settings.case['horizon'])
        self.assertEqual(row['drones_lost'], 0)
        self.assertGreater(row['bdi_cycles'], 0)
        self.assertEqual(row['llm_calls'], 0, 'demo substitutes are not model calls')
        self.assertEqual(row['model_calls'], row['rounds'] - 1, 'every PLAN round consulted the substitute')
        self.assertEqual(row['curve'][0]['tick'], 0)
        self.assertEqual(len(row['curve']), row['rounds'])

    def test_hospital_alert_hybrid_keeps_the_hospital_and_the_pilot_hits_the_dead_base(self):
        rows = {}
        for configuration in ('ariadne', 'single-llm'):
            settings = Settings(case_id='hospital-alert', configuration=configuration, demo=True)
            document = check_mission(simulate(settings), settings)
            self.assertLessEqual(document['simulation']['max_step_payload_bytes'], MAX_STEP_PAYLOAD_BYTES)
            rows[configuration] = episode_metrics(document, case=settings.case, configuration=configuration, demo=True)
        self.assertEqual(rows['ariadne']['alert_structure_status'], 'intact')
        self.assertIsNotNone(rows['ariadne']['alert_reaction_ticks'])
        self.assertLess(rows['ariadne']['burned'], rows['single-llm']['burned'])
        self.assertLess(rows['ariadne']['rejected_actions'], rows['single-llm']['rejected_actions'],
                        'the demo pilot keeps asking the dead base for supplies')
        self.assertEqual(rows['single-llm']['bdi_cycles'], 0)

    def test_storm_runs_eight_drones_in_parallel_within_the_step_limit(self):
        settings = Settings(case_id='storm', configuration='ariadne', demo=True)
        document = check_mission(simulate(settings), settings)
        row = episode_metrics(document, case=settings.case, configuration='ariadne', demo=True)
        self.assertEqual(row['max_parallel_steps'], 8)
        self.assertEqual(row['drones_offline'], 2, 'the radio took two drones off the air at tick 12')
        self.assertLessEqual(row['ticks'], 20)
        self.assertGreaterEqual(row['ticks'], 13)

    def test_analysis_reads_runs_and_writes_tables_and_figures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, (case_id, configuration) in enumerate([('single-fire', 'ariadne'), ('single-fire', 'single-llm')]):
                settings = Settings(case_id=case_id, configuration=configuration, demo=True)
                run = root / 'runs' / f'ariadne-{index}'
                run.mkdir(parents=True)
                (run / 'manifest.json').write_text(json.dumps({'metadata': settings.to_dict()}), encoding='utf-8')
                (run / 'mission-result.json').write_text(json.dumps(simulate(settings)), encoding='utf-8')
            code = analysis.main([str(root), '--output', str(root / 'analysis'), '--no-plots'])
            self.assertEqual(code, 0)
            names = {path.name for path in (root / 'analysis').iterdir()}
            self.assertTrue({'results.json', 'observations.csv', 'comparison.md', 'curves-single-fire.svg', 'summary.svg',
                             'frames-single-fire-ariadne.svg', 'frames-single-fire-single-llm.svg'} <= names, names)
            rows = json.loads((root / 'analysis' / 'results.json').read_text(encoding='utf-8'))
            self.assertEqual({row['configuration'] for row in rows}, {'ariadne', 'single-llm'})
            self.assertNotIn('document', rows[0])
            report = (root / 'analysis' / 'comparison.md').read_text(encoding='utf-8')
            self.assertIn('single-fire', report)
            self.assertIn('Diferença pareada', report)


if __name__ == '__main__':
    unittest.main()
