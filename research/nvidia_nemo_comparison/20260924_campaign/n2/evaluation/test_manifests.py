"""Read-only fixed-manifest firewall/denominator regressions. See README.md."""
import json
from pathlib import Path
import unittest

PRIVATE = Path("G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation")


@unittest.skipUnless((PRIVATE / "MANIFEST_RECEIPT.json").exists(), "Run prepare.py first")
class ManifestTests(unittest.TestCase):
    def read(self,name):
        return json.loads((PRIVATE / name).read_text(encoding="utf-8"))

    def test_runtime_has_exact_allowlist(self):
        jobs=self.read("AUDIO_ONLY.json")["jobs"]
        self.assertEqual(len(jobs),96)
        fields={"job_id","audio_path","audio_sha256","frames","sample_rate_hz","gain","reset_between_scenes","tap"}
        self.assertTrue(all(set(j)==fields for j in jobs))
        self.assertTrue(all(j["gain"]==1 and j["reset_between_scenes"] for j in jobs))

    def test_ec_disjoint_and_prefix_duration_not_repetition(self):
        manifest=self.read("WINDOW_MANIFEST.json")
        e={w["audio"]["sha256"] for w in manifest["windows"] if w["role"]=="E"}
        c={w["audio"]["sha256"] for w in manifest["windows"] if w["role"]=="C"}
        q={w["audio"]["sha256"] for w in manifest["diagnostic_Q_windows"]}
        self.assertFalse(e&c or e&q or c&q)
        for template in manifest["gallery_templates"]:
            self.assertEqual(len(template["source_ids"]),len(set(template["source_ids"])))
        self.assertEqual(len(self.read("EVALUATOR_TRUTH.json")["cells"]),480)

    def test_no_word_time_oracle_and_noise_control_retained(self):
        cells=self.read("EVALUATOR_TRUTH.json")["cells"]
        self.assertTrue(all(t["word_times"] is None for c in cells for t in c["turns"]))
        self.assertEqual(sum(c["screen48"] and c["case_id"]=="S45_12_20" for c in cells),2)


if __name__ == "__main__":
    unittest.main()
