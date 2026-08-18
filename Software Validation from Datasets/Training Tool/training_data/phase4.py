"""Build deterministic Phase-4 training manifests without training models.

Phase 4 consumes the immutable Phase-2 and Phase-3 registries.  It writes only
portable metadata below JP_TRAINING_ROOT: source manifests, development splits,
sampling policies, bundle descriptors, audits, and a successor freeze.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from training_data.common_voice import sha256_file
from training_data.common_voice_phase3 import (
    atomic_json,
    atomic_text,
    markdown_json,
    verify_phase3_freeze,
)
from training_data.registry import _frame_hash, _json_hash, verify_freeze_details


SOURCE_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_TOOL_ROOT = SOURCE_ROOT.parent / "Evaluation Tool"
sys.path.insert(0, str(EVALUATION_TOOL_ROOT))

from app.utils.paths import data_root, model_root, repository_root, training_root  # noqa: E402


PHASE4_SCHEMA = "training-manifest-freeze-phase4.v1"
MANIFEST_SCHEMA = "training-source-manifest-phase4.v1"
SAMPLER_ALGORITHM_VERSION = "dataset_group_source_rotating_view.v1"
SAMPLER_SEED = "just-peachy-phase4-training-sampler-v1"
SUCCESSOR_NAME = "phase4_training_manifests_v1"
EXPECTED_PHASE3_ID = "training_freeze_phase3_086685615728"
EXPECTED_PHASE3_SHA256 = (
    "0866856157288AC5B2FF3D2537EF7A6D11E2C5961320112CBB58FB6AD0AAA3A7"
)
EXPECTED_PHASE2_ID = "training_freeze_7a88aec7492f"
EXPECTED_PHASE2_SHA256 = (
    "7A88AEC7492FDFE2DB8F831DAB5AD383980092DAF4911CB36C0DB22C571F21F8"
)
EXPECTED_EXCLUSION_ID = "evaluation_exclusion_8674fe15c03f"
EXPECTED_EXCLUSION_SHA256 = (
    "8674FE15C03F34AE59E262DB43F59A1AE4E80252B5D76194C1741B229058660B"
)
PHASE2_REGISTRY_ID = "training_registry_a99aad23d118"
PHASE2_REGISTRY_SHA256 = (
    "A99AAD23D118D243A74B35A65AFBF8648CCEA190BD8E2DEBF2325AFD21B95261"
)
COMMON_VOICE_REGISTRY_ID = "common_voice_older_registry_7ca53117c59b"
COMMON_VOICE_REGISTRY_SHA256 = (
    "7CA53117C59BF500CEC469103DD2B4CBB37D6828A0AE23F571FA16E6C1BA3456"
)
COMMON_VOICE_SPLIT_ID = "common_voice_older_split_9237c5d9f9d8"
COMMON_VOICE_SPLIT_SHA256 = (
    "9237C5D9F9D8C2E53AC84A487CD81B3BFC41C997F26A2000D2C0A29281970569"
)
MONITOR_TARGET_HOURS = 5.0


class Phase4Error(RuntimeError):
    """Raised when a Phase-4 stop condition is encountered."""


@dataclass(frozen=True)
class Phase4Paths:
    repository_root: Path
    data_root: Path
    training_root: Path
    model_root: Path
    evaluation_tool_root: Path

    @property
    def phase2_root(self) -> Path:
        return self.training_root / "successors" / "ami_cc_by_4_0_2017_04_10"

    @property
    def phase3_root(self) -> Path:
        return self.training_root / "successors" / "common_voice_26_english_phase3"

    @property
    def phase4_root(self) -> Path:
        return self.training_root / "successors" / SUCCESSOR_NAME

    @property
    def source_manifests(self) -> Path:
        return self.phase4_root / "source_manifests"

    @property
    def bundles(self) -> Path:
        return self.phase4_root / "bundles"

    @property
    def sampling(self) -> Path:
        return self.phase4_root / "sampling"

    @property
    def development(self) -> Path:
        return self.phase4_root / "development"

    @property
    def monitoring(self) -> Path:
        return self.phase4_root / "monitoring"

    @property
    def audits(self) -> Path:
        return self.phase4_root / "audits"

    @property
    def registries(self) -> Path:
        return self.phase4_root / "registries"

    @property
    def policies(self) -> Path:
        return self.phase4_root / "policies"


def default_paths() -> Phase4Paths:
    return Phase4Paths(
        repository_root().path,
        data_root().path,
        training_root().path,
        model_root().path,
        EVALUATION_TOOL_ROOT.resolve(),
    )


def stable_rank(*parts: object) -> str:
    """Return a cross-process deterministic rank; never use Python hash()."""
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def _logical_phase4_path(paths: Phase4Paths, path: Path) -> str:
    return "JP_TRAINING_ROOT:" + path.relative_to(paths.training_root).as_posix()


def _has_absolute_path(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_has_absolute_path(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_absolute_path(item) for item in value)
    if not isinstance(value, str):
        return False
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", value)
        or value.startswith("\\\\")
        or value.startswith("//")
        or (value.startswith("/") and "://" not in value)
    )


def _identity_document(
    payload: dict[str, Any], *, prefix: str, kind: str
) -> dict[str, Any]:
    if _has_absolute_path(payload):
        raise Phase4Error(f"Absolute path found in canonical {kind} payload")
    digest = _json_hash(payload)
    result = dict(payload)
    result[f"{kind}_id"] = f"{prefix}_{digest[:12].lower()}"
    result[f"{kind}_sha256"] = digest
    return result


def _verify_identity_document(document: Mapping[str, Any], *, kind: str) -> bool:
    payload = {
        key: value
        for key, value in document.items()
        if key not in {f"{kind}_id", f"{kind}_sha256"}
    }
    return _json_hash(payload) == document.get(f"{kind}_sha256")


def _write_identity_document(
    path: Path, payload: dict[str, Any], *, prefix: str, kind: str
) -> dict[str, Any]:
    document = _identity_document(payload, prefix=prefix, kind=kind)
    atomic_json(path, document)
    return document


def deterministic_view_index(
    *,
    bundle_id: str,
    epoch_index: int,
    source_group_id: str,
    available_view_count: int,
    sampler_seed: str = SAMPLER_SEED,
    algorithm_version: str = SAMPLER_ALGORITHM_VERSION,
) -> int:
    """Select one sorted acoustic view reproducibly for a future epoch."""
    if epoch_index < 0 or available_view_count <= 0:
        raise ValueError(
            "epoch_index must be non-negative and available_view_count positive"
        )
    digest = hashlib.sha256(
        f"{algorithm_version}|{sampler_seed}|{bundle_id}|{epoch_index}|{source_group_id}".encode(
            "utf-8"
        )
    ).digest()
    return int.from_bytes(digest[:8], "big") % available_view_count


def speaker_probabilities(frame: pd.DataFrame) -> dict[str, float]:
    """Normalize sqrt-duration speaker weights for a TRAIN partition."""
    durations = frame.groupby("speaker_id", dropna=False)["duration_seconds"].sum()
    if durations.empty or bool((durations <= 0).any()):
        raise Phase4Error(
            "Speaker balancing requires positive duration for every speaker"
        )
    masses = durations.map(math.sqrt)
    probabilities = masses / masses.sum()
    return {str(key): float(value) for key, value in probabilities.items()}


def _allocate_counts(sizes: Mapping[str, int], total: int) -> dict[str, int]:
    """Allocate an exact count proportionally using deterministic largest remainder."""
    if total < 0 or total > sum(sizes.values()):
        raise ValueError("Requested allocation is outside available groups")
    nonempty = [key for key, value in sorted(sizes.items()) if value]
    minimum = 1 if total >= len(nonempty) else 0
    allocated = {key: min(minimum, value) for key, value in sizes.items()}
    remaining = total - sum(allocated.values())
    capacity_total = sum(value - allocated[key] for key, value in sizes.items())
    if not remaining:
        return allocated
    exact = {
        key: (
            Decimal(remaining)
            * Decimal(value - allocated[key])
            / Decimal(capacity_total)
        )
        for key, value in sizes.items()
    }
    for key in allocated:
        addition = min(sizes[key] - allocated[key], int(exact[key]))
        allocated[key] += addition
    left = total - sum(allocated.values())
    order = sorted(
        allocated,
        key=lambda key: (
            -(exact[key] - int(exact[key])),
            stable_rank(SAMPLER_SEED, "allocation", key),
            key,
        ),
    )
    for key in order:
        if not left:
            break
        if allocated[key] < sizes[key]:
            allocated[key] += 1
            left -= 1
    if left:
        raise Phase4Error("Could not complete deterministic group allocation")
    return allocated


def _select_fixed_count_by_duration(
    table: pd.DataFrame,
    *,
    key: str,
    count: int,
    target_seconds: float,
    seed_label: str,
) -> set[str]:
    """Use deterministic hashed initialization and improving swaps."""
    values = {
        str(row[key]): float(row["duration_seconds"])
        for row in table[[key, "duration_seconds"]].to_dict("records")
    }
    ranked = sorted(
        values, key=lambda value: (stable_rank(SAMPLER_SEED, seed_label, value), value)
    )
    selected = set(ranked[:count])

    def score(candidate: set[str]) -> tuple[float, str]:
        duration_error = abs(sum(values[item] for item in candidate) - target_seconds)
        tie = stable_rank(SAMPLER_SEED, seed_label, *sorted(candidate))
        return (duration_error, tie)

    current = score(selected)
    while True:
        best = current
        best_set: set[str] | None = None
        for old in sorted(selected):
            for new in sorted(set(values) - selected):
                candidate = (selected - {old}) | {new}
                candidate_score = score(candidate)
                if candidate_score < best:
                    best = candidate_score
                    best_set = candidate
        if best_set is None:
            break
        selected, current = best_set, best
    return selected


def ami_dev_meetings(frame: pd.DataFrame) -> set[str]:
    """Select a deterministic, meeting-disjoint, stratified ~10% AMI DEV set."""
    unique = frame.sort_values("source_item_id", kind="mergesort").drop_duplicates(
        "source_utterance_id"
    )
    groups = unique.groupby("meeting_id", as_index=False)["duration_seconds"].sum()
    groups["stratum"] = (
        groups["meeting_id"].astype(str).str.extract(r"^([A-Za-z]+)", expand=False)
    )
    target_count = max(1, round(len(groups) * 0.10))
    counts = _allocate_counts(groups.groupby("stratum").size().to_dict(), target_count)
    selected: set[str] = set()
    for stratum, part in groups.groupby("stratum", sort=True):
        quota = counts[str(stratum)]
        selected |= _select_fixed_count_by_duration(
            part,
            key="meeting_id",
            count=quota,
            target_seconds=float(part["duration_seconds"].sum()) * 0.10,
            seed_label=f"ami-dev-{stratum}",
        )
    return selected


def chime_dev_sessions(frame: pd.DataFrame) -> set[str]:
    """Select two CHiME sessions, honoring its official eval strata when present."""
    metadata = frame.groupby("session_id").agg(
        duration_seconds=("duration_seconds", "sum"),
        speakers=("speaker_id", lambda values: frozenset(map(str, values.dropna()))),
        upstream_split=(
            "upstream_split",
            lambda values: ",".join(sorted(set(map(str, values.dropna())))),
        ),
    )
    upstream_eval = sorted(
        str(key) for key, row in metadata.iterrows() if row["upstream_split"] == "eval"
    )
    if len(upstream_eval) == 2:
        return set(upstream_eval)
    target = float(metadata["duration_seconds"].sum()) * (2 / len(metadata))
    candidates: list[tuple[tuple[Any, ...], set[str]]] = []
    for pair in itertools.combinations(map(str, metadata.index), 2):
        speakers = metadata.loc[list(pair), "speakers"]
        coverage = len(set().union(*speakers))
        duration = float(metadata.loc[list(pair), "duration_seconds"].sum())
        score = (
            -coverage,
            abs(duration - target),
            stable_rank(SAMPLER_SEED, "chime-dev", *pair),
        )
        candidates.append((score, set(pair)))
    return min(candidates, key=lambda item: item[0])[1]


def voices_dev_speakers(frame: pd.DataFrame) -> set[str]:
    """Select ~10% VOiCES speakers while preserving upstream strata."""
    unique = frame.sort_values("source_item_id", kind="mergesort").drop_duplicates(
        "source_utterance_id"
    )
    speakers = unique.groupby("speaker_id", as_index=False).agg(
        duration_seconds=("duration_seconds", "sum"),
        stratum=(
            "upstream_split",
            lambda values: "+".join(sorted(set(map(str, values.dropna())))),
        ),
    )
    target_count = max(1, round(len(speakers) * 0.10))
    counts = _allocate_counts(
        speakers.groupby("stratum").size().to_dict(), target_count
    )
    selected: set[str] = set()
    for stratum, part in speakers.groupby("stratum", sort=True):
        selected |= _select_fixed_count_by_duration(
            part,
            key="speaker_id",
            count=counts[str(stratum)],
            target_seconds=float(part["duration_seconds"].sum()) * 0.10,
            seed_label=f"voices-dev-{stratum}",
        )
    return selected


def cmu_dev_speakers(frame: pd.DataFrame) -> set[str]:
    """Choose four of 18 speakers using deterministic accent-aware balancing."""
    speakers = frame.groupby("speaker_id", as_index=False).agg(
        duration_seconds=("duration_seconds", "sum"),
        accent=(
            "accent",
            lambda values: "+".join(sorted(set(map(str, values.dropna()))))
            or "unspecified",
        ),
    )
    count = max(1, round(len(speakers) * 0.20))
    total_duration = float(speakers["duration_seconds"].sum())
    overall = speakers["accent"].value_counts(normalize=True).to_dict()
    rows = {str(row.speaker_id): row for row in speakers.itertuples(index=False)}
    candidates: list[tuple[tuple[Any, ...], set[str]]] = []
    for combination in itertools.combinations(sorted(rows), count):
        chosen = [rows[item] for item in combination]
        distribution = Counter(str(row.accent) for row in chosen)
        l1 = sum(
            abs(distribution.get(accent, 0) / count - proportion)
            for accent, proportion in overall.items()
        )
        duration_error = abs(
            sum(float(row.duration_seconds) for row in chosen) / total_duration - 0.20
        )
        coverage = len(distribution)
        score = (
            round(l1, 15),
            round(duration_error, 15),
            -coverage,
            stable_rank(SAMPLER_SEED, "cmu-dev", *combination),
        )
        candidates.append((score, set(combination)))
    return min(candidates, key=lambda item: item[0])[1]


def clean_monitor_rows(
    librispeech: pd.DataFrame, *, forbidden_cross_keys: set[str]
) -> pd.DataFrame:
    """Select about five hours with at most one row per speaker for broad coverage."""
    candidates = librispeech.loc[
        librispeech["strict_training_eligible"].fillna(False)
        & ~librispeech["cross_source_key"].astype("string").isin(forbidden_cross_keys)
    ].copy()
    candidates["_item_rank"] = candidates.apply(
        lambda row: stable_rank(
            SAMPLER_SEED, "monitor-item", row["speaker_id"], row["source_item_id"]
        ),
        axis=1,
    )
    first = (
        candidates.sort_values(
            ["speaker_id", "_item_rank", "source_item_id"], kind="mergesort"
        )
        .drop_duplicates("speaker_id")
        .copy()
    )
    first["_speaker_rank"] = first["speaker_id"].map(
        lambda value: stable_rank(SAMPLER_SEED, "monitor-speaker", value)
    )
    first = first.sort_values(
        ["_speaker_rank", "speaker_id"], kind="mergesort"
    ).reset_index(drop=True)
    cumulative = first["duration_seconds"].cumsum()
    target = MONITOR_TARGET_HOURS * 3600
    best_index = int((cumulative - target).abs().idxmin())
    selected = first.iloc[: best_index + 1].drop(
        columns=["_item_rank", "_speaker_rank"]
    )
    if selected.empty:
        raise Phase4Error("Could not construct the clean regression monitor")
    return selected


def dataset_weights(hours: Mapping[str, float]) -> dict[str, dict[str, str]]:
    """Compute sqrt-effective-hour probabilities with VOiCES floor and CMU cap."""
    if not hours or any(value <= 0 for value in hours.values()):
        raise ValueError("Every dataset must have positive effective TRAIN hours")
    getcontext().prec = 50
    decimal_hours = {key: Decimal(str(value)) for key, value in hours.items()}
    masses = {key: value.sqrt() for key, value in decimal_hours.items()}
    mass_sum = sum(masses.values(), Decimal(0))
    pre = {key: value / mass_sum for key, value in masses.items()}
    final = dict(pre)
    if "voices" in final and final["voices"] < Decimal("0.10"):
        remaining_mass = sum(
            (value for key, value in masses.items() if key != "voices"), Decimal(0)
        )
        final = {
            key: Decimal("0.10")
            if key == "voices"
            else Decimal("0.90") * masses[key] / remaining_mass
            for key in masses
        }
    if (
        len(final) > 1
        and "cmu_arctic" in final
        and final["cmu_arctic"] > Decimal("0.10")
    ):
        fixed = {"cmu_arctic": Decimal("0.10")}
        if "voices" in final and final["voices"] == Decimal("0.10"):
            fixed["voices"] = Decimal("0.10")
        free = [key for key in masses if key not in fixed]
        remaining = Decimal(1) - sum(fixed.values(), Decimal(0))
        free_mass = sum((masses[key] for key in free), Decimal(0))
        final = {**fixed, **{key: remaining * masses[key] / free_mass for key in free}}
    residual = Decimal(1) - sum(final.values(), Decimal(0))
    if residual:
        # Decimal division/square roots can leave a final-place residue.  Put it
        # on one non-constrained dataset deterministically so the serialized
        # vector sums to exactly one without moving the VOiCES floor or CMU cap.
        adjustable = sorted(
            key
            for key in final
            if not (key == "voices" and final[key] == Decimal("0.10"))
            and not (key == "cmu_arctic" and final[key] == Decimal("0.10"))
        )
        if not adjustable:
            adjustable = sorted(final)
        final[adjustable[-1]] += residual
    result: dict[str, dict[str, str]] = {}
    for key in hours:
        result[key] = {
            "effective_unique_source_hours": str(decimal_hours[key]),
            "sqrt_hour_mass": str(masses[key]),
            "pre_floor_probability": str(pre[key]),
            "post_floor_probability": str(final[key]),
            "final_probability": str(final[key]),
        }
    if sum(
        (Decimal(item["final_probability"]) for item in result.values()), Decimal(0)
    ) != Decimal(1):
        raise Phase4Error("Dataset probabilities do not sum to one")
    return result


def _manifest_columns() -> list[str]:
    return [
        "manifest_schema_version",
        "phase3_parent_freeze_id",
        "phase3_parent_freeze_sha256",
        "dataset_id",
        "dataset_version",
        "source_registry_id",
        "source_registry_row_id",
        "training_role",
        "training_eligible_for_experiment",
        "strictness_class",
        "audio_root_id",
        "audio_relative_path",
        "audio_sha256",
        "duration_seconds",
        "raw_transcript",
        "transcript_sha256",
        "speaker_id",
        "speaker_group_id",
        "session_id",
        "meeting_id",
        "source_utterance_id",
        "source_recording_id",
        "source_group_id",
        "acoustic_view_group_id",
        "acoustic_view_id",
        "acoustic_view_count",
        "age_label",
        "normalized_age_bin",
        "accent_metadata",
        "license_id",
        "commercial_training_status",
        "commercial_release_review_status",
        "attribution_required",
        "sharealike_flag",
        "evaluation_exact_match",
        "evaluation_group_match",
        "evaluation_cross_dataset_match",
        "evaluation_content_hash_match",
        "sampling_group_type",
        "sampling_group_id",
        "sampling_group_probability",
    ]


def _source_configuration(dataset: str) -> dict[str, str]:
    return {
        "ami": {
            "source": "source_utterance_id",
            "sampling": "meeting_id",
            "sampling_type": "meeting",
        },
        "chime6": {
            "source": "source_utterance_id",
            "sampling": "session_id",
            "sampling_type": "session",
        },
        "voices": {
            "source": "source_utterance_id",
            "sampling": "speaker_id",
            "sampling_type": "source_speaker",
        },
        "cmu_arctic": {
            "source": "source_item_id",
            "sampling": "speaker_id",
            "sampling_type": "speaker",
        },
        "librispeech": {
            "source": "source_item_id",
            "sampling": "speaker_id",
            "sampling_type": "speaker",
        },
    }[dataset]


def _add_sampling_probabilities(manifest: pd.DataFrame, *, role: str) -> None:
    manifest["sampling_group_probability"] = pd.NA
    if role != "train":
        return
    unique = manifest.sort_values(
        "source_registry_row_id", kind="mergesort"
    ).drop_duplicates("source_group_id")
    durations = unique.groupby("sampling_group_id")["duration_seconds"].sum()
    masses = durations.map(math.sqrt)
    probabilities = masses / masses.sum()
    manifest["sampling_group_probability"] = (
        manifest["sampling_group_id"].map(probabilities).astype(float)
    )


def phase2_manifest(
    frame: pd.DataFrame,
    *,
    dataset: str,
    role: str,
    strictness: str,
    parent: Mapping[str, Any],
    training_eligible: bool = True,
) -> pd.DataFrame:
    config = _source_configuration(dataset)
    source_ids = frame[config["source"]].astype("string")
    view_counts = source_ids.value_counts(dropna=False)
    content_hash_match = (
        frame["evaluation_content_hash_match"]
        if "evaluation_content_hash_match" in frame
        else False
    )
    manifest = pd.DataFrame(
        {
            "manifest_schema_version": MANIFEST_SCHEMA,
            "phase3_parent_freeze_id": parent["training_data_freeze_id"],
            "phase3_parent_freeze_sha256": parent["training_data_freeze_sha256"],
            "dataset_id": dataset,
            "dataset_version": frame["dataset_version"],
            "source_registry_id": PHASE2_REGISTRY_ID,
            "source_registry_row_id": frame["source_item_id"],
            "training_role": role,
            "training_eligible_for_experiment": bool(
                training_eligible and role == "train"
            ),
            "strictness_class": strictness,
            "audio_root_id": "JP_DATA_ROOT",
            "audio_relative_path": frame["source_audio_logical_path"],
            "audio_sha256": pd.NA,
            "duration_seconds": frame["duration_seconds"],
            "raw_transcript": frame["transcript"],
            "transcript_sha256": frame["transcript_sha256"],
            "speaker_id": frame["speaker_id"],
            "speaker_group_id": frame["speaker_group_id"],
            "session_id": frame["session_id"],
            "meeting_id": frame["meeting_id"],
            "source_utterance_id": frame["source_utterance_id"],
            "source_recording_id": frame["source_recording_id"],
            "source_group_id": dataset + ":source:" + source_ids,
            "acoustic_view_group_id": dataset + ":view-family:" + source_ids,
            "acoustic_view_id": frame["source_item_id"],
            "acoustic_view_count": source_ids.map(view_counts).astype("Int64"),
            "age_label": frame["age_metadata"],
            "normalized_age_bin": pd.NA,
            "accent_metadata": frame["accent"],
            "license_id": frame["license_id"],
            "commercial_training_status": frame["commercial_training_status"],
            "commercial_release_review_status": frame[
                "commercial_release_review_status"
            ],
            "attribution_required": frame["attribution_required"],
            "sharealike_flag": frame["sharealike_flag"],
            "evaluation_exact_match": frame["evaluation_exact_match"],
            "evaluation_group_match": frame["evaluation_group_match"],
            "evaluation_cross_dataset_match": frame["evaluation_cross_dataset_match"],
            "evaluation_content_hash_match": content_hash_match,
            "sampling_group_type": config["sampling_type"],
            "sampling_group_id": dataset
            + ":sampling:"
            + frame[config["sampling"]].astype("string"),
        }
    )
    _add_sampling_probabilities(manifest, role=role)
    return (
        manifest[_manifest_columns()]
        .sort_values("source_registry_row_id", kind="mergesort")
        .reset_index(drop=True)
    )


def common_voice_manifest(
    frame: pd.DataFrame, *, role: str, parent: Mapping[str, Any]
) -> pd.DataFrame:
    source_ids = frame["source_item_id"].astype("string")
    manifest = pd.DataFrame(
        {
            "manifest_schema_version": MANIFEST_SCHEMA,
            "phase3_parent_freeze_id": parent["training_data_freeze_id"],
            "phase3_parent_freeze_sha256": parent["training_data_freeze_sha256"],
            "dataset_id": "common_voice",
            "dataset_version": frame["dataset_version"],
            "source_registry_id": COMMON_VOICE_REGISTRY_ID,
            "source_registry_row_id": frame["source_item_id"],
            "training_role": role,
            "training_eligible_for_experiment": role == "train",
            "strictness_class": "strict",
            "audio_root_id": "JP_TRAINING_ROOT",
            "audio_relative_path": (
                "datasets/common_voice/english/cv-corpus-26.0-2026-06-12/prepared/en/"
                + frame["prepared_audio_relative_path"].astype("string")
            ),
            "audio_sha256": frame["audio_sha256"],
            "duration_seconds": frame["duration_seconds"],
            "raw_transcript": frame["raw_transcript"],
            "transcript_sha256": frame["transcript_sha256"],
            "speaker_id": frame["speaker_id"],
            "speaker_group_id": frame["speaker_group_id"],
            "session_id": pd.NA,
            "meeting_id": pd.NA,
            "source_utterance_id": frame["source_utterance_id"],
            "source_recording_id": frame["source_recording_id"],
            "source_group_id": "common_voice:source:" + source_ids,
            "acoustic_view_group_id": "common_voice:view-family:" + source_ids,
            "acoustic_view_id": frame["source_item_id"],
            "acoustic_view_count": pd.Series(1, index=frame.index, dtype="Int64"),
            "age_label": frame["source_age_label"],
            "normalized_age_bin": frame["normalized_age_bin"],
            "accent_metadata": frame["accents"],
            "license_id": frame["license_id"],
            "commercial_training_status": frame["commercial_training_status"],
            "commercial_release_review_status": frame[
                "commercial_release_review_status"
            ],
            "attribution_required": frame["attribution_required"],
            "sharealike_flag": frame["sharealike_flag"],
            "evaluation_exact_match": frame["evaluation_exact_match"],
            "evaluation_group_match": frame["evaluation_group_match"],
            "evaluation_cross_dataset_match": frame["evaluation_cross_dataset_match"],
            "evaluation_content_hash_match": frame["evaluation_content_hash_match"],
            "sampling_group_type": "speaker",
            "sampling_group_id": "common_voice:sampling:"
            + frame["speaker_id"].astype("string"),
        }
    )
    _add_sampling_probabilities(manifest, role=role)
    return (
        manifest[_manifest_columns()]
        .sort_values("source_registry_row_id", kind="mergesort")
        .reset_index(drop=True)
    )


def manifest_summary(frame: pd.DataFrame) -> dict[str, Any]:
    unique = frame.sort_values(
        "source_registry_row_id", kind="mergesort"
    ).drop_duplicates("source_group_id")
    return {
        "record_count": int(len(frame)),
        "physical_hours": float(frame["duration_seconds"].sum()) / 3600,
        "effective_unique_source_hours": float(unique["duration_seconds"].sum()) / 3600,
        "speaker_count": int(frame["speaker_id"].nunique(dropna=True)),
        "group_count": int(frame["source_group_id"].nunique(dropna=True)),
        "sampling_group_count": int(frame["sampling_group_id"].nunique(dropna=True)),
        "meeting_count": int(frame["meeting_id"].nunique(dropna=True)),
        "session_count": int(frame["session_id"].nunique(dropna=True)),
        "source_utterance_count": int(
            frame["source_utterance_id"].nunique(dropna=True)
        ),
        "acoustic_view_family_count": int(
            frame["acoustic_view_group_id"].nunique(dropna=True)
        ),
        "license_summary": {
            str(key): int(value)
            for key, value in frame["license_id"]
            .value_counts(dropna=False)
            .sort_index()
            .items()
        },
        "role": str(frame["training_role"].iloc[0]),
        "strictness_class": str(frame["strictness_class"].iloc[0]),
        "training_eligible_for_experiment": bool(
            frame["training_eligible_for_experiment"].any()
        ),
    }


def write_manifest(
    paths: Phase4Paths,
    *,
    logical_name: str,
    frame: pd.DataFrame,
    subdirectory: str = "source_manifests",
) -> dict[str, Any]:
    directory = paths.phase4_root / subdirectory
    path = directory / f"{logical_name.lower()}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    if any(
        frame[column].dropna().astype(str).map(_has_absolute_path).any()
        for column in frame.select_dtypes(include=["object", "string"]).columns
    ):
        raise Phase4Error(f"Absolute path found in {logical_name}")
    frame.to_parquet(path, index=False)
    persisted = pd.read_parquet(path)
    digest = _frame_hash(persisted)
    descriptor = {
        "manifest_name": logical_name,
        "manifest_id": f"{logical_name.lower()}_manifest_{digest[:12].lower()}",
        "manifest_sha256": digest,
        "manifest_schema_version": MANIFEST_SCHEMA,
        "logical_path": _logical_phase4_path(paths, path),
        "phase3_parent_freeze_id": EXPECTED_PHASE3_ID,
        "phase3_parent_freeze_sha256": EXPECTED_PHASE3_SHA256,
        **manifest_summary(persisted),
    }
    atomic_json(directory / f"{logical_name.lower()}.manifest.json", descriptor)
    return descriptor


def overlap_audit(train: pd.DataFrame, dev: pd.DataFrame) -> dict[str, int]:
    def overlap(column: str) -> int:
        left = set(train[column].dropna().astype(str))
        right = set(dev[column].dropna().astype(str))
        return len(left & right)

    return {
        "exact_item_overlap": overlap("source_registry_row_id"),
        "source_utterance_overlap": overlap("source_utterance_id"),
        "speaker_overlap": overlap("speaker_id"),
        "meeting_overlap": overlap("meeting_id"),
        "session_overlap": overlap("session_id"),
        "acoustic_view_family_overlap": overlap("acoustic_view_group_id"),
    }


def _raw_overlap_audit(
    train: pd.DataFrame, dev: pd.DataFrame, *, dataset: str
) -> dict[str, int]:
    source_column = (
        "source_item_id"
        if dataset in {"cmu_arctic", "librispeech"}
        else "source_utterance_id"
    )

    def overlap(column: str) -> int:
        left = set(train[column].dropna().astype(str))
        right = set(dev[column].dropna().astype(str))
        return len(left & right)

    return {
        "exact_item_overlap": overlap("source_item_id"),
        "source_utterance_overlap": overlap("source_utterance_id"),
        "source_group_overlap": overlap(source_column),
        "speaker_overlap": overlap("speaker_id"),
        "meeting_overlap": overlap("meeting_id"),
        "session_overlap": overlap("session_id"),
        "acoustic_view_family_overlap": overlap(source_column),
    }


def verify_parent_inputs(paths: Phase4Paths) -> dict[str, Any]:
    phase2_freeze_path = (
        paths.phase2_root / "registries" / "training_data_freeze_manifest.json"
    )
    phase3_freeze_path = (
        paths.phase3_root / "registries" / "training_data_freeze_phase3.json"
    )
    phase2_registry_path = (
        paths.phase2_root / "registries" / "training_data_registry.parquet"
    )
    exclusion_path = (
        paths.phase2_root / "registries" / "evaluation_exclusion_index.parquet"
    )
    common_voice_registry_path = (
        paths.phase3_root / "registries" / "common_voice_older_registry.parquet"
    )
    common_voice_split_path = (
        paths.phase3_root / "registries" / "common_voice_older_split.parquet"
    )

    phase2 = json.loads(phase2_freeze_path.read_text(encoding="utf-8"))
    phase3 = json.loads(phase3_freeze_path.read_text(encoding="utf-8"))
    if (
        phase2.get("training_data_freeze_id") != EXPECTED_PHASE2_ID
        or phase2.get("training_data_freeze_sha256") != EXPECTED_PHASE2_SHA256
    ):
        raise Phase4Error(
            "Phase-2 parent identity is not the expected corrected freeze"
        )
    phase2_check = verify_freeze_details(phase2_freeze_path, paths.evaluation_tool_root)
    if not phase2_check["valid"]:
        raise Phase4Error(
            f"Phase-2 parent verification failed: {phase2_check['reasons']}"
        )
    if (
        phase3.get("training_data_freeze_id") != EXPECTED_PHASE3_ID
        or phase3.get("training_data_freeze_sha256") != EXPECTED_PHASE3_SHA256
    ):
        raise Phase4Error("Phase-3 parent identity is not authoritative")
    phase3_check = verify_phase3_freeze(
        phase3_freeze_path,
        parent_freeze_path=phase2_freeze_path,
        registry_path=common_voice_registry_path,
        split_path=common_voice_split_path,
    )
    if not phase3_check["valid"]:
        raise Phase4Error(
            f"Phase-3 parent verification failed: {phase3_check['reasons']}"
        )
    if phase3["parent_freeze"]["evaluation_exclusion_index"] != {
        "id": EXPECTED_EXCLUSION_ID,
        "sha256": EXPECTED_EXCLUSION_SHA256,
    }:
        raise Phase4Error("Evaluation exclusion identity does not match Phase 3")
    return {
        "phase2": phase2,
        "phase3": phase3,
        "phase2_check": phase2_check,
        "phase3_check": phase3_check,
        "paths": {
            "phase2_freeze": phase2_freeze_path,
            "phase3_freeze": phase3_freeze_path,
            "phase2_registry": phase2_registry_path,
            "evaluation_exclusion": exclusion_path,
            "common_voice_registry": common_voice_registry_path,
            "common_voice_split": common_voice_split_path,
        },
    }


def protected_snapshot(paths: Phase4Paths) -> dict[str, str]:
    """Hash parents, frozen manifests, Stage-10/11 data, and scenario catalogs."""
    phase3_audit_path = paths.phase3_root / "audits" / "phase3_immutability_audit.json"
    phase3_audit = json.loads(phase3_audit_path.read_text(encoding="utf-8"))
    targets: dict[str, Path] = {}
    for item in phase3_audit["files"]:
        logical = str(item["path"])
        if logical.startswith("JP_TRAINING_ROOT:"):
            target = paths.training_root / logical.split(":", 1)[1]
        elif logical.startswith("EVALUATION_TOOL:"):
            target = paths.evaluation_tool_root / logical.split(":", 1)[1]
        else:
            continue
        targets[logical] = target
    additions = {
        "JP_TRAINING_ROOT:successors/common_voice_26_english_phase3/registries/training_data_freeze_phase3.json": paths.phase3_root
        / "registries"
        / "training_data_freeze_phase3.json",
        "JP_TRAINING_ROOT:successors/common_voice_26_english_phase3/registries/common_voice_older_registry.parquet": paths.phase3_root
        / "registries"
        / "common_voice_older_registry.parquet",
        "JP_TRAINING_ROOT:successors/common_voice_26_english_phase3/registries/common_voice_older_split.parquet": paths.phase3_root
        / "registries"
        / "common_voice_older_split.parquet",
    }
    targets.update(additions)
    benchmark_root = paths.evaluation_tool_root / "benchmarks"
    for candidate in benchmark_root.rglob("*"):
        if candidate.is_file() and (
            "scenario" in candidate.name.casefold()
            or "catalog" in candidate.name.casefold()
        ):
            logical = (
                "EVALUATION_TOOL:"
                + candidate.relative_to(paths.evaluation_tool_root).as_posix()
            )
            targets[logical] = candidate
    missing = [logical for logical, target in targets.items() if not target.is_file()]
    if missing:
        raise Phase4Error(f"Protected artifacts are missing: {missing[:3]}")
    return {
        logical: sha256_file(target)
        for logical, target in sorted(
            targets.items(), key=lambda item: item[0].casefold()
        )
    }


def _policy_payloads(*, monitor_manifest_id: str) -> dict[str, dict[str, Any]]:
    return {
        "source_grouping": {
            "schema_version": "source-grouping-policy.v1",
            "phase3_parent_freeze_id": EXPECTED_PHASE3_ID,
            "dataset_grouping": {
                "common_voice": {
                    "source_unit": "validated clip",
                    "partition_unit": "speaker",
                },
                "ami": {
                    "source_unit": "source_utterance_id",
                    "partition_unit": "meeting_id",
                },
                "chime6": {
                    "source_unit": "registered canonical utterance",
                    "partition_unit": "session_id",
                },
                "voices": {
                    "source_unit": "source_utterance_id",
                    "partition_unit": "source speaker",
                },
                "cmu_arctic": {
                    "source_unit": "speaker recording",
                    "partition_unit": "speaker_id",
                },
                "librispeech_monitor": {
                    "source_unit": "utterance",
                    "partition_unit": "speaker_id",
                },
            },
            "rule": "all acoustic views of one source unit remain in one role",
        },
        "acoustic_view": {
            "schema_version": "acoustic-view-policy.v1",
            "sampler_algorithm_version": SAMPLER_ALGORITHM_VERSION,
            "sampler_seed": SAMPLER_SEED,
            "selection_hash": "sha256(algorithm_version|seed|bundle_id|epoch_index|source_group_id)",
            "view_order": "acoustic_view_id ascending",
            "dataset_policy": {
                "ami": {
                    "views_per_source_per_epoch": 1,
                    "selection": "deterministic rotating microphone view",
                },
                "voices": {
                    "views_per_source_per_epoch": 1,
                    "selection": "deterministic rotating retransmission",
                },
                "chime6": {
                    "views_per_source_per_epoch": 1,
                    "selection": "registered canonical row; no synthetic views",
                },
                "common_voice": {
                    "views_per_source_per_epoch": 1,
                    "selection": "only registered clip",
                },
                "cmu_arctic": {
                    "views_per_source_per_epoch": 1,
                    "selection": "only registered recording",
                },
            },
        },
        "speaker_balancing": {
            "schema_version": "speaker-balancing-policy.v1",
            "common_voice": {
                "hierarchy": ["dataset", "speaker", "clip"],
                "speaker_mass": "sqrt(total TRAIN duration for speaker)",
                "clip_selection": "uniform within selected speaker",
                "age_quota": "none",
                "accent_quota": "none",
            },
            "cmu_arctic": {
                "hierarchy": ["dataset", "speaker", "recording"],
                "speaker_mass": "sqrt(total exploratory TRAIN duration for speaker)",
            },
            "ami": {
                "hierarchy": [
                    "dataset",
                    "meeting",
                    "source utterance",
                    "one rotating view",
                ],
                "meeting_mass": "sqrt(unique source duration)",
            },
            "chime6": {
                "hierarchy": ["dataset", "session", "source item"],
                "session_mass": "sqrt(source duration)",
            },
            "voices": {
                "hierarchy": [
                    "dataset",
                    "source speaker",
                    "source utterance",
                    "one rotating view",
                ],
                "speaker_mass": "sqrt(unique source duration)",
            },
        },
        "dataset_weighting": {
            "schema_version": "dataset-weighting-policy.v1",
            "algorithm": "sqrt_train_effective_unique_source_hours.v1",
            "voices_minimum_probability": "0.10",
            "combined_bundle_cmu_maximum_probability": "0.10",
            "cmu_minimum_probability": "0",
            "single_source_bundle_rule": "the sole dataset has probability 1; floors/caps apply only to mixed bundles",
            "numerical_method": "base-10 Decimal with precision 50",
            "physical_row_count_used_as_mass": False,
            "physical_multiview_hours_used_as_mass": False,
        },
        "development_selection": {
            "schema_version": "development-selection-policy.v1",
            "seed": SAMPLER_SEED,
            "common_voice": "preserve Phase-3 train/dev/heldout roles exactly",
            "ami": "meeting-disjoint, leading-series stratified, deterministic duration-improving swaps, approximately 10% unique-source hours",
            "chime6": "10 TRAIN sessions and the two official eval-stratum sessions as DEV; deterministic fallback if metadata changes",
            "voices": "source-speaker-disjoint, upstream-stratified, approximately 10% unique-source hours",
            "cmu_arctic": "four of eighteen speakers in DEV using accent-distribution and duration objectives; exploratory remains exploratory",
            "additional_sealed_final_holdout": False,
        },
        "checkpoint_selection": {
            "schema_version": "checkpoint-selection-policy.v1",
            "single_source_objective": "source DEV WER",
            "combined_objective": "equal-weight macro mean of per-domain DEV WER",
            "per_domain_wer_reported": True,
            "clean_regression_monitor_id": monitor_manifest_id,
            "clean_monitor_relative_wer_regression_warning": "0.15",
            "monitor_is_secondary": True,
            "monitor_used_for_gradients": False,
        },
        "cmu_exploratory": {
            "schema_version": "cmu-exploratory-policy.v1",
            "training_policy": "relaxed_speaker_overlap_exploratory_v1",
            "strict_training_available": False,
            "exact_audio_leakage_allowed": False,
            "evaluation_speaker_group_overlap": True,
            "experiment_class": "exploratory",
            "confirmatory_generalization_claim_allowed": False,
            "controlled_cmu_score_status": "descriptive_in_domain_with_speaker_overlap",
            "full_large_aggregate_including_cmu_confirmatory": False,
            "matched_large_non_cmu_aggregate_confirmatory": True,
            "non_cmu_cross_domain_results_confirmatory": True,
            "common_voice_heldout_result_confirmatory": True,
        },
        "large_benchmark_use": {
            "schema_version": "large-benchmark-use-policy.v1",
            "large_is_hyperparameter_development_set": False,
            "required_sequence": [
                "train",
                "dev",
                "checkpoint decision",
                "candidate identity freeze",
                "Large evaluation",
            ],
            "phase4_large_evaluation": False,
            "large_result_retuning_requires_new_experiment_generation": True,
            "additional_sealed_final_holdout": False,
            "leave_one_domain_out_experiments": False,
        },
        "license": {
            "schema_version": "phase4-license-propagation-policy.v1",
            "datasets": {
                "common_voice": {
                    "license_id": "CC0-1.0",
                    "attribution_required": False,
                    "sharealike_flag": False,
                    "commercial_training_status": "allowed",
                    "commercial_model_release_review_required": False,
                },
                "cmu_arctic": {
                    "license_id": "CC0-1.0",
                    "attribution_required": False,
                    "sharealike_flag": False,
                    "commercial_training_status": "allowed",
                    "commercial_model_release_review_required": False,
                },
                "ami": {
                    "license_id": "CC-BY-4.0",
                    "attribution_required": True,
                    "sharealike_flag": False,
                    "commercial_training_status": "allowed_with_attribution",
                    "commercial_model_release_review_required": False,
                },
                "voices": {
                    "license_id": "CC-BY-4.0",
                    "attribution_required": True,
                    "sharealike_flag": False,
                    "commercial_training_status": "allowed_with_attribution",
                    "commercial_model_release_review_required": False,
                },
                "chime6": {
                    "license_id": "CC-BY-SA-4.0",
                    "attribution_required": True,
                    "sharealike_flag": True,
                    "commercial_training_status": "technically_eligible_review_gated",
                    "commercial_model_release_review_required": True,
                },
                "librispeech_monitor": {
                    "license_id": "CC-BY-4.0",
                    "attribution_required": True,
                    "sharealike_flag": False,
                    "commercial_training_status": "monitor_only",
                    "commercial_model_release_review_required": False,
                },
            },
            "propagation_rule": "union restrictions; a permissive source never erases another source's review requirement",
        },
    }


def write_policies(
    paths: Phase4Paths, *, monitor_manifest_id: str
) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for name, payload in _policy_payloads(
        monitor_manifest_id=monitor_manifest_id
    ).items():
        document = _write_identity_document(
            paths.policies / f"{name}_policy.json",
            payload,
            prefix=f"{name}_policy",
            kind="policy",
        )
        document["logical_path"] = _logical_phase4_path(
            paths, paths.policies / f"{name}_policy.json"
        )
        documents[name] = document
    return documents


def _bundle_license(datasets: Sequence[str]) -> dict[str, Any]:
    terms = _policy_payloads(monitor_manifest_id="not-applicable")["license"][
        "datasets"
    ]
    selected = [terms[dataset] for dataset in datasets]
    return {
        "license_composition": sorted({item["license_id"] for item in selected}),
        "attribution_required": any(item["attribution_required"] for item in selected),
        "sharealike_flag": any(item["sharealike_flag"] for item in selected),
        "commercial_training_status": "technically_eligible_review_gated"
        if "chime6" in datasets
        else "allowed",
        "commercial_model_release_review_required": any(
            item["commercial_model_release_review_required"] for item in selected
        ),
        "chime_used_in_training": "chime6" in datasets,
    }


def initialization_references(paths: Phase4Paths) -> dict[str, dict[str, Any]]:
    specifications = {
        "original": {
            "component_id": "asr.sherpa_onnx",
            "deployment_model_identity": "sherpa-onnx-streaming-zipformer-en-2023-06-26",
            "deployment_model_revision": "2023-06-26",
            "directory": "cache/sherpa_onnx/asr/sherpa-onnx-streaming-zipformer-en-2023-06-26",
            "assets": [
                "tokens.txt",
                "encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
                "decoder-epoch-99-avg-1-chunk-16-left-128.onnx",
                "joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
            ],
            "known_training_lineage": "Zengwei/icefall-asr-librispeech-streaming-zipformer-2023-05-17; Icefall PR 1058; LibriSpeech",
            "source_checkpoint_identity": "Zengwei/icefall-asr-librispeech-streaming-zipformer-2023-05-17",
            "source_checkpoint_revision": None,
            "training_corpora": ["LibriSpeech"],
            "model_license": "Apache-2.0",
            "trainable_checkpoint_resolved": False,
            "config": "Software Validation from Datasets/Evaluation Tool/configs/inference/components/asr/sherpa_onnx.yaml",
        },
        "giga": {
            "component_id": "asr.sherpa_onnx_libri_giga_zipformer_2023_06_21",
            "deployment_model_identity": "csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-21",
            "deployment_model_revision": "9a65b6ea94c311ca770c2bf895b30f456a22d703",
            "directory": "cache/sherpa_onnx/asr/sherpa-onnx-streaming-zipformer-en-2023-06-21",
            "assets": [
                "tokens.txt",
                "encoder-epoch-99-avg-1.int8.onnx",
                "decoder-epoch-99-avg-1.onnx",
                "joiner-epoch-99-avg-1.int8.onnx",
            ],
            "known_training_lineage": "marcoyang/icefall-libri-giga-pruned-transducer-stateless7-streaming-2023-04-04@df8a1ee67abb67244b87d8011ec64ba46c6e97c0; Icefall PR 984; LibriSpeech+GigaSpeech",
            "source_checkpoint_identity": "marcoyang/icefall-libri-giga-pruned-transducer-stateless7-streaming-2023-04-04",
            "source_checkpoint_revision": "df8a1ee67abb67244b87d8011ec64ba46c6e97c0",
            "training_corpora": ["LibriSpeech", "GigaSpeech"],
            "model_license": "Apache-2.0 weights; GigaSpeech training provenance review retained",
            "trainable_checkpoint_resolved": False,
            "config": "Software Validation from Datasets/Evaluation Tool/configs/inference/components/asr/sherpa_onnx_libri_giga_zipformer_2023_06_21.yaml",
        },
    }
    result: dict[str, dict[str, Any]] = {}
    for family, specification in specifications.items():
        directory = paths.model_root / specification["directory"]
        asset_hashes = []
        for filename in specification["assets"]:
            asset = directory / filename
            if not asset.is_file():
                raise Phase4Error(f"Deployed {family} model asset is missing: {asset}")
            asset_hashes.append(
                {
                    "logical_root": "JP_MODEL_ROOT",
                    "relative_path": (
                        Path(specification["directory"]) / filename
                    ).as_posix(),
                    "bytes": asset.stat().st_size,
                    "sha256": sha256_file(asset),
                }
            )
        config = paths.repository_root / specification["config"]
        payload = {
            "schema_version": "model-lineage-reference-phase4.v1",
            "initialization_family": family,
            "component_id": specification["component_id"],
            "deployment_model_identity": specification["deployment_model_identity"],
            "deployment_model_revision": specification["deployment_model_revision"],
            "deployment_assets": asset_hashes,
            "known_training_lineage": specification["known_training_lineage"],
            "source_checkpoint_identity": specification["source_checkpoint_identity"],
            "source_checkpoint_revision": specification["source_checkpoint_revision"],
            "training_corpora": specification["training_corpora"],
            "model_license": specification["model_license"],
            "trainable_checkpoint_resolved": specification[
                "trainable_checkpoint_resolved"
            ],
            "repository_evidence": {
                "logical_root": "JP_REPO_ROOT",
                "relative_path": specification["config"].replace("\\", "/"),
                "sha256": sha256_file(config),
            },
        }
        document = _write_identity_document(
            paths.registries / f"{family}_initialization_reference.json",
            payload,
            prefix=f"{family}_initialization_reference",
            kind="reference",
        )
        document["logical_path"] = _logical_phase4_path(
            paths, paths.registries / f"{family}_initialization_reference.json"
        )
        result[family] = document
    return result


def _write_audit(
    paths: Phase4Paths, name: str, title: str, payload: dict[str, Any]
) -> None:
    atomic_json(paths.audits / f"{name}.json", payload)
    atomic_text(paths.audits / f"{name}.md", markdown_json(title, payload))


def _speaker_sampling_diagnostics(frame: pd.DataFrame) -> dict[str, Any]:
    probabilities = speaker_probabilities(frame)
    values = list(probabilities.values())
    entropy = -sum(value * math.log(value) for value in values)
    return {
        "speaker_count": len(values),
        "maximum_speaker_probability": max(values),
        "minimum_speaker_probability": min(values),
        "speaker_weight_entropy_nats": entropy,
        "effective_speaker_count": math.exp(entropy),
        "probability_sum": sum(values),
    }


def _share_by_category(
    frame: pd.DataFrame, *, category: str, speaker_aware: bool
) -> dict[str, float]:
    if speaker_aware:
        speaker_probability = speaker_probabilities(frame)
        per_speaker_count = frame.groupby("speaker_id").size().to_dict()
        row_weights = frame.apply(
            lambda row: speaker_probability[str(row["speaker_id"])]
            / per_speaker_count[row["speaker_id"]],
            axis=1,
        )
    else:
        row_weights = pd.Series(1 / len(frame), index=frame.index)
    shares: Counter[str] = Counter()
    for index, value in frame[category].items():
        if pd.isna(value) or not str(value).strip():
            tokens = ["unspecified"]
        elif "|" in str(value):
            tokens = [token.strip() for token in str(value).split("|") if token.strip()]
        else:
            tokens = [str(value).strip()]
        contribution = float(row_weights.loc[index]) / len(tokens)
        for token in tokens:
            shares[token] += contribution
    ordered = sorted(shares.items(), key=lambda item: (-item[1], item[0]))
    if len(ordered) > 20:
        top = ordered[:20]
        top.append(("OTHER", sum(value for _, value in ordered[20:])))
        ordered = top
    return {key: value for key, value in ordered}


def sampling_audits(
    paths: Phase4Paths,
    *,
    age_train: pd.DataFrame,
    ami: pd.DataFrame,
    chime: pd.DataFrame,
    voices: pd.DataFrame,
) -> None:
    common_voice = {
        "schema_version": "common-voice-sampling-audit.v1",
        "policy": "sqrt speaker duration, then uniform clip within speaker; no age/accent quota",
        "speaker_diagnostics": _speaker_sampling_diagnostics(age_train),
        "age_bin_raw_row_share": _share_by_category(
            age_train, category="normalized_age_bin", speaker_aware=False
        ),
        "age_bin_speaker_aware_share": _share_by_category(
            age_train, category="normalized_age_bin", speaker_aware=True
        ),
        "accent_raw_row_share": _share_by_category(
            age_train, category="accents", speaker_aware=False
        ),
        "accent_speaker_aware_share": _share_by_category(
            age_train, category="accents", speaker_aware=True
        ),
    }
    _write_audit(
        paths,
        "common_voice_sampling_audit",
        "Common Voice sampling audit",
        common_voice,
    )

    ami_sources = ami.sort_values("source_item_id", kind="mergesort").drop_duplicates(
        "source_utterance_id"
    )
    ami_counts = ami.groupby("source_utterance_id").size()
    ami_audit = {
        "schema_version": "ami-sampling-audit.v1",
        "source_utterances": int(ami["source_utterance_id"].nunique()),
        "meetings": int(ami["meeting_id"].nunique()),
        "physical_views": int(len(ami)),
        "mean_views_per_source": float(ami_counts.mean()),
        "p50_views_per_source": float(ami_counts.quantile(0.50)),
        "p95_views_per_source": float(ami_counts.quantile(0.95)),
        "maximum_views_per_source": int(ami_counts.max()),
        "effective_source_hours": float(ami_sources["duration_seconds"].sum()) / 3600,
        "physical_hours": float(ami["duration_seconds"].sum()) / 3600,
        "future_views_per_source_selection": 1,
        "linguistic_weight_multiplied_by_view_count": False,
    }
    _write_audit(paths, "ami_sampling_audit", "AMI sampling audit", ami_audit)

    voices_sources = voices.sort_values(
        "source_item_id", kind="mergesort"
    ).drop_duplicates("source_utterance_id")
    voices_counts = voices.groupby("source_utterance_id").size()
    voices_audit = {
        "schema_version": "voices-sampling-audit.v1",
        "source_utterances": int(voices["source_utterance_id"].nunique()),
        "retransmission_views": int(len(voices)),
        "views_per_source_minimum": int(voices_counts.min()),
        "views_per_source_median": float(voices_counts.median()),
        "views_per_source_maximum": int(voices_counts.max()),
        "effective_source_hours": float(voices_sources["duration_seconds"].sum())
        / 3600,
        "physical_hours": float(voices["duration_seconds"].sum()) / 3600,
        "future_views_per_source_selection": 1,
        "source_utterance_is_one_selection_unit_before_view_selection": True,
    }
    _write_audit(paths, "voices_sampling_audit", "VOiCES sampling audit", voices_audit)

    source_counts = chime.groupby("source_utterance_id").size()
    chime_audit = {
        "schema_version": "chime-structure-audit.v1",
        "strict_sessions": int(chime["session_id"].nunique()),
        "strict_speakers": int(chime["speaker_id"].nunique()),
        "reported_channel_recordings": int(chime["source_recording_id"].nunique()),
        "strict_rows": int(len(chime)),
        "strict_source_utterances": int(chime["source_utterance_id"].nunique()),
        "registry_views_per_source_minimum": int(source_counts.min()),
        "registry_views_per_source_median": float(source_counts.median()),
        "registry_views_per_source_maximum": int(source_counts.max()),
        "interpretation": "The 48 recordings are four participant-close recordings for each of 12 sessions. Every registered utterance points to its canonical speaking participant recording and occurs once; they are not 48 interchangeable copies per utterance.",
        "view_policy": "use each registered canonical row once as its source/acoustic item; synthesize or duplicate no channels",
    }
    _write_audit(paths, "chime_structure_audit", "CHiME structure audit", chime_audit)


def _bundle_specs() -> dict[str, dict[str, Any]]:
    return {
        "AGE": {
            "datasets": ["common_voice"],
            "train": ["AGE_TRAIN"],
            "dev": ["AGE_DEV"],
            "strictness": "strict",
        },
        "CMU_EXPLORATORY": {
            "datasets": ["cmu_arctic"],
            "train": ["CMU_RELAXED_EXPLORATORY_TRAIN"],
            "dev": ["CMU_RELAXED_EXPLORATORY_DEV"],
            "strictness": "relaxed_exploratory",
        },
        "AMI": {
            "datasets": ["ami"],
            "train": ["AMI_TRAIN"],
            "dev": ["AMI_DEV"],
            "strictness": "strict",
        },
        "CHIME": {
            "datasets": ["chime6"],
            "train": ["CHIME_TRAIN"],
            "dev": ["CHIME_DEV"],
            "strictness": "strict",
        },
        "VOICES": {
            "datasets": ["voices"],
            "train": ["VOICES_TRAIN"],
            "dev": ["VOICES_DEV"],
            "strictness": "strict",
        },
        "ROBUST": {
            "datasets": ["ami", "chime6", "voices"],
            "train": ["AMI_TRAIN", "CHIME_TRAIN", "VOICES_TRAIN"],
            "dev": ["AMI_DEV", "CHIME_DEV", "VOICES_DEV"],
            "strictness": "strict",
        },
        "AGE_ROBUST": {
            "datasets": ["common_voice", "ami", "chime6", "voices"],
            "train": ["AGE_TRAIN", "AMI_TRAIN", "CHIME_TRAIN", "VOICES_TRAIN"],
            "dev": ["AGE_DEV", "AMI_DEV", "CHIME_DEV", "VOICES_DEV"],
            "strictness": "strict",
        },
        "AGE_ROBUST_CMU_EXPLORATORY": {
            "datasets": ["common_voice", "ami", "chime6", "voices", "cmu_arctic"],
            "train": [
                "AGE_TRAIN",
                "AMI_TRAIN",
                "CHIME_TRAIN",
                "VOICES_TRAIN",
                "CMU_RELAXED_EXPLORATORY_TRAIN",
            ],
            "dev": [
                "AGE_DEV",
                "AMI_DEV",
                "CHIME_DEV",
                "VOICES_DEV",
                "CMU_RELAXED_EXPLORATORY_DEV",
            ],
            "strictness": "relaxed_exploratory_due_to_CMU_speaker_overlap",
        },
    }


def write_bundles(
    paths: Phase4Paths,
    *,
    manifests: Mapping[str, Mapping[str, Any]],
    policies: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    bundles: dict[str, dict[str, Any]] = {}
    contribution: dict[str, Any] = {
        "schema_version": "dataset-contribution-audit.v1",
        "bundles": {},
    }
    for name, spec in _bundle_specs().items():
        train_refs = [manifests[item] for item in spec["train"]]
        hours = {
            dataset: float(reference["effective_unique_source_hours"])
            for dataset, reference in zip(spec["datasets"], train_refs, strict=True)
        }
        weights = dataset_weights(hours)
        sources = []
        audit_rows = []
        for dataset, reference in zip(spec["datasets"], train_refs, strict=True):
            weight = weights[dataset]
            sources.append(
                {
                    "dataset_id": dataset,
                    "manifest_id": reference["manifest_id"],
                    "manifest_sha256": reference["manifest_sha256"],
                    "manifest_path": reference["logical_path"],
                    "probability": weight["final_probability"],
                }
            )
            audit_rows.append(
                {
                    "dataset_id": dataset,
                    "train_records": reference["record_count"],
                    "train_speakers": reference["speaker_count"],
                    "train_groups": reference["sampling_group_count"],
                    "train_physical_hours": reference["physical_hours"],
                    **weight,
                    "expected_fraction_of_training_sampling_events": weight[
                        "final_probability"
                    ],
                    "expected_unique_source_exposure_basis": "one source-selection unit before bounded view selection",
                }
            )
        policy_refs = {
            key: {"id": value["policy_id"], "sha256": value["policy_sha256"]}
            for key, value in policies.items()
        }
        payload = {
            "schema_version": "training-bundle-phase4.v1",
            "bundle_name": name,
            "phase3_parent_freeze_id": EXPECTED_PHASE3_ID,
            "strictness_class": spec["strictness"],
            "sampler_algorithm_version": SAMPLER_ALGORITHM_VERSION,
            "sampler_seed": SAMPLER_SEED,
            "train_sources": sources,
            "dev_manifests": [
                {
                    "manifest_id": manifests[item]["manifest_id"],
                    "manifest_sha256": manifests[item]["manifest_sha256"],
                    "manifest_path": manifests[item]["logical_path"],
                }
                for item in spec["dev"]
            ],
            "checkpoint_objective": "single-domain DEV WER"
            if len(spec["dev"]) == 1
            else "equal-weight macro mean of per-domain DEV WER",
            "clean_regression_monitor": {
                "manifest_id": manifests["CLEAN_REGRESSION_MONITOR"]["manifest_id"],
                "manifest_sha256": manifests["CLEAN_REGRESSION_MONITOR"][
                    "manifest_sha256"
                ],
                "used_for_gradients": False,
            },
            "policies": policy_refs,
            "license": _bundle_license(spec["datasets"]),
            "cmu_evaluation_restriction": "descriptive speaker-overlap adaptation"
            if "cmu_arctic" in spec["datasets"]
            else "none",
            "audio_augmentation": "none",
            "general_rehearsal_enabled": False,
        }
        document = _write_identity_document(
            paths.bundles / f"{name.lower()}.json",
            payload,
            prefix=f"{name.lower()}_bundle",
            kind="bundle",
        )
        document["logical_path"] = _logical_phase4_path(
            paths, paths.bundles / f"{name.lower()}.json"
        )
        bundles[name] = document
        contribution["bundles"][name] = {
            "datasets": audit_rows,
            "probability_sum": str(
                sum(Decimal(item["final_probability"]) for item in weights.values())
            ),
            "physical_hours_are_independent_speech": False
            if any(dataset in {"ami", "voices"} for dataset in spec["datasets"])
            else True,
        }
    _write_audit(
        paths, "dataset_contribution_audit", "Dataset contribution audit", contribution
    )
    return bundles, contribution


def write_model_plan(
    paths: Phase4Paths,
    *,
    bundles: Mapping[str, Mapping[str, Any]],
    references: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    specifications = [
        ("O-AGE", "original", "AGE", "strict"),
        ("O-CMU", "original", "CMU_EXPLORATORY", "exploratory"),
        ("O-AMI", "original", "AMI", "strict"),
        ("O-CHIME", "original", "CHIME", "strict"),
        ("O-VOICES", "original", "VOICES", "strict"),
        ("O-ROBUST", "original", "ROBUST", "strict"),
        ("O-AGE-ROBUST", "original", "AGE_ROBUST", "strict"),
        ("O-AGE-ROBUST-CMU", "original", "AGE_ROBUST_CMU_EXPLORATORY", "exploratory"),
        ("G-AGE", "giga", "AGE", "strict"),
        ("G-ROBUST", "giga", "ROBUST", "strict"),
        ("G-AGE-ROBUST", "giga", "AGE_ROBUST", "strict"),
        ("G-AGE-ROBUST-CMU", "giga", "AGE_ROBUST_CMU_EXPLORATORY", "exploratory"),
    ]
    dataset_membership = {
        name: set(spec["datasets"]) for name, spec in _bundle_specs().items()
    }
    experiments = []
    for experiment_id, family, bundle_name, training_class in specifications:
        datasets = dataset_membership[bundle_name]
        bundle = bundles[bundle_name]
        experiments.append(
            {
                "experiment_id": experiment_id,
                "initialization_family": family,
                "initialization_reference_id": references[family]["reference_id"],
                "training_bundle_id": bundle["bundle_id"],
                "training_bundle_name": bundle_name,
                "training_class": training_class,
                "uses_common_voice": "common_voice" in datasets,
                "uses_cmu": "cmu_arctic" in datasets,
                "uses_ami": "ami" in datasets,
                "uses_chime": "chime6" in datasets,
                "uses_voices": "voices" in datasets,
                "commercial_release_review_required": bool(
                    bundle["license"]["commercial_model_release_review_required"]
                ),
                "cmu_evaluation_restriction": "descriptive speaker-overlap adaptation"
                if "cmu_arctic" in datasets
                else "none",
                "intended_training_method": "adapter",
                "training_started": False,
                "full_finetune_planned_automatically": False,
            }
        )
    payload = {
        "schema_version": "model-experiment-plan-phase4.v1",
        "experiments": experiments,
        "total_new_adapter_plans": len(experiments),
        "strict_new_adapter_plans": sum(
            item["training_class"] == "strict" for item in experiments
        ),
        "exploratory_new_adapter_plans": sum(
            item["training_class"] == "exploratory" for item in experiments
        ),
        "model_training_started": False,
    }
    return _write_identity_document(
        paths.registries / "model_experiment_plan.json",
        payload,
        prefix="model_experiment_plan",
        kind="plan",
    )


def _validate_source_pool(
    frame: pd.DataFrame, *, dataset: str, strictness: str
) -> None:
    if frame.empty:
        raise Phase4Error(f"{dataset} {strictness} source pool is empty")
    if bool(frame["evaluation_exact_match"].fillna(False).any()):
        raise Phase4Error(f"{dataset} contains an exact evaluation match")
    if bool(frame["evaluation_cross_dataset_match"].fillna(False).any()):
        raise Phase4Error(f"{dataset} contains a cross-dataset evaluation match")
    if strictness == "strict" and bool(
        frame["evaluation_group_match"].fillna(False).any()
    ):
        raise Phase4Error(f"{dataset} strict pool contains an evaluation group match")


def _manifest_reference(document: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "manifest_name",
        "manifest_id",
        "manifest_sha256",
        "manifest_schema_version",
        "logical_path",
        "record_count",
        "physical_hours",
        "effective_unique_source_hours",
        "speaker_count",
        "group_count",
        "sampling_group_count",
        "meeting_count",
        "session_count",
        "source_utterance_count",
        "acoustic_view_family_count",
        "license_summary",
        "role",
        "strictness_class",
        "training_eligible_for_experiment",
    ]
    return {key: document[key] for key in keys}


def phase4_declarations() -> dict[str, Any]:
    """Return the explicit boundary between this metadata phase and training."""
    return {
        "common_voice_heldout_preserved": True,
        "cmu_strict_pool_empty": True,
        "cmu_relaxed_exploratory_track_created": True,
        "additional_sealed_final_holdout_created": False,
        "general_rehearsal_enabled": False,
        "audio_augmentation": "none",
        "icefall_installed": False,
        "icefall_training_manifests_created": False,
        "adapter_training_configured": False,
        "model_training_started": False,
        "full_finetuning_started": False,
        "onnx_model_exported": False,
        "asr_campaign_created": False,
        "evaluation_functionality_changed": False,
        "direct_gigaspeech_dataset_training": False,
        "text_normalization_finalized": False,
        "tokenization_finalized": False,
    }


def _document_reference(document: Mapping[str, Any], *, kind: str) -> dict[str, Any]:
    return {
        "id": document[f"{kind}_id"],
        "sha256": document[f"{kind}_sha256"],
        "logical_path": document["logical_path"],
    }


def build_phase4(paths: Phase4Paths | None = None) -> dict[str, Any]:
    paths = paths or default_paths()
    freeze_path = paths.registries / "training_manifest_freeze_phase4.json"
    if freeze_path.is_file():
        existing = verify_phase4_freeze(freeze_path, paths=paths)
        if existing["valid"]:
            return {"status": "already_frozen", **existing}
        raise Phase4Error(
            f"An invalid Phase-4 freeze already exists; preserve it for diagnosis: {existing['reasons']}"
        )

    for directory in (
        paths.source_manifests,
        paths.bundles,
        paths.sampling,
        paths.development,
        paths.monitoring,
        paths.audits,
        paths.registries,
        paths.policies,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    parent = verify_parent_inputs(paths)
    before = protected_snapshot(paths)
    phase3 = parent["phase3"]
    source_paths = parent["paths"]

    phase2 = pd.read_parquet(source_paths["phase2_registry"])
    phase2_hash = _frame_hash(phase2, omit=("resolved_audio_path",))
    if phase2_hash != PHASE2_REGISTRY_SHA256:
        raise Phase4Error("Phase-2 source registry canonical hash changed")
    exclusion = pd.read_parquet(source_paths["evaluation_exclusion"])
    if _frame_hash(exclusion) != EXPECTED_EXCLUSION_SHA256:
        raise Phase4Error("Evaluation exclusion canonical hash changed")
    common_voice = pd.read_parquet(source_paths["common_voice_registry"])
    common_voice_split = pd.read_parquet(source_paths["common_voice_split"])
    if (
        _frame_hash(common_voice, omit=("resolved_audio_path",))
        != COMMON_VOICE_REGISTRY_SHA256
    ):
        raise Phase4Error("Common Voice source registry canonical hash changed")
    if _frame_hash(common_voice_split) != COMMON_VOICE_SPLIT_SHA256:
        raise Phase4Error("Common Voice split canonical hash changed")

    age_train = common_voice.loc[common_voice["training_role"].eq("train")].copy()
    age_dev = common_voice.loc[common_voice["training_role"].eq("dev")].copy()
    age_heldout = common_voice.loc[common_voice["training_role"].eq("heldout")].copy()
    expected_cv = {
        "train": (79_594, 1_089),
        "dev": (10_288, 35),
        "heldout": (11_529, 128),
    }
    for role, frame in (
        ("train", age_train),
        ("dev", age_dev),
        ("heldout", age_heldout),
    ):
        if (len(frame), frame["speaker_id"].nunique()) != expected_cv[role]:
            raise Phase4Error(f"Common Voice frozen {role} role changed")
    if set(age_train["speaker_id"].astype(str)) & set(
        age_dev["speaker_id"].astype(str)
    ):
        raise Phase4Error("Common Voice TRAIN and DEV speakers overlap")

    ami = phase2.loc[
        phase2["dataset_id"].eq("ami") & phase2["strict_training_eligible"]
    ].copy()
    chime = phase2.loc[
        phase2["dataset_id"].eq("chime6") & phase2["strict_training_eligible"]
    ].copy()
    voices = phase2.loc[
        phase2["dataset_id"].eq("voices") & phase2["strict_training_eligible"]
    ].copy()
    cmu_all = phase2.loc[phase2["dataset_id"].eq("cmu_arctic")].copy()
    cmu = cmu_all.loc[cmu_all["relaxed_training_eligible"]].copy()
    libri = phase2.loc[phase2["dataset_id"].eq("librispeech")].copy()
    if int(cmu_all["strict_training_eligible"].sum()) != 0:
        raise Phase4Error("CMU strict pool is no longer empty")
    for dataset, frame, strictness in (
        ("ami", ami, "strict"),
        ("chime6", chime, "strict"),
        ("voices", voices, "strict"),
        ("cmu_arctic", cmu, "relaxed_exploratory"),
    ):
        _validate_source_pool(frame, dataset=dataset, strictness=strictness)

    ami_dev_ids = ami_dev_meetings(ami)
    chime_dev_ids = chime_dev_sessions(chime)
    voices_dev_ids = voices_dev_speakers(voices)
    cmu_dev_ids = cmu_dev_speakers(cmu)
    ami_train_raw, ami_dev_raw = (
        ami.loc[~ami["meeting_id"].astype(str).isin(ami_dev_ids)],
        ami.loc[ami["meeting_id"].astype(str).isin(ami_dev_ids)],
    )
    chime_train_raw, chime_dev_raw = (
        chime.loc[~chime["session_id"].astype(str).isin(chime_dev_ids)],
        chime.loc[chime["session_id"].astype(str).isin(chime_dev_ids)],
    )
    voices_train_raw, voices_dev_raw = (
        voices.loc[~voices["speaker_id"].astype(str).isin(voices_dev_ids)],
        voices.loc[voices["speaker_id"].astype(str).isin(voices_dev_ids)],
    )
    cmu_train_raw, cmu_dev_raw = (
        cmu.loc[~cmu["speaker_id"].astype(str).isin(cmu_dev_ids)],
        cmu.loc[cmu["speaker_id"].astype(str).isin(cmu_dev_ids)],
    )
    if len(chime_dev_ids) != 2 or chime_train_raw["session_id"].nunique() != 10:
        raise Phase4Error("CHiME split is not 10 TRAIN / 2 DEV sessions")

    raw_splits = {
        "AMI": (ami_train_raw, ami_dev_raw),
        "CHIME": (chime_train_raw, chime_dev_raw),
        "VOICES": (voices_train_raw, voices_dev_raw),
        "CMU": (cmu_train_raw, cmu_dev_raw),
    }
    development_audit: dict[str, Any] = {
        "schema_version": "development-data-audit.v1",
        "datasets": {},
    }
    for name, (train_raw, dev_raw) in raw_splits.items():
        dataset = {
            "AMI": "ami",
            "CHIME": "chime6",
            "VOICES": "voices",
            "CMU": "cmu_arctic",
        }[name]
        overlaps = _raw_overlap_audit(train_raw, dev_raw, dataset=dataset)
        prohibited = [
            "exact_item_overlap",
            "source_group_overlap",
            "meeting_overlap"
            if name == "AMI"
            else "session_overlap"
            if name == "CHIME"
            else "acoustic_view_family_overlap",
        ]
        if any(overlaps[key] for key in prohibited):
            raise Phase4Error(
                f"{name} development split violates group-disjointness: {overlaps}"
            )
        overlap_interpretation = {
            "exact_item_overlap": "prohibited",
            "source_group_overlap": "prohibited",
            "acoustic_view_family_overlap": "prohibited",
            "meeting_overlap": "prohibited for AMI; not applicable otherwise",
            "session_overlap": "prohibited for CHiME; not applicable otherwise",
            "speaker_overlap": (
                "allowed and explicitly reported for recurring AMI/CHiME participants"
                if name in {"AMI", "CHIME"}
                else "prohibited by the speaker-disjoint partition"
            ),
            "source_utterance_overlap": (
                "allowed for CMU because source_utterance_id identifies a shared text prompt; exact speaker recordings and source groups remain disjoint"
                if name == "CMU"
                else "prohibited"
            ),
        }
        development_audit["datasets"][name] = {
            "train_records": int(len(train_raw)),
            "dev_records": int(len(dev_raw)),
            "train_physical_hours": float(train_raw["duration_seconds"].sum()) / 3600,
            "dev_physical_hours": float(dev_raw["duration_seconds"].sum()) / 3600,
            "train_speakers": int(train_raw["speaker_id"].nunique()),
            "dev_speakers": int(dev_raw["speaker_id"].nunique()),
            "train_meetings": int(train_raw["meeting_id"].nunique()),
            "dev_meetings": int(dev_raw["meeting_id"].nunique()),
            "train_sessions": int(train_raw["session_id"].nunique()),
            "dev_sessions": int(dev_raw["session_id"].nunique()),
            "overlaps": overlaps,
            "overlap_interpretation": overlap_interpretation,
            "speaker_overlap_interpretation": "allowed and reported for recurring meeting/session participants"
            if name in {"AMI", "CHIME"}
            else "prohibited by speaker partition",
        }

    forbidden_monitor_cross_keys = set(voices["cross_source_key"].dropna().astype(str))
    monitor_raw = clean_monitor_rows(
        libri, forbidden_cross_keys=forbidden_monitor_cross_keys
    )
    _validate_source_pool(
        monitor_raw, dataset="librispeech_monitor", strictness="strict"
    )

    manifests: dict[str, dict[str, Any]] = {}
    jobs = [
        (
            "AGE_TRAIN",
            "common_voice",
            age_train,
            "train",
            "strict",
            "source_manifests",
            True,
        ),
        ("AGE_DEV", "common_voice", age_dev, "dev", "strict", "development", False),
        (
            "AMI_TRAIN",
            "ami",
            ami_train_raw,
            "train",
            "strict",
            "source_manifests",
            True,
        ),
        ("AMI_DEV", "ami", ami_dev_raw, "dev", "strict", "development", False),
        (
            "CHIME_TRAIN",
            "chime6",
            chime_train_raw,
            "train",
            "strict",
            "source_manifests",
            True,
        ),
        ("CHIME_DEV", "chime6", chime_dev_raw, "dev", "strict", "development", False),
        (
            "VOICES_TRAIN",
            "voices",
            voices_train_raw,
            "train",
            "strict",
            "source_manifests",
            True,
        ),
        ("VOICES_DEV", "voices", voices_dev_raw, "dev", "strict", "development", False),
        (
            "CMU_RELAXED_EXPLORATORY_TRAIN",
            "cmu_arctic",
            cmu_train_raw,
            "train",
            "relaxed_exploratory",
            "source_manifests",
            True,
        ),
        (
            "CMU_RELAXED_EXPLORATORY_DEV",
            "cmu_arctic",
            cmu_dev_raw,
            "dev",
            "relaxed_exploratory",
            "development",
            False,
        ),
        (
            "CLEAN_REGRESSION_MONITOR",
            "librispeech",
            monitor_raw,
            "monitor",
            "monitor",
            "monitoring",
            False,
        ),
    ]
    for (
        logical_name,
        dataset,
        raw_frame,
        role,
        strictness,
        subdirectory,
        training_eligible,
    ) in jobs:
        if dataset == "common_voice":
            manifest_frame = common_voice_manifest(raw_frame, role=role, parent=phase3)
        else:
            manifest_frame = phase2_manifest(
                raw_frame,
                dataset=dataset,
                role=role,
                strictness=strictness,
                parent=phase3,
                training_eligible=training_eligible,
            )
        manifests[logical_name] = write_manifest(
            paths,
            logical_name=logical_name,
            frame=manifest_frame,
            subdirectory=subdirectory,
        )
        del manifest_frame

    empty_cmu_payload = {
        "manifest_name": "CMU_STRICT_EMPTY",
        "manifest_schema_version": MANIFEST_SCHEMA,
        "phase3_parent_freeze_id": EXPECTED_PHASE3_ID,
        "record_count": 0,
        "physical_hours": 0,
        "effective_unique_source_hours": 0,
        "speaker_count": 0,
        "group_count": 0,
        "role": "train",
        "strictness_class": "strict",
        "reason": "all speakers blocked by strict evaluation-group firewall",
    }
    empty_cmu = _write_identity_document(
        paths.source_manifests / "cmu_strict_empty_descriptor.json",
        empty_cmu_payload,
        prefix="cmu_strict_empty",
        kind="manifest",
    )

    development_audit["datasets"]["COMMON_VOICE"] = {
        "train_records": len(age_train),
        "dev_records": len(age_dev),
        "train_physical_hours": float(age_train["duration_seconds"].sum()) / 3600,
        "dev_physical_hours": float(age_dev["duration_seconds"].sum()) / 3600,
        "train_speakers": int(age_train["speaker_id"].nunique()),
        "dev_speakers": int(age_dev["speaker_id"].nunique()),
        "overlaps": {
            "exact_item_overlap": len(
                set(age_train["source_item_id"]) & set(age_dev["source_item_id"])
            ),
            "source_utterance_overlap": len(
                set(age_train["source_utterance_id"])
                & set(age_dev["source_utterance_id"])
            ),
            "speaker_overlap": len(
                set(age_train["speaker_id"]) & set(age_dev["speaker_id"])
            ),
            "meeting_overlap": 0,
            "session_overlap": 0,
            "acoustic_view_family_overlap": 0,
        },
        "overlap_interpretation": "all listed overlaps are prohibited and observed as zero",
        "selection": "unchanged Phase-3 frozen roles",
    }
    for name, (train_name, dev_name) in {
        "AMI": ("AMI_TRAIN", "AMI_DEV"),
        "CHIME": ("CHIME_TRAIN", "CHIME_DEV"),
        "VOICES": ("VOICES_TRAIN", "VOICES_DEV"),
        "CMU": ("CMU_RELAXED_EXPLORATORY_TRAIN", "CMU_RELAXED_EXPLORATORY_DEV"),
    }.items():
        development_audit["datasets"][name]["train_unique_source_hours"] = manifests[
            train_name
        ]["effective_unique_source_hours"]
        development_audit["datasets"][name]["dev_unique_source_hours"] = manifests[
            dev_name
        ]["effective_unique_source_hours"]
    _write_audit(
        paths, "development_data_audit", "Development data audit", development_audit
    )

    sampling_audits(paths, age_train=age_train, ami=ami, chime=chime, voices=voices)
    monitor_audit = {
        "schema_version": "clean-regression-monitor-audit.v1",
        **_manifest_reference(manifests["CLEAN_REGRESSION_MONITOR"]),
        "target_hours": MONITOR_TARGET_HOURS,
        "broad_speaker_policy": "one deterministic utterance per selected speaker",
        "forbidden_voices_source_keys": len(forbidden_monitor_cross_keys),
        "selected_cross_source_overlap_with_voices": int(
            monitor_raw["cross_source_key"]
            .astype("string")
            .isin(forbidden_monitor_cross_keys)
            .sum()
        ),
        "used_for_gradients": False,
        "general_rehearsal_enabled": False,
    }
    _write_audit(
        paths,
        "clean_regression_monitor_audit",
        "Clean regression monitor audit",
        monitor_audit,
    )

    heldout_speakers = set(age_heldout["speaker_id"].astype(str))
    bundle_cv_ids = set(age_train["source_item_id"].astype(str)) | set(
        age_dev["source_item_id"].astype(str)
    )
    heldout_audit = {
        "schema_version": "common-voice-heldout-audit.v1",
        "heldout_records": int(len(age_heldout)),
        "heldout_hours": float(age_heldout["duration_seconds"].sum()) / 3600,
        "heldout_speakers": len(heldout_speakers),
        "train_heldout_speaker_overlap": len(
            set(age_train["speaker_id"].astype(str)) & heldout_speakers
        ),
        "dev_heldout_speaker_overlap": len(
            set(age_dev["speaker_id"].astype(str)) & heldout_speakers
        ),
        "heldout_source_ids_in_train_or_dev": len(
            set(age_heldout["source_item_id"].astype(str)) & bundle_cv_ids
        ),
        "heldout_paths_in_train_or_dev": len(
            set(age_heldout["prepared_audio_relative_path"].astype(str))
            & (
                set(age_train["prepared_audio_relative_path"].astype(str))
                | set(age_dev["prepared_audio_relative_path"].astype(str))
            )
        ),
        "heldout_used_in_training": False,
        "heldout_used_in_dev": False,
    }
    if any(
        heldout_audit[key]
        for key in (
            "train_heldout_speaker_overlap",
            "dev_heldout_speaker_overlap",
            "heldout_source_ids_in_train_or_dev",
            "heldout_paths_in_train_or_dev",
        )
    ):
        raise Phase4Error("Common Voice HELDOUT isolation failed")
    _write_audit(
        paths, "common_voice_heldout_audit", "Common Voice HELDOUT audit", heldout_audit
    )

    policies = write_policies(
        paths, monitor_manifest_id=manifests["CLEAN_REGRESSION_MONITOR"]["manifest_id"]
    )
    bundles, contribution = write_bundles(paths, manifests=manifests, policies=policies)
    references = initialization_references(paths)
    model_plan = write_model_plan(paths, bundles=bundles, references=references)
    model_plan["logical_path"] = _logical_phase4_path(
        paths, paths.registries / "model_experiment_plan.json"
    )

    protected = [{"path": path, "sha256": digest} for path, digest in before.items()]
    freeze_payload = {
        "schema_version": PHASE4_SCHEMA,
        "successor_logical_root": "JP_TRAINING_ROOT",
        "successor_relative_path": f"successors/{SUCCESSOR_NAME}",
        "parent_phase3": {
            "id": phase3["training_data_freeze_id"],
            "sha256": phase3["training_data_freeze_sha256"],
            "logical_path": "JP_TRAINING_ROOT:successors/common_voice_26_english_phase3/registries/training_data_freeze_phase3.json",
        },
        "phase2_parent": {"id": EXPECTED_PHASE2_ID, "sha256": EXPECTED_PHASE2_SHA256},
        "evaluation_exclusion_index": {
            "id": EXPECTED_EXCLUSION_ID,
            "sha256": EXPECTED_EXCLUSION_SHA256,
        },
        "source_manifests": {
            name: _manifest_reference(document) for name, document in manifests.items()
        },
        "cmu_strict_empty_descriptor": {
            "id": empty_cmu["manifest_id"],
            "sha256": empty_cmu["manifest_sha256"],
            "record_count": 0,
        },
        "policies": {
            name: _document_reference(document, kind="policy")
            for name, document in policies.items()
        },
        "bundles": {
            name: _document_reference(document, kind="bundle")
            for name, document in bundles.items()
        },
        "model_plan": {
            "id": model_plan["plan_id"],
            "sha256": model_plan["plan_sha256"],
            "logical_path": model_plan["logical_path"],
            "total": 12,
            "strict": 9,
            "exploratory": 3,
        },
        "initialization_references": {
            name: _document_reference(document, kind="reference")
            for name, document in references.items()
        },
        "protected_artifacts": protected,
        "phase4_declarations": phase4_declarations(),
    }
    freeze = _identity_document(
        freeze_payload,
        prefix="training_manifest_freeze_phase4",
        kind="training_manifest_freeze",
    )
    atomic_json(freeze_path, freeze)

    after = protected_snapshot(paths)
    immutability = {
        "schema_version": "phase4-immutability-audit.v1",
        "files": [
            {
                "path": path,
                "sha_before": digest,
                "sha_after": after.get(path),
                "byte_identical": after.get(path) == digest,
            }
            for path, digest in before.items()
        ],
    }
    if not all(item["byte_identical"] for item in immutability["files"]):
        raise Phase4Error(
            "A protected parent/evaluation artifact changed during Phase 4"
        )
    _write_audit(
        paths, "phase4_immutability_audit", "Phase-4 immutability audit", immutability
    )

    summary = {
        "schema_version": "phase4-summary.v1",
        "freeze_id": freeze["training_manifest_freeze_id"],
        "freeze_sha256": freeze["training_manifest_freeze_sha256"],
        "freeze_path": _logical_phase4_path(paths, freeze_path),
        "source_manifests": {
            name: _manifest_reference(document) for name, document in manifests.items()
        },
        "bundles": {
            name: {
                "id": document["bundle_id"],
                "sha256": document["bundle_sha256"],
                "logical_path": document["logical_path"],
                "weights": {
                    item["dataset_id"]: item["probability"]
                    for item in document["train_sources"]
                },
                "license": document["license"],
            }
            for name, document in bundles.items()
        },
        "policies": {
            name: {"id": document["policy_id"], "sha256": document["policy_sha256"]}
            for name, document in policies.items()
        },
        "model_plan": {
            "id": model_plan["plan_id"],
            "sha256": model_plan["plan_sha256"],
            "total": 12,
            "strict": 9,
            "exploratory": 3,
        },
        "development": development_audit,
        "common_voice_heldout": heldout_audit,
        "clean_monitor": monitor_audit,
        "initialization_references": references,
        "dataset_contribution": contribution,
    }
    atomic_json(paths.registries / "phase4_summary.json", summary)
    atomic_text(
        paths.audits / "phase4_summary.md", markdown_json("Phase-4 summary", summary)
    )
    verification = verify_phase4_freeze(freeze_path, paths=paths)
    if not verification["valid"]:
        raise Phase4Error(
            f"Generated Phase-4 freeze failed verification: {verification['reasons']}"
        )
    return {
        "status": "created",
        **verification,
        "summary_path": str(paths.registries / "phase4_summary.json"),
    }


def _resolve_logical(paths: Phase4Paths, logical: str) -> Path:
    if logical.startswith("JP_TRAINING_ROOT:"):
        return paths.training_root / logical.split(":", 1)[1]
    if logical.startswith("EVALUATION_TOOL:"):
        return paths.evaluation_tool_root / logical.split(":", 1)[1]
    if logical.startswith("JP_REPO_ROOT:"):
        return paths.repository_root / logical.split(":", 1)[1]
    if logical.startswith("JP_MODEL_ROOT:"):
        return paths.model_root / logical.split(":", 1)[1]
    raise Phase4Error(f"Unsupported logical path: {logical}")


def verify_phase4_freeze(
    freeze_path: Path, *, paths: Phase4Paths | None = None
) -> dict[str, Any]:
    paths = paths or default_paths()
    reasons: list[str] = []
    try:
        parent = verify_parent_inputs(paths)
    except (
        Exception
    ) as exc:  # bounded verifier reports rather than obscuring all checks
        parent = None
        reasons.append(f"parent verification failed: {exc}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    canonical = {
        key: value
        for key, value in freeze.items()
        if key not in {"training_manifest_freeze_id", "training_manifest_freeze_sha256"}
    }
    if _json_hash(canonical) != freeze.get("training_manifest_freeze_sha256"):
        reasons.append("Phase-4 freeze self-hash mismatch")
    if (
        freeze.get("parent_phase3", {}).get("id") != EXPECTED_PHASE3_ID
        or freeze.get("parent_phase3", {}).get("sha256") != EXPECTED_PHASE3_SHA256
    ):
        reasons.append("Phase-3 parent reference mismatch")
    if _has_absolute_path(freeze):
        reasons.append("absolute path found in canonical Phase-4 freeze")
    for name, reference in freeze.get("source_manifests", {}).items():
        try:
            path = _resolve_logical(paths, reference["logical_path"])
            observed = pd.read_parquet(path)
            if _frame_hash(observed) != reference["manifest_sha256"]:
                reasons.append(f"source manifest hash mismatch: {name}")
            if bool(
                observed["audio_relative_path"]
                .dropna()
                .astype(str)
                .map(_has_absolute_path)
                .any()
            ):
                reasons.append(f"absolute audio path in source manifest: {name}")
            if name == "CLEAN_REGRESSION_MONITOR" and bool(
                observed["training_eligible_for_experiment"].any()
            ):
                reasons.append("clean monitor is training eligible")
        except Exception as exc:
            reasons.append(f"source manifest unavailable or invalid ({name}): {exc}")
    for collection, kind in (("policies", "policy"), ("bundles", "bundle")):
        for name, reference in freeze.get(collection, {}).items():
            try:
                document = json.loads(
                    _resolve_logical(paths, reference["logical_path"]).read_text(
                        encoding="utf-8"
                    )
                )
                if not _verify_identity_document(document, kind=kind):
                    reasons.append(f"{kind} self-hash mismatch: {name}")
                if (
                    document.get(f"{kind}_id") != reference["id"]
                    or document.get(f"{kind}_sha256") != reference["sha256"]
                ):
                    reasons.append(f"{kind} freeze reference mismatch: {name}")
                if kind == "bundle":
                    total = sum(
                        Decimal(item["probability"])
                        for item in document["train_sources"]
                    )
                    if abs(total - Decimal(1)) > Decimal("1e-40"):
                        reasons.append(f"bundle weights do not sum to one: {name}")
                    if (
                        "CHIME" in name
                        and not document["license"][
                            "commercial_model_release_review_required"
                        ]
                    ):
                        reasons.append(f"CHiME review gate missing: {name}")
            except Exception as exc:
                reasons.append(f"{kind} unavailable or invalid ({name}): {exc}")
    for name, reference in freeze.get("initialization_references", {}).items():
        try:
            document = json.loads(
                _resolve_logical(paths, reference["logical_path"]).read_text(
                    encoding="utf-8"
                )
            )
            if not _verify_identity_document(document, kind="reference"):
                reasons.append(f"initialization reference self-hash mismatch: {name}")
            if (
                document.get("reference_id") != reference["id"]
                or document.get("reference_sha256") != reference["sha256"]
            ):
                reasons.append(f"initialization freeze reference mismatch: {name}")
            if document.get("trainable_checkpoint_resolved") is not False:
                reasons.append(
                    f"unverified trainable checkpoint marked resolved: {name}"
                )
        except Exception as exc:
            reasons.append(
                f"initialization reference unavailable or invalid ({name}): {exc}"
            )
    try:
        model_reference = freeze["model_plan"]
        model_plan = json.loads(
            _resolve_logical(paths, model_reference["logical_path"]).read_text(
                encoding="utf-8"
            )
        )
        if not _verify_identity_document(model_plan, kind="plan"):
            reasons.append("model plan self-hash mismatch")
        experiments = model_plan["experiments"]
        if (
            len(experiments) != 12
            or sum(item["training_class"] == "strict" for item in experiments) != 9
            or sum(item["training_class"] == "exploratory" for item in experiments) != 3
        ):
            reasons.append("model plan counts changed")
        by_id = {item["experiment_id"]: item for item in experiments}
        for left, right in (
            ("O-AGE", "G-AGE"),
            ("O-ROBUST", "G-ROBUST"),
            ("O-AGE-ROBUST", "G-AGE-ROBUST"),
            ("O-AGE-ROBUST-CMU", "G-AGE-ROBUST-CMU"),
        ):
            if by_id[left]["training_bundle_id"] != by_id[right]["training_bundle_id"]:
                reasons.append(f"Original/Giga bundle mismatch: {left}/{right}")
    except Exception as exc:
        reasons.append(f"model plan unavailable or invalid: {exc}")
    for item in freeze.get("protected_artifacts", []):
        try:
            observed = sha256_file(_resolve_logical(paths, item["path"]))
            if observed != item["sha256"]:
                reasons.append(f"protected artifact changed: {item['path']}")
        except Exception as exc:
            reasons.append(
                f"protected artifact unavailable ({item.get('path')}): {exc}"
            )
    return {
        "valid": not reasons,
        "reasons": reasons,
        "freeze_id": freeze.get("training_manifest_freeze_id"),
        "freeze_sha256": freeze.get("training_manifest_freeze_sha256"),
        "parent_valid": parent is not None,
    }


def phase4_status(paths: Phase4Paths | None = None) -> dict[str, Any]:
    paths = paths or default_paths()
    freeze_path = paths.registries / "training_manifest_freeze_phase4.json"
    parent = verify_parent_inputs(paths)
    result = {
        "phase3_parent_valid": parent["phase3_check"]["valid"],
        "phase3_parent_id": parent["phase3"]["training_data_freeze_id"],
        "phase4_successor_logical_root": "JP_TRAINING_ROOT",
        "phase4_successor_relative_path": f"successors/{SUCCESSOR_NAME}",
        "phase4_freeze_present": freeze_path.is_file(),
    }
    if freeze_path.is_file():
        result["phase4_verification"] = verify_phase4_freeze(freeze_path, paths=paths)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "run", "verify"))
    args = parser.parse_args()
    paths = default_paths()
    try:
        if args.command == "status":
            result = phase4_status(paths)
        elif args.command == "run":
            result = build_phase4(paths)
        else:
            result = verify_phase4_freeze(
                paths.registries / "training_manifest_freeze_phase4.json", paths=paths
            )
            if not result["valid"]:
                print(json.dumps(result, indent=2, sort_keys=True))
                return 1
    except (Phase4Error, FileNotFoundError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "blocked", "reason": str(exc)}, indent=2, sort_keys=True
            )
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
