"""Um caso da logística v3 como missão declarada, com processos locais.

Da raiz:  LOGISTICS_V3_DEMO=1 ./ariadne run studies/scenarios/logistics/v3/scenario.py
Variáveis: LOGISTICS_V3_CASE (padrão ``easy``), LOGISTICS_V3_CONFIGURATION
(``ariadne-v3`` ou ``single-llm-v3``), LOGISTICS_V3_DEMO (``1`` usa os
substitutos determinísticos; sem ele, OPENAI_API_KEY e LLM_MODEL).
"""
import os

from ariadne_sdk import Scenario
from studies.scenarios.logistics.v3.agents.delivery.main import make_agent as delivery_agent
from studies.scenarios.logistics.v3.agents.execute.main import make_agent as execute_agent
from studies.scenarios.logistics.v3.agents.planner.main import make_agent as planner_agent
from studies.scenarios.logistics.v3.agents.single_llm.main import make_agent as single_llm_agent
from studies.scenarios.logistics.v3.domain.cases import find_case
from studies.scenarios.logistics.v3.mission import DELIVERY_AGENTS, mission_for

CASE = find_case(os.getenv('LOGISTICS_V3_CASE', 'easy'))
CONFIGURATION = os.getenv('LOGISTICS_V3_CONFIGURATION', 'ariadne-v3')
DEMO = os.getenv('LOGISTICS_V3_DEMO', '0') == '1'

if CONFIGURATION == 'single-llm-v3':
    agents = [single_llm_agent(demo=DEMO), execute_agent()]
else:
    agents = [planner_agent(demo=DEMO),
              *(delivery_agent(name=f'delivery-{index}') for index in range(1, DELIVERY_AGENTS + 1)),
              execute_agent()]

scenario = Scenario(
    name=f"logistics-v3-{CASE['id']}-{CONFIGURATION}",
    agents=agents,
    mission=mission_for(CASE, CONFIGURATION),
    metadata={'study': 'logistics-v3', 'case': CASE['id'], 'configuration': CONFIGURATION,
              'execution_kind': 'deterministic-integration-demo' if DEMO else 'real-llm'},
)
