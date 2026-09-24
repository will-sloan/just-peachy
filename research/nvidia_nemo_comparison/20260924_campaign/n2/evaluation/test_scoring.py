"""Leakage, metric and gate regressions; see README.md for execution."""
import copy
import unittest

from scoring import activity_metrics, apply_gate, asr_invariance, calibrate_c, cpwer, turn_coverage


def provenance():
    return {"encoder_sha256":"1"*64,"preprocessing_sha256":"2"*64,"window_manifest_sha256":"3"*64,
            "gallery_sha256":"4"*64,"roster_sha256":"5"*64,"enrollment_domain":"clean_source",
            "input_domain":"clean_source","reference_seconds":15,"vector_dimension":192}


class Tests(unittest.TestCase):
    def test_permutation_and_insertions_keep_denominators(self):
        self.assertEqual(cpwer({"a":["a"],"b":["b"]},{"x":["b"],"y":["a"]})["cpWER"],0)
        result=cpwer({"a":["a"]},{"x":["a"],"unknown":["z"]})
        self.assertEqual(result["errors"],1)
        self.assertIsNone(cpwer({}, {"unknown":["noise"]})["cpWER"])

    def test_asr_invariance_is_order_sensitive(self):
        self.assertFalse(asr_invariance(["a","b"],["b","a"])["raw_word_order_unchanged"])

    def test_overlap_der_counts_speaker_time(self):
        r=[{"start":0,"end":2,"label":"a"},{"start":0,"end":2,"label":"b"}]
        h=[{"start":0,"end":2,"label":"x"}]
        result=activity_metrics(r,h,2,collar_s=0)
        self.assertAlmostEqual(result["reference_speaker_seconds"],4)
        self.assertAlmostEqual(result["approximate_activity_DER"],0.5)
        self.assertAlmostEqual(result["approximate_activity_JER"],0.5)

    def test_no_silent_clamp_or_incomplete_gold(self):
        with self.assertRaises(ValueError):
            activity_metrics([],[{"start":-1,"end":2,"label":"x"}],2)
        self.assertIsNone(activity_metrics([],[],2,complete_reference=False)["approximate_activity_DER"])

    def test_c_gate_provenance_and_leakage(self):
        rows=[{"role":"C","source_id":f"n{i}","identity":f"s{i%5}","is_known":False,"winner_correct":False,"score":0.4,"margin":0.2} for i in range(100)]
        rows += [{"role":"C","source_id":f"p{i}","identity":"target","is_known":True,"winner_correct":True,"score":0.8,"margin":0.2} for i in range(20)]
        gate=calibrate_c(rows,provenance())
        self.assertEqual(gate["status"],"C_EMPIRICAL_CALIBRATION_ONLY")
        self.assertTrue(apply_gate(gate,provenance(),0.8,0.2)["accepted"])
        self.assertFalse(apply_gate(gate,provenance(),0.4,0.2)["accepted"])
        changed=provenance();changed["input_domain"]="XVF_query"
        self.assertFalse(apply_gate(gate,changed,0.8,0.2)["accepted"])
        bad=copy.deepcopy(gate);bad["threshold"]=-1
        with self.assertRaises(ValueError):apply_gate(bad,provenance(),0.8,0.2)
        with self.assertRaises(ValueError):calibrate_c(rows+[rows[0]],provenance())
        rows[0]["role"]="Q"
        with self.assertRaises(ValueError):calibrate_c(rows,provenance())

    def test_insufficient_negatives_fail_closed(self):
        gate=calibrate_c([],provenance())
        self.assertIsNone(gate["threshold"])
        self.assertFalse(apply_gate(gate,provenance(),1,1)["accepted"])

    def test_unresolved_returns_and_duplicate_evidence(self):
        turns=[{"turn_id":"a1","identity":"a","activity_ranges_samples_estimated":[[0,16000]]},
               {"turn_id":"a2","identity":"a","activity_ranges_samples_estimated":[[64000,80000]]}]
        tracks=[{"start":0,"end":1,"label":"x"}]
        windows=[{"start":0,"end":1,"label":"x"},{"start":0,"end":1,"label":"x"}]
        result=turn_coverage(turns,tracks,windows)
        self.assertEqual(result["return_unresolved"],1)
        self.assertEqual(result["short_turns_without_evidence"],1)
        self.assertEqual(result["short_turns_resolved"],1)
        self.assertEqual(result["short_turns_unresolved"],1)
        self.assertEqual(result["embedding_calls"],2)
        self.assertEqual(result["unique_evidence_wall_seconds"],1)


if __name__ == "__main__":
    unittest.main()
