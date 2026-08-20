"""CLI surface for the hybrid speaker-attribution protocol."""

from __future__ import annotations

import json
from pathlib import Path

from app.controlled_diarization.contracts import default_generated_root
from app.hybrid_speaker_attribution.analysis import analyze, collect
from app.hybrid_speaker_attribution.attribution import AttributionSettings, attribute_recording, score_recording
from app.hybrid_speaker_attribution.contracts import DEFAULT_BENCHMARK_ROOT, DEFAULT_PROTOCOL_ROOT, default_result_root, load_enrollment_policy
from app.hybrid_speaker_attribution.protocol import prepare_protocol, validate_protocol
from app.hybrid_speaker_attribution.runner import audit, freeze_configuration, plan, run_tier, status


def add_hybrid_attribution_parser(subparsers) -> None:
    parser = subparsers.add_parser("hybrid-attribution", help="Evaluate anonymous diarization plus open-set speaker identity")
    actions = parser.add_subparsers(dest="hybrid_action", required=True)
    audit_parser = actions.add_parser("audit")
    _selection(audit_parser)
    audit_parser.set_defaults(func=_audit)
    prepare = actions.add_parser("prepare")
    _protocol_paths(prepare)
    prepare.set_defaults(func=_prepare)
    plan_parser = actions.add_parser("plan")
    _selection(plan_parser)
    plan_parser.add_argument("--diarization-result-root", type=Path, default=None)
    plan_parser.set_defaults(func=_plan)
    validate = actions.add_parser("validate")
    _protocol_paths(validate)
    validate.add_argument("--generated-root", type=Path, default=default_generated_root())
    validate.add_argument("--verify-audio-hashes", action="store_true")
    validate.set_defaults(func=_validate)
    smoke = actions.add_parser("smoke")
    _run_args(smoke)
    smoke.set_defaults(func=_smoke)
    development = actions.add_parser("run-development")
    _run_args(development)
    development.set_defaults(func=_development)
    analyze_development = actions.add_parser("analyze-development")
    _analysis_args(analyze_development)
    analyze_development.set_defaults(func=_analyze_development)
    freeze = actions.add_parser("freeze")
    _selection(freeze)
    freeze.add_argument("--development-configuration-id", required=True)
    freeze.add_argument("--development-result-root", type=Path, required=True)
    freeze.add_argument("--frozen-diarization-config", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--decision-note", required=True)
    _settings(freeze)
    freeze.set_defaults(func=_freeze)
    evaluation = actions.add_parser("run-evaluation")
    _run_args(evaluation)
    evaluation.set_defaults(func=_evaluation)
    status_parser = actions.add_parser("status")
    status_parser.add_argument("--result-root", type=Path, default=None)
    status_parser.set_defaults(func=lambda args: _emit(status(args.result_root)))
    analyze_parser = actions.add_parser("analyze")
    _analysis_args(analyze_parser)
    analyze_parser.set_defaults(func=_analyze)
    collection = actions.add_parser("collect")
    collection.add_argument("--analysis-root", type=Path, required=True)
    collection.add_argument("--output-root", type=Path, required=True)
    collection.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)
    collection.add_argument("--frozen-hybrid-config", type=Path, default=None)
    collection.set_defaults(func=_collect)


def _protocol_paths(parser) -> None:
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    parser.add_argument("--protocol-root", type=Path, default=DEFAULT_PROTOCOL_ROOT)


def _selection(parser) -> None:
    _protocol_paths(parser)
    parser.add_argument("--speaker-backend", required=True)
    parser.add_argument("--diarization-pipeline", required=True)
    parser.add_argument("--enrollment-policy", type=Path, required=True)
    parser.add_argument("--generated-root", type=Path, default=default_generated_root())


def _settings(parser) -> None:
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--score-margin", type=float, default=None)
    parser.add_argument("--minimum-segment-sec", type=float, default=None)
    parser.add_argument("--minimum-evidence-sec", type=float, default=None)
    parser.add_argument("--enrollment-aggregation", choices=("normalized_mean", "duration_weighted_mean", "multi_template_mean_score"), default=None)
    parser.add_argument("--cluster-aggregation", choices=("normalized_mean", "duration_weighted_mean"), default=None)
    parser.add_argument("--overlap-policy", choices=("include_predicted_overlap", "exclude_predicted_overlap_segments"), default=None)


def _run_args(parser) -> None:
    _selection(parser)
    parser.add_argument("--diarization-result-root", type=Path, required=True)
    parser.add_argument("--result-root", type=Path, default=default_result_root())
    parser.add_argument("--frozen-diarization-config", type=Path, default=None)
    parser.add_argument("--frozen-hybrid-config", type=Path, default=None)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--reuse-diarization-only", action="store_true")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--score-margin", type=float, default=None)
    parser.add_argument("--minimum-evidence-sec", type=float, default=None)
    parser.add_argument("--cluster-aggregation", choices=("normalized_mean", "duration_weighted_mean"), default=None)
    parser.add_argument("--overlap-policy", choices=("include_predicted_overlap", "exclude_predicted_overlap_segments"), default=None)


