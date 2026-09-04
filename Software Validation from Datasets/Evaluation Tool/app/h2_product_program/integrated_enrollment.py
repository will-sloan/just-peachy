"""Session-aware, development-only H2 enrollment confirmation.

This module deliberately keeps biometric vectors in a private restart cache.
Its public outputs contain only scalar measurements, decisions, SHA-256
identities, and aggregate counts.  The study uses LibriSpeech train-clean-100
as development research material; it never opens the H2 held-out manifests.

The management interpreter builds and seals the panel before inference, then
launches the already-qualified ReDimNet2 environment for missing cache slices.
Policy calibration uses calibration speakers only.  A disjoint selection
cohort is used for the final 32-cell comparison and enrollment recommendation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
from itertools import combinations, permutations, product
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Callable, Iterable, Mapping, Sequence
import uuid

import numpy as np
import soundfile as sf

from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.speaker_embedding.base import SpeakerEmbeddingContext
from app.speaker_protocol.contracts import backend_identity, normalize_vector
from app.utils.paths import data_root, repository_root

from .contracts import H2Job, H2ProgramError, ProgramPaths
from .io import (
    canonical_sha256,
    read_json,
    sha256_file,
    write_json_atomic,
)
from .selection import (
    SAFETY_PRIORITY_CONTRACT_ID,
    SAFETY_PRIORITY_ORDERED_RISK_FAMILIES,
)


SCHEMA_VERSION = "h2-integrated-enrollment-confirmation.v4"
PANEL_SCHEMA_VERSION = "h2-integrated-enrollment-panel.v2"
CACHE_SCHEMA_VERSION = "h2-integrated-enrollment-private-cache.v1"
CACHE_ITEM_SCHEMA_VERSION = "h2-integrated-enrollment-cache-item.v1"
WORKER_REQUEST_SCHEMA_VERSION = "h2-integrated-enrollment-worker-request.v1"
BACKEND_ID = "redimnet2_b2_speaker_embedding"
SEED = 3800
SAMPLE_RATE_HZ = 16_000
MINIMUM_MODEL_FRAMES = 8_000
PROBE_FRAMES = 48_000
SPEAKERS_PER_ROLE = 16
PROBES_PER_SPEAKER = 5
MAX_ENROLLMENT_ATTEMPTS = 2
ENROLLMENT_DURATION_ALLOCATION_POLICY = "balanced_exact_frames_per_utterance.v1"
TARGET_FPIR = 0.02
CALIBRATION_MARGINS = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05)
MATRIX_AXES: Mapping[str, tuple[object, ...]] = {
    "utterances": (3, 5),
    "total_duration_sec": (10.0, 20.0),
    "sessions": ("single", "varied"),
    "aggregation": ("normalized_mean", "frozen_redim_multi_template"),
    "quality_filter": ("blind_accept", "quality_filtered"),
}
ROLE_ORDER = (
    "calibration_known",
    "calibration_stranger",
    "selection_known",
    "selection_stranger",
)
QC_POLICY: Mapping[str, object] = {
    "schema_version": "h2-enrollment-qc-policy.v1",
    "minimum_voiced_duration_sec": 0.50,
    "minimum_voiced_proportion": 0.25,
    "minimum_level_dbfs": -45.0,
    "maximum_clipping_fraction": 0.01,
    "minimum_declared_noise_proxy_db": 3.0,
    "minimum_pairwise_template_cosine": 0.20,
    "minimum_centroid_consistency": 0.30,
    "minimum_leave_one_out_cosine": 0.20,
    "voiced_frame_ms": 20,
    "voiced_absolute_threshold_dbfs": -45.0,
    "noise_proxy_definition": "20*log10(p90_frame_rms/max(p10_frame_rms,1e-8))",
    "failure_action": "REJECT_SAMPLE_SET_AND_USE_NEXT_PREDECLARED_REPEAT_ATTEMPT",
}


class IntegratedEnrollmentError(H2ProgramError):
    """The integrated enrollment contract cannot be satisfied safely."""


@dataclass(frozen=True)
class SourceAudio:
    """Metadata-only inventory row for one installed LibriSpeech utterance."""

    path: Path
    logical_path: str
    speaker_source_id: str
    chapter_source_id: str
    frames: int
    sample_rate_hz: int
    channels: int

    @property
    def duration_sec(self) -> float:
        return self.frames / self.sample_rate_hz


def default_librispeech_root() -> Path:
    """Return the installed train-clean-100 root without downloading assets."""

    return (
        data_root().path
        / "Raw Datasets (Not formatted)"
        / "LibreSpeech"
        / "train-clean-100"
        / "LibriSpeech"
        / "train-clean-100"
    ).resolve()


def _safe_id(prefix: str, value: object) -> str:
    return f"{prefix}_{canonical_sha256({'seed': SEED, 'value': value})[:16]}"


def _stable_order(values: Iterable[object], *, scope: object) -> list[object]:
    return sorted(
        values,
        key=lambda value: (
            canonical_sha256({"seed": SEED, "scope": scope, "value": str(value)}),
            str(value),
        ),
    )


def _source_metadata(path: Path, dataset_root: Path) -> SourceAudio | None:
    try:
        info = sf.info(path)
    except Exception:
        return None
    if int(info.samplerate) != SAMPLE_RATE_HZ or int(info.channels) != 1:
        return None
    if int(info.frames) < MINIMUM_MODEL_FRAMES:
        return None
    relative = path.resolve().relative_to(dataset_root.resolve()).as_posix()
    chapter = path.parent.name
    speaker = path.parent.parent.name
    return SourceAudio(
        path=path.resolve(),
        logical_path=relative,
        speaker_source_id=speaker,
        chapter_source_id=chapter,
        frames=int(info.frames),
        sample_rate_hz=int(info.samplerate),
        channels=int(info.channels),
    )


def _speaker_inventory(
    dataset_root: Path,
) -> dict[str, dict[str, tuple[SourceAudio, ...]]]:
    root = Path(dataset_root).resolve()
    if not root.is_dir():
        raise IntegratedEnrollmentError(
            f"installed LibriSpeech train-clean-100 root is missing: {root}"
        )
    output: dict[str, dict[str, tuple[SourceAudio, ...]]] = {}
    for speaker_dir in sorted(root.iterdir(), key=lambda value: value.name):
        if not speaker_dir.is_dir():
            continue
        chapters: dict[str, tuple[SourceAudio, ...]] = {}
        for chapter_dir in sorted(speaker_dir.iterdir(), key=lambda value: value.name):
            if not chapter_dir.is_dir():
                continue
            files = tuple(
                row
                for row in (
                    _source_metadata(path, root)
                    for path in sorted(
                        chapter_dir.glob("*.flac"), key=lambda value: value.name
                    )
                )
                if row is not None
            )
            if files:
                chapters[chapter_dir.name] = files
        if len(chapters) >= 3:
            output[speaker_dir.name] = chapters
    return output


def _candidate_enrollment_orders(
    chapter_a: Sequence[SourceAudio],
    chapter_b: Sequence[SourceAudio],
    *,
    utterances: int,
    target_frames: int,
    sessions: str,
    scope: object,
) -> tuple[tuple[SourceAudio, ...], ...]:
    """Select source-disjoint attempts for balanced exact-frame enrollment."""

    contribution_frames = _balanced_contribution_frames(target_frames, utterances)
    required_source_frames = max(contribution_frames)

    def eligible(
        values: Sequence[SourceAudio], *, local_scope: object
    ) -> list[SourceAudio]:
        return list(
            _stable_order(
                (row for row in values if row.frames >= required_source_frames),
                scope=(scope, local_scope),
            )
        )

    chapter_a_eligible = eligible(chapter_a, local_scope="chapter-a")
    if sessions == "single":
        required = utterances * MAX_ENROLLMENT_ATTEMPTS
        if len(chapter_a_eligible) < required:
            return ()
        return tuple(
            tuple(
                chapter_a_eligible[
                    attempt_index * utterances : (attempt_index + 1) * utterances
                ]
            )
            for attempt_index in range(MAX_ENROLLMENT_ATTEMPTS)
        )
    if sessions != "varied":
        raise IntegratedEnrollmentError(f"unknown session condition: {sessions}")

    chapter_b_eligible = eligible(chapter_b, local_scope="chapter-b")
    take_b = max(1, utterances // 2)
    take_a = utterances - take_b
    required_a = take_a * MAX_ENROLLMENT_ATTEMPTS
    required_b = take_b * MAX_ENROLLMENT_ATTEMPTS
    if len(chapter_a_eligible) < required_a or len(chapter_b_eligible) < required_b:
        return ()
    output: list[tuple[SourceAudio, ...]] = []
    for attempt_index in range(MAX_ENROLLMENT_ATTEMPTS):
        selected = [
            *chapter_a_eligible[attempt_index * take_a : (attempt_index + 1) * take_a],
            *chapter_b_eligible[attempt_index * take_b : (attempt_index + 1) * take_b],
        ]
        output.append(
            tuple(
                _stable_order(
                    selected,
                    scope=(scope, "varied-attempt", attempt_index),
                )
            )
        )
    return tuple(output)


def _balanced_contribution_frames(
    target_frames: int, utterances: int
) -> tuple[int, ...]:
    """Distribute an exact duration budget as evenly as integer frames allow."""

    if target_frames < 1 or utterances < 1:
        raise IntegratedEnrollmentError(
            "enrollment duration allocation requires positive frames and utterances"
        )
    base, remainder = divmod(target_frames, utterances)
    contributions = tuple(
        base + (1 if index < remainder else 0) for index in range(utterances)
    )
    if min(contributions) < MINIMUM_MODEL_FRAMES:
        raise IntegratedEnrollmentError(
            "balanced enrollment contribution violates backend minimum duration"
        )
    if sum(contributions) != target_frames:
        raise IntegratedEnrollmentError("balanced enrollment duration is not exact")
    return contributions


def _slice_identity(
    source_id: str, source_sha256: str, start_frame: int, end_frame: int
) -> str:
    return (
        "slice_"
        + canonical_sha256(
            {
                "schema_version": "h2-enrollment-audio-slice.v1",
                "source_id": source_id,
                "source_sha256": source_sha256,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "channels": 1,
                "dtype": "float32",
            }
        )[:24]
    )


def _seal_source(
    source: SourceAudio,
    *,
    source_hashes: dict[Path, str],
    source_rows: dict[str, dict[str, object]],
) -> dict[str, object]:
    source_hash = source_hashes.get(source.path)
    if source_hash is None:
        source_hash = sha256_file(source.path)
        source_hashes[source.path] = source_hash
    source_id = (
        "src_"
        + canonical_sha256(
            {"logical_path": source.logical_path, "source_sha256": source_hash}
        )[:24]
    )
    prior = source_rows.get(source_id)
    row = {
        "source_id": source_id,
        "logical_path": source.logical_path,
        "source_sha256": source_hash,
        "frames": source.frames,
        "sample_rate_hz": source.sample_rate_hz,
        "channels": source.channels,
        "duration_sec": source.duration_sec,
    }
    if prior is not None and prior != row:
        raise IntegratedEnrollmentError(f"source identity collision: {source_id}")
    source_rows[source_id] = row
    return row


def _add_slice(
    source: SourceAudio,
    end_frame: int,
    *,
    source_hashes: dict[Path, str],
    source_rows: dict[str, dict[str, object]],
    slice_rows: dict[str, dict[str, object]],
) -> str:
    sealed = _seal_source(source, source_hashes=source_hashes, source_rows=source_rows)
    if end_frame < MINIMUM_MODEL_FRAMES or end_frame > source.frames:
        raise IntegratedEnrollmentError("slice violates ReDim duration/source bounds")
    slice_id = _slice_identity(
        str(sealed["source_id"]), str(sealed["source_sha256"]), 0, end_frame
    )
    row = {
        "slice_id": slice_id,
        "source_id": sealed["source_id"],
        "logical_path": source.logical_path,
        "source_sha256": sealed["source_sha256"],
        "start_frame": 0,
        "end_frame": end_frame,
        "duration_sec": end_frame / SAMPLE_RATE_HZ,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "channels": 1,
    }
    prior = slice_rows.get(slice_id)
    if prior is not None and prior != row:
        raise IntegratedEnrollmentError(f"slice identity collision: {slice_id}")
    slice_rows[slice_id] = row
    return slice_id


def _build_speaker_plan(
    speaker_source_id: str,
    chapters: Mapping[str, Sequence[SourceAudio]],
    *,
    source_hashes: dict[Path, str],
    source_rows: dict[str, dict[str, object]],
    slice_rows: dict[str, dict[str, object]],
    probes_per_speaker: int,
) -> dict[str, object] | None:
    ordered_chapters = list(
        _stable_order(chapters, scope=("chapter-order", speaker_source_id))
    )
    for chapter_ids in permutations(ordered_chapters, 3):
        chapter_a = tuple(chapters[str(chapter_ids[0])])
        chapter_b = tuple(chapters[str(chapter_ids[1])])
        chapter_c = tuple(chapters[str(chapter_ids[2])])
        probe_sources = [row for row in chapter_c if row.frames >= PROBE_FRAMES]
        probe_sources = list(
            _stable_order(
                probe_sources,
                scope=("probes", speaker_source_id, str(chapter_ids[2])),
            )
        )[:probes_per_speaker]
        if len(probe_sources) != probes_per_speaker:
            continue
        raw_sets: list[dict[str, object]] = []
        feasible = True
        for utterances, duration, sessions in product(
            MATRIX_AXES["utterances"],
            MATRIX_AXES["total_duration_sec"],
            MATRIX_AXES["sessions"],
        ):
            target_frames = int(round(float(duration) * SAMPLE_RATE_HZ))
            orders = _candidate_enrollment_orders(
                chapter_a,
                chapter_b,
                utterances=int(utterances),
                target_frames=target_frames,
                sessions=str(sessions),
                scope=(speaker_source_id, chapter_ids, utterances, duration, sessions),
            )
            if len(orders) < MAX_ENROLLMENT_ATTEMPTS:
                feasible = False
                break
            raw_sets.append(
                {
                    "utterances": int(utterances),
                    "total_duration_sec": float(duration),
                    "sessions": str(sessions),
                    "target_frames": target_frames,
                    "orders": orders,
                }
            )
        if not feasible:
            continue
        enrollment_sets: list[dict[str, object]] = []
        for raw in raw_sets:
            attempts: list[dict[str, object]] = []
            target_frames = int(raw["target_frames"])
            contributions = _balanced_contribution_frames(
                target_frames, int(raw["utterances"])
            )
            for attempt_index, order in enumerate(raw["orders"]):
                slice_ids = [
                    _add_slice(
                        source,
                        frames,
                        source_hashes=source_hashes,
                        source_rows=source_rows,
                        slice_rows=slice_rows,
                    )
                    for source, frames in zip(order, contributions, strict=True)
                ]
                attempts.append(
                    {
                        "attempt_index": attempt_index,
                        "slice_ids": slice_ids,
                        "chapter_ids": [
                            _safe_id("session", source.chapter_source_id)
                            for source in order
                        ],
                        "slice_duration_sec": [
                            frames / SAMPLE_RATE_HZ for frames in contributions
                        ],
                        "contribution_frames": list(contributions),
                        "exact_total_duration_sec": sum(contributions) / SAMPLE_RATE_HZ,
                        "duration_allocation_policy": ENROLLMENT_DURATION_ALLOCATION_POLICY,
                        "source_was_truncated": [
                            frames < source.frames
                            for source, frames in zip(order, contributions, strict=True)
                        ],
                        "all_contributions_within_source_bounds": all(
                            frames <= source.frames
                            for source, frames in zip(order, contributions, strict=True)
                        ),
                    }
                )
            set_axes = {
                "utterances": raw["utterances"],
                "total_duration_sec": raw["total_duration_sec"],
                "sessions": raw["sessions"],
            }
            enrollment_sets.append(
                {
                    **set_axes,
                    "physical_set_id": "enset_"
                    + canonical_sha256(
                        {
                            "speaker": speaker_source_id,
                            "axes": set_axes,
                            "attempts": attempts,
                        }
                    )[:20],
                    "attempts": attempts,
                }
            )
        probes = [
            {
                "probe_id": _safe_id(
                    "probe", (speaker_source_id, index, source.logical_path)
                ),
                "slice_id": _add_slice(
                    source,
                    PROBE_FRAMES,
                    source_hashes=source_hashes,
                    source_rows=source_rows,
                    slice_rows=slice_rows,
                ),
                "duration_sec": PROBE_FRAMES / SAMPLE_RATE_HZ,
            }
            for index, source in enumerate(probe_sources)
        ]
        return {
            "speaker_id": _safe_id("speaker", speaker_source_id),
            "session_a_id": _safe_id("session", chapter_ids[0]),
            "session_b_id": _safe_id("session", chapter_ids[1]),
            "probe_session_id": _safe_id("session", chapter_ids[2]),
            "enrollment_sets": enrollment_sets,
            "probes": probes,
        }
    return None


def build_panel_manifest(
    dataset_root: Path | None = None,
    *,
    speakers_per_role: int = SPEAKERS_PER_ROLE,
    probes_per_speaker: int = PROBES_PER_SPEAKER,
) -> dict[str, object]:
    """Predeclare a deterministic speaker/session-disjoint development panel."""

    if speakers_per_role < 1 or probes_per_speaker < 1:
        raise IntegratedEnrollmentError("panel role/probe counts must be positive")
    root = Path(dataset_root or default_librispeech_root()).resolve()
    inventory = _speaker_inventory(root)
    source_hashes: dict[Path, str] = {}
    source_rows: dict[str, dict[str, object]] = {}
    slice_rows: dict[str, dict[str, object]] = {}
    qualified: list[tuple[str, dict[str, object]]] = []
    speaker_ids = _stable_order(inventory, scope="qualified-speakers")
    required = speakers_per_role * len(ROLE_ORDER)
    for speaker_source_id in speaker_ids:
        plan = _build_speaker_plan(
            str(speaker_source_id),
            inventory[str(speaker_source_id)],
            source_hashes=source_hashes,
            source_rows=source_rows,
            slice_rows=slice_rows,
            probes_per_speaker=probes_per_speaker,
        )
        if plan is not None:
            qualified.append((str(speaker_source_id), plan))
        if len(qualified) >= required:
            break
    if len(qualified) < required:
        raise IntegratedEnrollmentError(
            "train-clean-100 has too few speakers satisfying the sealed "
            f"three-session/exact-budget contract: required={required}, "
            f"qualified={len(qualified)}"
        )
    roles: dict[str, list[dict[str, object]]] = {role: [] for role in ROLE_ORDER}
    for index, (_source_id, plan) in enumerate(qualified[:required]):
        role = ROLE_ORDER[index // speakers_per_role]
        value = dict(plan)
        value["role"] = role
        # Stranger enrollment source choices are deliberately removed from the
        # public/execution panel; strangers contribute probes only.
        if role.endswith("stranger"):
            value["enrollment_sets"] = []
        roles[role].append(value)
    used_slice_ids = {
        str(probe["slice_id"])
        for values in roles.values()
        for speaker in values
        for probe in speaker["probes"]
    }
    used_slice_ids.update(
        str(slice_id)
        for role in ("calibration_known", "selection_known")
        for speaker in roles[role]
        for enrollment_set in speaker["enrollment_sets"]
        for attempt in enrollment_set["attempts"]
        for slice_id in attempt["slice_ids"]
    )
    kept_slices = {key: slice_rows[key] for key in sorted(used_slice_ids)}
    used_source_ids = {str(row["source_id"]) for row in kept_slices.values()}
    kept_sources = {key: source_rows[key] for key in sorted(used_source_ids)}
    unsigned = {
        "schema_version": PANEL_SCHEMA_VERSION,
        "dataset_id": "LibriSpeech_train-clean-100_development_research_only",
        "dataset_root_logical": "Raw Datasets (Not formatted)/LibreSpeech/train-clean-100/LibriSpeech/train-clean-100",
        "seed": SEED,
        "backend_id": BACKEND_ID,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "minimum_model_duration_sec": MINIMUM_MODEL_FRAMES / SAMPLE_RATE_HZ,
        "probe_duration_sec": PROBE_FRAMES / SAMPLE_RATE_HZ,
        "probes_per_speaker": probes_per_speaker,
        "speakers_per_role": speakers_per_role,
        "roles": roles,
        "sources": kept_sources,
        "slices": kept_slices,
        "matrix_axes": {key: list(values) for key, values in MATRIX_AXES.items()},
        "enrollment_duration_allocation_policy": ENROLLMENT_DURATION_ALLOCATION_POLICY,
        "calibration_selection_speaker_disjoint": True,
        "known_stranger_speaker_disjoint": True,
        "enrollment_probe_session_disjoint": True,
        "enrollment_probe_audio_overlap": False,
        "evaluation_or_heldout_material_used": False,
        "implicit_downloads_allowed": False,
    }
    panel_sha = canonical_sha256(unsigned)
    return {
        **unsigned,
        "panel_sha256": panel_sha,
        "panel_id": f"h2_enrollment_train_clean_100_{panel_sha[:12]}",
        # Operational resolution is intentionally outside the scientific panel
        # hash. Exact selected source bytes are bound by per-file SHA-256.
        "dataset_root": str(root),
    }


def validate_panel_manifest(panel: Mapping[str, object]) -> None:
    """Fail closed on panel identity, disjointness, or duration drift."""

    if panel.get("schema_version") != PANEL_SCHEMA_VERSION:
        raise IntegratedEnrollmentError("integrated enrollment panel schema differs")
    unsigned = dict(panel)
    declared = str(unsigned.pop("panel_sha256", ""))
    unsigned.pop("panel_id", None)
    unsigned.pop("dataset_root", None)
    if declared != canonical_sha256(unsigned):
        raise IntegratedEnrollmentError("integrated enrollment panel checksum differs")
    roles = panel.get("roles")
    slices = panel.get("slices")
    sources = panel.get("sources")
    if (
        not isinstance(roles, Mapping)
        or not isinstance(slices, Mapping)
        or not isinstance(sources, Mapping)
    ):
        raise IntegratedEnrollmentError("panel roles/slices/sources are invalid")
    role_speakers: dict[str, set[str]] = {}
    for role in ROLE_ORDER:
        values = roles.get(role)
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise IntegratedEnrollmentError(f"panel role is invalid: {role}")
        role_speakers[role] = {str(row["speaker_id"]) for row in values}
        if len(role_speakers[role]) != len(values):
            raise IntegratedEnrollmentError(f"duplicate speaker in role: {role}")
    for left, right in combinations(ROLE_ORDER, 2):
        if role_speakers[left] & role_speakers[right]:
            raise IntegratedEnrollmentError(f"speaker roles overlap: {left}/{right}")
    for role in ("calibration_known", "selection_known"):
        for speaker in roles[role]:
            probe_session = str(speaker["probe_session_id"])
            for enrollment_set in speaker["enrollment_sets"]:
                utterances = int(enrollment_set["utterances"])
                target = float(enrollment_set["total_duration_sec"])
                target_frames = int(round(target * SAMPLE_RATE_HZ))
                expected_contributions = _balanced_contribution_frames(
                    target_frames, utterances
                )
                expected_sessions = str(enrollment_set["sessions"])
                attempts = enrollment_set["attempts"]
                if len(attempts) < MAX_ENROLLMENT_ATTEMPTS:
                    raise IntegratedEnrollmentError("panel lacks repeat attempts")
                attempt_sources: list[set[str]] = []
                for attempt in attempts:
                    ids = list(map(str, attempt["slice_ids"]))
                    if len(ids) != utterances or len(set(ids)) != len(ids):
                        raise IntegratedEnrollmentError("enrollment count differs")
                    if attempt.get("duration_allocation_policy") != (
                        ENROLLMENT_DURATION_ALLOCATION_POLICY
                    ):
                        raise IntegratedEnrollmentError(
                            "enrollment duration allocation policy differs"
                        )
                    declared_contributions = tuple(
                        int(value) for value in attempt.get("contribution_frames", ())
                    )
                    if declared_contributions != expected_contributions:
                        raise IntegratedEnrollmentError(
                            "enrollment frame contributions differ from sealed allocation"
                        )
                    duration = sum(float(slices[item]["duration_sec"]) for item in ids)
                    if not math.isclose(duration, target, abs_tol=1 / SAMPLE_RATE_HZ):
                        raise IntegratedEnrollmentError(
                            "enrollment budget is not exact"
                        )
                    if any(
                        float(slices[item]["duration_sec"])
                        < MINIMUM_MODEL_FRAMES / SAMPLE_RATE_HZ
                        for item in ids
                    ):
                        raise IntegratedEnrollmentError("enrollment slice is too short")
                    sessions = set(map(str, attempt["chapter_ids"]))
                    if probe_session in sessions:
                        raise IntegratedEnrollmentError(
                            "enrollment/probe session overlap"
                        )
                    if expected_sessions == "single" and len(sessions) != 1:
                        raise IntegratedEnrollmentError(
                            "single-session set spans sessions"
                        )
                    if expected_sessions == "varied" and len(sessions) < 2:
                        raise IntegratedEnrollmentError(
                            "varied-session set is not varied"
                        )
                    source_ids = {str(slices[item]["source_id"]) for item in ids}
                    attempt_sources.append(source_ids)
                    for index, item in enumerate(ids):
                        slice_row = slices[item]
                        source_row = sources[str(slice_row["source_id"])]
                        start_frame = int(slice_row["start_frame"])
                        end_frame = int(slice_row["end_frame"])
                        contribution = end_frame - start_frame
                        if (
                            start_frame != 0
                            or contribution != expected_contributions[index]
                        ):
                            raise IntegratedEnrollmentError(
                                "enrollment slice differs from exact frame allocation"
                            )
                        if end_frame > int(source_row["frames"]):
                            raise IntegratedEnrollmentError(
                                "enrollment slice exceeds its source recording"
                            )
                    expected_truncation = [
                        int(slices[item]["end_frame"])
                        < int(sources[str(slices[item]["source_id"])]["frames"])
                        for item in ids
                    ]
                    if (
                        list(attempt.get("source_was_truncated", ()))
                        != expected_truncation
                    ):
                        raise IntegratedEnrollmentError(
                            "enrollment source-truncation declaration differs"
                        )
                    if (
                        attempt.get("all_contributions_within_source_bounds")
                        is not True
                    ):
                        raise IntegratedEnrollmentError(
                            "enrollment source-bound declaration differs"
                        )
                if any(
                    left & right
                    for index, left in enumerate(attempt_sources)
                    for right in attempt_sources[index + 1 :]
                ):
                    raise IntegratedEnrollmentError(
                        "repeat enrollment attempts reuse rejected source audio"
                    )
            enrollment_source_ids = {
                str(slices[slice_id]["source_id"])
                for enrollment_set in speaker["enrollment_sets"]
                for attempt in enrollment_set["attempts"]
                for slice_id in attempt["slice_ids"]
            }
            probe_source_ids = {
                str(slices[probe["slice_id"]]["source_id"])
                for probe in speaker["probes"]
            }
            if enrollment_source_ids & probe_source_ids:
                raise IntegratedEnrollmentError(
                    "enrollment/probe source audio overlaps"
                )


def _backend_runtime_identity() -> dict[str, object]:
    identity = backend_identity(BACKEND_ID, 192).to_jsonable()
    return {
        **identity,
        "preprocessing_contract": {
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "channels": 1,
            "dtype": "float32",
            "adapter_padding_or_cropping": "none",
            "slice_origin": "source_frame_zero",
        },
        "cache_schema_version": CACHE_SCHEMA_VERSION,
    }


def _cache_runtime_sha256(panel: Mapping[str, object]) -> str:
    return canonical_sha256(
        {
            "panel_sha256": panel["panel_sha256"],
            "backend": _backend_runtime_identity(),
            "module_sha256": sha256_file(Path(__file__)),
        }
    )


def _cache_item_path(cache_root: Path, slice_id: str) -> Path:
    return cache_root / "items" / slice_id[6:8] / f"{slice_id}.npz"


def _vector_sha256(vector: np.ndarray) -> str:
    canonical = np.asarray(vector, dtype="<f4").reshape(-1)
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def _read_cache_item(path: Path) -> dict[str, object]:
    with np.load(path, allow_pickle=False) as bundle:
        metadata = json.loads(str(bundle["metadata_json"][0]))
        vector = np.asarray(bundle["vector"], dtype=np.float32).reshape(-1)
    metadata["vector"] = vector
    return metadata


def _valid_cache_item(
    path: Path,
    slice_row: Mapping[str, object],
    *,
    runtime_sha256: str,
) -> bool:
    try:
        value = _read_cache_item(path)
        vector = np.asarray(value.pop("vector"), dtype=np.float32)
        expected = {
            "schema_version": CACHE_ITEM_SCHEMA_VERSION,
            "slice_id": slice_row["slice_id"],
            "source_sha256": slice_row["source_sha256"],
            "start_frame": int(slice_row["start_frame"]),
            "end_frame": int(slice_row["end_frame"]),
            "runtime_cache_sha256": runtime_sha256,
            "backend_id": BACKEND_ID,
        }
        if any(
            value.get(key) != expected_value for key, expected_value in expected.items()
        ):
            return False
        if str(value.get("status")) != "ok":
            return False
        if vector.shape != (192,) or not np.isfinite(vector).all():
            return False
        if not math.isclose(float(np.linalg.norm(vector)), 1.0, abs_tol=1e-4):
            return False
        if value.get("vector_sha256") != _vector_sha256(vector):
            return False
        item_unsigned = dict(value)
        declared = str(item_unsigned.pop("cache_item_sha256", ""))
        return declared == canonical_sha256(item_unsigned)
    except Exception:
        return False


def _write_cache_item(
    path: Path, metadata: Mapping[str, object], vector: np.ndarray
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        with temporary.open("wb") as stream:
            np.savez(
                stream,
                metadata_json=np.asarray(
                    [json.dumps(dict(metadata), sort_keys=True, separators=(",", ":"))]
                ),
                vector=np.asarray(vector, dtype=np.float32),
            )
            stream.flush()
            os.fsync(stream.fileno())
        with np.load(temporary, allow_pickle=False) as bundle:
            if np.asarray(bundle["vector"]).shape != (192,):
                raise IntegratedEnrollmentError(
                    "temporary embedding cache shape differs"
                )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def audio_quality_metrics(samples: np.ndarray, sample_rate_hz: int) -> dict[str, float]:
    """Return declared, deterministic audio-only QC scalar diagnostics."""

    values = np.asarray(samples, dtype=np.float32).reshape(-1)
    if not len(values) or not np.isfinite(values).all():
        raise IntegratedEnrollmentError("QC audio is empty or non-finite")
    rms = float(np.sqrt(np.mean(np.square(values, dtype=np.float64))))
    level = 20.0 * math.log10(max(rms, 1e-8))
    clipping = float(np.mean(np.abs(values) >= 0.999))
    frame = max(
        1, int(round(sample_rate_hz * int(QC_POLICY["voiced_frame_ms"]) / 1000))
    )
    pad = (-len(values)) % frame
    framed = (
        np.pad(values, (0, pad)).reshape(-1, frame)
        if pad
        else values.reshape(-1, frame)
    )
    frame_rms = np.sqrt(np.mean(np.square(framed, dtype=np.float64), axis=1))
    threshold = 10.0 ** (float(QC_POLICY["voiced_absolute_threshold_dbfs"]) / 20.0)
    voiced = frame_rms >= threshold
    voiced_proportion = float(np.mean(voiced))
    voiced_duration = float(np.sum(voiced) * frame / sample_rate_hz)
    p10, p90 = np.quantile(frame_rms, [0.10, 0.90])
    noise_proxy = 20.0 * math.log10(max(float(p90), 1e-8) / max(float(p10), 1e-8))
    return {
        "level_dbfs": level,
        "clipping_fraction": clipping,
        "voiced_proportion": voiced_proportion,
        "voiced_duration_sec": min(voiced_duration, len(values) / sample_rate_hz),
        "declared_noise_proxy_db": noise_proxy,
    }


def _audio_qc_reasons(metrics: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    checks = (
        (
            "voiced_duration_sec",
            "minimum_voiced_duration_sec",
            "INSUFFICIENT_VOICED_DURATION",
            "min",
        ),
        (
            "voiced_proportion",
            "minimum_voiced_proportion",
            "LOW_VOICED_PROPORTION",
            "min",
        ),
        ("level_dbfs", "minimum_level_dbfs", "LOW_LEVEL", "min"),
        ("clipping_fraction", "maximum_clipping_fraction", "CLIPPING", "max"),
        (
            "declared_noise_proxy_db",
            "minimum_declared_noise_proxy_db",
            "NOISE_PROXY_BELOW_GATE",
            "min",
        ),
    )
    for metric, gate, reason, direction in checks:
        value = float(metrics[metric])
        threshold = float(QC_POLICY[gate])
        if (direction == "min" and value < threshold) or (
            direction == "max" and value > threshold
        ):
            reasons.append(reason)
    return reasons


def template_quality_metrics(vectors: Sequence[Sequence[float]]) -> dict[str, object]:
    """Compute pairwise, centroid, and leave-one-out enrollment consistency."""

    matrix = np.asarray([normalize_vector(row) for row in vectors], dtype=np.float64)
    if matrix.ndim != 2 or len(matrix) < 2:
        raise IntegratedEnrollmentError("template QC requires at least two vectors")
    # These enrollment sets are deliberately small.  Explicit reductions avoid
    # dispatching hundreds of tiny products through a platform BLAS runtime;
    # the Windows MKL build used by the campaign can otherwise abort the whole
    # controller during repeated quality sweeps.  The formula remains the
    # ordinary dot product and is deterministic across Windows and ARM64 Linux.
    similarities = np.einsum("ij,kj->ik", matrix, matrix, optimize=False)
    upper = similarities[np.triu_indices(len(matrix), 1)]
    centroid = np.asarray(normalize_vector(matrix.mean(axis=0)), dtype=np.float64)
    centroid_scores = np.sum(matrix * centroid, axis=1)
    leave_one_out: list[float] = []
    for index in range(len(matrix)):
        peer = np.delete(matrix, index, axis=0)
        peer_centroid = np.asarray(
            normalize_vector(peer.mean(axis=0)), dtype=np.float64
        )
        leave_one_out.append(float(np.sum(matrix[index] * peer_centroid)))
    return {
        "mean_pairwise_template_cosine": float(np.mean(upper)),
        "minimum_pairwise_template_cosine": float(np.min(upper)),
        "mean_centroid_consistency": float(np.mean(centroid_scores)),
        "minimum_centroid_consistency": float(np.min(centroid_scores)),
        "minimum_leave_one_out_cosine": float(min(leave_one_out)),
        "leave_one_out_outlier_index": int(np.argmin(leave_one_out)),
    }


def _template_qc_reasons(metrics: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    if float(metrics["minimum_pairwise_template_cosine"]) < float(
        QC_POLICY["minimum_pairwise_template_cosine"]
    ):
        reasons.append("PAIRWISE_TEMPLATE_COHESION")
    if float(metrics["minimum_centroid_consistency"]) < float(
        QC_POLICY["minimum_centroid_consistency"]
    ):
        reasons.append("CENTROID_CONSISTENCY")
    if float(metrics["minimum_leave_one_out_cosine"]) < float(
        QC_POLICY["minimum_leave_one_out_cosine"]
    ):
        reasons.append("LEAVE_ONE_OUT_OUTLIER")
    return reasons


def _require_c_drive_reserve(minimum_gib: float = 35.0) -> None:
    usage = shutil.disk_usage(Path("C:/"))
    if usage.free < minimum_gib * 1024**3:
        raise IntegratedEnrollmentError(
            f"C: free-space reserve is below {minimum_gib:g} GiB; "
            "no new enrollment embedding slice was started"
        )


def _load_slice_samples(
    dataset_root: Path, slice_row: Mapping[str, object]
) -> np.ndarray:
    source = (dataset_root / str(slice_row["logical_path"])).resolve()
    try:
        source.relative_to(dataset_root.resolve())
    except ValueError as exc:
        raise IntegratedEnrollmentError(
            "panel source escaped train-clean-100 root"
        ) from exc
    if not source.is_file() or sha256_file(source) != str(slice_row["source_sha256"]):
        raise IntegratedEnrollmentError(
            f"panel source is missing or changed: {slice_row['slice_id']}"
        )
    start = int(slice_row["start_frame"])
    frames = int(slice_row["end_frame"]) - start
    values, rate = sf.read(
        source,
        start=start,
        frames=frames,
        dtype="float32",
        always_2d=False,
    )
    samples = np.asarray(values, dtype=np.float32).reshape(-1)
    if int(rate) != SAMPLE_RATE_HZ or len(samples) != frames:
        raise IntegratedEnrollmentError("decoded enrollment slice differs from panel")
    return samples


def _cache_metadata(
    slice_row: Mapping[str, object],
    vector: np.ndarray,
    quality: Mapping[str, object],
    *,
    runtime_sha256: str,
    extraction_sec: float,
) -> dict[str, object]:
    unsigned = {
        "schema_version": CACHE_ITEM_SCHEMA_VERSION,
        "slice_id": slice_row["slice_id"],
        "source_sha256": slice_row["source_sha256"],
        "start_frame": int(slice_row["start_frame"]),
        "end_frame": int(slice_row["end_frame"]),
        "duration_sec": float(slice_row["duration_sec"]),
        "runtime_cache_sha256": runtime_sha256,
        "backend_id": BACKEND_ID,
        "backend_identity_hash": _backend_runtime_identity()["identity_hash"],
        "status": "ok",
        "embedding_dimension": 192,
        "vector_sha256": _vector_sha256(vector),
        "extraction_sec": float(extraction_sec),
        "audio_quality": dict(quality),
        "biometric_vector_private": True,
        "public_export_allowed": False,
    }
    return {**unsigned, "cache_item_sha256": canonical_sha256(unsigned)}


def extract_slices_with_embedder(
    panel: Mapping[str, object],
    cache_root: Path,
    slice_ids: Sequence[str],
    embedder: Callable[[np.ndarray, Mapping[str, object]], Sequence[float]],
    *,
    require_storage_reserve: Callable[[], None] | None = None,
) -> dict[str, object]:
    """Model-independent cache loop used by the isolated worker and tests."""

    validate_panel_manifest(panel)
    root = Path(cache_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    slices = panel["slices"]
    if not isinstance(slices, Mapping):
        raise IntegratedEnrollmentError("panel slices are invalid")
    dataset_root = Path(str(panel["dataset_root"])).resolve()
    runtime_sha = _cache_runtime_sha256(panel)
    completed = reused = repaired = 0
    for index, slice_id in enumerate(slice_ids, start=1):
        if slice_id not in slices:
            raise IntegratedEnrollmentError(f"worker slice is absent: {slice_id}")
        row = slices[slice_id]
        if not isinstance(row, Mapping):
            raise IntegratedEnrollmentError(f"worker slice row is invalid: {slice_id}")
        path = _cache_item_path(root, slice_id)
        if path.is_file() and _valid_cache_item(path, row, runtime_sha256=runtime_sha):
            reused += 1
            continue
        if path.exists():
            quarantine = path.with_name(
                f"{path.name}.corrupt-{int(time.time())}-{uuid.uuid4().hex[:8]}"
            )
            os.replace(path, quarantine)
            repaired += 1
        (require_storage_reserve or _require_c_drive_reserve)()
        samples = _load_slice_samples(dataset_root, row)
        quality = audio_quality_metrics(samples, SAMPLE_RATE_HZ)
        started = time.perf_counter()
        vector = np.asarray(normalize_vector(embedder(samples, row)), dtype=np.float32)
        elapsed = time.perf_counter() - started
        if vector.shape != (192,) or not np.isfinite(vector).all():
            raise IntegratedEnrollmentError(
                f"ReDimNet2 returned an invalid vector for {slice_id}"
            )
        metadata = _cache_metadata(
            row,
            vector,
            quality,
            runtime_sha256=runtime_sha,
            extraction_sec=elapsed,
        )
        _write_cache_item(path, metadata, vector)
        if not _valid_cache_item(path, row, runtime_sha256=runtime_sha):
            raise IntegratedEnrollmentError(
                f"published cache item is invalid: {slice_id}"
            )
        completed += 1
        write_json_atomic(
            root / "progress.json",
            {
                "schema_version": "h2-integrated-enrollment-progress.v1",
                "panel_sha256": panel["panel_sha256"],
                "runtime_cache_sha256": runtime_sha,
                "current_slice_id": slice_id,
                "processed_this_worker": index,
                "requested_this_worker": len(slice_ids),
                "new_items_this_worker": completed,
                "reused_items_this_worker": reused,
                "corrupt_items_repaired_this_worker": repaired,
                "updated_at_unix_sec": time.time(),
            },
        )
    return {
        "requested": len(slice_ids),
        "completed": completed,
        "reused": reused,
        "corrupt_repaired": repaired,
        "runtime_cache_sha256": runtime_sha,
    }


def _native_redim_embedder(
    dataset_root: Path,
) -> Callable[[np.ndarray, Mapping[str, object]], Sequence[float]]:
    """Load the qualified native adapter once, with downloads disabled."""

    from app.inference_pipeline.speaker_embedding import (
        build_speaker_embedding_from_config,
    )
    from app.speaker_protocol.extraction import _embedding_config

    adapter = build_speaker_embedding_from_config(_embedding_config(BACKEND_ID))
    if adapter is None:
        raise IntegratedEnrollmentError("qualified ReDimNet2 adapter did not resolve")
    counter = 0

    def embed(samples: np.ndarray, slice_row: Mapping[str, object]) -> Sequence[float]:
        nonlocal counter
        counter += 1
        source = (dataset_root / str(slice_row["logical_path"])).resolve()
        start_sec = int(slice_row["start_frame"]) / SAMPLE_RATE_HZ
        end_sec = int(slice_row["end_frame"]) / SAMPLE_RATE_HZ
        segment = AudioSegment(
            audio_path=source,
            start_sec=start_sec,
            end_sec=end_sec,
            duration_sec=end_sec - start_sec,
            sample_rate_hz=SAMPLE_RATE_HZ,
            channel_count=1,
            is_mono=True,
        )
        context = SpeakerEmbeddingContext(
            recording_id=f"h2_enrollment_worker_{os.getpid()}",
            utt_id=f"slice_{counter}",
            source_audio_path=source,
            segment_start_sec=start_sec,
            segment_end_sec=end_sec,
            device="cpu",
            dtype="float32",
            run_config={
                "project_root": str(repository_root().path),
                "runtime": {
                    "device": "cpu",
                    "precision": "float32",
                    "sample_rate_hz": SAMPLE_RATE_HZ,
                    "allow_model_downloads": False,
                },
            },
        )
        result = adapter.embed(segment, context)
        if result.status != "ok":
            raise IntegratedEnrollmentError(
                f"ReDimNet2 extraction status is {result.status!r}"
            )
        return result.vector

    return embed


def _worker(request_path: Path) -> int:
    request = read_json(request_path)
    if request.get("schema_version") != WORKER_REQUEST_SCHEMA_VERSION:
        raise IntegratedEnrollmentError("enrollment worker request schema differs")
    panel_path = Path(str(request["panel_path"])).resolve()
    panel = read_json(panel_path)
    if panel.get("panel_sha256") != request.get("panel_sha256"):
        raise IntegratedEnrollmentError("worker panel checksum differs")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["TORCH_HOME"] = str(repository_root().path / "models" / "cache")
    result = extract_slices_with_embedder(
        panel,
        Path(str(request["cache_root"])),
        [str(value) for value in request.get("slice_ids") or ()],
        _native_redim_embedder(Path(str(panel["dataset_root"])).resolve()),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


def _all_required_slice_ids(panel: Mapping[str, object]) -> tuple[str, ...]:
    slices = panel.get("slices")
    if not isinstance(slices, Mapping):
        raise IntegratedEnrollmentError("panel slices are invalid")
    return tuple(sorted(map(str, slices)))


def validate_private_cache(
    panel: Mapping[str, object], cache_root: Path
) -> dict[str, object]:
    validate_panel_manifest(panel)
    root = Path(cache_root).resolve()
    slices = panel["slices"]
    assert isinstance(slices, Mapping)
    runtime_sha = _cache_runtime_sha256(panel)
    invalid = []
    manifest_rows: list[dict[str, object]] = []
    for slice_id in _all_required_slice_ids(panel):
        row = slices[slice_id]
        assert isinstance(row, Mapping)
        path = _cache_item_path(root, slice_id)
        if not path.is_file() or not _valid_cache_item(
            path, row, runtime_sha256=runtime_sha
        ):
            invalid.append(slice_id)
            continue
        value = _read_cache_item(path)
        value.pop("vector", None)
        manifest_rows.append(
            {
                "slice_id": slice_id,
                "cache_item_sha256": value["cache_item_sha256"],
                "vector_sha256": value["vector_sha256"],
                "source_sha256": value["source_sha256"],
                "duration_sec": value["duration_sec"],
                "extraction_sec": value["extraction_sec"],
                "backend_identity_hash": value["backend_identity_hash"],
                "status": value["status"],
                "biometric_vector_exported": False,
            }
        )
    if invalid:
        raise IntegratedEnrollmentError(
            f"private enrollment cache is incomplete/invalid: {invalid[:5]}"
        )
    unsigned = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "panel_sha256": panel["panel_sha256"],
        "runtime_cache_sha256": runtime_sha,
        "backend_identity": _backend_runtime_identity(),
        "item_count": len(manifest_rows),
        "items_sha256": canonical_sha256(manifest_rows),
        "private_cache_root": str(root),
        "public_vectors_exported": False,
    }
    summary = {**unsigned, "cache_manifest_sha256": canonical_sha256(unsigned)}
    write_json_atomic(root / "cache_manifest.json", summary)
    return {**summary, "rows": manifest_rows}


def ensure_private_embeddings(
    panel: Mapping[str, object], cache_root: Path
) -> dict[str, object]:
    """Launch the isolated ReDim worker only for missing/corrupt slices."""

    validate_panel_manifest(panel)
    root = Path(cache_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    panel_path = root / "panel_manifest.json"
    if panel_path.is_file():
        existing = read_json(panel_path)
        if existing != dict(panel):
            raise IntegratedEnrollmentError("private cache belongs to another panel")
    else:
        write_json_atomic(panel_path, panel)
    identity = _backend_runtime_identity()
    identity_path = root / "backend_identity.json"
    if identity_path.is_file() and read_json(identity_path) != identity:
        raise IntegratedEnrollmentError("private cache backend identity changed")
    write_json_atomic(identity_path, identity)
    runtime_sha = _cache_runtime_sha256(panel)
    slices = panel["slices"]
    assert isinstance(slices, Mapping)
    missing: list[str] = []
    corrupt = 0
    for slice_id in _all_required_slice_ids(panel):
        row = slices[slice_id]
        assert isinstance(row, Mapping)
        path = _cache_item_path(root, slice_id)
        if path.is_file() and _valid_cache_item(path, row, runtime_sha256=runtime_sha):
            continue
        if path.exists():
            quarantine = path.with_name(
                f"{path.name}.corrupt-{int(time.time())}-{uuid.uuid4().hex[:8]}"
            )
            os.replace(path, quarantine)
            corrupt += 1
        missing.append(slice_id)
    if missing:
        _require_c_drive_reserve()
        from app.h2_portability.interpreters import resolve_worker_interpreter

        resolution = resolve_worker_interpreter(
            "redimnet2", repository=repository_root().path
        )
        if resolution.path is None:
            raise IntegratedEnrollmentError("ReDimNet2 worker interpreter is absent")
        request = {
            "schema_version": WORKER_REQUEST_SCHEMA_VERSION,
            "panel_path": str(panel_path),
            "panel_sha256": panel["panel_sha256"],
            "cache_root": str(root),
            "runtime_cache_sha256": runtime_sha,
            "slice_ids": missing,
            "implicit_model_downloads_allowed": False,
        }
        request_path = root / "worker_request.json"
        write_json_atomic(request_path, request)
        env = os.environ.copy()
        env.update(
            {
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        attempt_id = f"attempt_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        log_path = root / "attempts" / f"{attempt_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(resolution.path),
            "-m",
            "app.h2_product_program.integrated_enrollment",
            "worker",
            "--request",
            str(request_path),
        ]
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        log_path.write_text(
            "COMMAND: "
            + json.dumps(command)
            + "\n\nSTDOUT:\n"
            + completed.stdout
            + "\nSTDERR:\n"
            + completed.stderr,
            encoding="utf-8",
        )
        write_json_atomic(
            root / "last_worker_receipt.json",
            {
                "schema_version": "h2-integrated-enrollment-worker-receipt.v1",
                "attempt_id": attempt_id,
                "request_sha256": sha256_file(request_path),
                "requested_missing_items": len(missing),
                "corrupt_items_quarantined": corrupt,
                "return_code": completed.returncode,
                "elapsed_sec": time.perf_counter() - started,
                "log_sha256": sha256_file(log_path),
                "interpreter_path": str(resolution.path),
                "environment_profile": "redimnet2",
            },
        )
        if completed.returncode != 0:
            raise IntegratedEnrollmentError(
                f"isolated ReDimNet2 enrollment worker failed; see {log_path}"
            )
    return validate_private_cache(panel, root)


def _cache_observations(
    panel: Mapping[str, object], cache_root: Path
) -> dict[str, dict[str, object]]:
    validated = validate_private_cache(panel, cache_root)
    del validated
    output: dict[str, dict[str, object]] = {}
    for slice_id in _all_required_slice_ids(panel):
        output[slice_id] = _read_cache_item(_cache_item_path(cache_root, slice_id))
    return output


def normalized_mean(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    matrix = np.asarray([normalize_vector(row) for row in vectors], dtype=np.float64)
    return np.asarray(normalize_vector(matrix.mean(axis=0)), dtype=np.float64)


def score_enrollment(
    probe: Sequence[float], templates: Sequence[Sequence[float]], aggregation: str
) -> float:
    probe_vector = np.asarray(normalize_vector(probe), dtype=np.float64)
    if aggregation == "normalized_mean":
        return float(np.sum(probe_vector * normalized_mean(templates)))
    if aggregation == "frozen_redim_multi_template":
        scores = sorted(
            (
                float(
                    np.sum(
                        probe_vector
                        * np.asarray(normalize_vector(row), dtype=np.float64)
                    )
                )
                for row in templates
            ),
            reverse=True,
        )
        # Exact historical/application H2 ReDim policy.  Top-1/Top-2 in the
        # open-set layer means the best and second-best *identities*; it must
        # not be confused with averaging a speaker's two best templates.
        return float(scores[0])
    raise IntegratedEnrollmentError(
        f"unsupported enrollment aggregation: {aggregation}"
    )


def _physical_enrollment_set(
    speaker: Mapping[str, object], cell: Mapping[str, object]
) -> Mapping[str, object]:
    matching = [
        row
        for row in speaker.get("enrollment_sets") or ()
        if int(row["utterances"]) == int(cell["utterances"])
        and math.isclose(
            float(row["total_duration_sec"]),
            float(cell["total_duration_sec"]),
            abs_tol=1e-9,
        )
        and str(row["sessions"]) == str(cell["sessions"])
    ]
    if len(matching) != 1:
        raise IntegratedEnrollmentError(
            "speaker lacks one exact physical enrollment set"
        )
    return matching[0]


def _attempt_quality(
    attempt: Mapping[str, object],
    observations: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, object], list[str], list[dict[str, object]]]:
    slice_ids = list(map(str, attempt["slice_ids"]))
    vectors = [
        np.asarray(observations[slice_id]["vector"], dtype=np.float64)
        for slice_id in slice_ids
    ]
    template_metrics = template_quality_metrics(vectors)
    template_reasons = _template_qc_reasons(template_metrics)
    sample_rows: list[dict[str, object]] = []
    all_reasons = list(template_reasons)
    for sample_index, slice_id in enumerate(slice_ids):
        quality = observations[slice_id].get("audio_quality")
        if not isinstance(quality, Mapping):
            raise IntegratedEnrollmentError("cache item lacks audio QC scalars")
        reasons = _audio_qc_reasons(quality)
        all_reasons.extend(f"SAMPLE_{sample_index}:{reason}" for reason in reasons)
        sample_rows.append(
            {
                "sample_index": sample_index,
                "slice_id": slice_id,
                **{key: quality[key] for key in sorted(quality)},
                "audio_qc_pass": not reasons,
                "audio_qc_reasons": "|".join(reasons),
                "vector_sha256": observations[slice_id]["vector_sha256"],
                "backend_identity_hash": observations[slice_id][
                    "backend_identity_hash"
                ],
            }
        )
    return template_metrics, sorted(set(all_reasons)), sample_rows


def _templates_for_cell(
    panel: Mapping[str, object],
    observations: Mapping[str, Mapping[str, object]],
    *,
    role: str,
    cell: Mapping[str, object],
) -> tuple[
    dict[str, list[np.ndarray]],
    list[dict[str, object]],
    list[str],
    dict[str, list[str]],
]:
    roles = panel["roles"]
    assert isinstance(roles, Mapping)
    speakers = roles[role]
    templates: dict[str, list[np.ndarray]] = {}
    qc_rows: list[dict[str, object]] = []
    invalid_speakers: list[str] = []
    selected_slices: dict[str, list[str]] = {}
    for speaker in speakers:
        speaker_id = str(speaker["speaker_id"])
        enrollment_set = _physical_enrollment_set(speaker, cell)
        accepted: Mapping[str, object] | None = None
        attempts = enrollment_set["attempts"]
        for attempt in attempts:
            template_metrics, reasons, sample_rows = _attempt_quality(
                attempt, observations
            )
            blind = str(cell["quality_filter"]) == "blind_accept"
            attempt_accepted = blind or not reasons
            action = (
                "BLIND_ACCEPTED_WITH_DIAGNOSTICS"
                if blind
                else "QUALITY_ACCEPTED"
                if attempt_accepted
                else "REJECTED_REPEAT_REQUIRED"
            )
            base = {
                "cell_id": cell["cell_id"],
                "cohort_role": role,
                "speaker_id": speaker_id,
                "physical_set_id": enrollment_set["physical_set_id"],
                "attempt_index": attempt["attempt_index"],
                "quality_filter": cell["quality_filter"],
                "attempt_accepted": attempt_accepted,
                "attempt_action": action,
                "attempt_reasons": "|".join(reasons),
                **template_metrics,
                "backend_id": BACKEND_ID,
                "biometric_vector_exported": False,
            }
            for sample in sample_rows:
                qc_rows.append({**base, **sample})
            if attempt_accepted:
                accepted = attempt
                break
        if accepted is None:
            invalid_speakers.append(speaker_id)
            continue
        ids = list(map(str, accepted["slice_ids"]))
        selected_slices[speaker_id] = ids
        templates[speaker_id] = [
            np.asarray(observations[slice_id]["vector"], dtype=np.float64)
            for slice_id in ids
        ]
    return templates, qc_rows, invalid_speakers, selected_slices


def _probe_rows(panel: Mapping[str, object], role: str) -> list[dict[str, object]]:
    roles = panel["roles"]
    assert isinstance(roles, Mapping)
    output: list[dict[str, object]] = []
    for speaker in roles[role]:
        for probe in speaker["probes"]:
            output.append(
                {
                    **dict(probe),
                    "true_speaker_id": speaker["speaker_id"],
                    "true_partition": "known" if role.endswith("known") else "stranger",
                }
            )
    return output


def _score_probes(
    probes: Sequence[Mapping[str, object]],
    templates: Mapping[str, Sequence[Sequence[float]]],
    observations: Mapping[str, Mapping[str, object]],
    *,
    aggregation: str,
) -> tuple[list[dict[str, object]], float]:
    decisions: list[dict[str, object]] = []
    started = time.perf_counter()
    for probe in probes:
        vector = observations[str(probe["slice_id"])]["vector"]
        ranked = sorted(
            (
                (speaker_id, score_enrollment(vector, values, aggregation))
                for speaker_id, values in templates.items()
            ),
            key=lambda value: (-value[1], value[0]),
        )
        if not ranked:
            raise IntegratedEnrollmentError("full-gallery scoring has no identities")
        top1_id, top1 = ranked[0]
        top2_id, top2 = ranked[1] if len(ranked) > 1 else ("NO_SECOND_IDENTITY", -1.0)
        decisions.append(
            {
                "probe_id": probe["probe_id"],
                "probe_slice_id": probe["slice_id"],
                "true_speaker_id": probe["true_speaker_id"],
                "true_partition": probe["true_partition"],
                "top1_speaker_id": top1_id,
                "top2_speaker_id": top2_id,
                "top1_score": float(top1),
                "top2_score": float(top2),
                "top1_top2_margin": float(top1 - top2),
                "top1_correct": probe["true_partition"] == "known"
                and top1_id == probe["true_speaker_id"],
            }
        )
    elapsed = time.perf_counter() - started
    return decisions, elapsed


def _apply_policy(
    decisions: Sequence[Mapping[str, object]],
    *,
    threshold: float,
    margin: float,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in decisions:
        accepted = (
            float(row["top1_score"]) >= threshold
            and float(row["top1_top2_margin"]) >= margin
        )
        predicted = str(row["top1_speaker_id"]) if accepted else "Unknown"
        true_partition = str(row["true_partition"])
        true_speaker = str(row["true_speaker_id"])
        output.append(
            {
                **dict(row),
                "score_threshold": threshold,
                "margin_threshold": margin,
                "accepted_known": accepted,
                "predicted_speaker_id": predicted,
                "known_correct": true_partition == "known"
                and predicted == true_speaker,
                "wrong_known": true_partition == "known"
                and predicted not in {"Unknown", true_speaker},
                "known_unknown": true_partition == "known" and predicted == "Unknown",
                "stranger_false_known": true_partition == "stranger"
                and predicted != "Unknown",
            }
        )
    return output


def calibrate_policy(
    known: Sequence[Mapping[str, object]],
    strangers: Sequence[Mapping[str, object]],
    *,
    target_fpir: float = TARGET_FPIR,
) -> dict[str, object]:
    """Tune score/margin only on calibration identities at a fixed FPIR target."""

    if not known or not strangers:
        raise IntegratedEnrollmentError("open-set calibration cohorts are empty")
    stranger_speakers = sorted({str(row["true_speaker_id"]) for row in strangers})
    if not stranger_speakers:
        raise IntegratedEnrollmentError("open-set calibration has no stranger speakers")
    probe_resolution = 1.0 / len(strangers)
    speaker_resolution = 1.0 / len(stranger_speakers)
    thresholds = sorted({float(row["top1_score"]) for row in (*known, *strangers)})
    thresholds.append(
        math.nextafter(
            max(float(row["top1_score"]) for row in (*known, *strangers)),
            math.inf,
        )
    )
    candidates: list[dict[str, object]] = []
    for threshold, margin in product(thresholds, CALIBRATION_MARGINS):
        known_scored = _apply_policy(known, threshold=threshold, margin=margin)
        stranger_scored = _apply_policy(strangers, threshold=threshold, margin=margin)
        fp = sum(bool(row["stranger_false_known"]) for row in stranger_scored)
        probe_fpir = fp / len(stranger_scored)
        false_speakers = {
            str(row["true_speaker_id"])
            for row in stranger_scored
            if row["stranger_false_known"]
        }
        speaker_fpir = len(false_speakers) / len(stranger_speakers)
        # Repeated probes from one stranger are dependent.  Freeze safety at
        # the conservative speaker unit (any false-known probe makes that
        # stranger a false-positive identity) while retaining conventional
        # probe FPIR as a separately named diagnostic.
        if speaker_fpir > target_fpir + 1e-12:
            continue
        wrong = sum(bool(row["wrong_known"]) for row in known_scored)
        correct = sum(bool(row["known_correct"]) for row in known_scored)
        candidates.append(
            {
                "score_threshold": float(threshold),
                "margin_threshold": float(margin),
                "calibration_fpir": speaker_fpir,
                "calibration_fpir_unit": "stranger_speaker_any_false_known",
                "calibration_probe_fpir": probe_fpir,
                "calibration_speaker_fpir": speaker_fpir,
                "calibration_false_known_count": fp,
                "calibration_false_known_speaker_count": len(false_speakers),
                "calibration_wrong_known_rate": wrong / len(known_scored),
                "calibration_known_correct_rate": correct / len(known_scored),
            }
        )
    if not candidates:
        raise IntegratedEnrollmentError("calibration failed to produce a safe policy")
    # FPIR is a constraint, not an objective that would always prefer reject-all.
    # Within the target, wrong-known safety precedes known yield, followed by
    # stricter deterministic tie-breaking.
    chosen = min(
        candidates,
        key=lambda row: (
            float(row["calibration_wrong_known_rate"]),
            -float(row["calibration_known_correct_rate"]),
            -float(row["margin_threshold"]),
            -float(row["score_threshold"]),
        ),
    )
    return {
        **chosen,
        "target_fpir": target_fpir,
        "calibration_stranger_trials": len(strangers),
        "calibration_stranger_probe_trials": len(strangers),
        "calibration_stranger_speaker_trials": len(stranger_speakers),
        # Backward-compatible generic fields deliberately refer to the
        # decision unit that governed calibration: stranger speakers.
        "empirical_fpir_resolution": speaker_resolution,
        "empirical_probe_fpir_resolution": probe_resolution,
        "empirical_speaker_fpir_resolution": speaker_resolution,
        "target_fpir_demonstrable_at_trial_resolution": target_fpir + 1e-12
        >= speaker_resolution,
        "target_fpir_demonstrable_at_probe_resolution": target_fpir + 1e-12
        >= probe_resolution,
        "target_fpir_demonstrable_at_speaker_resolution": target_fpir + 1e-12
        >= speaker_resolution,
        "calibration_identity_firewall": "CALIBRATION_SPEAKERS_ONLY",
    }


def exact_binomial_upper_95(false_count: int, trial_count: int) -> float | None:
    """One-sided Clopper-Pearson 95% upper bound without SciPy."""

    if trial_count <= 0 or false_count < 0 or false_count > trial_count:
        return None
    if false_count == trial_count:
        return 1.0
    if false_count == 0:
        return 1.0 - 0.05 ** (1.0 / trial_count)

    def cdf(p: float) -> float:
        return sum(
            math.comb(trial_count, value)
            * p**value
            * (1.0 - p) ** (trial_count - value)
            for value in range(false_count + 1)
        )

    low, high = false_count / trial_count, 1.0
    for _ in range(100):
        midpoint = (low + high) / 2.0
        if cdf(midpoint) > 0.05:
            low = midpoint
        else:
            high = midpoint
    return high


def _decision_metrics(
    known: Sequence[Mapping[str, object]],
    strangers: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    known_count = len(known)
    stranger_count = len(strangers)
    correct = sum(bool(row["known_correct"]) for row in known)
    wrong = sum(bool(row["wrong_known"]) for row in known)
    rejected = sum(bool(row["known_unknown"]) for row in known)
    false_known = sum(bool(row["stranger_false_known"]) for row in strangers)
    stranger_speakers = sorted({str(row["true_speaker_id"]) for row in strangers})
    false_known_speakers = {
        str(row["true_speaker_id"]) for row in strangers if row["stranger_false_known"]
    }
    closed_top1 = sum(bool(row["top1_correct"]) for row in known)
    return {
        "known_probe_count": known_count,
        "stranger_probe_count": stranger_count,
        "known_correct_count": correct,
        "wrong_known_count": wrong,
        "known_unknown_count": rejected,
        "stranger_false_known_count": false_known,
        "stranger_speaker_count": len(stranger_speakers),
        "stranger_false_known_speaker_count": len(false_known_speakers),
        "known_correct_rate": correct / known_count if known_count else None,
        "wrong_known_rate": wrong / known_count if known_count else None,
        "known_unknown_rate": rejected / known_count if known_count else None,
        "stranger_fpir": false_known / stranger_count if stranger_count else None,
        "stranger_speaker_fpir": len(false_known_speakers) / len(stranger_speakers)
        if stranger_speakers
        else None,
        "unknown_rejection": 1.0 - false_known / stranger_count
        if stranger_count
        else None,
        "closed_set_top1_accuracy": closed_top1 / known_count if known_count else None,
        "empirical_fpir_resolution": 1.0 / len(stranger_speakers)
        if stranger_speakers
        else None,
        "empirical_probe_fpir_resolution": 1.0 / stranger_count
        if stranger_count
        else None,
        "empirical_speaker_fpir_resolution": 1.0 / len(stranger_speakers)
        if stranger_speakers
        else None,
        "stranger_fpir_upper_95": exact_binomial_upper_95(false_known, stranger_count),
        "stranger_speaker_fpir_upper_95": exact_binomial_upper_95(
            len(false_known_speakers), len(stranger_speakers)
        ),
    }


def _hubness_rows(
    cell_id: str,
    strangers: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    nearest = Counter(str(row["top1_speaker_id"]) for row in strangers)
    accepted = Counter(
        str(row["top1_speaker_id"]) for row in strangers if row["stranger_false_known"]
    )
    scores: dict[str, list[float]] = defaultdict(list)
    margins: dict[str, list[float]] = defaultdict(list)
    for row in strangers:
        if row["stranger_false_known"]:
            key = str(row["top1_speaker_id"])
            scores[key].append(float(row["top1_score"]))
            margins[key].append(float(row["top1_top2_margin"]))
    total = len(strangers)
    return [
        {
            "cell_id": cell_id,
            "candidate_speaker_id": speaker_id,
            "nearest_stranger_count": count,
            "nearest_stranger_share": count / total if total else None,
            "accepted_false_known_count": accepted[speaker_id],
            "maximum_accepted_impostor_score": max(scores[speaker_id])
            if scores[speaker_id]
            else None,
            "minimum_accepted_impostor_margin": min(margins[speaker_id])
            if margins[speaker_id]
            else None,
            "biometric_vector_exported": False,
        }
        for speaker_id, count in sorted(nearest.items())
    ]


def _cell_axes() -> Iterable[dict[str, object]]:
    names = tuple(MATRIX_AXES)
    for values in product(*(MATRIX_AXES[name] for name in names)):
        axes = dict(zip(names, values, strict=True))
        cell_id = "__".join(f"{name}={axes[name]}" for name in names)
        yield {**axes, "cell_id": cell_id}


def evaluate_integrated_matrix(
    panel: Mapping[str, object],
    observations: Mapping[str, Mapping[str, object]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    """Measure all 32 cells using calibration-only policies and selection data."""

    validate_panel_manifest(panel)
    matrix_rows: list[dict[str, object]] = []
    qc_rows: list[dict[str, object]] = []
    hubness_rows: list[dict[str, object]] = []
    for cell in _cell_axes():
        calibration_templates, calibration_qc, calibration_invalid, cal_slices = (
            _templates_for_cell(
                panel,
                observations,
                role="calibration_known",
                cell=cell,
            )
        )
        selection_templates, selection_qc, selection_invalid, sel_slices = (
            _templates_for_cell(
                panel,
                observations,
                role="selection_known",
                cell=cell,
            )
        )
        qc_rows.extend(calibration_qc)
        qc_rows.extend(selection_qc)
        invalid = sorted((*calibration_invalid, *selection_invalid))
        if invalid:
            matrix_rows.append(
                {
                    **cell,
                    "status": "TECHNICALLY_INVALID",
                    "technical_invalidity_reason": "quality-filtered repeat attempts exhausted",
                    "invalid_speaker_count": len(invalid),
                    "invalid_speaker_ids": "|".join(invalid),
                    "attempted": True,
                    "panel_sha256": panel["panel_sha256"],
                    "biometric_vector_exported": False,
                }
            )
            continue
        aggregation = str(cell["aggregation"])
        cal_known_raw, cal_known_time = _score_probes(
            _probe_rows(panel, "calibration_known"),
            calibration_templates,
            observations,
            aggregation=aggregation,
        )
        cal_stranger_raw, cal_stranger_time = _score_probes(
            _probe_rows(panel, "calibration_stranger"),
            calibration_templates,
            observations,
            aggregation=aggregation,
        )
        policy = calibrate_policy(cal_known_raw, cal_stranger_raw)
        threshold = float(policy["score_threshold"])
        margin = float(policy["margin_threshold"])
        selection_known_raw, selection_known_time = _score_probes(
            _probe_rows(panel, "selection_known"),
            selection_templates,
            observations,
            aggregation=aggregation,
        )
        selection_stranger_raw, selection_stranger_time = _score_probes(
            _probe_rows(panel, "selection_stranger"),
            selection_templates,
            observations,
            aggregation=aggregation,
        )
        selection_known = _apply_policy(
            selection_known_raw, threshold=threshold, margin=margin
        )
        selection_strangers = _apply_policy(
            selection_stranger_raw, threshold=threshold, margin=margin
        )
        metrics = _decision_metrics(selection_known, selection_strangers)
        hubness = _hubness_rows(str(cell["cell_id"]), selection_strangers)
        hubness_rows.extend(hubness)
        nearest_counts = [int(row["nearest_stranger_count"]) for row in hubness]
        slice_ids = [
            slice_id
            for values in (*cal_slices.values(), *sel_slices.values())
            for slice_id in values
        ]
        mean_extract = statistics_fmean(
            float(observations[slice_id]["extraction_sec"]) for slice_id in slice_ids
        )
        stored_templates = (
            int(cell["utterances"]) if aggregation.startswith("frozen_") else 1
        )
        score_time = selection_known_time + selection_stranger_time
        selection_probe_count = len(selection_known) + len(selection_strangers)
        row = {
            **cell,
            "status": "MEASURED",
            "attempted": True,
            "evidence_class": "INTEGRATED_DEVELOPMENT_MEASURED",
            "panel_sha256": panel["panel_sha256"],
            "backend_id": BACKEND_ID,
            "backend_identity_hash": _backend_runtime_identity()["identity_hash"],
            "score_definition": (
                "cosine_to_l2_normalized_centroid"
                if aggregation == "normalized_mean"
                else "maximum_probe_to_retained_template_cosine"
            ),
            **policy,
            **metrics,
            "gallery_size": len(selection_templates),
            "maximum_nearest_stranger_hub_fraction": max(nearest_counts)
            / len(selection_strangers)
            if nearest_counts and selection_strangers
            else 0.0,
            "mean_enrollment_slice_extraction_sec": mean_extract,
            "probe_scoring_runtime_sec": score_time,
            "probe_scoring_latency_ms_mean": 1000.0 * score_time / selection_probe_count
            if selection_probe_count
            else None,
            "stored_templates_per_speaker": stored_templates,
            "template_storage_float32_bytes_per_speaker": stored_templates * 192 * 4,
            "template_cosine_comparisons_per_probe": len(selection_templates)
            * (stored_templates if aggregation.startswith("frozen_") else 1),
            "qc_rejected_attempt_count": sum(
                row["attempt_action"] == "REJECTED_REPEAT_REQUIRED"
                for row in (*calibration_qc, *selection_qc)
                if int(row["sample_index"]) == 0
            ),
            "h2_selected_policy_behavior_status": (
                "SCORE_COMPATIBLE_ONLY_NOT_POLICY_TRANSFER_COMPATIBLE"
                if aggregation == "frozen_redim_multi_template"
                else "NOT_SCORE_COMPATIBLE"
            ),
            "h2_selected_policy_behavior_reason": (
                "the exact frozen ReDim multi_template_max score is used; the "
                "16-speaker study gallery/enrollment distribution is not the "
                "fixed full-gallery H2 policy population, so its threshold and "
                "margin cannot be transferred"
                if aggregation == "frozen_redim_multi_template"
                else "normalized-centroid scores are not interchangeable with "
                "the frozen ReDim multi_template_max score"
            ),
            "evaluation_material_inspected": False,
            "biometric_vector_exported": False,
        }
        row["outcome_sha256"] = canonical_sha256(row)
        matrix_rows.append(row)
    if len(matrix_rows) != 32:
        raise IntegratedEnrollmentError("integrated enrollment matrix is not 32 cells")
    measured = [row for row in matrix_rows if row["status"] == "MEASURED"]
    if not measured:
        raise IntegratedEnrollmentError("no integrated enrollment cell is measurable")
    selected = min(measured, key=_integrated_enrollment_selection_key)
    recommendation_unsigned = {
        "schema_version": "h2-integrated-selected-enrollment-policy.v1",
        "selection_label": "INTEGRATED_SELECTED_CELL",
        "cell_id": selected["cell_id"],
        "utterances": selected["utterances"],
        "total_duration_sec": selected["total_duration_sec"],
        "sessions": selected["sessions"],
        "aggregation": selected["aggregation"],
        "quality_filter": selected["quality_filter"],
        "score_definition": selected["score_definition"],
        "score_threshold": selected["score_threshold"],
        "margin_threshold": selected["margin_threshold"],
        "target_fpir": selected["target_fpir"],
        "panel_sha256": panel["panel_sha256"],
        "backend_id": BACKEND_ID,
        "backend_identity_hash": _backend_runtime_identity()["identity_hash"],
        "qc_policy": dict(QC_POLICY),
        "selection_rule": (
            "lexicographic:min_wrong_known,min_stranger_speaker_fpir,"
            "min_stranger_probe_fpir,max_known_correct,"
            "min_scoring_latency,min_template_storage,cell_id"
        ),
        "safety_priority_contract_id": SAFETY_PRIORITY_CONTRACT_ID,
        "ordered_safety_risk_families": list(SAFETY_PRIORITY_ORDERED_RISK_FAMILIES),
        "selection_uses_development_only": True,
        "evaluation_material_inspected": False,
        "live_identity_threshold_altered_by_handler": False,
    }
    recommendation = {
        **recommendation_unsigned,
        "policy_provenance_sha256": canonical_sha256(recommendation_unsigned),
    }
    return matrix_rows, qc_rows, hubness_rows, recommendation


def _integrated_enrollment_selection_key(
    row: Mapping[str, object],
) -> tuple[object, ...]:
    """Select enrollment cells with wrong-known risk as the first criterion."""

    return (
        float(row["wrong_known_rate"]),
        float(row["stranger_speaker_fpir"]),
        float(row["stranger_fpir"]),
        -float(row["known_correct_rate"]),
        float(row["probe_scoring_latency_ms_mean"]),
        int(row["template_storage_float32_bytes_per_speaker"]),
        str(row["cell_id"]),
    )


def statistics_fmean(values: Iterable[float]) -> float:
    sequence = list(values)
    return sum(sequence) / len(sequence) if sequence else 0.0


def _historical_axis(row: Mapping[str, object], axis: str) -> object:
    aliases = {
        "utterances": ("utterances", "enrollment_utterance_count", "enrollment_count"),
        "total_duration_sec": (
            "total_duration_sec",
            "enrollment_total_duration_sec",
            "enrollment_target_audio_sec",
        ),
        "sessions": ("sessions", "session_condition", "enrollment_sessions"),
        "aggregation": ("aggregation", "integrated_aggregation", "aggregation_method"),
        "quality_filter": ("quality_filter", "enrollment_quality_filter"),
    }
    for key in aliases[axis]:
        raw = row.get(key)
        if raw in {None, ""}:
            continue
        if axis == "utterances":
            return int(float(raw))
        if axis == "total_duration_sec":
            return float(raw)
        normalized = str(raw).strip().casefold()
        if axis == "sessions":
            return {
                "single_session": "single",
                "varied_sessions": "varied",
            }.get(normalized, normalized)
        if axis == "aggregation":
            return {
                "normalized_mean": "normalized_mean",
                "multi_template_max": "frozen_redim_multi_template",
                "multi_template_max_score": "frozen_redim_multi_template",
                "frozen_redim_multi_template": "frozen_redim_multi_template",
            }.get(normalized, normalized)
        return {
            "blind": "blind_accept",
            "none": "blind_accept",
            "blind_accept": "blind_accept",
            "quality_filtered": "quality_filtered",
            "quality_filtering": "quality_filtered",
        }.get(normalized, normalized)
    return None


def build_historical_accounting(
    evidence_rows: Sequence[Mapping[str, object]],
    *,
    source_bindings: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Inventory historical ReDim cells without inventing missing session/QC axes."""

    inventory: list[dict[str, object]] = []
    for row in evidence_rows:
        inventory.append(
            {
                "evidence_class": "HISTORICAL_STANDALONE_MEASURED",
                "backend": row.get("backend"),
                "configuration_id": row.get("configuration_id"),
                "configuration_identity_hash": row.get("configuration_identity_hash"),
                "configuration_outcome": row.get("configuration_outcome"),
                "phase": row.get("phase"),
                "utterances": _historical_axis(row, "utterances"),
                "total_duration_sec": _historical_axis(row, "total_duration_sec"),
                "sessions": _historical_axis(row, "sessions")
                or "UNAVAILABLE_NOT_RECORDED",
                "aggregation": _historical_axis(row, "aggregation"),
                "quality_filter": _historical_axis(row, "quality_filter")
                or "UNAVAILABLE_NOT_RECORDED",
                "fpir": row.get("fpir"),
                "dir_rank1": row.get("dir_rank1"),
                "wrong_known_rate": row.get("wrong_known_rate"),
                "unknown_rejection": row.get("unknown_rejection"),
                "source_sha256": row.get("source_sha256"),
                "standalone_not_integrated": True,
                "session_diversity_inferred": False,
            }
        )
    requested: list[dict[str, object]] = []
    for cell in _cell_axes():
        exact = [
            row
            for row in evidence_rows
            if all(_historical_axis(row, axis) == cell[axis] for axis in MATRIX_AXES)
        ]
        if len(exact) == 1 and str(
            exact[0].get("configuration_outcome") or ""
        ).upper() in {
            "SCORED",
            "COMPLETE",
        }:
            source = exact[0]
            row = {
                **cell,
                "status": "HISTORICAL_STANDALONE_MEASURED",
                "evidence_class": "HISTORICAL_STANDALONE_MEASURED",
                "configuration_id": source.get("configuration_id"),
                "configuration_identity_hash": source.get(
                    "configuration_identity_hash"
                ),
                "fpir": source.get("fpir"),
                "dir_rank1": source.get("dir_rank1"),
                "wrong_known_rate": source.get("wrong_known_rate"),
                "unknown_rejection": source.get("unknown_rejection"),
                "source_sha256": source.get("source_sha256"),
                "source_bindings_sha256": canonical_sha256(list(source_bindings)),
                "standalone_not_integrated": True,
                "session_diversity_inferred": False,
            }
        else:
            partial = sum(
                _historical_axis(source, "utterances") == cell["utterances"]
                and _historical_axis(source, "total_duration_sec")
                == cell["total_duration_sec"]
                and _historical_axis(source, "aggregation") == cell["aggregation"]
                for source in evidence_rows
            )
            missing_axes = sorted(
                axis
                for axis in MATRIX_AXES
                if not any(
                    _historical_axis(source, axis) == cell[axis]
                    for source in evidence_rows
                )
            )
            row = {
                **cell,
                "status": "HISTORICAL_STANDALONE_UNSUPPORTED",
                "evidence_class": "HISTORICAL_STANDALONE_UNSUPPORTED",
                "reason": (
                    "no single completed historical row binds all exact requested axes; "
                    "the completed Common Voice enrollment study did not record an "
                    "independent single/varied-session axis or this exact acceptance-QC axis"
                ),
                "missing_or_unbound_axes": "|".join(
                    missing_axes or ("sessions", "quality_filter")
                ),
                "partial_axis_match_count": partial,
                "source_bindings_sha256": canonical_sha256(list(source_bindings)),
                "standalone_not_integrated": True,
                "session_diversity_inferred": False,
                "historical_metrics_borrowed": False,
            }
        row["outcome_sha256"] = canonical_sha256(row)
        requested.append(row)
    if len(requested) != 32:
        raise IntegratedEnrollmentError("historical requested matrix is not 32 cells")
    return inventory, requested


