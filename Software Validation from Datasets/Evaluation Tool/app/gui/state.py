"""GUI state, validation, and CLI command serialization.

This module intentionally contains no tkinter imports so it can be tested in a
headless shell. The tkinter layer builds a ``GuiRunConfig`` and this module turns
that into the same CLI commands a user could run manually.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.augmentation.config import RIR_AUDIO_ROOT
from app.dataset_registry.registry import get_dataset, list_datasets


AUGMENTATION_MODES = ("none", "reverb", "noise", "reverb_noise")
NOISE_TYPES = ("white", "pink")
SIMULATION_MODES = ("perfect", "noisy", "drop_some")
RIR_LISTBOX_HEIGHT = 8


@dataclass(frozen=True)
class GuiRunConfig:
    """User selections collected from the local GUI."""

    dataset_keys: tuple[str, ...]
    command: str = "full"
    runner: str = "simulation"
    simulation_mode: str = "perfect"
    augmentation: str = "none"
    rir_paths: tuple[str, ...] = ()
    noise_types: tuple[str, ...] = ()
    snr_db: tuple[float, ...] = ()
    max_recordings: int | None = None
    run_name: str | None = None
    preview: bool = False
    preview_recording_id: str | None = None
    filters_by_dataset: dict[
        str,
        dict[str, tuple[str, ...] | list[str] | str],
    ] = field(default_factory=dict)
    project_root: Path | None = None


@dataclass(frozen=True)
class ControlVisibility:
    """Which optional GUI control groups should be visible/enabled."""

    show_simulation_mode: bool
    show_rir_controls: bool
    show_noise_controls: bool
    show_preview_recording: bool


def augmentation_visibility(mode: str, preview: bool = False) -> ControlVisibility:
    """Return smart-control visibility for an augmentation mode."""

    if mode not in AUGMENTATION_MODES:
        raise ValueError(f"Unknown augmentation mode {mode!r}")
    return ControlVisibility(
        show_simulation_mode=True,
        show_rir_controls=mode in {"reverb", "reverb_noise"},
        show_noise_controls=mode in {"noise", "reverb_noise"},
        show_preview_recording=preview,
    )


def filters_for_selected_datasets(dataset_keys: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """Return supported filters grouped by selected dataset."""

    grouped: dict[str, tuple[str, ...]] = {}
    for key in dataset_keys:
        definition = get_dataset(key)
        grouped[definition.key] = definition.supported_subset_filters
    return grouped


def parse_snr_values(text: str) -> tuple[float, ...]:
    """Parse comma/space/semicolon separated SNR values."""

    stripped = text.strip()
    if not stripped:
        return ()
    tokens = [
        token.strip()
        for token in stripped.replace(";", ",").replace("\n", ",").split(",")
        if token.strip()
    ]
    values: list[float] = []
    for token in tokens:
        try:
            values.append(float(token))
        except ValueError as exc:
            raise ValueError(f"Invalid SNR value {token!r}; use values like 5, 10, 20") from exc
    return tuple(values)


def parse_max_recordings(text: str) -> int | None:
    """Parse optional max-recordings GUI field."""

    stripped = text.strip()
    if not stripped:
        return None
    try:
        value = int(stripped)
    except ValueError as exc:
        raise ValueError("--max-recordings must be a whole number") from exc
    if value <= 0:
        raise ValueError("--max-recordings must be greater than zero")
    return value


def validate_gui_config(config: GuiRunConfig) -> list[str]:
    """Return validation errors. Empty list means the config can launch."""

    errors: list[str] = []
    if not config.dataset_keys:
        errors.append("Select at least one dataset.")

    for key in config.dataset_keys:
        try:
            definition = get_dataset(key)
        except KeyError:
            errors.append(f"Unknown dataset {key!r}.")
            continue
        filters = config.filters_by_dataset.get(definition.key, {})
        unsupported = set(filters) - set(definition.supported_subset_filters)
        if unsupported:
            errors.append(
                f"{definition.display_name} does not support filter(s): "
                + ", ".join(sorted(unsupported))
            )

    augmentation_blocked = [
        get_dataset(key).display_name
        for key in config.dataset_keys
        if not get_dataset(key).supports_augmentation
    ]

    if config.command not in {"run", "full"}:
        errors.append("GUI can launch only run or full commands.")
    if config.runner not in {"simulation", "external-stub"}:
        errors.append("Runner must be simulation or external-stub.")
    if config.runner == "simulation" and config.simulation_mode not in SIMULATION_MODES:
        errors.append("Choose a valid simulation mode.")
    if config.augmentation not in AUGMENTATION_MODES:
        errors.append("Choose a valid augmentation mode.")
    if augmentation_blocked:
        blocked = ", ".join(augmentation_blocked)
        if config.augmentation != "none":
            errors.append(f"Audio augmentation is not available for: {blocked}.")
        if config.preview:
            errors.append(f"Augmentation preview audio is not available for: {blocked}.")
    if config.augmentation in {"reverb", "reverb_noise"} and not config.rir_paths:
        errors.append("Select at least one RIR for reverb augmentation.")
    if config.augmentation in {"noise", "reverb_noise"}:
        if not config.noise_types:
            errors.append("Select at least one noise type for noise augmentation.")
        if not config.snr_db:
            errors.append("Enter at least one SNR value for noise augmentation.")
    return errors


def build_cli_commands(
    config: GuiRunConfig,
    tool_root: Path,
    python_executable: str | None = None,
) -> list[list[str]]:
    """Serialize GUI selections to CLI commands for sequential execution."""

    errors = validate_gui_config(config)
    if errors:
        raise ValueError("\n".join(errors))

    executable = python_executable or sys.executable
    commands: list[list[str]] = []
    multi_dataset = len(config.dataset_keys) > 1
    for dataset_key in config.dataset_keys:
        definition = get_dataset(dataset_key)
        command = [
            executable,
            str(tool_root / "run_evaluation.py"),
            config.command,
            "--dataset",
            definition.key,
            "--runner",
            config.runner,
            "--augmentation",
            config.augmentation,
        ]
        if config.runner == "simulation":
            command.extend(["--simulation-mode", config.simulation_mode])
        if config.max_recordings is not None:
            command.extend(["--max-recordings", str(config.max_recordings)])
        run_name = _dataset_run_name(config.run_name, definition.key, multi_dataset)
        if run_name:
            command.extend(["--run-name", run_name])
        for key, value in sorted(config.filters_by_dataset.get(definition.key, {}).items()):
            formatted_value = _format_subset_filter_value(value)
            if formatted_value:
                command.extend(["--subset", f"{key}={formatted_value}"])
        if config.augmentation in {"reverb", "reverb_noise"}:
            for rir_path in config.rir_paths:
                command.extend(["--rir-paths", rir_path])
        if config.augmentation in {"noise", "reverb_noise"}:
            for noise_type in config.noise_types:
                command.extend(["--noise-type", noise_type])
            for snr in config.snr_db:
                command.extend(["--snr-db", f"{snr:g}"])
        if config.preview:
            command.append("--preview")
            if config.preview_recording_id:
                command.extend(["--preview-recording-id", config.preview_recording_id])
        commands.append(command)
    return commands


def list_available_rirs(project_root: Path) -> list[str]:
    """List available RIR WAV files relative to the MIT RIR Audio folder."""

    rir_root = project_root / RIR_AUDIO_ROOT
    if not rir_root.exists():
        return []
    values: list[str] = []
    for path in sorted(rir_root.rglob("*.wav")):
        values.append(path.relative_to(rir_root).as_posix())
    return values


def default_dataset_keys() -> tuple[str, ...]:
    """Return dataset keys supported by the registry."""

    return tuple(definition.key for definition in list_datasets())


def all_selected_datasets_support_augmentation(dataset_keys: Iterable[str]) -> bool:
    """Return whether augmentation controls should be enabled for this selection."""

    keys = tuple(dataset_keys)
    return not keys or all(get_dataset(key).supports_augmentation for key in keys)


def _dataset_run_name(run_name: str | None, dataset_key: str, multi_dataset: bool) -> str | None:
    if not run_name:
        return None
    if multi_dataset:
        return f"{run_name}_{dataset_key}"
    return run_name


def _format_subset_filter_value(value: tuple[str, ...] | list[str] | str) -> str:
    if isinstance(value, str):
        return value.strip()
    return ",".join(str(item).strip() for item in value if str(item).strip())
