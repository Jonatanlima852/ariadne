import importlib.util
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('inspector_serve', Path(__file__).with_name('serve.py'))
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)


class ServeTests(unittest.TestCase):
    def test_health_must_belong_to_supervised_session(self):
        for identity, expected in [('other', False), ('owned', True)]:
            with patch.object(serve, 'urlopen', return_value=io.BytesIO(json.dumps({'session': identity}).encode())):
                self.assertEqual(serve.ready('http://localhost/api/health', 'owned', api=True), expected)
        with patch.object(serve, 'urlopen', return_value=io.BytesIO(b'<meta content="owned">')):
            self.assertTrue(serve.ready('http://localhost', 'owned'))

    def test_busy_port_is_rejected_before_starting(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            with self.assertRaises(OSError):
                serve.available(occupied.getsockname()[1])

    def test_failure_after_start_attempt_still_cleans_up(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            frontend = root / 'tools/inspector'
            (frontend / 'node_modules/.bin').mkdir(parents=True)
            (frontend / 'node_modules/.bin/vite').touch()
            (frontend / 'package-lock.json').write_text('{}')
            stamp = root / '.ariadne/inspector/dependencies.sha256'
            stamp.parent.mkdir(parents=True)
            stamp.write_text(serve.hashlib.sha256(b'{}').hexdigest())
            with patch.object(serve, 'ROOT', root), patch.object(serve, 'INSPECTOR', frontend), \
                 patch.object(serve, 'tool_version', return_value='v24.16.0'), \
                 patch.object(serve, 'available'), patch.object(serve, 'Processes') as processes:
                processes.return_value.start.side_effect = RuntimeError('startup failure')
                with self.assertRaisesRegex(RuntimeError, 'startup failure'):
                    serve.main([])
                processes.return_value.stop.assert_called_once()
