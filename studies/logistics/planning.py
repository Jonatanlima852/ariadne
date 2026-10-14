"""Adaptador logístico para o planejador genérico do SDK.

O oráculo offline em domain.plan_mission mantém sua implementação de referência.
"""
from ariadne_sdk import SearchProblem, uniform_cost_search
from .domain import _initial, _candidate_actions, _apply, _goal, _state_dict


def plan_mission(world, mission):
    def transition(state, action):
        next_state, _ = _apply(state, action, world, mission)
        if next_state is not None and next_state.elapsed <= int(mission["deadline_minutes"]):
            return next_state
        return None

    result = uniform_cost_search(SearchProblem(
        initial=_initial(world),
        actions=lambda state: _candidate_actions(state, world, mission),
        transition=transition,
        is_goal=lambda state: _goal(state, mission),
        cost=lambda state, action, next_state: next_state.elapsed - state.elapsed,
    ))
    return {
        "feasible": result.found,
        "actions": list(result.actions),
        "final_state": _state_dict(result.state),
        "rejection_reason": "" if result.found else "nenhum plano satisfaz todas as restrições",
    }
