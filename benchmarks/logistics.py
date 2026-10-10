"""Compara BDI-only, LLM-only e LLM+BDI em missões restritas."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sdk/python/src"))

from studies.logistics import evaluate_plan, plan_mission
from tg_sdk import Scenario
from studies.logistics.reporting import aggregate, write_csv, write_chart
from studies.logistics.legacy import run_bdi, run_llm, run_hybrid


def measured(operation):
    started = time.perf_counter()
    try:
        return operation(), (time.perf_counter() - started) * 1000, ""
    except Exception as error:
        return None, (time.perf_counter() - started) * 1000, str(error)


def usage_tokens(metadata):
    usage = metadata.get("usage", {}) if metadata else {}
    return int(usage.get("total_tokens", 0) or 0)


def extract(strategy, result):
    if strategy in ("bdi-only", "llm-only"):
        result.assert_completed()
        return result.output, usage_tokens(result.metadata), None
    result.assert_completed()
    interpreted = result.steps["interpret"]["result"]
    executed = result.steps["execute"]["result"]
    return (
        executed.output,
        usage_tokens(interpreted.metadata),
        interpreted.output.get("mission"),
    )


def main():
    world = json.loads((ROOT / "studies/logistics/world.json").read_text())
    cases = json.loads((ROOT / "studies/logistics/cases.json").read_text())
    repetitions = int(os.getenv("LOGISTICS_REPETITIONS", "2"))
    output_dir = Path(os.getenv("LOGISTICS_OUTPUT_DIR", ROOT / "benchmarks/results/logistics-current"))
    output_dir.mkdir(parents=True, exist_ok=True)
    address = os.getenv("ORCHESTRATOR_ADDR", "localhost:54052")
    rows = []

    with Scenario("logistics-benchmark", address) as scenario:
        for repetition in range(1, repetitions + 1):
            for case in cases:
                oracle = plan_mission(world, case["mission"])
                for strategy, operation in (
                    ("bdi-only", lambda c=case: run_bdi(scenario, c, world)),
                    ("llm-only", lambda c=case: run_llm(scenario, c, world)),
                    ("hybrid", lambda c=case: run_hybrid(scenario, c, world)),
                ):
                    result, latency, runtime_error = measured(operation)
                    candidate, tokens, interpreted = {}, 0, None
                    if result is not None:
                        try:
                            candidate, tokens, interpreted = extract(strategy, result)
                        except Exception as error:
                            runtime_error = runtime_error or str(error)
                    evaluation = evaluate_plan(world, case["mission"], candidate)
                    if runtime_error:
                        evaluation = {
                            **evaluation,
                            "valid": False,
                            "safe": False,
                            "goal_reached": False,
                            "correct_rejection": False,
                            "optimal": False,
                            "optimality_gap_minutes": None,
                            "failure_reason": f"runtime: {runtime_error}",
                        }
                    row = {
                        "case_id": case["id"],
                        "repetition": repetition,
                        "strategy": strategy,
                        "request": case["request"],
                        "expected_mission": case["mission"],
                        "oracle": oracle,
                        "candidate": candidate,
                        "evaluation": evaluation,
                        "interpretation": interpreted,
                        "interpretation_exact": interpreted == case["mission"] if interpreted else False,
                        "latency_ms": latency,
                        "tokens": tokens,
                        "runtime_error": runtime_error,
                    }
                    rows.append(row)
                    print(
                        f"{strategy:8} case={case['id']:24} rep={repetition} "
                        f"valid={evaluation['valid']} latency_ms={latency:.1f}",
                        flush=True,
                    )

    summaries = aggregate(rows)
    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": os.getenv("LLM_MODEL", "gpt-5.6-luna"),
        "repetitions": repetitions,
        "case_count": len(cases),
        "method": "ground-truth mission and deterministic action simulator",
        "rows": rows,
        "summary": summaries,
    }
    (output_dir / "logistics-results.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(output_dir / "logistics-summary.csv", summaries)
    write_chart(output_dir / "logistics-quality.svg", summaries)
    print(json.dumps(summaries, indent=2), flush=True)
    print(f"LOGISTICS BENCHMARK COMPLETE output={output_dir}", flush=True)


if __name__ == "__main__":
    main()
