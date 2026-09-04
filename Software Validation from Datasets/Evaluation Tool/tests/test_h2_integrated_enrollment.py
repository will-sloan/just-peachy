from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.h2_product_program.integrated_enrollment import (
    ENROLLMENT_DURATION_ALLOCATION_POLICY,
    _cache_item_path,
    _integrated_enrollment_selection_key,
    _public_payload_has_vectors,
    build_historical_accounting,
    build_panel_manifest,
    calibrate_policy,
    evaluate_integrated_matrix,
    exact_binomial_upper_95,
    extract_slices_with_embedder,
    normalized_mean,
    score_enrollment,
    validate_panel_manifest,
    validate_private_cache,
)
from app.h2_product_program.io import canonical_sha256


def _tone(seconds: float, frequency: float) -> np.ndarray:
    frames = int(round(seconds * 16_000))
    time = np.arange(frames, dtype=np.float32) / 16_000
    return (0.15 * np.sin(2 * np.pi * frequency * time)).astype(np.float32)


def _dataset(tmp_path: Path) -> Path:
    root = tmp_path / "LibriSpeech" / "train-clean-100"
    for speaker_index in range(4):
        for chapter_index in range(3):
            chapter = root / str(100 + speaker_index) / str(200 + chapter_index)
            chapter.mkdir(parents=True)
            # Realistic minimum lengths expose the former 5-utterance/10-second
            # bug: four whole prefixes cannot fit inside the total budget.
            # Six longer and four shorter files satisfy every balanced cell
            # and provide two source-disjoint attempts.
            durations = [7.0] * 6 + [4.1] * 4
            for utterance_index, duration in enumerate(durations):
                path = chapter / (
                    f"{100 + speaker_index}-{200 + chapter_index}-{utterance_index:04d}.flac"
                )
                sf.write(
                    path,
                    _tone(duration, 180.0 + speaker_index * 70 + utterance_index),
                    16_000,
                )
    return root


