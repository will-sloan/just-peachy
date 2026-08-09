from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.campaign_analysis.analysis import analyze_campaign
from app.campaign_analysis.contracts import (
    AnalysisContractError,
    load_registries,
    plot_definitions,
    table_definitions,
)
from app.campaign_analysis.index import build_analysis_manifest, validate_analysis_manifest
from app.campaign_analysis.release import evaluate_release_gates
from app.campaign_analysis.statistics import benjamini_hochberg, paired_comparison
from app.campaign_exchange.execution import prepare_worker_campaign_copy
from app.campaign_exchange.merge import merge_worker_results
from app.cli.main import build_parser
from tests.automated_evaluation.test_stage6_campaign_exchange import (
    CREATED,
    _assignment,
    _execute,
    _export,
    _plan,
    _scenarios,
)


def _two_worker_campaign(tmp_path: Path, count: int = 4) -> Path:
    root = _plan(tmp_path, _scenarios(count), campaign_id="campaign_stage12test")
    first, first_path = _assignment(root, "amir", partition_index=0, partition_count=2)
    second, second_path = _assignment(root, "friend", partition_index=1, partition_count=2)
    friend_root = tmp_path / "friend_checkout" / root.name
    prepare_worker_campaign_copy(root, second_path, friend_root)
    friend_assignment = friend_root / "worker_assignments" / second_path.name
    _execute(root, "amir", first["scenario_ids"])
    _execute(friend_root, "friend", second["scenario_ids"])
    transfer_a = tmp_path / "transfer_a"
    transfer_b = tmp_path / "transfer_b"
    _export(root, first, first_path, transfer_a, machine="A", package_version="1.0")
    _export(friend_root, second, friend_assignment, transfer_b, machine="B", package_version="1.1")
    merge_worker_results(root, [transfer_a, transfer_b], created_at=CREATED)
    return root


def _synthetic_evidence() -> dict[str, object]:
    return {
        "evidence": {
            "two_worker_merge": True,
            "timeout_retry": True,
            "interruption_resume": True,
            "stop_request": True,
            "restart_recovery": True,
            "transfer_checksums": True,
            "long_path": True,
            "exact_reconciliation": True,
        }
    }


def test_registry_covers_required_metric_and_plot_contracts() -> None:
    registries = load_registries()
    names = {item["name"] for item in registries.metric_registry["metrics"]}
    assert {"micro_wer", "micro_cer", "embedding_eer", "diarization_der", "scenario_completion"} <= names
    plots = {item["id"] for item in plot_definitions(registries.plot_report_registry)}
    assert {
        "pareto_frontier",
        "exact_rir_heatmap",
        "native_condition",
        "speaker_score_distribution",
        "roc_det",
        "diarization_outcomes",
        "coverage_reconciliation",
        "qualitative_error",
    } <= plots
    assert {item["id"] for item in table_definitions(registries.plot_report_registry)} == {
        "scenario_index",
        "scenario_metric_values",
        "paired_comparisons",
        "failure_categories",
        "coverage_matrix",
        "repeated_finalist_variance",
    }


def test_full_two_worker_analysis_reconciles_and_reports_every_plot(tmp_path: Path) -> None:
    root = _two_worker_campaign(tmp_path)
    evidence = tmp_path / "synthetic_evidence.json"
    evidence.write_text(json.dumps(_synthetic_evidence()), encoding="utf-8")
    summary = analyze_campaign(root, prerequisite_evidence_path=evidence)
    assert summary["planned_scenario_count"] == 4
    assert summary["included_scenario_count"] == 4
    assert summary["release_status"] == "passed"
    manifest = validate_analysis_manifest(root / "analysis" / "analysis_manifest.json", campaign_root=root)
    assert [row["scenario_id"] for row in manifest["scenario_index"]] == json.loads((root / "campaign_manifest.json").read_text())["scenario_ids"]
    assert all(row["analysis_status"] == "included" for row in manifest["scenario_index"])
    plot_status = json.loads((root / "analysis" / "plot_status.json").read_text())
    assert len(plot_status["plots"]) == len(load_registries().plot_report_registry["plots"])
    assert {row["status"] for row in plot_status["plots"]} <= {"generated", "skipped"}
    report = json.loads((root / "analysis" / "report" / "campaign_report.json").read_text())
    assert report["excluded_and_gaps"] == []
    assert (root / "analysis" / "tables" / "scenario_metric_values.parquet").is_file()
    assert (root / "analysis" / "tables" / "scenario_index.csv").is_file()
    assert (root / "analysis" / "tables" / "repeated_finalist_variance.csv").is_file()
    assert (root / "analysis" / "analysis_checksums.json").is_file()
    assert (root / "analysis" / "contracts" / "metric_registry.v1.yaml").is_file()
    assert (root / "analysis" / "contracts" / "analysis_guide.md").is_file()


