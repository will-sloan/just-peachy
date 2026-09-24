"""Check the E1 adapter in the unchanged application Python; see README.md."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[key] = "1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if os.name == "nt":
        if not ctypes.windll.kernel32.SetPriorityClass(wintypes.HANDLE(-1), 0x00004000):
            raise OSError("could not set BelowNormal process priority")
    sys.path.insert(0, str(args.vendor))
    import numpy as np
    import soundfile as sf
    from edge_speech_pipeline.titanet_embedding import TitanetEmbedding, sha256_file
    start = time.perf_counter()
    model = TitanetEmbedding(args.bundle, threads=1)
    windows = json.loads(args.windows.read_text(encoding="utf-8"))["windows"]
    candidates = [row for row in windows if row["role"] in ("E", "C") and row["end_sample"] - row["start_sample"] >= 8000]
    panel = [min(candidates, key=lambda row: row["end_sample"] - row["start_sample"]), max(candidates, key=lambda row: row["end_sample"] - row["start_sample"])]
    rows = []
    for row in panel:
        path = Path(row["audio"]["path"])
        if sha256_file(path) != row["audio"]["sha256"]:
            raise ValueError("source hash mismatch")
        waveform, sr = sf.read(path, dtype="float32")
        waveform = waveform[row["start_sample"]:row["end_sample"]]
        vector = model.embed(waveform, sr)
        latency = model.last_embed_ms
        repeat = model.embed(waveform, sr)
        rows.append({"window_id": row["window_id"], "samples": len(waveform), "duration_sec": len(waveform)/sr, "shape": list(vector.shape), "norm": float(np.linalg.norm(vector)), "repeat_max_abs_delta": float(np.max(np.abs(vector-repeat))), "first_call_ms": latency, "repeat_ms": model.last_embed_ms})
    try:
        TitanetEmbedding(args.bundle, expected_sha256="0" * 64)
        namespace_reject = False
    except ValueError:
        namespace_reject = True
    receipt = {"status": "PASS" if namespace_reject and all(row["shape"] == [192] and abs(row["norm"]-1) < 1e-5 and row["repeat_max_abs_delta"] < 1e-5 for row in rows) else "FAILED", "scope": "unchanged application environment CPU adapter; shortest and longest admitted E/C windows, no calibration or Q selection", "rows": rows, "namespace_mismatch_rejected": namespace_reject, "namespace": model.namespace, "versions": {package: importlib.metadata.version(package) for package in ("numpy", "onnxruntime", "soundfile")}, "python": sys.version, "interpreter": sys.executable, "threads": 1, "elapsed_sec": time.perf_counter()-start, "process_cpu_sec": time.process_time()}
    if os.name == "nt":
        receipt["priority_class"] = ctypes.windll.kernel32.GetPriorityClass(wintypes.HANDLE(-1))
        class MemoryCounters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [(key, ctypes.c_size_t) for key in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(-1), ctypes.byref(counters), counters.cb):
            receipt["memory_bytes"] = {key: getattr(counters, key) for key in ("PeakWorkingSetSize", "WorkingSetSize", "PagefileUsage", "PeakPagefileUsage")}
    model.close()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    if receipt["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
