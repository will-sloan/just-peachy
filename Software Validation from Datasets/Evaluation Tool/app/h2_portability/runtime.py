"""Lean deterministic ONNX sessions used by the explicit H2 portable profile."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from .contracts import PYANNOTE_FIXED_SAMPLES, REDIMNET2_EMBEDDING_DIM
from .onnx_tooling import sha256_file
from .parity import POWERSET_TO_MULTILABEL


class H2OnnxRuntimeError(RuntimeError):
    """A graph or input does not satisfy the H2 ONNX runtime contract."""


def _session(path: Path, *, threads: int):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(
        str(path), sess_options=options, providers=["CPUExecutionProvider"]
    )


@dataclass
class H2OnnxRuntimeBundle:
    """One shared ReDim session and one fixed-window segmentation session."""

    redimnet2_path: Path
    segmentation_path: Path
    expected_sha256: Mapping[str, str] | None = None
    threads: int = 1

    def __post_init__(self) -> None:
        self.redimnet2_path = Path(self.redimnet2_path).resolve()
        self.segmentation_path = Path(self.segmentation_path).resolve()
        if self.threads < 1:
            raise ValueError("threads must be at least one")
        for path in (self.redimnet2_path, self.segmentation_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        expected = dict(self.expected_sha256 or {})
        observed = {
            "redimnet2_b2_speaker_embedding": sha256_file(self.redimnet2_path),
            "pyannote_segmentation_3_0": sha256_file(self.segmentation_path),
        }
        for component_id, digest in expected.items():
            if component_id not in observed:
                raise ValueError(f"unexpected component hash key: {component_id}")
            if observed[component_id].lower() != digest.lower():
                raise H2OnnxRuntimeError(
                    f"ONNX graph hash mismatch for {component_id}: "
                    f"expected {digest}, observed {observed[component_id]}"
                )
        self.graph_sha256 = observed
        self._redim = _session(self.redimnet2_path, threads=self.threads)
        self._segmentation = _session(self.segmentation_path, threads=self.threads)
        if self._redim.get_inputs()[0].name != "waveform":
            raise H2OnnxRuntimeError("ReDimNet2 ONNX input name mismatch")
        if self._segmentation.get_inputs()[0].shape != [1, 1, PYANNOTE_FIXED_SAMPLES]:
            raise H2OnnxRuntimeError("Pyannote ONNX input shape mismatch")

    def embed(self, waveform: np.ndarray) -> np.ndarray:
        """Return one finite L2-normalized 192-vector from mono 16 kHz samples."""

        samples = np.asarray(waveform, dtype=np.float32).reshape(-1)
        if samples.size < 8_000:
            raise H2OnnxRuntimeError("ReDimNet2 requires at least 0.5 seconds")
        raw = self._redim.run(None, {"waveform": samples[None, :]})[0]
        if raw.shape != (1, REDIMNET2_EMBEDDING_DIM):
            raise H2OnnxRuntimeError(f"ReDimNet2 output shape mismatch: {raw.shape}")
        vector = raw[0].astype(np.float64)
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 0.0:
            raise H2OnnxRuntimeError("ReDimNet2 output is zero or non-finite")
        return np.asarray(vector / norm, dtype=np.float32)

    def segment(self, waveform: np.ndarray) -> dict[str, np.ndarray]:
        """Return raw powerset scores and frozen speech/overlap frame views."""

        samples = np.asarray(waveform, dtype=np.float32).reshape(-1)
        if samples.size != PYANNOTE_FIXED_SAMPLES:
            raise H2OnnxRuntimeError("Pyannote requires exactly one 10-second window")
        raw = self._segmentation.run(
            None, {"waveform": samples[None, None, :]}
        )[0]
        if raw.ndim != 3 or raw.shape[0] != 1 or raw.shape[-1] != 7:
            raise H2OnnxRuntimeError(f"Pyannote output shape mismatch: {raw.shape}")
        powerset_class = np.argmax(raw, axis=-1)
        multilabel = POWERSET_TO_MULTILABEL[powerset_class]
        ordered = np.sort(multilabel, axis=-1)
        return {
            "powerset_log_scores": raw,
            "powerset_class": powerset_class,
            "speech_activity": ordered[..., -1].astype(np.int8),
            "overlap_activity": ordered[..., -2].astype(np.int8),
        }

    def status(self) -> dict[str, object]:
        return {
            "schema_version": "h2-onnx-runtime-bundle.v1",
            "status": "LOADED",
            "threads": self.threads,
            "providers": {
                "redimnet2": self._redim.get_providers(),
                "segmentation": self._segmentation.get_providers(),
            },
            "graph_sha256": self.graph_sha256,
            "shared_redimnet2_session_for_roles": [
                "anonymous_diarization_embedding",
                "enrolled_identity_embedding",
            ],
            "core_h2_factory_wired": True,
            "runtime_profile_id": "H2_PORTABLE_ONNX_FP32",
            "linux_arm64_hardware_qualified": False,
        }


__all__ = ["H2OnnxRuntimeBundle", "H2OnnxRuntimeError"]
