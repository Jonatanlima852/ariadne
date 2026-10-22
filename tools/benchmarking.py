"""Medição e exportação compartilhadas; os casos pertencem aos cenários."""

from __future__ import annotations

import csv
import json
import os
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


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
    maximum = max((row["average_latency_ms"] for row in plotted), default=1) or 1
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


def run_benchmark(source, collect):
    from ariadne_sdk import RuntimeClient
    output_dir = Path(os.getenv("BENCHMARK_OUTPUT_DIR", Path(source).parent / "results/current"))
    output_dir.mkdir(parents=True, exist_ok=True)
    address = os.getenv("ORCHESTRATOR_ADDR", "localhost:54052")
    # Primeiro heartbeat contém a carga usada por LEAST_LOADED.
    time.sleep(1.2)
    with RuntimeClient(Path(source).parents[1].name, address) as client:
        raw, summaries = collect(client, address)
    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "orchestrator": address, "raw": raw, "summary": summaries,
        "limitations": {"sample_note": "Rotas e recuperação usam uma amostra de integração; não permitem inferência estatística."},
    }
    (output_dir / "results.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    write_summary(output_dir / "summary.csv", summaries)
    write_chart(output_dir / "latency.svg", summaries)
    print(f"BENCHMARK APROVADO output={output_dir}")
    return output_dir, summaries
