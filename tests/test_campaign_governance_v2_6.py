from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from app.campaign_governance_v2_6 import validate_campaign_governance, validate_direction_binding
from app.publication_authority_v2_6 import resolve_stage5_owner_decision
from app.review_governance_v2_6 import govern_finding, update_loop_state

def contract(intent="PUBLICATION_CANDIDATE"):
    return {"delivery_intent":intent,"messaging":{"mode":"PROCESS_DOCUMENTARY","commercial_solicitation":False,"cta":"NONE","contact_information":False,"sales_language":False},"brand_marks":[{"mark_id":"customer","owner":"customer","internal_display_allowed":True,"public_display_allowed":False,"alteration_allowed":True,"replacement_requested":True,"replacement_asset":{"format":"SVG","transparent_background":True,"sha256":"abc"}}],"logo_replacement_preflight":{"status":"PASS","shots":[{"shot_id":"S1","mark_id":"customer","surface":"curved","camera_motion":True,"occlusion":True,"reflection":True,"uv_light":True,"route":"MASK_AND_TRACK"}]},"direction_contract":{"status":"OWNER_CONFIRMED","unresolved_owner_decisions":[],"contract_sha256":"direction-hash"}}

class CampaignGovernanceTests(unittest.TestCase):
    def test_public_process_documentary_with_logo_preflight_passes(self):
        result=validate_campaign_governance(contract());self.assertEqual(result["replacement_marks"],["customer"]);self.assertFalse(result["publication_authorized"])
    def test_client_preview_does_not_allow_stage5(self):
        result=validate_campaign_governance(contract("CLIENT_PREVIEW"));self.assertNotIn("stage_5",result["allowed_stages"])
    def test_process_documentary_rejects_solicitation(self):
        value=contract();value["messaging"]["commercial_solicitation"]=True
        with self.assertRaisesRegex(ValueError,"commercial_solicitation"):validate_campaign_governance(value)
    def test_public_customer_mark_requires_replacement_or_public_rights(self):
        value=contract();value["brand_marks"][0]["replacement_requested"]=False
        with self.assertRaisesRegex(ValueError,"cannot retain"):validate_campaign_governance(value)
    def test_replacement_requires_shot_preflight(self):
        value=contract();value["logo_replacement_preflight"]={"status":"PENDING","shots":[]}
        with self.assertRaisesRegex(ValueError,"VFX preflight"):validate_campaign_governance(value)
    def test_direction_binding_blocks_stale_artifact(self):
        with self.assertRaisesRegex(ValueError,"stale"):validate_direction_binding(contract()["direction_contract"],{"direction_contract_sha256":"old"})
    def test_stage5_archive_does_not_authorize_publication(self):
        value=resolve_stage5_owner_decision({"actor":"owner","decision":"ARCHIVE_NO_PUBLISH","stage_receipt_sha256":"ABC"},"abc")
        self.assertEqual(value["status"],"ARCHIVED_NOT_PUBLISHED");self.assertFalse(value["publication_authorized"])
    def test_publication_requires_targets(self):
        with self.assertRaisesRegex(ValueError,"target platforms"):resolve_stage5_owner_decision({"actor":"owner","decision":"AUTHORIZE_PUBLICATION","stage_receipt_sha256":"abc"},"abc")
    def test_stage_scope_corrects_fake_temporal_caption_blocker(self):
        finding={"id":"x","domain":"temporal_continuity","severity":"blocking","problem":"caption file and platform package are missing","required_change":"add SRT"}
        result=govern_finding("minimax",finding,"stage_4",{"temporal_continuity"});self.assertFalse(result["binding"]);self.assertEqual(result["target_stage"],"stage_5")
    def test_persistent_loop_guard_stops_third_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"loop.json";finding={"reviewer":"claude","domain":"typography","problem":"small","required_change":"larger"}
            update_loop_state(path,[finding],"same");update_loop_state(path,[finding],"same");state=update_loop_state(path,[finding],"same")
            self.assertEqual(state["status"],"HUMAN_DECISION")

if __name__=="__main__":unittest.main()
