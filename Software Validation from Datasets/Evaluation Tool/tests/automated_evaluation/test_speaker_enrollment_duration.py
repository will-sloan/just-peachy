from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess

import pytest

from app.benchmark_contracts.canonical import canonical_sha256
from app.speaker_enrollment.auto_gate import build_automatic_joint_gate
from app.speaker_enrollment.evaluation import (
    duration_weighted_mean,
    enrollment_quality,
    evaluate_configuration,
    normalized_mean,
    score_templates,
    threshold_artifact_id,
    validate_configuration_result,
)
from app.speaker_deployment.replay import calibrate_open_set_policy
from app.speaker_enrollment import extraction as enrollment_extraction
from app.speaker_enrollment.analysis import analyze_results
from app.speaker_enrollment.extraction import cache_item_identity
from app.speaker_enrollment.protocol import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROTOCOL_ROOT,
    DEFAULT_SOURCE_PROTOCOL_ROOT,
    _build_protocol_rows,
    audio_slice_id,
    load_config,
    load_protocol_tables,
    required_slice_ids,
    resolve_phase_configurations,
)
from app.speaker_protocol.contracts import BackendIdentity


TOOL_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = TOOL_ROOT / "scripts" / "run_speaker_enrollment_study.ps1"


@pytest.fixture(scope="module")
def tables() -> dict[str, list[dict[str, str]]]:
    return load_protocol_tables(DEFAULT_PROTOCOL_ROOT)


def test_split_disjointness_unknown_never_enrolled_and_core_consistency(tables):
    roles_by_parent: dict[str, set[str]] = {}
    for row in tables["audio_slices"]:
        roles_by_parent.setdefault(row["parent_item_id"], set()).add(row["protocol_split"])
        assert not (row["speaker_role"] == "unknown" and row["protocol_split"] == "enrollment")
    assert all(len(value) == 1 for value in roles_by_parent.values())
    core = {row["speaker_key"] for row in tables["cohort"] if row["study_role"] == "known"}
    by_family: dict[str, set[str]] = {}
    for row in tables["enrollment_sets"]:
        by_family.setdefault(row["selection_family_id"], set()).add(row["speaker_key"])
    assert by_family
    assert all(value == core for value in by_family.values())


def test_calibration_and_evaluation_unknown_speakers_are_disjoint(tables):
    calibration = {row["speaker_key"] for row in tables["cohort"] if row["study_role"] == "calibration_unknown"}
    evaluation = {row["speaker_key"] for row in tables["cohort"] if row["study_role"] == "evaluation_unknown"}
    assert calibration
    assert evaluation
    assert calibration.isdisjoint(evaluation)


