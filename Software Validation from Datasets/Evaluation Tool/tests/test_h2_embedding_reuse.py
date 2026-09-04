from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.full_pipeline.coordinator import StreamingPipelineCoordinator
from app.full_pipeline.embedding_reuse import (
    H2EmbeddingReuseRouter,
    R2_ONE_SHARED_MODEL,
    R3_EXACT_WINDOW_EMBEDDING_REUSE,
    R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION,
    request_fingerprint,
)
from app.full_pipeline.identity import (
    FROZEN_IDENTITY_POLICIES,
    ClusterCreation,
    IdentityEvidence,
    SessionIdentityManager,
)
from app.full_pipeline.models import EmbeddingResult, EmbeddingWindow
from app.full_pipeline.product_modes import H2RuntimeTuning
from app.h2_product_program.contracts import H2ProgramError
from app.h2_product_program.reuse import (
    VariantExecution,
    _assert_no_raw_embedding_vectors,
    _cleanup_private_probe_vector_cache,
    _combined_strategy_decision,
    compare_paired_bundles,
)


class _FakeEmbeddingAdapter:
    def __init__(
        self,
        *,
        vector: tuple[float, ...] = (1.0, 0.0),
        backend_config_sha256: str = "b" * 64,
    ) -> None:
        self.vector = np.asarray(vector, dtype=np.float32)
        self.backend_id = "redimnet2_b2_speaker_embedding"
        self.model_id = "ReDimNet2-B2"
        self.model_sha256 = "a" * 64
        self.backend_config_sha256 = backend_config_sha256
        self.calls = 0
        self.worker = SimpleNamespace()
        self._worker_started = True

    def reuse_identity_contract(self) -> dict[str, object]:
        return {
            "backend_id": self.backend_id,
            "model_id": self.model_id,
            "model_sha256": self.model_sha256,
            "backend_config_sha256": self.backend_config_sha256,
            "preprocessing": {
                "sample_rate_hz": 16000,
                "channel_policy": "mono",
                "sample_dtype": "float32",
                "normalization": "backend_l2",
                "worker_audio_transport": "pcm16_wav",
            },
        }

    def embed(self, window: EmbeddingWindow) -> EmbeddingResult:
        self.calls += 1
        vector = self.vector / np.linalg.norm(self.vector)
        return EmbeddingResult(
            window_id=window.window_id,
            backend_id=self.backend_id,
            model_id=self.model_id,
            model_sha256=self.model_sha256,
            vector=vector.copy(),
            duration_sec=window.end_sec - window.start_sec,
            role=window.role,
            quality={"status": "accepted"},
            cache_key=f"fake-{self.calls}",
            compute_latency_ms=1.0,
        )

    def status(self) -> dict[str, object]:
        return {
            "state": "running",
            "embedding_telemetry": {
                "neural_embedding_calls": self.calls,
                "initialization_sec": 0.1,
                "model_bytes": 1024,
            },
        }


def _window(
    role: str,
    *,
    window_id: str = "window-1",
    samples: np.ndarray | None = None,
    start_sec: float = 0.0,
    end_sec: float = 1.5,
) -> EmbeddingWindow:
    if samples is None:
        time = np.arange(round((end_sec - start_sec) * 16000), dtype=np.float32)
        samples = (0.1 * np.sin(2.0 * np.pi * 220.0 * time / 16000.0)).astype(
            np.float32
        )
    return EmbeddingWindow(
        window_id=window_id,
        start_sec=start_sec,
        end_sec=end_sec,
        assignment_start_sec=start_sec,
        assignment_end_sec=end_sec,
        samples=samples,
        role=role,
    )


def _router(strategy: str) -> tuple[H2EmbeddingReuseRouter, _FakeEmbeddingAdapter]:
    adapter = _FakeEmbeddingAdapter()
    return (
        H2EmbeddingReuseRouter(
            strategy=strategy,
            diarization_embedder=adapter,
            identity_embedder=adapter,
            minimum_identity_duration_sec=0.75,
            identity_accumulation="accumulated_window",
        ),
        adapter,
    )


