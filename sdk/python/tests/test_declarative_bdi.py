from concurrent.futures import ThreadPoolExecutor
import runpy
from pathlib import Path
import threading
import unittest

from ariadne_sdk import BdiAgent, GoalPlan, Input, Plan, Task


def task(payload=None):
    return Task(task_id="test", goal="choose", payload=payload or {},
                trace={"trace_id": "trace"}, bdi={"intention_id": "intent"})


def agent(plans, **options):
    return BdiAgent(name="test", capabilities=["test"], plans=plans, **options)


class DeclarativeBdiTests(unittest.TestCase):
    def test_only_selected_plan_executes_and_output_has_no_reserved_keys(self):
        effects = []
        def execute(name):
            return lambda beliefs, desire: effects.append(name) or {"cost": 99, "name": name}
        instance = agent([
            Plan("fallback", execute("fallback"), priority=100),
            Plan("unavailable", execute("unavailable"), when=lambda b, d: False, cost=-1),
            Plan("expensive", execute("expensive"), cost=10),
            Plan("cheap", execute("cheap"), cost=lambda b, d: d["cost"]),
        ])
        result = instance.handle(task({"cost": 2}))
        self.assertEqual(effects, ["cheap"])
        self.assertEqual(result.output, {"cost": 99, "name": "cheap"})
        self.assertEqual(result.metadata["selected_plan"], "cheap")
        self.assertEqual(result.metadata["intention_id"], "intent")
        self.assertEqual(len(result.metadata["evaluated_plans"]), 4)
        self.assertFalse(result.metadata["evaluated_plans"][1]["applicable"])
        self.assertEqual(result.trace["trace_id"], "trace")
        self.assertEqual(result.to_proto().metadata["selected_plan"], "cheap")

    def test_ties_use_priority_then_declaration_order(self):
        for cost in (None, 2):
            instance = agent([Plan(name, lambda b, d: {}, cost=cost, priority=priority)
                              for name, priority in [("first", 0), ("preferred", 1), ("tied", 1)]])
            self.assertEqual(instance.handle(task()).metadata["selected_plan"], "preferred")

    def test_missing_input_is_invalid_but_false_and_none_are_present(self):
        instance = agent([Plan("echo", lambda b, d: {"value": d})], desire=Input("nested", "value"))
        self.assertEqual(instance.handle(task()).error_code, "ERROR_CODE_INVALID_TASK")
        for value in (None, False, 0, {}, []):
            result = instance.handle(task({"nested": {"value": value}}))
            self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
            self.assertEqual(result.output["value"], value)
        self.assertEqual(Input("missing", default=0).resolve(task()), 0)

    def test_task_and_static_beliefs_are_isolated_during_concurrent_execution(self):
        barrier = threading.Barrier(2)
        initial = {"values": []}
        def execute(beliefs, desire):
            beliefs["values"].append(desire["id"])
            barrier.wait(timeout=5)
            return beliefs
        instance = agent([Plan("write", execute)], beliefs=initial)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(instance.handle, [task({"id": 1}), task({"id": 2})]))
        self.assertEqual([r.output["values"] for r in results], [[1], [2]])
        self.assertEqual(initial, {"values": []})
        received = task({"state": {"values": []}})
        instance = agent([Plan("write", lambda b, d: b["values"].append(1) or b)], beliefs=Input("state"))
        instance.handle(received)
        self.assertEqual(received.payload["state"], {"values": []})

    def test_no_applicable_plan_records_rejections_and_does_not_execute(self):
        instance = agent([Plan("never", lambda b, d: self.fail("executed"), when=lambda b, d: False)])
        result = instance.handle(task())
        self.assertEqual(result.error_code, "ERROR_CODE_EXECUTION_FAILED")
        self.assertFalse(result.metadata["evaluated_plans"][0]["applicable"])

    def test_execution_failure_keeps_decision_and_does_not_run_fallback(self):
        def fail(beliefs, desire):
            raise TimeoutError("calendar unavailable")
        instance = agent([Plan("chosen", fail, cost=1),
                          Plan("fallback", lambda b, d: self.fail("unexpected fallback"))])
        result = instance.handle(task())
        self.assertEqual(result.error_code, "ERROR_CODE_TIMEOUT")
        self.assertTrue(result.retryable)
        self.assertEqual(result.metadata["selected_plan"], "chosen")
        self.assertEqual(result.metadata["failure_phase"], "execution")
        self.assertEqual(result.metadata["intention_id"], "intent")
        self.assertEqual(len(result.metadata["evaluated_plans"]), 2)

    def test_input_functions_and_nested_defaults_are_copied(self):
        value = {"items": []}
        for source in (Input("missing", default=value), lambda received: value):
            instance = agent([Plan("append", lambda b, d: d["items"].append(1) or d)], desire=source)
            self.assertEqual(instance.handle(task()).output["items"], [1])
        self.assertEqual(value, {"items": []})

    def test_invalid_declarations_and_non_finite_costs(self):
        for cost in (float("inf"), float("nan"), "cheap", True):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                Plan("invalid", lambda b, d: {}, cost=cost)
        with self.assertRaises(ValueError):
            agent([])
        with self.assertRaises(ValueError):
            agent([Plan("same", lambda b, d: {}), Plan("same", lambda b, d: {})])
        with self.assertRaises(ValueError):
            agent([Plan("ok", lambda b, d: {}), GoalPlan("mixed", lambda b, g: {})])
        instance = agent([Plan("invalid", lambda b, d: self.fail("executed"), cost=lambda b, d: float("nan"))])
        result = instance._execute_contract_task(task().to_proto())
        from contract.v1 import contract_pb2
        self.assertEqual(result.status, contract_pb2.TASK_STATUS_FAILED)

    def test_meeting_example_uses_same_interface_and_handles_unavailable_people(self):
        namespace = runpy.run_path(str(Path(__file__).resolve().parents[3] / "studies/scenarios/meeting/scenario.py"))
        instance = namespace["scenario"].agents[0]
        request = {"participants": ["alice", "bob", "carol"], "duration_hours": 1, "preferred_start_hour": 13}
        result = instance.handle(task(request))
        self.assertEqual(result.output["start_hour"], 12)
        self.assertEqual(result.metadata["selected_plan"], "earliest_full_slot")
        self.assertEqual(result.metadata["bdi_trace"]["final_status"], "achieved")
        # Uma reunião de nove horas com alice (ocupada às 9h) não cabe no expediente: resta o plano de recuo.
        result = instance.handle(task({"participants": ["alice"], "duration_hours": 9, "preferred_start_hour": 9}))
        self.assertEqual(result.metadata["selected_plan"], "no_feasible_slot")
        self.assertIsNone(result.output["start_hour"])

if __name__ == "__main__":
    unittest.main()
