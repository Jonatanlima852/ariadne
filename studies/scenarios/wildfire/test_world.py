"""Regras do mundo, sem runtime: fogo, ações, eventos, verdade oculta e tamanho do estado."""
import json
import unittest

from studies.scenarios.wildfire.domain import world
from studies.scenarios.wildfire.domain.cases import CASES, find_case, load_cases


def tiny(**overrides):
    case = {'id': 'tiny', 'suite': 'basic', 'title': 'tiny', 'width': 8, 'height': 8, 'horizon': 10,
            'wind': {'toward': 'E', 'speed': 1}, 'bases': {'B1': '0,0'}, 'drones': 1, 'fires': {'4,4': 1},
            'obstacles': [], 'structures': {}, 'briefing': '', 'events': [],
            'rules': {'speed': 3, 'battery_capacity': 30, 'water_capacity': 3, 'drop_power': 2, 'recharge': 15}}
    case.update(overrides)
    return case


class FireTests(unittest.TestCase):
    def test_fire_grows_spreads_downwind_and_turns_to_ash(self):
        case = tiny()
        state = world.initial_state(case)
        state = world.step(state, [], case)['state']          # 4,4 -> 2
        self.assertEqual(state['fires'], {'4,4': 2})
        state = world.step(state, [], case)['state']          # 4,4 -> 3 and ignites 5,4 (downwind, E)
        self.assertEqual(state['fires'], {'4,4': 3, '5,4': 1})
        out = world.step(state, [], case)                     # 4,4 -> ash, laterals 4,3 and 4,5 ignite
        self.assertEqual(out['state']['ash'], ['4,4'])
        self.assertEqual(out['state']['fires'], {'4,3': 1, '4,5': 1, '5,4': 2})
        self.assertEqual(out['fire']['ash'], ['4,4'])
        self.assertEqual(out['state']['tick'], 3)

    def test_wind_speed_two_spreads_downwind_every_tick_and_never_upwind(self):
        case = tiny(wind={'toward': 'S', 'speed': 2})
        state = world.initial_state(case)
        state = world.step(state, [], case)['state']
        self.assertEqual(state['fires'], {'4,4': 2, '4,5': 1})
        for _ in range(6):
            state = world.step(state, [], case)['state']
        self.assertFalse(any(world.coords(c)[1] < 4 for c in state['fires']), 'fire went upwind')

    def test_obstacles_bases_and_ash_do_not_burn_but_structures_do(self):
        case = tiny(fires={'3,4': 3}, obstacles=['4,4'], bases={'B1': '3,5'}, structures={'3,3': 'school'})
        state = world.initial_state(case)
        out = world.step(state, [], case)
        self.assertNotIn('4,4', out['state']['fires'])
        self.assertNotIn('3,5', out['state']['fires'])
        self.assertEqual(out['state']['fires'], {'3,3': 1})
        self.assertEqual(out['state']['structures']['3,3']['condition'], 'burning')
        for _ in range(3):
            out = world.step(out['state'], [], case)
        self.assertEqual(out['state']['structures']['3,3']['condition'], 'burned')
        self.assertEqual(out['metrics']['structures_burned'], 1)


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.case = tiny(fires={'2,0': 1, '3,0': 3}, bases={'B1': '0,0', 'B2': '7,7'}, drones=2)
        self.state = world.initial_state(self.case)

    def test_move_follows_the_path_and_stops_at_speed_or_battery(self):
        out = world.step(self.state, [{'drone': 'd1', 'action': 'move', 'target': '5,0'}], self.case)
        entry = out['applied'][0]
        self.assertEqual((entry['status'], entry['moved_to'], entry['cells'], entry['arrived']), ('applied', '3,0', 3, False))
        self.assertEqual(out['state']['drones']['d1']['battery'], 27)
        low = world.initial_state(self.case)
        low['drones']['d1']['battery'] = 1
        out = world.step(low, [{'drone': 'd1', 'action': 'move', 'target': '5,0'}], self.case)
        self.assertEqual(out['applied'][0]['moved_to'], '1,0')
        self.assertEqual(out['state']['drones']['d1']['condition'], 'lost', 'zero battery away from a base')
        self.assertEqual(out['lost'], ['d1'])

    def test_move_rejections(self):
        case = tiny(obstacles=['1,0', '0,1'])
        state = world.initial_state(case)
        reasons = []
        for action in ({'drone': 'd1', 'action': 'move', 'target': '0,0'},
                       {'drone': 'd1', 'action': 'move', 'target': '1,0'},
                       {'drone': 'd1', 'action': 'move', 'target': '9,9'},
                       {'drone': 'd1', 'action': 'move', 'target': 'north'},
                       {'drone': 'd9', 'action': 'move', 'target': '2,2'},
                       {'drone': 'd1', 'action': 'fly', 'target': '2,2'}):
            entry = world.step(state, [action], case)['applied'][0]
            self.assertEqual(entry['status'], 'rejected', action)
            reasons.append(entry['reason'])
        self.assertIn('already at', reasons[0])
        self.assertIn('no path', reasons[1])
        self.assertIn('no path', reasons[2])
        self.assertIn('requires target', reasons[3])
        self.assertIn('unknown drone', reasons[4])
        self.assertIn('unknown action', reasons[5])

    def test_drop_needs_adjacency_water_and_fire(self):
        state = world.initial_state(self.case)
        state['drones']['d1']['at'] = '2,1'
        out = world.step(state, [{'drone': 'd1', 'action': 'drop', 'target': '3,0'}], self.case)
        entry = out['applied'][0]
        self.assertEqual((entry['status'], entry['intensity_after'], entry['extinguished']), ('applied', 1, False))
        self.assertEqual(out['state']['drones']['d1']['water'], 2)
        self.assertEqual(out['state']['drones']['d1']['battery'], 29)
        self.assertEqual(out['state']['fires']['3,0'], 2, 'intensity 3 minus 2 then grows by one')
        far = world.step(state, [{'drone': 'd1', 'action': 'drop', 'target': '5,5'}], self.case)['applied'][0]
        self.assertIn('not adjacent', far['reason'])
        cold = world.step(state, [{'drone': 'd1', 'action': 'drop', 'target': '2,2'}], self.case)['applied'][0]
        self.assertIn('no fire', cold['reason'])
        state['drones']['d1']['water'] = 0
        dry = world.step(state, [{'drone': 'd1', 'action': 'drop', 'target': '2,0'}], self.case)['applied'][0]
        self.assertIn('no water', dry['reason'])

    def test_drop_extinguishes_and_counts(self):
        state = world.initial_state(self.case)
        state['drones']['d1']['at'] = '1,1'
        out = world.step(state, [{'drone': 'd1', 'action': 'drop', 'target': '2,0'}], self.case)
        self.assertTrue(out['applied'][0]['extinguished'])
        self.assertNotIn('2,0', out['state']['fires'])
        self.assertEqual(out['state']['counters']['extinguished'], 1)
        self.assertEqual(out['metrics']['drops'], 1)

    def test_resupply_only_on_a_usable_base_and_one_action_per_drone(self):
        state = world.initial_state(self.case)
        state['drones']['d1'].update(water=0, battery=5)
        out = world.step(state, [{'drone': 'd1', 'action': 'resupply'},
                                 {'drone': 'd1', 'action': 'hold'}], self.case)
        self.assertEqual(out['applied'][0]['status'], 'applied')
        self.assertEqual(out['state']['drones']['d1']['water'], 3)
        self.assertEqual(out['state']['drones']['d1']['battery'], 20)
        self.assertEqual(out['applied'][1]['status'], 'rejected')
        self.assertIn('second action', out['applied'][1]['reason'])
        self.assertEqual(out['applied'][2]['status'], 'idle', 'd2 had no action')
        self.assertEqual(out['state']['counters'], {'accepted': 1, 'rejected': 1, 'idle': 1, 'drops': 0,
                                                     'extinguished': 0, 'moved_cells': 0})
        state['drones']['d1']['at'] = '4,4'
        away = world.step(state, [{'drone': 'd1', 'action': 'resupply'}], self.case)['applied'][0]
        self.assertIn('not on a base', away['reason'])

    def test_radio_only_base_failure_rejects_resupply_and_hidden_structure_scores(self):
        case = tiny(bases={'B1': '0,0', 'B2': '7,7'}, fires={'5,5': 1}, events=[
            {'tick': 1, 'radio': 'B1 explodiu; hospital em (6,5)',
             'effects': {'disable_bases': ['B1'], 'hidden_structures': {'6,5': 'hospital'}}}])
        state = world.initial_state(case)
        out = world.step(state, [], case)
        self.assertEqual(out['events'], [{'tick': 1, 'radio': 'B1 explodiu; hospital em (6,5)'}])
        self.assertEqual(out['state']['radio'][-1]['text'], 'B1 explodiu; hospital em (6,5)')
        self.assertTrue(out['state']['bases']['B1']['active'], 'telemetry does not reflect the radio')
        self.assertEqual(world.truth_at(case, 1), {'disabled_bases': ['B1'], 'hidden_structures': {'6,5': 'hospital'}})
        self.assertEqual(world.truth_at(case, 0), {'disabled_bases': [], 'hidden_structures': {}})
        again = world.step(out['state'], [{'drone': 'd1', 'action': 'resupply'}], case)
        self.assertIn('out of service', again['applied'][0]['reason'])
        self.assertEqual(again['metrics']['structures_total'], 1)
        self.assertTrue(again['metrics']['structures']['6,5']['hidden'])
        self.assertNotIn('6,5', again['state']['structures'], 'hidden structure never enters the state')

    def test_visible_effects_wind_and_offline(self):
        case = tiny(drones=2, bases={'B1': '0,0'}, events=[
            {'tick': 1, 'radio': 'vento e enlace', 'effects': {'wind': {'toward': 'S', 'speed': 2}, 'offline_drones': ['d2']}}])
        out = world.step(world.initial_state(case), [], case)
        self.assertEqual(out['state']['wind'], {'toward': 'S', 'speed': 2})
        self.assertEqual(out['state']['drones']['d2']['condition'], 'offline')
        ignored = world.step(out['state'], [{'drone': 'd2', 'action': 'hold'}], case)['applied'][0]
        self.assertIn('offline', ignored['reason'])


