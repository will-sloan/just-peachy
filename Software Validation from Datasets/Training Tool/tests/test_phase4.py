"""Bounded tests for deterministic Phase-4 manifests and sampling policies."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest


TRAINING_TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_TOOL))

from training_data.phase4 import (  # noqa: E402
    EXPECTED_PHASE3_ID,
    EXPECTED_PHASE3_SHA256,
    Phase4Paths,
    _bundle_license,
    _bundle_specs,
    _has_absolute_path,
    _identity_document,
    _policy_payloads,
    ami_dev_meetings,
    chime_dev_sessions,
    clean_monitor_rows,
    cmu_dev_speakers,
    common_voice_manifest,
    dataset_weights,
    deterministic_view_index,
    phase2_manifest,
    phase4_declarations,
    speaker_probabilities,
    stable_rank,
    voices_dev_speakers,
    write_model_plan,
)
from training_data.registry import _frame_hash  # noqa: E402


def _phase2_rows(
    dataset: str, groups: list[tuple[str, str, float]], *, views: int = 1
) -> pd.DataFrame:
    rows = []
    for index, (group, speaker, duration) in enumerate(groups):
        for view in range(views):
            source = f"source-{index}"
            rows.append(
                {
                    "dataset_id": dataset,
                    "dataset_version": "fixture",
                    "upstream_split": "train",
                    "source_item_id": f"item-{index}-{view}",
                    "source_recording_id": f"recording-{index}-{view}",
                    "source_utterance_id": source,
                    "source_audio_logical_path": f"Raw Datasets (Not formatted)/fixture/{index}-{view}.wav",
                    "transcript": f"text {index}",
                    "transcript_sha256": f"HASH-{index}",
                    "speaker_id": speaker,
                    "speaker_group_id": f"{dataset}:speaker:{speaker}",
                    "session_id": group if dataset == "chime6" else None,
                    "meeting_id": group if dataset == "ami" else None,
                    "duration_seconds": duration,
                    "age_metadata": None,
                    "accent": "US English",
                    "license_id": "CC-BY-4.0",
                    "commercial_training_status": "allowed_with_attribution",
                    "commercial_release_review_status": "normal",
                    "attribution_required": True,
                    "sharealike_flag": False,
                    "evaluation_exact_match": False,
                    "evaluation_group_match": False,
                    "evaluation_cross_dataset_match": False,
                    "strict_training_eligible": True,
                    "cross_source_key": f"key-{index}",
                }
            )
    return pd.DataFrame(rows)


def _parent() -> dict[str, str]:
    return {
        "training_data_freeze_id": EXPECTED_PHASE3_ID,
        "training_data_freeze_sha256": EXPECTED_PHASE3_SHA256,
    }


def test_stable_rank_is_cross_call_deterministic() -> None:
    assert stable_rank("a", 1) == stable_rank("a", 1)
    assert stable_rank("a", 1) != stable_rank("a", 2)


def test_rotating_view_selection_is_bounded_and_deterministic() -> None:
    first = deterministic_view_index(
        bundle_id="bundle",
        epoch_index=3,
        source_group_id="source",
        available_view_count=9,
    )
    second = deterministic_view_index(
        bundle_id="bundle",
        epoch_index=3,
        source_group_id="source",
        available_view_count=9,
    )
    assert first == second
    assert 0 <= first < 9
    assert (
        len(
            {
                deterministic_view_index(
                    bundle_id="bundle",
                    epoch_index=epoch,
                    source_group_id="source",
                    available_view_count=9,
                )
                for epoch in range(50)
            }
        )
        > 1
    )


def test_rotating_view_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError):
        deterministic_view_index(
            bundle_id="b", epoch_index=-1, source_group_id="s", available_view_count=1
        )


def test_sqrt_dataset_weighting_applies_voices_floor() -> None:
    weights = dataset_weights({"ami": 90.0, "chime6": 30.0, "voices": 1.0})
    assert Decimal(weights["voices"]["final_probability"]) == Decimal("0.10")
    assert sum(
        Decimal(value["final_probability"]) for value in weights.values()
    ) == Decimal(1)


def test_sqrt_dataset_weighting_caps_cmu() -> None:
    weights = dataset_weights(
        {"common_voice": 1.0, "voices": 1.0, "cmu_arctic": 1000.0}
    )
    assert Decimal(weights["cmu_arctic"]["final_probability"]) == Decimal("0.10")
    assert Decimal(weights["voices"]["final_probability"]) == Decimal("0.10")
    assert sum(
        Decimal(value["final_probability"]) for value in weights.values()
    ) == Decimal(1)


def test_single_source_cmu_bundle_has_probability_one() -> None:
    weights = dataset_weights({"cmu_arctic": 5.0})
    assert Decimal(weights["cmu_arctic"]["final_probability"]) == Decimal(1)


def test_speaker_probabilities_use_sqrt_duration() -> None:
    frame = pd.DataFrame({"speaker_id": ["a", "b"], "duration_seconds": [1.0, 9.0]})
    probabilities = speaker_probabilities(frame)
    assert probabilities["a"] == pytest.approx(0.25)
    assert probabilities["b"] == pytest.approx(0.75)


def test_ami_split_is_deterministic_meeting_disjoint_and_stratified() -> None:
    groups = []
    for prefix in ("EN", "ES", "IB", "IN", "IS", "TS"):
        for index in range(10):
            groups.append(
                (f"{prefix}{index:04d}", f"{prefix}-speaker-{index}", 10 + index)
            )
    frame = _phase2_rows("ami", groups, views=3)
    first = ami_dev_meetings(frame)
    assert first == ami_dev_meetings(frame)
    assert len(first) == 6
    assert {value[:2] for value in first} == {"EN", "ES", "IB", "IN", "IS", "TS"}
    assert set(frame.loc[frame.meeting_id.isin(first), "meeting_id"]).isdisjoint(
        set(frame.loc[~frame.meeting_id.isin(first), "meeting_id"])
    )


def test_chime_prefers_two_official_eval_sessions() -> None:
    groups = [
        (f"S{index:02d}", f"P{index:02d}", 10.0 + index) for index in range(1, 13)
    ]
    frame = _phase2_rows("chime6", groups)
    frame.loc[frame.session_id.isin(["S01", "S12"]), "upstream_split"] = "eval"
    assert chime_dev_sessions(frame) == {"S01", "S12"}


def test_voices_split_is_speaker_disjoint_and_deterministic() -> None:
    groups = [("unused", f"speaker-{index}", 10.0 + index / 10) for index in range(40)]
    frame = _phase2_rows("voices", groups)
    selected = voices_dev_speakers(frame)
    assert selected == voices_dev_speakers(frame)
    assert len(selected) == 4
    assert set(frame.loc[frame.speaker_id.isin(selected), "speaker_id"]).isdisjoint(
        set(frame.loc[~frame.speaker_id.isin(selected), "speaker_id"])
    )


def test_cmu_split_uses_four_speakers_without_overlap() -> None:
    groups = [("unused", f"speaker-{index}", 10.0 + index) for index in range(18)]
    frame = _phase2_rows("cmu_arctic", groups)
    accents = ["US", "Indian", "German", "Scottish", "Canadian", "Israeli"]
    frame["accent"] = [accents[index % len(accents)] for index in range(len(frame))]
    selected = cmu_dev_speakers(frame)
    assert len(selected) == 4
    assert selected == cmu_dev_speakers(frame)


def test_clean_monitor_is_broad_and_excludes_voices_sources() -> None:
    rows = _phase2_rows(
        "librispeech", [("unused", f"speaker-{index}", 18.0) for index in range(1_200)]
    )
    rows.loc[0, "cross_source_key"] = "forbidden"
    selected = clean_monitor_rows(rows, forbidden_cross_keys={"forbidden"})
    assert selected.duration_seconds.sum() / 3600 == pytest.approx(5.0, abs=0.01)
    assert selected.speaker_id.nunique() == len(selected)
    assert "forbidden" not in set(selected.cross_source_key)


def test_phase2_manifest_groups_ami_views_without_multiplying_sources() -> None:
    raw = _phase2_rows(
        "ami", [("EN0001", "speaker", 4.0), ("EN0001", "speaker", 6.0)], views=3
    )
    manifest = phase2_manifest(
        raw, dataset="ami", role="train", strictness="strict", parent=_parent()
    )
    assert manifest.source_group_id.nunique() == 2
    assert set(manifest.acoustic_view_count) == {3}
    assert manifest.sampling_group_id.nunique() == 1
    assert manifest.sampling_group_probability.iloc[0] == pytest.approx(1.0)


def test_chime_manifest_does_not_fabricate_views() -> None:
    raw = _phase2_rows("chime6", [("S01", "P01", 4.0), ("S01", "P02", 6.0)])
    manifest = phase2_manifest(
        raw, dataset="chime6", role="train", strictness="strict", parent=_parent()
    )
    assert set(manifest.acoustic_view_count) == {1}


def test_voices_manifest_groups_retransmissions() -> None:
    raw = _phase2_rows(
        "voices", [("unused", "speaker", 4.0), ("unused", "speaker", 6.0)], views=4
    )
    manifest = phase2_manifest(
        raw, dataset="voices", role="train", strictness="strict", parent=_parent()
    )
    assert manifest.source_group_id.nunique() == 2
    assert set(manifest.acoustic_view_count) == {4}


def test_monitor_manifest_is_never_gradient_eligible() -> None:
    raw = _phase2_rows("librispeech", [("unused", "speaker", 4.0)])
    manifest = phase2_manifest(
        raw,
        dataset="librispeech",
        role="monitor",
        strictness="monitor",
        parent=_parent(),
        training_eligible=False,
    )
    assert not manifest.training_eligible_for_experiment.any()
    assert manifest.sampling_group_probability.isna().all()


def test_common_voice_manifest_preserves_raw_text_and_portable_path() -> None:
    frame = pd.DataFrame(
        {
            "dataset_version": ["fixture"],
            "source_item_id": ["cv-item"],
            "prepared_audio_relative_path": ["clips/a.mp3"],
            "audio_sha256": ["A" * 64],
            "duration_seconds": [1.0],
            "raw_transcript": ["Raw Text"],
            "transcript_sha256": ["B" * 64],
            "speaker_id": ["speaker"],
            "speaker_group_id": ["cv:speaker:speaker"],
            "source_utterance_id": ["utterance"],
            "source_recording_id": ["recording"],
            "source_age_label": ["sixties"],
            "normalized_age_bin": ["60s"],
            "accents": ["Canadian English"],
            "license_id": ["CC0-1.0"],
            "commercial_training_status": ["allowed"],
            "commercial_release_review_status": ["normal"],
            "attribution_required": [False],
            "sharealike_flag": [False],
            "evaluation_exact_match": [False],
            "evaluation_group_match": [False],
            "evaluation_cross_dataset_match": [False],
            "evaluation_content_hash_match": [False],
        }
    )
    manifest = common_voice_manifest(frame, role="train", parent=_parent())
    assert manifest.raw_transcript.iloc[0] == "Raw Text"
    assert manifest.audio_root_id.iloc[0] == "JP_TRAINING_ROOT"
    assert not _has_absolute_path(manifest.audio_relative_path.iloc[0])


def test_manifest_hash_is_portable_and_deterministic() -> None:
    raw = _phase2_rows("ami", [("EN0001", "speaker", 4.0)])
    left = phase2_manifest(
        raw, dataset="ami", role="train", strictness="strict", parent=_parent()
    )
    right = phase2_manifest(
        raw, dataset="ami", role="train", strictness="strict", parent=_parent()
    )
    assert _frame_hash(left) == _frame_hash(right)
    assert not _has_absolute_path(left.to_dict("records"))


def test_identity_documents_are_deterministic_and_reject_absolute_paths() -> None:
    first = _identity_document(
        {"schema_version": "fixture.v1", "path": "JP_TRAINING_ROOT:a/b"},
        prefix="fixture",
        kind="policy",
    )
    second = _identity_document(
        {"schema_version": "fixture.v1", "path": "JP_TRAINING_ROOT:a/b"},
        prefix="fixture",
        kind="policy",
    )
    assert first == second
    with pytest.raises(Exception, match="Absolute path"):
        _identity_document({"path": "C:/machine/path"}, prefix="fixture", kind="policy")


def test_required_policy_set_and_cmu_labels_are_frozen() -> None:
    policies = _policy_payloads(monitor_manifest_id="monitor")
    assert set(policies) == {
        "source_grouping",
        "acoustic_view",
        "speaker_balancing",
        "dataset_weighting",
        "development_selection",
        "checkpoint_selection",
        "cmu_exploratory",
        "large_benchmark_use",
        "license",
    }
    assert policies["cmu_exploratory"]["strict_training_available"] is False
    assert (
        policies["cmu_exploratory"]["confirmatory_generalization_claim_allowed"]
        is False
    )


def test_phase4_boundary_declares_no_training_or_export() -> None:
    declarations = phase4_declarations()
    assert declarations["icefall_installed"] is False
    assert declarations["model_training_started"] is False
    assert declarations["full_finetuning_started"] is False
    assert declarations["onnx_model_exported"] is False
    assert declarations["asr_campaign_created"] is False
    assert declarations["general_rehearsal_enabled"] is False


def test_license_propagation_retains_chime_review_gate() -> None:
    robust = _bundle_license(["ami", "chime6", "voices"])
    age = _bundle_license(["common_voice"])
    assert robust["commercial_model_release_review_required"] is True
    assert robust["sharealike_flag"] is True
    assert age["commercial_model_release_review_required"] is False


def test_bundle_matrix_has_exact_required_eight_bundles() -> None:
    assert set(_bundle_specs()) == {
        "AGE",
        "CMU_EXPLORATORY",
        "AMI",
        "CHIME",
        "VOICES",
        "ROBUST",
        "AGE_ROBUST",
        "AGE_ROBUST_CMU_EXPLORATORY",
    }


def test_model_plan_has_exact_12_and_matched_original_giga_bundles(
    tmp_path: Path,
) -> None:
    paths = Phase4Paths(tmp_path, tmp_path, tmp_path, tmp_path, tmp_path)
    paths.registries.mkdir(parents=True)
    bundles = {}
    for name, spec in _bundle_specs().items():
        bundles[name] = {
            "bundle_id": f"bundle-{name}",
            "license": _bundle_license(spec["datasets"]),
        }
    references = {
        "original": {"reference_id": "original"},
        "giga": {"reference_id": "giga"},
    }
    plan = write_model_plan(paths, bundles=bundles, references=references)
    assert plan["total_new_adapter_plans"] == 12
    assert plan["strict_new_adapter_plans"] == 9
    assert plan["exploratory_new_adapter_plans"] == 3
    by_id = {item["experiment_id"]: item for item in plan["experiments"]}
    assert by_id["O-AGE"]["training_bundle_id"] == by_id["G-AGE"]["training_bundle_id"]
    assert (
        by_id["O-ROBUST"]["training_bundle_id"]
        == by_id["G-ROBUST"]["training_bundle_id"]
    )
    assert by_id["O-AGE-ROBUST-CMU"]["training_class"] == "exploratory"
    persisted = json.loads(
        (paths.registries / "model_experiment_plan.json").read_text(encoding="utf-8")
    )
    assert persisted["plan_id"] == plan["plan_id"]
