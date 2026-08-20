from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from app.speaker_protocol.contracts import (
    BackendIdentity,
    EmbeddingObservation,
    SpeakerProtocolError,
    UNKNOWN_LABEL,
    eligible_embedding_backends,
    validate_enrollment_compatibility,
)
from app.speaker_protocol.evaluation import (
    evaluate_protocol_rows,
    validate_protocol_results,
)
from app.speaker_protocol.manifests import (
    MANIFEST_FILENAMES,
    build_protocol_manifests,
    leakage_report,
    read_protocol_rows,
    validate_protocol_manifest_set,
)
from app.speaker_protocol.metrics import (
    equal_error_rate,
    operating_point,
    threshold_sweep,
)
from app.speaker_protocol.smoke import DEFAULT_MANIFEST_ROOT, DEFAULT_OUTPUT_ROOT


TOOL_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def small_rows() -> dict[str, list[dict[str, object]]]:
    return {
        kind: read_protocol_rows(
            DEFAULT_MANIFEST_ROOT / MANIFEST_FILENAMES[kind], expected_kind=kind
        )
        for kind in ("enrollment", "calibration", "known_evaluation", "unknown_evaluation")
    }


@pytest.fixture(scope="module")
def smoke_rows(small_rows) -> dict[str, list[dict[str, object]]]:
    enrollment = small_rows["enrollment"]
    calibration = small_rows["calibration"]
    known_eval = small_rows["known_evaluation"]
    unknown_eval = small_rows["unknown_evaluation"]
    speakers = sorted({str(row["speaker_key"]) for row in enrollment})[:2]

    def first(rows, role, speaker=None):
        values = [
            row
            for row in rows
            if row["trial_role"] == role
            and row["protocol_condition"] == "clean"
            and (speaker is None or row["speaker_key"] == speaker)
        ]
        return sorted(values, key=lambda row: str(row["item_id"]))[0]

    return {
        "enrollment": [first(enrollment, "enrollment", speaker) for speaker in speakers],
        "calibration": [
            *(first(calibration, "known_probe", speaker) for speaker in speakers),
            first(calibration, "unknown_probe"),
        ],
        "known_evaluation": [
            first(known_eval, "known_probe", speaker) for speaker in speakers
        ],
        "unknown_evaluation": [first(unknown_eval, "unknown_probe")],
    }


@pytest.fixture(scope="module")
def synthetic_identity() -> BackendIdentity:
    return BackendIdentity(
        backend_id="synthetic_embedding",
        environment_profile="test",
        model_id="synthetic-v1",
        model_hash="A" * 64,
        config_path="tests/synthetic.yaml",
        config_hash="B" * 64,
        embedding_dimension=4,
        normalization="l2",
        preprocessing={"channel_count": 1, "sample_rate_hz": 16000, "dtype": "float32"},
        aggregation_method="normalized_mean",
        threshold_policy_version="speaker-threshold-policy.v1",
        qualification_status="test_only",
    )


def _observations(rows, identity, *, omit: str | None = None):
    enrolled = sorted(
        {str(row["speaker_key"]) for row in rows["enrollment"]}
    )
    speaker_vectors = {
        enrolled[0]: (1.0, 0.0, 0.0, 0.0),
        enrolled[1]: (0.0, 1.0, 0.0, 0.0),
    }
    result = []
    for values in rows.values():
        for row in values:
            item_id = str(row["item_id"])
            if item_id == omit:
                continue
            vector = speaker_vectors.get(str(row["speaker_key"]), (0.0, 0.0, 1.0, 0.0))
            result.append(
                EmbeddingObservation(
                    item_id=item_id,
                    backend_id=identity.backend_id,
                    model_hash=identity.model_hash,
                    config_hash=identity.config_hash,
                    vector=vector,
                    status="ok",
                    duration_sec=float(row["duration_sec"]),
                    extraction_sec=0.01,
                )
            )
    return result


