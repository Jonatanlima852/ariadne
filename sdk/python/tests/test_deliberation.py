"""Ciclo de deliberação BDI: crenças, objetivos, planos, rastro e contrato."""
import unittest

from contract.v1 import contract_pb2
from ariadne_sdk import (
    BdiAgent, BeliefBase, Deliberation, Goal, GoalFailure, GoalPlan, Input, Plan, Task, TaskResult,
    achieve, act, forget, observe,
)
from ariadne_sdk.models import _result_bdi_supported

TRACE_FIELDS = ["cycle", "beliefs_added", "beliefs_removed", "goal", "selected_plan", "action", "outcome"]


def task(payload=None, goal="deliver", bdi=None):
    return Task(task_id="test", goal=goal, payload=payload or {}, trace={"trace_id": "trace"},
                bdi={"intention_id": "intent", **(bdi or {})})


def agent(plans, **options):
    return BdiAgent(name="test", capabilities=["test"], plans=plans,
                    **({"beliefs": Input("state")} | options))


def failing(message, error=RuntimeError):
    def body(beliefs, goal):
        raise error(message)
    return body


class BeliefBaseTests(unittest.TestCase):
    def test_records_additions_revisions_and_removals_as_text(self):
        beliefs = BeliefBase({"x": 1, "flag": True})
        beliefs["x"] = 2
        beliefs.add("x", 2)
        beliefs.remove("flag")
        beliefs.remove("missing")
        self.assertEqual(beliefs.drain_changes(), (["x=1", "flag", "x=2"], ["x=1", "flag"]))
        self.assertEqual(beliefs.drain_changes(), ([], []))
        self.assertEqual(beliefs.snapshot(), {"x": 2})
        with self.assertRaises(KeyError):
            del beliefs["missing"]
        with self.assertRaises(TypeError):
            beliefs.add(1, "number key")


class DeliberationEngineTests(unittest.TestCase):
    def test_selection_uses_cost_then_priority_then_order_and_matches_trigger(self):
        chosen = []
        def body(name):
            return lambda beliefs, goal: chosen.append(name) or {"plan": name}
        engine = Deliberation([
            GoalPlan("other_goal", body("other_goal"), goal="refuel", cost=0),
            GoalPlan("fallback", body("fallback"), goal="deliver", priority=100),
            GoalPlan("blocked", body("blocked"), goal="deliver", context=lambda b, g: False, cost=0),
            GoalPlan("expensive", body("expensive"), goal="deliver", cost=10),
            GoalPlan("cheap", body("cheap"), goal="deliver", cost=lambda b, g: b["cost"]),
            GoalPlan("tied", body("tied"), goal="deliver", cost=2, priority=1),
        ])
        self.assertEqual([plan.name for plan in engine.options(Goal("deliver"), BeliefBase({"cost": 2}))],
                         ["tied", "cheap", "expensive", "fallback"])
        result = engine.run("deliver", {"cost": 1})
        self.assertEqual((chosen, result.output, result.status), (["cheap"], {"plan": "cheap"}, "achieved"))

    def test_invalid_libraries_and_steps_are_rejected(self):
        for plans in ([], [GoalPlan("a", lambda b, g: {}), GoalPlan("a", lambda b, g: {})]):
            with self.assertRaises(ValueError):
                Deliberation(plans)
        with self.assertRaises(ValueError):
            Deliberation([GoalPlan("a", lambda b, g: {})], max_cycles=0)
        with self.assertRaises(ValueError):
            GoalPlan("bad", lambda b, g: {}, cost=float("nan"))
        with self.assertRaises(TypeError):
            act("not callable")
        with self.assertRaises(TypeError):
            achieve(Goal("x"), extra=1)
        with self.assertRaises(TypeError):
            Goal.coerce(42)
        self.assertEqual(str(Goal.coerce({"name": "charge", "vehicle": "v1"})), 'charge(vehicle="v1")')

    def test_plan_yielding_unknown_step_fails_that_plan(self):
        def body(beliefs, goal):
            yield "not a step"
        result = Deliberation([GoalPlan("bad", body, goal="g")]).run("g")
        self.assertEqual(result.status, "failed")
        self.assertIsInstance(result.error, TypeError)
        self.assertEqual([c["outcome"] for c in result.cycles], ["failed", "failed"])


