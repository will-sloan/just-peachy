"""Focused unit tests for the Phase-2 registry's portable safety rules."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


TRAINING_TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_TOOL))

from training_data.registry import (  # noqa: E402
    _apply_policy_and_firewall,
    _cross_key,
    _frame_hash,
    _json_hash,
    evaluation_inputs,
    select_records,
    verify_freeze_details,
)


def _terms(status: str = "allowed_with_attribution") -> dict:
    return {
        "datasets": {
            "librispeech": {
                "dataset_version": "test", "license_id": "CC-BY-4.0",
                "commercial_training_status": status, "technical_training_status": "eligible",
                "commercial_release_review_status": "normal", "attribution_required": True,
                "sharealike_flag": False,
            }
        }
    }


def _source_row() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dataset_id": ["librispeech"],
            "source_utterance_id": ["154-124002-0012"],
            "source_recording_id": ["LIBRISPEECH_154_124002_154-124002-0012"],
            "source_audio_logical_path": ["Raw Datasets (Not formatted)/LibreSpeech/a.flac"],
            "speaker_group_id": ["librispeech:speaker:154"],
            "cross_source_key": ["librispeech-source:154:124002:12"],
        }
    )


def test_cross_source_keys_link_voices_to_librispeech() -> None:
    libri = pd.DataFrame({"utterance_id": ["0154-124002-0012"]})
    voices = pd.DataFrame({"speaker_id_padded": ["0154"], "chapter_id": ["124002"], "segment_id": ["0012"]})
    assert _cross_key("librispeech", libri).iloc[0] == "librispeech-source:154:124002:12"
    assert _cross_key("voices", voices).iloc[0] == "librispeech-source:154:124002:12"


def test_firewall_excludes_cross_dataset_source_and_strict_group() -> None:
    source = _source_row()
    exclusion = pd.DataFrame(
        {
            "dataset": ["voices"],
            "source_utterance_id": ["0154:124002:12"],
            "source_recording_id": ["VOICE"],
            "strict_group_id": ["voices:source_speaker:154"],
            "cross_source_key": ["librispeech-source:154:124002:12"],
        }
    )
    output = _apply_policy_and_firewall(source, _terms(), exclusion)
    assert bool(output.loc[0, "evaluation_cross_dataset_match"])
    assert not bool(output.loc[0, "relaxed_training_eligible"])
    assert not bool(output.loc[0, "strict_training_eligible"])


def test_registry_hash_ignores_absolute_resolved_path() -> None:
    left = _source_row().assign(resolved_audio_path="C:/one/a.flac")
    right = _source_row().assign(resolved_audio_path="D:/two/a.flac")
    assert _frame_hash(left, omit=("resolved_audio_path",)) == _frame_hash(right, omit=("resolved_audio_path",))


def test_review_gated_selection_is_not_straightforward_commercial() -> None:
    frame = pd.DataFrame(
        {
            "dataset_id": ["chime6", "librispeech"],
            "source_item_id": ["chime", "libri"],
            "strict_training_eligible": [True, True],
            "relaxed_training_eligible": [True, True],
            "commercial_training_eligible": [False, True],
            "review_gated_training_eligible": [True, False],
        }
    )
    assert select_records(frame, commercial_policy="straightforward")["source_item_id"].tolist() == ["libri"]
    assert select_records(frame, commercial_policy="review_gated")["source_item_id"].tolist() == ["chime"]


def test_verify_freeze_rejects_changed_evaluation_manifest(tmp_path: Path) -> None:
    tool_root = tmp_path / "Evaluation Tool"
    manifest = tool_root / "benchmarks" / "v1" / "small_source_manifest.parquet"
    manifest.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "dataset": ["cmu_arctic"], "source_recording_id": ["r1"],
            "source_utterance_id": ["u1"], "speaker_id": ["s1"],
        }
    ).to_parquet(manifest, index=False)
    _, manifests = evaluation_inputs(tool_root)
    registries = tmp_path / "registries"
    registries.mkdir()
    registry = pd.DataFrame({"source_item_id": ["one"], "resolved_audio_path": ["C:/one.wav"]})
    exclusion = pd.DataFrame({"dataset": ["cmu_arctic"], "source_recording_id": ["r1"]})
    registry.to_parquet(registries / "training_data_registry.parquet", index=False)
    exclusion.to_parquet(registries / "evaluation_exclusion_index.parquet", index=False)
    payload = {
        "schema_version": "training-data-freeze.v1", "evaluation_manifests": manifests,
        "registry": {"sha256": _frame_hash(registry, omit=("resolved_audio_path",))},
        "evaluation_exclusion_index": {"sha256": _frame_hash(exclusion)},
    }
    payload["training_data_freeze_sha256"] = _json_hash(payload)
    payload["training_data_freeze_id"] = "training_freeze_test"
    freeze = registries / "freeze.json"
    freeze.write_text(json.dumps(payload), encoding="utf-8")
    assert verify_freeze_details(freeze, tool_root)["valid"]
    pd.DataFrame(
        {
            "dataset": ["cmu_arctic", "cmu_arctic"], "source_recording_id": ["r1", "r2"],
            "source_utterance_id": ["u1", "u2"], "speaker_id": ["s1", "s2"],
        }
    ).to_parquet(manifest, index=False)
    assert not verify_freeze_details(freeze, tool_root)["valid"]
