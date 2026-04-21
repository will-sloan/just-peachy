"""Configuration and condition expansion for augmentation runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from app.utils.paths import safe_relative_to


RIR_AUDIO_ROOT = Path("Raw Datasets (Not formatted)") / "MIT 271 RIRs" / "Audio"


@dataclass(frozen=True)
class AugmentationCondition:
    """One concrete augmentation condition."""

    condition_id: str
    mode: str
    rir_path: str | None = None
    rir_label: str | None = None
    noise_type: str | None = None
    snr_db: float | None = None

    def to_jsonable(self) -> dict[str, object]:
        """Convert to a JSON-friendly dictionary."""

        return asdict(self)


@dataclass(frozen=True)
class AugmentationPlan:
    """Resolved augmentation configuration for a run."""

    mode: str
    conditions: tuple[AugmentationCondition, ...]
    preview_enabled: bool = False
    preview_recording_id: str | None = None
    seed: int = 1337
    peak_limit: float = 0.98
    keep_temp_audio: bool = False

    def to_jsonable(self) -> dict[str, object]:
        """Convert to a JSON-friendly dictionary."""

        return {
            "mode": self.mode,
            "preview_enabled": self.preview_enabled,
            "preview_recording_id": self.preview_recording_id,
            "seed": self.seed,
            "peak_limit": self.peak_limit,
            "keep_temp_audio": self.keep_temp_audio,
            "conditions": [condition.to_jsonable() for condition in self.conditions],
        }


def build_augmentation_plan(
    project_root: Path,
    mode: str,
    rir_path_values: Iterable[str] | None = None,
    noise_types: Iterable[str] | None = None,
    snr_values: Iterable[float] | None = None,
    preview_enabled: bool = False,
    preview_recording_id: str | None = None,
    seed: int = 1337,
) -> AugmentationPlan:
    """Build a concrete augmentation condition plan from CLI options."""

    if mode == "none":
        return AugmentationPlan(
            mode=mode,
            conditions=(AugmentationCondition(condition_id="clean", mode="none"),),
            preview_enabled=preview_enabled,
            preview_recording_id=preview_recording_id,
            seed=seed,
        )

    needs_reverb = mode in {"reverb", "reverb_noise"}
    needs_noise = mode in {"noise", "reverb_noise"}
    rir_paths = _resolve_rir_paths(project_root, rir_path_values or []) if needs_reverb else []
    if needs_reverb and not rir_paths:
        raise ValueError(
            "--augmentation reverb/reverb_noise requires at least one --rir-paths value. "
            f"Paths can be relative to the project root or to {RIR_AUDIO_ROOT.as_posix()}."
        )

    resolved_noise_types = tuple(noise_types or ("white",)) if needs_noise else (None,)
    resolved_snrs = tuple(float(value) for value in (snr_values or (20.0,))) if needs_noise else (None,)

    conditions: list[AugmentationCondition] = []
    if mode == "reverb":
        for rir_path in rir_paths:
            conditions.append(_condition_for(rir_path=rir_path, project_root=project_root, mode=mode))
    elif mode == "noise":
        for noise_type in resolved_noise_types:
            for snr_db in resolved_snrs:
                conditions.append(_condition_for(mode=mode, noise_type=noise_type, snr_db=snr_db))
    elif mode == "reverb_noise":
        for rir_path in rir_paths:
            for noise_type in resolved_noise_types:
                for snr_db in resolved_snrs:
                    conditions.append(
                        _condition_for(
                            rir_path=rir_path,
                            project_root=project_root,
                            mode=mode,
                            noise_type=noise_type,
                            snr_db=snr_db,
                        )
                    )
    else:
        raise ValueError(f"Unsupported augmentation mode {mode!r}")

    return AugmentationPlan(
        mode=mode,
        conditions=tuple(conditions),
        preview_enabled=preview_enabled,
        preview_recording_id=preview_recording_id,
        seed=seed,
    )


def _resolve_rir_paths(project_root: Path, values: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for value in values:
        candidate = Path(value)
        if candidate.is_absolute() and candidate.exists():
            paths.append(candidate.resolve())
            continue

        project_relative = project_root / candidate
        if project_relative.exists():
            paths.append(project_relative.resolve())
            continue

        rir_relative = project_root / RIR_AUDIO_ROOT / candidate
        if rir_relative.exists():
            paths.append(rir_relative.resolve())
            continue

        raise FileNotFoundError(
            f"Could not find RIR path {value!r}. Try a project-relative path or a file "
            f"name under {RIR_AUDIO_ROOT.as_posix()}."
        )
    return paths


def _condition_for(
    mode: str,
    rir_path: Path | None = None,
    project_root: Path | None = None,
    noise_type: str | None = None,
    snr_db: float | None = None,
) -> AugmentationCondition:
    parts: list[str] = [mode]
    rir_relative: str | None = None
    rir_label: str | None = None
    if rir_path is not None:
        if project_root is None:
            raise ValueError("project_root is required when rir_path is provided")
        rir_relative = safe_relative_to(rir_path, project_root)
        rir_label = rir_path.stem
        parts.append(_safe_id(rir_label))
    if noise_type is not None:
        parts.append(noise_type)
    if snr_db is not None:
        parts.append(f"{snr_db:g}db")
    return AugmentationCondition(
        condition_id="_".join(parts),
        mode=mode,
        rir_path=rir_relative,
        rir_label=rir_label,
        noise_type=noise_type,
        snr_db=snr_db,
    )


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)

