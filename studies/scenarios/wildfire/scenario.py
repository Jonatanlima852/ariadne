"""Um caso do incêndio florestal como missão declarada; cada agente num contêiner.

Da raiz:  WILDFIRE_DEMO=1 ./ariadne run studies/scenarios/wildfire/scenario.py
Variáveis: WILDFIRE_CASE (padrão ``three-fronts``), WILDFIRE_CONFIGURATION
(``ariadne`` ou ``single-llm``), WILDFIRE_DEMO (``1`` usa os substitutos
determinísticos; sem ele, OPENAI_API_KEY e LLM_MODEL), WILDFIRE_DRONES,
WILDFIRE_DRONE_AGENTS e WILDFIRE_COMMAND_EVERY (ver ``mission.py``).
"""
from ariadne_sdk import Scenario
from studies.scenarios.wildfire.mission import agents_for, mission_for, presentation, settings_from_env

SETTINGS = settings_from_env()

scenario = Scenario(
    name=SETTINGS.label,
    agents=agents_for(SETTINGS),
    mission=mission_for(SETTINGS.case, SETTINGS.configuration),
    metadata={**SETTINGS.to_dict(), 'presentation': presentation(SETTINGS)},
)
