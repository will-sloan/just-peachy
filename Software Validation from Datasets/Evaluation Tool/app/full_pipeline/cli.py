"""Command-line entry points for bounded streaming runtime operations."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Sequence
import uuid

from .matrix import FullPipelineMatrix


EVALUATION_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = (
    EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
)
RUNTIME_CONFIG_PATH = (
    EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml"
)
DEFAULT_RESULTS_ROOT = (
    EVALUATION_ROOT / "JustPeachyResults/full_pipeline/runtime_sessions"
)


DEFAULT_SMOKE_AUDIO = (
    EVALUATION_ROOT
    / "artifacts/realtime_test_audio/aew_rxr_eey_arctic_a0301_concat.wav"
)
DEFAULT_PIPELINE = "fullpipe_v1_ao_dr_ir"


def new_session_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"fullpipe_session_{timestamp}_{uuid.uuid4().hex[:10]}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "status":
            value = runtime_status(Path(args.output_root) if args.output_root else None)
        elif args.command == "file-smoke":
            value = run_file_smoke(args)
        elif args.command == "microphone-smoke":
            value = run_microphone_smoke(args)
        elif args.command == "enrollment-smoke":
            value = run_enrollment_smoke(args)
        elif args.command == "component-smoke":
            value = run_component_smoke(args)
        elif args.command == "matrix-status":
            value = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH).status()
        else:  # pragma: no cover - argparse owns this boundary
            raise ValueError(f"unsupported command: {args.command}")
        print(json.dumps(value, indent=2, sort_keys=True))
        status = str(
            value.get("status")
            or value.get("completion_state")
            or value.get("state")
            or ""
        )
        return 0 if status not in {"FAILED", "failed"} else 1
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}, indent=2
            ),
            file=sys.stderr,
        )
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Just-Peachy true streaming full-pipeline runtime"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    file_parser = sub.add_parser(
        "file-smoke", help="Run one bounded incremental file stream"
    )
    file_parser.add_argument("--pipeline-id", default=DEFAULT_PIPELINE)
    file_parser.add_argument("--input", type=Path, default=DEFAULT_SMOKE_AUDIO)
    file_parser.add_argument("--output-root", type=Path)
    file_parser.add_argument("--enrollment-root", type=Path)
    file_parser.add_argument("--session-id")
    file_parser.add_argument("--duration-sec", type=float)
    file_parser.add_argument("--realtime", action="store_true")
    file_parser.add_argument("--no-telemetry", action="store_true")

    mic_parser = sub.add_parser(
        "microphone-smoke", help="Run a bounded microphone stream"
    )
    mic_parser.add_argument("--pipeline-id", default=DEFAULT_PIPELINE)
    mic_parser.add_argument("--duration-sec", type=float, default=10.0)
    mic_parser.add_argument("--output-root", type=Path)
    mic_parser.add_argument("--enrollment-root", type=Path)
    mic_parser.add_argument("--session-id")
    mic_parser.add_argument("--device")
    mic_parser.add_argument("--source-sample-rate-hz", type=int)
    mic_parser.add_argument("--source-channels", type=int)
    mic_parser.add_argument("--no-telemetry", action="store_true")

    enrollment = sub.add_parser(
        "enrollment-smoke", help="Create checksum-bound test profiles"
    )
    enrollment.add_argument(
        "--backend",
        action="append",
        choices=("wespeaker", "redimnet2_b2_speaker_embedding", "speechbrain_ecapa"),
    )
    enrollment.add_argument("--input", type=Path, default=DEFAULT_SMOKE_AUDIO)
    enrollment.add_argument("--output-root", type=Path)

    components = sub.add_parser(
        "component-smoke", help="Bounded smoke for 2+3+3 components"
    )
    components.add_argument("--input", type=Path, default=DEFAULT_SMOKE_AUDIO)
    components.add_argument("--output-root", type=Path)
    components.add_argument("--duration-sec", type=float)
    components.add_argument("--no-telemetry", action="store_true")

    status = sub.add_parser(
        "status", help="Read latest or named runtime status without models"
    )
    status.add_argument("--output-root", type=Path)
    sub.add_parser("matrix-status", help="List the locked 18 pipeline identities")
    return parser


def run_file_smoke(args: argparse.Namespace) -> dict[str, object]:
    from .factory import build_file_runtime

    session_id = args.session_id or new_session_id()
    output = args.output_root or (DEFAULT_RESULTS_ROOT / session_id)
    runtime = build_file_runtime(
        pipeline_id=args.pipeline_id,
        input_path=args.input,
        output_root=output,
        enrollment_root=args.enrollment_root,
        session_id=session_id,
        realtime=args.realtime,
        duration_sec=args.duration_sec,
        telemetry_enabled=not args.no_telemetry,
    )
    result = dict(runtime.run())
    result["output_root"] = str(Path(output).resolve())
    return result


def run_microphone_smoke(args: argparse.Namespace) -> dict[str, object]:
    from .factory import build_microphone_runtime

    session_id = args.session_id or new_session_id()
    output = args.output_root or (DEFAULT_RESULTS_ROOT / session_id)
    if args.duration_sec <= 0:
        raise ValueError("microphone smoke duration must be positive")
    device: int | str | None = args.device
    if isinstance(device, str) and device.strip().lstrip("-").isdigit():
        device = int(device)
    runtime = build_microphone_runtime(
        pipeline_id=args.pipeline_id,
        duration_sec=args.duration_sec,
        output_root=output,
        enrollment_root=args.enrollment_root,
        session_id=session_id,
        device=device,
        source_sample_rate_hz=args.source_sample_rate_hz,
        source_channels=args.source_channels,
        telemetry_enabled=not args.no_telemetry,
    )
    result = dict(runtime.run())
    result["output_root"] = str(Path(output).resolve())
    return result


def run_enrollment_smoke(args: argparse.Namespace) -> dict[str, object]:
    import numpy as np
    import soundfile as sf

    from app.inference_pipeline.audio_io.resample import resample_audio

    from .enrollment import (
        EnrollmentTemplate,
        ProtectedEnrollmentStore,
        export_public_enrollment_contracts,
    )
    from .cache import ContentAddressedCache
    from .models import EmbeddingWindow
    from .runtime_components import WorkerEmbeddingAdapter
    from .workers import PersistentWorker, embedding_worker_spec

    backends = args.backend or ["redimnet2_b2_speaker_embedding"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (
        Path(args.output_root).resolve()
        if args.output_root
        else (
            EVALUATION_ROOT
            / f"JustPeachyResults/full_pipeline/enrollment_smoke/{stamp}"
        )
    )
    store = ProtectedEnrollmentStore(root / "protected_store")
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    audio, rate = sf.read(Path(args.input), dtype="float32", always_2d=True)
    mono = np.mean(audio, axis=1, keepdims=True, dtype=np.float32)
    mono = resample_audio(mono, int(rate), 16000)[:, 0]
    # Repeat one bounded segment so a functional profile smoke cannot silently
    # enroll the three different speakers in the concatenated fixture.  This is
    # deliberately not a diversity or production-enrollment qualification.
    segments = ((0.0, 2.5), (0.0, 2.5), (0.0, 2.5))
    rows = []
    for backend_id in backends:
        axis = _axis_for_backend(matrix, backend_id)
        worker = PersistentWorker(
            embedding_worker_spec(
                backend_id, worker_id=f"enrollment-smoke-{backend_id}"
            )
        )
        adapter = WorkerEmbeddingAdapter(
            worker=worker,
            work_root=root / "runtime_work",
            backend_config_sha256=str(axis["config_sha256"]),
            model_id=str(axis["model_id"]),
            model_sha256=str(axis["model_identity_sha256"]),
            cache=ContentAddressedCache(
                EVALUATION_ROOT / "JustPeachyResults/full_pipeline/_shared_cache"
            ),
        )
        templates = []
        try:
            adapter.start("enrollment-smoke")
            for index, (start, end) in enumerate(segments):
                samples = mono[round(start * 16000) : round(end * 16000)]
                result = adapter.embed(
                    EmbeddingWindow(
                        window_id=f"enrollment_{index + 1}",
                        start_sec=start,
                        end_sec=end,
                        assignment_start_sec=start,
                        assignment_end_sec=end,
                        samples=samples,
                        role="enrollment_embedding",
                    )
                )
                templates.append(
                    EnrollmentTemplate(
                        sample_id=f"{backend_id}_smoke_sample_{index + 1}",
                        vector=result.vector,
                        duration_sec=end - start,
                        audio_sha256=hashlib.sha256(
                            np.ascontiguousarray(samples).tobytes()
                        ).hexdigest(),
                        quality={"status": "accepted", "smoke_only": True},
                    )
                )
        finally:
            adapter.close()
        policy = _enrollment_policy_for_backend(matrix, backend_id)
        profile = store.create_profile(
            profile_id=f"smoke_profile_{backend_id}_{stamp}",
            speaker_id=f"smoke_speaker_{backend_id}",
            display_label="Smoke Speaker",
            backend_id=backend_id,
            backend_config_sha256=str(axis["config_sha256"]),
            model_id=str(axis["model_id"]),
            model_sha256=str(axis["model_identity_sha256"]),
            aggregation_method=str(policy["aggregation"]),
            templates=templates,
        )
        public_contracts = export_public_enrollment_contracts(
            output_root=root,
            profile=profile,
            backend_axis=axis,
            enrollment_policy=policy,
            runtime_config_sha256=matrix.resolve(
                DEFAULT_PIPELINE
            ).runtime_config_sha256,
            source_audio_path=Path(args.input),
            sample_ranges_sec=segments,
        )
        rows.append(
            {
                "backend_id": backend_id,
                "profile_id": profile.profile_id,
                "profile_sha256": profile.profile_sha256,
                "template_sha256": profile.template_sha256,
                "template_count": len(profile.templates),
                "aggregation": profile.aggregation_method,
                "within_enrollment_consistency": profile.within_enrollment_consistency,
                **public_contracts,
                "status": "PASS",
            }
        )
    result = {
        "schema_version": "full-pipeline-enrollment-smoke.v1",
        "status": "PASS",
        "input": str(Path(args.input).resolve()),
        "output_root": str(root),
        "backends": rows,
        "profiles_are_smoke_only": True,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "enrollment_smoke.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def run_component_smoke(args: argparse.Namespace) -> dict[str, object]:
    from .factory import build_file_runtime

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (
        Path(args.output_root).resolve()
        if args.output_root
        else (
            EVALUATION_ROOT / f"JustPeachyResults/full_pipeline/component_smoke/{stamp}"
        )
    )
    selections = (
        "fullpipe_v1_ao_dw_iw",
        "fullpipe_v1_ag_dr_ir",
        "fullpipe_v1_ao_de_ie",
    )
    rows = []
    for index, pipeline_id in enumerate(selections, start=1):
        session_id = f"component_smoke_{stamp}_{index}"
        output = root / pipeline_id
        runtime = build_file_runtime(
            pipeline_id=pipeline_id,
            input_path=args.input,
            output_root=output,
            enrollment_root=root / "_empty_enrollment",
            session_id=session_id,
            duration_sec=args.duration_sec,
            telemetry_enabled=not args.no_telemetry,
            cache_root=root / "_isolated_component_cache",
        )
        result = dict(runtime.run())
        rows.append(
            {
                "pipeline_id": pipeline_id,
                "completion_state": result["completion_state"],
                "output_root": str(output),
                "errors": result["errors"],
            }
        )
        if result["completion_state"] != "complete":
            break
    complete = len(rows) == len(selections) and all(
        row["completion_state"] == "complete" for row in rows
    )
    result = {
        "schema_version": "full-pipeline-component-smoke.v1",
        "status": "PASS" if complete else "FAILED",
        "bounded": True,
        "scientific_campaign": False,
        "expected_components": {
            "asr": ["sherpa_onnx", "sherpa_onnx_libri_giga_zipformer_2023_06_21"],
            "diarization": [
                "modular_pyannote_wespeaker",
                "modular_pyannote_redimnet2",
                "modular_pyannote_speechbrain_ecapa",
            ],
            "identity": [
                "wespeaker",
                "redimnet2_b2_speaker_embedding",
                "speechbrain_ecapa",
            ],
        },
        "runs": rows,
        "output_root": str(root),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "component_smoke.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def runtime_status(output_root: Path | None) -> dict[str, object]:
    if output_root is not None:
        status_path = output_root.resolve() / "status.json"
        if not status_path.is_file():
            return {
                "schema_version": "full-pipeline-runtime-status.v1",
                "status": "NOT_FOUND",
                "path": str(status_path),
            }
        return json.loads(status_path.read_text(encoding="utf-8"))
    if not DEFAULT_RESULTS_ROOT.is_dir():
        return {
            "schema_version": "full-pipeline-runtime-status.v1",
            "status": "NO_SESSIONS",
            "root": str(DEFAULT_RESULTS_ROOT),
        }
    candidates = sorted(
        DEFAULT_RESULTS_ROOT.glob("*/status.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if not candidates:
        return {
            "schema_version": "full-pipeline-runtime-status.v1",
            "status": "NO_SESSIONS",
            "root": str(DEFAULT_RESULTS_ROOT),
        }
    value = json.loads(candidates[0].read_text(encoding="utf-8"))
    return {**value, "status_path": str(candidates[0])}


def _axis_for_backend(matrix: FullPipelineMatrix, backend_id: str) -> dict[str, object]:
    for value in matrix.matrix["axes"]["identity"].values():
        if value["backend_id"] == backend_id:
            return dict(value)
    raise KeyError(backend_id)


def _enrollment_policy_for_backend(
    matrix: FullPipelineMatrix, backend_id: str
) -> dict[str, object]:
    axes = matrix.matrix["axes"]["identity"]
    policies = matrix.matrix["policies"]["enrollment"]
    for alias, value in axes.items():
        if value["backend_id"] == backend_id:
            return dict(policies[alias])
    raise KeyError(backend_id)