def test_duration_slice_identity_and_nested_probe_prefixes(tables):
    sample = tables["audio_slices"][0]
    assert sample["slice_id"] == audio_slice_id(
        sample["parent_item_id"],
        float(sample["start_sec"]),
        float(sample["end_sec"]),
        sample["duration_policy_version"],
    )
    assert sample["slice_id"] != audio_slice_id(
        sample["parent_item_id"],
        float(sample["start_sec"]),
        float(sample["end_sec"]) + 0.001,
        sample["duration_policy_version"],
    )
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in tables["probe_variants"]:
        grouped.setdefault(row["parent_item_id"], []).append(row)
    for rows in list(grouped.values())[:25]:
        prefixes = sorted(
            (float(row["target_audio_sec"]), float(row["start_sec"]), float(row["end_sec"]))
            for row in rows
            if row["duration_label"] != "natural"
        )
        assert [value[0] for value in prefixes] == [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
        assert {value[1] for value in prefixes} == {0.0}
        assert [value[2] for value in prefixes] == [value[0] for value in prefixes]


def test_enrollment_count_and_duration_budget_construction(tables):
    counts = {1, 2, 3, 5}
    observed_counts = set()
    observed_budgets = set()
    for row in tables["enrollment_sets"]:
        ids = json.loads(row["slice_ids_json"])
        if row["enrollment_basis"] == "natural_utterance_count":
            expected = int(row["target_count"])
            observed_counts.add(expected)
            assert len(ids) == expected
            assert int(row["actual_utterance_count"]) == expected
        else:
            target = float(row["target_audio_sec"])
            observed_budgets.add(target)
            assert float(row["actual_audio_sec"]) == pytest.approx(target, abs=1e-6)
    assert observed_counts == counts
    assert observed_budgets == {1.0, 2.0, 5.0, 10.0, 20.0}


def test_required_aggregation_methods():
    vectors = [(1.0, 0.0), (0.0, 1.0)]
    assert normalized_mean(vectors) == pytest.approx((2 ** -0.5, 2 ** -0.5))
    weighted = duration_weighted_mean(vectors, [3.0, 1.0])
    assert weighted[0] > weighted[1]
    probe = (1.0, 0.0)
    assert score_templates(probe, vectors, "normalized_mean", [3.0, 1.0]) == pytest.approx(2 ** -0.5)
    assert score_templates(probe, vectors, "duration_weighted_mean", [3.0, 1.0]) > 2 ** -0.5
    assert score_templates(probe, vectors, "multi_template_mean_score", [3.0, 1.0]) == pytest.approx(0.5)
    assert score_templates(probe, vectors, "multi_template_max_score", [3.0, 1.0]) == pytest.approx(1.0)
    assert score_templates(probe, vectors, "multi_template_top2_mean_score", [3.0, 1.0]) == pytest.approx(0.5)


def test_v2_open_set_policy_is_calibration_only_and_uses_margin():
    import numpy as np

    policy = calibrate_open_set_policy(
        np.asarray([0.90, 0.84, 0.80, 0.76]),
        np.asarray([0.12, 0.08, 0.05, 0.02]),
        np.asarray([True, True, True, False]),
        np.asarray([0.88, 0.70, 0.60, 0.50]),
        np.asarray([0.005, 0.04, 0.03, 0.02]),
        fpir_target=0.0,
        wrong_name_rate_cap=0.0,
        margin_grid=[0.0, 0.01, 0.05],
    )
    assert policy["evaluation_used_for_selection"] is False
    assert policy["margin_threshold"] >= 0.01
    accepted_unknown = (
        np.asarray([0.88, 0.70, 0.60, 0.50]) >= policy["score_threshold"]
    ) & (np.asarray([0.005, 0.04, 0.03, 0.02]) >= policy["margin_threshold"])
    assert not accepted_unknown.any()


def test_enrollment_quality_finds_inconsistent_template():
    quality = enrollment_quality([(1.0, 0.0), (0.99, 0.01), (-1.0, 0.0)])
    assert quality["lowest_consistency_template_index"] == 2
    assert quality["cohesion_gain_after_dropping_lowest"] > 0


def test_all_too_short_probe_duration_completes_as_technically_invalid(tmp_path, tables):
    reference = next(
        row
        for row in tables["configurations"]
        if row["phase"] == "EnrollmentCount"
        and row["enrollment_count"] == "5"
        and row["repetition"] == "0"
        and row["aggregation_method"] == "normalized_mean"
    )
    configuration = next(
        row
        for row in resolve_phase_configurations(
            DEFAULT_PROTOCOL_ROOT,
            "ProbeDuration",
            reference_enrollment_configuration_id=reference["configuration_id"],
        )
        if float(row["probe_target_audio_sec"]) == 0.5
    )
    required = required_slice_ids(DEFAULT_PROTOCOL_ROOT, [configuration])
    slice_rows = {row["slice_id"]: row for row in tables["audio_slices"] if row["slice_id"] in required}
    too_short = {
        row["slice_id"]
        for row in tables["probe_variants"]
        if row["duration_label"] == configuration["probe_duration_label"]
    }
    observations = {}
    for slice_id, row in slice_rows.items():
        if slice_id in too_short:
            observations[slice_id] = {
                "slice_id": slice_id,
                "status": "too_short",
                "duration_sec": float(row["duration_sec"]),
            }
        else:
            observations[slice_id] = {
                "slice_id": slice_id,
                "status": "ok",
                "duration_sec": float(row["duration_sec"]),
                "vector": (1.0, 0.0, 0.0, 0.0),
            }
    identity = BackendIdentity(
        backend_id="technical_invalid_test_backend",
        environment_profile="test",
        model_id="test",
        model_hash="0" * 64,
        config_path="TEST",
        config_hash="1" * 64,
        embedding_dimension=4,
        normalization="l2",
        preprocessing={"sample_rate_hz": 16000},
        aggregation_method="normalized_mean",
        threshold_policy_version="speaker-threshold-policy.v1",
        qualification_status="qualified",
    )
    result_base = tmp_path / "results"
    destination = (
        result_base
        / identity.backend_id
        / "phase_d_probe_duration"
        / configuration["configuration_id"]
    )
    result = evaluate_configuration(
        DEFAULT_PROTOCOL_ROOT,
        configuration,
        identity,
        observations,
        destination,
    )
    validation = validate_configuration_result(destination, protocol_root=DEFAULT_PROTOCOL_ROOT)

    assert result["status"] == "complete"
    assert result["configuration_outcome"] == "TECHNICALLY_INVALID"
    assert result["operating_threshold"] is None
    assert result["operating_margin"] is None
    assert result["metrics"]["valid_probe_rate"]["value"] == 0.0
    assert validation["calibration_unavailable_technically_invalid"] is True

    manifest = analyze_results(
        DEFAULT_PROTOCOL_ROOT,
        result_base,
        tmp_path / "analysis",
        [identity.backend_id],
        bootstrap_repetitions=2,
    )
    assert manifest["completed_configurations"] == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing-violation retry")
def test_embedding_cache_json_retries_windows_access_denied(tmp_path, monkeypatch):
    destination = tmp_path / "state.json"
    real_replace = enrollment_extraction.os.replace
    attempts = 0

    def flaky_replace(source, target):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            error = PermissionError("transient sharing violation")
            error.winerror = 5
            raise error
        real_replace(source, target)

    monkeypatch.setattr(enrollment_extraction.os, "replace", flaky_replace)
    monkeypatch.setattr(enrollment_extraction.time, "sleep", lambda _: None)
    enrollment_extraction._write_json(destination, {"status": "ok"})

    assert attempts == 2
    assert json.loads(destination.read_text(encoding="utf-8")) == {"status": "ok"}
    assert not list(tmp_path.glob(".state.json.tmp-*"))


def test_automatic_phase_e_gate_uses_only_calibration_metrics(tmp_path):
    backend = "test_backend"
    protocol_root = tmp_path / "protocol"
    result_base = tmp_path / "results"
    protocol_root.mkdir()
    (protocol_root / "selection_config.yaml").write_text(
        "schema_version: speaker-enrollment-live-policy.v2\n"
        "protocol_version: speaker_enrollment_live_v2\n"
        "selection_algorithm_version: speaker-enrollment-live-selection.v2\n"
        "seed: 3800\n"
        "probe_durations_sec: [0.5, 1.0, 2.0]\n",
        encoding="utf-8",
    )

    candidates = [
        ("calibration_winner", "1", 0.91, 0.01, 0.01, 0.00),
        ("second_mode", "5", 0.84, 0.00, 0.00, 0.10),
        # This candidate has the best held-out score but worse calibration evidence.
        ("evaluation_only_winner", "10", 0.20, 0.00, 0.00, 1.00),
    ]
    for config_id, count, acceptance, wrong_name, fpir, evaluation_score in candidates:
        path = result_base / backend / "phase_a_enrollment_count" / config_id / "configuration_result.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "backend_id": backend,
                    "configuration": {
                        "configuration_id": config_id,
                        "enrollment_basis": "natural_utterance_count",
                        "enrollment_count": count,
                        "enrollment_target_audio_sec": "",
                        "aggregation_method": "normalized_mean",
                    },
                    "selected_open_set_policy": {
                        "calibration_known_correct_acceptance": acceptance,
                        "calibration_known_wrong_name_rate": wrong_name,
                        "calibration_fpir": fpir,
                        "evaluation_used_for_selection": False,
                    },
                    "metrics": {"tpir": {"value": evaluation_score}},
                    "representation_cost": {"estimated_bytes_per_speaker_float32": 1000},
                }
            ),
            encoding="utf-8",
        )
    for duration in (0.5, 1.0, 2.0):
        path = result_base / backend / "phase_d_probe_duration" / str(duration) / "configuration_result.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "configuration": {"probe_target_audio_sec": duration},
                }
            ),
            encoding="utf-8",
        )

    output_path = tmp_path / "automatic_gate.yaml"
    gate = build_automatic_joint_gate(protocol_root, result_base, backend, output_path)

    assert gate["enrollment_configuration_ids"] == ["calibration_winner", "second_mode"]
    assert gate["probe_durations_sec"] == [0.5, 1.0, 2.0]
    assert gate["evaluation_metrics_used_for_selection"] is False
    assert "evaluation_only_winner" not in gate["enrollment_configuration_ids"]
    assert output_path.is_file()


