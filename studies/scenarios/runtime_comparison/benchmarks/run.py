"""Executa os casos A-D contra a topologia de benchmarks."""

from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "sdk/python/src"))

from ariadne_sdk import RuntimeClient


GOAL = "Planeje uma rota de A para D e explique por que ela foi escolhida"


def measured(operation):
    started = time.perf_counter()
    result = operation()
    return result, (time.perf_counter() - started) * 1000


def percentile(values, percentile_value):
    ordered = sorted(values)
    if not ordered:
        return None
    index = round((percentile_value / 100) * (len(ordered) - 1))
    return ordered[index]


def task_case(scenario, name, capability, count, policy="FIRST_AVAILABLE"):
    samples = []
    for index in range(count):
        result, latency = measured(lambda: scenario.submit(
            f"{name}-{index}", goal=f"benchmark {name} {index}",
            capabilities=[capability], task_type="BENCHMARK",
            selection_policy=policy,
        ))
        result.assert_completed()
        samples.append({
            "latency_ms": latency,
            "agent_id": result.agent_id,
            "status": result.status,
        })
    return samples


def summarize(case, samples, **extra):
    latencies = [sample["latency_ms"] for sample in samples]
    completed = [
        sample for sample in samples
        if sample["status"] in ("TASK_STATUS_COMPLETED", "WORKFLOW_STATUS_COMPLETED")
    ]
    agents = Counter(
        sample["agent_id"] for sample in samples if sample.get("agent_id")
    )
    return {
        "case": case,
        "runs": len(samples),
        "success_rate": len(completed) / len(samples) if samples else 0,
        "average_latency_ms": statistics.mean(latencies) if latencies else None,
        "p95_latency_ms": percentile(latencies, 95),
        "agent_distribution": dict(sorted(agents.items())),
        **extra,
    }


def workflow_sample(result, latency):
    return {
        "latency_ms": latency,
        "agent_id": "",
        "status": result.status,
        "workflow": result.to_dict(),
    }


def write_summary(path, summaries):
    fields = [
        "case", "runs", "success_rate", "average_latency_ms",
        "p95_latency_ms", "agent_distribution", "details",
    ]
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for summary in summaries:
            row = dict(summary)
            row["agent_distribution"] = json.dumps(
                row.get("agent_distribution", {}), sort_keys=True
            )
            details = {
                key: row.pop(key) for key in list(row)
                if key not in fields
            }
            row["details"] = json.dumps(details, ensure_ascii=False, sort_keys=True)
            writer.writerow(row)


def write_chart(path, summaries):
    plotted = [row for row in summaries if row["average_latency_ms"] is not None]
    width, height, left, bottom = 960, 440, 80, 90
    chart_height = height - bottom - 30
    maximum = max(row["average_latency_ms"] for row in plotted) or 1
    bar_width = max(30, (width - left - 30) // max(1, len(plotted)) - 12)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="24" y="24" font-family="sans-serif" font-size="16">Latência média por cenário/caso (ms)</text>',
        f'<line x1="{left}" y1="30" x2="{left}" y2="{height-bottom}" stroke="#333"/>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-20}" y2="{height-bottom}" stroke="#333"/>',
    ]
    for index, row in enumerate(plotted):
        value = row["average_latency_ms"]
        bar_height = value / maximum * chart_height
        x = left + 12 + index * (bar_width + 12)
        y = height - bottom - bar_height
        parts.extend([
            f'<rect x="{x}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" fill="#367bf5"/>',
            f'<text x="{x + bar_width/2:.1f}" y="{y-5:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{value:.1f}</text>',
            f'<text x="{x + bar_width/2:.1f}" y="{height-bottom+16}" text-anchor="end" transform="rotate(-35 {x + bar_width/2:.1f} {height-bottom+16})" font-family="sans-serif" font-size="10">{row["case"]}</text>',
        ])
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_distribution_chart(path, summaries):
    rows = [row for row in summaries if row["case"].startswith("B-")]
    agents = sorted({agent for row in rows for agent in row["agent_distribution"]})
    colors = ["#367bf5", "#20a464", "#f59e0b"]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="760" height="330" viewBox="0 0 760 330">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="24" y="28" font-family="sans-serif" font-size="16">Distribuição de 12 tasks por política</text>',
    ]
    for row_index, row in enumerate(rows):
        y = 65 + row_index * 80
        parts.append(f'<text x="20" y="{y+18}" font-family="sans-serif" font-size="11">{row["case"].removeprefix("B-")}</text>')
        x = 160
        for agent_index, agent in enumerate(agents):
            count = row["agent_distribution"].get(agent, 0)
            width = count * 35
            parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="24" fill="{colors[agent_index]}"/>')
            if count:
                parts.append(f'<text x="{x + width/2}" y="{y+17}" text-anchor="middle" fill="white" font-family="sans-serif" font-size="11">{agent}: {count}</text>')
            x += width
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_message_chart(path):
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="620" height="180" viewBox="0 0 620 180">\n'
        '<rect width="100%" height="100%" fill="white"/>\n'
        '<text x="24" y="30" font-family="sans-serif" font-size="16">MessageEnvelope por cenário</text>\n'
        '<line x1="60" y1="130" x2="590" y2="130" stroke="#333"/>\n'
        '<text x="310" y="90" text-anchor="middle" font-family="sans-serif" font-size="14">0 — execução usa AgentService direto</text>\n'
        '</svg>\n',
        encoding="utf-8",
    )


