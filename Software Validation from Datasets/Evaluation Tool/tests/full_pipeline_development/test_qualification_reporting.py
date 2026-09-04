from __future__ import annotations

import copy
import json
from pathlib import Path

from app.full_pipeline_development.qualification import (
    QUALIFICATION_RECORD_SCHEMA_VERSION,
    REQUIRED_CHECKS,
    build_qualification_bundle,
    build_qualification_plan,
    validate_qualification_bundle,
)
from app.full_pipeline_development.reporting import (
    COMPACT_ZIP_NAME,
    collect_development_report,
    publish_development_report,
)
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    sha256_bytes,
    sha256_file,
)
from app.full_pipeline_evaluation.metrics import METRIC_CATALOG
from app.full_pipeline_evaluation.planning import matrix


def _qualification(tmp_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    plan = build_qualification_plan()
    records = []
    for expected in plan["records"]:
        evidence = tmp_path / "evidence" / f"{expected['pipeline_id']}.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text('{"status":"PASS"}\n', encoding="utf-8")
        digest = sha256_file(evidence)
        ref = {"path": evidence.relative_to(tmp_path).as_posix(), "sha256": digest}
        checks = {
            name: {
                "status": "PASS",
                "expected_contract_sha256": expected["expected_contract_sha256"],
                "evidence_refs": [ref],
            }
            for name in REQUIRED_CHECKS
        }
        minimum = expected["expected_contract"]["minimum_duration"]
        checks["minimum_duration"].update(
            {
                "documented_minimum_duration_sec": minimum[
                    "documented_minimum_duration_sec"
                ],
                "technical_checkpoint_duration_sec": 0.5,
                "checkpoint_outcome": minimum["expected_checkpoint_outcome"],
                "full_pipeline_invalidated_by_checkpoint": False,
            }
        )
        semantic = "9" * 64
        events = "8" * 64
        checks["cold_vs_shared_equivalence"].update(
            {
                "semantically_equivalent": True,
                "cold_execution_origin": "primary_computed",
                "shared_execution_origin": "shared_worker_pool",
                "cold_semantic_result_sha256": semantic,
                "shared_semantic_result_sha256": semantic,
                "cold_event_sequence_sha256": events,
                "shared_event_sequence_sha256": events,
            }
        )
        for check in checks.values():
            check["evidence_sha256"] = sha256_bytes(canonical_json_bytes(check))
        records.append(
            {
                "schema_version": QUALIFICATION_RECORD_SCHEMA_VERSION,
                **{
                    field: copy.deepcopy(expected[field])
                    for field in (
                        "pipeline_id",
                        "aliases",
                        "frozen_anchor",
                        "split",
                        "protocol_id",
                        "development_identity_sha256",
                        "pipeline_config_sha256",
                        "expected_contract",
                        "expected_contract_sha256",
                    )
                },
                "qualification_status": "PASS",
                "evaluation_material_inspected": False,
                "actual_short_runtime_count": 1,
                "cold_execution_count": 1,
                "shared_execution_count": 1,
                "smoke_audio_duration_sec": max(
                    1.0, float(minimum["documented_minimum_duration_sec"])
                ),
                "smoke_case_id": f"smoke_{expected['pipeline_id']}",
                "source_audio_sha256": "7" * 64,
                "checks": checks,
            }
        )
    return plan, build_qualification_bundle(plan, records)


def test_qualification_plan_distinguishes_segmentation_asset_from_cache_contract() -> None:
    plan = build_qualification_plan()

    for row in plan["records"]:
        contract = row["expected_contract"]
        segmentation = contract["assets"]["segmentation"]
        assert segmentation["asset_id"] == "pyannote_segmentation_3_0"
        assert segmentation["runtime_component_id"] == "pyannote_segmentation_3_0"
        assert segmentation["cache_contract_id"] == (
            "pyannote_segmentation_3_0_shared_cache"
        )
        assert contract["segmentation_component_id"] == segmentation["asset_id"]
        assert contract["segmentation_cache_contract_id"] == segmentation[
            "cache_contract_id"
        ]
        assert len(segmentation["installed_tree_sha256"]) == 64


def _metric_documents() -> dict[str, object]:
    subviews: dict[str, dict[str, object]] = {}
    for metric_id, definition in METRIC_CATALOG.items():
        value = 0.0
        numerator = 0.0
        denominator = 1.0
        if metric_id == "wrong_known_time_sec":
            value = 1.0
        elif metric_id == "correctly_named_known_rate":
            value, numerator, denominator = 0.8, 8.0, 10.0
        elif metric_id == "fpir":
            value, numerator, denominator = 0.1, 1.0, 10.0
        elif metric_id == "speaker_attributed_wer":
            value, numerator, denominator = 0.2, 2.0, 10.0
        elif metric_id == "stable_name_latency_sec":
            value, numerator, denominator = 1.5, 3.0, 2.0
        elif metric_id == "total_rtf":
            value, numerator, denominator = 0.5, 5.0, 10.0
        elif metric_id == "peak_rss_bytes":
            value = 100_000_000.0
        category = definition.category
        subviews.setdefault(category, {"metrics": {}})["metrics"][metric_id] = {
            "status": "computed",
            "value": value,
            "numerator": numerator,
            "denominator": denominator,
            "reason": None,
        }
    return {"all": {"subviews": subviews}}


def _analysis_manifest(
    plan: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    jobs = []
    rows = []
    for pipeline_id in matrix().pipeline_ids:
        for mode in ("accuracy", "resources"):
            job_id = f"{pipeline_id}_{mode}"
            spec = {
                "job_id": job_id,
                "pipeline_id": pipeline_id,
                "protocol_id": "source_protocol",
                "source_key": "controlled_end_to_end",
                "split": "development",
                "measurement_mode": mode,
            }
            jobs.append(spec)
            rows.append(
                {
                    **spec,
                    "evaluation_material_inspected": False,
                    "result_checksums_sha256": "a" * 64,
                    "metric_documents": _metric_documents(),
                }
            )
    manifest = {
        "schema_version": "full-pipeline-evaluation-campaign.v1",
        "campaign_id": "campaign_fixture",
        "campaign_identity_sha256": "b" * 64,
        "development_identity": plan["development_identity_sha256"],
        "matrix_sha256": plan["matrix_sha256"],
        "runtime_config_sha256": plan["runtime_config_sha256"],
        "parallelism_policy": {"resource_measurement_jobs": 1},
        "jobs": jobs,
    }
    analysis = {
        "schema_version": "full-pipeline-evaluation-analysis.v1",
        "campaign_id": "campaign_fixture",
        "rows": rows,
    }
    return analysis, manifest


def _frozen_configs(root: Path) -> None:
    root.mkdir(parents=True)
    for pipeline_id in matrix().pipeline_ids:
        (root / f"{pipeline_id}.yaml").write_text(
            f"pipeline_id: {pipeline_id}\n", encoding="utf-8"
        )
    (root / "checksums.json").write_text(
        json.dumps(
            {
                "schema_version": "full-pipeline-development-config-checksums.v1",
                "entries": checksum_map(root),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_all_18_qualification_records_verify_files_and_short_checkpoint(
    tmp_path: Path,
) -> None:
    plan, bundle = _qualification(tmp_path)

    result = validate_qualification_bundle(
        bundle, plan=plan, evidence_root=tmp_path, verify_evidence_files=True
    )

    assert result["valid"], result["errors"]
    assert result["pipeline_count"] == 18
    assert result["all_six_anchor_pipelines_integrated_smoke_passed"] is True


def test_qualification_fails_closed_on_missing_check_and_evaluation_material(
    tmp_path: Path,
) -> None:
    plan, bundle = _qualification(tmp_path)
    broken = copy.deepcopy(bundle)
    broken["records"][0]["checks"].pop("clean_shutdown")
    broken["records"][0]["evaluation_case_ids"] = ["heldout"]
    broken = build_qualification_bundle(plan, broken["records"])

    result = validate_qualification_bundle(
        broken, plan=plan, evidence_root=tmp_path, verify_evidence_files=True
    )

    assert result["valid"] is False
    assert any("check coverage" in error for error in result["errors"])
    assert any("evaluation evidence" in error for error in result["errors"])


def test_report_has_exact_outputs_deterministic_zip_and_no_winner(tmp_path: Path) -> None:
    plan, bundle = _qualification(tmp_path)
    analysis, manifest = _analysis_manifest(plan)
    configs = tmp_path / "source_configs"
    _frozen_configs(configs)
    output = tmp_path / "report"

    result = publish_development_report(
        analysis_index=analysis,
        campaign_manifest=manifest,
        qualification_bundle=bundle,
        qualification_plan=plan,
        qualification_evidence_root=tmp_path,
        frozen_config_root=configs,
        output_root=output,
    )
    first_zip_sha = result["compact_zip_sha256"]
    collected = collect_development_report(output)

    assert result["pipeline_count"] == 18
    assert result["mandatory_anchor_count"] == 6
    assert result["additional_challenger_count"] <= 2
    assert result["production_winner_selected"] is False
    assert collected["compact_zip_sha256"] == first_zip_sha
    assert (output / COMPACT_ZIP_NAME).is_file()
    for relative in (
        "development_matrix.csv",
        "development_summary.csv",
        "extended_set.yaml",
        "development_report.md",
        "metric_guide.md",
        "failure_inventory.csv",
        "resource_spot_checks.csv",
        "development_analysis.json",
        "checksums.json",
    ):
        assert (output / relative).is_file()
    assert len(list((output / "frozen_pipeline_configs").glob("*.yaml"))) == 18
    assert "Production winner: none" in (output / "development_report.md").read_text(
        encoding="utf-8"
    )
