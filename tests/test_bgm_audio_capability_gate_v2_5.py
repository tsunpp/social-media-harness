from __future__ import annotations
import unittest
from app.bgm_audio_capability_gate_v2_5 import require_validated_audio_authority


class BgmAudioCapabilityGateTests(unittest.TestCase):
    def test_inconsistent_audio_model_routes_to_human(self):
        result=require_validated_audio_authority({"reviewer":"minimax","complete_duration_audio":False,"semantic_consistency":False,"validated":False})
        self.assertEqual(result["status"],"HUMAN_AUDIO_REVIEW")
        self.assertTrue(result["model_selection_is_provisional"])
    def test_validated_audio_model_can_receive_authority(self):
        result=require_validated_audio_authority({"reviewer":"future-audio-model","complete_duration_audio":True,"semantic_consistency":True,"validated":True})
        self.assertEqual(result["status"],"AUDIO_MODEL_AUTHORITY_VALIDATED")
        self.assertFalse(result["publication_authorized"])


if __name__=="__main__":unittest.main()
