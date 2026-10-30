"""Planejador de rotas: agente BDI deliberativo com crenças por tarefa.

As crenças nascem do payload da tarefa (mapa, origem, destino, limite de
escalas) e morrem com ela. O objetivo é sempre ``plan_route``; dois planos o
atendem, e o ciclo de deliberação escolhe entre eles pelo custo estimado.
"""

from ariadne_sdk import BdiAgent, GoalPlan, SearchProblem, act, observe, uniform_cost_search
from ariadne_sdk.plans import InputError

# Mapa padrão do exemplo: arestas dirigidas origem -> {destino: distância}.
# A ligação direta A->D existe (30), mas A->B->D (10 + 15 = 25) é mais curta:
# é isso que mostra o agente escolhendo o melhor plano, não o primeiro.
DEFAULT_GRAPH = {
    "A": {"B": 10, "C": 25, "D": 30},
    "B": {"C": 8, "D": 15},
    "C": {"D": 6},
}


def perceive(task):
    """Crenças iniciais a partir do payload; campos faltantes invalidam a tarefa."""
    payload = task.payload
    if "origin" not in payload or "destination" not in payload:
        raise InputError("missing payload input: origin and destination")
    return {
        "origin": str(payload["origin"]),
        "destination": str(payload["destination"]),
        "graph": payload.get("graph") or DEFAULT_GRAPH,
        "max_stops": int(payload.get("max_stops", 1)),
    }


def find_route(graph, origin, destination, max_stops):
    """Ação: busca de custo uniforme sobre o mapa, com no máximo max_stops escalas.

    O estado é (nó, trechos percorridos) para que o limite de escalas faça
    parte da busca e não seja checado depois.
    """
    result = uniform_cost_search(SearchProblem(
        initial=(origin, 0),
        actions=lambda state: sorted(graph.get(state[0], {}).items()),
        transition=lambda state, edge: (edge[0], state[1] + 1) if state[1] <= max_stops else None,
        is_goal=lambda state: state[0] == destination,
        cost=lambda state, edge, following: edge[1],
    ))
    if not result.found:
        raise RuntimeError(f"no route from {origin} to {destination} with {max_stops} stop(s)")
    return {"route": [origin, *(edge[0] for edge in result.actions)], "distance": result.cost}


# --- planos: gatilho plan_route, contexto sobre as crenças, custo estimado, corpo ---

def direct_edge(beliefs):
    return beliefs["graph"].get(beliefs["origin"], {}).get(beliefs["destination"])


def first_legs(beliefs):
    """Trechos que saem da origem sem chegar direto ao destino."""
    return {node: distance for node, distance in beliefs["graph"].get(beliefs["origin"], {}).items()
            if node != beliefs["destination"]}


def direct_route(beliefs, goal):
    return {"origin": beliefs["origin"], "destination": beliefs["destination"],
            "route": [beliefs["origin"], beliefs["destination"]], "distance": direct_edge(beliefs)}


def via_intermediate(beliefs, goal):
    # Cada yield é um passo do ciclo: a ação roda e o retorno vira crença.
    found = yield act(find_route, beliefs["graph"], beliefs["origin"], beliefs["destination"],
                      beliefs["max_stops"])
    yield observe(stops=len(found["route"]) - 2)
    return {"origin": beliefs["origin"], "destination": beliefs["destination"],
            "route": found["route"], "distance": found["distance"]}


PLANS = [
    GoalPlan("direct_route", direct_route, goal="plan_route",
             context=lambda beliefs, goal: direct_edge(beliefs) is not None,
             cost=lambda beliefs, goal: direct_edge(beliefs)),
    # Custo estimado de forma otimista (o menor primeiro trecho): a busca só
    # roda depois que o plano vira intenção. Se ela falhar, o ciclo tenta o outro.
    GoalPlan("via_intermediate", via_intermediate, goal="plan_route",
             context=lambda beliefs, goal: beliefs["max_stops"] > 0 and bool(first_legs(beliefs)),
             cost=lambda beliefs, goal: min(first_legs(beliefs).values())),
]


def route_planner(**options):
    configuration = dict(
        agent_id="route-planner-01", name="Route Planner", capabilities=["route-planning"],
        runtime="python-sdk-bdi", beliefs=perceive, goal="plan_route", plans=PLANS,
    )
    return BdiAgent(**(configuration | options))
