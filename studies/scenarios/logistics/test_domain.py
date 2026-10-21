import json
import unittest
from pathlib import Path

from studies.scenarios.logistics.domain import evaluate_plan, plan_mission


ROOT = Path(__file__).resolve().parent


class LogisticsDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = json.loads((ROOT / "world.json").read_text())
        cls.cases = json.loads((ROOT / "cases.json").read_text())

    def test_oracle_plans_or_rejects_every_case_safely(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                plan = plan_mission(self.world, case["mission"])
                evaluation = evaluate_plan(self.world, case["mission"], plan)
                self.assertTrue(evaluation["valid"], evaluation)

    def test_unknown_edge_is_rejected(self):
        candidate = {
            "feasible": True,
            "actions": [
                {"type": "PICK_UP_PACKAGE", "location": "A"},
                {"type": "MOVE", "from": "A", "to": "H"},
                {"type": "DELIVER_PACKAGE", "location": "H"},
            ],
        }
        result = evaluate_plan(self.world, self.cases[0]["mission"], candidate)
        self.assertFalse(result["valid"])
        self.assertIn("conexão inexistente", result["failure_reason"])

    def test_deterministic_plan_is_stable(self):
        mission = self.cases[1]["mission"]
        self.assertEqual(
            plan_mission(self.world, mission),
            plan_mission(self.world, mission),
        )

    def test_valid_but_slower_plan_is_not_optimal(self):
        mission = self.cases[0]["mission"]
        candidate = {
            "feasible": True,
            "actions": [
                {"type": "PICK_UP_PACKAGE", "location": "A"},
                {"type": "MOVE", "from": "A", "to": "B"},
                {"type": "MOVE", "from": "B", "to": "D"},
                {"type": "PICK_UP_KEY", "location": "D"},
                {"type": "MOVE", "from": "D", "to": "G"},
                {"type": "MOVE", "from": "G", "to": "H"},
                {"type": "DELIVER_PACKAGE", "location": "H"},
            ],
        }
        result = evaluate_plan(self.world, mission, candidate)
        self.assertTrue(result["valid"])
        self.assertFalse(result["optimal"])
        self.assertEqual(result["optimality_gap_minutes"], 3)


if __name__ == "__main__":
    unittest.main()
