import unittest
from tg_sdk import SearchProblem, SearchLimitExceeded, uniform_cost_search


class PlanningTests(unittest.TestCase):
    def problem(self, edges, goal="goal"):
        return SearchProblem(
            initial="start", actions=lambda state: edges.get(state, []),
            transition=lambda state, action: action[0],
            is_goal=lambda state: state == goal,
            cost=lambda state, action, next_state: action[1],
        )

    def test_weighted_graph_reopens_cheaper_path_and_ignores_cycles(self):
        problem = self.problem({"start": [("goal", 20), ("a", 8), ("b", 1)],
                                "b": [("a", 1), ("b", 0)], "a": [("goal", 1), ("start", 0)]})
        result = uniform_cost_search(problem)
        self.assertTrue(result.found)
        self.assertEqual(result.cost, 3)
        self.assertEqual(result.actions, (("b", 1), ("a", 1), ("goal", 1)))

    def test_exhaustion_and_budget_exhaustion_are_distinct(self):
        problem = self.problem({"start": [("start", 0)]})
        result = uniform_cost_search(problem)
        self.assertFalse(result.found)
        self.assertIsNone(result.cost)
        with self.assertRaises(SearchLimitExceeded):
            uniform_cost_search(problem, max_expansions=0)
        self.assertTrue(uniform_cost_search(self.problem({}, goal="start"), max_expansions=0).found)

    def test_ties_preserve_action_order_and_unorderable_states_work(self):
        start, first, second, goal = (frozenset([i]) for i in range(4))
        edges = {start: [first, second], first: [goal], second: [goal]}
        problem = SearchProblem(start, lambda state: edges.get(state, []), lambda state, action: action,
                                lambda state: state == goal)
        self.assertEqual(uniform_cost_search(problem).actions, (first, goal))

    def test_invalid_transition_is_skipped_and_invalid_cost_rejected(self):
        problem = SearchProblem(0, lambda state: ["blocked"], lambda state, action: None, lambda state: False)
        self.assertFalse(uniform_cost_search(problem).found)
        for cost in (-1, float("nan"), float("inf"), True, "1"):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                uniform_cost_search(self.problem({"start": [("goal", cost)]}))

    def test_stale_nodes_do_not_consume_expansion_budget(self):
        problem = self.problem({"start": [("a", 10), ("b", 1)], "b": [("a", 1)]})
        result = uniform_cost_search(problem, max_expansions=3)
        self.assertFalse(result.found)
        self.assertEqual(result.expanded, 3)


if __name__ == "__main__":
    unittest.main()