class CaseTests(unittest.TestCase):
    def test_cases_are_consistent_and_fit_the_step_payload_limit(self):
        for case in CASES:
            state = world.initial_state(case)
            self.assertLess(len(json.dumps(state)), 8 * 1024, case['id'])
            for c in list(case['fires']) + list(case['obstacles']) + list(case['structures']) + list(case['bases'].values()):
                self.assertTrue(world.in_bounds(state, world.coords(c)), (case['id'], c))
            for event in case['events']:
                self.assertLess(int(event['tick']), int(case['horizon']), case['id'])
                for drone_id in (event.get('effects') or {}).get('offline_drones') or []:
                    self.assertIn(drone_id, state['drones'], case['id'])
            for _ in range(case['horizon']):
                state = world.step(state, [], case)['state']
            self.assertLess(len(json.dumps(state)), 24 * 1024, case['id'])
            self.assertTrue(world.is_done(state))

    def test_suites_and_overrides(self):
        self.assertEqual([c['id'] for c in load_cases('basic')], ['single-fire', 'three-fronts', 'windy'])
        self.assertEqual(len(load_cases('all')), len(CASES))
        self.assertEqual(find_case('storm', drones=3)['drones'], 3)
        self.assertEqual(len(world.initial_state(find_case('storm', drones=3))['drones']), 3)
        with self.assertRaises(ValueError):
            load_cases('nope')
        with self.assertRaises(ValueError):
            find_case('nope')


if __name__ == '__main__':
    unittest.main()
