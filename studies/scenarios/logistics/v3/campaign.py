"""Campanha da logística v3, executada por ``./ariadne campaign``.

Da raiz, sem credencial (substitutos determinísticos):
    LOGISTICS_V3_DEMO=1 ./ariadne campaign studies/scenarios/logistics/v3/campaign.py
Campanha real, com ``OPENAI_API_KEY`` (e ``LLM_MODEL`` opcional) exportadas:
    LOGISTICS_V3_CAMPAIGN_SUITE=stress LOGISTICS_V3_CAMPAIGN_REPEAT=3 \\
        ./ariadne campaign studies/scenarios/logistics/v3/campaign.py

Matriz: os casos da suíte ``LOGISTICS_V3_CAMPAIGN_SUITE`` (``basic``, ``stress``
ou ``all``; padrão ``basic``) ou os IDs de ``LOGISTICS_V3_CAMPAIGN_CASES``, pelas
configurações ``LOGISTICS_V3_CAMPAIGN_CONFIGURATIONS`` (padrão
``ariadne-v3 single-llm-v3``), com ``LOGISTICS_V3_CAMPAIGN_REPEAT`` repetições
(padrão ``1``). As configurações se alternam dentro de cada caso e cada
observação sobe sua própria topologia em contêineres.

Depois, analise a pasta da campanha:
    python -m studies.scenarios.logistics.v3.analysis \\
        studies/scenarios/logistics/v3/campaigns/campaign-<id> --no-plots
"""
import os

from ariadne_sdk import Campaign
from studies.scenarios.logistics.v3.domain.cases import load_cases
from studies.scenarios.logistics.v3.mission import CONFIGURATIONS

SUITE = os.getenv("LOGISTICS_V3_CAMPAIGN_SUITE", "basic")
CASES = os.getenv("LOGISTICS_V3_CAMPAIGN_CASES", "").split() or None
CONFIGS = os.getenv("LOGISTICS_V3_CAMPAIGN_CONFIGURATIONS", "ariadne-v3 single-llm-v3").split()
REPEAT = int(os.getenv("LOGISTICS_V3_CAMPAIGN_REPEAT", "1"))

if not set(CONFIGS) <= set(CONFIGURATIONS):
    raise ValueError(f"unknown configurations {CONFIGS}; use {sorted(CONFIGURATIONS)}")

campaign = Campaign(
    "scenario.py",
    matrix={"LOGISTICS_V3_CASE": [case["id"] for case in load_cases(SUITE, CASES)],
            "LOGISTICS_V3_CONFIGURATION": CONFIGS},
    repeat=REPEAT,
    timeout=3600,  # uma missão real pode passar de um minuto; o limite do RPC não altera os prazos do runtime
    name=f"logistics-v3-{SUITE}",
    metadata={"study": "logistics-v3", "suite": SUITE, "configurations": CONFIGS,
              "execution_kind": "deterministic-integration-demo" if os.getenv("LOGISTICS_V3_DEMO", "0") == "1" else "real-llm"},
)
