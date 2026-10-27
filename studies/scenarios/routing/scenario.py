"""Missão de rotas: planejador LLM -> rota BDI -> explicação LLM -> DONE.

Execute da raiz com ``./ariadne run studies/scenarios/routing/scenario.py``.
Com ``ROUTING_DEMO=1`` o planejador e o explicador usam o substituto
determinístico, sem credencial.
"""
from ariadne_sdk import Mission, Scenario
from studies.scenarios.routing.agents.planner_explainer.main import planner_explainer
from studies.scenarios.routing.agents.route_planner.main import route_planner
from studies.scenarios.routing.mission import CONTEXT, GOAL, LIMITS

scenario = Scenario(
    agents=[planner_explainer(), route_planner()],
    mission=Mission(goal=GOAL, context=CONTEXT, limits=LIMITS),
)
