"""JSONL entry point for persistent isolated segmentation/embedding workers.

The module writes protocol messages only to stdout.  Component diagnostics and
tracebacks belong on stderr so they cannot corrupt the RPC channel.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata as importlib_metadata
import json
import os
from pathlib import Path
import random
import sys
import time
from typing import Mapping

from app.full_pipeline.cache import canonical_sha256
from app.full_pipeline.workers import WORKER_PROTOCOL


class WorkerMainError(RuntimeError):
    """Structured component-side failure."""


class _Engine:
    def __init__(self, component_id: str) -> None:
        self.component_id = component_id
        self.warmed_up = False
        self.request_count = 0
        self.identity: dict[str, object] = {
            "component_id": component_id,
            "declared_identity_sha256": canonical_sha256(
                {"kind": type(self).__name__, "component_id": component_id}
            ),
        }

    def execute(
        self, operation: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        self.request_count += 1
        if operation == "ping":
            return self._health()
        if operation == "reset":
            return {"reset": True, **self._health()}
        if operation == "warmup":
            result = self._infer(payload)
            status = str(result.get("status", "ok"))
            if status.lower() not in {"ok", "running", "healthy", "pass"}:
                raise WorkerMainError(f"model warmup failed with status {status}")
            self.warmed_up = True
            return {
                "warmed_up": True,
                "status": result.get("status", "ok"),
                "identity": self.identity,
            }
        if operation in {"infer", "segment", "embed"}:
            return self._infer(payload)
        raise WorkerMainError(f"unsupported operation: {operation}")

    def _infer(self, payload: Mapping[str, object]) -> dict[str, object]:
        raise WorkerMainError("inference is not implemented")

    def _health(self) -> dict[str, object]:
        return {
            "status": "HEALTHY",
            "pid": os.getpid(),
            "component_id": self.component_id,
            "warmed_up": self.warmed_up,
            "request_count": self.request_count,
            "identity": self.identity,
        }


class _TestEngine(_Engine):
    """Model-free protocol engine used only by targeted supervisor tests."""

    def execute(
        self, operation: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        if operation == "crash":
            os._exit(91)
        if operation == "sleep":
            time.sleep(float(payload.get("seconds", 0.0)))
            return {"slept": float(payload.get("seconds", 0.0))}
        if operation == "fail":
            raise WorkerMainError("requested test failure")
        if operation == "echo":
            return {"echo": dict(payload)}
        return super().execute(operation, payload)

    def _infer(self, payload: Mapping[str, object]) -> dict[str, object]:
        return {
            "status": str(payload.get("force_status") or "ok"),
            "echo": dict(payload),
        }


class _SpeakerEmbeddingEngine(_Engine):
    def __init__(self, component_id: str) -> None:
        from app.hybrid_speaker_attribution.embedding_cache import (
            canonical_sha256 as hybrid_sha256,
        )
        from app.inference_pipeline.speaker_embedding import (
            build_speaker_embedding_from_config,
        )
        from app.speaker_protocol.contracts import eligible_embedding_backends
        from app.speaker_protocol.extraction import _embedding_config

        eligible = eligible_embedding_backends(backend_ids={component_id})
        if component_id not in eligible:
            raise WorkerMainError(f"speaker backend is not qualified: {component_id}")
        declared = dict(eligible[component_id])
        config = _embedding_config(component_id)
        config_identity = config.to_jsonable()
        adapter = build_speaker_embedding_from_config(config)
        if adapter is None:
            raise WorkerMainError(f"speaker backend did not build: {component_id}")
        self.adapter = adapter
        self.declared = declared
        super().__init__(component_id)
        self.identity = {
            "kind": "speaker_embedding",
            "component_id": component_id,
            "environment_profile": declared["environment_profile"],
            "declared_backend": declared,
            "declared_backend_identity_hash": hybrid_sha256(declared),
            "declared_identity_sha256": canonical_sha256(
                {
                    "kind": "speaker_embedding",
                    "component_id": component_id,
                    "declared_backend": declared,
                    "config": config_identity,
                }
            ),
            "pipeline_config": config_identity,
            "implicit_model_downloads_allowed": False,
        }

    def _infer(self, payload: Mapping[str, object]) -> dict[str, object]:
        import soundfile as sf

        from app.inference_pipeline.contracts import AudioSegment
        from app.inference_pipeline.speaker_embedding.base import (
            SpeakerEmbeddingContext,
        )
        from app.speaker_protocol.contracts import backend_identity

        path = _verified_audio_path(payload)
        info = sf.info(path)
        start_sec = float(payload.get("start_sec", 0.0))
        end_sec = float(payload.get("end_sec", info.duration))
        if start_sec < 0 or end_sec <= start_sec or end_sec > info.duration + 1e-6:
            raise WorkerMainError("embedding audio interval is invalid")
        segment = AudioSegment(
            audio_path=path,
            start_sec=start_sec,
            end_sec=end_sec,
            duration_sec=end_sec - start_sec,
            sample_rate_hz=int(info.samplerate),
            channel_count=int(info.channels),
            is_mono=int(info.channels) == 1,
        )
        job_id = str(
            payload.get("job_id") or payload.get("window_id") or "runtime-window"
        )
        context = SpeakerEmbeddingContext(
            recording_id=str(payload.get("recording_id") or "runtime-session"),
            utt_id=job_id,
            source_audio_path=path,
            segment_index=int(payload.get("segment_index", 0)),
            segment_start_sec=start_sec,
            segment_end_sec=end_sec,
            device=str(payload.get("device") or "cpu"),
            dtype="float32",
            run_config={"project_root": str(Path(__file__).resolve().parents[4])},
        )
        started = time.perf_counter()
        result = self.adapter.embed(segment, context)
        if result.status == "ok":
            observed = backend_identity(
                self.component_id, int(result.dimension or 0)
            ).to_jsonable()
            self.identity = {**self.identity, "observed_backend_identity": observed}
        return {
            "status": result.status,
            "role": str(payload.get("role") or "unspecified"),
            "window_id": job_id,
            "embedding": result.to_jsonable(),
            "worker_wall_sec": time.perf_counter() - started,
            "identity": self.identity,
        }


class _PyannoteSegmentationEngine(_Engine):
    def __init__(self, component_id: str) -> None:
        if component_id != "pyannote_segmentation_3_0":
            raise WorkerMainError(f"unsupported segmentation component: {component_id}")
        from app.diarization_product_v2.cross_environment import _segmentation_config
        from app.inference_pipeline.asr.audio_utils import resolve_model_path
        from app.inference_pipeline.diarization.modular_adapter import (
            ModularClusteringDiarizer,
        )

        config = _segmentation_config()
        params = {
            **config,
            "embedding_component_config": (
                "configs/inference/components/speaker_embedding/campplus.yaml"
            ),
            "clustering_policy_id": "full_pipeline_segmentation_worker_only",
            "clustering_threshold": 0.35,
            "min_embedding_window_sec": 0.75,
            "device": "cpu",
            "allow_model_downloads": False,
        }
        self.diarizer = ModularClusteringDiarizer(params)
        model_root = resolve_model_path(str(config["segmentation_model_path"]))
        asset_files = {
            name: _sha256_file(model_root / name)
            for name in ("config.yaml", "pytorch_model.bin")
            if (model_root / name).is_file()
        }
        try:
            package_version = importlib_metadata.version("pyannote.audio")
        except importlib_metadata.PackageNotFoundError:
            package_version = None
        super().__init__(component_id)
        declared = {
            "kind": "pyannote_segmentation",
            "component_id": component_id,
            "segmentation_config": config,
            "model_asset_files": asset_files,
            "pyannote_audio_version": package_version,
            "model_training_chunk_duration_sec": 10.0,
            "model_temporal_architecture": "bidirectional_lstm",
            "implicit_model_downloads_allowed": False,
        }
        self.identity = {
            **declared,
            "declared_identity_sha256": canonical_sha256(declared),
        }

    def _infer(self, payload: Mapping[str, object]) -> dict[str, object]:
        from app.inference_pipeline.audio_io.loader import load_audio

        path = _verified_audio_path(payload)
        start_sec = float(payload.get("start_sec", 0.0))
        end_value = payload.get("end_sec")
        end_sec = float(end_value) if end_value is not None else None
        offset_sec = float(payload.get("source_timestamp_offset_sec", start_sec))
        record = {
            "recording_id": str(payload.get("recording_id") or "runtime-session"),
            "source_recording_id": str(
                payload.get("recording_id") or "runtime-session"
            ),
            "utt_id": str(payload.get("chunk_id") or "segmentation-chunk"),
            "inference_audio_path": str(path),
            "start_sec": start_sec,
            "end_sec": end_sec,
        }
        started = time.perf_counter()
        audio = load_audio(
            record,
            {
                "runtime": {"sample_rate_hz": 16_000},
                "audio": {"channel_policy": "mono"},
            },
        )
        # These values are part of the request/cache identity.  The persistent
        # worker is serial, so applying them immediately before inference is
        # deterministic and does not leak between concurrent calls.
        self.diarizer.segmentation_onset = float(
            payload.get("segmentation_onset", self.diarizer.segmentation_onset)
        )
        self.diarizer.segmentation_offset = float(
            payload.get("segmentation_offset", self.diarizer.segmentation_offset)
        )
        self.diarizer.segmentation_min_duration_on = float(
            payload.get(
                "segmentation_min_duration_on",
                self.diarizer.segmentation_min_duration_on,
            )
        )
        self.diarizer.segmentation_min_duration_off = float(
            payload.get(
                "segmentation_min_duration_off",
                self.diarizer.segmentation_min_duration_off,
            )
        )
        regions, predicted_overlap_regions = (
            self.diarizer._speech_and_overlap_regions(audio)
        )
        return {
            "status": "ok",
            "chunk_id": record["utt_id"],
            "speech_regions": [
                {
                    "start_sec": offset_sec + float(row.start_sec),
                    "end_sec": offset_sec + float(row.end_sec),
                }
                for row in regions
            ],
            "predicted_overlap_regions": [
                {
                    "start_sec": offset_sec + float(row.start_sec),
                    "end_sec": offset_sec + float(row.end_sec),
                }
                for row in predicted_overlap_regions
            ],
            "input_duration_sec": audio.duration_sec,
            "segmentation_compute_sec": time.perf_counter() - started,
            "algorithmic_lookahead_sec": payload.get("algorithmic_lookahead_sec"),
            "compute_latency_included_in_lookahead": False,
            "identity": self.identity,
        }


class _NativeSherpaEngine(_Engine):
    """Persistent decoder session inside the qualified ONNX environment."""

    def __init__(self, component_id: str) -> None:
        import yaml

        from app.full_pipeline.asr import build_sherpa_streaming_adapter

        config_names = {
            "sherpa_onnx": "sherpa_onnx.yaml",
            "sherpa_onnx_libri_giga_zipformer_2023_06_21": (
                "sherpa_onnx_libri_giga_zipformer_2023_06_21.yaml"
            ),
        }
        if component_id not in config_names:
            raise WorkerMainError(
                f"unsupported native Sherpa component: {component_id}"
            )
        path = (
            Path(__file__).resolve().parents[2]
            / "configs/inference/components/asr"
            / config_names[component_id]
        )
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        params = dict(config["component"]["params"])
        endpoint = {
            "enabled": True,
            "policy_id": "full_pipeline_sherpa_endpoint_backend_defaults.v1",
            "rule1_min_trailing_silence": 2.4,
            "rule2_min_trailing_silence": 1.2,
            "rule3_min_utterance_length": 20.0,
        }
        self.adapter = build_sherpa_streaming_adapter(
            component_id,
            params,
            endpoint_overlay=endpoint,
            auto_reset_on_endpoint=True,
        )
        self.config_path = path
        self.config_sha256 = _sha256_file(path)
        self._session_started = False
        super().__init__(component_id)
        declared = {
            "kind": "native_sherpa_asr",
            "component_id": component_id,
            "config_path": str(path),
            "config_sha256": self.config_sha256,
            "endpoint_overlay": endpoint,
            "native_persistent_stream": True,
            "implicit_model_downloads_allowed": False,
        }
        self.identity = {
            **declared,
            "declared_identity_sha256": canonical_sha256(declared),
        }

    def execute(
        self, operation: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        self.request_count += 1
        if operation == "ping":
            return {**self._health(), "adapter": dict(self.adapter.status())}
        if operation in {"start_session", "warmup"}:
            if self._session_started:
                self.adapter.close()
            session_id = str(payload.get("session_id") or "worker-warmup")
            self.adapter.start(
                session_id,
                source_start_sec=float(payload.get("source_start_sec", 0.0)),
            )
            self._session_started = True
            self.warmed_up = True
            return {
                "status": "running",
                "warmed_up": True,
                "identity": self.identity,
                "adapter": dict(self.adapter.status()),
            }
        if operation in {"accept_audio", "accept"}:
            if not self._session_started:
                raise WorkerMainError("start_session is required before accept_audio")
            samples_path = Path(str(payload.get("samples_path") or "")).resolve()
            if not samples_path.is_file():
                raise WorkerMainError("samples_path does not exist")
            import numpy as np

            samples = np.load(samples_path, allow_pickle=False)
            updates = self.adapter.accept_samples(
                samples,
                sample_rate=int(payload.get("sample_rate_hz", 16000)),
                source_start_sec=float(payload["source_start_sec"]),
                source_end_sec=float(payload["source_end_sec"]),
                source_sample_start=int(payload["source_sample_start"]),
                source_sample_end=int(payload["source_sample_end"]),
                source_clock_id=str(payload["source_clock_id"]),
                source_clock_type=str(payload["source_clock_type"]),
            )
            return {
                "status": "ok",
                "updates": [
                    dict(self.adapter._hypothesis_record(update)) for update in updates
                ],
                "identity": self.identity,
            }
        if operation == "finalize":
            if not self._session_started:
                return {"status": "idle", "updates": [], "identity": self.identity}
            update = self.adapter.finalize_one(
                reason=str(payload.get("reason") or "input_finished")
            )
            self._session_started = False
            return {
                "status": "finalized",
                "updates": [dict(self.adapter._hypothesis_record(update))],
                "identity": self.identity,
            }
        if operation == "reset":
            if not self._session_started:
                return {"status": "idle", "reset": True, "identity": self.identity}
            update = self.adapter.reset_one(
                reason=str(payload.get("reason") or "worker_reset")
            )
            return {
                "status": "running",
                "reset": update.to_jsonable(),
                "identity": self.identity,
            }
        if operation == "status":
            return {"identity": self.identity, "adapter": dict(self.adapter.status())}
        raise WorkerMainError(f"unsupported native ASR operation: {operation}")


class _H2PortableOnnxEngine(_Engine):
    """One isolated ONNX Runtime worker shared by H2 segmentation/embedding."""

    def __init__(
        self,
        component_id: str,
        *,
        redimnet2_path: Path,
        segmentation_path: Path,
        redimnet2_sha256: str,
        segmentation_sha256: str,
    ) -> None:
        if component_id != "h2_portable_onnx_fp32":
            raise WorkerMainError(f"unsupported H2 ONNX component: {component_id}")
        from app.h2_portability.runtime import H2OnnxRuntimeBundle

        self.bundle = H2OnnxRuntimeBundle(
            redimnet2_path=redimnet2_path,
            segmentation_path=segmentation_path,
            expected_sha256={
                "redimnet2_b2_speaker_embedding": redimnet2_sha256,
                "pyannote_segmentation_3_0": segmentation_sha256,
            },
            threads=1,
        )
        super().__init__(component_id)
        declared = {
            "kind": "h2_portable_onnx_fp32",
            "component_id": component_id,
            "runtime_profile_id": "H2_PORTABLE_ONNX_FP32",
            "runtime_profile_version": "h2-portable-onnx-runtime-profile.v1",
            "graph_sha256": dict(self.bundle.graph_sha256),
            "providers": self.bundle.status()["providers"],
            "precision": "FP32",
            "implicit_model_downloads_allowed": False,
            "native_scientific_policy_changed": False,
            "linux_arm64_hardware_qualified": False,
        }
        self.identity = {
            **declared,
            "declared_identity_sha256": canonical_sha256(declared),
        }

    def execute(
        self, operation: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        self.request_count += 1
        if operation == "embed":
            return self._embed(payload)
        if operation == "segment":
            return self._segment(payload)
        if operation == "warmup":
            # Warm both graphs with the caller's checksum-pinned 10-second WAV.
            self._segment(payload)
            self._embed({**dict(payload), "start_sec": 0.0, "end_sec": 2.0})
            self.warmed_up = True
            return {"status": "ok", "warmed_up": True, "identity": self.identity}
        if operation == "ping":
            return self._health()
        if operation == "reset":
            return {"reset": True, **self._health()}
        raise WorkerMainError(f"unsupported H2 ONNX operation: {operation}")

    def _embed(self, payload: Mapping[str, object]) -> dict[str, object]:
        import numpy as np
        import soundfile as sf

        path = _verified_audio_path(payload)
        samples, rate = sf.read(path, dtype="float32", always_2d=True)
        if int(rate) != 16_000:
            raise WorkerMainError("H2 ONNX embedding input must be 16 kHz")
        mono = np.mean(samples, axis=1, dtype=np.float32)
        start = float(payload.get("start_sec", 0.0))
        end = float(payload.get("end_sec", mono.size / 16_000))
        left = round(start * 16_000)
        right = round(end * 16_000)
        if left < 0 or right <= left or right > mono.size:
            raise WorkerMainError("H2 ONNX embedding interval is invalid")
        started = time.perf_counter()
        vector = self.bundle.embed(mono[left:right])
        return {
            "status": "ok",
            "role": str(payload.get("role") or "unspecified"),
            "window_id": str(payload.get("window_id") or "runtime-window"),
            "embedding": {
                "status": "ok",
                "vector": vector.tolist(),
                "dimension": int(vector.size),
            },
            "worker_wall_sec": time.perf_counter() - started,
            "identity": self.identity,
        }

    def _segment(self, payload: Mapping[str, object]) -> dict[str, object]:
        import numpy as np
        import soundfile as sf

        path = _verified_audio_path(payload)
        samples, rate = sf.read(path, dtype="float32", always_2d=True)
        if int(rate) != 16_000:
            raise WorkerMainError("H2 ONNX segmentation input must be 16 kHz")
        mono = np.mean(samples, axis=1, dtype=np.float32)
        if mono.size != 160_000:
            raise WorkerMainError("H2 ONNX segmentation requires exactly 10 seconds")
        started = time.perf_counter()
        views = self.bundle.segment(mono)
        onset = float(payload.get("segmentation_onset", 0.5))
        offset = float(payload.get("segmentation_offset", onset))
        minimum_on = float(payload.get("segmentation_min_duration_on", 0.0))
        minimum_off = float(payload.get("segmentation_min_duration_off", 0.0))
        source_offset = float(payload.get("source_timestamp_offset_sec", 0.0))
        speech = _binarize_h2_activity(
            views["speech_activity"],
            onset=onset,
            offset=offset,
            minimum_on_sec=minimum_on,
            minimum_off_sec=minimum_off,
        )
        overlap = _binarize_h2_activity(
            views["overlap_activity"],
            onset=onset,
            offset=offset,
            minimum_on_sec=minimum_on,
            minimum_off_sec=minimum_off,
        )
        return {
            "status": "ok",
            "chunk_id": str(payload.get("chunk_id") or "segmentation-chunk"),
            "speech_regions": [
                {"start_sec": source_offset + left, "end_sec": source_offset + right}
                for left, right in speech
            ],
            "predicted_overlap_regions": [
                {"start_sec": source_offset + left, "end_sec": source_offset + right}
                for left, right in overlap
            ],
            "input_duration_sec": mono.size / 16_000,
            "segmentation_compute_sec": time.perf_counter() - started,
            "algorithmic_lookahead_sec": payload.get("algorithmic_lookahead_sec"),
            "compute_latency_included_in_lookahead": False,
            "identity": self.identity,
        }


def _binarize_h2_activity(
    activity: object,
    *,
    onset: float,
    offset: float,
    minimum_on_sec: float,
    minimum_off_sec: float,
) -> list[tuple[float, float]]:
    """Pure-NumPy equivalent of the pinned Pyannote ``Binarize`` contract."""

    import numpy as np

    values = np.asarray(activity, dtype=np.float32).reshape(-1)
    if values.size == 0:
        return []
    if not 0.0 <= onset <= 1.0 or not 0.0 <= offset <= 1.0:
        raise WorkerMainError("segmentation thresholds must be in [0, 1]")
    if minimum_on_sec < 0.0 or minimum_off_sec < 0.0:
        raise WorkerMainError("segmentation minimum durations must be non-negative")
    # Exact receptive field of the pinned Segmentation 3.0 model.
    frame_duration = 0.0619375
    frame_step = 0.016875
    timestamps = frame_duration / 2.0 + np.arange(values.size) * frame_step
    active = bool(values[0] > onset)
    start = float(timestamps[0])
    regions: list[tuple[float, float]] = []
    for timestamp, score in zip(timestamps[1:], values[1:], strict=True):
        current = float(timestamp)
        if active and float(score) < offset:
            if current > start:
                regions.append((start, current))
            start = current
            active = False
        elif not active and float(score) > onset:
            start = current
            active = True
    if active:
        final = float(timestamps[-1])
        if final > start:
            regions.append((start, final))
    if minimum_off_sec > 0.0 and regions:
        merged = [regions[0]]
        for left, right in regions[1:]:
            prior_left, prior_right = merged[-1]
            if left - prior_right <= minimum_off_sec:
                merged[-1] = (prior_left, max(prior_right, right))
            else:
                merged.append((left, right))
        regions = merged
    return [
        (left, right)
        for left, right in regions
        if right - left >= minimum_on_sec
    ]


def _build_engine(
    kind: str,
    component_id: str,
    *,
    h2_onnx_options: Mapping[str, object] | None = None,
) -> _Engine:
    if kind == "test":
        return _TestEngine(component_id)
    if kind == "speaker_embedding":
        return _SpeakerEmbeddingEngine(component_id)
    if kind == "pyannote_segmentation":
        return _PyannoteSegmentationEngine(component_id)
    if kind == "native_sherpa_asr":
        return _NativeSherpaEngine(component_id)
    if kind == "h2_portable_onnx":
        options = dict(h2_onnx_options or {})
        required = {
            "redimnet2_path",
            "segmentation_path",
            "redimnet2_sha256",
            "segmentation_sha256",
        }
        missing = sorted(required - set(options))
        if missing:
            raise WorkerMainError(f"H2 ONNX worker options are missing: {missing}")
        return _H2PortableOnnxEngine(
            component_id,
            redimnet2_path=Path(str(options["redimnet2_path"])),
            segmentation_path=Path(str(options["segmentation_path"])),
            redimnet2_sha256=str(options["redimnet2_sha256"]),
            segmentation_sha256=str(options["segmentation_sha256"]),
        )
    raise WorkerMainError(f"unsupported worker kind: {kind}")


def _verified_audio_path(payload: Mapping[str, object]) -> Path:
    value = payload.get("audio_path")
    if value is None or not str(value).strip():
        raise WorkerMainError("audio_path is required")
    path = Path(str(value)).expanduser().resolve()
    if not path.is_file():
        raise WorkerMainError(f"audio file does not exist: {path}")
    expected = payload.get("audio_sha256")
    if expected is not None and _sha256_file(path).lower() != str(expected).lower():
        raise WorkerMainError(f"audio SHA-256 mismatch: {path}")
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _emit(value: Mapping[str, object]) -> None:
    sys.stdout.write(json.dumps(dict(value), sort_keys=True, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def run_worker(
    *,
    worker_id: str,
    kind: str,
    component_id: str,
    h2_onnx_options: Mapping[str, object] | None = None,
) -> int:
    try:
        engine = _build_engine(
            kind, component_id, h2_onnx_options=h2_onnx_options
        )
    except Exception as exc:
        print(
            f"worker initialization failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    _emit(
        {
            "protocol": WORKER_PROTOCOL,
            "type": "ready",
            "worker_id": worker_id,
            "identity": engine.identity,
        }
    )
    for line in sys.stdin:
        request_id: object = None
        try:
            request = json.loads(line)
            if not isinstance(request, Mapping):
                raise WorkerMainError("request must be an object")
            request_id = request.get("request_id")
            if (
                request.get("protocol") != WORKER_PROTOCOL
                or request.get("type") != "request"
            ):
                raise WorkerMainError("request protocol mismatch")
            operation = str(request.get("operation") or "")
            payload = request.get("payload") or {}
            if not isinstance(payload, Mapping):
                raise WorkerMainError("request payload must be an object")
            if operation == "shutdown":
                _emit(
                    {
                        "protocol": WORKER_PROTOCOL,
                        "type": "response",
                        "request_id": request_id,
                        "ok": True,
                        "result": {"status": "SHUTTING_DOWN"},
                    }
                )
                return 0
            result = engine.execute(operation, payload)
            _emit(
                {
                    "protocol": WORKER_PROTOCOL,
                    "type": "response",
                    "request_id": request_id,
                    "ok": True,
                    "result": result,
                }
            )
        except Exception as exc:
            print(
                f"worker request failed: {type(exc).__name__}: {exc}", file=sys.stderr
            )
            _emit(
                {
                    "protocol": WORKER_PROTOCOL,
                    "type": "response",
                    "request_id": request_id,
                    "ok": False,
                    "error": {
                        "category": type(exc).__name__,
                        "message": str(exc)[:4000],
                    },
                }
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    _apply_process_seed()
    parser = argparse.ArgumentParser(
        description="Persistent full-pipeline component worker"
    )
    parser.add_argument("--worker-id", required=True)
    parser.add_argument(
        "--kind",
        choices=(
            "pyannote_segmentation",
            "speaker_embedding",
            "native_sherpa_asr",
            "h2_portable_onnx",
            "test",
        ),
        required=True,
    )
    parser.add_argument("--component", required=True)
    parser.add_argument("--h2-redim-onnx", type=Path)
    parser.add_argument("--h2-segmentation-onnx", type=Path)
    parser.add_argument("--h2-redim-sha256")
    parser.add_argument("--h2-segmentation-sha256")
    args = parser.parse_args(argv)
    h2_options = None
    if args.kind == "h2_portable_onnx":
        h2_options = {
            "redimnet2_path": args.h2_redim_onnx,
            "segmentation_path": args.h2_segmentation_onnx,
            "redimnet2_sha256": args.h2_redim_sha256,
            "segmentation_sha256": args.h2_segmentation_sha256,
        }
    return run_worker(
        worker_id=args.worker_id,
        kind=args.kind,
        component_id=args.component,
        h2_onnx_options=h2_options,
    )


def _apply_process_seed() -> None:
    raw = os.environ.get("JUST_PEACHY_EVALUATION_SEED")
    if raw is None:
        return
    seed = int(raw)
    if seed < 0:
        raise ValueError("JUST_PEACHY_EVALUATION_SEED must be non-negative")
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
