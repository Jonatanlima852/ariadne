"""Missão de rotas: objetivo, contexto e verificação do resultado.

Compartilhado pela declaração (``scenario.py``) e pelo teste de integração. A
verificação lê o JSON do contrato salvo em ``mission-result.json``.
"""
from studies.scenarios.routing.agents.route_planner.main import DEFAULT_GRAPH

GOAL = "Planeje uma rota de A para D e explique por que ela foi escolhida"
CONTEXT = {"origin": "A", "destination": "D", "graph": DEFAULT_GRAPH}
LIMITS = {"max_rounds": 3}
EXPECTED_ROUTE = ["A", "B", "D"]
EXPECTED_DISTANCE = 25


def agent_kind(result):
    """Mesma regra do cliente de cenário: provedor marca LLM, plano marca BDI."""
    metadata = result.get("metadata", {})
    if metadata.get("provider"):
        return "llm"
    if metadata.get("selected_plan"):
        return "bdi"
    return "generic"


def check_mission(document):
    """Confere o ``MissionResult`` salvo: estado, agentes, rota, rastro BDI e saída."""
    if document.get("status") != "MISSION_STATUS_COMPLETED":
        raise AssertionError(f"mission did not complete: {document.get('error') or document.get('status')}")
    rounds = document["rounds"]
    steps = {step["step_id"]: step for item in rounds for step in item.get("result", {}).get("step_results", [])}
    kinds = {agent_kind(step["result"]) for step in steps.values()}
    kinds |= {agent_kind(item["planner_result"]) for item in rounds if "planner_result" in item}
    if not {"llm", "bdi"} <= kinds:
        raise AssertionError(f"expected LLM and BDI agents, used: {sorted(kinds)}")
    route = steps["route"]["result"]
    if route["output"]["route"] != EXPECTED_ROUTE or route["output"]["distance"] != EXPECTED_DISTANCE:
        raise AssertionError(f"unexpected route: {route['output']}")
    if route["metadata"].get("selected_plan") != "via_intermediate":
        raise AssertionError(f"unexpected plan: {route['metadata'].get('selected_plan')}")
    trace = route["metadata"].get("bdi_trace", {})
    if trace.get("final_status") != "achieved" or trace.get("cycle_count", 0) < 2:
        raise AssertionError(f"deliberation trace missing or too short: {trace}")
    output = document.get("output", {})
    if output.get("route") != EXPECTED_ROUTE or output.get("distance") != EXPECTED_DISTANCE or not output.get("explanation"):
        raise AssertionError(f"unexpected mission output: {output}")
    if rounds[-1]["action"] != "PLANNER_ACTION_DONE":
        raise AssertionError(f"last round is not DONE: {rounds[-1]['action']}")
    return document
