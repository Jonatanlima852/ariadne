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
    # Rótulos editoriais do Mission Viewer; não alteram eventos nem resultados.
    metadata={"presentation": {
        "title": "Rota heterogênea",
        "description": "Um planejador LLM decompõe o objetivo, um agente BDI delibera e escolhe a rota, "
                       "e o mesmo LLM explica a escolha.",
        "agents": {
            "planner-explainer-01": {"label": "Planejador e explicador", "role": "LLM: decompõe o objetivo e explica a rota"},
            "route-planner-01": {"label": "Planejador de rotas", "role": "BDI: delibera entre rotas e escolhe a mais curta"},
        },
        "steps": {"route": {"label": "Escolher rota"}, "explain": {"label": "Explicar rota"}},
    }},
)
