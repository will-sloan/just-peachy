"""Preview-only generation for the GUI.

This keeps preview generation connected to the existing dataset loader and
augmentation processor while avoiding a full inference/scoring run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.augmentation import build_augmentation_plan, generate_previews
from app.dataset_registry.loader import load_dataset_selection, selection_records
from app.dataset_registry.registry import get_dataset
from app.gui.state import GuiRunConfig, validate_gui_config
from app.utils.json_utils import write_json, write_jsonl
from app.utils.logging_utils import setup_run_logger
from app.utils.paths import safe_relative_to, tool_root
from app.utils.run_artifacts import create_run_dir, write_yaml


LineCallback = Callable[[str], None]


@dataclass(frozen=True)
class PreviewOnlyResult:
    """Result of a GUI preview-only generation."""

    run_dir: Path
    preview_count: int
    preview_manifest_path: Path


def generate_preview_only(
    config: GuiRunConfig,
    project_root: Path,
    selected_source_file: Path | None = None,
    on_line: LineCallback | None = None,
) -> PreviewOnlyResult:
    """Generate preview audio from current GUI settings without running inference."""

    errors = validate_gui_config(config)
    if errors:
        raise ValueError("\n".join(errors))
    if not config.dataset_keys:
        raise ValueError("Select at least one dataset before generating preview audio.")

    dataset_key = config.dataset_keys[0]
    definition = get_dataset(dataset_key)
    run_dir = create_run_dir(
        tool_root(project_root) / "runs",
        definition.key,
        "preview",
        config.run_name or "gui_preview",
    )
    logger = setup_run_logger(run_dir / "logs" / "evaluation.log")
    _emit(on_line, f"Preview run folder: {run_dir}")

    base_records = _preview_records_from_config(
        config=config,
        project_root=project_root,
        dataset_key=definition.key,
        selected_source_file=selected_source_file,
        logger=logger,
    )
    plan = build_augmentation_plan(
        project_root=project_root,
        mode=config.augmentation,
        rir_path_values=config.rir_paths,
        noise_types=config.noise_types,
        snr_values=config.snr_db,
        preview_enabled=True,
        preview_recording_id=None if selected_source_file else config.preview_recording_id,
    )
    preview_manifest = generate_previews(
        base_records=base_records,
        run_dir=run_dir,
        project_root=project_root,
        plan=plan,
        logger=logger,
    )

    run_config = {
        "command": "preview",
        "project_root": str(project_root),
        "run_dir": str(run_dir),
        "dataset": {
            "key": definition.key,
            "name": definition.display_name,
            "dataset_id": definition.dataset_id,
        },
        "selection": {
            "subset_filters": config.filters_by_dataset.get(definition.key, {}),
            "max_recordings": config.max_recordings,
            "selected_source_recordings": len(base_records),
        },
        "run_name": config.run_name,
        "augmentation": {
            **plan.to_jsonable(),
            "preview_count": len(preview_manifest),
        },
    }
    write_yaml(run_dir / "run_config.yaml", run_config)
    write_json(run_dir / "augmentation_config.json", run_config["augmentation"])
    write_json(
        run_dir / "dataset_selection.json",
        {
            "dataset_key": definition.key,
            "dataset_name": definition.display_name,
            "selected_source_recordings": len(base_records),
            "source_records_manifest": "dataset_selection_source_records.jsonl",
        },
    )
    write_jsonl(run_dir / "dataset_selection_source_records.jsonl", base_records)
    manifest_path = run_dir / "preview_audio" / "preview_manifest.json"
    _emit(on_line, f"Wrote {len(preview_manifest)} preview file(s).")
    _emit(on_line, f"Preview manifest: {manifest_path}")
    return PreviewOnlyResult(
        run_dir=run_dir,
        preview_count=len(preview_manifest),
        preview_manifest_path=manifest_path,
    )


def _preview_records_from_config(
    config: GuiRunConfig,
    project_root: Path,
    dataset_key: str,
    selected_source_file: Path | None,
    logger: logging.Logger,
) -> list[dict[str, object]]:
    if selected_source_file is not None:
        source = selected_source_file.resolve()
        if not source.exists():
            raise FileNotFoundError(f"Preview source audio does not exist: {source}")
        definition = get_dataset(dataset_key)
        return [
            {
                "_selection_index": 0,
                "recording_id": source.stem,
                "utt_id": source.stem,
                "speaker_label": "",
                "start_sec": None,
                "end_sec": None,
                "reference_text": "",
                "audio_path_project_relative": safe_relative_to(source, project_root),
                "audio_path_resolved": str(source),
                "audio_exists": True,
                "dataset": definition.display_name,
                "dataset_id": definition.dataset_id,
            }
        ]

    definition = get_dataset(dataset_key)
    filters = config.filters_by_dataset.get(definition.key, {})
    max_recordings = None if config.preview_recording_id else (config.max_recordings or 1)
    selection = load_dataset_selection(
        project_root=project_root,
        definition=definition,
        subset_filters=filters,
        max_recordings=max_recordings,
    )
    records = selection_records(selection.dataframe)
    if not records:
        raise ValueError("No records matched the current preview dataset/filter selection.")
    logger.info("Selected %d metadata record(s) for preview lookup", len(records))
    return records


def _emit(callback: LineCallback | None, line: str) -> None:
    if callback:
        callback(line)

