"""Benchmark do cenário contra seu runtime Docker."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sdk/python/src"))
from tools.benchmarking import measured, task_case, summarize, workflow_sample, run_benchmark


def collect(client, address):
    raw, summaries = {}, []
    for policy in ("FIRST_AVAILABLE", "ROUND_ROBIN", "LEAST_LOADED"):
        samples = task_case(client, f"B-{policy.lower()}", "benchmark-policy", 12, policy)
        raw[policy] = samples
        summaries.append(summarize(f"B-{policy}", samples, policy=policy))
    return {"B": raw}, summaries


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



if __name__ == "__main__":
    output, summaries = run_benchmark(__file__, collect)
    write_distribution_chart(output / "agent-distribution.svg", summaries)
