"""Agentes do estudo: contadores de fragmento, um contador lento, o redutor e
o planejador determinístico.

Todos usam ``Agent`` com um ``handler``: a deliberação não é o ponto aqui. O
que importa é que K contadores idênticos oferecem a mesma capacidade
(``fanout-count``), que um deles demora mais que o prazo do passo, e que o
planejador pede N passos de mapa sem dependências entre si (o engine os
executa em paralelo) seguidos de um ``reduce`` que depende de todos.
"""
from __future__ import annotations

import time

from ariadne_sdk import Agent, PlannerRequest, PlannerResponse, plan_step
from studies.scenarios.fanout.domain import count_words, merge_counts, top_words

COUNT_CAPABILITY = "fanout-count"
REDUCE_CAPABILITY = "fanout-reduce"
PLANNER_CAPABILITY = "mission-planning"
FLAKY_AGENT_ID = "counter-flaky"
REDUCE_STEP_ID = "reduce"
# O validador do orquestrador aceita no máximo 10 passos por workflow; um
# deles é o reduce, logo o planejador nunca pede mais de 9 passos de mapa.
MAX_STEPS = 10
MAX_SHARDS = MAX_STEPS - 1


def map_step_id(shard: int) -> str:
    return f"map-{shard}"


# ---------------------------------------------------------------------------
# Contadores (capacidade fanout-count)
# ---------------------------------------------------------------------------


def _count_handler(agent_id: str, delay_ms: int):
    def count(task):
        payload = task.payload
        if "shard" not in payload or "text" not in payload:
            raise ValueError("count step requires payload.shard and payload.text")
        # Trabalho simulado: cada fragmento "custa" work_ms, para que a
        # sobreposição dos passos seja mensurável. O contador lento soma o
        # atraso que o leva além do prazo do passo.
        work_ms = int(payload.get("work_ms", 0) or 0)
        time.sleep((work_ms + delay_ms) / 1000)
        counts = count_words(payload["text"])
        return {
            "shard": int(payload["shard"]),
            "counts": counts,
            "words": sum(counts.values()),
            "counted_by": agent_id,
            "work_ms": work_ms,
            "delay_ms": delay_ms,
        }
    return count


def shard_counter(name: str, **options) -> Agent:
    """Contador saudável: responde após ``work_ms`` do payload."""
    return Agent(name=name, capabilities=[COUNT_CAPABILITY], handler=_count_handler(name, 0), **options)


def flaky_counter(delay_ms: int, name: str = FLAKY_AGENT_ID, **options) -> Agent:
    """Contador lento: responde certo, mas ``delay_ms`` depois do que deveria.

    Com ``delay_ms`` maior que o prazo do passo, o orquestrador registra
    ``TASK_TIMEOUT`` e reatribui o passo a outro contador (``TASK_REASSIGNED``).
    """
    if delay_ms <= 0:
        raise ValueError("flaky delay_ms must be positive")
    return Agent(name=name, capabilities=[COUNT_CAPABILITY], handler=_count_handler(name, delay_ms), **options)


# ---------------------------------------------------------------------------
# Redutor (capacidade fanout-reduce)
# ---------------------------------------------------------------------------


def reduce_shards(task):
    """Mescla as contagens entregues por ``input_bindings`` em ``payload.shards``."""
    shards = task.payload.get("shards")
    if not isinstance(shards, dict) or not shards:
        raise ValueError("reduce step requires payload.shards bound from the map steps")
    expected = [int(item) for item in task.payload.get("expected_shards", [])]
    outputs = [shards[key] for key in sorted(shards, key=lambda key: int(shards[key].get("shard", 0)))]
    received = sorted(int(item.get("shard", 0)) for item in outputs)
    if expected and received != sorted(expected):
        raise ValueError(f"reduce received shards {received}, expected {sorted(expected)}")
    merged = merge_counts([item.get("counts", {}) for item in outputs])
    limit = int(task.payload.get("top_n", 5) or 5)
    return {
        "total_words": sum(merged.values()),
        "distinct_words": len(merged),
        "top_words": top_words(merged, limit),
        "shards_merged": received,
        "counted_by": {str(int(item["shard"])): item.get("counted_by", "") for item in outputs},
    }


