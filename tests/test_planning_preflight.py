from __future__ import annotations

import unittest

from app.planning_preflight import find_plan_fact_conflicts


class PlanningFactPreflightTests(unittest.TestCase):
    def test_superseded_phrase_is_blocked(self):
        plan = {"options": [{"concept": "蓝色容器中的样品"}]}
        rules = [{
            "decision_id": "sample-container",
            "forbidden_phrases": ["蓝色容器"],
            "required_fact": "样品位于透明容器中",
            "preferred_terms": ["透明容器"],
        }]
        conflicts = find_plan_fact_conflicts(plan, rules)
        self.assertEqual(conflicts[0]["occurrences"], 1)
        self.assertEqual(conflicts[0]["decision_id"], "sample-container")

    def test_current_wording_passes(self):
        plan = {"options": [{"concept": "透明容器中的样品"}]}
        rules = [{"decision_id": "sample-container", "forbidden_phrases": ["蓝色容器"]}]
        self.assertEqual(find_plan_fact_conflicts(plan, rules), [])


if __name__ == "__main__":
    unittest.main()

