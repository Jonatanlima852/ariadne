import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ariadne_sdk.doctor import compose_supported, diagnose, node_supported, writable_destination
from ariadne_sdk.__main__ import main


class DoctorTests(unittest.TestCase):
    def test_node_versions_match_frontend_requirements(self):
        for version in ('v18.20.0', 'v20.18.9', 'v21.7.0', 'v22.11.0'):
            self.assertFalse(node_supported(version), version)
        for version in ('v20.19.0', 'v22.12.0', 'v24.16.0'):
            self.assertTrue(node_supported(version), version)

    def test_compose_versions_follow_the_minimum(self):
        for version in ('2.24.3', '2.20.0', 'v1.29.2'):
            self.assertFalse(compose_supported(version), version)
        for version in ('2.24.4', 'v2.39.2-desktop.1', '3.0.0'):
            self.assertTrue(compose_supported(version), version)

    def test_destination_does_not_create_files_and_rejects_file_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'new' / 'runs'
            self.assertTrue(writable_destination(target))
            self.assertFalse(target.exists())
            blocker = Path(directory) / 'file'
            blocker.write_text('block')
            self.assertFalse(writable_destination(blocker / 'runs'))

    def test_old_compose_and_missing_key_fail_without_exposing_credentials(self):
        def tools(tool, *arguments):
            return '2.20.0' if 'compose' in arguments else '28.4.0'
        with tempfile.TemporaryDirectory() as directory:
            with patch('ariadne_sdk.doctor.tool_version', side_effect=tools):
                with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        self.assertEqual(diagnose(output=directory, llm=True), 1)
                    self.assertIn('use Docker Compose >=2.24.4', output.getvalue())
                    self.assertIn('exporte OPENAI_API_KEY', output.getvalue())
                with patch.dict(os.environ, {'OPENAI_API_KEY': 'secret-do-not-print'}):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        diagnose(output=directory, llm=True)
                    self.assertNotIn('secret-do-not-print', output.getvalue())

    def test_docker_ready_environment_passes_without_running_containers(self):
        def tools(tool, *arguments):
            return '2.24.4' if 'compose' in arguments else '28.4.0'
        with tempfile.TemporaryDirectory() as directory:
            with patch('ariadne_sdk.doctor.tool_version', side_effect=tools):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(diagnose(output=directory), 0)

    def test_cli_passes_options(self):
        with patch('ariadne_sdk.doctor.diagnose', return_value=1) as diagnose_mock:
            self.assertEqual(main(['doctor', '--inspector', '--llm']), 1)
            self.assertTrue(diagnose_mock.call_args.kwargs['inspector'])
            self.assertTrue(diagnose_mock.call_args.kwargs['llm'])
            self.assertIsNone(diagnose_mock.call_args.kwargs['source'])


if __name__ == '__main__':
    unittest.main()
