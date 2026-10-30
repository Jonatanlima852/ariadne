"""Análise das evidências do estudo de paralelismo e reatribuição.

Lê, de cada execução de ``./ariadne run``, o ``results.jsonl`` (um
``MissionResult`` do contrato por amostra), o ``events.jsonl`` do orquestrador
e o ``manifest.json``. Calcula, por amostra:

- intervalos dos passos (``started_at``/``completed_at`` do ``TaskResult``) e
  o fator de paralelismo = soma das durações / intervalo da rodada;
- tempo de parede da missão (``created_at`` a ``completed_at``);
- reatribuições: eventos ``TASK_REASSIGNED`` e passos com ``task.attempt > 1``;
- recuperação por passo reatribuído: ``TASK_REASSIGNED - TASK_TIMEOUT`` e
  ``TASK_COMPLETED - TASK_TIMEOUT``;
- completude do rastro contra o conjunto esperado de eventos da missão.

Entre repetições: mediana, média, desvio padrão e p95. Saídas: ``report.json``,
``report.md``, um Gantt SVG por amostra (passos por agente ao longo do tempo)
e, com execuções de K diferentes, ``speedup.svg``. Só biblioteca padrão; com
matplotlib disponível as figuras também saem em PNG.

Uso, da raiz do repositório:

    python -m studies.scenarios.fanout.analysis RUN_DIR [RUN_DIR ...] --output DIR
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.runtime_metrics.compute_metrics import percentile, summarize_task  # noqa: E402

MISSION_EVENTS = ("MISSION_ROUND_STARTED", "MISSION_PLANNED", "MISSION_ROUND_COMPLETED")
WORKFLOW_EVENTS = ("WORKFLOW_CREATED", "WORKFLOW_VALIDATED", "WORKFLOW_STARTED")
ATTEMPT_START = ("TASK_ASSIGNED", "TASK_REASSIGNED")
ATTEMPT_END = ("TASK_COMPLETED", "TASK_TIMEOUT", "TASK_FAILED")
_ATTEMPT = re.compile(r"attempt=(\d+)")

# Paleta de referência (validada para visão de cores): identidade por tipo de
# trabalho em ordem fixa; vermelho reservado ao estado "prazo estourado".
COLORS = {
    "map": "#2a78d6", "reduce": "#eb6834", "planner": "#1baf7a",
    "timeout": "#e34948", "reassigned": "#6250d6", "ideal": "#52514e",
    "surface": "#fcfcfb", "ink": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3df",
}


# ---------------------------------------------------------------------------
# Leitura das evidências
# ---------------------------------------------------------------------------


def parse_ms(text) -> float | None:
    """Carimbo RFC 3339 (eventos Go e JSON do contrato) em milissegundos de época."""
    if not text:
        return None
    return datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp() * 1000


def find_runs(paths) -> list[Path]:
    """Diretórios de execução (contêm ``results.jsonl``), direto ou por busca."""
    found = []
    for item in paths:
        path = Path(item)
        if (path / "results.jsonl").is_file():
            found.append(path)
        else:
            found.extend(sorted(candidate.parent for candidate in path.rglob("results.jsonl")))
    return list(dict.fromkeys(found))


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_run(directory: Path) -> dict:
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    settings = dict(manifest.get("metadata") or {})
    mission = manifest.get("mission") or {}
    settings.setdefault("workers", (mission.get("limits") or {}).get("max_parallel"))
    settings.setdefault("shards", (mission.get("context") or {}).get("shard_count"))
    records = [record for record in read_jsonl(directory / "results.jsonl") if "rounds" in record]
    return {"directory": directory, "manifest": manifest, "settings": settings,
            "records": records, "events": read_jsonl(directory / "events.jsonl")}


# ---------------------------------------------------------------------------
# Uma amostra
# ---------------------------------------------------------------------------


def _attempt_of(event) -> int:
    if event.get("attempt"):
        return int(event["attempt"])
    match = _ATTEMPT.search(event.get("details", "") or "")
    return int(match.group(1)) if match else 1


def _step_kind(step_id: str) -> str:
    if step_id == "planner":
        return "planner"
    if step_id.startswith("reduce"):
        return "reduce"
    return "map"


def task_index(document: dict) -> dict[str, dict]:
    """``task_id`` -> passo (``step_id``, rodada, tipo) para todas as tarefas da missão."""
    index = {}
    for item in document.get("rounds") or []:
        planner_task = item.get("planner_task") or {}
        if planner_task.get("task_id"):
            index[planner_task["task_id"]] = {"step_id": "planner", "round": item.get("round"), "kind": "planner"}
        for step in (item.get("result") or {}).get("step_results", []):
            task_id = (step.get("task") or {}).get("task_id")
            if task_id:
                index[task_id] = {"step_id": step["step_id"], "round": item.get("round"),
                                  "kind": _step_kind(step["step_id"])}
    return index


def mission_events(document: dict, events: list[dict]) -> list[dict]:
    """Eventos desta missão: por ``mission_id``, pela tarefa raiz e pelas tarefas dos passos."""
    mission_id, root = document.get("mission_id"), document.get("root_task_id")
    tasks = task_index(document)
    selected = [event for event in events
                if event.get("mission_id") == mission_id or event.get("task_id") == root
                or event.get("task_id") in tasks]
    # Ordena pelo instante, não pelo texto: RFC 3339 omite a fração quando é zero.
    return sorted(selected, key=lambda event: parse_ms(event["timestamp"]))


def attempts_from_events(document: dict, events: list[dict], origin_ms: float) -> list[dict]:
    """Uma linha por tentativa (atribuição até término), a matéria-prima do Gantt."""
    tasks = task_index(document)
    rows, open_attempts = [], {}
    for event in events:
        task_id = event.get("task_id")
        if task_id not in tasks:
            continue
        if event["type"] in ATTEMPT_START:
            open_attempts[task_id] = {
                "task_id": task_id, **tasks[task_id], "agent_id": event.get("agent_id", ""),
                "attempt": _attempt_of(event), "start_ms": parse_ms(event["timestamp"]) - origin_ms,
                "end_ms": None, "outcome": "open", "reassigned": event["type"] == "TASK_REASSIGNED",
            }
        elif event["type"] in ATTEMPT_END and task_id in open_attempts:
            row = open_attempts.pop(task_id)
            row["end_ms"] = parse_ms(event["timestamp"]) - origin_ms
            row["outcome"] = event["type"].removeprefix("TASK_").lower()
            row["duration_ms"] = row["end_ms"] - row["start_ms"]
            rows.append(row)
    rows.extend(open_attempts.values())
    return sorted(rows, key=lambda row: (row["start_ms"], row["step_id"]))


def concurrency(attempts: list[dict], kinds=("map", "reduce")) -> dict | None:
    """Quantas tentativas (inclusive as que estouraram o prazo) rodavam ao mesmo tempo.

    ``peak`` é o máximo instantâneo; ``mean`` é a soma das durações das
    tentativas dividida pelo intervalo em que houve alguma em execução.
    """
    rows = [row for row in attempts if row["kind"] in kinds and row["end_ms"] is not None]
    if not rows:
        return None
    changes = sorted([(row["start_ms"], 1) for row in rows] + [(row["end_ms"], -1) for row in rows])
    running = peak = 0
    for _, delta in changes:
        running += delta
        peak = max(peak, running)
    span = max(row["end_ms"] for row in rows) - min(row["start_ms"] for row in rows)
    busy = sum(row["end_ms"] - row["start_ms"] for row in rows)
    return {"peak": peak, "mean": (busy / span) if span > 0 else None, "busy_ms": busy, "span_ms": span}


def round_metrics(item: dict, origin_ms: float) -> dict:
    """Intervalos dos passos de uma rodada PLAN e o fator de paralelismo."""
    steps = []
    for step in (item.get("result") or {}).get("step_results", []):
        result, task = step.get("result") or {}, step.get("task") or {}
        started, completed = parse_ms(result.get("started_at")), parse_ms(result.get("completed_at"))
        steps.append({
            "step_id": step["step_id"], "kind": _step_kind(step["step_id"]),
            "status": step.get("status", "").removeprefix("WORKFLOW_STEP_STATUS_"),
            "agent_id": result.get("agent_id", ""), "attempt": int(task.get("attempt") or 1),
            "started_ms": None if started is None else started - origin_ms,
            "completed_ms": None if completed is None else completed - origin_ms,
            "duration_ms": None if started is None or completed is None else completed - started,
        })
    timed = [step for step in steps if step["duration_ms"] is not None]
    maps = [step for step in timed if step["kind"] == "map"]

    def factor(group):
        if not group:
            return None
        span = max(step["completed_ms"] for step in group) - min(step["started_ms"] for step in group)
        total = sum(step["duration_ms"] for step in group)
        return {"sum_ms": total, "span_ms": span, "factor": (total / span) if span > 0 else None}

    started, completed = parse_ms(item.get("started_at")), parse_ms(item.get("completed_at"))
    planner = item.get("planner_result") or {}
    planner_started, planner_done = parse_ms(planner.get("started_at")), parse_ms(planner.get("completed_at"))
    return {
        "round": item.get("round"), "action": item.get("action", "").removeprefix("PLANNER_ACTION_"),
        "workflow_status": (item.get("result") or {}).get("status", "").removeprefix("WORKFLOW_STATUS_") or None,
        "round_span_ms": None if started is None or completed is None else completed - started,
        "planner_ms": None if planner_started is None or planner_done is None else planner_done - planner_started,
        "steps": steps, "all_steps": factor(timed), "map_steps": factor(maps),
        "parallelism_factor": (factor(timed) or {}).get("factor"),
        "map_parallelism_factor": (factor(maps) or {}).get("factor"),
    }


def recovery_metrics(document: dict, events: list[dict]) -> list[dict]:
    """Por tarefa com ``TASK_TIMEOUT``: detecção, recuperação e conclusão após o prazo."""
    tasks = task_index(document)
    by_task = defaultdict(list)
    for event in events:
        if event.get("task_id") in tasks:
            by_task[event["task_id"]].append(event)
    rows = []
    for task_id, items in by_task.items():
        timeouts = [event for event in items if event["type"] == "TASK_TIMEOUT"]
        if not timeouts:
            continue
        # Reutiliza o cálculo de tools/runtime_metrics (recovery_ms e contagem).
        summary = summarize_task(task_id, [{"type": "TASK_CREATED", "timestamp": items[0]["timestamp"]}, *items])
        timeout_ms = parse_ms(timeouts[0]["timestamp"])
        assigned = [event for event in items if event["type"] in ATTEMPT_START
                    and parse_ms(event["timestamp"]) <= timeout_ms]
        completed = [event for event in items if event["type"] == "TASK_COMPLETED"]
        reassigned = [event for event in items if event["type"] == "TASK_REASSIGNED"]
        rows.append({
            "task_id": task_id, "step_id": tasks[task_id]["step_id"], "round": tasks[task_id]["round"],
            "timeout_agent": timeouts[0].get("agent_id", ""),
            "recovered_by": reassigned[-1].get("agent_id", "") if reassigned else None,
            "timeouts": len(timeouts), "reassignments": summary["reassignment_count"],
            "timeout_detection_ms": (timeout_ms - parse_ms(assigned[-1]["timestamp"])) if assigned else None,
            "recovery_ms": summary["recovery_ms"],
            "completion_after_timeout_ms": (parse_ms(completed[-1]["timestamp"]) - timeout_ms) if completed else None,
        })
    return sorted(rows, key=lambda row: (row["round"] or 0, row["step_id"]))


def expected_events(document: dict) -> Counter:
    """Conjunto esperado de eventos de uma missão, como contagem por chave.

    Chave: ``(tipo, task_id, step_id)``. Por missão: ``MISSION_CREATED``, por
    rodada ``MISSION_ROUND_STARTED``/``MISSION_PLANNED``/``MISSION_ROUND_COMPLETED``
    e o evento terminal do estado. Por rodada PLAN: ``WORKFLOW_CREATED``,
    ``WORKFLOW_VALIDATED``, ``WORKFLOW_STARTED`` e o terminal do workflow. Por
    chamada ao planejador: ``TASK_ASSIGNED`` e ``TASK_COMPLETED``. Por passo:
    ``STEP_READY``, ``STEP_STARTED``, ``TASK_ASSIGNED``, o terminal da tarefa e
    ``STEP_COMPLETED``/``STEP_FAILED``; para cada tentativa além da primeira,
    ``TASK_TIMEOUT`` e ``TASK_REASSIGNED``. O orquestrador não emite
    ``TASK_CREATED`` para passos de workflow, por isso ele não entra.
    """
    mission_id, root = document.get("mission_id"), document.get("root_task_id")
    expected = Counter()
    expected[("MISSION_CREATED", mission_id, "")] += 1
    status = document.get("status", "").removeprefix("MISSION_STATUS_")
    expected[(f"MISSION_{status}", mission_id, "")] += 1
    for item in document.get("rounds") or []:
        for name in MISSION_EVENTS:
            expected[(name, mission_id, "")] += 1
        planner_task = (item.get("planner_task") or {}).get("task_id")
        if planner_task:
            planner_status = (item.get("planner_result") or {}).get("status", "TASK_STATUS_COMPLETED")
            expected[("TASK_ASSIGNED", planner_task, "")] += 1
            expected[(planner_status.replace("TASK_STATUS_", "TASK_"), planner_task, "")] += 1
        result = item.get("result")
        if not result:
            continue
        for name in WORKFLOW_EVENTS:
            expected[(name, root, "")] += 1
        workflow_status = result.get("status", "").removeprefix("WORKFLOW_STATUS_")
        expected[(f"WORKFLOW_{workflow_status}", root, "")] += 1
        for step in result.get("step_results", []):
            step_id, task = step["step_id"], step.get("task") or {}
            expected[("STEP_READY", root, step_id)] += 1
            if not task.get("task_id"):
                continue
            task_id, attempt = task["task_id"], int(task.get("attempt") or 1)
            step_status = step.get("status", "").removeprefix("WORKFLOW_STEP_STATUS_")
            task_status = (step.get("result") or {}).get("status", "").replace("TASK_STATUS_", "TASK_")
            expected[("STEP_STARTED", task_id, step_id)] += 1
            expected[("TASK_ASSIGNED", task_id, "")] += 1
            expected[(task_status or "TASK_COMPLETED", task_id, "")] += 1
            expected[(f"STEP_{step_status}", task_id, step_id)] += 1
            expected[("TASK_TIMEOUT", task_id, "")] += attempt - 1
            expected[("TASK_REASSIGNED", task_id, "")] += attempt - 1
    return expected


def completeness(document: dict, events: list[dict]) -> dict:
    expected = expected_events(document)
    present = Counter()
    for event in events:
        key = (event["type"], event.get("task_id") or event.get("mission_id") or "", event.get("step_id", "") or "")
        if event["type"].startswith("MISSION_"):
            key = (event["type"], event.get("mission_id", ""), "")
        elif event["type"].startswith(("TASK_", "WORKFLOW_")):
            key = (event["type"], event.get("task_id", ""), "")
        present[key] += 1
    missing, found = [], 0
    for key, count in sorted(expected.items()):
        have = min(present.get(key, 0), count)
        found += have
        if have < count:
            missing.append({"type": key[0], "task_id": key[1], "step_id": key[2], "expected": count, "present": have})
    total = sum(expected.values())
    return {"expected": total, "present": found, "missing": missing,
            "ratio": (found / total) if total else None, "events_observed": len(events)}


def analyze_sample(document: dict, events: list[dict], settings: dict | None = None) -> dict:
    origin = parse_ms(document.get("created_at"))
    selected = mission_events(document, events)
    rounds = [round_metrics(item, origin) for item in document.get("rounds") or []]
    plan_rounds = [item for item in rounds if item["action"] == "PLAN"]
    steps = [step for item in rounds for step in item["steps"]]
    reassigned_steps = [{"step_id": step["step_id"], "round": item["round"], "attempts": step["attempt"],
                         "final_agent": step["agent_id"]}
                        for item in rounds for step in item["steps"] if step["attempt"] > 1]
    attempts = attempts_from_events(document, selected, origin)
    first_agent = {}
    for row in attempts:
        first_agent.setdefault(row["task_id"], row["agent_id"])
    tasks_by_step = {value["step_id"]: key for key, value in task_index(document).items()}
    for entry in reassigned_steps:
        entry["first_agent"] = first_agent.get(tasks_by_step.get(entry["step_id"]))
    completed_at = parse_ms(document.get("completed_at"))
    status = document.get("status", "").removeprefix("MISSION_STATUS_")
    running = concurrency(attempts, kinds=("map",))
    return {
        "mission_id": document.get("mission_id"), "sample": document.get("sample"), "status": status,
        "completed": status == "COMPLETED",
        "settings": dict(settings or {}),
        "wall_ms": None if completed_at is None else completed_at - origin,
        "client_ms": document.get("client_duration_ms"),
        "rounds": rounds,
        "parallelism_factor": plan_rounds[0]["parallelism_factor"] if plan_rounds else None,
        "map_parallelism_factor": plan_rounds[0]["map_parallelism_factor"] if plan_rounds else None,
        "map_concurrency_peak": running["peak"] if running else None,
        "map_concurrency_mean": running["mean"] if running else None,
        "map_steps_completed": sum(1 for step in steps if step["kind"] == "map" and step["status"] == "COMPLETED"),
        "steps_completed": sum(1 for step in steps if step["status"] == "COMPLETED"),
        "reassignments": {
            "events": sum(1 for event in selected if event["type"] == "TASK_REASSIGNED"),
            "timeouts": sum(1 for event in selected if event["type"] == "TASK_TIMEOUT"),
            "steps_with_attempt_gt_1": len(reassigned_steps),
            "steps": reassigned_steps,
        },
        "recovery": recovery_metrics(document, selected),
        "completeness": completeness(document, selected),
        "attempts": attempts,
        "round_markers": [{"round": event.get("round"), "at_ms": parse_ms(event["timestamp"]) - origin}
                          for event in selected if event["type"] == "MISSION_ROUND_STARTED"],
        "output": document.get("output") or {},
    }


# ---------------------------------------------------------------------------
# Agregação entre repetições e entre valores de K
# ---------------------------------------------------------------------------


def describe(values) -> dict | None:
    values = [float(value) for value in values if value is not None]
    if not values:
        return None
    return {
        "n": len(values), "median": statistics.median(values), "mean": statistics.fmean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "p95": percentile(values, 95), "min": min(values), "max": max(values),
    }


def group_key(settings: dict) -> str:
    flaky = settings.get("flaky")
    return f"K={settings.get('workers')} N={settings.get('shards')} " + ("flaky" if flaky else "no-flaky")


def aggregate(samples: list[dict]) -> dict:
    recovery = [row for sample in samples for row in sample["recovery"]]
    return {
        "samples": len(samples),
        "completed": sum(1 for sample in samples if sample["completed"]),
        "wall_ms": describe(sample["wall_ms"] for sample in samples),
        "client_ms": describe(sample["client_ms"] for sample in samples),
        "parallelism_factor": describe(sample["parallelism_factor"] for sample in samples),
        "map_parallelism_factor": describe(sample["map_parallelism_factor"] for sample in samples),
        "map_concurrency_peak": describe(sample["map_concurrency_peak"] for sample in samples),
        "map_concurrency_mean": describe(sample["map_concurrency_mean"] for sample in samples),
        "round_1_span_ms": describe(sample["rounds"][0]["round_span_ms"] for sample in samples if sample["rounds"]),
        "reassignment_events": sum(sample["reassignments"]["events"] for sample in samples),
        "timeout_events": sum(sample["reassignments"]["timeouts"] for sample in samples),
        "steps_with_attempt_gt_1": sum(sample["reassignments"]["steps_with_attempt_gt_1"] for sample in samples),
        "samples_with_reassignment": sum(1 for sample in samples if sample["reassignments"]["events"]),
        "timeout_detection_ms": describe(row["timeout_detection_ms"] for row in recovery),
        "recovery_ms": describe(row["recovery_ms"] for row in recovery),
        "completion_after_timeout_ms": describe(row["completion_after_timeout_ms"] for row in recovery),
        "completeness": describe(sample["completeness"]["ratio"] for sample in samples),
        "missing_events": sum(len(sample["completeness"]["missing"]) for sample in samples),
    }


def speedup_table(groups: dict) -> list[dict]:
    """Speedup por K em relação ao menor K, para grupos com mesmo N e mesma falha."""
    rows = []
    by_shape = defaultdict(list)
    for label, group in groups.items():
        settings = group["settings"]
        if settings.get("workers") is None or not group["summary"]["wall_ms"]:
            continue
        by_shape[(settings.get("shards"), bool(settings.get("flaky")))].append((int(settings["workers"]), label, group))
    for (shards, flaky), items in sorted(by_shape.items(), key=lambda item: (item[0][0] or 0, item[0][1])):
        if len(items) < 2:
            continue
        items.sort()
        base_k, _, base = items[0]
        base_median = base["summary"]["wall_ms"]["median"]
        base_map = (base["summary"]["round_1_span_ms"] or {}).get("median")
        for workers, label, group in items:
            median = group["summary"]["wall_ms"]["median"]
            round_span = (group["summary"]["round_1_span_ms"] or {}).get("median")
            rows.append({
                "shards": shards, "flaky": flaky, "workers": workers, "label": label,
                "samples": group["summary"]["samples"], "wall_median_ms": median,
                "wall_p95_ms": group["summary"]["wall_ms"]["p95"],
                "speedup": base_median / median if median else None,
                "round_1_span_median_ms": round_span,
                "round_1_speedup": (base_map / round_span) if base_map and round_span else None,
                "ideal": min(workers, shards or workers) / min(base_k, shards or base_k),
                "map_parallelism_median": (group["summary"]["map_parallelism_factor"] or {}).get("median"),
            })
    return rows


def analyze_runs(run_directories) -> dict:
    runs, samples = [], []
    for directory in run_directories:
        run = load_run(directory)
        analysed = [analyze_sample(record, run["events"], run["settings"]) for record in run["records"]]
        for sample in analysed:
            sample["run"] = str(run["directory"])
            sample["group"] = group_key(run["settings"])
        samples.extend(analysed)
        runs.append({"directory": str(run["directory"]), "settings": run["settings"], "samples": len(analysed),
                     "scenario": run["manifest"].get("metadata", {}).get("study"), "execution_id": run["manifest"].get("execution_id")})
    groups = {}
    for sample in samples:
        groups.setdefault(sample["group"], {"settings": sample["settings"], "samples": []})["samples"].append(sample)
    for group in groups.values():
        group["summary"] = aggregate(group["samples"])
    return {
        "runs": runs,
        "groups": {label: {"settings": group["settings"], "summary": group["summary"],
                           "samples": [{key: value for key, value in sample.items() if key not in ("attempts", "rounds")}
                                       for sample in group["samples"]]}
                   for label, group in groups.items()},
        "speedup": speedup_table(groups),
        "samples": samples,
    }


# ---------------------------------------------------------------------------
# Relatório em Markdown
# ---------------------------------------------------------------------------


def _fmt(value, digits=1):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _stats(block, digits=1):
    if not block:
        return "-"
    return (f"mediana {_fmt(block['median'], digits)}, média {_fmt(block['mean'], digits)}, "
            f"desvio {_fmt(block['std'], digits)}, p95 {_fmt(block['p95'], digits)} (n={block['n']})")


def markdown_report(report: dict) -> str:
    lines = ["# Estudo de paralelismo e reatribuição: relatório", ""]
    lines.append("## Execuções analisadas")
    lines.append("")
    lines.append("| Execução | Grupo | Amostras |")
    lines.append("|---|---|---:|")
    for run in report["runs"]:
        lines.append(f"| `{Path(run['directory']).name}` | {group_key(run['settings'])} | {run['samples']} |")
    lines.append("")
    lines.append("## Por grupo (K trabalhadores, N fragmentos, contador lento)")
    lines.append("")
    lines.append("| Grupo | Amostras completas | Tempo de parede (ms) | Fator de paralelismo (mapa) | Fator (rodada 1, todos os passos) | Concorrência de mapa (pico / média) | Reatribuições (eventos / passos) | Completude do rastro |")
    lines.append("|---|---:|---|---|---|---|---:|---:|")
    for label, group in report["groups"].items():
        summary = group["summary"]
        comp = summary["completeness"]
        lines.append(
            f"| {label} | {summary['completed']}/{summary['samples']} | {_stats(summary['wall_ms'])} | "
            f"{_stats(summary['map_parallelism_factor'], 2)} | {_stats(summary['parallelism_factor'], 2)} | "
            f"{_fmt((summary['map_concurrency_peak'] or {}).get('median'), 0)} / {_fmt((summary['map_concurrency_mean'] or {}).get('median'), 2)} | "
            f"{summary['reassignment_events']} / {summary['steps_with_attempt_gt_1']} | "
            f"{_fmt(comp['min'] * 100 if comp else None)}% mín., {_fmt(comp['mean'] * 100 if comp else None)}% média |"
        )
    lines.append("")
    lines.append("## Recuperação após prazo estourado")
    lines.append("")
    lines.append("| Grupo | Passos com timeout | Detecção do prazo (ms) | Recuperação TASK_REASSIGNED - TASK_TIMEOUT (ms) | Conclusão após o timeout (ms) |")
    lines.append("|---|---:|---|---|---|")
    for label, group in report["groups"].items():
        summary = group["summary"]
        lines.append(f"| {label} | {summary['timeout_events']} | {_stats(summary['timeout_detection_ms'])} | "
                     f"{_stats(summary['recovery_ms'], 2)} | {_stats(summary['completion_after_timeout_ms'])} |")
    lines.append("")
    reassigned = [(sample["group"], sample["sample"], entry) for sample in report["samples"]
                  for entry in sample["reassignments"]["steps"]]
    if reassigned:
        lines.append("| Grupo | Amostra | Passo | Primeiro agente | Agente final | Tentativas |")
        lines.append("|---|---:|---|---|---|---:|")
        for group, sample, entry in reassigned:
            lines.append(f"| {group} | {sample} | {entry['step_id']} | {entry.get('first_agent') or '-'} | "
                         f"{entry['final_agent']} | {entry['attempts']} |")
        lines.append("")
    if report["speedup"]:
        lines.append("## Speedup por K")
        lines.append("")
        lines.append("| N | Contador lento | K | Amostras | Parede mediana (ms) | Parede p95 (ms) | Speedup | Rodada 1 mediana (ms) | Speedup da rodada 1 | Ideal | Paralelismo (mapa) mediano |")
        lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in report["speedup"]:
            lines.append(f"| {row['shards']} | {'sim' if row['flaky'] else 'não'} | {row['workers']} | {row['samples']} | "
                         f"{_fmt(row['wall_median_ms'])} | {_fmt(row['wall_p95_ms'])} | {_fmt(row['speedup'], 2)} | "
                         f"{_fmt(row['round_1_span_median_ms'])} | {_fmt(row['round_1_speedup'], 2)} | "
                         f"{_fmt(row['ideal'], 2)} | {_fmt(row['map_parallelism_median'], 2)} |")
        lines.append("")
    lines.append("## Amostras")
    lines.append("")
    lines.append("| Grupo | Amostra | Estado | Parede (ms) | Rodada 1 (ms) | Paralelismo (mapa) | Concorrência pico | Reatribuições | Eventos esperados / presentes | Faltantes |")
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|---|---:|")
    for sample in report["samples"]:
        comp = sample["completeness"]
        first = sample["rounds"][0]["round_span_ms"] if sample["rounds"] else None
        lines.append(f"| {sample['group']} | {sample['sample']} | {sample['status']} | {_fmt(sample['wall_ms'])} | "
                     f"{_fmt(first)} | {_fmt(sample['map_parallelism_factor'], 2)} | {_fmt(sample['map_concurrency_peak'], 0)} | {sample['reassignments']['events']} | "
                     f"{comp['expected']} / {comp['present']} | {len(comp['missing'])} |")
    lines.append("")
    lines.append("Definições: tempo de parede = `completed_at - created_at` do `MissionResult`; "
                 "fator de paralelismo = soma das durações dos passos (`started_at`/`completed_at` do `TaskResult`) "
                 "dividida pelo intervalo entre o primeiro início e o último término; recuperação = "
                 "`TASK_REASSIGNED - TASK_TIMEOUT` no `events.jsonl`; concorrência = tentativas de mapa em execução ao mesmo "
                 "tempo segundo `TASK_ASSIGNED`/`TASK_REASSIGNED` e seus términos (inclui a tentativa que estourou o prazo); "
                 "completude = eventos esperados presentes / esperados.")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Figuras em SVG (biblioteca padrão)
# ---------------------------------------------------------------------------


def _agent_order(agents) -> list[str]:
    def key(agent):
        if agent == "planner":
            return (0, 0, agent)
        match = re.fullmatch(r"counter-(\d+)", agent)
        if match:
            return (1, int(match.group(1)), agent)
        if agent.startswith("counter"):
            return (2, 0, agent)
        if agent.startswith("reducer"):
            return (3, 0, agent)
        return (4, 0, agent)
    return sorted(set(agents), key=key)


def _nice_step(span_ms: float, target_ticks: int = 8) -> float:
    raw = span_ms / max(target_ticks, 1)
    for step in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000):
        if step >= raw:
            return step
    return 50000


def _esc(text) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def gantt_svg(sample: dict, title: str | None = None) -> str:
    attempts = sample["attempts"]
    agents = _agent_order(row["agent_id"] for row in attempts)
    span = max([row["end_ms"] or row["start_ms"] for row in attempts] + [sample["wall_ms"] or 0, 1])
    width, left, right, top, row_h = 960, 120, 24, 64, 30
    plot_w = width - left - right
    height = top + row_h * len(agents) + 92
    scale = plot_w / span
    settings = sample["settings"]
    title = title or (f"Passos por agente: K={settings.get('workers')}, N={settings.get('shards')}, "
                      f"contador lento {'sim' if settings.get('flaky') else 'não'}; amostra {sample['sample']}; "
                      f"parede {_fmt(sample['wall_ms'])} ms; reatribuições {sample['reassignments']['events']}")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="Helvetica, Arial, sans-serif" font-size="12">',
        '<defs><pattern id="hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">'
        f'<rect width="6" height="6" fill="#fbe3e2"/><line x1="0" y1="0" x2="0" y2="6" stroke="{COLORS["timeout"]}" stroke-width="2"/></pattern></defs>',
        f'<rect width="100%" height="100%" fill="{COLORS["surface"]}"/>',
        f'<text x="{left}" y="24" fill="{COLORS["ink"]}" font-size="14">{_esc(title)}</text>',
    ]
    step = _nice_step(span)
    tick = 0.0
    base_y = top + row_h * len(agents)
    while tick <= span + 1e-9:
        x = left + tick * scale
        parts.append(f'<line x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" y2="{base_y}" stroke="{COLORS["grid"]}" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{base_y + 16}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="11">{int(tick)}</text>')
        tick += step
    parts.append(f'<text x="{left + plot_w / 2:.1f}" y="{base_y + 34}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="11">tempo desde MISSION_CREATED (ms)</text>')
    for marker in sample.get("round_markers", []):
        x = left + marker["at_ms"] * scale
        parts.append(f'<line x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" y2="{base_y}" stroke="{COLORS["muted"]}" stroke-width="1" stroke-dasharray="4 3"/>')
        anchor = "end" if x > left + plot_w - 60 else "start"
        parts.append(f'<text x="{x + (-4 if anchor == "end" else 4):.1f}" y="{top - 10}" text-anchor="{anchor}" fill="{COLORS["muted"]}" font-size="11">rodada {marker["round"]}</text>')
    for index, agent in enumerate(agents):
        y = top + index * row_h
        parts.append(f'<text x="{left - 8}" y="{y + row_h / 2 + 4:.1f}" text-anchor="end" fill="{COLORS["ink"]}">{_esc(agent)}</text>')
        if index % 2 == 1:
            parts.append(f'<rect x="{left}" y="{y}" width="{plot_w}" height="{row_h}" fill="#f1f0ec" opacity="0.6"/>')
    for row in attempts:
        y = top + agents.index(row["agent_id"]) * row_h + 6
        x = left + row["start_ms"] * scale
        end = row["end_ms"] if row["end_ms"] is not None else span
        w = max((end - row["start_ms"]) * scale, 2)
        if row["outcome"] == "timeout":
            fill, stroke, label_fill = "url(#hatch)", COLORS["timeout"], COLORS["ink"]
        else:
            fill, stroke, label_fill = COLORS[row["kind"]], (COLORS["reassigned"] if row["reassigned"] else "none"), COLORS["surface"]
        stroke_attr = f' stroke="{stroke}" stroke-width="2.5"' if stroke != "none" else ""
        parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{row_h - 12}" rx="3" fill="{fill}"{stroke_attr}/>')
        label = row["step_id"] + (f" (tentativa {row['attempt']})" if row["attempt"] > 1 else "")
        if row["outcome"] == "timeout":
            label += ", prazo estourado"
        if w >= 6 * len(label) + 8:
            parts.append(f'<text x="{x + 5:.1f}" y="{y + 13}" fill="{label_fill}" font-size="11">{_esc(label)}</text>')
        elif w >= 30:
            parts.append(f'<text x="{x + 4:.1f}" y="{y + 13}" fill="{label_fill}" font-size="10">{_esc(row["step_id"])}</text>')
    legend_y = base_y + 56
    legend = [("map (tentativa 1)", COLORS["map"], None), ("reduce", COLORS["reduce"], None),
              ("planejador", COLORS["planner"], None), ("tentativa reatribuída", COLORS["map"], COLORS["reassigned"]),
              ("prazo estourado", "url(#hatch)", COLORS["timeout"])]
    x = left
    for text, fill, stroke in legend:
        stroke_attr = f' stroke="{stroke}" stroke-width="2"' if stroke else ""
        parts.append(f'<rect x="{x}" y="{legend_y - 10}" width="18" height="12" rx="2" fill="{fill}"{stroke_attr}/>')
        parts.append(f'<text x="{x + 24}" y="{legend_y}" fill="{COLORS["ink"]}" font-size="11">{_esc(text)}</text>')
        x += 24 + 7 * len(text) + 20
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def speedup_svg(rows: list[dict]) -> str:
    width, height = 960, 380
    panel_w, left, top, bottom = 400, 70, 56, 70
    plot_h = height - top - bottom
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="Helvetica, Arial, sans-serif" font-size="12">',
        f'<rect width="100%" height="100%" fill="{COLORS["surface"]}"/>',
    ]
    shapes = sorted({(row["shards"], row["flaky"]) for row in rows}, key=lambda item: (item[0] or 0, item[1]))
    subtitle = "; ".join(f"N={shards}, contador lento {'sim' if flaky else 'não'}" for shards, flaky in shapes)
    parts.append(f'<text x="{left}" y="24" fill="{COLORS["ink"]}" font-size="14">Tempo de parede mediano e speedup por K ({_esc(subtitle)})</text>')
    # Painel 1: tempo de parede mediano por K (uma série: sem legenda, rótulos diretos).
    max_wall = max(row["wall_median_ms"] for row in rows) or 1
    bar_w = min(48, (panel_w - 20) / max(len(rows), 1) - 12)
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="{COLORS["grid"]}"/>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + panel_w}" y2="{top + plot_h}" stroke="{COLORS["muted"]}"/>')
    for index, row in enumerate(rows):
        x = left + 16 + index * (bar_w + 12)
        h = row["wall_median_ms"] / max_wall * plot_h
        y = top + plot_h - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="3" fill="{COLORS["map"]}"/>')
        if row["wall_p95_ms"] is not None:
            py = top + plot_h - row["wall_p95_ms"] / max_wall * plot_h
            parts.append(f'<line x1="{x + bar_w / 2:.1f}" y1="{py:.1f}" x2="{x + bar_w / 2:.1f}" y2="{y:.1f}" stroke="{COLORS["muted"]}" stroke-width="1.5"/>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" fill="{COLORS["ink"]}" font-size="11">{_fmt(row["wall_median_ms"], 0)}</text>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h + 16}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="11">K={row["workers"]}</text>')
    parts.append(f'<text x="{left + panel_w / 2:.1f}" y="{top + plot_h + 36}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="11">tempo de parede mediano (ms); traço = p95</text>')
    # Painel 2: speedup medido e ideal por K (duas séries: legenda presente).
    px = left + panel_w + 90
    max_k = max(row["workers"] for row in rows)
    max_s = max([row["speedup"] or 0 for row in rows] + [row["ideal"] for row in rows] + [1]) * 1.15
    parts.append(f'<line x1="{px}" y1="{top}" x2="{px}" y2="{top + plot_h}" stroke="{COLORS["grid"]}"/>')
    parts.append(f'<line x1="{px}" y1="{top + plot_h}" x2="{px + panel_w}" y2="{top + plot_h}" stroke="{COLORS["muted"]}"/>')

    def point(k, s):
        return px + 20 + (k - 1) / max(max_k - 1, 1) * (panel_w - 40), top + plot_h - s / max_s * plot_h

    for value in range(1, int(max_s) + 1):
        _, y = point(1, value)
        parts.append(f'<line x1="{px}" y1="{y:.1f}" x2="{px + panel_w}" y2="{y:.1f}" stroke="{COLORS["grid"]}"/>')
        parts.append(f'<text x="{px - 6}" y="{y + 4:.1f}" text-anchor="end" fill="{COLORS["muted"]}" font-size="11">{value}x</text>')
    ideal = " ".join(f"{point(row['workers'], row['ideal'])[0]:.1f},{point(row['workers'], row['ideal'])[1]:.1f}" for row in rows)
    measured = " ".join(f"{point(row['workers'], row['speedup'] or 0)[0]:.1f},{point(row['workers'], row['speedup'] or 0)[1]:.1f}" for row in rows)
    parts.append(f'<polyline points="{ideal}" fill="none" stroke="{COLORS["ideal"]}" stroke-width="2" stroke-dasharray="5 4"/>')
    parts.append(f'<polyline points="{measured}" fill="none" stroke="{COLORS["map"]}" stroke-width="2"/>')
    for row in rows:
        x, y = point(row["workers"], row["speedup"] or 0)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{COLORS["map"]}" stroke="{COLORS["surface"]}" stroke-width="2"/>')
        parts.append(f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" fill="{COLORS["ink"]}" font-size="11">{_fmt(row["speedup"], 2)}x</text>')
        parts.append(f'<text x="{x:.1f}" y="{top + plot_h + 16}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="11">K={row["workers"]}</text>')
    parts.append(f'<text x="{px + panel_w / 2:.1f}" y="{top + plot_h + 36}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="11">speedup = parede mediana(K mínimo) / parede mediana(K)</text>')
    ly = top + plot_h + 56
    parts.append(f'<line x1="{px}" y1="{ly - 4}" x2="{px + 24}" y2="{ly - 4}" stroke="{COLORS["map"]}" stroke-width="2"/>')
    parts.append(f'<text x="{px + 30}" y="{ly}" fill="{COLORS["ink"]}" font-size="11">medido</text>')
    parts.append(f'<line x1="{px + 90}" y1="{ly - 4}" x2="{px + 114}" y2="{ly - 4}" stroke="{COLORS["ideal"]}" stroke-width="2" stroke-dasharray="5 4"/>')
    parts.append(f'<text x="{px + 120}" y="{ly}" fill="{COLORS["ink"]}" font-size="11">ideal (min(K, N) / min(K mínimo, N))</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Figuras em PNG (matplotlib opcional)
# ---------------------------------------------------------------------------


def _matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        return None


def gantt_png(sample: dict, path: Path) -> bool:
    plt = _matplotlib()
    if plt is None:
        return False
    attempts = sample["attempts"]
    agents = _agent_order(row["agent_id"] for row in attempts)
    figure, axis = plt.subplots(figsize=(11, 0.45 * len(agents) + 2.2))
    for row in attempts:
        y = agents.index(row["agent_id"])
        end = row["end_ms"] if row["end_ms"] is not None else row["start_ms"]
        if row["outcome"] == "timeout":
            axis.barh(y, end - row["start_ms"], left=row["start_ms"], height=0.6, color="#fbe3e2",
                      edgecolor=COLORS["timeout"], hatch="///", linewidth=1.2)
        else:
            axis.barh(y, end - row["start_ms"], left=row["start_ms"], height=0.6, color=COLORS[row["kind"]],
                      edgecolor=COLORS["reassigned"] if row["reassigned"] else "none", linewidth=2)
        label = row["step_id"] + (f" (t{row['attempt']})" if row["attempt"] > 1 else "")
        axis.text(row["start_ms"] + 8, y, label, va="center", fontsize=8,
                  color=COLORS["ink"] if row["outcome"] == "timeout" else "white")
    for marker in sample.get("round_markers", []):
        axis.axvline(marker["at_ms"], color=COLORS["muted"], linestyle="--", linewidth=1)
    axis.set_yticks(range(len(agents)), agents)
    axis.invert_yaxis()
    axis.set_xlabel("tempo desde MISSION_CREATED (ms)")
    settings = sample["settings"]
    axis.set_title(f"K={settings.get('workers')}, N={settings.get('shards')}, contador lento "
                   f"{'sim' if settings.get('flaky') else 'não'}; amostra {sample['sample']}; "
                   f"parede {_fmt(sample['wall_ms'])} ms; reatribuições {sample['reassignments']['events']}", fontsize=10)
    axis.grid(axis="x", color=COLORS["grid"])
    axis.set_axisbelow(True)
    from matplotlib.patches import Patch
    axis.legend(handles=[Patch(color=COLORS["map"], label="map (tentativa 1)"), Patch(color=COLORS["reduce"], label="reduce"),
                         Patch(color=COLORS["planner"], label="planejador"),
                         Patch(facecolor=COLORS["map"], edgecolor=COLORS["reassigned"], linewidth=2, label="tentativa reatribuída"),
                         Patch(facecolor="#fbe3e2", edgecolor=COLORS["timeout"], hatch="///", label="prazo estourado")],
                loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=5, fontsize=8, frameon=False)
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)
    return True


def speedup_png(rows: list[dict], path: Path) -> bool:
    plt = _matplotlib()
    if plt is None:
        return False
    figure, (left, right) = plt.subplots(1, 2, figsize=(11, 4))
    labels = [f"K={row['workers']}" for row in rows]
    left.bar(labels, [row["wall_median_ms"] for row in rows], color=COLORS["map"], width=0.6)
    for index, row in enumerate(rows):
        left.text(index, row["wall_median_ms"], _fmt(row["wall_median_ms"], 0), ha="center", va="bottom", fontsize=9)
    left.set_ylabel("tempo de parede mediano (ms)")
    left.grid(axis="y", color=COLORS["grid"])
    left.set_axisbelow(True)
    ks = [row["workers"] for row in rows]
    right.plot(ks, [row["ideal"] for row in rows], linestyle="--", color=COLORS["ideal"], label="ideal")
    right.plot(ks, [row["speedup"] for row in rows], marker="o", color=COLORS["map"], label="medido")
    for row in rows:
        right.annotate(f"{_fmt(row['speedup'], 2)}x", (row["workers"], row["speedup"]), textcoords="offset points",
                       xytext=(0, 8), ha="center", fontsize=9)
    right.set_xlabel("K")
    right.set_ylabel("speedup")
    right.set_xticks(ks)
    right.grid(color=COLORS["grid"])
    right.set_axisbelow(True)
    right.legend(frameon=False)
    figure.suptitle("Tempo de parede mediano e speedup por K", fontsize=11)
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)
    return True


# ---------------------------------------------------------------------------
# Linha de comando
# ---------------------------------------------------------------------------


def write_outputs(report: dict, output: Path, *, figures: bool = True, gantt: str = "all") -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    written = []
    saved = {key: value for key, value in report.items() if key != "samples"}
    saved["samples"] = [{key: value for key, value in sample.items() if key != "rounds"} for sample in report["samples"]]
    (output / "report.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(markdown_report(report), encoding="utf-8")
    written += [output / "report.json", output / "report.md"]
    if not figures:
        return written
    seen_runs = set()
    for sample in report["samples"]:
        if gantt == "first" and sample["run"] in seen_runs:
            continue
        seen_runs.add(sample["run"])
        if not sample["attempts"]:
            continue
        settings = sample["settings"]
        name = f"gantt-k{settings.get('workers')}-n{settings.get('shards')}{'-flaky' if settings.get('flaky') else ''}-s{sample['sample']}"
        (output / f"{name}.svg").write_text(gantt_svg(sample), encoding="utf-8")
        written.append(output / f"{name}.svg")
        if gantt_png(sample, output / f"{name}.png"):
            written.append(output / f"{name}.png")
    if report["speedup"]:
        (output / "speedup.svg").write_text(speedup_svg(report["speedup"]), encoding="utf-8")
        written.append(output / "speedup.svg")
        if speedup_png(report["speedup"], output / "speedup.png"):
            written.append(output / "speedup.png")
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analisa execuções do estudo de paralelismo e reatribuição.")
    parser.add_argument("paths", nargs="+", help="diretórios de execução ou de campanha")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-figures", action="store_true")
    parser.add_argument("--gantt", choices=("all", "first"), default="all", help="um Gantt por amostra ou só a primeira de cada execução")
    args = parser.parse_args(argv)
    runs = find_runs(args.paths)
    if not runs:
        parser.error("no run directory with results.jsonl found")
    report = analyze_runs(runs)
    written = write_outputs(report, args.output, figures=not args.no_figures, gantt=args.gantt)
    print(markdown_report(report))
    print("Arquivos: " + ", ".join(str(path) for path in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
