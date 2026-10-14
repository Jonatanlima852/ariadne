import json
from pathlib import Path
import subprocess
import tempfile
from unittest import TestCase

from ariadne_sdk.provenance import capture, file_record


class ProvenanceTests(TestCase):
    def test_changed_declared_dataset_changes_hash_and_git_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'experiment.py'
            dataset = root / 'world.json'
            source.write_text('scenario = None\n')
            dataset.write_text('{"a": 1}')
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                            'commit', '-qm', 'initial'], check=True)
            before = capture(source, ['world.json'])
            self.assertFalse(before['git']['dirty'])
            dataset.write_text('{"a": 2}')
            after = capture(source, ['world.json'])
            self.assertTrue(after['git']['dirty'])
            self.assertEqual(before['git']['revision'], after['git']['revision'])
            hashes = lambda document: {row['path']: row['sha256'] for row in document['files']}
            self.assertNotEqual(hashes(before)[str(dataset.resolve())], hashes(after)[str(dataset.resolve())])
            json.dumps(after, allow_nan=False)

    def test_credentials_and_missing_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / '.env'
            path.touch()
            with self.assertRaises(ValueError):
                file_record(path)
            with self.assertRaises(FileNotFoundError):
                file_record(path.with_name('missing.json'))
