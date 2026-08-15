from __future__ import annotations

import unittest

from app.planning_preflight import find_plan_fact_conflicts


class PlanningFactPreflightTests(unittest.TestCase):
    def test_superseded_phrase_is_blocked(self):
        plan = {"options": [{"concept": "黄色托盘中的晶体"}]}
        rules = [{
            "decision_id": "mother-liquor",
            "forbidden_phrases": ["黄色托盘"],
            "required_fact": "黄色部分是母液",
            "preferred_terms": ["黄色母液"],
        }]
        conflicts = find_plan_fact_conflicts(plan, rules)
        self.assertEqual(conflicts[0]["occurrences"], 1)
        self.assertEqual(conflicts[0]["decision_id"], "mother-liquor")

    def test_current_wording_passes(self):
        plan = {"options": [{"concept": "母液中的DIAMOND"}]}
        rules = [{"decision_id": "mother-liquor", "forbidden_phrases": ["黄色托盘"]}]
        self.assertEqual(find_plan_fact_conflicts(plan, rules), [])


if __name__ == "__main__":
    unittest.main()

