"""Avaliação offline das evidências; nenhuma dependência do SDK ou de LLM."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import uuid

from studies.logistics.domain import evaluate_plan, plan_mission
from studies.evidence import analysis_provenance
from studies.logistics.reporting import write_csv, write_chart


def evaluate_run(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    metadata = manifest.get("metadata", {})
    if metadata.get("study") != "logistics":
        raise ValueError(f"not a declarative logistics run: {directory}")
    world, case, strategy = metadata["world"], metadata["case"], metadata["strategy"]
    if strategy not in ("bdi-only", "llm-only", "hybrid"):
        raise ValueError(f"unknown strategy: {strategy}")
    path = directory / "results.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []
    by_sample = {row["sample"]: row for row in records}
    if len(by_sample) != len(records):
        raise ValueError(f"duplicate samples: {directory}")
    expected = set(range(1, manifest["repeat"] + 1))
    if set(by_sample) - expected:
        raise ValueError(f"unexpected samples: {directory}")
    rows = []
    for sample in sorted(expected):
        record = by_sample.get(sample, {"status": "MISSING", "error": "no completed sample recorded"})
        runtime_error = "" if record["status"] == "WORKFLOW_STATUS_COMPLETED" else (record.get("error") or record["status"])
        steps = record.get("steps", {})
        final = steps.get("plan" if strategy == "llm-only" else "execute", {}).get("result") or {}
        candidate = final.get("output") or {}
        if not isinstance(candidate.get("feasible"), bool):
            runtime_error = runtime_error or "missing or malformed plan result"
        interpretation = (steps.get("interpret", {}).get("result") or {}).get("output", {}).get("mission")
        tokens = sum(int((step.get("result") or {}).get("metadata", {}).get("usage", {}).get("total_tokens", 0) or 0)
                     for step in steps.values())
        try:
            evaluation = evaluate_plan(world, case["mission"], candidate)
        except (KeyError, TypeError, ValueError) as error:
            evaluation = evaluate_plan(world, case["mission"], {})
            runtime_error = runtime_error or f"malformed candidate: {error}"
        if runtime_error:
            evaluation.update(valid=False, safe=False, goal_reached=False, correct_rejection=False,
                              optimal=False, optimality_gap_minutes=None, failure_reason=f"runtime: {runtime_error}")
        rows.append({
            "execution_id": directory.name, "sample": sample, "case_id": case["id"], "strategy": strategy,
            "model": metadata.get("model"),
            "world_sha256": hashlib.sha256(json.dumps(world, sort_keys=True).encode()).hexdigest(),
            "case_sha256": hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest(),
            "expected_mission": case["mission"], "request": case["request"], "candidate": candidate,
            "oracle": plan_mission(world, case["mission"]), "evaluation": evaluation,
            "interpretation": interpretation, "interpretation_exact": interpretation == case["mission"],
            "latency_ms": record.get("client_duration_ms"), "tokens": tokens, "runtime_error": runtime_error,
        })
    return rows


def summarize(rows):
    summaries = []
    for strategy in ("bdi-only", "llm-only", "hybrid"):
        selected = [row for row in rows if row["strategy"] == strategy]
        if not selected:
            continue
        if len({row["model"] for row in selected}) > 1:
            raise ValueError(f"evaluate different models separately for {strategy}")
        latencies = [row["latency_ms"] for row in selected if row["latency_ms"] is not None]
        groups = {}
        for row in selected:
            groups.setdefault((row["world_sha256"], row["case_sha256"]), []).append(row)
        comparable = [group for group in groups.values() if len(group) >= 2]
        consistent = sum(
            not any(row["runtime_error"] for row in group) and
            len({json.dumps(row["candidate"], sort_keys=True) for row in group}) == 1 for group in comparable
        )
        rate = lambda field: sum(row["evaluation"][field] for row in selected) / len(selected)
        summaries.append({
            "strategy": strategy, "runs": len(selected), "valid_rate": rate("valid"), "safe_rate": rate("safe"),
            "optimal_rate": rate("optimal"), "goal_rate": rate("goal_reached"),
            "correct_rejection_rate": rate("correct_rejection"),
            "runtime_success_rate": sum(not row["runtime_error"] for row in selected) / len(selected),
            "interpretation_accuracy": sum(row["interpretation_exact"] for row in selected) / len(selected) if strategy == "hybrid" else None,
            "consistency_rate": consistent / len(comparable) if comparable else None,
            "average_latency_ms": statistics.mean(latencies) if latencies else None,
            "p95_latency_ms": sorted(latencies)[round(.95 * (len(latencies) - 1))] if latencies else None,
            "total_tokens": sum(row["tokens"] for row in selected),
        })
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="run directories or campaign directories")
    parser.add_argument("--output", type=Path, default=Path(".ariadne/evaluations") / ("logistics-" + uuid.uuid4().hex))
    args = parser.parse_args(argv)
    runs = []
    campaigns = []
    for source in args.inputs:
        source = source.resolve()
        if (source / "manifest.json").is_file():
            runs.append(source)
        else:
            found = sorted((source / "runs").glob("*/manifest.json"))
            if not found:
                parser.error(f"no run evidence found: {source}")
            runs.extend(path.parent for path in found)
            campaign_path = source / "campaign.json"
            if campaign_path.is_file():
                campaign = json.loads(campaign_path.read_text())
                planned = campaign.get("planned_observations")
                if planned is None:
                    planned = len(campaign["cases"]) * len(campaign["strategies"]) * campaign["repetitions"]
                campaigns.append({"source": str(source), "status": campaign["status"],
                                  "planned_observations": planned, "recorded_runs": len(found)})
    rows = [row for directory in dict.fromkeys(runs) for row in evaluate_run(directory)]
    summaries = summarize(rows)
    args.output.mkdir(parents=True, exist_ok=False)
    document = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
                "sources": [str(path) for path in dict.fromkeys(runs)], "campaigns": campaigns,
                "rows": rows, "summary": summaries,
                "provenance": analysis_provenance(__file__, list(dict.fromkeys(runs)),
                    [Path(__file__).with_name("domain.py"), Path(__file__).with_name("reporting.py")]),
                "limitations": ["shared domain rules between planner and evaluator", "correct rejections count as optimal",
                                "consistency requires at least two observations of the same case and world",
                                "new workflow latencies are not identical to historical single-task measurements"]}
    if any(campaign["recorded_runs"] < campaign["planned_observations"] for campaign in campaigns):
        document["limitations"].append("incomplete campaign: unstarted observations are not included in rates")
    (args.output / "logistics-results.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    write_csv(args.output / "logistics-summary.csv", summaries)
    write_chart(args.output / "logistics-quality.svg", summaries)
    print(f"Avaliação offline: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
