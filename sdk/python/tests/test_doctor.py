import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ariadne_sdk.doctor import diagnose, node_supported, writable_destination
from ariadne_sdk.__main__ import main


class DoctorTests(unittest.TestCase):
    def test_node_versions_match_frontend_requirements(self):
        for version in ('v18.20.0', 'v20.18.9', 'v21.7.0', 'v22.11.0'):
            self.assertFalse(node_supported(version), version)
        for version in ('v20.19.0', 'v22.12.0', 'v24.16.0'):
            self.assertTrue(node_supported(version), version)

    def test_destination_does_not_create_files_and_rejects_file_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'new' / 'runs'
            self.assertTrue(writable_destination(target))
            self.assertFalse(target.exists())
            blocker = Path(directory) / 'file'
            blocker.write_text('block')
            self.assertFalse(writable_destination(blocker / 'runs'))

    def test_prebuilt_runtime_does_not_require_go(self):
        with tempfile.TemporaryDirectory() as directory:
            for service in ('registry', 'orchestrator', 'messaging'):
                binary = Path(directory) / f'ariadne-{service}'
                binary.write_text('unused')
                binary.chmod(0o700)
            with patch('ariadne_sdk.doctor.tool_version', side_effect=AssertionError('must not run tools')):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(diagnose(runtime_dir=directory, output=directory), 0)
                (Path(directory) / 'ariadne-registry').chmod(0o600)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(diagnose(runtime_dir=directory, output=directory), 1)

    def test_old_go_and_missing_key_fail_without_exposing_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'go.mod').write_text('module demo\ngo 1.26.3\n')
            with patch('ariadne_sdk.doctor.tool_version', return_value='go version go1.25.0 linux/amd64'):
                with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        self.assertEqual(diagnose(runtime_source=directory, output=directory, llm=True), 1)
                    self.assertIn('instale Go >=1.26.3', output.getvalue())
                    self.assertIn('exporte OPENAI_API_KEY', output.getvalue())
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'secret-do-not-print'}):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    diagnose(runtime_dir=directory, output=directory, llm=True)
                self.assertNotIn('secret-do-not-print', output.getvalue())

    def test_cli_preserves_docker_default_and_rejects_mixed_options(self):
        # Real Docker adapter replaces this process; stop the mock at that boundary.
        with patch('ariadne_sdk.docker.command', side_effect=SystemExit(0)) as command:
            with self.assertRaises(SystemExit):
                main(['doctor'])
            command.assert_called_once_with('doctor', 'demo')
        for args in (['doctor', '--llm'], ['doctor', '--local', 'demo']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code, 2)

    def test_cli_passes_local_options(self):
        with patch('ariadne_sdk.doctor.diagnose', return_value=1) as diagnose_mock:
            self.assertEqual(main(['doctor', '--local', '--runtime-dir', '/bin/test', '--inspector']), 1)
            self.assertEqual(diagnose_mock.call_args.kwargs['runtime_dir'], Path('/bin/test'))
            self.assertTrue(diagnose_mock.call_args.kwargs['inspector'])


if __name__ == '__main__':
    unittest.main()
