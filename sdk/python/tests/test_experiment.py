import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ariadne_sdk import Agent, Scenario, Step, Task
from ariadne_sdk.evidence import EventLog
from ariadne_sdk.execution import load_scenario


class ExperimentTests(unittest.TestCase):
    def test_description_opens_no_channel_and_compiles_nested_binding(self):
        with patch("grpc.insecure_channel", side_effect=AssertionError("network during declaration")):
            first = Step("echo", "hello")
            last = Step("consume", "use result", payload={"context": {"text": first.output["text"]}})
            scenario = Scenario(agents=[Agent(name="echo", capabilities=["echo"])], tasks=[first, last])
            steps = scenario.definition()
        self.assertEqual(steps[1]["depends_on"], ["step_1"])
        self.assertEqual(steps[1]["input_bindings"], [{
            "source_step_id": "step_1", "source_path": "output.text", "target_field": "context.text",
        }])
        self.assertIsInstance(last.payload["context"]["text"].step, Step)

    def test_independent_steps_remain_parallel_and_dependencies_deduplicate(self):
        first, other = Step("echo", "a"), Step("echo", "b")
        third = Step("echo", "c", depends_on=(first,), payload={"a": first.output, "b": first.output["text"]})
        steps = Scenario(tasks=[first, other, third]).definition()
        self.assertEqual(steps[1]["depends_on"], [])
        self.assertEqual(steps[2]["depends_on"], ["step_1"])

    def test_unknown_reference_cycle_duplicate_and_array_reference_are_rejected(self):
        first, second = Step("echo", "a"), Step("echo", "b")
        cases = [
            ([Step("echo", "x", payload={"text": first.output})], "outside"),
            ([first, first], "twice"),
            ([first, Step("echo", "x", payload={"items": [first.output]})], "arrays"),
            ([Step("echo", "a", name="same"), Step("echo", "b", name="same")], "unique"),
        ]
        cycle_a, cycle_b = Step("echo", "a"), Step("echo", "b")
        cycle_a.depends_on, cycle_b.depends_on = (cycle_b,), (cycle_a,)
        cases.append(([cycle_a, cycle_b], "cycle"))
        for tasks, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                Scenario(tasks=tasks).definition()

    def test_mapping_handler_gets_python_task_and_preserves_operational_fields(self):
        received = []

        def echo(task):
            received.append(task)
            return {"text": task.goal}

        agent = Agent(name="echo", capabilities=["echo"], handler=echo)
        raw = Task(task_id="t", goal="hello", trace={"trace_id": "trace"}).to_proto()
        result = agent._execute_contract_task(raw)
        self.assertIsInstance(received[0], Task)
        self.assertEqual(result.task_id, "t")
        self.assertEqual(result.agent_id, "echo")
        self.assertEqual(result.trace.trace_id, "trace")
        self.assertEqual(result.output["text"], "hello")

    def test_handler_failure_keeps_error_semantics(self):
        def reject(task):
            raise ValueError("bad input")
        agent = Agent(name="reject", capabilities=["echo"], handler=reject)
        result = agent._execute_contract_task(Task(task_id="t", goal="hello").to_proto())
        self.assertEqual(result.error.message, "bad input")
        self.assertFalse(result.error.retryable)

    def test_load_external_file_and_import_neighbor(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "experiment_helpers_unique.py").write_text("def echo(task): return {'text': task.goal}\n")
            source = directory / "experiment.py"
            source.write_text(
                "from ariadne_sdk import Agent, Scenario, Step\n"
                "from experiment_helpers_unique import echo\n"
                "scenario = Scenario(agents=[Agent(name='e', capabilities=['echo'], handler=echo)], "
                "tasks=[Step('echo', 'hello')])\n"
            )
            loaded = load_scenario(source)
            self.assertEqual(loaded.agents[0].handle(Task(task_id="t", goal="hello")), {"text": "hello"})

    def test_load_rejects_duplicate_agents_and_missing_capabilities(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "experiment.py"
            for declarations, capability, error in [
                ("[Agent(name='a', capabilities=['echo']), Agent(name='a', capabilities=['echo'])]", "echo", "unique"),
                ("[Agent(name='a', capabilities=['echo'])]", "missing", "no declared agent"),
            ]:
                source.write_text(
                    "from ariadne_sdk import Agent, Scenario, Step\n"
                    f"scenario = Scenario(agents={declarations}, tasks=[Step('{capability}', 'hello')])\n"
                )
                with self.assertRaisesRegex(ValueError, error):
                    load_scenario(source)

    def test_evidence_is_jsonl_with_execution_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"
            log = EventLog(path, execution_id="run")
            log.emit("FIRST", task_id="t")
            log.emit("SECOND", output={"text": "Olá"})
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([event["type"] for event in events], ["FIRST", "SECOND"])
            self.assertEqual(events[1]["execution_id"], "run")
            self.assertIn("timestamp", events[0])


if __name__ == "__main__":
    unittest.main()


class StaticContractTests(unittest.TestCase):
    def test_go_workflow_limits_and_invalid_policies_fail_before_startup(self):
        chain = [Step('echo', 'first')]
        for _ in range(5):
            chain.append(Step('echo', 'next', depends_on=(chain[-1],)))
        for steps, message in (
            ([Step('echo', 'x') for _ in range(11)], '10 steps'),
            (chain, 'depth'),
            ([Step('echo', 'x', selection_policy='typo')], 'selection policy'),
            ([Step('echo', 'x', deadline_ms=1.5)], 'integers'),
            ([Step('task-decomposition', 'x')], 'recursively'),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                Scenario(tasks=steps).definition()
