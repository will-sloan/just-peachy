from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.full_pipeline.coordinator import StreamingPipelineCoordinator
from app.full_pipeline.identity import FROZEN_IDENTITY_POLICIES
from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline.provenance import runtime_identities
from app.full_pipeline.runtime_components import WorkerStreamingSegmenter


TOOL_ROOT = Path(__file__).resolve().parents[2]
MATRIX = TOOL_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
RUNTIME = TOOL_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml"
FROZEN_SELECTION_SHA = (
    "2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a"
)


def test_diarization_provenance_uses_anonymous_embedding_not_identity_backend() -> None:
    matrix = FullPipelineMatrix(MATRIX, RUNTIME)
    h4 = matrix.resolve("fullpipe_v1_ao_dw_ir")
    h5 = matrix.resolve("fullpipe_v1_ao_dr_ie")

    h4_identity = runtime_identities(h4, evaluation_root=TOOL_ROOT)["diarization"]
    h5_identity = runtime_identities(h5, evaluation_root=TOOL_ROOT)["diarization"]

    assert str(h4.diarization_embedding["backend_id"]) == "wespeaker"
    assert str(h4.diarization_embedding["model_identity_sha256"]) in set(
        h4_identity.model_asset_sha256s
    )
    assert str(h4.identity["model_identity_sha256"]) not in set(
        h4_identity.model_asset_sha256s
    )
    assert str(h5.diarization_embedding["backend_id"]) == (
        "redimnet2_b2_speaker_embedding"
    )
    assert str(h5.diarization_embedding["model_identity_sha256"]) in set(
        h5_identity.model_asset_sha256s
    )
    assert str(h5.identity["model_identity_sha256"]) not in set(
        h5_identity.model_asset_sha256s
    )


def test_frozen_consistency_is_mean_cosine_to_duration_weighted_aggregate() -> None:
    coordinator = object.__new__(StreamingPipelineCoordinator)
    coordinator.identity_manager = SimpleNamespace(
        policy=FROZEN_IDENTITY_POLICIES["H2"]
    )
    rows = [
        (np.asarray([1.0, 0.0]), 1.0),
        (np.asarray([0.0, 1.0]), 1.0),
    ]
    aggregate = np.asarray([1.0, 1.0])
    aggregate /= np.linalg.norm(aggregate)
    assert coordinator._embedding_consistency(
        rows, aggregate=aggregate
    ) == pytest.approx(np.sqrt(0.5))


def test_overlap_query_uses_any_positive_committed_intersection() -> None:
    segmenter = object.__new__(WorkerStreamingSegmenter)
    segmenter._predicted_overlap_intervals = [(1.0, 1.5), (3.0, 3.25)]
    assert segmenter.predicted_overlap(0.5, 1.1) is True
    assert segmenter.predicted_overlap(1.5, 2.0) is False
    assert segmenter.predicted_overlap(3.1, 3.2) is True


def test_anchor_threshold_contract_binds_decision_not_enrollment_policy() -> None:
    matrix = FullPipelineMatrix(MATRIX, RUNTIME)
    selection = matrix.resolve("fullpipe_v1_ao_dr_ir")
    coordinator = object.__new__(StreamingPipelineCoordinator)
    coordinator.selection = selection
    coordinator.identity_manager = SimpleNamespace(
        policy=FROZEN_IDENTITY_POLICIES["H2"]
    )
    coordinator.decision_policy_contract = None

    threshold = coordinator._threshold_contract(57)
    assert threshold["threshold_policy_sha256"] == FROZEN_SELECTION_SHA
    assert threshold["threshold_policy_sha256"] != selection.enrollment_policy["sha256"]
    assert threshold["score_threshold"] == 0.5265351286789879
    assert threshold["target_fpir"] == 0.01
    assert threshold["gallery_size"] == 57
    assert threshold["threshold_scope"] == (
        "frozen_product_v2_balanced_gallery10_scalar_reused_for_all_galleries"
    )
