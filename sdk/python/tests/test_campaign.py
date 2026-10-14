import json
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from ariadne_sdk import Campaign
from ariadne_sdk.campaign import run_campaign


class CampaignTests(TestCase):
    def test_matrix_order_environment_restore_and_independent_observations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'experiment.py'
            source.write_text('')
            seen = []
            previous = os.environ.get('ARIADNE_TEST_CASE')
            def runner(source, **options):
                seen.append((os.environ['ARIADNE_TEST_CASE'], options['execution_id']))
                if os.environ['ARIADNE_TEST_CASE'] == 'fail':
                    raise ValueError('invalid declaration')
                return None, {'status': 'COMPLETED'}
            directory, manifest = run_campaign(Campaign(source, {'ARIADNE_TEST_CASE': ['ok', 'fail']}, repeat=2),
                                               output_root=root, runner=runner)
            self.assertEqual([case for case, _ in seen], ['ok', 'fail', 'ok', 'fail'])
            self.assertEqual(len({identity for _, identity in seen}), 4)
            self.assertEqual(manifest['planned_observations'], 4)
            self.assertEqual(manifest['status'], 'FAILED')
            self.assertEqual(manifest, json.loads((directory / 'campaign.json').read_text()))
            self.assertEqual(os.environ.get('ARIADNE_TEST_CASE'), previous)

    def test_cancelled_observation_is_preserved_and_stops_campaign(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'experiment.py'
            source.touch()
            def runner(*args, **options):
                raise KeyboardInterrupt
            _, manifest = run_campaign(Campaign(source, repeat=3), output_root=root, runner=runner)
            self.assertEqual(manifest['status'], 'CANCELLED')
            self.assertEqual(len(manifest['runs']), 1)
            self.assertEqual(manifest['runs'][0]['status'], 'CANCELLED')

    def test_invalid_matrix_is_rejected(self):
        for matrix in ({'CASE': []}, {'CASE': ['a', 'a']}, {'BAD=KEY': ['a']}):
            with self.assertRaises(ValueError):
                Campaign('unused.py', matrix).variants()
