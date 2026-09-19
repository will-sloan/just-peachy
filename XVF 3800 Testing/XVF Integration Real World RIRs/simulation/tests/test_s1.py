"""Focused S1 invariants; the independent known-FIR synthetic gate is separate."""
import json
import os
import sys
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from s1_signal import gcc_delay, sinc_sample

class SignalTests(unittest.TestCase):
    def test_gcc_sign(self):
        a=np.zeros(256);b=a.copy();a[80]=1;b[83]=1
        self.assertAlmostEqual(gcc_delay(a,b),3,places=3)
        self.assertAlmostEqual(gcc_delay(b,a),-3,places=3)

    def test_sinc_dc_preservation(self):
        x=np.ones(1000)*.125
        np.testing.assert_allclose(sinc_sample(x,np.arange(100,900)+.37),.125,atol=1e-12)

class SavedRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=Path(os.environ["S1_REPORT"])
        cls.read=lambda _,p:json.loads(p.read_text(encoding="utf-8"))
        cls.active=json.loads((cls.r/"active_campaign_manifest.json").read_text())
        cls.selected=json.loads((cls.r/"selected_pilot_manifest.json").read_text())["recordings"]
        cls.metrics=[json.loads((cls.r/"records"/r["run_id"]/"metrics.json").read_text()) for r in cls.selected]

    def test_exact_scope_and_distance(self):
        self.assertEqual(len(self.active["recordings"]),121)
        self.assertEqual(len(self.active["scope_excluded_recordings"]),6)
        self.assertEqual(len(self.active["original_audit_exclusions"]),52)
        self.assertTrue(all(r["room_table"]=="Loeb Caf" for r in self.active["scope_excluded_recordings"]))
        self.assertNotIn("Loeb Caf",{r["room_table"] for r in self.active["recordings"]})
        self.assertIn("Upper Loeb",{r["room_table"] for r in self.active["recordings"]})
        self.assertTrue(all(0<r["source_distance_m_effective"]<=5 for r in self.active["recordings"]))
        self.assertTrue(all(r["original_status"] in ("PASS","REVIEW") for r in self.active["recordings"]))
        self.assertEqual(self.active["metadata_geometry_groups"],51)

    def test_revised_pilot(self):
        self.assertEqual(len({r["run_id"] for r in self.selected}),12)
        self.assertEqual([r["pilot_order"] for r in self.selected],list(range(1,13)))
        self.assertEqual([r["room_table"] for r in self.selected[-2:]],["Upper Loeb"]*2)
        self.assertEqual([r["speaker_angle_deg_effective"] for r in self.selected[-2:]],[30,-90])
        self.assertEqual([r["source_distance_m_effective"] for r in self.selected[-2:]],[.9,1.37])

    def test_gates_and_no_individual_warp(self):
        self.assertEqual(sum(m["status"]=="PROVISIONAL_LIMITED_BAND_TAIL" for m in self.metrics),4)
        self.assertEqual(sum(m["status"]=="PROVISIONAL_TIMING_REVIEW" for m in self.metrics),8)
        for m in self.metrics:
            self.assertFalse(m["simulation_ready"])
            self.assertFalse(m["qualified_rir_available"])
            self.assertFalse(m["timing"]["microphone_vector_resampled"])
            self.assertTrue(m["regeneration"]["byte_identical"])
            self.assertEqual(len(m["response_metrics"]["pairwise_delays"]),6)
            self.assertTrue(m["noise"]["window_verified_before_excitation"])
            self.assertFalse(m["noise"]["post_sweep_used_as_noise_only"])
            self.assertIsNone(m["response_metrics"]["decay_estimate_rt60_sec"])

    def test_candidate_headers_and_gain_receipts(self):
        import hashlib
        for m in self.metrics:
            o=next(o for o in m["outputs"] if o["role"]=="candidate_4ch")
            a,fs=sf.read(o["path"],dtype="float32",always_2d=True)
            self.assertEqual((fs,a.shape[1],sf.info(o["path"]).subtype),(16000,4,"FLOAT"))
            self.assertTrue(np.isfinite(a).all())
            self.assertEqual(hashlib.sha256(a.astype("<f4").tobytes()).hexdigest(),m["regeneration"]["candidate_float32_sha256"])
            self.assertTrue(all(p["candidate_delay_change_samples"]==0 for p in m["response_metrics"]["pairwise_delays"]))

if __name__=="__main__":unittest.main(verbosity=2)
