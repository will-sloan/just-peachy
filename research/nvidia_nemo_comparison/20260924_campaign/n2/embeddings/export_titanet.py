"""Export and exercise official TitaNet-Large; see the adjacent README.md."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["WANDB_MODE"] = "disabled"

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--window-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vendor", type=Path, required=True)
    parser.add_argument("--panel-size", type=int, default=6)
    args = parser.parse_args()
    sys.path.insert(0, str(args.vendor.resolve()))
    from edge_speech_pipeline.titanet_embedding import TitanetEmbedding, TITANET_SOURCE_SHA256, PREPROCESSING_VERSION, mel_features, sha256_file
    if os.name == "nt":
        import ctypes
        if not ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(-1), 0x00004000):
            raise OSError("could not set BelowNormal process priority")
    import torch
    import soundfile as sf
    from nemo.collections.asr.models import EncDecSpeakerLabelModel
    from nemo.core.classes import typecheck

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    args.output.mkdir(parents=True, exist_ok=True)
    if sha256_file(args.checkpoint) != TITANET_SOURCE_SHA256:
        raise ValueError("checkpoint SHA256 differs from pinned E1")
    started = time.perf_counter()
    model = EncDecSpeakerLabelModel.restore_from(str(args.checkpoint), map_location=torch.device("cpu"))
    model.eval()
    model.freeze()
    model.preprocessor.featurizer.dither = 0.0
    featurizer = model.preprocessor.featurizer
    frontend_path = args.output / "titanet_frontend.npz"
    np.savez(frontend_path, window=featurizer.window.detach().cpu().numpy(), filterbank=featurizer.fb.detach().cpu().numpy())
    official_frontend = {key: getattr(featurizer, key) for key in ("sample_rate", "win_length", "hop_length", "n_fft", "preemph", "pad_to", "normalize", "log_zero_guard_value", "mag_power", "exact_pad")}
    if official_frontend != {"sample_rate": 16000, "win_length": 400, "hop_length": 160, "n_fft": 512, "preemph": 0.97, "pad_to": 16, "normalize": "per_feature", "log_zero_guard_value": 2 ** -24, "mag_power": 2.0, "exact_pad": False}:
        raise ValueError(f"unexpected official frontend: {official_frontend}")
    windows = json.loads(args.window_manifest.read_text(encoding="utf-8"))["windows"]
    calibration = [row for row in windows if row["role"] == "C" and row["domain"] == "clean_source"]
    identities = list(dict.fromkeys(row["identity"] for row in calibration))[:max(1, (args.panel_size + 1) // 2)]
    panel = []
    for identity in identities:
        panel.extend([row for row in calibration if row["identity"] == identity][:2])
    panel = panel[:args.panel_size]
    if len(panel) < 2:
        raise ValueError("at least two disjoint calibration windows required")
    waves = []
    for row in panel:
        audio = row["audio"]
        if sha256_file(Path(audio["path"])) != audio["sha256"]:
            raise ValueError("panel waveform hash mismatch")
        wave, sr = sf.read(audio["path"], dtype="float32")
        if sr != 16000 or wave.ndim != 1:
            raise ValueError("panel must contain unchanged mono 16k waveforms")
        wave = wave[row["start_sample"]:row["end_sample"]]
        waves.append(wave)

    class EmbeddingExport(torch.nn.Module):
        def __init__(self, reference):
            super().__init__()
            self.encoder = reference.encoder
            self.decoder = reference.decoder

        def forward(self, features, feature_length):
            encoded, length = self.encoder(audio_signal=features, length=feature_length)
            _, embedding = self.decoder(encoder_output=encoded, length=length)
            return embedding

    example = torch.from_numpy(waves[0][None])
    with torch.inference_mode():
        features, feature_length = model.preprocessor(input_signal=example, length=torch.tensor([example.shape[1]]))
    graph = EmbeddingExport(model).eval()
    onnx_path = args.output / "titanet_embedding.onnx"
    with torch.inference_mode(), typecheck.disable_checks():
        torch.onnx.export(graph, (features, feature_length), str(onnx_path),
                          input_names=["features", "feature_length"], output_names=["embedding"],
                          dynamic_axes={"features": {2: "frames"}}, opset_version=17, dynamo=False)
    manifest = {
        "schema_version": 1, "backend_id": "titanet_large_fp32", "dimension": 192,
        "source_model_repo": "nvidia/speakerverification_en_titanet_large",
        "source_model_revision": "0dc382f40121a5fbd34db10a2bb04d826c2be6a8",
        "source_model_sha256": TITANET_SOURCE_SHA256, "license": "CC-BY-4.0",
        "nemo_source_revision": "cf724ac337d1ebc7d0dda1e23fb80916f52927a5",
        "preprocessing_version": PREPROCESSING_VERSION, "preprocessing": official_frontend,
        "normalization": "l2", "minimum_samples": 8000, "minimum_span_policy": "application minimum checked with real audio; no vendor accuracy guarantee",
        "onnx": {"filename": onnx_path.name, "sha256": sha256_file(onnx_path)},
        "frontend": {"filename": frontend_path.name, "sha256": sha256_file(frontend_path)},
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = args.output / "titanet_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    candidate = TitanetEmbedding(manifest_path)
    rows, reference_vectors, actual_vectors = [], [], []
    test_cases = [(row["window_id"], wave) for row, wave in zip(panel, waves)]
    # Prefixes check dynamic export/minimum behavior only, never enroll padded
    # or repeated snippets, and never enter verification/calibration statistics.
    test_cases += [("minimum_real_0.5s", waves[0][:8000]), ("real_non_hop_length", waves[0][:8013]), ("constant_zero_control", np.zeros(16000, np.float32)), ("constant_one_control", np.ones(16000, np.float32))]
    for window_id, wave in test_cases:
        tensor = torch.from_numpy(wave[None])
        lengths = torch.tensor([len(wave)])
        t0 = time.perf_counter()
        with torch.inference_mode():
            ref_features, ref_length = model.preprocessor(input_signal=tensor, length=lengths)
            _, reference_raw = model(input_signal=tensor, input_signal_length=lengths)
        reference = reference_raw[0].numpy()
        reference = reference / np.linalg.norm(reference)
        ref_ms = (time.perf_counter() - t0) * 1000
        actual = candidate.embed(wave)
        frontend_actual, length_actual = mel_features(wave, candidate._window, candidate._filterbank)
        feature_delta = float(np.max(np.abs(frontend_actual - ref_features.numpy())))
        vector_delta = float(np.max(np.abs(reference - actual)))
        cosine = float(reference @ actual)
        rows.append({"window_id": window_id, "samples": len(wave), "feature_shape": list(frontend_actual.shape), "feature_length_equal": bool(np.array_equal(length_actual, ref_length.numpy())), "feature_max_abs_error": feature_delta, "embedding_max_abs_error": vector_delta, "embedding_cosine": cosine, "reference_ms": ref_ms, "onnx_frontend_ms": candidate.last_embed_ms})
        if window_id not in {"minimum_real_0.5s", "real_non_hop_length", "constant_zero_control", "constant_one_control"}:
            reference_vectors.append(reference)
            actual_vectors.append(actual)
    ref_matrix, actual_matrix = np.stack(reference_vectors), np.stack(actual_vectors)
    score_error = float(np.max(np.abs(ref_matrix @ ref_matrix.T - actual_matrix @ actual_matrix.T)))
    rejects = {}
    for label, waveform, sr in [("empty", np.empty(0, np.float32), 16000), ("too_short", waves[0][:7999], 16000), ("stereo", np.zeros((8000, 2), np.float32), 16000), ("wrong_rate", waves[0], 8000), ("nan", np.full(8000, np.nan, np.float32), 16000)]:
        try:
            candidate.embed(waveform, sr)
            rejects[label] = False
        except ValueError:
            rejects[label] = True
    passed = all(row["feature_length_equal"] and row["embedding_cosine"] > 0.9999 and row["embedding_max_abs_error"] < 1e-3 for row in rows) and score_error < 1e-3 and all(rejects.values())
    receipt = {"status": "PASS" if passed else "FAILED", "scope": "actual CPU reference vs ONNX+NumPy, identical saved calibration waveform windows; not calibration efficacy or target-hardware performance", "window_manifest_sha256": sha256_file(args.window_manifest), "panel_window_ids": [row["window_id"] for row in panel], "rows": rows, "pairwise_cosine_max_abs_error": score_error, "invalid_inputs_rejected": rejects, "parameter_count": sum(p.numel() for p in model.parameters()), "onnx_bytes": onnx_path.stat().st_size, "namespace": candidate.namespace, "versions": {package: importlib.metadata.version(package) for package in ("nemo-toolkit", "torch", "numpy", "onnx", "onnxruntime", "librosa")}, "threads": 1, "device": "CPU", "gpu_used": False, "elapsed_sec": time.perf_counter() - started, "arm64_execution": "NOT_TESTED", "minimum_policy": "8000 samples; real waveform passed; shorter rejected", "created_at_utc": datetime.now(timezone.utc).isoformat()}
    receipt["process_cpu_sec"] = time.process_time()
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        receipt["priority_class"] = ctypes.windll.kernel32.GetPriorityClass(wintypes.HANDLE(-1))
        class MemoryCounters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [(key, ctypes.c_size_t) for key in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(-1), ctypes.byref(counters), counters.cb):
            receipt["memory_bytes"] = {key: getattr(counters, key) for key in ("PeakWorkingSetSize", "WorkingSetSize", "PagefileUsage", "PeakPagefileUsage")}
    (args.output / "parity_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "pairwise_cosine_max_abs_error": score_error, "onnx_bytes": receipt["onnx_bytes"], "elapsed_sec": receipt["elapsed_sec"]}))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
