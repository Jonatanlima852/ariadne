"""Configuração do estudo: variáveis de ambiente, agentes e missão declarada.

Compartilhado pela declaração (``scenario.py``), pela campanha
(``campaign.py``) e pelos testes.

| Variável | Padrão | Significado |
|---|---|---|
| ``FANOUT_WORKERS`` | 4 | K contadores saudáveis (``counter-1..K``); vira ``max_parallel`` |
| ``FANOUT_SHARDS`` | 8 | N fragmentos (máximo 9: o workflow aceita 10 passos, um é o reduce) |
| ``FANOUT_FLAKY`` | 1 | 1 inclui o contador lento ``counter-flaky`` |
| ``FANOUT_STEP_DEADLINE_MS`` | 1500 | prazo de cada passo (``EXECUTION_TIMEOUT`` do orquestrador) |
| ``FANOUT_FLAKY_FACTOR`` | 3 | o contador lento atrasa ``factor × prazo`` |
| ``FANOUT_WORK_MS`` | 300 | trabalho simulado por fragmento |
| ``FANOUT_WORDS_PER_SHARD`` | 200 | tamanho de cada fragmento |
| ``FANOUT_ROUND_DEADLINE_MS`` | 60000 | prazo da rodada (timeout total do workflow) |
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os

from ariadne_sdk import Mission, MissionLimits
from studies.scenarios.fanout.agents import (
    COUNT_CAPABILITY, FLAKY_AGENT_ID, MAX_SHARDS, PLANNER_CAPABILITY, REDUCE_CAPABILITY, REDUCE_STEP_ID,
    flaky_counter, map_step_id, planner, reducer, shard_counter,
)
from studies.scenarios.fanout.domain import count_words, make_shards

GOAL = "Contar as palavras de um texto dividido em fragmentos e consolidar o total"
RETRY_POLICY = {"max_attempts": 2, "exclude_failed_agent": True}
# Com FIRST_AVAILABLE todos os passos iriam ao primeiro contador e o lento
# nunca receberia um passo; o rodízio distribui e inclui o lento.
SELECTION_POLICY = "round_robin"
TOP_N = 5


@dataclass(frozen=True)
class Settings:
    workers: int = 4
    shards: int = 8
    flaky: bool = True
    step_deadline_ms: int = 1500
    flaky_factor: int = 3
    work_ms: int = 300
    words_per_shard: int = 200
    round_deadline_ms: int = 60000
    planner_deadline_ms: int = 10000

    def __post_init__(self):
        for name in ("workers", "shards", "step_deadline_ms", "flaky_factor", "work_ms",
                     "words_per_shard", "round_deadline_ms", "planner_deadline_ms"):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.shards > MAX_SHARDS:
            raise ValueError(f"FANOUT_SHARDS must be at most {MAX_SHARDS}: the workflow validator "
                             f"accepts {MAX_SHARDS + 1} steps and one of them is the reduce")

    @property
    def flaky_delay_ms(self) -> int:
        return self.step_deadline_ms * self.flaky_factor

    @property
    def label(self) -> str:
        return f"fanout-k{self.workers}-n{self.shards}" + ("-flaky" if self.flaky else "")

    def to_dict(self) -> dict:
        return {**asdict(self), "flaky_delay_ms": self.flaky_delay_ms, "study": "fanout",
                "flaky_agent_id": FLAKY_AGENT_ID if self.flaky else None}


def settings_from_env(environ=None) -> Settings:
    env = os.environ if environ is None else environ

    def number(name, default):
        return int(env.get(name, default) or default)

    return Settings(
        workers=number("FANOUT_WORKERS", 4),
        shards=number("FANOUT_SHARDS", 8),
        flaky=env.get("FANOUT_FLAKY", "1") == "1",
        step_deadline_ms=number("FANOUT_STEP_DEADLINE_MS", 1500),
        flaky_factor=number("FANOUT_FLAKY_FACTOR", 3),
        work_ms=number("FANOUT_WORK_MS", 300),
        words_per_shard=number("FANOUT_WORDS_PER_SHARD", 200),
        round_deadline_ms=number("FANOUT_ROUND_DEADLINE_MS", 60000),
        planner_deadline_ms=number("FANOUT_PLANNER_DEADLINE_MS", 10000),
    )


def configure_runtime(settings: Settings, environ=None) -> str:
    """Prazo de passo como ``EXECUTION_TIMEOUT`` do orquestrador.

    O plano do planejador não transporta ``deadline_ms`` por passo (o
    decodificador Go aceita só ``step_id``, ``type``, ``goal``, ``payload``,
    ``required_capabilities``, ``depends_on``, ``input_bindings`` e
    ``bdi_goal``); um passo sem prazo usa o prazo padrão do orquestrador, que
    vem da variável ``EXECUTION_TIMEOUT``. ``./ariadne run`` inicia o
    orquestrador com o ambiente do processo que carregou esta declaração, por
    isso basta definir a variável aqui, antes de os serviços subirem.
    """
    env = os.environ if environ is None else environ
    value = f"{settings.step_deadline_ms}ms"
    env["EXECUTION_TIMEOUT"] = value
    return value


def agents_for(settings: Settings) -> list:
    agents = [planner()]
    agents.extend(shard_counter(f"counter-{index}") for index in range(1, settings.workers + 1))
    if settings.flaky:
        agents.append(flaky_counter(settings.flaky_delay_ms))
    agents.append(reducer())
    return agents


def mission_context(settings: Settings) -> dict:
    return {
        "shards": make_shards(settings.shards, settings.words_per_shard),
        "shard_count": settings.shards,
        "work_ms": settings.work_ms,
        "top_n": TOP_N,
    }


def mission_for(settings: Settings) -> Mission:
    return Mission(
        goal=GOAL,
        context=mission_context(settings),
        limits=MissionLimits(max_rounds=3, max_parallel=settings.workers,
                             round_deadline_ms=settings.round_deadline_ms,
                             planner_deadline_ms=settings.planner_deadline_ms),
        planner_capability=PLANNER_CAPABILITY,
        retry_policy=RETRY_POLICY,
        selection_policy=SELECTION_POLICY,
        metadata=settings.to_dict(),
    )


def expected_total_words(settings: Settings) -> int:
    return sum(sum(count_words(item["text"]).values()) for item in make_shards(settings.shards, settings.words_per_shard))


def check_mission(document: dict, settings: Settings) -> dict:
    """Confere o ``mission-result.json``: estado, passos, contagem e reatribuição."""
    if document.get("status") != "MISSION_STATUS_COMPLETED":
        raise AssertionError(f"mission did not complete: {document.get('error') or document.get('status')}")
    rounds = document.get("rounds") or []
    if len(rounds) != 2 or rounds[0]["action"] != "PLANNER_ACTION_PLAN" or rounds[1]["action"] != "PLANNER_ACTION_DONE":
        raise AssertionError(f"expected PLAN then DONE, got {[item.get('action') for item in rounds]}")
    steps = {step["step_id"]: step for step in rounds[0].get("result", {}).get("step_results", [])}
    expected_ids = {map_step_id(index) for index in range(1, settings.shards + 1)} | {REDUCE_STEP_ID}
    if set(steps) != expected_ids:
        raise AssertionError(f"unexpected steps: {sorted(steps)}")
    for step in steps.values():
        if step.get("status") != "WORKFLOW_STEP_STATUS_COMPLETED":
            raise AssertionError(f"step {step['step_id']} did not complete: {step.get('status')}")
    output = document.get("output") or {}
    if output.get("total_words") != expected_total_words(settings):
        raise AssertionError(f"unexpected total: {output.get('total_words')}")
    if output.get("shards_merged") != list(range(1, settings.shards + 1)):
        raise AssertionError(f"unexpected shards merged: {output.get('shards_merged')}")
    agents = {step["result"]["agent_id"] for sid, step in steps.items() if sid != REDUCE_STEP_ID}
    if agents - {f"counter-{index}" for index in range(1, settings.workers + 1)} - {FLAKY_AGENT_ID}:
        raise AssertionError(f"unexpected map agents: {sorted(agents)}")
    if settings.flaky:
        reassigned = [sid for sid, step in steps.items()
                      if int(step.get("task", {}).get("attempt", 1) or 1) > 1]
        if not reassigned:
            raise AssertionError("flaky counter enabled but no step was reassigned")
        for sid in reassigned:
            if steps[sid]["result"]["agent_id"] == FLAKY_AGENT_ID:
                raise AssertionError(f"reassigned step {sid} still completed by the flaky counter")
    return document


CAPABILITIES = {"count": COUNT_CAPABILITY, "reduce": REDUCE_CAPABILITY, "planner": PLANNER_CAPABILITY}
