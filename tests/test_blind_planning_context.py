from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.planning_orchestrator import prepare_planning_context


class BlindPlanningContextTests(unittest.TestCase):
    def test_blind_context_uses_campaign_snapshots_and_omits_head_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for path, text in {
                "projects/p/project.yaml": "historical project",
                "projects/p/PROJECT_DECISIONS.md": "SM000 old edit",
                "campaigns/c/brief.yaml": "blind brief",
                "campaigns/c/blind-project.yaml": "blind project",
                "campaigns/c/blind-facts.md": "facts only",
            }.items():
                target = root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text, encoding="utf-8")
            manifest = {"assets": [], "blind_context": {"enabled": True, "project_config_override": "blind-project.yaml", "project_decisions_override": "blind-facts.md", "allowed_active_decisions": []}}
            target = root / "campaigns/c/source/manifest.json"; target.parent.mkdir(parents=True); target.write_text(json.dumps(manifest), encoding="utf-8")
            head = root / "memory/HEAD.json"; head.parent.mkdir(); head.write_text(json.dumps({"active_decisions": []}), encoding="utf-8")
            context = prepare_planning_context(root, "p", "c")
            self.assertTrue(context["blind_context"]["enabled"])
            self.assertFalse(context["blind_context"]["historical_head_content_loaded"])
            self.assertEqual(context["project_config"]["raw"], "blind project")
            self.assertEqual(context["project_decisions"], "facts only")
            self.assertNotIn("recovery_head", {x["role"] for x in context["evidence"]["files"]})


if __name__ == "__main__": unittest.main()
