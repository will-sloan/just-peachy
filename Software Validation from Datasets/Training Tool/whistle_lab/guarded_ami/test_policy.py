"""Boundary tests for retention, exposure, early stopping and partial scores."""
import copy
import unittest
from policy import COHORTS, guards, select
from score import records
from pathlib import Path
import tempfile


def summary(value=.30):
    return {"cohorts": {c: {"wer": value} for c in COHORTS},
            "quiet_audio": {"wer": .4, "reference_words": 120},
            "negative_probes": {"clips": 20, "false_positive_rate": 0., "inserted_words": 0}}


class SelectionTests(unittest.TestCase):
    def test_exposure_before_candidate_selection(self):
        ref, candidate = summary(), summary(.28)
        self.assertEqual(select(ref, [(2000, 2000, candidate)])["selected_step"], 0)
        self.assertEqual(select(ref, [(4000, 999, candidate)])["selected_step"], 0)
        result = select(ref, [(4000, 1000, candidate)])
        self.assertEqual(result["selected_step"], 4000)
        self.assertFalse(result["automatic_promotion"])

    def test_clean_regression_blocks_noisy_gain(self):
        ref, candidate = summary(), summary(.28)
        candidate["cohorts"]["librispeech_clean"]["wer"] = .303
        self.assertFalse(guards(ref, candidate)["passed"])
        result = select(ref, [(2000, 1000, candidate), (4000, 2000, candidate)])
        self.assertEqual(result["selected_step"], 0)
        self.assertTrue(result["early_stop"])

    def test_missing_quiet_and_noise_are_not_passes(self):
        for key in ("quiet_audio", "negative_probes"):
            candidate = summary(.28)
            candidate.pop(key)
            self.assertFalse(guards(summary(), candidate)["passed"])

    def test_tie_uses_earlier_checkpoint(self):
        result = select(summary(), [(4000, 1000, summary(.28)), (6000, 2000, summary(.28))])
        self.assertEqual(result["selected_step"], 4000)

    def test_plateau_keeps_initial(self):
        result = select(summary(), [(s, 2000, summary()) for s in (2000, 4000, 6000)])
        self.assertTrue(result["early_stop"])
        self.assertEqual(result["selected_step"], 0)

    def test_partial_final_line_only_is_recoverable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"scores.jsonl"
            path.write_bytes(b'{"item_id":"a"}\n{"interrupted"')
            self.assertEqual(records(path), [{"item_id":"a"}])
            self.assertEqual(path.read_bytes(), b'{"item_id":"a"}\n')
            path.write_bytes(b'{"item_id":"a"}\nBAD\n{"item_id":"b"}\n')
            with self.assertRaises(ValueError):
                records(path)


if __name__ == "__main__":
    unittest.main()
