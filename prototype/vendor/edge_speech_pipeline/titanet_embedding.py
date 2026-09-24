"""Pinned TitaNet-Large CPU embedding adapter; see README_TITANET.md.

The ONNX graph is NVIDIA NeMo's encoder and speaker decoder.  The NumPy
frontend implements the pinned NeMo inference frontend using exported buffers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
import time

import numpy as np


TITANET_SOURCE_SHA256 = "e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3"
PREPROCESSING_VERSION = "nemo-cf724ac3-mel80-16k-eval-v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mel_features(samples: np.ndarray, window: np.ndarray, filterbank: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic single-waveform NeMo eval features; no resampling or gain."""
    wave = np.asarray(samples, dtype=np.float32)
    emphasized = np.empty_like(wave)
    emphasized[0] = wave[0]
    emphasized[1:] = wave[1:] - np.float32(0.97) * wave[:-1]
    padded = np.pad(emphasized, (256, 256), mode="constant")
    frames = np.lib.stride_tricks.sliding_window_view(padded, 512)[::160]
    fft_window = np.pad(np.asarray(window, np.float32), (56, 56))
    spectrum = np.fft.rfft(frames * fft_window, n=512, axis=-1).astype(np.complex64)
    power = (spectrum.real ** 2 + spectrum.imag ** 2).astype(np.float32)
    # The reference computes magnitude followed by power; retain its rounding.
    power = np.sqrt(power).astype(np.float32) ** np.float32(2.0)
    mel = np.asarray(filterbank, np.float32).reshape(80, 257) @ power.T
    logged = np.log(mel + np.float32(2.0 ** -24)).astype(np.float32)
    length = len(wave) // 160
    valid = logged[:, :length]
    reference = valid[:, :1]
    means = reference + (valid - reference).sum(axis=1, keepdims=True) / np.float32(length)
    std = np.sqrt(((valid - means) ** 2).sum(axis=1, keepdims=True) / np.float32(length - 1))
    normalized = (logged - means) / (std + np.float32(1e-5))
    normalized[:, length:] = 0.0
    normalized = np.pad(normalized, ((0, 0), (0, (-normalized.shape[1]) % 16)))
    return normalized[None].astype(np.float32), np.asarray([length], np.int64)


class TitanetEmbedding:
    """Persistent one-thread CPU runtime, returning normalized 192-D vectors.

    ``model_path`` is the exported bundle's JSON manifest or its directory.
    ``expected_sha256`` binds the source .nemo checkpoint, not an ONNX filename.
    Input is mono float32 at 16 kHz. Unsupported short spans are rejected rather
    than repeated or zero padded to create evidence. 0.5 s is an application
    admission minimum, empirically checked, not a vendor accuracy guarantee.
    """

    backend_id = "titanet_large_fp32"
    dimension = 192
    sample_rate = 16000
    minimum_samples = 8000
    minimum_span_sec = 0.5
    normalization = "l2"

    def __init__(self, model_path: Path | str, *, expected_sha256: str | None = TITANET_SOURCE_SHA256, threads: int = 1) -> None:
        import onnxruntime as ort

        manifest_path = Path(model_path).resolve()
        if manifest_path.is_dir():
            manifest_path = manifest_path / "titanet_manifest.json"
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if self.manifest.get("backend_id") != self.backend_id or self.manifest.get("dimension") != self.dimension:
            raise ValueError("unsupported TitaNet representation")
        if self.manifest.get("preprocessing_version") != PREPROCESSING_VERSION:
            raise ValueError("TitaNet preprocessing version mismatch")
        if expected_sha256 and self.manifest.get("source_model_sha256") != expected_sha256:
            raise ValueError("TitaNet source checkpoint hash mismatch")
        if self.manifest.get("normalization") != self.normalization or self.manifest.get("minimum_samples") != self.minimum_samples:
            raise ValueError("TitaNet normalization or minimum span mismatch")
        artifacts = {}
        for key in ("onnx", "frontend"):
            item = self.manifest[key]
            path = (manifest_path.parent / item["filename"]).resolve()
            if path.parent != manifest_path.parent or sha256_file(path) != item["sha256"]:
                raise ValueError(f"TitaNet {key} artifact path/hash mismatch")
            artifacts[key] = path
        with np.load(artifacts["frontend"], allow_pickle=False) as buffers:
            self._window = buffers["window"].copy()
            self._filterbank = buffers["filterbank"].copy()
        if self._window.shape != (400,) or self._filterbank.shape != (1, 80, 257):
            raise ValueError("TitaNet frontend buffer dimension mismatch")
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, int(threads))
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self._session = ort.InferenceSession(str(artifacts["onnx"]), sess_options=options, providers=["CPUExecutionProvider"])
        if [x.name for x in self._session.get_inputs()] != ["features", "feature_length"]:
            raise ValueError("TitaNet ONNX input contract mismatch")
        self._lock = threading.Lock()
        self.last_embed_ms = 0.0
        self.namespace = {
            "backend_id": self.backend_id,
            "backend_sha256": self.manifest["source_model_sha256"],
            "onnx_sha256": self.manifest["onnx"]["sha256"],
            "frontend_sha256": self.manifest["frontend"]["sha256"],
            "dimension": self.dimension,
            "normalization": self.normalization,
            "minimum_samples": self.minimum_samples,
            "sample_rate_hz": self.sample_rate,
            "preprocessing_version": PREPROCESSING_VERSION,
        }

    def embed(self, waveform: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        samples = np.asarray(waveform, dtype=np.float32)
        if samples.ndim != 1 or sample_rate != self.sample_rate:
            raise ValueError("TitaNet requires mono audio sampled at 16000 Hz")
        if samples.size < self.minimum_samples:
            raise ValueError("TitaNet embedding requires at least 0.5 seconds; no audio repetition is permitted")
        if not np.isfinite(samples).all():
            raise ValueError("TitaNet waveform contains non-finite values")
        started = time.perf_counter()
        with self._lock:
            features, length = mel_features(samples, self._window, self._filterbank)
            vector = np.asarray(self._session.run(["embedding"], {"features": features, "feature_length": length})[0], np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if vector.shape != (self.dimension,) or not np.isfinite(vector).all() or norm <= 0:
            raise RuntimeError("TitaNet produced an invalid embedding")
        self.last_embed_ms = (time.perf_counter() - started) * 1000.0
        return vector / norm

    def close(self) -> None:
        """Release this runtime's ONNX session; never reset a shared gallery."""
        with self._lock:
            self._session = None
