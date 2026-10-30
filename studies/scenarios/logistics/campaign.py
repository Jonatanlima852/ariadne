"""Campanha da logística v1, executada por ``./ariadne campaign``.

Da raiz, com ``OPENAI_API_KEY`` exportada:
    ARIADNE_SDK_EXTRAS=llm ./ariadne campaign studies/scenarios/logistics/campaign.py
    LOGISTICS_CAMPAIGN_STRATEGIES="llm-only hybrid" ARIADNE_SDK_EXTRAS=llm ./ariadne campaign studies/scenarios/logistics/campaign.py

Matriz: todos os casos (ou ``LOGISTICS_CAMPAIGN_CASES="simple-delivery impossible-deadline"``)
pela estratégia ``hybrid`` (ou ``LOGISTICS_CAMPAIGN_STRATEGIES``), com
``LOGISTICS_CAMPAIGN_REPEAT`` repetições (padrão ``2``). As estratégias se
alternam dentro de cada caso. Cada observação sobe sua própria topologia.

Depois, avalie a pasta da campanha:
    python3 -m studies.scenarios.logistics.analysis studies/scenarios/logistics/campaigns/campaign-<id>
"""
import os

from ariadne_sdk import Campaign
from studies.scenarios.logistics.datasets.loader import load_cases

ALL_CASES = [case["id"] for case in load_cases()]
CASES = os.getenv("LOGISTICS_CAMPAIGN_CASES", " ".join(ALL_CASES)).split()
STRATEGIES = os.getenv("LOGISTICS_CAMPAIGN_STRATEGIES", "hybrid").split()
REPEAT = int(os.getenv("LOGISTICS_CAMPAIGN_REPEAT", "2"))

unknown = sorted(set(CASES) - set(ALL_CASES))
if unknown or not set(STRATEGIES) <= {"llm-only", "hybrid"}:
    raise ValueError(f"unknown cases {unknown} or strategies {STRATEGIES}; use llm-only and hybrid")

campaign = Campaign(
    "scenario.py",
    matrix={"LOGISTICS_CASE": CASES, "LOGISTICS_STRATEGY": STRATEGIES},
    repeat=REPEAT,
    name="logistics",
    metadata={"study": "logistics"},
)
