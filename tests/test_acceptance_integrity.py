from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from app.acceptance_integrity import *
from app.engine_api_v2_3 import EngineV23

class AcceptanceIntegrityTests(unittest.TestCase):
    def test_missing_documentary_evidence_is_blocked(self):
        with self.assertRaisesRegex(ValueError,"authentic asset_id"):require_documentary_evidence({"required_evidence":"shot"})
    def test_generation_cannot_fill_missing_fact_beat(self):
        with self.assertRaisesRegex(ValueError,"cannot substitute"):require_documentary_evidence({"asset_id":"A","required_evidence":"shot","generated_to_fill_missing_evidence":True})
    def test_contract_asset_mismatch_is_blocked(self):
        c={"narrative":{"hook":{"asset_id":"A","text":"T","output":"0-1"}}};r={"segments":[{"asset_id":"B","text":"T"}]}
        with self.assertRaisesRegex(ValueError,"asset differs"):validate_contract_render_sync(c,r)
    def test_contract_text_mismatch_is_blocked(self):
        c={"narrative":{"hook":{"asset_id":"A","text":"T","output":"0-1"}}};r={"segments":[{"asset_id":"A","text":"X"}]}
        with self.assertRaisesRegex(ValueError,"text differs"):validate_contract_render_sync(c,r)
    def test_resolution_semantics_are_mandatory(self):
        with self.assertRaisesRegex(ValueError,"semantics"):validate_resolution_semantics({"narrative":{"resolution":{"job":"rest"}},"continuity_contract":{}})
    def test_complete_video_owns_motion_without_pixel_conflict(self):self.assertEqual(adjudicate_modality_conflict({}, {},"motion")["authority"],"MINIMAX")
    def test_claude_owns_typography(self):self.assertEqual(adjudicate_modality_conflict({}, {},"typography")["authority"],"CLAUDE")
    def test_stale_contract_blocks_dual_pass(self):
        with self.assertRaisesRegex(ValueError,"stale"):validate_final_dual_pass({"decision":"PASS","blocking_issues":[]},{"decision":"PASS","blocking_issues":[]},False)
    def test_wrong_version_text_attribution_is_blocked(self):
        with self.assertRaisesRegex(ValueError,"wrong version"):validate_version_attribution({"text_attributions":{"V2":["V3 TEXT"]}},{"V2":{"V2 TEXT"}})
    def test_blind_context_leak_is_blocked(self):
        with self.assertRaisesRegex(ValueError,"leaked"):validate_blind_isolation({"blind_context":{"enabled":True,"prior_creative_history_excluded":True},"prior_caption":"x"})
    def test_engine_declares_acceptance_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'data').mkdir();cap=EngineV23(root).capabilities().data['capabilities']['acceptance_integrity'];self.assertTrue(cap['dual_pass_after_sync'])
if __name__=='__main__':unittest.main()