@pytest.fixture(scope="module")
def dataset_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the moderately sized audio panel once for this test module."""

    return _dataset(tmp_path_factory.mktemp("h2_integrated_enrollment"))


def _fake_observations(panel: dict[str, object]) -> dict[str, dict[str, object]]:
    sources = panel["sources"]
    slices = panel["slices"]
    assert isinstance(sources, dict) and isinstance(slices, dict)
    speaker_vectors: dict[str, np.ndarray] = {}
    for role in panel["roles"].values():
        for speaker in role:
            safe = str(speaker["speaker_id"])
            digest = int(hashlib.sha256(safe.encode()).hexdigest()[:8], 16)
            vector = np.zeros(192, dtype=np.float32)
            vector[digest % 192] = 1.0
            vector[(digest // 193) % 192] += 0.2
            vector /= np.linalg.norm(vector)
            speaker_vectors[safe] = vector
    source_to_speaker: dict[str, str] = {}
    for role in panel["roles"].values():
        for speaker in role:
            all_ids = [probe["slice_id"] for probe in speaker["probes"]]
            all_ids.extend(
                slice_id
                for enrollment_set in speaker["enrollment_sets"]
                for attempt in enrollment_set["attempts"]
                for slice_id in attempt["slice_ids"]
            )
            for slice_id in all_ids:
                source_to_speaker[str(slices[slice_id]["source_id"])] = str(
                    speaker["speaker_id"]
                )
    output = {}
    for slice_id, row in slices.items():
        speaker = source_to_speaker[str(row["source_id"])]
        vector = speaker_vectors[speaker].copy()
        output[str(slice_id)] = {
            "vector": vector,
            "vector_sha256": hashlib.sha256(vector.astype("<f4").tobytes()).hexdigest(),
            "backend_identity_hash": "a" * 64,
            "extraction_sec": 0.01,
            "audio_quality": {
                "level_dbfs": -18.0,
                "clipping_fraction": 0.0,
                "voiced_proportion": 0.9,
                "voiced_duration_sec": float(row["duration_sec"]) * 0.9,
                "declared_noise_proxy_db": 8.0,
            },
        }
    return output


def test_panel_is_deterministic_disjoint_and_exact(dataset_root: Path) -> None:
    first = build_panel_manifest(
        dataset_root, speakers_per_role=1, probes_per_speaker=2
    )
    second = build_panel_manifest(
        dataset_root, speakers_per_role=1, probes_per_speaker=2
    )
    assert first == second
    validate_panel_manifest(first)
    assert first["panel_sha256"] == second["panel_sha256"]
    role_sets = [
        {row["speaker_id"] for row in first["roles"][role]} for role in first["roles"]
    ]
    assert all(
        not left & right
        for index, left in enumerate(role_sets)
        for right in role_sets[index + 1 :]
    )
    for role in ("calibration_known", "selection_known"):
        for speaker in first["roles"][role]:
            for enrollment_set in speaker["enrollment_sets"]:
                for attempt in enrollment_set["attempts"]:
                    assert len(attempt["slice_ids"]) == enrollment_set["utterances"]
                    assert (
                        abs(
                            sum(
                                first["slices"][value]["duration_sec"]
                                for value in attempt["slice_ids"]
                            )
                            - enrollment_set["total_duration_sec"]
                        )
                        < 1 / 16_000
                    )
                    assert attempt["duration_allocation_policy"] == (
                        ENROLLMENT_DURATION_ALLOCATION_POLICY
                    )
                    expected_base, expected_remainder = divmod(
                        int(round(enrollment_set["total_duration_sec"] * 16_000)),
                        enrollment_set["utterances"],
                    )
                    assert attempt["contribution_frames"] == [
                        expected_base + (1 if index < expected_remainder else 0)
                        for index in range(enrollment_set["utterances"])
                    ]
                first_sources = {
                    first["slices"][slice_id]["source_id"]
                    for slice_id in enrollment_set["attempts"][0]["slice_ids"]
                }
                second_sources = {
                    first["slices"][slice_id]["source_id"]
                    for slice_id in enrollment_set["attempts"][1]["slice_ids"]
                }
                assert first_sources.isdisjoint(second_sources)
                if enrollment_set["sessions"] == "varied":
                    assert all(
                        len(set(attempt["chapter_ids"])) >= 2
                        for attempt in enrollment_set["attempts"]
                    )


def test_five_utterances_share_ten_second_budget_evenly(dataset_root: Path) -> None:
    panel = build_panel_manifest(
        dataset_root, speakers_per_role=1, probes_per_speaker=1
    )
    for role in ("calibration_known", "selection_known"):
        for speaker in panel["roles"][role]:
            target_sets = [
                enrollment_set
                for enrollment_set in speaker["enrollment_sets"]
                if enrollment_set["utterances"] == 5
                and enrollment_set["total_duration_sec"] == 10.0
            ]
            assert len(target_sets) == 2
            for enrollment_set in target_sets:
                for attempt in enrollment_set["attempts"]:
                    assert attempt["contribution_frames"] == [32_000] * 5
                    assert attempt["slice_duration_sec"] == [2.0] * 5


def test_all_32_cells_and_qc_repeat_are_measured(dataset_root: Path) -> None:
    panel = build_panel_manifest(
        dataset_root, speakers_per_role=1, probes_per_speaker=2
    )
    observations = _fake_observations(panel)
    rows, qc, _hubness, selected = evaluate_integrated_matrix(panel, observations)
    assert len(rows) == 32
    assert {row["status"] for row in rows} == {"MEASURED"}
    assert any(row["attempt_action"] == "QUALITY_ACCEPTED" for row in qc)
    assert any(row["attempt_action"] == "BLIND_ACCEPTED_WITH_DIAGNOSTICS" for row in qc)
    assert selected["selection_label"] == "INTEGRATED_SELECTED_CELL"
    assert selected["selection_uses_development_only"] is True

    # Corrupt one predeclared first-attempt recording.  The quality-filtered
    # path must reject it and accept the source-disjoint repeat; blind mode
    # continues to accept the same poor attempt with diagnostics.
    target = panel["roles"]["calibration_known"][0]["enrollment_sets"][0]
    bad_slice = target["attempts"][0]["slice_ids"][0]
    observations[bad_slice]["audio_quality"]["clipping_fraction"] = 0.5
    _rows, repeated_qc, _hubness, _selected = evaluate_integrated_matrix(
        panel, observations
    )
    target_rows = [
        row
        for row in repeated_qc
        if row["physical_set_id"] == target["physical_set_id"]
    ]
    assert any(
        row["attempt_action"] == "REJECTED_REPEAT_REQUIRED" for row in target_rows
    )
    assert any(row["attempt_action"] == "QUALITY_ACCEPTED" for row in target_rows)
    assert any(
        row["attempt_action"] == "BLIND_ACCEPTED_WITH_DIAGNOSTICS"
        for row in target_rows
    )


def test_aggregation_formulas_and_calibration_firewall() -> None:
    first = np.zeros(192)
    second = np.zeros(192)
    probe = np.zeros(192)
    first[0] = 1
    second[1] = 1
    probe[0] = 1
    centroid = normalized_mean([first, second])
    assert np.isclose(np.linalg.norm(centroid), 1.0)
    assert np.isclose(
        score_enrollment(probe, [first, second], "normalized_mean"), 2**-0.5
    )
    assert np.isclose(
        score_enrollment(probe, [first, second], "frozen_redim_multi_template"),
        1.0,
    )
    known = [
        {
            "top1_score": 0.8,
            "top1_top2_margin": 0.1,
            "top1_speaker_id": "a",
            "true_speaker_id": "a",
            "true_partition": "known",
            "top1_correct": True,
        }
    ]
    strangers = [
        {
            "top1_score": 0.2 + index / 1000,
            "top1_top2_margin": 0.01,
            "top1_speaker_id": "a",
            "true_speaker_id": f"s{index}",
            "true_partition": "stranger",
            "top1_correct": False,
        }
        for index in range(80)
    ]
    policy = calibrate_policy(known, strangers)
    assert policy["calibration_identity_firewall"] == "CALIBRATION_SPEAKERS_ONLY"
    assert policy["empirical_fpir_resolution"] == 1 / 80
    assert policy["empirical_probe_fpir_resolution"] == 1 / 80
    assert policy["calibration_fpir_unit"] == "stranger_speaker_any_false_known"
    assert policy["target_fpir_demonstrable_at_trial_resolution"] is True
    assert exact_binomial_upper_95(0, 80) > 0


def test_private_cache_reuses_valid_and_repairs_only_corrupt(
    tmp_path: Path, dataset_root: Path
) -> None:
    panel = build_panel_manifest(
        dataset_root, speakers_per_role=1, probes_per_speaker=1
    )
    cache = tmp_path / "cache"

    def fake(samples: np.ndarray, _row: dict[str, object]) -> np.ndarray:
        vector = np.zeros(192, dtype=np.float32)
        vector[0] = 1.0
        vector[1] = min(0.1, float(np.mean(np.abs(samples))))
        return vector / np.linalg.norm(vector)

    slice_ids = sorted(panel["slices"])
    first = extract_slices_with_embedder(
        panel, cache, slice_ids, fake, require_storage_reserve=lambda: None
    )
    assert first["completed"] == len(slice_ids)
    validate_private_cache(panel, cache)
    broken = _cache_item_path(cache, slice_ids[0])
    broken.write_bytes(b"corrupt")
    second = extract_slices_with_embedder(
        panel, cache, slice_ids, fake, require_storage_reserve=lambda: None
    )
    assert second["completed"] == 1
    assert second["corrupt_repaired"] == 1
    assert second["reused"] == len(slice_ids) - 1
    validate_private_cache(panel, cache)


def test_historical_requested_cells_never_infer_sessions_or_qc() -> None:
    rows = [
        {
            "backend": "redimnet2_b2_speaker_embedding",
            "configuration_id": "old",
            "configuration_identity_hash": "a" * 64,
            "configuration_outcome": "SCORED",
            "enrollment_count": "3",
            "enrollment_target_audio_sec": "10.0",
            "aggregation_method": "multi_template_top2_mean_score",
            "source_sha256": "b" * 64,
            "fpir": "0.01",
        }
    ]
    inventory, requested = build_historical_accounting(
        rows, source_bindings=({"source_sha256": "b" * 64},)
    )
    assert inventory[0]["sessions"] == "UNAVAILABLE_NOT_RECORDED"
    assert len(requested) == 32
    assert {row["status"] for row in requested} == {"HISTORICAL_STANDALONE_UNSUPPORTED"}
    assert all(row["historical_metrics_borrowed"] is False for row in requested)


def test_public_vector_scan_allows_hashes_but_rejects_vectors() -> None:
    assert not _public_payload_has_vectors(
        {"vector_sha256": "a" * 64, "biometric_vector_exported": False}
    )
    assert _public_payload_has_vectors({"template_vectors": [[0.1, 0.2]]})
    assert canonical_sha256({"selection": "deterministic"})


def test_enrollment_selection_puts_wrong_known_before_stranger_risk() -> None:
    common = {
        "known_correct_rate": 0.9,
        "probe_scoring_latency_ms_mean": 1.0,
        "template_storage_float32_bytes_per_speaker": 768,
    }
    safer_known = {
        **common,
        "cell_id": "safer-known",
        "wrong_known_rate": 0.01,
        "stranger_speaker_fpir": 0.20,
        "stranger_fpir": 0.20,
    }
    safer_stranger = {
        **common,
        "cell_id": "safer-stranger",
        "wrong_known_rate": 0.02,
        "stranger_speaker_fpir": 0.00,
        "stranger_fpir": 0.00,
    }
    assert (
        min((safer_known, safer_stranger), key=_integrated_enrollment_selection_key)
        is safer_known
    )
