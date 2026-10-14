"""Busca de custo uniforme, sem regras de domínio ou dependências externas."""

from dataclasses import dataclass
import heapq
from itertools import count
import math
from numbers import Real
from typing import Callable, Any, Iterable


class SearchLimitExceeded(RuntimeError):
    """O orçamento acabou; não é uma prova de inviabilidade."""


@dataclass(frozen=True)
class SearchProblem:
    """Estados devem ser hashable e callbacks puros.

    transition(state, action) devolve o próximo estado, ou None para rejeitar
    a ação. cost(state, action, next_state) é um custo incremental não negativo.
    A ordem de actions(state) determina o desempate entre caminhos de mesmo custo.
    """

    initial: Any
    actions: Callable[[Any], Iterable]
    transition: Callable[[Any, Any], Any]
    is_goal: Callable[[Any], bool]
    cost: Callable[[Any, Any, Any], Real] = lambda state, action, next_state: 1


@dataclass(frozen=True)
class SearchResult:
    found: bool
    state: Any
    actions: tuple
    cost: Real | None
    expanded: int


def uniform_cost_search(problem: SearchProblem, *, max_expansions: int = 100_000) -> SearchResult:
    """Encontra o objetivo de menor custo; exaustão do grafo retorna found=False.

    Estados iguais representam o mesmo futuro (inclua recursos relevantes no
    estado). Custos zero são permitidos; ciclos que não melhoram são descartados.
    O limite conta estados expandidos, não tempo, memória nem ações geradas.
    """
    if isinstance(max_expansions, bool) or not isinstance(max_expansions, int) or max_expansions < 0:
        raise ValueError("max_expansions must be a non-negative integer")
    serial = count()
    # Cada nó guarda seu predecessor; não copiamos caminhos na fronteira.
    nodes = [(problem.initial, None, None)]
    queue = [(0, next(serial), 0)]
    best = {problem.initial: 0}
    expanded = 0
    while queue:
        total, _, node_index = heapq.heappop(queue)
        state, _, _ = nodes[node_index]
        if total != best[state]:
            continue
        if problem.is_goal(state):
            actions = []
            cursor = node_index
            while nodes[cursor][1] is not None:
                _, parent, action = nodes[cursor]
                actions.append(action)
                cursor = parent
            return SearchResult(True, state, tuple(reversed(actions)), total, expanded)
        if expanded >= max_expansions:
            raise SearchLimitExceeded(f"search exceeded {max_expansions} state expansions")
        expanded += 1
        for action in problem.actions(state):
            next_state = problem.transition(state, action)
            if next_state is None:
                continue
            step_cost = problem.cost(state, action, next_state)
            if (isinstance(step_cost, bool) or not isinstance(step_cost, Real)
                    or not math.isfinite(step_cost) or step_cost < 0):
                raise ValueError("search step cost must be finite and non-negative")
            candidate_cost = total + step_cost
            if not math.isfinite(candidate_cost):
                raise ValueError("search cumulative cost must be finite")
            if candidate_cost >= best.get(next_state, math.inf):
                continue
            best[next_state] = candidate_cost
            nodes.append((next_state, node_index, action))
            heapq.heappush(queue, (candidate_cost, next(serial), len(nodes) - 1))
    return SearchResult(False, problem.initial, (), None, expanded)
