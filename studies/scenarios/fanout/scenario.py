"""Contagem de palavras em MapReduce como missão: paralelismo e reatribuição.

Da raiz:  ./ariadne run studies/scenarios/fanout/scenario.py --repeat 5
Variáveis: FANOUT_WORKERS (K, padrão 4), FANOUT_SHARDS (N, padrão 8, máximo 9),
FANOUT_FLAKY (1 inclui o contador lento), FANOUT_STEP_DEADLINE_MS (1500),
FANOUT_WORK_MS (300). Sem LLM, sem Docker.
"""
from ariadne_sdk import Scenario
from studies.scenarios.fanout.mission import agents_for, mission_for, settings_from_env

SETTINGS = settings_from_env()

scenario = Scenario(
    name=SETTINGS.label,
    agents=agents_for(SETTINGS),
    mission=mission_for(SETTINGS),
    metadata=SETTINGS.to_dict(),
)
