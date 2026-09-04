"""Predeclared metadata-only selection for the reduced Prompt-5 core panel."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline_evaluation.io import sha256_file

from . import (
    EXPECTED_CASE_COUNT,
    EXPECTED_SELECTED_CASE_SHA256,
    EXPECTED_SOURCE_CASE_COUNTS,
    SELECTION_SEED,
    SELECTION_TAG,
)
from .io import CoreEvaluationError, hash_lines, scope_fields


def case_id(row: Mapping[str, object]) -> str:
    value = row.get("protocol_case_id") or row.get("case_id")
    if not str(value or "").strip():
        raise CoreEvaluationError("case manifest row lacks protocol_case_id")
    return str(value)


def rank_digest(row: Mapping[str, object], *, seed: int = SELECTION_SEED) -> str:
    payload = f"{SELECTION_TAG}|{seed}|{case_id(row)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def select_reduced_panel(
    rows: Sequence[Mapping[str, object]], *, seed: int = SELECTION_SEED
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Select the immutable 2,240-case panel without using predictions."""

    selected_ids: set[str] = set()
    cv_groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    standard_groups: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(
        list
    )
    for raw in rows:
        row = dict(raw)
        source = str(row.get("source_key") or "")
        if str(row.get("partition") or row.get("split") or "") != "evaluation":
            raise CoreEvaluationError("Prompt-5 selector received a non-evaluation row")
        if source == "controlled_v1":
            selected_ids.add(case_id(row))
        elif source == "product_v2":
            if (
                row.get("gallery_primary") is True
                or str(row.get("gallery_requested_size")) == "full"
            ):
                selected_ids.add(case_id(row))
        elif source == "commonvoice_60plus_asr":
            speaker = str(row.get("reference_speaker_id") or "")
            if not speaker:
                raise CoreEvaluationError("Common Voice row lacks reference_speaker_id")
            cv_groups[speaker].append(row)
        elif source == "standard_asr":
            dataset = str(row.get("source_dataset") or "")
            speaker = str(row.get("reference_speaker_id") or "")
            if not dataset or not speaker:
                raise CoreEvaluationError(
                    "standard ASR row lacks dataset/speaker identity"
                )
            standard_groups[(dataset, speaker)].append(row)
        elif source != "native_standard":
            raise CoreEvaluationError(f"unknown Prompt-5 source_key: {source}")
    if len(cv_groups) != 365:
        raise CoreEvaluationError(
            f"expected 365 Common Voice speakers, got {len(cv_groups)}"
        )
    if len(standard_groups) != 114:
        raise CoreEvaluationError(
            f"expected 114 standard-ASR speaker groups, got {len(standard_groups)}"
        )
    for group in cv_groups.values():
        for row in sorted(
            group, key=lambda item: (rank_digest(item, seed=seed), case_id(item))
        )[:2]:
            selected_ids.add(case_id(row))
    for group in standard_groups.values():
        for row in sorted(
            group, key=lambda item: (rank_digest(item, seed=seed), case_id(item))
        )[:3]:
            selected_ids.add(case_id(row))
    selected = sorted(
        (dict(row) for row in rows if case_id(row) in selected_ids), key=case_id
    )
    excluded = sorted(
        (dict(row) for row in rows if case_id(row) not in selected_ids), key=case_id
    )
    validate_selected_panel(selected, excluded=excluded)
    return selected, excluded


def source_bucket(row: Mapping[str, object]) -> str:
    source = str(row.get("source_key") or "")
    if source != "standard_asr":
        return source
    dataset = str(row.get("source_dataset") or "").casefold()
    if "arctic" in dataset:
        return "cmu_arctic"
    if "hifi" in dataset:
        return "hifitts"
    if "libri" in dataset:
        return "librispeech"
    if "voice" in dataset:
        return "voices"
    raise CoreEvaluationError(f"unknown standard-ASR dataset: {dataset}")


def selected_case_sha256(rows: Sequence[Mapping[str, object]]) -> str:
    return hash_lines(sorted(case_id(row) for row in rows))