def test_analysis_manifest_is_byte_stable_for_unchanged_inputs(tmp_path: Path) -> None:
    root = _two_worker_campaign(tmp_path, count=2)
    first = build_analysis_manifest(root)
    payload = (root / "analysis" / "analysis_manifest.json").read_bytes()
    second = build_analysis_manifest(root)
    assert first["analysis_manifest_id"] == second["analysis_manifest_id"]
    assert payload == (root / "analysis" / "analysis_manifest.json").read_bytes()


def test_partial_merge_keeps_missing_scenarios_visible_and_blocks_release(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(3), campaign_id="campaign_stage12partial")
    assignment, assignment_path = _assignment(root, "amir")
    _execute(root, "amir", assignment["scenario_ids"][:1])
    transfer = tmp_path / "partial_transfer"
    _export(root, assignment, assignment_path, transfer, machine="A")
    merge_worker_results(root, [transfer], created_at=CREATED)
    manifest = build_analysis_manifest(root)
    statuses = [row["analysis_status"] for row in manifest["scenario_index"]]
    assert statuses.count("included") == 1
    assert statuses.count("missing") == 2
    coverage = {
        "summary": {"mandatory_unexpected_missing": 2},
    }
    release = evaluate_release_gates(manifest, coverage, load_registries().decision_policy, prerequisite_evidence=_synthetic_evidence())
    assert release["passed"] is False
    assert release["counts"]["missing_or_excluded"] == 2


def test_paired_cluster_bootstrap_is_deterministic_and_counts_missing(tmp_path: Path) -> None:
    baseline = pa.table(
        {
            "item_id": ["a", "b", "c", "d"],
            "speaker_id": ["s1", "s1", "s2", "s2"],
            "wer": [0.1, 0.2, 0.3, 0.4],
            "duration_sec": [1.0, 2.0, 3.0, 4.0],
        }
    )
    candidate = pa.table(
        {
            "item_id": ["a", "b", "c", "e"],
            "speaker_id": ["s1", "s1", "s2", "s3"],
            "wer": [0.05, 0.25, None, 0.8],
            "duration_sec": [1.0, 2.0, 3.0, 5.0],
        }
    )
    baseline_path = tmp_path / "baseline.parquet"
    candidate_path = tmp_path / "candidate.parquet"
    pq.write_table(baseline, baseline_path)
    pq.write_table(candidate, candidate_path)
    first = paired_comparison(baseline_path, candidate_path, metric="wer", baseline_scenario_id="scenario_a", candidate_scenario_id="scenario_b", bootstrap_repetitions=200)
    second = paired_comparison(baseline_path, candidate_path, metric="wer", baseline_scenario_id="scenario_a", candidate_scenario_id="scenario_b", bootstrap_repetitions=200)
    assert first == second
    assert first["shared_item_count"] == 3
    assert first["valid_pair_count"] == 2
    assert first["missing_or_invalid_pair_count"] == 1
    assert first["baseline_only_count"] == 1
    assert first["candidate_only_count"] == 1
    assert first["duration"]["valid_shared_total_sec"] == 3.0


def test_paired_comparison_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "items.parquet"
    pq.write_table(pa.table({"item_id": ["a", "a"], "wer": [0.1, 0.2]}), path)
    with pytest.raises(AnalysisContractError, match="duplicated"):
        paired_comparison(path, path, metric="wer", baseline_scenario_id="a", candidate_scenario_id="b", bootstrap_repetitions=100)


def test_multiple_comparison_adjustment_is_monotone() -> None:
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.2])
    assert adjusted[0] <= adjusted[2] <= adjusted[1] <= adjusted[3]
    assert all(0 <= value <= 1 for value in adjusted)


def test_manifest_validation_detects_hash_corruption(tmp_path: Path) -> None:
    root = _two_worker_campaign(tmp_path, count=2)
    build_analysis_manifest(root)
    path = root / "analysis" / "analysis_manifest.json"
    value = json.loads(path.read_text())
    value["status_counts"] = {"corrupt": 99}
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(AnalysisContractError, match="canonical content"):
        validate_analysis_manifest(path, campaign_root=root)


def test_stage12_cli_and_public_schemas_are_available() -> None:
    parser = build_parser()
    args = parser.parse_args(["analysis", "index", "--campaign-root", "campaign"])
    assert args.analysis_command == "index"
    schema_root = Path("configs/automated_evaluation/schemas")
    for name in (
        "analysis_manifest.v1.schema.json",
        "campaign_result_index.v1.schema.json",
        "campaign_coverage_matrix.v1.schema.json",
        "campaign_release_qualification.v1.schema.json",
        "campaign_plot_metadata.v1.schema.json",
    ):
        value = json.loads((schema_root / name).read_text(encoding="utf-8"))
        assert value["$schema"].endswith("2020-12/schema")
