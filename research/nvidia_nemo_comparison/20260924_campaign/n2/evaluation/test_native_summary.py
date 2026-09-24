"""Raw endpoint, capacity and source-support checks without model/audio calls."""
from copy import deepcopy
import unittest

import numpy as np

from summarize_native_profiles import activity_aggregate,normalize_jobs,score_native_probability


def truth():
    return {"frames":16000,"complete_reference":True,"turns":[{"turn_id":"private-turn","identity":"private-reference","activity_ranges_samples_estimated":[[0,16000]]}]}


def availability():
    return [{"frame_start":0,"frame_end":40,"audio_received_sec":.4,"received_at_elapsed_sec":0.,"available_at_elapsed_sec":.2,"compute_sec":.2,"is_final":False},
            {"frame_start":40,"frame_end":101,"audio_received_sec":1.,"received_at_elapsed_sec":.2,"available_at_elapsed_sec":.4,"compute_sec":.2,"is_final":True}]


class NativeSummaryTests(unittest.TestCase):
    def test_scheduler_prefix_alias_requires_exact_same_audio_job(self):
        job={"job_id":"N2_S45_01_04_O0","audio_sha256":"1"*64,"gain":1,"frames":16000,"sample_rate_hz":16000,"audio_path":"same.wav","tap":"O0","reset_between_scenes":True}
        native=dict(job,job_id="N1_BASELINE_S45_01_04_O0")
        self.assertEqual(normalize_jobs({native["job_id"]:native},{job["job_id"]:job}),{native["job_id"]:job["job_id"]})
        native["gain"]=2
        with self.assertRaises(ValueError):normalize_jobs({native["job_id"]:native},{job["job_id"]:job})

    def test_raw_endpoint_preserved_and_supported_activity_scored(self):
        values=np.zeros((101,8),dtype=np.float32);values[:,0]=1
        original=values.copy()
        result=score_native_probability(values,.01,availability(),truth())
        np.testing.assert_array_equal(values,original)
        self.assertEqual(result["frame_support"]["raw_native_frames"],101)
        self.assertAlmostEqual(result["frame_support"]["native_waveform_overhang_seconds"],.01)
        self.assertAlmostEqual(result["activity"]["approximate_activity_DER"],0)
        self.assertEqual(result["coverage"]["short_turns_resolved"],1)
        self.assertAlmostEqual(result["coverage"]["source_turn_activity_with_native_activity_seconds_sum"],1)
        self.assertNotIn("short_turns_without_evidence",result["coverage"])

    def test_saturation_is_descriptive_and_tied_turn_stays_unresolved(self):
        result=score_native_probability(np.ones((101,8),dtype=np.float32),.01,availability(),truth())
        self.assertEqual(result["capacity"]["maximum_simultaneously_active_slots"],8)
        self.assertAlmostEqual(result["capacity"]["seconds_all_eight_slots_active"],1)
        self.assertAlmostEqual(result["activity"]["approximate_activity_DER"],7)
        self.assertEqual(result["coverage"]["short_turns_unresolved"],1)
        self.assertEqual(result["coverage"]["short_turns_without_native_activity"],0)

    def test_invalid_availability_and_probabilities_rejected(self):
        values=np.zeros((101,8),dtype=np.float32)
        events=availability();events[1]["frame_start"]=41
        with self.assertRaises(ValueError):score_native_probability(values,.01,events,truth())
        events=availability();events[0]["audio_received_sec"]=1.2
        with self.assertRaises(ValueError):score_native_probability(values,.01,events,truth())
        values[0,0]=np.nan
        with self.assertRaises(ValueError):score_native_probability(values,.01,availability(),truth())

    def test_incomplete_reference_never_reports_full_der(self):
        reference=deepcopy(truth());reference["complete_reference"]=False
        result=score_native_probability(np.zeros((101,8),dtype=np.float32),.01,availability(),reference)
        self.assertIsNone(result["activity"]["approximate_activity_DER"])
        self.assertEqual(result["coverage"]["source_turns_without_native_activity"],1)

    def test_empty_control_false_activity_remains_in_pooled_der(self):
        values=np.zeros((101,8),dtype=np.float32);values[:,0]=1
        positive=score_native_probability(values,.01,availability(),truth())
        empty=truth();empty["turns"]=[]
        control=score_native_probability(values,.01,availability(),empty)
        self.assertIsNone(control["activity"]["approximate_activity_DER"])
        pooled=activity_aggregate([positive,control],"activity")
        self.assertAlmostEqual(pooled["reference_speaker_seconds"],1)
        self.assertAlmostEqual(pooled["false_alarm_seconds"],1)
        self.assertAlmostEqual(pooled["micro_approximate_activity_DER"],1)


if __name__=="__main__":unittest.main()
