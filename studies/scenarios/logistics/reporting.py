"""Relatórios offline; não inicia runtime nem agentes."""
import csv
import statistics
import json
from collections import defaultdict

def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((p / 100) * (len(ordered) - 1))]


def aggregate(rows):
    summaries = []
    for strategy in ("bdi-only", "llm-only", "hybrid"):
        selected = [row for row in rows if row["strategy"] == strategy]
        latencies = [row["latency_ms"] for row in selected]
        by_case = defaultdict(list)
        for row in selected:
            by_case[row["case_id"]].append(json.dumps(row["candidate"], sort_keys=True))
        consistent = sum(len(set(values)) == 1 for values in by_case.values())
        summaries.append({
            "strategy": strategy,
            "runs": len(selected),
            "valid_rate": sum(row["evaluation"]["valid"] for row in selected) / len(selected),
            "safe_rate": sum(row["evaluation"]["safe"] for row in selected) / len(selected),
            "optimal_rate": sum(row["evaluation"]["optimal"] for row in selected) / len(selected),
            "goal_rate": sum(row["evaluation"]["goal_reached"] for row in selected) / len(selected),
            "correct_rejection_rate": sum(row["evaluation"]["correct_rejection"] for row in selected) / len(selected),
            "runtime_success_rate": sum(not row["runtime_error"] for row in selected) / len(selected),
            "interpretation_accuracy": (
                sum(row["interpretation_exact"] for row in selected) / len(selected)
                if strategy == "hybrid" else None
            ),
            "consistency_rate": consistent / len(by_case),
            "average_latency_ms": statistics.mean(latencies),
            "p95_latency_ms": percentile(latencies, 95),
            "total_tokens": sum(row["tokens"] for row in selected),
        })
    return summaries


def write_csv(path, rows):
    fields = [
        "strategy", "runs", "valid_rate", "safe_rate", "optimal_rate", "goal_rate",
        "correct_rejection_rate", "runtime_success_rate",
        "interpretation_accuracy", "consistency_rate", "average_latency_ms",
        "p95_latency_ms", "total_tokens",
    ]
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_chart(path, summaries):
    colors = {"bdi-only": "#7c3aed", "llm-only": "#ef4444", "hybrid": "#059669"}
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="820" height="390" viewBox="0 0 820 390">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="24" y="28" font-family="sans-serif" font-size="17">Validade, segurança e consistência por estratégia</text>',
    ]
    metrics = [("valid_rate", "planos válidos"), ("optimal_rate", "planos ótimos"), ("consistency_rate", "consistência")]
    for group, (field, label) in enumerate(metrics):
        base_x = 70 + group * 250
        parts.append(f'<text x="{base_x + 80}" y="350" text-anchor="middle" font-family="sans-serif" font-size="12">{label}</text>')
        for index, row in enumerate(summaries):
            value = row[field]
            height = (value or 0) * 250
            x = base_x + index * 55
            y = 320 - height
            parts.append(f'<rect x="{x}" y="{y:.1f}" width="42" height="{height:.1f}" fill="{colors[row["strategy"]]}"/>')
            label = "N/A" if value is None else f"{value*100:.0f}%"
            parts.append(f'<text x="{x+21}" y="{y-6:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{label}</text>')
    for index, row in enumerate(summaries):
        x = 270 + index * 120
        parts.append(f'<rect x="{x}" y="370" width="12" height="12" fill="{colors[row["strategy"]]}"/>')
        parts.append(f'<text x="{x+17}" y="380" font-family="sans-serif" font-size="11">{row["strategy"]}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
