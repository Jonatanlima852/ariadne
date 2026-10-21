"""Planejador e oráculo determinísticos para uma missão logística restrita."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, replace
from itertools import count


@dataclass(frozen=True)
class State:
    location: str
    battery: int
    elapsed: int
    has_package: bool = False
    has_key: bool = False
    door_unlocked: bool = False
    delivered: bool = False
    visited: frozenset[str] = frozenset()


def _edges(world):
    result = {}
    for edge in world["edges"]:
        result[(edge["from"], edge["to"])] = edge
        if edge.get("bidirectional", True):
            result[(edge["to"], edge["from"])] = {
                **edge, "from": edge["to"], "to": edge["from"]
            }
    return result


def _initial(world):
    location = world["start"]
    return State(
        location=location,
        battery=int(world["initial_battery"]),
        elapsed=0,
        visited=frozenset({location}),
    )


def _action(kind, **fields):
    return {"type": kind, **fields}


def _apply(state, action, world, mission):
    """Aplica uma ação ou devolve (None, motivo) se uma precondição falhar."""
    kind = str(action.get("type", "")).upper()
    forbidden = set(mission.get("forbidden_locations", []))
    edges = _edges(world)

    if state.elapsed > int(mission["deadline_minutes"]):
        return None, "deadline excedido antes da ação"

    if kind == "PICK_UP_PACKAGE":
        if state.location != world["package_location"] or state.has_package:
            return None, "pacote indisponível na posição atual"
        return replace(state, has_package=True, elapsed=state.elapsed + 1), None

    if kind == "PICK_UP_KEY":
        if state.location != world["key_location"] or state.has_key:
            return None, "chave indisponível na posição atual"
        return replace(state, has_key=True, elapsed=state.elapsed + 1), None

    if kind == "RECHARGE":
        if state.location not in world["charging_locations"]:
            return None, "não existe carregador na posição atual"
        if state.battery >= int(world["battery_capacity"]):
            return None, "bateria já está cheia"
        return replace(
            state,
            battery=int(world["battery_capacity"]),
            elapsed=state.elapsed + int(world["recharge_minutes"]),
        ), None

    if kind == "UNLOCK_DOOR":
        if state.location != world["door_unlock_location"]:
            return None, "porta não pode ser destrancada desta posição"
        if not state.has_key or state.door_unlocked:
            return None, "chave ausente ou porta já destrancada"
        return replace(state, door_unlocked=True, elapsed=state.elapsed + 1), None

    if kind == "MOVE":
        origin, destination = action.get("from"), action.get("to")
        if origin != state.location:
            return None, "origem da ação difere da posição atual"
        edge = edges.get((origin, destination))
        if edge is None:
            return None, "conexão inexistente"
        if destination in forbidden or origin in forbidden:
            return None, "ação atravessa localização proibida"
        if destination == world["locked_location"] and not state.door_unlocked:
            return None, "entrada exige porta destrancada"
        energy = int(edge["energy"])
        if state.battery < energy:
            return None, "bateria insuficiente"
        return replace(
            state,
            location=destination,
            battery=state.battery - energy,
            elapsed=state.elapsed + int(edge["minutes"]),
            visited=state.visited | {destination},
        ), None

    if kind == "DELIVER_PACKAGE":
        if state.location != mission["destination"] or not state.has_package:
            return None, "destino incorreto ou pacote ausente"
        return replace(state, delivered=True, elapsed=state.elapsed + 1), None

    return None, f"tipo de ação desconhecido: {kind or '<vazio>'}"


def _goal(state, mission):
    return (
        state.delivered
        and state.location == mission["destination"]
        and state.battery >= int(mission.get("minimum_final_battery", 0))
        and state.elapsed <= int(mission["deadline_minutes"])
        and set(mission.get("required_locations", [])).issubset(state.visited)
    )


def _candidate_actions(state, world, mission):
    actions = []
    if state.location == world["package_location"] and not state.has_package:
        actions.append(_action("PICK_UP_PACKAGE", location=state.location))
    if state.location == world["key_location"] and not state.has_key:
        actions.append(_action("PICK_UP_KEY", location=state.location))
    if (
        state.location in world["charging_locations"]
        and state.battery < int(world["battery_capacity"])
    ):
        actions.append(_action("RECHARGE", location=state.location))
    if (
        state.location == world["door_unlock_location"]
        and state.has_key
        and not state.door_unlocked
    ):
        actions.append(_action("UNLOCK_DOOR", location=state.location))
    if (
        state.location == mission["destination"]
        and state.has_package
        and not state.delivered
    ):
        actions.append(_action("DELIVER_PACKAGE", location=state.location))
    for (origin, destination), _ in sorted(_edges(world).items()):
        if origin == state.location:
            actions.append(_action("MOVE", **{"from": origin, "to": destination}))
    return actions


def plan_mission(world, mission):
    """Busca de custo uniforme; mesmos dados sempre produzem o mesmo plano."""
    initial = _initial(world)
    queue = [(0, 0, initial, [])]
    serial = count(1)
    best = {initial: 0}
    deadline = int(mission["deadline_minutes"])

    while queue:
        _, _, state, actions = heapq.heappop(queue)
        if _goal(state, mission):
            return {
                "feasible": True,
                "actions": actions,
                "final_state": _state_dict(state),
                "rejection_reason": "",
            }
        for action in _candidate_actions(state, world, mission):
            next_state, _ = _apply(state, action, world, mission)
            if next_state is None or next_state.elapsed > deadline:
                continue
            if next_state.elapsed >= best.get(next_state, 10**9):
                continue
            best[next_state] = next_state.elapsed
            heapq.heappush(
                queue,
                (next_state.elapsed, next(serial), next_state, actions + [action]),
            )

    return {
        "feasible": False,
        "actions": [],
        "final_state": _state_dict(initial),
        "rejection_reason": "nenhum plano satisfaz todas as restrições",
    }


def _state_dict(state):
    return {
        "location": state.location,
        "battery": state.battery,
        "elapsed_minutes": state.elapsed,
        "has_package": state.has_package,
        "has_key": state.has_key,
        "door_unlocked": state.door_unlocked,
        "delivered": state.delivered,
        "visited": sorted(state.visited),
    }


def evaluate_plan(world, mission, candidate):
    """Oráculo independente: simula a resposta sem corrigi-la."""
    oracle = plan_mission(world, mission)
    claimed_feasible = bool(candidate.get("feasible", False))
    if not claimed_feasible:
        correct_rejection = not oracle["feasible"]
        return {
            "valid": correct_rejection,
            "safe": True,
            "goal_reached": False,
            "correct_rejection": correct_rejection,
            "optimal": correct_rejection,
            "optimality_gap_minutes": 0 if correct_rejection else None,
            "oracle_feasible": oracle["feasible"],
            "failure_reason": "" if correct_rejection else "missão viável foi rejeitada",
            "action_count": 0,
            "final_state": _state_dict(_initial(world)),
        }

    state = _initial(world)
    actions = candidate.get("actions") or []
    for index, action in enumerate(actions):
        state, error = _apply(state, action, world, mission)
        if error:
            return {
                "valid": False,
                "safe": False,
                "goal_reached": False,
                "correct_rejection": False,
                "optimal": False,
                "optimality_gap_minutes": None,
                "oracle_feasible": oracle["feasible"],
                "failure_reason": f"ação {index + 1}: {error}",
                "action_count": len(actions),
                "final_state": None,
            }
    reached = _goal(state, mission)
    oracle_elapsed = (
        oracle["final_state"]["elapsed_minutes"] if oracle["feasible"] else None
    )
    gap = state.elapsed - oracle_elapsed if reached and oracle_elapsed is not None else None
    return {
        "valid": reached,
        "safe": reached,
        "goal_reached": reached,
        "correct_rejection": False,
        "optimal": reached and gap == 0,
        "optimality_gap_minutes": gap,
        "oracle_feasible": oracle["feasible"],
        "failure_reason": "" if reached else "estado final não satisfaz o objetivo",
        "action_count": len(actions),
        "final_state": _state_dict(state),
    }
