import tempfile
import unittest
from pathlib import Path

from app.engine_api_v2_5 import EngineV25


class AdversarialReviewTests(unittest.TestCase):
    def engine(self, directory):
        root = Path(directory)
        (root / "data").mkdir()
        return EngineV25(root)

    def test_capability_optional_not_vote(self):
        with tempfile.TemporaryDirectory() as directory:
            cap = self.engine(directory).capabilities().data["capabilities"]["deepseek_adversarial_review"]
            self.assertTrue(cap["optional"])
            self.assertTrue(cap["not_a_panel_vote"])

    def test_unknown_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            review = {"reviewer":"deepseek_text_critic","decision":"CHALLENGE","evidence_complete":True,"summary":"x","challenges":[{"id":"c1","codex_conclusion":"x","argument":"y","evidence_ids":["missing"],"proposed_action":"z","claimed_modalities":[]}]}
            with self.assertRaises(ValueError):
                self.engine(directory).validate_adversarial_review(review, {"fact-1"})

    def test_audio_claim_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            review = {"reviewer":"deepseek_text_critic","decision":"CHALLENGE","evidence_complete":True,"summary":"x","challenges":[{"id":"c1","codex_conclusion":"x","argument":"y","evidence_ids":["fact-1"],"proposed_action":"z","claimed_modalities":["audio"]}]}
            with self.assertRaises(ValueError):
                self.engine(directory).validate_adversarial_review(review, {"fact-1"})

    def test_every_challenge_must_be_adjudicated(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.engine(directory).adversarial_adjudicate({"challenges":[{"id":"c1"}]}, [])


if __name__ == "__main__":
    unittest.main()
