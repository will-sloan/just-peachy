from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess

import pytest

from app.benchmark_contracts.canonical import canonical_sha256
from app.speaker_enrollment.evaluation import (
    duration_weighted_mean,
    normalized_mean,
    score_templates,
    threshold_artifact_id,
)
from app.speaker_enrollment.extraction import cache_item_identity
from app.speaker_enrollment.protocol import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROTOCOL_ROOT,
    DEFAULT_SOURCE_PROTOCOL_ROOT,
    _build_protocol_rows,
    audio_slice_id,
    load_config,
    load_protocol_tables,
)


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
