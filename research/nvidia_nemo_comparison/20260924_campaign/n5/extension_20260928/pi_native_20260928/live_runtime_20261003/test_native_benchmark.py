"""Host benchmark contracts with synthetic WAV/fake model. See README_NATIVE_BENCHMARK.md."""
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from native_benchmark import (SegmentedOutput, digest, inspect_wav, make_plan,
                              pcm_blocks, run_stream)
from profiles import RuntimeSelection, SessionPolicy
import native_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_linux_virtual_swap_and_pss_sampling_cadence(self):
        reads = []
        values = {"/proc/self/statm": "100 12", "/proc/meminfo": "MemAvailable: 4096 kB\n",
                  "/proc/self/status": "VmSize: 60000 kB\nVmPeak: 70000 kB\nVmSwap: 32 kB\n",
                  "/proc/self/smaps_rollup": "Pss: 1234 kB\n"}
        def read(path, *args, **kwargs):
            name = str(path).replace("\\", "/")
            reads.append(name)
            return values[name]
        fake_resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=lambda who: SimpleNamespace(ru_maxrss=64))
        with patch.object(native_benchmark.platform, "system", return_value="Linux"), \
             patch.dict("sys.modules", {"resource": fake_resource}), \
             patch.object(native_benchmark.os, "sysconf", return_value=4096, create=True), \
             patch.object(Path, "read_text", read), patch.object(Path, "glob", return_value=[]), \
             patch.object(native_benchmark.time, "perf_counter", side_effect=[10., 10.4, 11.1]), \
             patch.dict(native_benchmark._PSS_CACHE, dict(pid=None, sampled_at=-float("inf"), pss_bytes=None)), \
             patch.dict(native_benchmark._TASK_CACHE, dict(pid=None, sampled_at=-float("inf"))):
            first, cached, refreshed = [native_benchmark.resource_sample() for _ in range(3)]
        self.assertEqual(first["virtual_bytes"], 60000*1024)
        self.assertEqual(first["peak_virtual_bytes"], 70000*1024)
        self.assertEqual(first["swap_bytes"], 32*1024)
        self.assertEqual(first["pss_bytes"], 1234*1024)
        self.assertAlmostEqual(cached["pss_sample_age_seconds"], .4)
        self.assertEqual(refreshed["pss_sample_age_seconds"], 0.)
        self.assertEqual(reads.count("/proc/self/smaps_rollup"), 2)

    def test_task_affinity_sampling_bounded_cached_and_not_graph_thread_claim(self):
        scans = []
        def entries(path, pattern):
            if str(path).replace("\\", "/") == "/proc/self/task":
                scans.append(pattern)
                return (Path(str(tid)) for tid in range(100, 200))
            return []
        fake_resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=lambda who: SimpleNamespace(ru_maxrss=64))
        with patch.object(native_benchmark.platform, "system", return_value="Linux"), \
             patch.dict("sys.modules", {"resource": fake_resource}), \
             patch.object(Path, "read_text", side_effect=OSError("procfs unavailable")), \
             patch.object(Path, "glob", entries), \
             patch.object(native_benchmark.os, "sched_getaffinity", return_value={2, 3}, create=True) as affinity, \
             patch.object(native_benchmark.time, "perf_counter", side_effect=[10., 10.4, 11.1]), \
             patch.dict(native_benchmark._PSS_CACHE, dict(pid=None, sampled_at=-float("inf"), pss_bytes=None)), \
             patch.dict(native_benchmark._TASK_CACHE, dict(pid=None, sampled_at=-float("inf"))):
            first, cached, refreshed = [native_benchmark.resource_sample() for _ in range(3)]
        self.assertEqual(first["task_count"], 65)
        self.assertTrue(first["task_sample_truncated"])
        self.assertEqual(len(first["task_affinities"]), 64)
        self.assertEqual(first["task_affinities"][0], {"tid": 100, "cpus": [2, 3]})
        self.assertEqual(first["native_graph_threads"], "unverified")
        self.assertAlmostEqual(cached["task_sample_age_seconds"], .4)
        self.assertEqual(refreshed["task_sample_age_seconds"], 0.)
        self.assertEqual(len(scans), 2)
        self.assertEqual(affinity.call_count, 128)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="benchmark-contract-", dir=os.environ.get("JP_BENCH_TEST_ROOT"))
        self.root = Path(self.directory.name)
        self.wav = self.root / "matched.wav"
        self.pcm = bytes((i % 251 for i in range(640)))
        with wave.open(str(self.wav), "wb") as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000)
            stream.writeframes(self.pcm)
        self.selection = RuntimeSelection("nemotron", "anonymous", "saved", "current_delayed")

    def tearDown(self):
        self.directory.cleanup()

    def info(self):
        return inspect_wav(self.wav, digest(self.wav))

    def test_matched_wav_and_policy_no_implicit_truncation(self):
        info = self.info()
        self.assertEqual(info["source_samples"], 320)
        with self.assertRaises(ValueError):
            inspect_wav(self.wav, "0" * 64)
        oversized = dict(info, source_samples=16001)
        with self.assertRaises(ValueError):
            make_plan(oversized, self.selection, SessionPolicy(1))
        with self.assertRaises(ValueError):
            make_plan(info, self.selection, SessionPolicy(), repeat_seconds=3600)

    def test_explicit_hour_plan_bounded_reads_continuous_source_clock(self):
        plan = make_plan(self.info(), self.selection, SessionPolicy(3600, True), repeat_seconds=3600)
        self.assertEqual(plan["target_samples"], 57600000)
        self.assertTrue(plan["repeated_input"])
        self.assertFalse(plan["reset_between_repetitions"])
        blocks = list(islice(pcm_blocks(self.wav, plan["target_samples"], 1600, repeat=True), 2))
        self.assertEqual([row[0] for row in blocks], [0, 1600])
        self.assertEqual(blocks[0][1], self.pcm * 5)
        self.assertEqual(blocks[1][1], self.pcm * 5)
        self.assertEqual(blocks[1][2]["repetition_start"], 5)
        self.assertEqual(blocks[1][2]["repetition_end"], 9)
        self.assertEqual(len(blocks[0][1]), 3200)

    def test_segmented_probability_bytes_and_hashes_exact(self):
        writer = SegmentedOutput(self.root, "prob", 100, part_bytes=16)
        writer.write(b"a" * 21)
        writer.write(b"b" * 9)
        receipt = writer.close()
        self.assertEqual([p["bytes"] for p in receipt["parts"]], [16, 14])
        raw = b"".join((self.root / p["path"]).read_bytes() for p in receipt["parts"])
        self.assertEqual(raw, b"a" * 21 + b"b" * 9)
        self.assertEqual(receipt["sha256"], hashlib.sha256(raw).hexdigest())
        with self.assertRaises(ValueError):
            SegmentedOutput(self.root, "too-large", 2).write(b"123")

    def fake_factory(self, *, invalid=False):
        import numpy as np
        owner = self
        class FakeModel:
            def __init__(self):
                self.samples = self.frames = 0
                self._closed = False
                self._stream = object(); self._model = object()
                self.reset_calls = 0
                owner.created = self
            def update(self, final):
                count = self.samples // 160 + 1
                first = self.frames
                values = np.full((count-first, 8), .25, dtype=np.float32)
                if invalid and len(values): values[0, 0] = np.nan
                self.frames = count
                return SimpleNamespace(frame_start=first, frame_end=count, probabilities=values,
                    seconds_per_frame=.01, audio_received_sec=self.samples / 16000,
                    is_final=final, compute_sec=0.)
            def push(self, audio, *, received_at_monotonic=None):
                self.samples += len(audio)
                return self.update(False)
            def finish(self): return self.update(True)
            def reset(self):
                self.reset_calls += 1
                raise AssertionError("No reset is permitted")
            def close(self):
                self._closed = True; self._stream = self._model = None
        return np, FakeModel

    def test_full_frame_eof_init_push_finish_and_no_native_claim(self):
        plan = make_plan(self.info(), self.selection, SessionPolicy(), block_samples=160)
        np, factory = self.fake_factory()
        out = self.root / "output"; out.mkdir()
        result = run_stream(plan, factory, np, out, native_execution=False,
                            measure=lambda: dict(rss_bytes=None, cpu_seconds=0., temperatures_celsius={}))
        self.assertIsNone(result["failure"])
        self.assertEqual((result["delivered_samples"], result["output_frames"]), (320, 3))
        self.assertEqual(result["probabilities"]["bytes"], 96)
        self.assertEqual(self.created.reset_calls, 0)
        self.assertTrue(result["closure"]["pointers_empty"])
        self.assertFalse(result["native_execution"])
        self.assertFalse(result["sustained_realtime_qualified"])
        raw = b"".join((out / p["path"]).read_bytes() for p in result["timings"]["parts"])
        rows = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual([row["kind"] for row in rows], ["push", "push", "finish"])
        self.assertEqual([row["source_samples"] for row in rows], [160, 320, 320])
        self.assertTrue((out / "MODEL_INIT.json").exists())

    def test_invalid_model_output_keeps_failure_receipt_without_exporting_nan(self):
        plan = make_plan(self.info(), self.selection, SessionPolicy())
        np, factory = self.fake_factory(invalid=True)
        out = self.root / "failed"; out.mkdir()
        result = run_stream(plan, factory, np, out, native_execution=False,
                            measure=lambda: dict(rss_bytes=None))
        self.assertEqual(result["status"], "FAILED_PREFIX_PRESERVED")
        self.assertFalse(result["complete_eof"])
        self.assertEqual(result["probabilities"]["bytes"], 0)
        self.assertTrue(self.created._closed)

    def test_truncated_wav_is_failure_and_keeps_processed_prefix(self):
        raw = self.wav.read_bytes()
        self.wav.write_bytes(raw[:-320])
        plan = make_plan(self.info(), self.selection, SessionPolicy(), block_samples=160)
        np, factory = self.fake_factory()
        out = self.root / "truncated"; out.mkdir()
        result = run_stream(plan, factory, np, out, native_execution=False,
                            measure=lambda: dict(rss_bytes=None))
        self.assertEqual(result["delivered_samples"], 160)
        self.assertEqual(result["output_frames"], 2)
        self.assertEqual(result["probabilities"]["bytes"], 64)
        self.assertIn("Truncated WAV", result["failure"])


if __name__ == "__main__":
    unittest.main()
