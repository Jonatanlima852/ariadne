"""Testa a prontidão real por identidade/capacidade, sem sleeps ou serviços."""

import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace

from contract.v1 import contract_pb2 as pb

spec = importlib.util.spec_from_file_location("tg_runner", Path(__file__).with_name("runner.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def agent(identifier="a", capability="echo", status=pb.AGENT_STATUS_ALIVE):
    return pb.GetAgentResponse(agent=pb.AgentDescriptor(
        agent_id=identifier, status=status,
        capabilities=[pb.Capability(capability_id=capability)],
        endpoint=pb.AgentEndpoint(address="worker:60051"),
    ))


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.now = 0

    def sleep(self, amount):
        self.now += amount

    def wait(self, stub, connect=None):
        runner.wait_for_agents(stub, {"a": "echo"}, timeout=2,
                               clock=lambda: self.now, sleep=self.sleep, connect=connect)

    def test_waits_for_correct_capability_alive_state_and_reachable_endpoint(self):
        responses = iter([agent(capability="other"), agent(status=pb.AGENT_STATUS_DEAD), agent(), agent()])
        attempts = []

        def connect(address, _timeout):
            attempts.append(address)
            if len(attempts) == 1:
                raise TimeoutError('not listening yet')

        self.wait(SimpleNamespace(GetAgent=lambda *a, **k: next(responses)), connect)
        self.assertEqual(attempts, ['worker:60051', 'worker:60051'])
        self.assertGreater(self.now, 0)

    def test_missing_agent_times_out_with_identity(self):
        with self.assertRaisesRegex(TimeoutError, 'a'):
            self.wait(SimpleNamespace(GetAgent=lambda *a, **k: agent(identifier='other')))
        self.assertEqual(self.now, 2)

    def test_busy_agent_is_usable(self):
        self.wait(SimpleNamespace(GetAgent=lambda *a, **k: agent(status=pb.AGENT_STATUS_BUSY)))
        self.assertEqual(self.now, 0)


if __name__ == '__main__':
    unittest.main()
