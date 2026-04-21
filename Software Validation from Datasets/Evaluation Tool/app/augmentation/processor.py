"""Runtime augmentation and preview generation."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

from tqdm import tqdm

from app.augmentation.audio import (
    add_noise_at_snr,
    convolve_with_rir,
    load_rir,
    peak_protect,
    read_audio,
    write_wav,
)
from app.augmentation.config import AugmentationCondition, AugmentationPlan
from app.utils.json_utils import write_json


class RuntimeAugmentor:
    """Materialize augmented audio only for the current inference item."""

    def __init__(
        self,
        project_root: Path,
        run_dir: Path,
        plan: AugmentationPlan,
        logger: logging.Logger,
    ) -> None:
        self.project_root = project_root
        self.run_dir = run_dir
        self.plan = plan
        self.logger = logger
        self.temp_dir = run_dir / "temp_audio"
        self._rir_cache: dict[tuple[str, int], object] = {}

    @classmethod
    def from_run_config(
        cls,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> "RuntimeAugmentor":
        """Create an augmentor from saved run configuration."""

        project_root = Path(str(run_config["project_root"]))
        run_dir = Path(str(run_config["run_dir"]))
        augmentation = run_config.get("augmentation", {})
        if not isinstance(augmentation, dict):
            augmentation = {}
        plan = plan_from_jsonable(augmentation)
        return cls(project_root=project_root, run_dir=run_dir, plan=plan, logger=logger)

    def prepare(self) -> None:
        """Create temporary folder for augmented inference audio."""

        if self.plan.mode != "none":
            self.temp_dir.mkdir(parents=True, exist_ok=True)

    def cleanup(self) -> None:
        """Remove temporary augmented files unless explicitly retained."""

        if self.plan.keep_temp_audio:
            return
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @contextlib.contextmanager
    def materialized_record(self, record: dict[str, object]) -> Iterator[dict[str, object]]:
        """Yield a record whose inference path points at source or temp augmented audio."""

        if self.plan.mode == "none":
            current = dict(record)
            current["inference_audio_path"] = current.get("audio_path_resolved")
            current["inference_audio_project_relative"] = current.get("audio_path_project_relative")
            yield current
            return

        temp_path = self._temp_path_for(record)
        try:
            self.write_augmented_audio(record, temp_path)
            current = dict(record)
            current["inference_audio_path"] = str(temp_path)
            current["inference_audio_project_relative"] = None
            yield current
        finally:
            if not self.plan.keep_temp_audio and temp_path.exists():
                temp_path.unlink()

    def write_augmented_audio(self, record: dict[str, object], output_path: Path) -> None:
        """Read source audio, apply the record's condition, and write WAV output."""

        source_path = Path(str(record.get("source_audio_path_resolved") or record["audio_path_resolved"]))
        audio, sample_rate = read_audio(source_path)
        condition = condition_from_record(record)
        augmented = self.apply_condition(audio, sample_rate, condition, str(record["recording_id"]))
        write_wav(output_path, augmented, sample_rate)

    def apply_condition(
        self,
        audio,
        sample_rate: int,
        condition: AugmentationCondition,
        seed_text: str,
    ):
        """Apply one augmentation condition to audio already loaded in memory."""

        augmented = audio
        if condition.rir_path:
            rir_path = self.project_root / condition.rir_path
            cache_key = (condition.rir_path, sample_rate)
            if cache_key not in self._rir_cache:
                self._rir_cache[cache_key] = load_rir(rir_path, sample_rate)
            augmented = convolve_with_rir(augmented, self._rir_cache[cache_key])
        if condition.noise_type and condition.snr_db is not None:
            seed = f"{self.plan.seed}:{seed_text}:{condition.condition_id}"
            augmented = add_noise_at_snr(augmented, condition.noise_type, condition.snr_db, seed)
        return peak_protect(augmented, self.plan.peak_limit)

    def _temp_path_for(self, record: dict[str, object]) -> Path:
        digest = hashlib.sha1(str(record["recording_id"]).encode("utf-8")).hexdigest()[:16]
        return self.temp_dir / f"{digest}.wav"


def expand_records_for_augmentation(
    records: list[dict[str, object]],
    plan: AugmentationPlan,
) -> list[dict[str, object]]:
    """Expand selected records across all augmentation conditions."""

    expanded: list[dict[str, object]] = []
    for record in records:
        source_recording_id = str(record["recording_id"])
        for condition in plan.conditions:
            current = dict(record)
            current["source_recording_id"] = source_recording_id
            current["source_audio_path_resolved"] = record.get("audio_path_resolved")
            current["source_audio_path_project_relative"] = record.get("audio_path_project_relative")
            current["augmentation_condition_id"] = condition.condition_id
            current["augmentation_mode"] = condition.mode
            current["rir_path"] = condition.rir_path
            current["rir_label"] = condition.rir_label
            current["noise_type"] = condition.noise_type
            current["snr_db"] = condition.snr_db
            if condition.mode != "none":
                current["recording_id"] = f"{source_recording_id}__aug_{condition.condition_id}"
            expanded.append(current)
    return expanded