def test_role_requests_are_distinct_but_exact_scientific_inputs_are_equivalent() -> None:
    adapter = _FakeEmbeddingAdapter()
    diar = request_fingerprint(_window("anonymous_diarization"), adapter)
    identity = request_fingerprint(_window("identity_matching"), adapter)
    assert diar.request_sha256 != identity.request_sha256
    assert diar.equivalence_sha256 == identity.equivalence_sha256
    assert diar.equivalent_to(identity) is True

    changed_pcm = request_fingerprint(
        _window("identity_matching", samples=np.ones(24000, dtype=np.float32)),
        adapter,
    )
    changed_bounds = request_fingerprint(
        _window("identity_matching", start_sec=0.25, end_sec=1.75), adapter
    )
    changed_backend = request_fingerprint(
        _window("identity_matching"),
        _FakeEmbeddingAdapter(backend_config_sha256="c" * 64),
    )
    assert not diar.equivalent_to(changed_pcm)
    assert not diar.equivalent_to(changed_bounds)
    assert not diar.equivalent_to(changed_backend)


def test_fingerprint_bounds_match_materialized_exact_duration_pcm() -> None:
    start_sec = 4.87096875
    end_sec = 5.370968749999999
    window = _window(
        "identity_matching",
        start_sec=start_sec,
        end_sec=end_sec,
        samples=np.zeros(8000, dtype=np.float32),
    )
    fingerprint = request_fingerprint(window, _FakeEmbeddingAdapter())

    assert fingerprint.source_end_sample - fingerprint.source_start_sample == 8000
    assert fingerprint.duration_samples == 8000


def test_r3_reuses_only_exact_window_and_records_hash_scalar_counters() -> None:
    router, adapter = _router(R3_EXACT_WINDOW_EMBEDDING_REUSE)
    diar = router.embed_diarization(_window("anonymous_diarization"))
    identity = router.embed_identity(_window("identity_matching"))
    assert adapter.calls == 1
    assert np.array_equal(diar.vector, identity.vector)
    observation = router.observations()[0]
    assert observation["reused"] is True
    assert observation["fresh_fallback"] is False
    assert observation["diarization_vector_sha256"] == observation[
        "identity_vector_sha256"
    ]
    assert observation["diarization_normalized_pcm_sha256"] == observation[
        "identity_normalized_pcm_sha256"
    ]
    assert observation["source_start_sample"] == 0
    assert observation["source_end_sample"] == 24000
    assert observation["duration_samples"] == 24000
    assert observation["diarization_preprocessing_identity_sha256"] == observation[
        "identity_preprocessing_identity_sha256"
    ]
    assert observation["raw_embedding_vectors_present"] is False
    assert "vector" not in observation
    telemetry = router.telemetry()
    assert telemetry["diarization_model_calls"] == 1
    assert telemetry["identity_model_calls"] == 0
    assert telemetry["reuse_hits"] == 1
    assert telemetry["total_embedding_model_calls"] == 1

    router.embed_diarization(_window("anonymous_diarization", window_id="window-2"))
    router.embed_identity(
        _window(
            "identity_matching",
            window_id="window-2",
            samples=np.ones(24000, dtype=np.float32),
        )
    )
    fallback = router.observations()[-1]
    assert fallback["reused"] is False
    assert fallback["fresh_fallback"] is True
    assert fallback["fallback_reason"] == (
        "scientific_equivalence_fingerprint_mismatch"
    )
    assert adapter.calls == 3


def test_r4_applies_identity_quality_then_preserves_aggregation_contract() -> None:
    router, adapter = _router(R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION)
    router.embed_diarization(_window("anonymous_diarization"))
    router.embed_identity(_window("identity_matching"))
    accepted = router.observations()[-1]
    assert accepted["reused"] is True
    assert accepted["identity_quality_status"] == "accepted"
    assert accepted["duration_weighting"] is True
    assert accepted["recent_vs_accumulated"] == "accumulated_window"
    assert adapter.calls == 1

    silence = np.zeros(24000, dtype=np.float32)
    router.embed_diarization(
        _window("anonymous_diarization", window_id="silent", samples=silence)
    )
    router.embed_identity(
        _window("identity_matching", window_id="silent", samples=silence)
    )
    rejected = router.observations()[-1]
    assert rejected["reused"] is False
    assert rejected["fresh_fallback"] is True
    assert rejected["fallback_reason"] == "identity_quality_level_below_minimum"
    assert rejected["identity_quality_policy_sha256"]
    assert router.telemetry()["quality_fallbacks"] == 1
    assert router.telemetry()["identity_model_calls"] == 1
    assert adapter.calls == 3


