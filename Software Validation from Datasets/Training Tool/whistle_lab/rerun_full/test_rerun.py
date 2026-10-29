"""Checks for exposure, resume boundaries, evaluation identity and selection."""
import copy
import tempfile
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from runtime import COHORTS, validation_steps, next_target, export_paths, BASE
from prepare import reweight, training_clusters
from policy import guards, primary, select
from results import paired


def summary(value=.2):
    return {"complete": True, "panel_sha256": "frozen",
            "cohorts": {c: {"wer": value} for c in COHORTS},
            "quiet_audio": {"wer": value, "reference_words": 1000},
            "negative_probes": {"clips": 20, "false_positive_rate": 0., "inserted_words": 0}}


class FullRerunTests(unittest.TestCase):
    def test_all_rows_and_source_weights(self):
        frame = pd.DataFrame({"dataset_id": ["a","a","a","b"],
                              "source_group_id": ["x","x","y","z"],
                              "view_confidence": [1.,.25,1.,1.]})
        result = reweight(frame, {"a": .6, "b": .4})
        self.assertEqual(len(result), len(frame))
        self.assertAlmostEqual(result[result.dataset_id.eq("a")].sample_weight.sum()/4, .6)
        self.assertAlmostEqual(result.loc[:1, "sample_weight"].sum(), result.loc[2, "sample_weight"])
        self.assertAlmostEqual(result.loc[1, "sample_weight"]/result.loc[0, "sample_weight"], .25)

    def test_full_epoch_coverage_even_partial_batches(self):
        from data import plan_batches
        frame = pd.DataFrame({"audio_capacity": [5]*11+[30]*3, "token_capacity": [32]*14})
        config = {"seed": 26, "max_batch_size": 8, "batch_audio_seconds": 60, "batch_tokens": 1024}
        for epoch in range(3):
            plan = plan_batches(frame, epoch, config)
            self.assertEqual(sorted(np.concatenate([x[0] for x in plan]).tolist()), list(range(14)))

    def test_fixed_resume_boundaries(self):
        slots = validation_steps(11)
        self.assertEqual(slots, [6,11,17,22,28,33])
        self.assertEqual(next_target(9, slots), 11)
        self.assertEqual(next_target(11, slots), 17)
        self.assertIsNone(next_target(33, slots))
        self.assertEqual(export_paths(0)[1], BASE/"whistle.final.cact")

    def test_bad_early_scores_do_not_stop_full_training(self):
        baseline = summary()
        bad = summary(.3)
        choice = select(baseline, [(6,bad), (11,bad), (17,bad)], validation_steps(11))
        self.assertFalse(choice["early_stop"])
        self.assertEqual(choice["selected_step"], 0)
        good = summary(.195)
        choice = select(baseline, [(6,bad), (11,bad), (17,bad), (22,good)], validation_steps(11))
        self.assertEqual(choice["selected_step"], 22)

    def test_macro_guards_and_panel_identity(self):
        baseline, candidate = summary(), summary(.195)
        self.assertLess(primary(candidate), primary(baseline))
        candidate["cohorts"]["librispeech_clean"]["wer"] = .203
        self.assertFalse(guards(baseline, candidate)["passed"])
        candidate = summary(.195)
        candidate["panel_sha256"] = "changed"
        with self.assertRaises(ValueError):
            select(baseline, [(6,candidate)], validation_steps(11))
        candidate = summary(.195)
        del candidate["cohorts"]["voices"]
        self.assertFalse(guards(baseline, candidate)["passed"])

    def test_small_groups_remain_undefined_and_pair_identity_checked(self):
        rows = [{"item_id": c+str(g), "cohort": c, "cluster": str(g),
                 "source_group_id": c+str(g), "word_errors": 20, "reference_words": 100,
                 "panel_sha256": "p", "audio_level": "quiet"}
                for c in COHORTS for g in range(1 if c == "hifitts_clean" else 2)]
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d)/"a.jsonl", Path(d)/"b.jsonl"
            pd.DataFrame(rows).to_json(a, orient="records", lines=True)
            changed = copy.deepcopy(rows)
            for row in changed:
                row["word_errors"] = 19
            pd.DataFrame(changed).to_json(b, orient="records", lines=True)
            result = paired(a,b)
            self.assertIsNone(result["macro_delta_ci95"])
            self.assertIsNone(result["by_cohort"]["hifitts_clean"]["ci95"])
            changed[0]["panel_sha256"] = "wrong"
            pd.DataFrame(changed).to_json(b, orient="records", lines=True)
            with self.assertRaises(ValueError):
                paired(a,b)


if __name__ == "__main__":
    unittest.main()