def validate_selected_panel(
    selected: Sequence[Mapping[str, object]],
    *,
    excluded: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    ids = [case_id(row) for row in selected]
    if len(ids) != len(set(ids)):
        raise CoreEvaluationError("selected panel contains duplicate case IDs")
    digest = selected_case_sha256(selected)
    if len(selected) != EXPECTED_CASE_COUNT or digest != EXPECTED_SELECTED_CASE_SHA256:
        raise CoreEvaluationError(
            f"reduced panel identity differs: count={len(selected)} sha256={digest}"
        )
    counts = Counter(source_bucket(row) for row in selected)
    if dict(sorted(counts.items())) != dict(
        sorted(EXPECTED_SOURCE_CASE_COUNTS.items())
    ):
        raise CoreEvaluationError(f"reduced panel source counts differ: {dict(counts)}")
    if any(str(row.get("source_key")) == "native_standard" for row in selected):
        raise CoreEvaluationError("native AMI/CHiME cases must be deferred to Prompt 6")
    if excluded is not None:
        overlap = set(ids) & {case_id(row) for row in excluded}
        if overlap:
            raise CoreEvaluationError("selected and excluded inventories overlap")
    return {
        "status": "PASS",
        "case_count": len(selected),
        "selected_case_sha256": digest,
        "source_case_counts": dict(sorted(counts.items())),
    }


def selection_manifest(
    selected: Sequence[Mapping[str, object]],
    excluded: Sequence[Mapping[str, object]],
    *,
    input_manifest_path: Path,
    reference_hashes: Mapping[str, str],
) -> dict[str, object]:
    selected_audio = {str(row.get("audio_logical_path") or "") for row in selected}
    unique_duration: dict[str, float] = {}
    speakers: set[str] = set()
    scenarios: Counter[str] = Counter()
    for row in selected:
        audio = str(row.get("audio_logical_path") or "")
        unique_duration.setdefault(audio, float(row.get("duration_sec") or 0.0))
        speakers.update(
            str(value) for value in row.get("global_speaker_ids", []) if value
        )
        speaker = str(row.get("reference_speaker_id") or "")
        if speaker:
            speakers.add(speaker)
        scenarios[
            str(row.get("scenario_id") or row.get("scoring_stratum") or "unknown")
        ] += 1
    return {
        "schema_version": "full-pipeline-core-reduced-selection.v1",
        **scope_fields(),
        "status": "FROZEN_BEFORE_PREDICTIONS",
        "selection_tag": SELECTION_TAG,
        "selection_seed": SELECTION_SEED,
        "selection_inputs": ["metadata", "references"],
        "predictions_or_metrics_inspected": False,
        "inclusion_and_stratification_rules": {
            "controlled_v1": "all 360 cases",
            "product_v2": "all gallery_primary plus every source full-gallery case",
            "commonvoice_60plus_asr": (
                "two cases per exact reference_speaker_id, ranked by "
                "sha256(prompt5_reduced_core_v1|5107|protocol_case_id)"
            ),
            "standard_asr": (
                "three cases per (source_dataset, reference_speaker_id), same hash rank"
            ),
            "native_standard": "excluded and deferred to Prompt 6",
        },
        "input_case_manifest": str(input_manifest_path.resolve()),
        "input_case_manifest_sha256": sha256_file(input_manifest_path),
        "reference_sha256s": dict(sorted(reference_hashes.items())),
        "selected_case_count": len(selected),
        "excluded_case_count": len(excluded),
        "selected_case_sha256": selected_case_sha256(selected),
        "source_case_counts": dict(
            sorted(Counter(source_bucket(row) for row in selected).items())
        ),
        "selected_audio_path_count": len(selected_audio),
        "selected_logical_audio_duration_sec": sum(
            float(row.get("duration_sec") or 0.0) for row in selected
        ),
        "selected_unique_audio_duration_sec": sum(unique_duration.values()),
        "achieved_speaker_coverage": {
            "distinct_reference_or_global_speakers": len(speakers),
        },
        "achieved_scenario_coverage": dict(sorted(scenarios.items())),
        "original_requested_case_count": len(selected) + len(excluded),
        "original_full_scope_complete": False,
    }