@pytest.mark.parametrize(
    ("accumulation", "expected_count"),
    (("accumulated_window", 2), ("recent_window", 1)),
)
def test_r4_downstream_aggregation_remains_duration_weighted_and_configurable(
    accumulation: str, expected_count: int
) -> None:
    coordinator = object.__new__(StreamingPipelineCoordinator)
    coordinator._identity_vectors = {}
    coordinator._identity_observation_times = {}
    coordinator.runtime_tuning = H2RuntimeTuning(
        redim_execution_strategy=R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION,
        embedding_reuse_qualification_sha256="f" * 64,
        identity_accumulation=accumulation,
    )
    first = np.asarray([1.0, 0.0], dtype=np.float32)
    second = np.asarray([0.0, 1.0], dtype=np.float32)
    coordinator._upsert_identity_observation(
        "cluster-a", "w1", first, 1.0, source_time_sec=1.0
    )
    _, rows = coordinator._upsert_identity_observation(
        "cluster-a", "w2", second, 3.0, source_time_sec=2.0
    )
    assert len(rows) == expected_count
    weights = np.asarray([duration for _, duration in rows])
    aggregate = np.average(
        np.stack([vector for vector, _ in rows]), axis=0, weights=weights
    )
    aggregate = aggregate / np.linalg.norm(aggregate)
    expected = (
        np.asarray([1.0, 3.0], dtype=np.float32)
        if accumulation == "accumulated_window"
        else second
    )
    expected = expected / np.linalg.norm(expected)
    assert np.allclose(aggregate, expected)


