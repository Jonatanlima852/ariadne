"""Shared graph queries and proposal identity; decisions live in each agent."""
from ariadne_sdk import SearchProblem, uniform_cost_search
from studies.scenarios.logistics.v2.domain.graph import _edges
from studies.scenarios.logistics.v2.domain.world import edge


def path(s, start, target):
    result = uniform_cost_search(SearchProblem(
        initial=start,
        actions=lambda node: [b for a, b in sorted(_edges(s)) if a == node and edge(s, a, b)],
        transition=lambda node, dest: dest,
        is_goal=lambda node: node == target,
        cost=lambda node, dest, _: edge(s, node, dest)['minutes'],
    ), max_expansions=10000)
    return (list(result.actions), result.cost) if result.found else (None, None)


def allocation_key(choice):
    return '|'.join((choice['order'], choice.get('depot', choice.get('source_vehicle', '')), choice['vehicle']))


def energy_to_charger(s, start):
    """Minimum movement energy to any open charger; a graph query, not a policy."""
    result = uniform_cost_search(SearchProblem(
        initial=start,
        actions=lambda node: [b for a, b in sorted(_edges(s)) if a == node and edge(s, a, b)],
        transition=lambda node, dest: dest,
        is_goal=lambda node: node in s['charging_locations'],
        cost=lambda node, dest, _: edge(s, node, dest)['energy'],
    ), max_expansions=10000)
    return result.cost if result.found else float('inf')
