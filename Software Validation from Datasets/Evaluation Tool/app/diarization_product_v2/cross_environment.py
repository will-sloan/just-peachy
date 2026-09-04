"""Checksum-bound Pyannote segmentation shared across isolated embedders.

This bridge intentionally passes anonymous time windows only.  It never loads
an enrollment database and never produces a known-person label.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Mapping
import uuid

import numpy as np
import yaml

from app.controlled_diarization.contracts import (
    TOOL_ROOT,
    ControlledDiarizationError,
    PipelineDefinition,
    canonical_json,
    sha256_file,
    sha256_text,
)
from app.diarization_evaluation.artifacts import write_json_atomic
from app.diarization_evaluation.formats import RttmTurn


SEGMENTATION_SCHEMA = "diarization-product-segmentation-cache.v1"
WINDOW_POLICY = {
    "window_duration_sec": 1.5,
    "window_step_sec": 0.75,
    "minimum_window_sec": 0.75,
    "assignment_policy": "midpoint_partition_within_merged_speech_region",
}


def cross_environment_predictions(
    *,
    audio_path: Path,
    audio_sha256: str,
    recording_id: str,
    duration_sec: float,
    pipeline: PipelineDefinition,
    output_root: Path,
    oracle_speaker_count: int | None,
) -> tuple[list[RttmTurn], dict[str, object]]:
    """Run/reuse segmentation, extract embeddings, and cluster anonymously."""

    backend = str(pipeline.configuration.get("embedding_backend") or pipeline.component_name or "")
    if backend not in {
        "wespeaker",
        "redimnet2_b2_speaker_embedding",
        "speechbrain_ecapa",
    }:
        raise ControlledDiarizationError(f"unsupported Product V2 embedding backend: {backend}")
    cache_root = _shared_cache_root(output_root)
    segmentation = _ensure_segmentation(
        audio_path=audio_path,
        audio_sha256=audio_sha256,
        recording_id=recording_id,
        duration_sec=duration_sec,
        cache_root=cache_root,
    )
    windows = list(segmentation["windows"])
    jobs = _embedding_jobs(
        windows=windows,
        audio_path=audio_path,
        audio_sha256=audio_sha256,
        recording_id=recording_id,
        segmentation_identity=str(segmentation["segmentation_identity"]),
    )
    extraction = _invoke_embedding_worker(backend, jobs, cache_root / "embeddings")
    entries = {str(row["job_id"]): row for row in extraction["cache_entries"]}
    vectors: list[tuple[float, ...]] = []
    valid_windows: list[Mapping[str, object]] = []
    invalid: list[dict[str, object]] = []
    for job, window in zip(jobs, windows, strict=True):
        entry = entries[str(job["job_id"])]
        cached = json.loads(
            (cache_root / "embeddings" / backend / str(entry["filename"])).read_text(
                encoding="utf-8"
            )
        )
        if cached.get("status") != "ok":
            invalid.append(
                {
                    "job_id": job["job_id"],
                    "status": cached.get("status"),
                    "duration_sec": cached.get("duration_sec"),
                    "classification": "TECHNICALLY_INVALID",
                }
            )
            continue
        vector = tuple(float(value) for value in cached["vector"])
        if not vector or not all(np.isfinite(value) for value in vector):
            raise ControlledDiarizationError("embedding cache returned an invalid successful vector")
        vectors.append(vector)
        valid_windows.append(window)

    if vectors:
        from app.inference_pipeline.diarization.clustering import (
            agglomerative_cosine_labels,
        )
        from app.inference_pipeline.diarization.modular_adapter import (
            _merge_adjacent_turns,
        )
        from app.inference_pipeline.diarization.base import SpeakerTurnRegion

        threshold = float(pipeline.configuration.get("clustering_threshold", 0.5))
        labels = agglomerative_cosine_labels(
            vectors,
            threshold=threshold,
            min_clusters=oracle_speaker_count or 1,
            max_clusters=oracle_speaker_count,
        )
        regions = _merge_adjacent_turns(
            [
                SpeakerTurnRegion(
                    start_sec=float(window["assignment_start_sec"]),
                    end_sec=float(window["assignment_end_sec"]),
                    speaker_turn_label=f"speaker_{int(label):02d}",
                    source=(
                        "diarization_product_v2:pyannote_segmentation_3_0:"
                        f"{backend}"
                    ),
                )
                for window, label in zip(valid_windows, labels, strict=True)
            ],
            min_turn_sec=0.05,
        )
        turns = [
            RttmTurn(
                recording_id=recording_id,
                channel="1",
                start_sec=float(region.start_sec),
                end_sec=float(region.end_sec),
                speaker_label=str(region.speaker_turn_label),
            )
            for region in regions
        ]
    else:
        threshold = float(pipeline.configuration.get("clustering_threshold", 0.5))
        labels = []
        turns = []

    technical = {
        "schema_version": "diarization-product-technical-coverage.v1",
        "recording_id": recording_id,
        "backend_id": backend,
        "planned_windows": len(windows),
        "valid_windows": len(valid_windows),
        "technically_invalid_windows": len(invalid),
        "technical_coverage": len(valid_windows) / len(windows) if windows else 0.0,
        "invalid": invalid,
        "segmentation_cache_reused": bool(segmentation["cache_reused"]),
    }
    write_json_atomic(output_root / "diagnostics" / "technical_coverage.json", technical)
    identity = {
        "schema_version": "diarization-product-cross-environment-pipeline.v1",
        **pipeline.to_jsonable(),
        "implementation_class": "CrossEnvironmentPyannoteEmbeddingClustering",
        "segmentation_identity": segmentation["segmentation_identity"],
        "segmentation_config": segmentation["segmentation_config"],
        "segmentation_cache_sha256": segmentation["manifest_sha256"],
        "window_policy": WINDOW_POLICY,
        "embedding_backend_identity": extraction.get("backend_identity"),
        "embedding_declared_identity_hash": extraction.get(
            "declared_backend_identity_hash"
        ),
        "clustering": {
            "family": "agglomerative_cosine",
            "threshold": threshold,
            "speaker_count_mode": "oracle_diagnostic" if oracle_speaker_count else "estimated",
        },
        "anonymous_labels_only": True,
        "known_speaker_attribution_performed": False,
        "implicit_model_downloads_allowed": False,
        "technical_coverage": technical,
    }
    return turns, identity


def _shared_cache_root(output_root: Path) -> Path:
    configured = os.environ.get("JP_DIARIZATION_SHARED_CACHE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    # output_root is normally <result>/<tier>/<pipeline>/<case-attempt>.
    try:
        result_root = output_root.resolve().parents[2]
    except IndexError:  # pragma: no cover - defensive only
        result_root = output_root.resolve().parent
    return result_root / "_shared_cache"


def _segmentation_config() -> dict[str, object]:
    source = (
        TOOL_ROOT
        / "configs"
        / "inference"
        / "components"
        / "diarization"
        / "modular_pyannote_campplus.yaml"
    )
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    params = dict(dict(payload["component"])["params"])
    return {
        "source_config_path": source.relative_to(TOOL_ROOT).as_posix(),
        "source_config_sha256": sha256_file(source),
        "segmentation_source": params["segmentation_source"],
        "segmentation_model_path": params["segmentation_model_path"],
        "segmentation_onset": params["segmentation_onset"],
        "segmentation_offset": params["segmentation_offset"],
        "segmentation_min_duration_on": params["segmentation_min_duration_on"],
        "segmentation_min_duration_off": params["segmentation_min_duration_off"],
        **WINDOW_POLICY,
    }


def _ensure_segmentation(
    *,
    audio_path: Path,
    audio_sha256: str,
    recording_id: str,
    duration_sec: float,
    cache_root: Path,
) -> dict[str, object]:
    config = _segmentation_config()
    identity = sha256_text(
        canonical_json(
            {
                "schema_version": SEGMENTATION_SCHEMA,
                "audio_sha256": audio_sha256.lower(),
                "duration_sec": duration_sec,
                "segmentation_config": config,
            }
        )
    )
    path = cache_root / "segmentation" / f"{identity}.json"
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("schema_version") == SEGMENTATION_SCHEMA
            and payload.get("segmentation_identity") == identity
            and payload.get("audio_sha256") == audio_sha256.lower()
        ):
            payload["cache_reused"] = True
            payload["manifest_sha256"] = sha256_file(path)
            return payload
    from app.controlled_diarization.runner import interpreter_for_profile

    interpreter = interpreter_for_profile("credential-diarization")
    if interpreter is None or not interpreter.is_file():
        raise ControlledDiarizationError("credential-diarization environment is unavailable")
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            str(interpreter),
            "-m",
            "app.diarization_product_v2.cross_environment",
            "segment",
            "--audio",
            str(audio_path),
            "--audio-sha256",
            audio_sha256,
            "--recording-id",
            recording_id,
            "--duration-sec",
            str(duration_sec),
            "--identity",
            identity,
            "--output",
            str(path),
        ],
        cwd=TOOL_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise ControlledDiarizationError(
            "Pyannote segmentation worker failed: "
            + (completed.stderr or completed.stdout)[-4000:]
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("segmentation_identity") != identity:
        raise ControlledDiarizationError("segmentation worker identity mismatch")
    payload["cache_reused"] = False
    payload["manifest_sha256"] = sha256_file(path)
    return payload


def _segment_worker(args: argparse.Namespace) -> int:
    from app.inference_pipeline.audio_io.loader import load_audio
    from app.inference_pipeline.diarization.modular_adapter import (
        ModularClusteringDiarizer,
        _embedding_windows,
    )

    audio_path = args.audio.resolve()
    if sha256_file(audio_path).lower() != args.audio_sha256.lower():
        raise ControlledDiarizationError("segmentation source audio hash mismatch")
    audio = load_audio(
        {
            "recording_id": args.recording_id,
            "source_recording_id": args.recording_id,
            "utt_id": args.recording_id,
            "inference_audio_path": str(audio_path),
            "start_sec": 0.0,
            "end_sec": args.duration_sec,
            "duration_sec": args.duration_sec,
        },
        {"runtime": {"sample_rate_hz": 16000}, "audio": {"channel_policy": "mono"}},
    )
    config = _segmentation_config()
    # The embedder config is required by constructor validation but is never
    # loaded: this worker calls only the segmentation stage.
    params = {
        **config,
        "embedding_component_config": (
            "configs/inference/components/speaker_embedding/campplus.yaml"
        ),
        "clustering_policy_id": "diarization_product_v2_segmentation_only",
        "clustering_threshold": 0.5,
        "device": "cpu",
        "allow_model_downloads": False,
    }
    started = time.perf_counter()
    diarizer = ModularClusteringDiarizer(params)
    regions = diarizer._speech_regions(audio)
    windows = [
        window
        for region in regions
        for window in _embedding_windows(
            region,
            duration_sec=float(WINDOW_POLICY["window_duration_sec"]),
            step_sec=float(WINDOW_POLICY["window_step_sec"]),
            minimum_sec=float(WINDOW_POLICY["minimum_window_sec"]),
        )
    ]
    payload = {
        "schema_version": SEGMENTATION_SCHEMA,
        "segmentation_identity": args.identity,
        "recording_id": args.recording_id,
        "audio_sha256": args.audio_sha256.lower(),
        "duration_sec": args.duration_sec,
        "segmentation_config": config,
        "speech_regions": [
            {"start_sec": float(row.start_sec), "end_sec": float(row.end_sec)}
            for row in regions
        ],
        "windows": [
            {
                "window_index": index,
                "start_sec": float(row.start_sec),
                "end_sec": float(row.end_sec),
                "assignment_start_sec": float(row.assignment_start_sec),
                "assignment_end_sec": float(row.assignment_end_sec),
            }
            for index, row in enumerate(windows)
        ],
        "segmentation_inference_sec": time.perf_counter() - started,
        "known_speaker_attribution_performed": False,
    }
    write_json_atomic(args.output, payload)
    return 0


def _embedding_jobs(
    *,
    windows: list[Mapping[str, object]],
    audio_path: Path,
    audio_sha256: str,
    recording_id: str,
    segmentation_identity: str,
) -> list[dict[str, object]]:
    from app.hybrid_speaker_attribution.embedding_cache import embedding_job

    return [
        embedding_job(
            job_id=f"dprod_{segmentation_identity[:16]}_{int(window['window_index']):06d}",
            audio_path=audio_path,
            audio_sha256=audio_sha256,
            start_sec=float(window["start_sec"]),
            end_sec=float(window["end_sec"]),
            role="anonymous_diarization_window",
            metadata={
                "recording_id": recording_id,
                "segmentation_identity": segmentation_identity,
                "assignment_start_sec": window["assignment_start_sec"],
                "assignment_end_sec": window["assignment_end_sec"],
            },
        )
        for window in windows
    ]


def _invoke_embedding_worker(
    backend: str, jobs: list[Mapping[str, object]], cache_root: Path
) -> dict[str, object]:
    from app.controlled_diarization.runner import interpreter_for_profile
    from app.speaker_protocol.contracts import eligible_embedding_backends

    eligible = eligible_embedding_backends(backend_ids={backend})
    if backend not in eligible:
        raise ControlledDiarizationError(f"embedding backend is not qualified: {backend}")
    profile = str(eligible[backend]["environment_profile"])
    interpreter = interpreter_for_profile(profile)
    if interpreter is None or not interpreter.is_file():
        raise ControlledDiarizationError(f"embedding environment is unavailable: {profile}")
    cache_root.mkdir(parents=True, exist_ok=True)
    manifest = cache_root / f".{backend}_{uuid.uuid4().hex[:8]}.jsonl"
    manifest.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in jobs),
        encoding="utf-8",
        newline="\n",
    )
    try:
        completed = subprocess.run(
            [
                str(interpreter),
                "-m",
                "app.hybrid_speaker_attribution.embedding_cache",
                "--backend",
                backend,
                "--jobs",
                str(manifest),
                "--cache-root",
                str(cache_root),
            ],
            cwd=TOOL_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode:
            raise ControlledDiarizationError(
                f"embedding worker failed ({completed.returncode}): "
                + (completed.stderr or completed.stdout)[-4000:]
            )
        return json.loads(
            (cache_root / backend / "extraction_summary.json").read_text(
                encoding="utf-8"
            )
        )
    finally:
        manifest.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    segment = commands.add_parser("segment")
    segment.add_argument("--audio", type=Path, required=True)
    segment.add_argument("--audio-sha256", required=True)
    segment.add_argument("--recording-id", required=True)
    segment.add_argument("--duration-sec", type=float, required=True)
    segment.add_argument("--identity", required=True)
    segment.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "segment":
        return _segment_worker(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
