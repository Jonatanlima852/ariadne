"""Agentes e configuração sem runtime: domínio, planejador, mapa/redução, contador lento."""
import os
import time
import unittest
from unittest.mock import patch

from ariadne_sdk import PlannerResponse, Task
from ariadne_sdk.execution import load_scenario
from studies.scenarios.fanout.agents import (
    COUNT_CAPABILITY, FLAKY_AGENT_ID, MAX_SHARDS, REDUCE_CAPABILITY, REDUCE_STEP_ID, flaky_counter, map_step_id,
    plan, planner, reduce_shards, reducer, shard_counter,
)
from studies.scenarios.fanout.domain import count_words, make_shards, merge_counts, top_words
from studies.scenarios.fanout.mission import (
    Settings, agents_for, expected_total_words, mission_context, mission_for, settings_from_env,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


def planner_task(context, history=()):
    payload = {"mission_id": "m1", "goal": "contar", "round": len(history) + 1, "context": context,
               "history": list(history), "available_capabilities": [], "limits": {"max_rounds": 3}}
    return Task(task_id="plan", goal="contar", type="MISSION_PLANNING", payload=payload)


def count_task(shard, work_ms=0):
    return Task(task_id=f"map-{shard['shard']}", goal="contar", payload={**shard, "work_ms": work_ms})


class DomainTests(unittest.TestCase):
    def test_shards_are_deterministic_and_counts_add_up(self):
        first, second = make_shards(3, 50), make_shards(3, 50)
        self.assertEqual(first, second)
        self.assertEqual([item["shard"] for item in first], [1, 2, 3])
        self.assertTrue(all(len(item["text"].split()) == 50 for item in first))
        merged = merge_counts([count_words(item["text"]) for item in first])
        self.assertEqual(sum(merged.values()), 150)
        self.assertEqual(merged, count_words(" ".join(item["text"] for item in first)))

    def test_counting_normalizes_case_and_accents(self):
        counts = count_words("Fé fe FÉ, Reino; reino")
        self.assertEqual(counts, {"fe": 3, "reino": 2})
        self.assertEqual(top_words(counts, 1), [["fe", 3]])


class PlannerTests(unittest.TestCase):
    def test_round_one_plans_parallel_maps_and_a_bound_reduce(self):
        settings = Settings(shards=4, words_per_shard=20)
        response = PlannerResponse.from_output(plan(planner_task(mission_context(settings))))
        self.assertEqual(response.action, "PLAN")
        steps = {step["step_id"]: step for step in response.plan["steps"]}
        self.assertEqual(set(steps), {map_step_id(i) for i in range(1, 5)} | {REDUCE_STEP_ID})
        self.assertEqual(response.plan["final_step_id"], REDUCE_STEP_ID)
        for index in range(1, 5):
            step = steps[map_step_id(index)]
            self.assertEqual(step["required_capabilities"], [COUNT_CAPABILITY])
            self.assertEqual(step["depends_on"], [])
            self.assertEqual(step["payload"]["shard"], index)
            self.assertEqual(step["payload"]["work_ms"], settings.work_ms)
            self.assertTrue(step["payload"]["text"])
        reduce = steps[REDUCE_STEP_ID]
        self.assertEqual(reduce["required_capabilities"], [REDUCE_CAPABILITY])
        self.assertEqual(sorted(reduce["depends_on"]), sorted(map_step_id(i) for i in range(1, 5)))
        self.assertEqual({b["target_field"] for b in reduce["input_bindings"]}, {f"shards.{map_step_id(i)}" for i in range(1, 5)})
        self.assertTrue(all(b["source_path"] == "output" for b in reduce["input_bindings"]))
        self.assertEqual(response.context_update, {"planned_shards": 4, "dropped_shards": 0})

    def test_round_one_caps_shards_to_the_workflow_limit(self):
        context = {"shards": make_shards(12, 10), "work_ms": 0, "top_n": 3}
        response = PlannerResponse.from_output(plan(planner_task(context)))
        self.assertEqual(len(response.plan["steps"]), MAX_SHARDS + 1)
        self.assertEqual(response.context_update, {"planned_shards": MAX_SHARDS, "dropped_shards": 3})
        self.assertIn("dropped", response.summary)

    def test_round_two_is_done_from_the_reduce_output(self):
        history = [{"round": 1, "action": "PLANNER_ACTION_PLAN", "status": "WORKFLOW_STATUS_COMPLETED", "step_results": [
            {"step_id": "map-1", "status": "WORKFLOW_STEP_STATUS_COMPLETED", "task": {"attempt": 1}, "result": {"output": {}}},
            {"step_id": "map-2", "status": "WORKFLOW_STEP_STATUS_COMPLETED", "task": {"attempt": 2}, "result": {"output": {}}},
            {"step_id": REDUCE_STEP_ID, "status": "WORKFLOW_STEP_STATUS_COMPLETED", "task": {"attempt": 1},
             "result": {"output": {"total_words": 40, "top_words": [["e", 5]], "shards_merged": [1, 2]}}},
        ]}]
        response = PlannerResponse.from_output(plan(planner_task({"shards": []}, history)))
        self.assertEqual(response.action, "DONE")
        self.assertEqual(response.output["total_words"], 40)
        self.assertEqual(response.output["map_steps"], 2)
        self.assertEqual(response.output["reassigned_steps"], ["map-2"])
        self.assertIn("1 step(s) reassigned", response.output["summary"])

    def test_round_two_aborts_when_a_step_failed(self):
        history = [{"round": 1, "action": "PLANNER_ACTION_PLAN", "status": "WORKFLOW_STATUS_FAILED", "step_results": [
            {"step_id": "map-1", "status": "WORKFLOW_STEP_STATUS_FAILED", "result": {}},
            {"step_id": REDUCE_STEP_ID, "status": "WORKFLOW_STEP_STATUS_SKIPPED", "result": {}},
        ]}]
        response = PlannerResponse.from_output(plan(planner_task({"shards": []}, history)))
        self.assertEqual(response.action, "ABORT")
        self.assertIn("map-1", response.reason)

    def test_empty_context_aborts(self):
        self.assertEqual(plan(planner_task({"shards": []}))["action"], "ABORT")


class MapReduceTests(unittest.TestCase):
    def test_map_then_reduce_matches_a_direct_count(self):
        settings = Settings(shards=3, words_per_shard=30, work_ms=1)
        counters = [shard_counter("counter-1"), shard_counter("counter-2")]
        outputs = {}
        for index, shard in enumerate(make_shards(settings.shards, settings.words_per_shard)):
            result = counters[index % 2].handle(count_task(shard, settings.work_ms))
            self.assertEqual(result["shard"], shard["shard"])
            self.assertEqual(result["counted_by"], counters[index % 2].agent_id)
            outputs[map_step_id(shard["shard"])] = result
        reduced = reducer().handle(Task(task_id="reduce", goal="reduzir", payload={
            "shards": outputs, "top_n": 2, "expected_shards": [1, 2, 3]}))
        self.assertEqual(reduced["total_words"], expected_total_words(settings))
        self.assertEqual(reduced["shards_merged"], [1, 2, 3])
        self.assertEqual(reduced["counted_by"], {"1": "counter-1", "2": "counter-2", "3": "counter-1"})
        self.assertEqual(len(reduced["top_words"]), 2)

    def test_reduce_rejects_missing_shards_and_empty_input(self):
        with self.assertRaises(ValueError):
            reduce_shards(Task(task_id="r", goal="r", payload={"shards": {}}))
        with self.assertRaises(ValueError):
            reduce_shards(Task(task_id="r", goal="r", payload={
                "shards": {"map-1": {"shard": 1, "counts": {"a": 1}}}, "expected_shards": [1, 2]}))

    def test_count_requires_shard_and_text(self):
        with self.assertRaises(ValueError):
            shard_counter("c").handle(Task(task_id="t", goal="t", payload={"shard": 1}))


class FlakyCounterTests(unittest.TestCase):
    def test_flaky_counter_answers_correctly_but_after_its_delay(self):
        shard = make_shards(1, 10)[0]
        slow, healthy = flaky_counter(delay_ms=80), shard_counter("counter-1")
        self.assertEqual(slow.agent_id, FLAKY_AGENT_ID)
        self.assertEqual(slow.capabilities, [COUNT_CAPABILITY])
        started = time.perf_counter()
        quick = healthy.handle(count_task(shard))
        healthy_elapsed = time.perf_counter() - started
        started = time.perf_counter()
        late = slow.handle(count_task(shard))
        slow_elapsed = time.perf_counter() - started
        self.assertEqual(late["counts"], quick["counts"])
        self.assertEqual(late["delay_ms"], 80)
        self.assertGreaterEqual(slow_elapsed, 0.08)
        self.assertLess(healthy_elapsed, 0.08)

    def test_flaky_delay_must_be_positive(self):
        with self.assertRaises(ValueError):
            flaky_counter(delay_ms=0)


class SettingsTests(unittest.TestCase):
    def test_settings_from_env_and_derived_values(self):
        settings = settings_from_env({"FANOUT_WORKERS": "2", "FANOUT_SHARDS": "5", "FANOUT_FLAKY": "0",
                                      "FANOUT_STEP_DEADLINE_MS": "500", "FANOUT_FLAKY_FACTOR": "4"})
        self.assertEqual((settings.workers, settings.shards, settings.flaky), (2, 5, False))
        self.assertEqual(settings.flaky_delay_ms, 2000)
        self.assertEqual(settings.label, "fanout-k2-n5")
        self.assertEqual(settings_from_env({}).label, "fanout-k4-n8-flaky")
        # O prazo de passo viaja no plano (deadline_ms), não no ambiente.
        self.assertEqual(mission_context(settings)["step_deadline_ms"], 500)

    def test_shards_above_the_workflow_limit_are_rejected(self):
        with self.assertRaises(ValueError):
            Settings(shards=MAX_SHARDS + 1)
        with self.assertRaises(ValueError):
            settings_from_env({"FANOUT_WORKERS": "0"})

    def test_agents_and_mission_follow_the_settings(self):
        settings = Settings(workers=2, shards=3, flaky=True, words_per_shard=10)
        self.assertEqual([agent.agent_id for agent in agents_for(settings)],
                         ["planner", "counter-1", "counter-2", FLAKY_AGENT_ID, "reducer"])
        self.assertEqual([agent.agent_id for agent in agents_for(Settings(workers=1, flaky=False, words_per_shard=10))],
                         ["planner", "counter-1", "reducer"])
        mission = mission_for(settings).validate()
        self.assertEqual(mission.limits.max_parallel, 2)
        self.assertEqual(mission.limits.max_rounds, 3)
        self.assertEqual(mission.selection_policy, "round_robin")
        self.assertEqual(mission.retry_policy, {"max_attempts": 2, "exclude_failed_agent": True})
        self.assertEqual(len(mission.context["shards"]), 3)
        self.assertEqual(mission.metadata["flaky_delay_ms"], 4500)

    def test_declared_scenario_loads_from_the_environment(self):
        with patch.dict(os.environ, {"FANOUT_WORKERS": "2", "FANOUT_SHARDS": "3", "FANOUT_FLAKY": "1",
                                     "FANOUT_STEP_DEADLINE_MS": "700"}):
            scenario = load_scenario(os.path.join(ROOT, "studies/scenarios/fanout/scenario.py"))
        self.assertEqual(scenario.mission.context["step_deadline_ms"], 700)
        self.assertEqual(scenario.name, "fanout-k2-n3-flaky")
        self.assertEqual([agent.agent_id for agent in scenario.agents],
                         ["planner", "counter-1", "counter-2", FLAKY_AGENT_ID, "reducer"])
        self.assertEqual(scenario.definition(), [])
        self.assertEqual(scenario.metadata["step_deadline_ms"], 700)


if __name__ == "__main__":
    unittest.main()
