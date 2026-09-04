"""Command-line interface for the H2 streaming product demonstration app."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

from app.full_pipeline.factory import (
    DEFAULT_ENROLLMENT_ROOT,
    MATRIX_PATH,
    RUNTIME_CONFIG_PATH,
)
from app.full_pipeline.matrix import FullPipelineMatrix
from app.utils.paths import resolve_data_path_from_logical

from .devices import enumerate_input_devices
from .enrollment import (
    DEFAULT_ENROLLMENT_PROMPTS,
    LabelledWav,
    LocalEnrollmentService,
)
from .exports import export_session
from .h2_ux import (
    H2_DEFAULT_PRODUCT_MODE,
    H2_PRIMARY_PIPELINE_ID,
    H2_PRODUCT_MODE_IDS,
    require_h2_pipeline_id,
)
from .presets import PresetCatalog
from .session import DemoSessionManager, TERMINAL_STATES


EVALUATION_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEMO_RESULTS_ROOT = (
    EVALUATION_ROOT / "JustPeachyResults/full_pipeline/demo_sessions"
)
DEFAULT_SMOKE_AUDIO_LOGICAL = Path(
    "Raw Datasets (Not formatted)/CMU Arctic/cmu_us_aew_arctic/wav/arctic_a0281.wav"
)
DEFAULT_PIPELINE = H2_PRIMARY_PIPELINE_ID


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        value = _dispatch(args)
        if value is not None:
            print(json.dumps(value, indent=2, sort_keys=True, default=str))
        state = str((value or {}).get("state") or (value or {}).get("status") or "")
        return (
            1
            if state.casefold() in {"repeat_required", "invalid", "failed", "blocked"}
            else 0
        )
    except KeyboardInterrupt:
        print("Stopped by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Just-Peachy H2 streaming product demo"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    launch = sub.add_parser(
        "launch", help="Open the local Tkinter demonstration app"
    )
    _runtime_config_arguments(launch)
    presets = sub.add_parser("presets", help="List the AG-H2/AO-H2 product pair")
    presets.add_argument(
        "--all-matrix",
        action="store_true",
        help="Show the superseded 18-row research matrix for audit only",
    )
    sub.add_parser("devices", help="Enumerate local microphone input devices")

    file_parser = sub.add_parser(
        "file", help="Incrementally simulate the exact live path from a WAV"
    )
    _session_arguments(file_parser)
    file_parser.add_argument("--input", type=Path, required=True)
    file_parser.add_argument(
        "--pace",
        type=float,
        default=1.0,
        help="0=unpaced engineering mode, 1=real time, >1=accelerated",
    )
    file_parser.add_argument("--play-audio", action="store_true")
    file_parser.add_argument("--duration-sec", type=float)

    live = sub.add_parser("live", help="Run a bounded direct microphone session")
    _session_arguments(live)
    live.add_argument("--duration-sec", type=float, default=30.0)
    live.add_argument("--device")
    live.add_argument("--source-sample-rate-hz", type=int)
    live.add_argument("--source-channels", type=int)
    live.add_argument("--record-input-audio", action="store_true")

    enroll_import = sub.add_parser(
        "enroll-import",
        help="Create a local profile from the matrix-required labelled WAV count",
    )
    _enrollment_arguments(enroll_import)
    enroll_import.add_argument(
        "--wav",
        action="append",
        required=True,
        metavar="PROMPT_ID=PATH",
        help="Repeat once per labelled enrollment take",
    )

    enroll_record = sub.add_parser(
        "enroll-record", help="Record prompted local microphone samples"
    )
    _enrollment_arguments(enroll_record)
    enroll_record.add_argument("--device")
    enroll_record.add_argument("--source-sample-rate-hz", type=int)
    enroll_record.add_argument("--source-channels", type=int)

    profile_list = sub.add_parser(
        "profiles", help="List local active/archived profiles"
    )
    profile_list.add_argument(
        "--enrollment-root", type=Path, default=DEFAULT_ENROLLMENT_ROOT
    )

    remove = sub.add_parser(
        "profile-remove", help="Recoverably archive a local profile"
    )
    remove.add_argument("--profile-id", required=True)
    remove.add_argument("--reason", default="operator_removed")
    remove.add_argument("--enrollment-root", type=Path, default=DEFAULT_ENROLLMENT_ROOT)

    restore = sub.add_parser(
        "profile-restore", help="Restore a locally archived profile"
    )
    restore.add_argument("--profile-id", required=True)
    restore.add_argument("--archive-id")
    restore.add_argument(
        "--enrollment-root", type=Path, default=DEFAULT_ENROLLMENT_ROOT
    )

    rebuild = sub.add_parser("profile-rebuild", help="Replace a profile with new WAVs")
    rebuild.add_argument("--profile-id", required=True)
    rebuild.add_argument("--pipeline-id")
    rebuild.add_argument(
        "--enrollment-root", type=Path, default=DEFAULT_ENROLLMENT_ROOT
    )
    rebuild.add_argument(
        "--wav", action="append", required=True, metavar="PROMPT_ID=PATH"
    )

    export = sub.add_parser("export", help="Export a completed session locally")
    export.add_argument("--run-root", type=Path, required=True)
    export.add_argument("--export-root", type=Path, required=True)
    export.add_argument("--input-audio", type=Path)
    export.add_argument("--include-audio", action="store_true")

    smoke = sub.add_parser(
        "smoke",
        help="Run the retained pre-pivot bounded application regression smoke",
    )
    smoke.add_argument(
        "--input",
        type=Path,
        help=(
            "single-speaker WAV; defaults to the portable JP_DATA_ROOT CMU Arctic "
            "aew arctic_a0281 asset"
        ),
    )
    smoke.add_argument("--output-root", type=Path)
    smoke.add_argument("--no-telemetry", action="store_true")
    return parser


def _session_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pipeline-id",
        help="AG-H2 primary or AO-H2 fallback; defaults to AG-H2",
    )
    parser.add_argument("--results-root", type=Path, default=DEFAULT_DEMO_RESULTS_ROOT)
    parser.add_argument("--enrollment-root", type=Path, default=DEFAULT_ENROLLMENT_ROOT)
    parser.add_argument("--session-id")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--export-root", type=Path)
    parser.add_argument("--include-audio", action="store_true")
    parser.add_argument("--no-telemetry", action="store_true")
    parser.add_argument(
        "--product-mode",
        choices=H2_PRODUCT_MODE_IDS,
        help=(
            "H2 speaker-label behavior; omitted uses the checksum-bound "
            "binding default, or the non-final engineering baseline default"
        ),
    )
    _runtime_config_arguments(parser)


def _runtime_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--h2-runtime-config",
        type=Path,
        help=(
            "strict h2-demo-runtime-binding.v1 or frozen per-mode JSON; "
            "omitting it labels the session ENGINEERING_BASELINE_NOT_FINAL"
        ),
    )
    parser.add_argument(
        "--h2-runtime-config-sha256",
        help="optional expected SHA-256 of --h2-runtime-config",
    )


def _enrollment_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pipeline-id",
        help="AG-H2 primary or AO-H2 fallback; defaults to AG-H2",
    )
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--speaker-id")
    parser.add_argument("--enrollment-root", type=Path, default=DEFAULT_ENROLLMENT_ROOT)


def _dispatch(args: argparse.Namespace) -> dict[str, object] | None:
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    if hasattr(args, "pipeline_id") and args.pipeline_id is None:
        args.pipeline_id = PresetCatalog(matrix).default_h2_preset_id
    if args.command == "launch":
        from .ui import launch_demo

        launch_demo(
            runtime_config_path=args.h2_runtime_config,
            runtime_config_expected_sha256=args.h2_runtime_config_sha256,
        )
        return None
    if args.command == "presets":
        catalog = PresetCatalog(matrix)
        return catalog.payload() if args.all_matrix else catalog.h2_payload()
    if args.command == "devices":
        return {
            "schema_version": "full-pipeline-demo-devices.v1",
            "devices": [asdict(row) for row in enumerate_input_devices()],
        }
    if args.command in {"file", "live"}:
        require_h2_pipeline_id(args.pipeline_id)
        return _run_session_command(args)
    if args.command == "enroll-import":
        require_h2_pipeline_id(args.pipeline_id)
        labelled = _labelled_wavs(args.wav)
        _require_policy_take_count(matrix, args.pipeline_id, labelled)
        service = LocalEnrollmentService(
            matrix=matrix, enrollment_root=args.enrollment_root
        )
        return service.import_wavs(
            pipeline_id=args.pipeline_id,
            display_label=args.display_name,
            speaker_id=args.speaker_id,
            labelled_wavs=labelled,
        ).to_dict()
    if args.command == "enroll-record":
        require_h2_pipeline_id(args.pipeline_id)
        required = _required_take_count(matrix, args.pipeline_id)
        if required > len(DEFAULT_ENROLLMENT_PROMPTS):
            raise ValueError(
                f"matrix requires {required} enrollment prompts but only "
                f"{len(DEFAULT_ENROLLMENT_PROMPTS)} are configured"
            )
        service = LocalEnrollmentService(
            matrix=matrix, enrollment_root=args.enrollment_root
        )
        return service.record_profile(
            pipeline_id=args.pipeline_id,
            display_label=args.display_name,
            speaker_id=args.speaker_id,
            device=_device_value(args.device),
            source_sample_rate_hz=args.source_sample_rate_hz,
            source_channels=args.source_channels,
            prompts=DEFAULT_ENROLLMENT_PROMPTS[:required],
        ).to_dict()
    if args.command == "profiles":
        service = LocalEnrollmentService(
            matrix=matrix, enrollment_root=args.enrollment_root
        )
        return {
            "schema_version": "full-pipeline-demo-profile-list.v1",
            "profiles": [row.__dict__ for row in service.list_profiles()],
        }
    if args.command == "profile-remove":
        service = LocalEnrollmentService(
            matrix=matrix, enrollment_root=args.enrollment_root
        )
        return asdict(service.remove_profile(args.profile_id, reason=args.reason))
    if args.command == "profile-restore":
        service = LocalEnrollmentService(
            matrix=matrix, enrollment_root=args.enrollment_root
        )
        profile = service.restore_profile(args.profile_id, archive_id=args.archive_id)
        return {
            "schema_version": "full-pipeline-demo-profile-restored.v1",
            "profile_id": profile.profile_id,
            "profile_sha256": profile.profile_sha256,
            "speaker_id": profile.speaker_id,
            "display_label": profile.display_label,
            "backend_id": profile.backend_id,
            "backend_config_sha256": profile.backend_config_sha256,
            "model_id": profile.model_id,
            "model_sha256": profile.model_sha256,
            "aggregation_method": profile.aggregation_method,
            "profile_version": profile.profile_version,
            "state": profile.state,
            "biometric_vectors_inline": False,
        }
    if args.command == "profile-rebuild":
        require_h2_pipeline_id(args.pipeline_id)
        labelled = _labelled_wavs(args.wav)
        _require_policy_take_count(matrix, args.pipeline_id, labelled)
        service = LocalEnrollmentService(
            matrix=matrix, enrollment_root=args.enrollment_root
        )
        return service.rebuild_profile(
            profile_id=args.profile_id,
            pipeline_id=args.pipeline_id,
            labelled_wavs=labelled,
        ).to_dict()
    if args.command == "export":
        if args.include_audio and args.input_audio is None:
            raise ValueError("--include-audio requires --input-audio")
        return export_session(
            args.run_root,
            args.export_root,
            input_audio_path=args.input_audio if args.include_audio else None,
            authorize_input_audio=args.include_audio,
        )
    if args.command == "smoke":
        from .smoke import run_common_demo_smoke

        return run_common_demo_smoke(
            input_path=args.input or _default_smoke_audio_path(),
            output_root=args.output_root,
            telemetry_enabled=not args.no_telemetry,
        )
    raise ValueError(f"unsupported command: {args.command}")


def _default_smoke_audio_path() -> Path:
    """Resolve the strict smoke asset through the portable external data root."""

    return resolve_data_path_from_logical(DEFAULT_SMOKE_AUDIO_LOGICAL).resolve()


def _run_session_command(args: argparse.Namespace) -> dict[str, object]:
    args.pipeline_id = args.pipeline_id or DEFAULT_PIPELINE
    require_h2_pipeline_id(args.pipeline_id)
    if args.include_audio and args.export_root is None:
        raise ValueError("--include-audio requires --export-root")
    if args.command == "live" and args.include_audio and not args.record_input_audio:
        raise ValueError(
            "live --include-audio requires --record-input-audio so a local WAV exists"
        )
    manager = DemoSessionManager(
        results_root=args.results_root,
        enrollment_root=args.enrollment_root,
        runtime_config_path=args.h2_runtime_config,
        runtime_config_expected_sha256=args.h2_runtime_config_sha256,
    )
    product_mode = args.product_mode or getattr(
        manager, "default_product_mode", H2_DEFAULT_PRODUCT_MODE
    )
    try:
        if args.command == "file":
            status = manager.start_file(
                pipeline_id=args.pipeline_id,
                input_path=args.input,
                pace=args.pace,
                play_audio=args.play_audio,
                duration_sec=args.duration_sec,
                telemetry_enabled=not args.no_telemetry,
                product_mode=product_mode,
                session_id=args.session_id,
                output_root=args.output_root,
            )
        else:
            status = manager.start_microphone(
                pipeline_id=args.pipeline_id,
                duration_sec=args.duration_sec,
                device=_device_value(args.device),
                source_sample_rate_hz=args.source_sample_rate_hz,
                source_channels=args.source_channels,
                telemetry_enabled=not args.no_telemetry,
                record_input_audio=args.record_input_audio,
                product_mode=product_mode,
                session_id=args.session_id,
                output_root=args.output_root,
            )
        session_id = str(status["session_id"])
        status = _wait_for_session(manager, session_id)
        if args.export_root is not None and str(status["state"]) in TERMINAL_STATES:
            status = {
                **status,
                "session_export": manager.export(
                    args.export_root,
                    session_id=session_id,
                    include_input_audio=args.include_audio,
                ),
            }
        return status
    except KeyboardInterrupt:
        if manager.session_id is not None:
            manager.stop()
            manager.join(timeout=30)
        raise
    finally:
        manager.shutdown(timeout_per_session=30)


def _wait_for_session(
    manager: DemoSessionManager, session_id: str
) -> dict[str, object]:
    previous: tuple[object, ...] | None = None
    while True:
        status = manager.join(session_id, timeout=0.5)
        runtime = status.get("runtime_status")
        detail = runtime if isinstance(runtime, Mapping) else {}
        marker = (
            status.get("state"),
            detail.get("pipeline_state") or detail.get("state"),
            detail.get("audio_processed_sec"),
            detail.get("event_count"),
        )
        if marker != previous:
            print(
                "[DEMO] "
                f"state={marker[0]} runtime={marker[1]} "
                f"audio_sec={marker[2]} events={marker[3]}",
                file=sys.stderr,
                flush=True,
            )
            previous = marker
        if str(status["state"]) in TERMINAL_STATES:
            return manager.join(session_id)
        time.sleep(0.1)


def _labelled_wavs(values: Sequence[str]) -> tuple[LabelledWav, ...]:
    rows: list[LabelledWav] = []
    for value in values:
        prompt, separator, raw_path = value.partition("=")
        if not separator or not prompt.strip() or not raw_path.strip():
            raise ValueError(f"--wav must use PROMPT_ID=PATH: {value}")
        rows.append(LabelledWav(prompt.strip(), Path(raw_path.strip())))
    return tuple(rows)


def _required_take_count(matrix: FullPipelineMatrix, pipeline_id: str) -> int:
    count = int(matrix.resolve(pipeline_id).enrollment_policy["utterance_count"])
    if count < 1:
        raise ValueError("matrix enrollment utterance_count must be positive")
    return count


def _require_policy_take_count(
    matrix: FullPipelineMatrix,
    pipeline_id: str,
    labelled_wavs: Sequence[LabelledWav],
) -> None:
    required = _required_take_count(matrix, pipeline_id)
    if len(labelled_wavs) != required:
        raise ValueError(
            f"pipeline {pipeline_id} requires exactly {required} labelled WAVs; "
            f"received {len(labelled_wavs)}"
        )
    prompt_ids = [row.prompt_id for row in labelled_wavs]
    if len(set(prompt_ids)) != required:
        raise ValueError("labelled enrollment prompt IDs must be unique")


def _device_value(value: object) -> int | str | None:
    if value is None:
        return None
    text = str(value).strip()
    return int(text) if text.lstrip("-").isdigit() else text


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
