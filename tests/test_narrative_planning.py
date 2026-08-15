from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from app.narrative_planning import validate_narrative_option, validate_narrative_review
from app.planning_orchestrator_v2_1 import validate_narrative_plan
from app.engine_api_v2_1 import EngineV21
from app.narrative_planning import validate_narrative_review

def option(option_id="A"):
    beats=[]; coverage=[]
    for name in ("hook","development","turn","reveal","resolution"):
        beats.append({"function":name,"story_job":f"advance {name}","required_evidence":f"evidence {name}","text_job":f"change understanding at {name}"})
        coverage.append({"function":name,"asset_ids":["AST-1"]})
    return {"id":option_id,"name":"story","target_duration_seconds":21,"concept":"change and reveal","opening_hook":{},"timeline":[{},{},{},{},{}],"strength":"narrative","risk":"low","narrative_contract":{"audience_question":"what is beneath the surface?","middle_change":"the material changes state","visual_climax":"clear crystal emerges","ending_insight":"environment and form differ","text_progression":"each line changes understanding","source_feasibility":"all beats have authentic footage","beats":beats},"narrative_evidence_coverage":coverage}

class NarrativePlanningTests(unittest.TestCase):
    def test_valid_story_contract_passes(self): validate_narrative_option(option())
    def test_pretty_sequence_without_story_is_blocked(self):
        value=option(); del value["narrative_contract"]
        with self.assertRaisesRegex(ValueError,"narrative_contract"): validate_narrative_option(value)
    def test_missing_source_evidence_is_blocked(self):
        value=option(); value["narrative_evidence_coverage"][-1]["asset_ids"]=[]
        with self.assertRaisesRegex(ValueError,"lacks source evidence"): validate_narrative_option(value)
    def test_label_only_text_is_blocked(self):
        value=option(); value["narrative_contract"]["beats"][0]["text_job"]="label image"
        with self.assertRaisesRegex(ValueError,"advance the story"): validate_narrative_option(value)
    def test_pass_without_evidence_is_contradictory(self):
        review={"decision":"PASS","narrative_assessment":{"hook_question":"q","causal_or_discovery_progression":"p","visual_climax":"c","resolution":"r","text_advances_story":True,"all_beats_evidence_supported":False,"missing_beats":["turn"],"unsupported_claims":[]}}
        with self.assertRaisesRegex(ValueError,"contradicts"): validate_narrative_review(review)
    def test_three_v2_options_are_required(self): validate_narrative_plan({"schema_version":2,"campaign":"c","options":[option(x) for x in "ABC"]},"c")
    def test_engine_declares_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"data").mkdir(); gate=EngineV21(root).capabilities().data["capabilities"]["narrative_plan"]
            self.assertTrue(gate["required_for_new_campaigns"]); self.assertFalse(gate["production_before_gate"])

if __name__=="__main__": unittest.main()