def generate_previews(
    base_records: list[dict[str, object]],
    run_dir: Path,
    project_root: Path,
    plan: AugmentationPlan,
    logger: logging.Logger,
) -> list[dict[str, object]]:
    """Generate saved preview WAVs for one selected source recording."""

    if not plan.preview_enabled:
        return []
    if not base_records:
        return []

    preview_record = _choose_preview_record(base_records, plan.preview_recording_id)
    preview_dir = run_dir / "preview_audio"
    preview_dir.mkdir(parents=True, exist_ok=True)

    augmentor = RuntimeAugmentor(project_root=project_root, run_dir=run_dir, plan=plan, logger=logger)
    manifest: list[dict[str, object]] = []
    for condition in tqdm(plan.conditions, desc="Preview augmentation", unit="condition"):
        condition_record = dict(preview_record)
        condition_record.update(
            {
                "source_recording_id": preview_record["recording_id"],
                "source_audio_path_resolved": preview_record.get("audio_path_resolved"),
                "augmentation_condition_id": condition.condition_id,
                "augmentation_mode": condition.mode,
                "rir_path": condition.rir_path,
                "rir_label": condition.rir_label,
                "noise_type": condition.noise_type,
                "snr_db": condition.snr_db,
            }
        )
        dataset_label = _safe_filename(
            str(preview_record.get("dataset_id") or preview_record.get("dataset") or "dataset")
        )
        source_label = _safe_filename(str(preview_record["recording_id"]))
        output_name = f"{dataset_label}__{source_label}__{condition.condition_id}.wav"
        condition_dir = preview_dir / _safe_filename(condition.condition_id)
        output_path = condition_dir / output_name
        if condition.mode == "none":
            audio, sample_rate = read_audio(Path(str(preview_record["audio_path_resolved"])))
            write_wav(output_path, audio, sample_rate)
        else:
            augmentor.write_augmented_audio(condition_record, output_path)
        manifest.append(
            {
                "source_recording_id": preview_record["recording_id"],
                "condition_id": condition.condition_id,
                "preview_path": output_path.relative_to(run_dir).as_posix(),
                "rir_path": condition.rir_path,
                "noise_type": condition.noise_type,
                "snr_db": condition.snr_db,
            }
        )

    write_json(preview_dir / "preview_manifest.json", {"previews": manifest})
    logger.info("Wrote %d augmentation preview file(s)", len(manifest))
    return manifest


def condition_from_record(record: dict[str, object]) -> AugmentationCondition:
    """Create a condition object from an expanded evaluation record."""

    return AugmentationCondition(
        condition_id=str(record.get("augmentation_condition_id") or "clean"),
        mode=str(record.get("augmentation_mode") or "none"),
        rir_path=_optional_str(record.get("rir_path")),
        rir_label=_optional_str(record.get("rir_label")),
        noise_type=_optional_str(record.get("noise_type")),
        snr_db=_optional_float(record.get("snr_db")),
    )


def plan_from_jsonable(data: dict[str, object]) -> AugmentationPlan:
    """Rebuild an augmentation plan from saved JSON/YAML data."""

    conditions_data = data.get("conditions") or [{"condition_id": "clean", "mode": "none"}]
    conditions = []
    for item in conditions_data:
        if not isinstance(item, dict):
            continue
        conditions.append(
            AugmentationCondition(
                condition_id=str(item.get("condition_id") or "clean"),
                mode=str(item.get("mode") or "none"),
                rir_path=_optional_str(item.get("rir_path")),
                rir_label=_optional_str(item.get("rir_label")),
                noise_type=_optional_str(item.get("noise_type")),
                snr_db=_optional_float(item.get("snr_db")),
            )
        )
    return AugmentationPlan(
        mode=str(data.get("mode") or "none"),
        conditions=tuple(conditions) or (AugmentationCondition("clean", "none"),),
        preview_enabled=bool(data.get("preview_enabled", False)),
        preview_recording_id=_optional_str(data.get("preview_recording_id")),
        seed=int(data.get("seed") or 1337),
        peak_limit=float(data.get("peak_limit") or 0.98),
        keep_temp_audio=bool(data.get("keep_temp_audio", False)),
    )


def total_duration_sec(records: list[dict[str, object]]) -> float:
    """Sum best-available duration fields for selected evaluation records."""

    return float(sum(record_duration_sec(record) for record in records))


def record_duration_sec(record: dict[str, object]) -> float:
    """Return duration from normalized metadata fields."""

    start = _optional_float(record.get("start_sec"))
    end = _optional_float(record.get("end_sec"))
    if start is not None and end is not None and end >= start:
        return end - start
    for key in ("duration_sec", "duration_sec_audio", "duration_sec_manifest"):
        value = _optional_float(record.get(key))
        if value is not None:
            return value
    return 0.0


def _choose_preview_record(
    base_records: list[dict[str, object]],
    preview_recording_id: str | None,
) -> dict[str, object]:
    if preview_recording_id is None:
        return base_records[0]
    for record in base_records:
        if str(record.get("recording_id")) == preview_recording_id:
            return record
    raise ValueError(f"Preview recording_id {preview_recording_id!r} was not in the selected records")


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)[:120]


def _optional_str(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