class DeliberativeAgentTests(unittest.TestCase):
    def test_beliefs_come_from_payload_and_die_with_the_task(self):
        seen = []
        instance = agent([GoalPlan("direct", goal="deliver",
                                   body=lambda b, g: seen.append(b.snapshot()) or {"ok": b["x"]})])
        payload = {"state": {"x": 1, "ready": True}}
        result = instance.handle(task(payload))
        self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
        self.assertEqual(result.output, {"ok": 1})
        self.assertEqual(result.metadata["selected_plan"], "direct")
        self.assertEqual(result.metadata["intention_id"], "intent")
        self.assertEqual(result.metadata["goals"], ["deliver"])
        self.assertEqual(result.trace["trace_id"], "trace")
        trace = result.metadata["bdi_trace"]
        self.assertEqual((trace["cycle_count"], trace["final_status"]), (1, "achieved"))
        self.assertEqual(trace["cycles"][0], {
            "cycle": 1, "beliefs_added": ["x=1", "ready"], "beliefs_removed": [],
            "goal": "deliver", "selected_plan": "direct", "action": "return", "outcome": "achieved"})
        self.assertEqual(payload, {"state": {"x": 1, "ready": True}})
        instance.handle(task({"state": {"x": 2}}))
        self.assertEqual([snapshot["x"] for snapshot in seen], [1, 2])

    def test_goal_sources_default_to_task_bdi_goal_then_task_goal(self):
        plans = [GoalPlan("echo", goal="deliver", body=lambda b, g: {"goal": str(g)})]
        default = BdiAgent(name="t", capabilities=["t"], plans=plans)
        self.assertEqual(default.handle(task({"x": 1}, goal="deliver")).output, {"goal": "deliver"})
        self.assertEqual(default.handle(task(goal="free text", bdi={"goal": "deliver"})).output, {"goal": "deliver"})
        self.assertEqual(default.handle(task(goal="free text")).error_code, "ERROR_CODE_EXECUTION_FAILED")
        self.assertEqual(default.handle(task(goal="")).error_code, "ERROR_CODE_INVALID_TASK")
        from_payload = agent(plans, goal=Input("goal"))
        result = from_payload.handle(task({"state": {}, "goal": {"name": "deliver", "order": "o1"}}))
        self.assertEqual(result.output, {"goal": 'deliver(order="o1")'})
        self.assertEqual(from_payload.handle(task({"state": {}})).error_code, "ERROR_CODE_INVALID_TASK")
        self.assertEqual(agent(plans).handle(task({"state": "not a mapping"})).error_code,
                         "ERROR_CODE_INVALID_TASK")

    def test_multi_cycle_plan_with_observe_act_achieve_and_forget(self):
        actions = []
        def lookup(order):
            actions.append(order)
            return {"route": ["A", "B"], "eta": 5}
        def deliver(beliefs, goal):
            yield observe(stock=3)
            found = yield act(lookup, goal.params["order"])
            charged = yield achieve("charge", vehicle="v1")
            yield forget("eta")
            return {"route": beliefs["route"], "battery": charged["battery"],
                    "stock": beliefs["stock"], "found": found["eta"], "has_eta": "eta" in beliefs}
        instance = agent([GoalPlan("deliver_plan", deliver, goal="deliver"),
                          GoalPlan("charge_plan", lambda b, g: {"battery": 100}, goal="charge")],
                         goal=Input("goal"))
        result = instance.handle(task({"state": {"x": 1}, "goal": {"name": "deliver", "order": "o1"}}))
        self.assertEqual(result.status, "TASK_STATUS_COMPLETED")
        self.assertEqual(result.output, {"route": ["A", "B"], "battery": 100, "stock": 3, "found": 5, "has_eta": False})
        self.assertEqual(actions, ["o1"])
        self.assertEqual(result.metadata["goals"], ['deliver(order="o1")', 'charge(vehicle="v1")'])
        cycles = result.metadata["bdi_trace"]["cycles"]
        self.assertEqual([c["action"] for c in cycles], [
            "observe(stock=3)", "act(lookup)", 'achieve(charge(vehicle="v1"))', "return", "forget(eta)", "return"])
        self.assertEqual([c["outcome"] for c in cycles],
                         ["continue", "continue", "continue", "achieved", "continue", "achieved"])
        self.assertEqual([c["goal"] for c in cycles][3], 'charge(vehicle="v1")')
        self.assertEqual(cycles[0]["beliefs_added"], ["x=1", "stock=3"])
        self.assertEqual(cycles[1]["beliefs_added"], ['route=["A","B"]', "eta=5"])
        self.assertEqual(cycles[4]["beliefs_removed"], ["eta=5"])
        self.assertEqual(result.metadata["bdi_trace"]["cycle_count"], 6)
        self.assertEqual(list(cycles[0]), TRACE_FIELDS)

    def test_sub_goal_plan_failure_falls_back_to_next_applicable_plan(self):
        def deliver(beliefs, goal):
            charged = yield achieve("charge")
            return {"battery": charged["battery"]}
        instance = agent([
            GoalPlan("deliver_plan", deliver, goal="deliver"),
            GoalPlan("fast", failing("charger down"), goal="charge", cost=1),
            GoalPlan("slow", lambda b, g: {"battery": 80}, goal="charge", cost=5),
        ])
        result = instance.handle(task({"state": {}}))
        self.assertEqual(result.output, {"battery": 80})
        cycles = result.metadata["bdi_trace"]["cycles"]
        self.assertEqual([(c["selected_plan"], c["outcome"]) for c in cycles], [
            ("deliver_plan", "continue"), ("fast", "failed"), ("slow", "achieved"), ("deliver_plan", "achieved")])
        self.assertEqual(cycles[1]["action"], "body -> RuntimeError: charger down")

    def test_sub_goal_failure_reaches_parent_body_as_goal_failure(self):
        caught = []
        def handling(beliefs, goal):
            try:
                yield achieve("charge")
            except GoalFailure as failure:
                caught.append((str(failure.goal), failure.reason, type(failure.cause).__name__))
                return {"battery": None}
        def unhandled(beliefs, goal):
            yield achieve("missing")
            return {}
        instance = agent([
            GoalPlan("handling", handling, goal="deliver", cost=1),
            GoalPlan("unhandled", unhandled, goal="deliver", cost=2),
            GoalPlan("fast", failing("charger down"), goal="charge"),
        ])
        result = instance.handle(task({"state": {}}))
        self.assertEqual(result.output, {"battery": None})
        self.assertEqual(caught, [("charge", "failed", "RuntimeError")])
        outcomes = [c["outcome"] for c in result.metadata["bdi_trace"]["cycles"]]
        self.assertEqual(outcomes, ["continue", "failed", "failed", "achieved"])

        instance = agent([GoalPlan("unhandled", unhandled, goal="deliver", cost=1),
                          GoalPlan("rescue", lambda b, g: {"rescued": True}, goal="deliver", cost=2)])
        result = instance.handle(task({"state": {}}))
        self.assertEqual(result.output, {"rescued": True})
        cycles = result.metadata["bdi_trace"]["cycles"]
        self.assertEqual([(c["goal"], c["selected_plan"], c["outcome"]) for c in cycles], [
            ("deliver", "unhandled", "continue"), ("missing", "", "no_applicable_plan"),
            ("deliver", "unhandled", "failed"), ("deliver", "rescue", "achieved")])
        self.assertIn("GoalFailure: goal missing no_applicable_plan", cycles[2]["action"])

    def test_no_applicable_plan_fails_without_executing(self):
        instance = agent([GoalPlan("never", lambda b, g: self.fail("executed"), goal="deliver",
                                   context=lambda b, g: b.get("ready")),
                          GoalPlan("other", lambda b, g: self.fail("executed"), goal="refuel")])
        result = instance.handle(task({"state": {"ready": False}}))
        self.assertEqual(result.status, "TASK_STATUS_FAILED")
        self.assertEqual(result.error_code, "ERROR_CODE_EXECUTION_FAILED")
        self.assertNotIn("selected_plan", result.metadata)
        trace = result.metadata["bdi_trace"]
        self.assertEqual((trace["final_status"], trace["cycle_count"]), ("no_applicable_plan", 1))
        self.assertEqual(trace["cycles"][0]["outcome"], "no_applicable_plan")
        self.assertEqual(trace["cycles"][0]["beliefs_added"], ["ready=false"])
        self.assertEqual(result.bdi["trace"]["final_status"], "no_applicable_plan")

    def test_all_plans_failing_reports_failed_with_error_type(self):
        instance = agent([GoalPlan("a", failing("bad input", ValueError), goal="deliver", cost=1),
                          GoalPlan("b", failing("late", TimeoutError), goal="deliver", cost=2)])
        result = instance.handle(task({"state": {}}))
        self.assertEqual(result.error_code, "ERROR_CODE_TIMEOUT")
        self.assertTrue(result.retryable)
        self.assertEqual(result.metadata["error_type"], "TimeoutError")
        self.assertEqual(result.metadata["selected_plan"], "b")
        self.assertEqual(result.metadata["bdi_trace"]["final_status"], "failed")
        self.assertEqual([c["outcome"] for c in result.metadata["bdi_trace"]["cycles"]],
                         ["failed", "failed", "failed"])

    def test_cycle_limit_stops_runaway_intentions(self):
        def forever(beliefs, goal):
            tick = 0
            while True:
                tick += 1
                yield observe(tick=tick)
        instance = agent([GoalPlan("loop", forever, goal="deliver")], max_cycles=5)
        result = instance.handle(task({"state": {}}))
        self.assertEqual(result.status, "TASK_STATUS_FAILED")
        self.assertIn("5 ciclos", result.error_message)
        trace = result.metadata["bdi_trace"]
        self.assertEqual((trace["final_status"], trace["cycle_count"]), ("cycle_limit", 5))
        self.assertEqual(trace["cycles"][-1]["beliefs_removed"], ["tick=4"])
        self.assertEqual(trace["cycles"][-1]["beliefs_added"], ["tick=5"])
        with self.assertRaises(ValueError):
            agent([GoalPlan("loop", forever)], max_cycles=0)

    def test_action_errors_are_delivered_to_the_plan_body(self):
        def flaky():
            raise ConnectionError("charger offline")
        def resilient(beliefs, goal):
            try:
                yield act(flaky)
            except ConnectionError:
                yield observe(charger="offline")
            return {"charger": beliefs["charger"]}
        def brittle(beliefs, goal):
            yield act(flaky)
            return {}
        result = agent([GoalPlan("resilient", resilient, goal="deliver")]).handle(task({"state": {}}))
        self.assertEqual(result.output, {"charger": "offline"})
        cycles = result.metadata["bdi_trace"]["cycles"]
        self.assertEqual([c["action"] for c in cycles],
                         ["act(flaky) handled ConnectionError: charger offline", 'observe(charger="offline")', "return"])
        result = agent([GoalPlan("brittle", brittle, goal="deliver")]).handle(task({"state": {}}))
        self.assertEqual(result.status, "TASK_STATUS_FAILED")
        self.assertEqual(result.metadata["bdi_trace"]["cycles"][0]["action"],
                         "act(flaky) raised ConnectionError: charger offline -> ConnectionError: charger offline")

    def test_result_crosses_the_contract_with_trace_in_metadata_and_bdi(self):
        instance = agent([GoalPlan("direct", lambda b, g: {"ok": True}, goal="deliver")])
        result = instance.handle(task({"state": {"x": 1}}))
        self.assertEqual(result.bdi["goal"], "deliver")
        self.assertEqual(result.bdi["goals"], ["deliver"])
        message = result.to_proto()
        self.assertEqual(message.metadata["bdi_trace"]["final_status"], "achieved")
        self.assertEqual(message.metadata["bdi_trace"]["cycles"][0]["beliefs_added"][0], "x=1")
        restored = TaskResult.from_proto(message)
        self.assertEqual(restored.metadata["bdi_trace"]["cycle_count"], 1)
        if _result_bdi_supported():
            self.assertEqual(message.bdi.trace.final_status, "achieved")
            self.assertEqual(message.bdi.trace.cycles[0].beliefs_added, ["x=1"])
            self.assertEqual(restored.bdi, result.bdi)
        else:
            self.assertFalse(hasattr(contract_pb2, "BdiTrace"))
            self.assertEqual(restored.bdi, {})
        wire = instance._execute_contract_task(task({"state": {"x": 1}}).to_proto())
        self.assertEqual(wire.status, contract_pb2.TASK_STATUS_COMPLETED)
        self.assertEqual(wire.metadata["selected_plan"], "direct")

    def test_declarative_api_keeps_working_and_libraries_cannot_be_mixed(self):
        declarative = BdiAgent(name="t", capabilities=["t"], beliefs=Input("world"), desire=Input("mission"),
                               plans=[Plan("solve", lambda beliefs, desire: {"to": desire["to"], "from": beliefs["at"]})])
        result = declarative.handle(task({"world": {"at": "A"}, "mission": {"to": "D"}}))
        self.assertEqual(result.output, {"to": "D", "from": "A"})
        self.assertEqual(result.metadata["selected_plan"], "solve")
        self.assertNotIn("bdi_trace", result.metadata)
        self.assertEqual(result.bdi, {})
        with self.assertRaises(ValueError):
            BdiAgent(name="t", capabilities=["t"], plans=[Plan("a", lambda b, d: {}), GoalPlan("b", lambda b, g: {})])
        with self.assertRaises(ValueError):
            BdiAgent(name="t", capabilities=["t"], plans=[Plan("a", lambda b, d: {})], goal="deliver")
        with self.assertRaises(ValueError):
            BdiAgent(name="t", capabilities=["t"], plans=[GoalPlan("a", lambda b, g: {})], desire=Input())


if __name__ == "__main__":
    unittest.main()
