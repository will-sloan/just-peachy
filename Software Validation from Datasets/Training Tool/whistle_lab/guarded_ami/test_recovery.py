"""Exercise interruption recovery and paired scoring invariants without a model."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import runtime
import supervise
import results
import pandas as pd
from prepare import panel_partitions
from test_policy import summary


class RecoveryTests(unittest.TestCase):
    def test_group_split_repairs_sparse_clean_speaker_coverage(self):
        frame = pd.DataFrame({"cohort": ["clean"]*3+["native"]*4,
                              "cluster": ["librivox:6097", "librivox:9017", "librivox:92",
                                          "librivox:6097", "librivox:11614", "librivox:12787", "librivox:9136"]})
        assignment = panel_partitions(frame)
        for _, part in frame.groupby("cohort"):
            self.assertEqual(set(part.cluster.map(assignment)), {0, 1})
        self.assertEqual(assignment, panel_partitions(frame.sample(frac=1, random_state=3)))

    @unittest.skipIf(os.name == "nt", "The actual supervisor lock is POSIX; run this check in WSL")
    def test_partial_optimizer_checkpoint_resumes_to_next_fixed_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"exports").mkdir()
            (root/"scores").mkdir()
            runtime.atomic_json(root/"checkpoint.json", {"step": 1250, "training_cap_reached": False})
            runtime.atomic_json(root/"initialization_verification.json", {"passed": True})
            runtime.atomic_json(root/"preflight.json", {"complete": True})
            runtime.atomic_json(root/"scores/dev_00000.json", {"complete": True, **summary()})
            calls = []
            class Child:
                pid = 12345
                def __init__(self, command, **kwargs):
                    self.command = command
                    self.script = Path(command[2]).name
                    calls.append(command[2:])
                def wait(self):
                    if self.script == "worker.py":
                        step = int(self.command[-1])
                        runtime.atomic_json(root/"checkpoint.json", {"step": step, "training_cap_reached": False})
                        runtime.atomic_json(root/"exports"/f"step_{step:05d}.json",
                                            {"complete": True, "step": step, "distinct_sources": {"ami": step}})
                    else:
                        step = int(self.command[-1])
                        runtime.atomic_json(root/"scores"/f"dev_{step:05d}.json",
                                            {"complete": True, **summary(.31)})
                    return 0
            with patch.object(runtime, "RUN", root), patch.object(supervise, "RUN", root), \
                 patch.object(supervise, "verify"), patch.object(supervise, "paused", return_value=False), \
                 patch.object(supervise.subprocess, "Popen", Child), patch.object(results, "finish") as finish:
                self.assertEqual(supervise.main(), 0)
                self.assertEqual([int(c[-1]) for c in calls if Path(c[0]).name == "worker.py"], [2000, 4000])
                self.assertEqual([int(c[-1]) for c in calls if Path(c[0]).name == "score.py"], [2000, 4000])
                self.assertEqual(finish.call_args[0][0]["selected_step"], 0)
                self.assertTrue(finish.call_args[0][0]["early_stop"])

    def test_paired_intervals_and_changed_reference_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory)/"a.jsonl", Path(directory)/"b.jsonl"
            def write(path, errors, words=10):
                records = []
                for cohort in runtime.COHORTS:
                    for group in range(3):
                        records.append({"item_id": f"{cohort}_{group}", "source_group_id": f"source_{group}",
                            "cluster": f"group_{group}", "cohort": cohort, "panel_sha256": "fixed",
                            "reference_words": words, "word_errors": errors, "audio_level": "quiet"})
                path.write_text("\n".join(json.dumps(r) for r in records)+"\n", encoding="utf-8")
            write(a, 5); write(b, 3)
            output = results.paired(a, b)
            self.assertLess(output["primary_delta_ci95"][1], 0)
            self.assertLess(output["quiet_delta_ci95"][1], 0)
            write(b, 3, words=11)
            with self.assertRaises(ValueError):
                results.paired(a, b)


if __name__ == "__main__":
    unittest.main()
