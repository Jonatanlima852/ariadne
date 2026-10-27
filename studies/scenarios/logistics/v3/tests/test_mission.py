"""Integração real da missão v3 com os binários Go (ARIADNE_TEST_RUNTIME_DIR).

Usa LOGISTICS_V3_DEMO=1: substitutos determinísticos no lugar do modelo;
nenhuma chamada LLM, nenhum Docker.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from studies.scenarios.logistics.v3.domain.adapters import DELIVERY_CAPABILITY, EXECUTE_STEP_ID
from studies.scenarios.logistics.v3.domain.cases import find_case
from studies.scenarios.logistics.v3.mission import episode_metrics

ROOT = Path(__file__).resolve().parents[5]
RUNTIME = os.getenv('ARIADNE_TEST_RUNTIME_DIR')


def run_case(case_id, configuration):
    with tempfile.TemporaryDirectory() as temporary:
        completed = subprocess.run(
            [sys.executable, '-m', 'ariadne_sdk', 'run', 'studies/scenarios/logistics/v3/scenario.py',
             '--runtime-dir', str(Path(RUNTIME).resolve()), '--output', temporary, '--timeout', '300'],
            cwd=ROOT, capture_output=True, text=True, timeout=400,
            env={**os.environ, 'LOGISTICS_V3_DEMO': '1', 'LOGISTICS_V3_CASE': case_id,
                 'LOGISTICS_V3_CONFIGURATION': configuration})
        if completed.returncode != 0:
            raise AssertionError(completed.stdout + completed.stderr)
        run = next(Path(temporary).iterdir())
        return (json.loads((run / 'manifest.json').read_text()), json.loads((run / 'mission-result.json').read_text()))


@unittest.skipUnless(RUNTIME, 'set ARIADNE_TEST_RUNTIME_DIR to run real Go/Python integration')
class LogisticsV3MissionIntegrationTests(unittest.TestCase):
    def test_cooperative_mission_replans_after_a_breakdown(self):
        case = find_case('vehicle-loss')
        manifest, saved = run_case('vehicle-loss', 'ariadne-v3')
        self.assertEqual(manifest['mission']['planner_capability'], 'mission-planning')
        self.assertEqual(manifest['mission']['limits']['max_parallel'], 3)
        self.assertEqual(saved['status'], 'MISSION_STATUS_COMPLETED', saved.get('error'))
        rounds = saved['rounds']
        self.assertEqual(rounds[-1]['action'], 'PLANNER_ACTION_DONE')
        first = rounds[0]
        steps = {step['step_id']: step for step in first['result']['step_results']}
        self.assertIn(EXECUTE_STEP_ID, steps)
        delivery_steps = [step for sid, step in steps.items() if sid != EXECUTE_STEP_ID]
        self.assertEqual(len(delivery_steps), 2)
        for step in delivery_steps:
            self.assertEqual(step['task']['required_capabilities'], [DELIVERY_CAPABILITY])
            self.assertIn(step['result']['agent_id'], {'delivery-1', 'delivery-2', 'delivery-3'})
            self.assertGreaterEqual(step['result']['metadata']['bdi_trace']['cycle_count'], 1)
        # The bindings delivered each proposal into the execute payload, and the output reached the context.
        proposals = steps[EXECUTE_STEP_ID]['task']['payload']['proposals']
        self.assertEqual(set(proposals), {step['step_id'] for step in delivery_steps})
        self.assertEqual(steps[EXECUTE_STEP_ID]['result']['output']['incidents'][0]['type'], 'unavailable')
        self.assertFalse(first['context_after']['state']['vehicles']['van1']['available'])
        plans = [step['result']['metadata'].get('selected_plan') for item in rounds
                 for step in item.get('result', {}).get('step_results', [])]
        self.assertIn('transfer_from_disabled_vehicle', plans)
        # The planner received the previous round in the history and used the substitute.
        self.assertEqual(saved['planner_calls'][1]['request']['history'][0]['round'], 1)
        self.assertEqual(first['planner_result']['metadata']['provider'], 'deterministic-integration-substitute')
        row = episode_metrics(saved, case=case, configuration='ariadne-v3', demo=True)
        self.assertEqual((row['delivered'], row['total_orders'], row['result']), (2, 2, 'complete'))
        self.assertEqual(row['llm_calls'], 0)
        self.assertGreater(row['bdi_cycles'], 0)
        self.assertEqual(row['max_parallel_steps'], 2)
        self.assertGreater(row['wall_seconds'], 0)

    def test_single_llm_baseline_runs_as_a_mission(self):
        case = find_case('two-orders')
        manifest, saved = run_case('two-orders', 'single-llm-v3')
        self.assertEqual(manifest['mission']['planner_capability'], 'logistics-v3-single-llm')
        self.assertEqual(saved['status'], 'MISSION_STATUS_COMPLETED', saved.get('error'))
        for item in saved['rounds'][:-1]:
            self.assertEqual([step['step_id'] for step in item['result']['step_results']], [EXECUTE_STEP_ID])
        row = episode_metrics(saved, case=case, configuration='single-llm-v3', demo=True)
        self.assertEqual((row['delivered'], row['result'], row['bdi_cycles']), (2, 'complete', 0))


if __name__ == '__main__':
    unittest.main()