@pytest.fixture(scope="module")
def synthetic_result(tmp_path_factory, smoke_rows, synthetic_identity):
    root = tmp_path_factory.mktemp("stage10-result")
    metrics = evaluate_protocol_rows(
        smoke_rows,
        _observations(smoke_rows, synthetic_identity),
        synthetic_identity,
        root,
        scope="synthetic-contract-test",
    )
    return root, metrics


def test_all_and_only_qualified_embedding_backends_are_in_scope():
    assert set(eligible_embedding_backends()) == {
        "speechbrain_ecapa",
        "resemblyzer",
        "sherpa_onnx_speaker_embedding",
        "wespeaker",
        "campplus_speaker_embedding",
        "eres2net_base_speaker_embedding",
        "redimnet2_b2_speaker_embedding",
    }


def test_manifest_set_is_immutable_valid_and_privacy_safe():
    result = validate_protocol_manifest_set(DEFAULT_MANIFEST_ROOT)
    assert result["valid"] is True
    index = json.loads(
        (DEFAULT_MANIFEST_ROOT / "speaker_protocol_manifest.json").read_text(encoding="utf-8")
    )
    assert index["selection_seed"] == 3800
    assert index["privacy"]["private_real_name_mapping_included"] is False
    for filename in MANIFEST_FILENAMES.values():
        assert "speaker_id" not in pq.read_table(DEFAULT_MANIFEST_ROOT / filename).column_names
        assert "display_name" not in pq.read_table(DEFAULT_MANIFEST_ROOT / filename).column_names


def test_manifest_rebuild_matches_committed_golden(tmp_path):
    rebuilt = build_protocol_manifests(tmp_path, tier="small")
    committed = json.loads(
        (DEFAULT_MANIFEST_ROOT / "speaker_protocol_manifest.json").read_text(encoding="utf-8")
    )
    assert rebuilt["protocol_id"] == committed["protocol_id"]
    assert {
        key: value["sha256"] for key, value in rebuilt["artifacts"].items()
    } == {
        key: value["sha256"] for key, value in committed["artifacts"].items()
    }


def test_enrollment_probe_and_calibration_evaluation_do_not_leak(small_rows):
    report = leakage_report(small_rows)
    assert all(report.values())
    calibration_unknown = {
        row["speaker_key"]
        for row in small_rows["calibration"]
        if row["trial_role"] == "unknown_probe"
    }
    evaluation_unknown = {
        row["speaker_key"] for row in small_rows["unknown_evaluation"]
    }
    assert calibration_unknown.isdisjoint(evaluation_unknown)


def test_backend_model_dimension_and_preprocessing_mismatches_are_rejected(
    synthetic_identity,
):
    for changes in (
        {"backend_id": "different"},
        {"model_hash": "C" * 64},
        {"embedding_dimension": 5},
        {"preprocessing": {"sample_rate_hz": 8000}},
    ):
        value = synthetic_identity.to_jsonable()
        value.pop("identity_hash")
        value.update(changes)
        with pytest.raises(SpeakerProtocolError, match="incompatible"):
            validate_enrollment_compatibility(
                synthetic_identity, BackendIdentity.from_mapping(value)
            )


def test_observation_identity_mismatch_rejected(
    tmp_path, smoke_rows, synthetic_identity
):
    observations = _observations(smoke_rows, synthetic_identity)
    first = observations[0]
    observations[0] = EmbeddingObservation(
        item_id=first.item_id,
        backend_id=first.backend_id,
        model_hash="C" * 64,
        config_hash=first.config_hash,
        vector=first.vector,
    )
    with pytest.raises(SpeakerProtocolError, match="model_hash"):
        evaluate_protocol_rows(
            smoke_rows,
            observations,
            synthetic_identity,
            tmp_path / "mismatch",
            scope="test",
        )


