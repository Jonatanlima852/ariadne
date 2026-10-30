"""Funções de análise sobre um ``MissionResult`` e um ``events.jsonl`` construídos à mão."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from studies.scenarios.fanout.analysis import (
    aggregate, analyze_runs, analyze_sample, completeness, expected_events, find_runs, gantt_svg, speedup_svg,
    speedup_table, write_outputs,
)

ORIGIN = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
MISSION = "m-1"
ROOT_TASK = "mission-m-1"


def ts(ms):
    return (ORIGIN + timedelta(milliseconds=ms)).isoformat().replace("+00:00", "Z")


def event(ms, kind, **fields):
    return {"event_id": f"e{ms}-{kind}", "type": kind, "timestamp": ts(ms), **fields}


def step(step_id, task_id, agent, started, completed, attempt=1):
    return {"step_id": step_id, "status": "WORKFLOW_STEP_STATUS_COMPLETED",
            "task": {"task_id": task_id, "attempt": attempt, "assigned_agent_id": agent},
            "result": {"task_id": task_id, "agent_id": agent, "status": "TASK_STATUS_COMPLETED",
                       "started_at": ts(started), "completed_at": ts(completed), "output": {}}}


def fixture(flaky=True, workers=2):
    """Dois passos de mapa e um reduce; com ``flaky``, map-2 estoura o prazo e é reatribuído."""
    second_agent, second_attempt, second_start = ("counter-1", 2, 1517) if flaky else ("counter-2", 1, 12)
    second_end = second_start + 296
    finish = second_end + 20
    document = {
        "mission_id": MISSION, "root_task_id": ROOT_TASK, "status": "MISSION_STATUS_COMPLETED",
        "created_at": ts(0), "completed_at": ts(finish + 25), "sample": 1, "client_duration_ms": finish + 30.0,
        "output": {"total_words": 40},
        "rounds": [
            {"round": 1, "action": "PLANNER_ACTION_PLAN", "started_at": ts(0), "completed_at": ts(finish + 5),
             "planner_task": {"task_id": "p1"}, "planner_result": {"started_at": ts(2), "completed_at": ts(4)},
             "result": {"status": "WORKFLOW_STATUS_COMPLETED", "step_results": [
                 step("map-1", "t1", "counter-1", 12, 308),
                 step("map-2", "t2", second_agent, second_start, second_end, second_attempt),
                 step("reduce", "t3", "reducer", finish - 10, finish - 4),
             ]}},
            {"round": 2, "action": "PLANNER_ACTION_DONE", "started_at": ts(finish + 6), "completed_at": ts(finish + 20),
             "planner_task": {"task_id": "p2"}, "planner_result": {"started_at": ts(finish + 8), "completed_at": ts(finish + 12)}},
        ],
    }
    m = {"mission_id": MISSION}
    events = [
        event(0, "MISSION_CREATED", round=0, **m), event(0, "MISSION_ROUND_STARTED", round=1, **m),
        event(1, "TASK_ASSIGNED", task_id="p1", agent_id="planner", details="attempt=1"),
        event(5, "TASK_COMPLETED", task_id="p1", agent_id="planner", details="attempt=1"),
        event(6, "MISSION_PLANNED", round=1, agent_id="planner", **m),
        event(7, "WORKFLOW_CREATED", task_id=ROOT_TASK), event(7, "WORKFLOW_VALIDATED", task_id=ROOT_TASK),
        event(7, "WORKFLOW_STARTED", task_id=ROOT_TASK),
        event(8, "STEP_READY", task_id=ROOT_TASK, step_id="map-1"), event(8, "STEP_READY", task_id=ROOT_TASK, step_id="map-2"),
        event(9, "STEP_STARTED", task_id="t1", step_id="map-1"), event(9, "STEP_STARTED", task_id="t2", step_id="map-2"),
        event(10, "TASK_ASSIGNED", task_id="t1", agent_id="counter-1", details="attempt=1"),
        event(10, "TASK_ASSIGNED", task_id="t2", agent_id="counter-flaky" if flaky else "counter-2", details="attempt=1"),
        event(310, "TASK_COMPLETED", task_id="t1", agent_id="counter-1", details="attempt=1"),
    ]
    if flaky:
        events += [
            event(1510, "TASK_TIMEOUT", task_id="t2", agent_id="counter-flaky", details="attempt=1"),
            event(1515, "TASK_REASSIGNED", task_id="t2", agent_id="counter-1", details="attempt=2"),
            event(1815, "TASK_COMPLETED", task_id="t2", agent_id="counter-1", details="attempt=2"),
        ]
    else:
        events.append(event(310, "TASK_COMPLETED", task_id="t2", agent_id="counter-2", details="attempt=1"))
    events += [
        event(second_end + 3, "STEP_COMPLETED", task_id="t1", step_id="map-1", agent_id="counter-1", attempt=1),
        event(second_end + 3, "STEP_COMPLETED", task_id="t2", step_id="map-2", agent_id=second_agent, attempt=second_attempt),
        event(second_end + 4, "STEP_READY", task_id=ROOT_TASK, step_id="reduce"),
        event(second_end + 5, "STEP_STARTED", task_id="t3", step_id="reduce"),
        event(finish - 12, "TASK_ASSIGNED", task_id="t3", agent_id="reducer", details="attempt=1"),
        event(finish - 2, "TASK_COMPLETED", task_id="t3", agent_id="reducer", details="attempt=1"),
        event(finish - 1, "STEP_COMPLETED", task_id="t3", step_id="reduce", agent_id="reducer", attempt=1),
        event(finish, "WORKFLOW_COMPLETED", task_id=ROOT_TASK, step_id="reduce"),
        event(finish + 5, "MISSION_ROUND_COMPLETED", round=1, agent_id="planner", **m),
        event(finish + 6, "MISSION_ROUND_STARTED", round=2, **m),
        event(finish + 7, "TASK_ASSIGNED", task_id="p2", agent_id="planner", details="attempt=1"),
        event(finish + 13, "TASK_COMPLETED", task_id="p2", agent_id="planner", details="attempt=1"),
        event(finish + 14, "MISSION_PLANNED", round=2, agent_id="planner", **m),
        event(finish + 20, "MISSION_ROUND_COMPLETED", round=2, agent_id="planner", **m),
        event(finish + 25, "MISSION_COMPLETED", round=2, **m),
        # Ruído de outra missão: deve ser ignorado.
        event(50, "TASK_ASSIGNED", task_id="other", agent_id="counter-9", details="attempt=1"),
    ]
    settings = {"workers": workers, "shards": 2, "flaky": flaky, "study": "fanout"}
    return document, events, settings


class SampleAnalysisTests(unittest.TestCase):
    def test_parallelism_factor_and_concurrency_without_failures(self):
        document, events, settings = fixture(flaky=False)
        sample = analyze_sample(document, events, settings)
        self.assertEqual(sample["status"], "COMPLETED")
        self.assertAlmostEqual(sample["wall_ms"], 353.0)
        first = sample["rounds"][0]
        self.assertAlmostEqual(first["map_parallelism_factor"], 2.0)
        self.assertAlmostEqual(first["map_steps"]["sum_ms"], 592.0)
        self.assertGreater(first["parallelism_factor"], 1.0)
        self.assertEqual(sample["map_concurrency_peak"], 2)
        self.assertAlmostEqual(sample["map_concurrency_mean"], 2.0)
        self.assertEqual(sample["reassignments"], {"events": 0, "timeouts": 0, "steps_with_attempt_gt_1": 0, "steps": []})
        self.assertEqual(sample["recovery"], [])
        self.assertEqual(sample["completeness"]["ratio"], 1.0)
        self.assertEqual([marker["round"] for marker in sample["round_markers"]], [1, 2])

    def test_reassignment_recovery_and_attempts_with_a_timeout(self):
        document, events, settings = fixture(flaky=True)
        sample = analyze_sample(document, events, settings)
        self.assertEqual(sample["reassignments"]["events"], 1)
        self.assertEqual(sample["reassignments"]["timeouts"], 1)
        self.assertEqual(sample["reassignments"]["steps_with_attempt_gt_1"], 1)
        self.assertEqual(sample["reassignments"]["steps"][0],
                         {"step_id": "map-2", "round": 1, "attempts": 2, "final_agent": "counter-1", "first_agent": "counter-flaky"})
        recovery = sample["recovery"][0]
        self.assertEqual((recovery["step_id"], recovery["timeout_agent"], recovery["recovered_by"]), ("map-2", "counter-flaky", "counter-1"))
        self.assertAlmostEqual(recovery["timeout_detection_ms"], 1500.0)
        self.assertAlmostEqual(recovery["recovery_ms"], 5.0)
        self.assertAlmostEqual(recovery["completion_after_timeout_ms"], 305.0)
        attempts = {(row["step_id"], row["attempt"]): row for row in sample["attempts"]}
        self.assertEqual(attempts[("map-2", 1)]["outcome"], "timeout")
        self.assertEqual(attempts[("map-2", 1)]["agent_id"], "counter-flaky")
        self.assertTrue(attempts[("map-2", 2)]["reassigned"])
        self.assertAlmostEqual(attempts[("map-2", 2)]["duration_ms"], 300.0)
        self.assertEqual(sample["map_concurrency_peak"], 2)
        # A tentativa estourada conta como ocupação; o fator de paralelismo dos passos não.
        self.assertLess(sample["map_parallelism_factor"], 1.0)
        self.assertEqual(sample["completeness"]["ratio"], 1.0)
        self.assertNotIn("other", {row["task_id"] for row in sample["attempts"]})

    def test_completeness_reports_missing_events(self):
        document, events, _ = fixture(flaky=True)
        expected = expected_events(document)
        self.assertEqual(expected[("TASK_TIMEOUT", "t2", "")], 1)
        self.assertEqual(expected[("TASK_REASSIGNED", "t2", "")], 1)
        self.assertEqual(expected[("WORKFLOW_COMPLETED", ROOT_TASK, "")], 1)
        self.assertNotIn(("TASK_CREATED", "t1", ""), expected)
        without = [item for item in events if not (item["type"] == "TASK_REASSIGNED" and item["task_id"] == "t2")]
        result = completeness(document, without)
        self.assertEqual(result["present"], result["expected"] - 1)
        self.assertEqual(result["missing"], [{"type": "TASK_REASSIGNED", "task_id": "t2", "step_id": "", "expected": 1, "present": 0}])
        self.assertLess(result["ratio"], 1.0)


class AggregationTests(unittest.TestCase):
    def test_aggregate_and_speedup_table(self):
        slow = analyze_sample(*fixture(flaky=True))
        quick = analyze_sample(*fixture(flaky=False))
        summary = aggregate([slow, slow])
        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["reassignment_events"], 2)
        self.assertAlmostEqual(summary["recovery_ms"]["median"], 5.0)
        self.assertAlmostEqual(summary["recovery_ms"]["p95"], 5.0)
        self.assertEqual(summary["recovery_ms"]["n"], 2)
        self.assertAlmostEqual(summary["completeness"]["mean"], 1.0)
        groups = {
            "K=1": {"settings": {"workers": 1, "shards": 2, "flaky": False}, "summary": aggregate([quick])},
            "K=2": {"settings": {"workers": 2, "shards": 2, "flaky": False}, "summary": aggregate([quick])},
        }
        groups["K=1"]["summary"]["wall_ms"]["median"] = 706.0
        rows = speedup_table(groups)
        self.assertEqual([row["workers"] for row in rows], [1, 2])
        self.assertAlmostEqual(rows[1]["speedup"], 2.0)
        self.assertAlmostEqual(rows[1]["ideal"], 2.0)
        self.assertAlmostEqual(rows[0]["speedup"], 1.0)
        self.assertEqual(speedup_table({"only": groups["K=1"]}), [])


class OutputTests(unittest.TestCase):
    def test_figures_and_reports_from_a_run_directory(self):
        document, events, settings = fixture(flaky=True)
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "runs" / "ariadne-abc"
            run.mkdir(parents=True)
            (run / "results.jsonl").write_text(json.dumps(document) + "\n")
            (run / "events.jsonl").write_text("".join(json.dumps(item) + "\n" for item in events))
            (run / "manifest.json").write_text(json.dumps({"metadata": settings, "mission": {"limits": {"max_parallel": 2}}}))
            self.assertEqual(find_runs([Path(temporary)]), [run])
            report = analyze_runs([run])
            self.assertEqual(list(report["groups"]), ["K=2 N=2 flaky"])
            self.assertEqual(report["groups"]["K=2 N=2 flaky"]["summary"]["reassignment_events"], 1)
            written = write_outputs(report, Path(temporary) / "analysis")
            names = {path.name for path in written}
            self.assertIn("report.json", names)
            self.assertIn("report.md", names)
            self.assertIn("gantt-k2-n2-flaky-s1.svg", names)
            saved = json.loads((Path(temporary) / "analysis/report.json").read_text())
            self.assertEqual(saved["samples"][0]["reassignments"]["events"], 1)
            markdown = (Path(temporary) / "analysis/report.md").read_text()
            self.assertIn("| K=2 N=2 flaky | 1 | map-2 | counter-flaky | counter-1 | 2 |", markdown)
        sample = report["samples"][0]
        svg = gantt_svg(sample)
        for agent in ("planner", "counter-1", "counter-flaky", "reducer"):
            self.assertIn(f">{agent}<", svg)
        self.assertIn('fill="url(#hatch)"', svg)
        self.assertIn("map-2 (tentativa 2)", svg)
        chart = speedup_svg([
            {"shards": 2, "flaky": False, "workers": 1, "wall_median_ms": 700.0, "wall_p95_ms": 720.0, "speedup": 1.0, "ideal": 1.0},
            {"shards": 2, "flaky": False, "workers": 2, "wall_median_ms": 350.0, "wall_p95_ms": 360.0, "speedup": 2.0, "ideal": 2.0},
        ])
        self.assertIn("K=2", chart)
        self.assertIn("2.00x", chart)


if __name__ == "__main__":
    unittest.main()
