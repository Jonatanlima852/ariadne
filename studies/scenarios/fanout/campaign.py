"""Varredura de K para o fan-out, executada por ``./ariadne campaign``.

Da raiz:
    ./ariadne campaign studies/scenarios/fanout/campaign.py
    FANOUT_CAMPAIGN_FLAKY=1 FANOUT_CAMPAIGN_WORKERS="1 2 4" ./ariadne campaign studies/scenarios/fanout/campaign.py

Cada observação é uma execução independente do ``scenario.py`` (topologia
nova) com ``FANOUT_WORKERS`` igual a um valor de ``FANOUT_CAMPAIGN_WORKERS``
(padrão ``1 2 4 8``) e ``FANOUT_FLAKY`` igual a ``FANOUT_CAMPAIGN_FLAKY``
(padrão ``0``: o contador lento fica desligado para que o speedup meça só o
paralelismo). ``FANOUT_CAMPAIGN_REPEAT`` (padrão ``3``) repete cada K. As
demais variáveis do estudo (``FANOUT_SHARDS``, ``FANOUT_WORK_MS``,
``FANOUT_STEP_DEADLINE_MS``) são lidas do terminal como numa execução comum.

Depois, analise a pasta da campanha:
    uv run --project sdk/python python -m studies.scenarios.fanout.analysis \
        studies/scenarios/fanout/campaigns/campaign-<id> --output <pasta>
"""
import os

from ariadne_sdk import Campaign

WORKERS = os.getenv("FANOUT_CAMPAIGN_WORKERS", "1 2 4 8").split()
FLAKY = os.getenv("FANOUT_CAMPAIGN_FLAKY", "0")
REPEAT = int(os.getenv("FANOUT_CAMPAIGN_REPEAT", "3"))

campaign = Campaign(
    "scenario.py",
    matrix={"FANOUT_WORKERS": WORKERS, "FANOUT_FLAKY": [FLAKY]},
    repeat=REPEAT,
    name="fanout-sweep",
    metadata={"study": "fanout", "workers": WORKERS, "flaky": FLAKY == "1"},
)