def test_backend_specific_threshold_and_cache_identities(tables):
    assert threshold_artifact_id("a" * 64, "c" * 64) != threshold_artifact_id("b" * 64, "c" * 64)
    assert threshold_artifact_id("a" * 64, "c" * 64) != threshold_artifact_id("a" * 64, "d" * 64)
    row = tables["audio_slices"][0]
    first = cache_item_identity(row, "runtime-a")
    assert first != cache_item_identity(row, "runtime-b")
    changed = dict(row)
    changed["end_sec"] = f"{float(row['end_sec']) + 0.001:.6f}"
    assert first != cache_item_identity(changed, "runtime-a")


def test_manifest_construction_is_deterministic():
    with (DEFAULT_SOURCE_PROTOCOL_ROOT / "source_selection.tsv").open("r", encoding="utf-8", newline="") as handle:
        source_rows = [dict(row) for row in csv.DictReader(handle, delimiter="\t")]
    config = load_config(DEFAULT_CONFIG_PATH)
    protocol_id = json.loads((DEFAULT_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8"))["protocol_id"]
    first = _build_protocol_rows(source_rows, config, protocol_id)
    second = _build_protocol_rows(source_rows, config, protocol_id)
    def identity(value):
        return canonical_sha256(
            {
                "slices": [row["slice_id"] for row in value["audio_slices"]],
                "sets": [row["selection_id"] for row in value["enrollment_sets"]],
                "configs": [row["configuration_id"] for row in value["configurations"]],
            }
        )
    assert identity(first) == identity(second)


@pytest.mark.parametrize("action", ["Plan", "Validate"])
def test_runner_plan_and_validate(action):
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(WRAPPER),
            "-Action",
            action,
            "-Phase",
            "EnrollmentCount",
        ],
        cwd=TOOL_ROOT.parents[1],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    if action == "Plan":
        assert '"model_inference_performed": false' in completed.stdout
    else:
        assert '"valid": true' in completed.stdout
