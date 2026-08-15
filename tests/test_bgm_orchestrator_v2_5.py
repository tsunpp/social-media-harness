from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from app.bgm_orchestrator_v2_5 import adjudicate_bgm_reviews, finalize_dual_master, prepare_bgm_contract, review_contract, sha256, validate_candidate_manifest, validate_sound_strategy
from app.engine_api_v2_5_bgm import EngineV25BGM

def strategy():
    return {"mode":"original_bgm","story_job":"support narrative progression","beat_map":[{"id":"hook","start":0,"end":3,"music_job":"quiet question"},{"id":"reveal","start":3,"end":8,"music_job":"textural lift"}],"vocals_allowed":False,"preserve_silent_master":True,"candidate_count":3}
def directions():
    return [{"id":"A","prompt":"original instrumental A","story_rationale":"precise"},{"id":"B","prompt":"original instrumental B","story_rationale":"documentary"},{"id":"C","prompt":"original instrumental C","story_rationale":"minimal"}]
def model_review(selected=None,findings=None):
    value={"evidence_complete":True,"findings":findings or []}
    if selected is not None:value["selected"]=selected
    return value

class BgmOrchestratorV25Tests(unittest.TestCase):
    def test_strategy_requires_three_candidates(self):
        value=strategy();value["candidate_count"]=2
        with self.assertRaisesRegex(ValueError,"exactly three"):validate_sound_strategy(value)
    def test_prepare_writes_reusable_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);silent=root/"silent.mp4";story=root/"story.json";silent.write_bytes(b"video");story.write_text("{}",encoding="utf-8")
            result=prepare_bgm_contract(root,"new-campaign",silent,story,strategy(),directions())
            self.assertEqual(result["campaign"],"new-campaign");self.assertTrue((root/"campaigns/new-campaign/production/bgm-v2-5/bgm-stage-contract.json").is_file())
    def test_review_contract_preserves_authority(self):
        result=review_contract(["A","B","C"]);self.assertIn("heard_music_quality",result["minimax"]["authority"]);self.assertIn("heard_audio_quality",result["kimi"]["must_not_claim"])
    def test_manifest_requires_complete_provenance(self):
        contract={"directions":directions(),"silent_master_sha256":"S"};candidates=[]
        for item in directions():candidates.append({"id":item["id"],"provider":"p","model":"m","prompt":item["prompt"],"task_id":"t","audio":"a","audio_sha256":"h","mix":"x","mix_sha256":"h","technical_qc":"PASS"})
        validate_candidate_manifest(contract,{"source_silent_master_sha256":"S","candidates":candidates});del candidates[0]["task_id"]
        with self.assertRaisesRegex(ValueError,"incomplete"):validate_candidate_manifest(contract,{"source_silent_master_sha256":"S","candidates":candidates})
    def test_minimax_selects_when_other_authorities_clear(self):
        result=adjudicate_bgm_reviews(["A","B","C"],model_review(),model_review("B"),model_review());self.assertEqual(result["selected"],"B")
    def test_kimi_provenance_blocker_is_binding(self):
        result=adjudicate_bgm_reviews(["A","B","C"],model_review(),model_review("A"),model_review(findings=[{"domain":"provenance","severity":"blocking"}]));self.assertEqual(result["status"],"CODEX_ADJUDICATION")
    def test_dual_master_never_overwrites_silent(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);silent=root/"silent.mp4";mix=root/"mix.mp4";silent.write_bytes(b"silent");mix.write_bytes(b"mix")
            with self.assertRaisesRegex(ValueError,"never overwrite"):finalize_dual_master(silent,mix,silent,sha256(silent),sha256(mix))
    def test_dual_master_preserves_source_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);silent=root/"silent.mp4";mix=root/"mix.mp4";dest=root/"out/bgm.mp4";silent.write_bytes(b"silent");mix.write_bytes(b"mix");before=sha256(silent)
            result=finalize_dual_master(silent,mix,dest,before,sha256(mix));self.assertTrue(result["silent_master_preserved"]);self.assertEqual(sha256(silent),before)
    def test_engine_declares_bgm_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/"data").mkdir();cap=EngineV25BGM(root).capabilities().data["capabilities"]["bgm_stage"];self.assertTrue(cap["silent_master_immutable"]);self.assertEqual(cap["candidate_count"],3)
if __name__=="__main__":unittest.main()
