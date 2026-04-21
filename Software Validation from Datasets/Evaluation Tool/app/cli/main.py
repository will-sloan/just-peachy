"""Command-line entry point for the Evaluation Tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from app.augmentation import (
    build_augmentation_plan,
    expand_records_for_augmentation,
    generate_previews,
)
from app.augmentation.processor import total_duration_sec
from app.dataset_registry.loader import (
    load_dataset_selection,
    parse_subset_filters,
    selection_records,
)
from app.dataset_registry.registry import (
    filter_help,
    get_dataset,
    list_datasets,
    mode_help,
)
from app.model_runner.external_stub import ExternalStubRunner
from app.model_runner.simulated import FakeModelRunner
from app.plotting.plots import build_plots
from app.reporting.reporter import build_report
from app.scoring.scorer import score_run
from app.utils.json_utils import read_jsonl, write_json, write_jsonl
from app.utils.logging_utils import setup_run_logger
from app.utils.paths import find_project_root, safe_relative_to, tool_root
from app.utils.run_artifacts import (
    create_run_dir,
    ensure_run_subdirs,
    read_yaml,
    write_yaml,
)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evaluation-tool",
        description="Dataset-aware batch evaluation for normalized speech metadata.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-datasets", help="List supported datasets")
    add_project_arg(list_parser)
    list_parser.set_defaults(func=command_list_datasets)

    gui_parser = subparsers.add_parser("gui", help="Launch the local tkinter GUI")
    add_project_arg(gui_parser)
    gui_parser.set_defaults(func=command_gui)

    run_parser = subparsers.add_parser("run", help="Run inference only")
    add_selection_args(run_parser)
    add_runner_args(run_parser)
    add_augmentation_args(run_parser)
    run_parser.set_defaults(func=command_run)

    score_parser = subparsers.add_parser("score", help="Score predictions in an existing run folder")
    score_parser.add_argument("--run-dir", required=True, type=Path, help="Existing run folder")
    score_parser.set_defaults(func=command_score)

    report_parser = subparsers.add_parser("report", help="Build plots and reports for an existing scored run")
    report_parser.add_argument("--run-dir", required=True, type=Path, help="Existing run folder")
    report_parser.set_defaults(func=command_report)

    full_parser = subparsers.add_parser("full", help="Run inference, score, plot, and report")
    add_selection_args(full_parser)
    add_runner_args(full_parser)
    add_augmentation_args(full_parser)
    full_parser.set_defaults(func=command_full)
    return parser


def add_project_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root containing Normalized Metadata and Raw Datasets (Not formatted)",
    )


def add_selection_args(parser: argparse.ArgumentParser) -> None:
    add_project_arg(parser)
    parser.add_argument("--dataset", required=True, help="Dataset name or key")
    parser.add_argument(
        "--subset",
        action="append",
        default=[],
        help="Optional subset filter as key=value or key=value1,value2. Can be repeated.",
    )
    parser.add_argument(
        "--reader-split",
        default=None,
        help="Convenience filter for HiFiTTS reader_split, e.g. 6097_clean.",
    )
    parser.add_argument(
        "--reader-id",
        default=None,
        help="Convenience filter for datasets with reader_id.",
    )
    parser.add_argument(
        "--split",
        default=None,
        help="Convenience filter for datasets with split.",
    )
    parser.add_argument(
        "--clean-vs-other",
        default=None,
        help="Convenience filter for HiFiTTS clean_vs_other labels.",
    )
    parser.add_argument(
        "--audio-quality",
        default=None,
        help="Convenience filter for HiFiTTS audio_quality labels.",
    )
    parser.add_argument(
        "--speaker-id",
        default=None,
        help="Convenience filter for datasets with speaker_id, including VOiCES.",
    )
    parser.add_argument(
        "--speaker-id-ref",
        default=None,
        help="Convenience filter for CHiME-6 reference speaker labels, e.g. P05.",
    )
    parser.add_argument(
        "--recording-speaker-id",
        default=None,
        help="Convenience filter for CHiME-6 participant-close recording speaker labels.",
    )
    parser.add_argument(
        "--gender",
        default=None,
        help="Convenience filter for datasets with gender metadata.",
    )
    parser.add_argument(
        "--room",
        default=None,
        help="Convenience filter for VOiCES room labels, e.g. rm1.",
    )
    parser.add_argument(
        "--distractor",
        default=None,
        help="Convenience filter for VOiCES distractor labels, e.g. musi, babb, tele, none.",
    )
    parser.add_argument(
        "--mic",
        default=None,
        help="Convenience filter for VOiCES microphone id.",
    )
    parser.add_argument(
        "--position",
        default=None,
        help="Convenience filter for VOiCES position labels, e.g. clo or far.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Convenience filter for VOiCES device labels.",
    )
    parser.add_argument(
        "--device-id",
        default=None,
        help="Convenience filter for CHiME-6 device ids, e.g. U01.",
    )
    parser.add_argument(
        "--channel-id",
        default=None,
        help="Convenience filter for CHiME-6 channel ids, e.g. CH1.",
    )
    parser.add_argument(
        "--microphone-id",
        default=None,
        help="Convenience filter for CHiME-6 microphone ids, e.g. U01_CH1 or P05.",
    )
    parser.add_argument(
        "--degrees",
        default=None,
        help="Convenience filter for VOiCES angle/degrees labels.",
    )
    parser.add_argument(
        "--query-name",
        default=None,
        help="Convenience filter for VOiCES query_name.",
    )
    parser.add_argument(
        "--meeting-id",
        default=None,
        help="Convenience filter for meeting datasets such as AMI.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Convenience filter for session-based datasets such as CHiME-6.",
    )
    parser.add_argument(
        "--stream-type",
        default=None,
        help="Convenience filter for stream_type, e.g. AMI headset/array or CHiME-6 farfield_array.",
    )
    parser.add_argument(
        "--stream-id",
        default=None,
        help="Convenience filter for AMI stream_id, e.g. Headset-0 or Array1-01.",
    )
    parser.add_argument(
        "--seen-type",
        default=None,
        help="Convenience filter for AMI seen_type, e.g. training or development.",
    )
    parser.add_argument(
        "--meeting-type",
        default=None,
        help="Convenience filter for AMI meeting_type, e.g. scenario or nonscenario.",
    )
    parser.add_argument(
        "--ref-device",
        default=None,
        help="Convenience filter for CHiME-6 transcript reference device, e.g. U02.",
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Convenience filter for datasets with location labels.",
    )
    parser.add_argument(
        "--location-hint",
        default=None,
        help="Convenience filter for CHiME-6 recording location hints, e.g. kitchen.",
    )
    parser.add_argument(
        "--max-recordings",
        type=int,
        default=None,
        help="Limit selected recordings for smoke tests.",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Optional human-readable suffix for the timestamped run folder.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=None,
        help="Optional folder for run outputs. Defaults to Evaluation Tool/runs.",
    )


def add_runner_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--runner",
        choices=("simulation", "external-stub"),
        default="simulation",
        help="Model runner implementation.",
    )
    parser.add_argument(
        "--simulation-mode",
        choices=("perfect", "noisy", "drop_some"),
        default="perfect",
        help="Fake runner behavior for simulation mode.",
    )


def add_augmentation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--augmentation",
        choices=("none", "reverb", "noise", "reverb_noise"),
        default="none",
        help="On-the-fly audio augmentation mode.",
    )
    parser.add_argument(
        "--rir-paths",
        nargs="+",
        action="append",
        default=[],
        help=(
            "One or more RIR WAV paths. Values can be project-relative or file names "
            "inside Raw Datasets (Not formatted)/MIT 271 RIRs/Audio."
        ),
    )
    parser.add_argument(
        "--noise-type",
        choices=("white", "pink"),
        action="append",
        default=[],
        help="Noise type. Repeat to sweep both white and pink noise.",
    )
    parser.add_argument(
        "--snr-db",
        type=float,
        action="append",
        default=[],
        help="Target SNR in dB. Repeat to sweep multiple SNRs.",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Save preview WAV files for the selected augmentation condition(s).",
    )
    parser.add_argument(
        "--preview-recording-id",
        default=None,
        help="Optional source recording_id to use for augmentation preview.",
    )
    parser.add_argument(
        "--augmentation-seed",
        type=int,
        default=1337,
        help="Deterministic seed for generated noise.",
    )


def command_list_datasets(args: argparse.Namespace) -> None:
    project_root = resolve_project_root(args.project_root)
    print(f"Project root: {project_root}")
    print("Supported datasets:")
    for definition in list_datasets():
        metadata_dir = project_root / definition.normalized_metadata_dir
        status = "ok" if metadata_dir.exists() else "missing metadata"
        print(f"- {definition.display_name} ({definition.key}) [{status}]")
        print(f"  metadata: {definition.normalized_metadata_dir.as_posix()}")
        print(f"  unit: {definition.evaluation_unit}")
        print(f"  filters: {filter_help(definition)}")
        print(f"  modes: {mode_help(definition)}")
        print(f"  augmentation: {'yes' if definition.supports_augmentation else 'no'}")
        print(f"  speaker attribution: {'yes' if definition.supports_speaker_attribution else 'no'}")


def command_gui(args: argparse.Namespace) -> None:
    from app.gui.main import launch_gui

    launch_gui(project_root=args.project_root)


def command_run(args: argparse.Namespace) -> None:
    run_dir, run_config, records = prepare_new_run(args, "run")
    logger = setup_run_logger(run_dir / "logs" / "evaluation.log")

    print("[3/4] Running inference")
    runner = build_runner(args)
    result = runner.run_batch(records, run_dir / "predictions", run_config, logger)
    print(
        f"[4/4] Done: attempted={result.attempted_count}, "
        f"predictions={result.written_count}, skipped={result.skipped_count}, "
        f"failed={result.failed_count}"
    )
    print(f"Run folder: {run_dir}")


def command_score(args: argparse.Namespace) -> None:
    run_dir = args.run_dir.resolve()
    print("[1/3] Loading run selection")
    run_config, records = load_existing_run(run_dir)
    logger = setup_run_logger(run_dir / "logs" / "evaluation.log")
    definition = get_dataset(str(run_config["dataset"]["key"]))

    print("[2/3] Scoring predictions")
    result = score_run(run_dir, definition, records, logger)
    print(
        "[3/3] Done: "
        f"aggregate_wer={_format_float(result.aggregate_metrics.get('aggregate_wer'))}, "
        f"missing={result.aggregate_metrics.get('missing_predictions')}"
    )
    print(f"Metrics: {result.per_recording_metrics_path}")


def command_report(args: argparse.Namespace) -> None:
    run_dir = args.run_dir.resolve()
    print("[1/3] Loading run config")
    run_config, _records = load_existing_run(run_dir)
    logger = setup_run_logger(run_dir / "logs" / "evaluation.log")

    print("[2/3] Building plots and report")
    build_plots(run_dir, str(run_config["dataset"]["key"]), logger)
    report_path = build_report(run_dir, logger)
    print(f"[3/3] Done: {report_path}")


def command_full(args: argparse.Namespace) -> None:
    run_dir, run_config, records = prepare_new_run(args, "full")
    logger = setup_run_logger(run_dir / "logs" / "evaluation.log")
    definition = get_dataset(str(run_config["dataset"]["key"]))

    print("[3/6] Running inference")
    runner = build_runner(args)
    runner_result = runner.run_batch(records, run_dir / "predictions", run_config, logger)

    print("[4/6] Scoring predictions")
    score_result = score_run(run_dir, definition, records, logger)

    print("[5/6] Building plots and report")
    build_plots(run_dir, definition.key, logger)
    report_path = build_report(run_dir, logger)

    print(
        f"[6/6] Done: selected={len(records)}, "
        f"predictions={runner_result.written_count}, "
        f"failed={runner_result.failed_count}, "
        f"missing={score_result.aggregate_metrics.get('missing_predictions')}, "
        f"aggregate_wer={_format_float(score_result.aggregate_metrics.get('aggregate_wer'))}"
    )
    print(f"Run folder: {run_dir}")
    print(f"Report: {report_path}")


def prepare_new_run(
    args: argparse.Namespace,
    command_name: str,
) -> tuple[Path, dict[str, Any], list[dict[str, object]]]:
    project_root = resolve_project_root(args.project_root)
    definition = get_dataset(args.dataset)
    validate_augmentation_allowed(args, definition)
    filters = parse_subset_filters(collect_subset_filter_items(args), definition)
    runs_root = (args.runs_root or (tool_root(project_root) / "runs")).resolve()

    print("[1/6] Loading dataset selection" if command_name == "full" else "[1/4] Loading dataset selection")
    selection = load_dataset_selection(
        project_root=project_root,
        definition=definition,
        subset_filters=filters,
        max_recordings=args.max_recordings,
    )
    base_records = selection_records(selection.dataframe)
    augmentation_plan = build_augmentation_plan(
        project_root=project_root,
        mode=args.augmentation,
        rir_path_values=_flatten_arg_groups(args.rir_paths),
        noise_types=args.noise_type,
        snr_values=args.snr_db,
        preview_enabled=args.preview,
        preview_recording_id=args.preview_recording_id,
        seed=args.augmentation_seed,
    )
    records = expand_records_for_augmentation(base_records, augmentation_plan)
    run_dir = create_run_dir(runs_root, definition.key, command_name, args.run_name)

    logger = setup_run_logger(run_dir / "logs" / "evaluation.log")
    print("[2/6] Preparing augmentation" if command_name == "full" else "[2/4] Preparing augmentation")
    preview_manifest = generate_previews(
        base_records=base_records,
        run_dir=run_dir,
        project_root=project_root,
        plan=augmentation_plan,
        logger=logger,
    )

    run_config: dict[str, Any] = {
        "command": command_name,
        "project_root": str(project_root),
        "project_root_relative_to_run": safe_relative_to(project_root, run_dir),
        "run_dir": str(run_dir),
        "dataset": {
            "key": definition.key,
            "name": definition.display_name,
            "dataset_id": definition.dataset_id,
            "normalized_metadata_dir": definition.normalized_metadata_dir.as_posix(),
        },
        "selection": {
            "subset_filters": filters,
            "max_recordings": args.max_recordings,
            "selected_source_recordings": len(base_records),
            "selected_recordings": len(records),
            "total_source_duration_sec": total_duration_sec(base_records),
            "total_evaluation_duration_sec": total_duration_sec(records),
        },
        "run_name": args.run_name,
        "augmentation": {
            **augmentation_plan.to_jsonable(),
            "preview_count": len(preview_manifest),
        },
        "runner": {
            "name": args.runner,
            "simulation_mode": args.simulation_mode if args.runner == "simulation" else None,
        },
        "prediction_contract": {
            "minimum_file": "predictions/utterances.jsonl",
            "optional_files": ["predictions/words.jsonl", "predictions/segments.rttm"],
        },
    }
    write_yaml(run_dir / "run_config.yaml", run_config)
    write_json(
        run_dir / "dataset_selection.json",
        {
            **selection.summary,
            "selected_source_recordings": len(base_records),
            "selected_evaluation_items": len(records),
            "records_manifest": "dataset_selection_records.jsonl",
            "source_records_manifest": "dataset_selection_source_records.jsonl",
        },
    )
    write_json(run_dir / "augmentation_config.json", run_config["augmentation"])
    write_jsonl(run_dir / "dataset_selection_source_records.jsonl", base_records)
    write_jsonl(run_dir / "dataset_selection_records.jsonl", records)

    print(
        f"Selected {len(base_records)} source recording(s), "
        f"{len(records)} evaluation item(s); "
        f"missing audio paths={selection.summary['missing_audio_count']}"
    )
    return run_dir, run_config, records


def collect_subset_filter_items(args: argparse.Namespace) -> list[str]:
    """Combine generic and convenience subset filters."""

    items = list(args.subset or [])
    convenience = {
        "reader_split": args.reader_split,
        "reader_id": args.reader_id,
        "split": args.split,
        "clean_vs_other": args.clean_vs_other,
        "audio_quality": args.audio_quality,
        "speaker_id": args.speaker_id,
        "speaker_id_ref": args.speaker_id_ref,
        "recording_speaker_id_ref": args.recording_speaker_id,
        "gender": args.gender,
        "room": args.room,
        "distractor": args.distractor,
        "mic": args.mic,
        "position": args.position,
        "device": args.device,
        "device_id": args.device_id,
        "channel_id": args.channel_id,
        "microphone_id": args.microphone_id,
        "degrees": args.degrees,
        "query_name": args.query_name,
        "meeting_id": args.meeting_id,
        "session_id": args.session_id,
        "stream_type": args.stream_type,
        "stream_id": args.stream_id,
        "seen_type": args.seen_type,
        "meeting_type": args.meeting_type,
        "ref_device": args.ref_device,
        "location": args.location,
        "location_hint": args.location_hint,
    }
    for key, value in convenience.items():
        if value:
            items.append(f"{key}={value}")
    return items


def validate_augmentation_allowed(args: argparse.Namespace, definition) -> None:
    """Block augmentation options for datasets that do not support them."""

    if definition.supports_augmentation:
        return
    requested = []
    if args.augmentation != "none":
        requested.append(f"--augmentation {args.augmentation}")
    if _flatten_arg_groups(args.rir_paths):
        requested.append("--rir-paths")
    if args.noise_type:
        requested.append("--noise-type")
    if args.snr_db:
        requested.append("--snr-db")
    if args.preview:
        requested.append("--preview")
    if requested:
        joined = ", ".join(requested)
        raise ValueError(
            f"{definition.display_name} does not support Evaluation Tool audio augmentation. "
            f"Remove these option(s): {joined}."
        )


def _flatten_arg_groups(groups: list[list[str]] | None) -> list[str]:
    values: list[str] = []
    for group in groups or []:
        values.extend(group)
    return values


def load_existing_run(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, object]]]:
    ensure_run_subdirs(run_dir)
    config_path = run_dir / "run_config.yaml"
    records_path = run_dir / "dataset_selection_records.jsonl"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing run config: {config_path}")
    if not records_path.exists():
        raise FileNotFoundError(f"Missing selection records: {records_path}")
    return read_yaml(config_path), list(read_jsonl(records_path))


def build_runner(args: argparse.Namespace):
    if args.runner == "simulation":
        return FakeModelRunner(args.simulation_mode)
    if args.runner == "external-stub":
        return ExternalStubRunner()
    raise ValueError(f"Unknown runner {args.runner}")


def resolve_project_root(value: Path | None) -> Path:
    return find_project_root(value.resolve() if value else None)


def _format_float(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


if __name__ == "__main__":
    main()