def _public_payload_has_vectors(value: object, *, path: str = "root") -> list[str]:
    findings: list[str] = []
    if isinstance(value, np.ndarray):
        findings.append(path + ":ndarray")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if "vector" in normalized and normalized not in {
                "vector_sha256",
                "biometric_vector_exported",
                "public_vectors_exported",
            }:
                findings.append(f"{path}.{key}:vector_field")
            findings.extend(_public_payload_has_vectors(item, path=f"{path}.{key}"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            findings.extend(_public_payload_has_vectors(item, path=f"{path}[{index}]"))
    return findings


def execute_integrated_enrollment(
    paths: ProgramPaths,
    job: H2Job,
    *,
    historical_summary: Mapping[str, object],
    historical_evidence_rows: Sequence[Mapping[str, object]],
    historical_configuration_rows: Sequence[Mapping[str, object]],
    historical_source_bindings: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, Sequence[Mapping[str, object]]]]:
    """Run/reuse the bounded real ReDim development confirmation."""

    if job.split != "development" or not job.development_only:
        raise IntegratedEnrollmentError(
            "integrated enrollment must be development-only"
        )
    panel = build_panel_manifest()
    validate_panel_manifest(panel)
    cache_root = (
        paths.workspace
        / "private_biometric_cache"
        / "integrated_enrollment"
        / str(panel["panel_id"])
    ).resolve()
    cache = ensure_private_embeddings(panel, cache_root)
    observations = _cache_observations(panel, cache_root)
    integrated_rows, qc_rows, hubness_rows, selected = evaluate_integrated_matrix(
        panel, observations
    )
    historical_inventory, historical_matrix = build_historical_accounting(
        historical_configuration_rows,
        source_bindings=historical_source_bindings,
    )
    measured = sum(row["status"] == "MEASURED" for row in integrated_rows)
    invalid = sum(row["status"] == "TECHNICALLY_INVALID" for row in integrated_rows)
    public_cache_rows = list(cache["rows"])
    cache_public = {key: value for key, value in cache.items() if key != "rows"}
    panel_public = dict(panel)
    # The absolute dataset root is operational metadata outside panel_sha256.
    # Public evidence retains a portable marker plus exact logical paths/hashes.
    panel_public["dataset_root"] = "PRIVATE_OPERATIONAL_PATH_REDACTED_USE_JP_DATA_ROOT"
    selected_row = {
        **selected,
        "status": "INTEGRATED_SELECTED_CELL",
        "historical_comparison_status": "NO_IDENTICAL_HISTORICAL_CELL",
        "historical_comparison_reason": (
            "the historical study did not bind independent session diversity and "
            "the requested acceptance-QC axis in the same configuration row"
        ),
        "biometric_vector_exported": False,
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "COMPLETE",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "comparison_design": "sealed train-clean-100 session-aware 32-cell development confirmation",
        "panel_id": panel["panel_id"],
        "panel_sha256": panel["panel_sha256"],
        "panel_manifest_checksum_valid": True,
        "cache_manifest_sha256": cache["cache_manifest_sha256"],
        "cache_manifest_checksum_valid": True,
        "cache_item_count": cache["item_count"],
        "backend_identity": _backend_runtime_identity(),
        "historical_evidence": dict(historical_summary),
        "historical_requested_cell_count": len(historical_matrix),
        "historical_standalone_measured_requested_cells": sum(
            row["status"] == "HISTORICAL_STANDALONE_MEASURED"
            for row in historical_matrix
        ),
        "historical_standalone_unsupported_requested_cells": sum(
            row["status"] == "HISTORICAL_STANDALONE_UNSUPPORTED"
            for row in historical_matrix
        ),
        "declared_matrix_cell_count": len(integrated_rows),
        "measured_matrix_cell_count": measured,
        "technically_invalid_matrix_cell_count": invalid,
        "all_declared_cells_attempted": len(integrated_rows) == 32
        and all(bool(row.get("attempted")) for row in integrated_rows),
        "integrated_enrollment_confirmation_measured": measured > 0,
        "enrollment_frontier_measured": measured > 0,
        "selected_enrollment_policy": selected,
        "selected_enrollment_policy_provenance_sha256": selected[
            "policy_provenance_sha256"
        ],
        "selected_runtime_tuning": {},
        "selected_runtime_axes": [],
        "live_identity_threshold_altered_by_handler": False,
        "h2_selected_policy_compatible_cell_count": sum(
            row["status"] == "MEASURED"
            and row["aggregation"] == "frozen_redim_multi_template"
            for row in integrated_rows
        ),
        "h2_selected_policy_behavior_status": (
            "EXACT_SCORE_METHOD_PRESENT_POLICY_TRANSFER_NOT_PROVEN"
        ),
        "full_gallery_policy_compatibility_proven": False,
        "integrated_recommendation_runtime_activation_eligible": False,
        "integrated_selected_cell_is_development_advisory": True,
        "historical_recommendation_comparison": "NO_IDENTICAL_HISTORICAL_CELL",
        "qc_policy": dict(QC_POLICY),
        "calibration_selection_speaker_disjoint": True,
        "known_stranger_speaker_disjoint": True,
        "enrollment_probe_session_disjoint": True,
        "evaluation_material_inspected": False,
        "development_only_selection": True,
        "promotion_eligible": True,
        "neural_inference_performed_by_handler": True,
        "implicit_model_downloads_allowed": False,
        "generated_audio_persisted": False,
        "private_embedding_cache_present": True,
        "public_embedding_payload_present": False,
        "public_zip_must_exclude_private_cache": True,
        "integrated_enrollment_code_sha256": sha256_file(Path(__file__)),
    }
    tables: dict[str, Sequence[Mapping[str, object]]] = {
        "integrated_enrollment_panel.jsonl": (panel_public,),
        "integrated_enrollment_cache_manifest.csv": public_cache_rows,
        "historical_enrollment_cell_inventory.csv": historical_inventory,
        "historical_enrollment_matrix.csv": historical_matrix,
        "historical_enrollment_evidence.csv": tuple(
            dict(row) for row in historical_evidence_rows
        ),
        "integrated_enrollment_matrix.csv": integrated_rows,
        "integrated_enrollment_qc_events.csv": qc_rows,
        "integrated_enrollment_hubness.csv": hubness_rows,
        "integrated_enrollment_selected_cell.csv": (selected_row,),
        "integrated_enrollment_cache_summary.jsonl": (cache_public,),
    }
    findings = _public_payload_has_vectors({"payload": payload, "tables": tables})
    if findings:
        raise IntegratedEnrollmentError(
            "public integrated enrollment payload contains biometric vector fields: "
            + "; ".join(findings[:5])
        )
    return payload, tables


def _main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    worker = subparsers.add_parser(
        "worker", help="run isolated missing-slice extraction"
    )
    worker.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "worker":
        return _worker(args.request)
    raise IntegratedEnrollmentError(f"unsupported action: {args.action}")


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    raise SystemExit(_main())


__all__ = [
    "BACKEND_ID",
    "MATRIX_AXES",
    "QC_POLICY",
    "build_historical_accounting",
    "build_panel_manifest",
    "calibrate_policy",
    "evaluate_integrated_matrix",
    "exact_binomial_upper_95",
    "execute_integrated_enrollment",
    "extract_slices_with_embedder",
    "normalized_mean",
    "score_enrollment",
    "template_quality_metrics",
    "validate_panel_manifest",
    "validate_private_cache",
]