def main():
    output_dir = Path(os.getenv("BENCHMARK_OUTPUT_DIR", ROOT / "studies/scenarios/runtime_comparison/benchmarks/results/current"))
    output_dir.mkdir(parents=True, exist_ok=True)
    address = os.getenv("ORCHESTRATOR_ADDR", "localhost:54052")
    # Aguarda o primeiro heartbeat, que carrega a telemetria usada por LEAST_LOADED.
    time.sleep(1.2)
    raw, summaries = {}, []

    with RuntimeClient("benchmark-suite", address) as scenario:
        samples = task_case(scenario, "A-basic", "benchmark-basic", 10)
        raw["A"] = samples
        summaries.append(summarize("A-basic", samples))

        raw["B"] = {}
        for policy in ("FIRST_AVAILABLE", "ROUND_ROBIN", "LEAST_LOADED"):
            samples = task_case(
                scenario, f"B-{policy.lower()}", "benchmark-policy", 12, policy
            )
            raw["B"][policy] = samples
            summaries.append(summarize(f"B-{policy}", samples, policy=policy))

        workflow, latency = measured(lambda: RuntimeClient(
            "benchmark-c", address, entry_capability="task-decomposition"
        ).ask(GOAL))
        workflow.assert_completed().assert_agent_kind_used("bdi").assert_agent_kind_used("llm")
        sample = workflow_sample(workflow, latency)
        raw["C"] = [sample]
        summaries.append(summarize(
            "C-heterogeneous", [sample],
            subtask_count=len(workflow.steps), message_count=0,
            explanation_present=bool(workflow.output.get("explanation")),
        ))

        recovered, latency = measured(lambda: scenario.submit(
            "D-recovery", goal="recover", capabilities=["benchmark-recovery"],
            task_type="FAILURE_BENCHMARK", deadline_ms=100,
            max_attempts=2, exclude_failed_agent=True,
        ))
        recovered.assert_completed()
        if recovered.agent_id != "b-healthy":
            raise AssertionError(f"reassignment selected {recovered.agent_id}")
        sample = {"latency_ms": latency, "agent_id": recovered.agent_id, "status": recovered.status}
        raw["D"] = [sample]
        summaries.append(summarize("D-reassignment", [sample], reassigned=True))

    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "orchestrator": address,
        "raw": raw,
        "summary": summaries,
        "limitations": {
            "message_count": "0: the evaluated workflow uses direct AgentService calls; the Messaging Service is evaluated separately",
            "sample_note": "C and D use one integration sample by default",
        },
    }
    (output_dir / "results.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_summary(output_dir / "summary.csv", summaries)
    write_chart(output_dir / "latency.svg", summaries)
    write_distribution_chart(output_dir / "agent-distribution.svg", summaries)
    write_message_chart(output_dir / "message-count.svg")
    print(f"BENCHMARKS A-D APROVADOS output={output_dir}")


if __name__ == "__main__":
    main()
