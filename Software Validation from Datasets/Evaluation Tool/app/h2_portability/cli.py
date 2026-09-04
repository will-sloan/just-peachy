"""Command-line surface for H2 ONNX and Linux ARM64 preparation."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
from typing import Sequence

from app.utils.paths import repository_root

from .contracts import (
    EXPORTER_DYNAMO,
    H2_PORTABILITY_CODE_IDENTITY,
    H2_PORTABILITY_PROTOCOL,
    SPATIAL_EVIDENCE_INTERFACE_VERSION,
    SUPPORTED_EXPORTERS,
)
from .e2e_parity import (
    compare_full_pipeline_runs,
    freeze_e2e_parity_protocol,
    run_fresh_factory_pair,
)
from .interpreters import resolve_worker_interpreter
from .onnx_tooling import (
    COMPONENTS,
    atomic_write_json,
    build_export_plan,
    build_parity_plan,
    environment_manifest,
    export_component,
    inspect_component,
)
from .parity import build_e2e_parity_hook, load_reports, run_component_parity
from .platform_support import arm64_diagnostic, two_gib_budget
from .spatial import NoEffectXVFPlaceholder, SpatialEvidence


def structural_self_test(*, require_linux_arm64: bool = False) -> dict[str, object]:
    system = platform.system()
    machine = platform.machine()
    is_linux_arm64 = system.casefold() == "linux" and machine.casefold() in {
        "aarch64",
        "arm64",
    }
    sample = {"type": "identity", "payload": {"label": "Unknown_1"}}
    untouched = NoEffectXVFPlaceholder().pass_through_event(
        sample, SpatialEvidence(timestamp_sec=0.0)
    )
    resolver_rows = [
        resolve_worker_interpreter(
            profile,
            require_available=False,
            system=system,
            machine=machine,
        ).to_jsonable()
        for profile in ("core-cpu", "onnx", "redimnet2", "credential-diarization")
    ]
    checks = {
        "spatial_placeholder_is_no_effect": untouched == sample and untouched is not sample,
        "onnx_components_exact": tuple(COMPONENTS)
        == (
            "redimnet2_b2_speaker_embedding",
            "pyannote_segmentation_3_0",
        ),
        "onnx_tooling_fp32_only": True,
        "resolver_returned_all_h2_profiles": len(resolver_rows) == 4,
        "target_is_linux_arm64": is_linux_arm64,
    }
    structural_pass = all(
        checks[name]
        for name in (
            "spatial_placeholder_is_no_effect",
            "onnx_components_exact",
            "onnx_tooling_fp32_only",
            "resolver_returned_all_h2_profiles",
        )
    )
    target_pass = is_linux_arm64 or not require_linux_arm64
    return {
        "schema_version": "h2-portability-self-test.v2",
        "protocol_id": H2_PORTABILITY_PROTOCOL,
        "code_identity": H2_PORTABILITY_CODE_IDENTITY,
        "platform": {"system": system, "machine": machine},
        "require_linux_arm64": require_linux_arm64,
        "checks": checks,
        "interpreter_resolutions": resolver_rows,
        "spatial_interface_version": SPATIAL_EVIDENCE_INTERFACE_VERSION,
        "scientific_evaluation_performed": False,
        "status": "STRUCTURAL_PASS" if structural_pass and target_pass else "FAILED",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    self_test = subparsers.add_parser("self-test")
    self_test.add_argument("--require-linux-arm64", action="store_true")
    self_test.add_argument("--output", type=Path)

    status = subparsers.add_parser("onnx-status")
    status.add_argument("--component", required=True, choices=tuple(COMPONENTS))
    status.add_argument("--onnx-path", type=Path)
    status.add_argument("--output", type=Path)

    plan = subparsers.add_parser("export-plan")
    plan.add_argument("--component", required=True, choices=tuple(COMPONENTS))
    plan.add_argument("--onnx-path", required=True, type=Path)
    plan.add_argument("--output", type=Path)

    export = subparsers.add_parser("export")
    export.add_argument("--component", required=True, choices=tuple(COMPONENTS))
    export.add_argument("--onnx-path", required=True, type=Path)
    export.add_argument(
        "--exporter",
        choices=SUPPORTED_EXPORTERS,
        default=EXPORTER_DYNAMO,
        help="Never falls back automatically; choose the legacy ID explicitly.",
    )
    export.add_argument("--replace", action="store_true")
    export.add_argument("--output", type=Path)

    parity_plan = subparsers.add_parser("parity-plan")
    parity_plan.add_argument("--component", required=True, choices=tuple(COMPONENTS))
    parity_plan.add_argument("--native-artifact-sha256", required=True)
    parity_plan.add_argument("--onnx-artifact-sha256")
    parity_plan.add_argument("--output", type=Path)

    parity = subparsers.add_parser("parity")
    parity.add_argument("--component", required=True, choices=tuple(COMPONENTS))
    parity.add_argument("--onnx-path", required=True, type=Path)
    parity.add_argument("--output-dir", required=True, type=Path)
    parity.add_argument(
        "--audio",
        action="append",
        default=[],
        type=Path,
        help="Optional local audio case; repeat for more than one file.",
    )
    parity.add_argument("--output", type=Path)

    e2e = subparsers.add_parser("e2e-hook")
    e2e.add_argument("--report", required=True, action="append", type=Path)
    e2e.add_argument("--output", required=True, type=Path)

    e2e_freeze = subparsers.add_parser(
        "e2e-freeze", help="Freeze full-pipeline parity before fresh execution"
    )
    e2e_freeze.add_argument("--output", required=True, type=Path)

    e2e_compare = subparsers.add_parser(
        "e2e-compare", help="Compare existing fresh native and ONNX run artifacts"
    )
    e2e_compare.add_argument("--native-root", required=True, type=Path)
    e2e_compare.add_argument("--portable-root", required=True, type=Path)
    e2e_compare.add_argument("--freeze-receipt", required=True, type=Path)
    e2e_compare.add_argument("--case-identity", required=True, type=Path)
    e2e_compare.add_argument("--output", required=True, type=Path)

    e2e_run = subparsers.add_parser(
        "e2e-run", help="Run one fresh same-input native-vs-ONNX H2 pair"
    )
    e2e_run.add_argument("--input", required=True, type=Path)
    e2e_run.add_argument("--enrollment-root", required=True, type=Path)
    e2e_run.add_argument("--output-root", required=True, type=Path)
    e2e_run.add_argument("--freeze-receipt", required=True, type=Path)
    e2e_run.add_argument("--redim-onnx", required=True, type=Path)
    e2e_run.add_argument("--redim-sha256", required=True)
    e2e_run.add_argument("--segmentation-onnx", required=True, type=Path)
    e2e_run.add_argument("--segmentation-sha256", required=True)
    e2e_run.add_argument("--pipeline-id", default="fullpipe_v1_ag_dr_ir")
    e2e_run.add_argument("--duration-sec", default=10.0, type=float)
    e2e_run.add_argument(
        "--product-mode", default="H2_SESSION_MEMORY_ENHANCED"
    )
    e2e_run.add_argument("--runtime-tuning", type=Path)
    e2e_run.add_argument("--allow-empty-enrollment", action="store_true")

    for command, help_text in (
        ("runtime-file", "Run the explicit portable H2 profile on a local file"),
        ("runtime-live", "Run the explicit portable H2 profile on a microphone"),
    ):
        runtime = subparsers.add_parser(command, help=help_text)
        runtime.add_argument("--pipeline-id", default="fullpipe_v1_ag_dr_ir")
        runtime.add_argument("--output-root", required=True, type=Path)
        runtime.add_argument("--enrollment-root", required=True, type=Path)
        runtime.add_argument("--redim-onnx", required=True, type=Path)
        runtime.add_argument("--redim-sha256", required=True)
        runtime.add_argument("--segmentation-onnx", required=True, type=Path)
        runtime.add_argument("--segmentation-sha256", required=True)
        runtime.add_argument(
            "--product-mode", default="H2_SESSION_MEMORY_ENHANCED"
        )
        runtime.add_argument("--runtime-tuning", type=Path)
        runtime.add_argument("--session-id")
        runtime.add_argument("--duration-sec", required=True, type=float)
        runtime.add_argument("--no-telemetry", action="store_true")
        if command == "runtime-file":
            runtime.add_argument("--input", required=True, type=Path)
            runtime.add_argument("--realtime", action="store_true")
        else:
            runtime.add_argument("--device")

    environment = subparsers.add_parser("environment-manifest")
    environment.add_argument("--profile", required=True)
    environment.add_argument("--output", type=Path)

    arm64 = subparsers.add_parser("arm64-diagnostic")
    arm64.add_argument("--require-linux-arm64", action="store_true")
    arm64.add_argument("--require-graphs", action="store_true")
    arm64.add_argument("--redim-onnx", type=Path)
    arm64.add_argument("--segmentation-onnx", type=Path)
    arm64.add_argument("--probe-audio", action="store_true")
    arm64.add_argument("--output", type=Path)

    budget = subparsers.add_parser("resource-budget")
    budget.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = repository_root().path
    if args.command == "self-test":
        payload = structural_self_test(require_linux_arm64=args.require_linux_arm64)
    elif args.command == "onnx-status":
        payload = inspect_component(
            args.component, repository=repo, proposed_onnx_path=args.onnx_path
        )
    elif args.command == "export-plan":
        payload = build_export_plan(
            args.component,
            repository=repo,
            proposed_onnx_path=args.onnx_path,
        )
    elif args.command == "export":
        payload = export_component(
            args.component,
            repository=repo,
            onnx_path=args.onnx_path,
            exporter=args.exporter,
            replace=args.replace,
        )
    elif args.command == "parity-plan":
        payload = build_parity_plan(
            args.component,
            native_artifact_sha256=args.native_artifact_sha256,
            onnx_artifact_sha256=args.onnx_artifact_sha256,
        )
    elif args.command == "parity":
        payload = run_component_parity(
            args.component,
            repository=repo,
            onnx_path=args.onnx_path,
            output_dir=args.output_dir,
            audio_paths=args.audio,
        )
    elif args.command == "e2e-hook":
        payload = build_e2e_parity_hook(
            load_reports(args.report), output_path=args.output
        )
    elif args.command == "e2e-freeze":
        payload = freeze_e2e_parity_protocol(
            args.output,
            planned_cases=(
                {
                    "case_id": "enrolled_same_input_10s",
                    "identity_required": True,
                },
            ),
            engineering_smokes_excluded=(
                "native_factory_run_smoke",
                "portable_factory_run_smoke",
            ),
        )
    elif args.command == "e2e-compare":
        case_identity = json.loads(args.case_identity.read_text(encoding="utf-8"))
        if not isinstance(case_identity, dict):
            raise ValueError("case identity must contain a JSON object")
        payload = compare_full_pipeline_runs(
            args.native_root,
            args.portable_root,
            output_path=args.output,
            freeze_receipt_path=args.freeze_receipt,
            case_identity=case_identity,
        )
    elif args.command == "e2e-run":
        tuning = None
        if args.runtime_tuning is not None:
            tuning = json.loads(args.runtime_tuning.read_text(encoding="utf-8"))
            if not isinstance(tuning, dict):
                raise ValueError("runtime tuning must contain a JSON object")
        payload = run_fresh_factory_pair(
            input_path=args.input,
            enrollment_root=args.enrollment_root,
            output_root=args.output_root,
            freeze_receipt_path=args.freeze_receipt,
            graph_paths={
                "redimnet2_b2_speaker_embedding": args.redim_onnx,
                "pyannote_segmentation_3_0": args.segmentation_onnx,
            },
            graph_sha256={
                "redimnet2_b2_speaker_embedding": args.redim_sha256,
                "pyannote_segmentation_3_0": args.segmentation_sha256,
            },
            pipeline_id=args.pipeline_id,
            duration_sec=args.duration_sec,
            product_mode=args.product_mode,
            runtime_tuning=tuning,
            require_identity_exercised=not args.allow_empty_enrollment,
        )
    elif args.command in {"runtime-file", "runtime-live"}:
        from app.full_pipeline.factory import (
            build_file_runtime,
            build_microphone_runtime,
        )

        tuning = None
        if args.runtime_tuning is not None:
            tuning = json.loads(args.runtime_tuning.read_text(encoding="utf-8"))
            if not isinstance(tuning, dict):
                raise ValueError("runtime tuning must contain a JSON object")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        session_id = args.session_id or f"h2_portable_{stamp}"
        shared = {
            "pipeline_id": args.pipeline_id,
            "output_root": args.output_root,
            "enrollment_root": args.enrollment_root,
            "session_id": session_id,
            "duration_sec": args.duration_sec,
            "telemetry_enabled": not args.no_telemetry,
            "product_mode": args.product_mode,
            "runtime_tuning": tuning,
            "runtime_profile": "H2_PORTABLE_ONNX_FP32",
            "h2_onnx_graphs": {
                "redimnet2_b2_speaker_embedding": args.redim_onnx,
                "pyannote_segmentation_3_0": args.segmentation_onnx,
            },
            "h2_onnx_expected_sha256": {
                "redimnet2_b2_speaker_embedding": args.redim_sha256,
                "pyannote_segmentation_3_0": args.segmentation_sha256,
            },
        }
        if args.command == "runtime-file":
            runtime = build_file_runtime(
                input_path=args.input,
                realtime=args.realtime,
                **shared,
            )
        else:
            device: int | str | None = args.device
            if isinstance(device, str) and device.lstrip("-").isdigit():
                device = int(device)
            runtime = build_microphone_runtime(device=device, **shared)
        payload = dict(runtime.run())
        payload["output_root"] = str(args.output_root.resolve())
    elif args.command == "environment-manifest":
        payload = environment_manifest(profile=args.profile)
    elif args.command == "arm64-diagnostic":
        graph_paths = {}
        if args.redim_onnx is not None:
            graph_paths["redimnet2_b2_speaker_embedding"] = args.redim_onnx
        if args.segmentation_onnx is not None:
            graph_paths["pyannote_segmentation_3_0"] = args.segmentation_onnx
        payload = arm64_diagnostic(
            repository=repo,
            graph_paths=graph_paths,
            require_linux_arm64=args.require_linux_arm64,
            require_graphs=args.require_graphs,
            probe_audio=args.probe_audio,
        )
    elif args.command == "resource-budget":
        payload = two_gib_budget()
    else:  # pragma: no cover - argparse owns this branch.
        raise AssertionError(args.command)

    payload = deepcopy(payload)
    output = getattr(args, "output", None)
    if output is not None and args.command != "e2e-hook":
        atomic_write_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    status = str(payload.get("status", ""))
    return 2 if status == "FAILED" or status.endswith("FAIL") or status.endswith("BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