def reducer(name: str = "reducer", **options) -> Agent:
    return Agent(name=name, capabilities=[REDUCE_CAPABILITY], handler=reduce_shards, **options)


# ---------------------------------------------------------------------------
# Planejador determinístico (capacidade mission-planning)
# ---------------------------------------------------------------------------


def plan_round_one(request: PlannerRequest) -> PlannerResponse:
    """N passos de mapa em paralelo e um reduce dependente de todos."""
    context = request.context
    shards = list(context.get("shards") or [])
    if not shards:
        return PlannerResponse.abort("mission context has no shards to count")
    dropped = shards[MAX_SHARDS:]
    shards = shards[:MAX_SHARDS]
    work_ms = int(context.get("work_ms", 0) or 0)
    steps, map_ids = [], []
    for item in shards:
        step_id = map_step_id(int(item["shard"]))
        map_ids.append(step_id)
        steps.append(plan_step(
            step_id, COUNT_CAPABILITY, f"Contar as palavras do fragmento {item['shard']}",
            payload={"shard": int(item["shard"]), "text": item["text"], "work_ms": work_ms},
            type="MAP_COUNT",
        ))
    bindings = [{"source_step_id": sid, "source_path": "output", "target_field": f"shards.{sid}"}
                for sid in map_ids]
    steps.append(plan_step(
        REDUCE_STEP_ID, REDUCE_CAPABILITY, "Consolidar as contagens de todos os fragmentos",
        payload={"top_n": int(context.get("top_n", 5) or 5),
                 "expected_shards": [int(item["shard"]) for item in shards]},
        depends_on=map_ids, input_bindings=bindings, type="REDUCE_COUNT",
    ))
    summary = f"{len(map_ids)} map steps in parallel, then reduce"
    if dropped:
        summary += f"; {len(dropped)} shards dropped (workflow limit of {MAX_STEPS} steps)"
    return PlannerResponse.make_plan(
        steps, final_step_id=REDUCE_STEP_ID, workflow_id="fanout-word-count", summary=summary,
        context_update={"planned_shards": len(map_ids), "dropped_shards": len(dropped)},
    )


def plan_round_two(request: PlannerRequest) -> PlannerResponse:
    """DONE com a saída do reduce; ABORT se algum passo não completou."""
    last = request.last_round or {}
    results = {item.get("step_id"): item for item in last.get("step_results", [])}
    failed = sorted(sid for sid, item in results.items()
                    if item.get("status") != "WORKFLOW_STEP_STATUS_COMPLETED")
    if failed or REDUCE_STEP_ID not in results:
        return PlannerResponse.abort("steps did not complete: " + ", ".join(failed or ["reduce missing"]))
    reduce_output = dict(results[REDUCE_STEP_ID].get("result", {}).get("output", {}))
    map_steps = sorted(sid for sid in results if sid != REDUCE_STEP_ID)
    reassigned = sorted(sid for sid in map_steps
                        if int(results[sid].get("task", {}).get("attempt", 1) or 1) > 1)
    output = {
        **reduce_output,
        "map_steps": len(map_steps),
        "reassigned_steps": reassigned,
        "summary": (f"{reduce_output.get('total_words', 0)} words in {len(map_steps)} shards; "
                    f"{len(reassigned)} step(s) reassigned"),
    }
    return PlannerResponse.done(output, summary="word count consolidated")


def plan(task):
    request = PlannerRequest.from_payload(task.payload)
    response = plan_round_one(request) if not request.history else plan_round_two(request)
    return response.to_output()


def planner(name: str = "planner", **options) -> Agent:
    return Agent(name=name, capabilities=[PLANNER_CAPABILITY], handler=plan, **options)