def test_threshold_eer_far_and_frr_contracts():
    trials = [
        {"score": 0.95, "is_target": True},
        {"score": 0.85, "is_target": True},
        {"score": 0.20, "is_target": False},
        {"score": 0.10, "is_target": False},
    ]
    sweep = threshold_sweep(trials, split="calibration")
    eer = equal_error_rate(sweep)
    assert eer is not None and eer["eer"] == 0.0
    operating = operating_point(trials, float(eer["threshold"]))
    assert operating is not None
    assert operating["far"] == 0.0
    assert operating["frr"] == 0.0


def test_metrics_reconcile_and_open_closed_results_are_separate(synthetic_result):
    root, metrics = synthetic_result
    assert metrics["counts_reconcile"] is True
    assert metrics["calibration_evaluation_separate"] is True
    assert metrics["closed_set_identification"]["top_1"]["value"] == 1.0
    assert metrics["open_set_identification"]["unknown_rejection"]["value"] == 1.0
    assert metrics["verification"]["operating_threshold_source"] == "calibration_only"
    assert validate_protocol_results(root)["valid"] is True


def test_unknown_is_preserved_and_reference_fallback_is_forbidden(
    tmp_path, smoke_rows, synthetic_identity
):
    missing_known = str(smoke_rows["known_evaluation"][0]["item_id"])
    root = tmp_path / "failed-probe"
    metrics = evaluate_protocol_rows(
        smoke_rows,
        _observations(smoke_rows, synthetic_identity, omit=missing_known),
        synthetic_identity,
        root,
        scope="failure-denominator-test",
    )
    decisions = pq.read_table(root / "unknown_rejection_decisions.parquet").to_pylist()
    missing = next(row for row in decisions if row["probe_id"] == missing_known)
    assert missing["predicted_speaker_key"] == UNKNOWN_LABEL
    assert missing["predicted_speaker_key"] != missing["true_speaker_key"]
    assert missing["status"] == "failed"
    assert missing["correct"] is False
    assert metrics["extraction"]["success_rate"]["denominator"] == 8
    assert metrics["extraction"]["success_rate"]["numerator"] == 7


def test_enrollment_vectors_are_npz_without_pickle(synthetic_result):
    root, _ = synthetic_result
    centroid = next((root / "enrollment" / "centroids").glob("*.npz"))
    with np.load(centroid, allow_pickle=False) as archive:
        assert "centroid" in archive.files
        assert archive["centroid"].ndim == 1


def test_calibration_and_evaluation_score_tables_are_distinct(synthetic_result):
    root, _ = synthetic_result
    scores = pq.read_table(root / "similarity_scores.parquet").to_pylist()
    calibration = {row["probe_id"] for row in scores if row["protocol_split"] == "calibration"}
    evaluation = {row["probe_id"] for row in scores if row["protocol_split"] == "evaluation"}
    assert calibration
    assert evaluation
    assert calibration.isdisjoint(evaluation)


@pytest.mark.parametrize(
    "backend_id",
    [
        "speechbrain_ecapa",
        "resemblyzer",
        "sherpa_onnx_speaker_embedding",
        "wespeaker",
    ],
)
def test_real_ecapa_and_extended_embedding_smokes_are_available(backend_id):
    matrix = json.loads(
        (DEFAULT_OUTPUT_ROOT / "real_smoke_matrix.json").read_text(encoding="utf-8")
    )
    row = next(value for value in matrix["results"] if value["backend_id"] == backend_id)
    assert row["status"] == "passed"
    assert row["successful_items"] == matrix["item_count_per_backend"]
    assert row["unknown_label"] == UNKNOWN_LABEL


def test_shared_smoke_artifacts_contain_no_private_identity_mapping():
    matrix = json.loads(
        (DEFAULT_OUTPUT_ROOT / "real_smoke_matrix.json").read_text(encoding="utf-8")
    )
    assert matrix["private_identity_mapping_included"] is False
    for path in DEFAULT_OUTPUT_ROOT.rglob("*.json"):
        text = path.read_text(encoding="utf-8").casefold()
        assert '"real_name"' not in text
        assert '"display_name"' not in text
