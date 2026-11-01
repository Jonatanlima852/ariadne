"""Campanha do incêndio florestal, executada por ``./ariadne campaign``.

Da raiz, sem credencial (substitutos determinísticos):
    WILDFIRE_DEMO=1 ./ariadne campaign studies/scenarios/wildfire/campaign.py
Campanha real, com ``OPENAI_API_KEY`` (e ``LLM_MODEL`` opcional) exportadas:
    WILDFIRE_CAMPAIGN_SUITE=all WILDFIRE_CAMPAIGN_REPEAT=3 \\
        ./ariadne campaign studies/scenarios/wildfire/campaign.py
Varredura de drones no caso de estresse:
    WILDFIRE_CAMPAIGN_CASES=storm WILDFIRE_CAMPAIGN_DRONES="2 4 8" \\
        ./ariadne campaign studies/scenarios/wildfire/campaign.py

Matriz: os casos da suíte ``WILDFIRE_CAMPAIGN_SUITE`` (``basic``, ``alert``,
``stress`` ou ``all``; padrão ``all``) ou os IDs de ``WILDFIRE_CAMPAIGN_CASES``,
pelas configurações ``WILDFIRE_CAMPAIGN_CONFIGURATIONS`` (padrão
``ariadne single-llm``) e, se dada, pela varredura ``WILDFIRE_CAMPAIGN_DRONES``,
com ``WILDFIRE_CAMPAIGN_REPEAT`` repetições (padrão ``1``). As configurações
se alternam dentro de cada caso e cada observação sobe sua própria topologia.

Depois, analise a pasta da campanha:
    uv run --project sdk/python --extra llm python -m studies.scenarios.wildfire.analysis \\
        studies/scenarios/wildfire/campaigns/campaign-<id>
"""
import os

from ariadne_sdk import Campaign
from studies.scenarios.wildfire.domain.cases import load_cases
from studies.scenarios.wildfire.mission import CONFIGURATIONS

SUITE = os.getenv('WILDFIRE_CAMPAIGN_SUITE', 'all')
CASES = os.getenv('WILDFIRE_CAMPAIGN_CASES', '').split() or None
CONFIGS = os.getenv('WILDFIRE_CAMPAIGN_CONFIGURATIONS', 'ariadne single-llm').split()
DRONES = os.getenv('WILDFIRE_CAMPAIGN_DRONES', '').split()
REPEAT = int(os.getenv('WILDFIRE_CAMPAIGN_REPEAT', '1'))

if not set(CONFIGS) <= set(CONFIGURATIONS):
    raise ValueError(f'unknown configurations {CONFIGS}; use {sorted(CONFIGURATIONS)}')

matrix = {'WILDFIRE_CASE': [case['id'] for case in load_cases(SUITE, CASES)], 'WILDFIRE_CONFIGURATION': CONFIGS}
if DRONES:
    matrix['WILDFIRE_DRONES'] = DRONES

campaign = Campaign(
    'scenario.py',
    matrix=matrix,
    repeat=REPEAT,
    timeout=3600,  # uma missão real tem até 23 chamadas ao modelo; o limite do RPC não altera os prazos do runtime
    name=f'wildfire-{SUITE}' + ('-drones' if DRONES else ''),
    metadata={'study': 'wildfire', 'suite': SUITE, 'configurations': CONFIGS, 'drones': DRONES or None,
              'execution_kind': 'deterministic-integration-demo' if os.getenv('WILDFIRE_DEMO', '0') == '1' else 'real-llm'},
)