def _analysis_args(parser) -> None:
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)


def _audit(args) -> None:
    _emit(audit(speaker_backend=args.speaker_backend, diarization_pipeline=args.diarization_pipeline, enrollment_policy=args.enrollment_policy, benchmark_root=args.benchmark_root, protocol_root=args.protocol_root, generated_root=args.generated_root))


def _prepare(args) -> None:
    _emit(prepare_protocol(benchmark_root=args.benchmark_root, output_root=args.protocol_root))


def _plan(args) -> None:
    _emit(plan(speaker_backend=args.speaker_backend, diarization_pipeline=args.diarization_pipeline, enrollment_policy=args.enrollment_policy, protocol_root=args.protocol_root, benchmark_root=args.benchmark_root, diarization_result_root=getattr(args, "diarization_result_root", None)))


def _validate(args) -> None:
    from app.controlled_diarization.benchmark import validate_benchmark

    controlled = validate_benchmark(
        benchmark_root=args.benchmark_root,
        generated_root=args.generated_root,
        verify_source_hashes=args.verify_audio_hashes,
        write_report=False,
    )
    if not controlled.get("valid"):
        raise ValueError("controlled benchmark validation failed")
    hybrid = validate_protocol(args.protocol_root, benchmark_root=args.benchmark_root, verify_audio_hashes=args.verify_audio_hashes)
    _emit({"controlled_benchmark": controlled, "hybrid_protocol": hybrid, "valid": True})


def _smoke(args) -> None:
    args.max_cases = args.max_cases or 1
    _emit(_run(args, "smoke"))


def _development(args) -> None:
    _emit(_run(args, "development"))


def _evaluation(args) -> None:
    _emit(_run(args, "evaluation"))


def _run(args, tier: str) -> dict[str, object]:
    overrides = {key: value for key, value in {
        "product_threshold": args.threshold,
        "score_margin": args.score_margin,
        "minimum_evidence_duration_sec": args.minimum_evidence_sec,
        "cluster_aggregation": args.cluster_aggregation,
        "overlap_policy": args.overlap_policy,
    }.items() if value is not None}
    return run_tier(tier=tier, speaker_backend=args.speaker_backend, diarization_pipeline=args.diarization_pipeline, enrollment_policy_path=args.enrollment_policy, diarization_result_root=args.diarization_result_root, result_root=args.result_root, benchmark_root=args.benchmark_root, protocol_root=args.protocol_root, generated_root=args.generated_root, frozen_diarization_config=args.frozen_diarization_config, frozen_hybrid_config=args.frozen_hybrid_config, max_cases=args.max_cases, settings_override=overrides, run_diarization=not args.reuse_diarization_only)


def _analyze_development(args) -> None:
    _emit(analyze(result_root=args.result_root, output_root=args.output_root, tiers=("development",), include_development_curves=True))


def _analyze(args) -> None:
    _emit(analyze(result_root=args.result_root, output_root=args.output_root, tiers=("development", "evaluation"), include_development_curves=True))


def _freeze(args) -> None:
    policy = load_enrollment_policy(args.enrollment_policy)
    settings = AttributionSettings(
        product_threshold=args.threshold,
        score_margin=float(policy.get("score_margin") or 0.0) if args.score_margin is None else args.score_margin,
        minimum_segment_duration_sec=float(policy["minimum_segment_duration_sec"]) if args.minimum_segment_sec is None else args.minimum_segment_sec,
        minimum_evidence_duration_sec=float(policy["minimum_evidence_duration_sec"]) if args.minimum_evidence_sec is None else args.minimum_evidence_sec,
        enrollment_aggregation=str(policy["aggregation_method"]) if args.enrollment_aggregation is None else args.enrollment_aggregation,
        cluster_aggregation=args.cluster_aggregation or "normalized_mean",
        overlap_policy=args.overlap_policy or "include_predicted_overlap",
    )
    _emit(freeze_configuration(development_configuration_id=args.development_configuration_id, speaker_backend=args.speaker_backend, diarization_pipeline=args.diarization_pipeline, enrollment_policy_path=args.enrollment_policy, frozen_diarization_config=args.frozen_diarization_config, output_path=args.output, attribution_settings=settings.__dict__, decision_note=args.decision_note, protocol_root=args.protocol_root, development_result_root=args.development_result_root))


def _collect(args) -> None:
    _emit(collect(analysis_root=args.analysis_root, output_root=args.output_root, protocol_root=args.protocol_root, frozen_hybrid_config=args.frozen_hybrid_config))


def _emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))