def test_successful_private_measurement_cleanup_removes_only_probe_cache(
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "attempt_001"
    probe_cache = attempt / "resource_runtime_cache"
    shared_cache = tmp_path / "shared_cache"
    probe_cache.mkdir(parents=True)
    shared_cache.mkdir()
    (probe_cache / "probe-vector.json").write_text("[0.1, 0.2]")
    (shared_cache / "enrollment-vector.json").write_text("[0.3, 0.4]")

    cleanup = _cleanup_private_probe_vector_cache(attempt)

    assert cleanup["status"] == "DELETED_AFTER_CHECKSUM_SEALED_MEASUREMENT"
    assert not probe_cache.exists()
    assert shared_cache.is_dir()
    assert _cleanup_private_probe_vector_cache(attempt)["status"] == "ALREADY_ABSENT"


def test_r1_r2_semantics_stay_fresh_and_do_not_claim_reuse() -> None:
    router, adapter = _router(R2_ONE_SHARED_MODEL)
    router.embed_diarization(_window("anonymous_diarization"))
    router.embed_identity(_window("identity_matching"))
    assert adapter.calls == 2
    assert router.observations()[0]["reused"] is False
    assert router.telemetry()["reuse_hits"] == 0


def _paired_bundle(*, candidate: bool) -> dict[str, object]:
    strategy = (
        R3_EXACT_WINDOW_EMBEDDING_REUSE
        if candidate
        else R2_ONE_SHARED_MODEL
    )
    embedding_rows = [
        {
            "case_id": "case-1",
            "window_id": "window-1",
            "diarization_vector_sha256": "1" * 64,
            "identity_vector_sha256": "1" * 64,
            "embedding_cosine_agreement": 1.0,
            "maximum_absolute_error": 0.0,
            "reused": candidate,
        }
    ]
    scores = [
        {
            "case_id": "case-1",
            "source_time_sec": 2.0,
            "predicted_overlap": False,
            "top1_candidate_id": "Alice",
            "top1_score": 0.8,
            "top2_candidate_id": "Bob",
            "top2_score": 0.2,
            "candidate_raw_cosine_scores": {"Alice": 0.8, "Bob": 0.2},
        }
    ]
    identity_event = {
        "event_id": "volatile-identity",
        "event_type": "identity_evidence",
        "backend_latency_ms": 9.0 if candidate else 99.0,
        "payload": {
            "anonymous_speaker_id": "anon-a",
            "top1_candidate_speaker_id": "Alice",
            "top1_raw_score": 0.8,
            "top2_candidate_speaker_id": "Bob",
            "top2_raw_score": 0.2,
            "top1_top2_margin": 0.6,
            "threshold_identity": {
                "score_threshold": 0.5,
                "margin_threshold": 0.03,
            },
            "decision": {"identity_state": "confirmed_known", "accepted": True},
            "decision_reason": {"code": "candidate_confirmed", "detail": None},
        },
    }
    anonymous_events = [
        {
            "event_id": "volatile-anon-1",
            "event_type": "anonymous_speaker",
            "payload": {
                "anonymous_speaker_id": "anon-a",
                "start_sec": 0.0,
                "end_sec": 1.0,
            },
        },
        {
            "event_id": "volatile-anon-2",
            "event_type": "anonymous_speaker",
            "payload": {
                "anonymous_speaker_id": "anon-a",
                "start_sec": 1.0,
                "end_sec": 2.0,
            },
        },
    ]
    return {
        "embedding_reuse_observations": embedding_rows,
        "challenger_score_observations": scores,
        "events": [*anonymous_events, identity_event],
        "labelled_rows": [
            {
                "case_id": "case-1",
                "start_sec": 0.0,
                "end_sec": 2.0,
                "text": "hello",
                "anonymous_speaker_id": "anon-a",
                "speaker_label": "Alice",
                "state": "final",
            }
        ],
        "hypothesis_segments": [
            {
                "start_sec": 0.0,
                "end_sec": 1.0,
                "speaker_id": "anon-a",
                "overlap": False,
            },
            {
                "start_sec": 1.0,
                "end_sec": 2.0,
                "speaker_id": "anon-a",
                "overlap": False,
            },
        ],
        "selected_profile_identity_sha256": "f" * 64,
        "total_embedding_model_calls": 2 if candidate else 4,
        "identity_model_calls": 0 if candidate else 2,
        "reuse_hits": 2 if candidate else 0,
        "audio_seconds_embedded": 2.0 if candidate else 4.0,
        "strategy": strategy,
    }


def test_paired_comparator_passes_all_required_surfaces_and_benefit() -> None:
    comparison = compare_paired_bundles(
        _paired_bundle(candidate=False),
        _paired_bundle(candidate=True),
        strategy=R3_EXACT_WINDOW_EMBEDDING_REUSE,
    )
    assert comparison["required_parity_outputs_measured"] is True
    assert comparison["parity_passed"] is True
    assert comparison["candidate_qualified"] is True
    assert comparison["engineering_benefit_measured"] is True
    assert comparison["embedding_cosine_agreement"] == 1.0
    assert comparison["maximum_absolute_error"] == 0.0


def test_reused_fp32_vector_accepts_predeclared_numeric_tolerance_chain() -> None:
    baseline = _paired_bundle(candidate=False)
    candidate = _paired_bundle(candidate=True)
    observation = candidate["embedding_reuse_observations"][0]  # type: ignore[index]
    observation["identity_vector_sha256"] = "2" * 64  # type: ignore[index]
    observation["embedding_cosine_agreement"] = 1.0  # type: ignore[index]
    observation["maximum_absolute_error"] = 2.980232238769531e-08  # type: ignore[index]

    comparison = compare_paired_bundles(
        baseline,
        candidate,
        strategy=R3_EXACT_WINDOW_EMBEDDING_REUSE,
    )

    assert comparison["required_parity_outputs_measured"] is True
    assert comparison["parity_passed"] is True
    assert comparison["candidate_qualified"] is True
    assert comparison["maximum_absolute_error"] == pytest.approx(
        2.980232238769531e-08
    )


def test_run_local_event_ids_and_absolute_sequences_are_not_product_semantics() -> None:
    baseline = _paired_bundle(candidate=False)
    candidate = _paired_bundle(candidate=True)
    for index, (base, cand) in enumerate(
        zip(baseline["events"], candidate["events"])  # type: ignore[arg-type]
    ):
        base["event_sequence"] = index + 100  # type: ignore[index]
        cand["event_sequence"] = index + 200  # type: ignore[index]
    baseline_identity = baseline["events"][-1]["payload"]  # type: ignore[index]
    candidate_identity = candidate["events"][-1]["payload"]  # type: ignore[index]
    baseline_identity["decision_reason"]["causal_event_ids"] = ["baseline-event"]
    candidate_identity["decision_reason"]["causal_event_ids"] = ["candidate-event"]

    comparison = compare_paired_bundles(
        baseline,
        candidate,
        strategy=R3_EXACT_WINDOW_EMBEDDING_REUSE,
    )

    assert comparison["known_unknown_decision_agreement"] is True
    assert comparison["event_sequence_semantic_agreement"] is True
    assert comparison["candidate_qualified"] is True


def test_parity_without_measured_embedding_call_reduction_is_not_qualified() -> None:
    baseline = _paired_bundle(candidate=False)
    candidate = _paired_bundle(candidate=True)
    candidate["total_embedding_model_calls"] = baseline[
        "total_embedding_model_calls"
    ]
    comparison = compare_paired_bundles(
        baseline,
        candidate,
        strategy=R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION,
    )

    assert comparison["parity_passed"] is True
    assert comparison["engineering_benefit_measured"] is False
    assert comparison["candidate_qualified"] is False


def test_periodic_resource_samples_do_not_corrupt_product_event_parity() -> None:
    baseline = _paired_bundle(candidate=False)
    candidate = _paired_bundle(candidate=True)
    baseline["events"].append(  # type: ignore[union-attr]
        {"event_type": "resource_telemetry", "process_rss_bytes": 100}
    )
    candidate["events"].extend(  # type: ignore[union-attr]
        [
            {"event_type": "resource_telemetry", "process_rss_bytes": 200},
            {"event_type": "resource_telemetry", "process_rss_bytes": 300},
        ]
    )
    candidate["events"][-3]["payload"]["threshold_identity"][  # type: ignore[index]
        "threshold_policy_id"
    ] = "strategy-specific-provenance"
    comparison = compare_paired_bundles(
        baseline,
        candidate,
        strategy=R3_EXACT_WINDOW_EMBEDDING_REUSE,
    )
    assert comparison["event_sequence_semantic_agreement"] is True
    assert comparison["parity_passed"] is True


def _variant(
    strategy: str,
    *,
    measurement_sha: str,
    identity_calls: int,
    total_calls: int,
    audio_sec: float,
) -> VariantExecution:
    measurement = {
        "identity_model_calls": identity_calls,
        "total_embedding_model_calls": total_calls,
        "audio_seconds_embedded": audio_sec,
    }
    return VariantExecution(
        strategy=strategy,
        spec=SimpleNamespace(),  # type: ignore[arg-type]
        result_root=Path("result"),
        measurement_path=Path("measurement.json"),
        measurement_sha256=measurement_sha,
        measurement=measurement,
        bundle={},
    )


def test_combined_r2_r3_r4_selection_is_deterministic_and_binds_both_candidates() -> None:
    baseline = _variant(
        R2_ONE_SHARED_MODEL,
        measurement_sha="b" * 64,
        identity_calls=2,
        total_calls=4,
        audio_sec=4.0,
    )
    r4 = _variant(
        R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION,
        measurement_sha="4" * 64,
        identity_calls=0,
        total_calls=2,
        audio_sec=2.0,
    )
    r3_result = {
        "candidate_qualified": True,
        "parity_passed": True,
        "candidate_measurement_sha256": "3" * 64,
        "published_result_sha256": "5" * 64,
        "candidate_measurement": {
            "identity_model_calls": 0,
            "total_embedding_model_calls": 2,
            "audio_seconds_embedded": 2.0,
        },
    }
    comparison = {"candidate_qualified": True, "parity_passed": True}

    first = _combined_strategy_decision(
        baseline=baseline,
        r3_result=r3_result,
        r4_candidate=r4,
        r4_comparison=comparison,
    )
    second = _combined_strategy_decision(
        baseline=baseline,
        r3_result=r3_result,
        r4_candidate=r4,
        r4_comparison=comparison,
    )

    assert first == second
    assert first["selected_strategy"] == R3_EXACT_WINDOW_EMBEDDING_REUSE
    assert first["r3_candidate_measurement_sha256"] == "3" * 64
    assert first["r4_candidate_measurement_sha256"] == "4" * 64
    assert first["last_job_wins_used"] is False


def test_combined_selection_retains_r2_when_both_reuse_candidates_are_rejected() -> None:
    baseline = _variant(
        R2_ONE_SHARED_MODEL,
        measurement_sha="b" * 64,
        identity_calls=2,
        total_calls=4,
        audio_sec=4.0,
    )
    r4 = _variant(
        R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION,
        measurement_sha="4" * 64,
        identity_calls=0,
        total_calls=2,
        audio_sec=2.0,
    )
    r3_result = {
        "candidate_qualified": False,
        "parity_passed": False,
        "candidate_measurement_sha256": "3" * 64,
        "published_result_sha256": "5" * 64,
        "candidate_measurement": {
            "identity_model_calls": 0,
            "total_embedding_model_calls": 2,
            "audio_seconds_embedded": 2.0,
        },
    }

    decision = _combined_strategy_decision(
        baseline=baseline,
        r3_result=r3_result,
        r4_candidate=r4,
        r4_comparison={"candidate_qualified": False, "parity_passed": False},
    )

    assert decision["selected_strategy"] == R2_ONE_SHARED_MODEL
    assert decision["pareto_frontier"] == [R2_ONE_SHARED_MODEL]


def test_exportable_reuse_aggregate_rejects_any_raw_embedding_vector() -> None:
    _assert_no_raw_embedding_vectors(
        {"observation": {"identity_vector_sha256": "a" * 64}}
    )
    with pytest.raises(H2ProgramError, match="raw embedding vector"):
        _assert_no_raw_embedding_vectors(
            {"observation": {"embedding_vector": [0.1, 0.2]}}
        )


@pytest.mark.parametrize(
    ("mutation", "expected_check"),
    (
        ("vector", "embedding"),
        ("score", "score"),
        ("decision", "known_unknown_decision"),
        ("cluster", "anonymous_cluster_assignment"),
        ("label", "transcript_label"),
        ("event", "event_sequence_semantic"),
    ),
)
def test_paired_comparator_fails_closed_on_each_changed_surface(
    mutation: str, expected_check: str
) -> None:
    baseline = _paired_bundle(candidate=False)
    candidate = _paired_bundle(candidate=True)
    if mutation == "vector":
        candidate["embedding_reuse_observations"][0][  # type: ignore[index]
            "identity_vector_sha256"
        ] = "2" * 64
        candidate["embedding_reuse_observations"][0][  # type: ignore[index]
            "maximum_absolute_error"
        ] = 2.0e-6
    elif mutation == "score":
        candidate["challenger_score_observations"][0][  # type: ignore[index]
            "candidate_raw_cosine_scores"
        ]["Alice"] = 0.7  # type: ignore[index]
    elif mutation == "decision":
        candidate["events"][-1]["payload"]["decision"][  # type: ignore[index]
            "identity_state"
        ] = "unknown"
    elif mutation == "cluster":
        candidate["hypothesis_segments"][1][  # type: ignore[index]
            "speaker_id"
        ] = "anon-b"
    elif mutation == "label":
        candidate["labelled_rows"][0]["speaker_label"] = "Bob"  # type: ignore[index]
    elif mutation == "event":
        candidate["events"][0]["payload"]["new_semantic_field"] = True  # type: ignore[index]
    comparison = compare_paired_bundles(
        baseline,
        candidate,
        strategy=R3_EXACT_WINDOW_EMBEDDING_REUSE,
    )
    assert comparison["parity_passed"] is False
    assert comparison["candidate_qualified"] is False
    assert comparison["checks"][expected_check] is False


@pytest.mark.parametrize("policy_name", ("H2A_ADAPTIVE_EARLY", "H4_DURATION_DEPENDENT"))
def test_adaptive_identity_event_contract_uses_effective_thresholds(
    policy_name: str,
) -> None:
    policy = replace(
        FROZEN_IDENTITY_POLICIES["H2"],
        hysteresis_policy=policy_name,
        frozen_anchor=False,
    )
    manager = SessionIdentityManager(policy)
    manager.ensure_cluster(ClusterCreation(0.0, 1, "anon-a"))
    transition = manager.observe(
        IdentityEvidence(
            anonymous_speaker_id="anon-a",
            source_time_sec=1.0,
            evidence_duration_sec=1.0,
            candidate_scores={"Alice": 0.9, "Bob": 0.1},
            embedding_consistency=0.9,
            evidence_event_id="evidence-1",
        )
    )
    coordinator = object.__new__(StreamingPipelineCoordinator)
    coordinator.identity_manager = manager
    coordinator.decision_policy_contract = None
    base = coordinator._threshold_contract(2)
    event = coordinator._threshold_contract_for_transition(2, transition)
    assert base["score_threshold"] == policy.score_threshold
    assert base["margin_threshold"] == policy.margin_threshold
    assert event["score_threshold"] == transition.effective_score_threshold
    assert event["margin_threshold"] == transition.effective_margin_threshold
    assert event["score_threshold"] != base["score_threshold"]
    assert event["margin_threshold"] != base["margin_threshold"]


def test_exportable_comparison_contains_no_raw_embedding_vectors() -> None:
    comparison = compare_paired_bundles(
        _paired_bundle(candidate=False),
        _paired_bundle(candidate=True),
        strategy=R3_EXACT_WINDOW_EMBEDDING_REUSE,
    )
    serialized = repr(comparison).casefold()
    assert "raw_embedding_vectors_present': false" in serialized
    assert "array(" not in serialized
