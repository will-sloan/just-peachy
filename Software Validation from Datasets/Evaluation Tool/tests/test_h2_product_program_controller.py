from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace

import pytest

from app.full_pipeline.product_modes import H2RuntimeTuning
from app.full_pipeline_evaluation.store import EvaluationStateStore
from app.h2_product_program import controller
from app.h2_product_program import cli as h2_cli
from app.h2_product_program.contracts import H2Job
from app.h2_product_program.execution import RUNTIME_KINDS
from app.h2_product_program.execution import run_runtime_job
from app.h2_product_program.execution import runtime_implementation_identity
from app.h2_product_program.io import read_json, write_json_atomic
from app.h2_product_program.planning import (
    build_job_manifest,
    build_protocol_manifest,
    default_paths,
)
from app.h2_product_program.promotion import select_promotions


def _paths(tmp_path: Path):
    return default_paths(
        workspace=tmp_path / "workspace",
        results_root=tmp_path / "results",
        summary_root=tmp_path / "summaries",
    )


def test_superseded_evidence_tracks_configured_prior_version() -> None:
    root = Path("C:/evaluation")
    evidence = controller._superseded_h2_evidence(
        {"supersedes_program_id": "h2_complete_product_pipeline_program_v9"},
        root,
    )

    assert "superseded_h2_v9_program_state" in evidence
    assert evidence["superseded_h2_v9_program_state"] == (
        root / "automated_runs/h2_complete_product_pipeline_v9/program_state.json"
    )
    assert "superseded_h2_v8_program_state" not in evidence


def test_superseded_evidence_binds_optional_v9_stop_receipt(tmp_path: Path) -> None:
    prior = tmp_path / "automated_runs/h2_complete_product_pipeline_v9"
    prior.mkdir(parents=True)
    stop_request = prior / "stop_request.json"
    stop_request.write_text('{"status":"STOP_REQUESTED"}', encoding="utf-8")
    supersession = prior / "supersession_receipt.json"
    supersession.write_text('{"status":"SUPERSEDED"}', encoding="utf-8")

    evidence = controller._superseded_h2_evidence(
        {"supersedes_program_id": "h2_complete_product_pipeline_program_v9"},
        tmp_path,
    )

    assert evidence["superseded_h2_v9_stop_request"] == stop_request
    assert evidence["superseded_h2_v9_supersession_receipt"] == supersession


def test_runtime_identity_binds_complete_app_and_arm64_bundle() -> None:
    identity = runtime_implementation_identity()

    assert identity["schema_version"] == "h2-runtime-implementation-identity.v2"
    assert set(identity["components"]) >= {
        "complete_application_source_tree",
        "h2_arm64_deployment_bundle",
        "h2_controller",
        "streaming_runtime",
        "evaluation_and_scorers",
    }
    assert all(
        len(identity["components"][name]) == 64
        for name in (
            "complete_application_source_tree",
            "h2_arm64_deployment_bundle",
        )
    )


def test_prepare_is_restart_safe_and_h2_only(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    first = controller.prepare(paths)
    second = controller.prepare(paths)
    checked = controller.validate(paths, verify_results=False)

    manifest = read_json(paths.jobs_path)
    expected_runtime = sum(
        row["job_kind"] in RUNTIME_KINDS and row["split"] != "evaluation"
        for row in manifest["jobs"]
    )
    assert first["job_count"] == len(manifest["jobs"]) == 103
    assert second["runtime_queue"]["queue"]["unchanged"] == expected_runtime
    assert checked["valid"] is True
    assert {row["pipeline_id"] for row in manifest["jobs"]} <= {
        "fullpipe_v1_ag_dr_ir",
        "fullpipe_v1_ao_dr_ir",
        "NOT_APPLICABLE",
    }


def test_bounded_run_completes_only_truthful_evidence_audit(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    controller.prepare(paths)
    result = controller.run(paths, maximum_jobs=1)
    state = read_json(paths.state_path)
    manifest = build_job_manifest(build_protocol_manifest(paths))
    audit_job = next(
        row for row in manifest["jobs"] if row["job_kind"] == "evidence_audit"
    )

    assert result["status"] == "PAUSED"
    assert state["jobs"][audit_job["job_id"]]["state"] == "COMPLETE"
    assert state["jobs"][audit_job["job_id"]]["result_sha256"]
    assert sum(row["state"] == "COMPLETE" for row in state["jobs"].values()) == 1


def test_unimplemented_research_handler_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.results_root.mkdir(parents=True)
    job = H2Job(
        job_id="blocked",
        phase_index=3,
        phase_name="IDENTITY_POLICY_FRONTIER",
        job_kind="policy_replay",
        split="development",
        pipeline_id="fullpipe_v1_ag_dr_ir",
        configuration_id="GRID",
        mode="H2_SESSION_MEMORY_ENHANCED",
        case_ids=("case",),
        audio_duration_sec=1.0,
        runtime_tuning={},
    )
    result = controller._blocked_job_result(paths, job, "not implemented")
    payload = read_json(Path(result["result_path"]))

    assert result["state"] == "failed"
    assert payload["marked_complete"] is False
    assert payload["scientific_work_performed"] is False


def test_next_job_preserves_same_phase_manifest_order_across_restart() -> None:
    jobs = tuple(
        H2Job(
            job_id=job_id,
            phase_index=6,
            phase_name="PORTABILITY_RESOURCE",
            job_kind=job_kind,
            split="none",
            pipeline_id="NOT_APPLICABLE",
            configuration_id=configuration_id,
            mode="NOT_APPLICABLE",
            case_ids=(),
            audio_duration_sec=0.0,
            runtime_tuning={},
        )
        for job_id, job_kind, configuration_id in (
            ("export", "onnx_export", "H2_PORTABLE_ONNX_FP32_EXPORT"),
            (
                "parity",
                "onnx_parity",
                "H2_PORTABLE_ONNX_FP32_FROZEN_FIXTURE_PARITY",
            ),
            ("package", "linux_portability", "H2_LINUX_ARM64_PACKAGE"),
        )
    )
    state: dict[str, object] = {
        "jobs": {job.job_id: {"state": "PENDING"} for job in jobs}
    }

    assert controller._next_job(state, jobs) == jobs[0]
    state["jobs"]["export"]["state"] = "COMPLETE"  # type: ignore[index]
    assert controller._next_job(state, jobs) == jobs[1]
    state["jobs"]["parity"]["state"] = "COMPLETE"  # type: ignore[index]
    assert controller._next_job(state, jobs) == jobs[2]


def test_job_manifest_is_topological_and_collection_is_terminal(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    manifest = build_job_manifest(build_protocol_manifest(paths))
    jobs = manifest["jobs"]
    positions = {row["job_id"]: index for index, row in enumerate(jobs)}

    assert len(positions) == len(jobs) == 103
    for row in jobs:
        assert all(
            dependency in positions
            and positions[dependency] < positions[row["job_id"]]
            for dependency in row["dependencies"]
        )

    freeze = next(row for row in jobs if row["job_kind"] == "freeze")
    heldout = [row for row in jobs if row["split"] == "evaluation"]
    assert heldout
    assert all(freeze["job_id"] in row["dependencies"] for row in heldout)
    assert jobs[-1]["job_kind"] == "collection"
    assert jobs[-1]["phase_index"] == 7


def test_development_promotion_uses_pareto_without_composite(tmp_path: Path) -> None:
    jobs = tuple(
        H2Job(
            job_id=f"job_{name}",
            phase_index=1,
            phase_name="SEGMENTATION_FRONTIER",
            job_kind="successive_halving_runtime",
            split="development",
            pipeline_id="fullpipe_v1_ag_dr_ir",
            configuration_id=f"{name}_SMALL",
            mode="H2_SESSION_MEMORY_ENHANCED",
            case_ids=("case",),
            audio_duration_sec=1.0,
            runtime_tuning=H2RuntimeTuning().to_jsonable(),
        )
        for name in ("SAFE", "UNSAFE")
    )
    for job, wrong, stranger in ((jobs[0], 0.0, 0.0), (jobs[1], 1.0, 0.0)):
        root = tmp_path / "jobs" / job.job_id / "result" / "metrics"
        write_json_atomic(
            root / "identity.json",
            {
                "subviews": {
                    "identity": {
                        "metrics": {
                            "wrong_known_time_sec": {
                                "status": "computed",
                                "value": wrong,
                            },
                            "stranger_false_known_time_sec": {
                                "status": "computed",
                                "value": stranger,
                            },
                        }
                    }
                }
            },
        )
        write_json_atomic(
            root / "diarization.json",
            {
                "subviews": {
                    "diarization": {
                        "metrics": {
                            metric_id: {"status": "computed", "value": wrong}
                            for metric_id in controller.REQUIRED_SHORT_TURN_METRICS
                        }
                    }
                }
            },
        )
    decision = select_promotions(jobs, results_root=tmp_path, maximum=1)

    assert decision["selected_candidates"] == ["SAFE"]
    assert decision["weighted_composite_used"] is False
    assert decision["evaluation_material_inspected"] is False


def test_post_freeze_overlay_binds_selected_tuning(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    protocol = build_protocol_manifest(paths)
    manifest = build_job_manifest(protocol)
    jobs = tuple(H2Job.from_jsonable(row) for row in manifest["jobs"])
    selected = H2RuntimeTuning(score_threshold=0.61)
    freeze = {
        "schema_version": "h2-frozen-development-policy.v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol["protocol_sha256"],
        "job_manifest_sha256": manifest["job_manifest_sha256"],
        "freeze_identity_sha256": "f" * 64,
        "runtime_implementation_identity_sha256": (
            controller.runtime_implementation_identity()["identity_sha256"]
        ),
        "selected_runtime": {"runtime_tuning": selected.to_jsonable()},
    }
    paths.workspace.mkdir(parents=True)
    paths.results_root.mkdir(parents=True)
    paths.summary_root.mkdir(parents=True)
    write_json_atomic(paths.protocol_path, protocol)
    result = controller._prepare_heldout_execution_queue(paths, jobs, freeze)
    overlay = result["manifest"]
    execution_jobs = [H2Job.from_jsonable(row) for row in overlay["jobs"]]

    assert len(execution_jobs) == 7
    assert all(
        H2RuntimeTuning.from_mapping(job.runtime_tuning).score_threshold == 0.61
        for job in execution_jobs
    )
    assert all(job.job_id.startswith("h2eval_") for job in execution_jobs)
    store = EvaluationStateStore(
        paths.workspace / controller.HELDOUT_QUEUE_DIRECTORY / "campaign.sqlite3"
    )
    assert {row.spec.job_id for row in store.list_jobs()} == {
        job.job_id for job in execution_jobs
    }


def test_dynamic_execution_identity_binds_private_score_diagnostic_flag() -> None:
    inputs = {
        "logical_job_identity_sha256": "1" * 64,
        "selection_sha256": "2" * 64,
        "runtime_tuning_identity_sha256": "3" * 64,
        "runtime_implementation_identity_sha256": "4" * 64,
    }
    ordinary = controller._dynamic_execution_seed(
        **inputs, emit_identity_score_diagnostics=False
    )
    diagnostic = controller._dynamic_execution_seed(
        **inputs, emit_identity_score_diagnostics=True
    )

    assert ordinary != diagnostic
    assert ordinary == controller._dynamic_execution_seed(
        **inputs, emit_identity_score_diagnostics=False
    )


def test_freeze_merges_checksum_bound_handler_selected_axes(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    baseline = H2RuntimeTuning(score_threshold=0.52)
    baseline_job = H2Job(
        job_id="baseline",
        phase_index=0,
        phase_name="AUDIT_BASELINE",
        job_kind="runtime_accuracy",
        split="development",
        pipeline_id="fullpipe_v1_ag_dr_ir",
        configuration_id="H2_BASELINE_REFERENCE",
        mode="H2_SESSION_MEMORY_ENHANCED",
        case_ids=("case",),
        audio_duration_sec=1.0,
        runtime_tuning=baseline.to_jsonable(),
    )
    policy_job = H2Job(
        job_id="policy",
        phase_index=3,
        phase_name="IDENTITY_POLICY_FRONTIER",
        job_kind="policy_replay",
        split="development",
        pipeline_id="fullpipe_v1_ag_dr_ir",
        configuration_id="H2_IDENTITY_POLICY_GRID",
        mode="H2_SESSION_MEMORY_ENHANCED",
        case_ids=("case",),
        audio_duration_sec=1.0,
        runtime_tuning=baseline.to_jsonable(),
    )
    result_path = paths.results_root / "policy_selection.json"
    write_json_atomic(
        result_path,
        {
            "development_only_selection": True,
            "evaluation_material_inspected": False,
            "promotion_eligible": True,
            "selected_runtime_axes": ["score_threshold", "margin_threshold"],
            "selected_runtime_tuning": {
                "score_threshold": 0.58,
                "margin_threshold": 0.04,
            },
        },
    )
    state = {
        "jobs": {
            "baseline": {"state": "COMPLETE", "result_sha256": "b" * 64},
            "policy": {
                "state": "COMPLETE",
                "result_path": str(result_path),
                "result_sha256": controller.sha256_file(result_path),
            },
        }
    }
    selected = controller._selected_runtime_configuration(
        paths, state, (baseline_job, policy_job)
    )
    tuning = H2RuntimeTuning.from_mapping(selected["runtime_tuning"])

    assert tuning.score_threshold == 0.58
    assert tuning.margin_threshold == 0.04
    assert selected["selected_axis_provenance"]["score_threshold"]["job_id"] == "policy"


def test_enrollment_binding_preserves_historical_policy_without_gallery_proof(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    policy_path = tmp_path / "historical_redim_policy.yaml"
    policy_path.write_text(
        "\n".join(
            (
                "policy_id: historical-redim",
                "identity_backend_id: redimnet2_b2_speaker_embedding",
                "enrollment_utterance_count: 3",
                "enrollment_total_target_sec: 10.0",
                "clip_selection: first_three_frozen_reserved_clean_diverse_clips",
                "aggregation_method: multi_template_max",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    selected_unsigned = {
        "selection_label": "INTEGRATED_SELECTED_CELL",
        "selection_uses_development_only": True,
        "evaluation_material_inspected": False,
        "live_identity_threshold_altered_by_handler": False,
        "panel_sha256": "p" * 64,
        "backend_id": "redimnet2_b2_speaker_embedding",
        "backend_identity_hash": "b" * 64,
        "utterances": 5,
        "total_duration_sec": 20.0,
        "sessions": "varied",
        "aggregation": "frozen_redim_multi_template",
        "quality_filter": "quality_filtered",
        "score_definition": "maximum_probe_to_retained_template_cosine",
        "score_threshold": 0.7,
        "margin_threshold": 0.03,
    }
    selected = {
        **selected_unsigned,
        "policy_provenance_sha256": controller.canonical_sha256(selected_unsigned),
    }
    result_path = paths.results_root / "enrollment.json"
    write_json_atomic(
        result_path,
        {
            "selected_enrollment_policy": selected,
            "full_gallery_policy_compatibility_proven": False,
            "integrated_recommendation_runtime_activation_eligible": False,
            "historical_evidence": {
                "frozen_policy_path": str(policy_path),
                "frozen_policy_sha256": controller.sha256_file(policy_path),
            },
        },
    )
    job = H2Job(
        job_id="enrollment",
        phase_index=3,
        phase_name="ENROLLMENT",
        job_kind="integrated_enrollment",
        split="development",
        pipeline_id="fullpipe_v1_ag_dr_ir",
        configuration_id="H2_ENROLLMENT",
        mode="H2_SESSION_MEMORY_ENHANCED",
        case_ids=(),
        audio_duration_sec=0.0,
        runtime_tuning={},
    )
    state = {
        "jobs": {
            job.job_id: {
                "state": "COMPLETE",
                "result_path": str(result_path),
                "result_sha256": controller.sha256_file(result_path),
            }
        }
    }

    binding = controller._selected_enrollment_policy_binding(state, job)

    assert binding["effective_policy"]["utterance_count"] == 3
    assert binding["effective_policy"]["application_aggregation"] == (
        "multi_template_max"
    )
    assert binding["integrated_study_recommendation"]["utterance_count"] == 5
    assert binding["compatibility_proof"]["runtime_activation_eligible"] is False

    unsafe = read_json(result_path)
    unsafe["full_gallery_policy_compatibility_proven"] = True
    write_json_atomic(result_path, unsafe)
    state["jobs"][job.job_id]["result_sha256"] = controller.sha256_file(result_path)
    with pytest.raises(Exception, match="unsupported full-gallery compatibility"):
        controller._selected_enrollment_policy_binding(state, job)


def test_memory_selection_propagates_only_exact_executable_axes(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    planned = build_job_manifest(build_protocol_manifest(paths))
    baseline_job = next(
        H2Job.from_jsonable(row)
        for row in planned["jobs"]
        if row["configuration_id"] == "H2_BASELINE_REFERENCE"
    )
    assert baseline_job.runtime_tuning["schema_version"] == "h2-runtime-tuning.v1"
    memory_job = H2Job(
        job_id="memory",
        phase_index=4,
        phase_name="MEMORY_HYSTERESIS",
        job_kind="memory_policy_replay",
        split="development",
        pipeline_id="fullpipe_v1_ag_dr_ir",
        configuration_id="MEMORY",
        mode="H2_SESSION_MEMORY_ENHANCED",
        case_ids=("case",),
        audio_duration_sec=1.0,
        runtime_tuning=baseline_job.runtime_tuning,
    )
    result_path = paths.results_root / "memory_selection.json"
    axes = {
        "hysteresis_policy": "H1_TWO_CONFIRM_TWO_RELEASE",
        "consecutive_passes_to_confirm": 2,
        "consecutive_failures_to_release": 2,
        "hysteresis": 0.02,
        "identity_expiry_sec": 60.0,
        "identity_expiry_mode": "source_clock",
        "memory_level": "M3_SHORT_TURN",
    }
    write_json_atomic(
        result_path,
        {
            "development_only_selection": True,
            "evaluation_material_inspected": False,
            "promotion_eligible": True,
            "selected_runtime_axes": list(axes),
            "selected_runtime_tuning": axes,
        },
    )
    state = {
        "jobs": {
            baseline_job.job_id: {
                "state": "COMPLETE",
                "result_sha256": "b" * 64,
            },
            "memory": {
                "state": "COMPLETE",
                "result_path": str(result_path),
                "result_sha256": controller.sha256_file(result_path),
            },
        }
    }
    selected = controller._selected_runtime_configuration(
        paths, state, (baseline_job, memory_job)
    )
    tuning = H2RuntimeTuning.from_mapping(selected["runtime_tuning"])

    assert tuning.hysteresis_policy == "H1_TWO_CONFIRM_TWO_RELEASE"
    assert tuning.consecutive_passes_to_confirm == 2
    assert tuning.consecutive_failures_to_release == 2
    assert tuning.identity_expiry_mode == "source_clock"
    assert tuning.memory_level == "M3_SHORT_TURN"
    assert selected["runtime_tuning"]["schema_version"] == "h2-runtime-tuning.v2"
    assert set(controller.HANDLER_SELECTED_AXES["memory_policy_replay"]) == set(axes)


def test_all_development_integration_partition_is_source_and_speaker_disjoint() -> None:
    protocol = build_protocol_manifest(default_paths())
    development = protocol["panels"]["development"]
    panel = development["all"]
    eligible_panel = development["integration_eligible"]
    partition = development["integration_partition"]

    assert panel["case_count"] == 807
    assert partition["schema_version"] == "h2-development-integration-partition.v2"
    assert partition["original_source_count"] == 96
    assert partition["independent_source_count"] == (
        partition["calibration_source_count"] + partition["selection_source_count"]
    )
    assert partition["original_source_count"] == (
        partition["independent_source_count"]
        + partition["excluded_cross_cohort_source_count"]
    )
    assert partition["calibration_case_count"] >= 200
    assert partition["selection_case_count"] >= 200
    calibration_cases = set(partition["calibration_case_ids"])
    selection_cases = set(partition["selection_case_ids"])
    excluded_cases = set(partition["excluded_cross_cohort_case_ids"])
    assert calibration_cases.isdisjoint(selection_cases)
    assert calibration_cases.isdisjoint(excluded_cases)
    assert selection_cases.isdisjoint(excluded_cases)
    assert len(calibration_cases) + len(selection_cases) + len(excluded_cases) == 807
    assert set(partition["calibration_speaker_ids"]).isdisjoint(
        partition["selection_speaker_ids"]
    )
    assert partition["speaker_overlap_count"] == 0
    assert partition["source_overlap_count"] == 0
    assert partition["excluded_cases_used_for_calibration_or_selection"] is False
    assert partition["prediction_or_metric_inputs_used"] is False
    assert partition["reference_speaker_identity_metadata_used"] is True
    assert partition["reference_transcript_or_audio_content_used"] is False
    assert partition["speaker_disjoint_scope"] == "probe_audio_speakers"
    assert partition["fixed_enrollment_gallery_shared_between_roles"] is True
    assert eligible_panel["case_count"] == (
        partition["calibration_case_count"] + partition["selection_case_count"]
    )
    assert eligible_panel["unique_audio_count"] == partition["independent_source_count"]

    manifest = build_job_manifest(protocol)
    integration_job = next(
        row
        for row in manifest["jobs"]
        if row["configuration_id"] == "H2_POST_PROMOTION_INTEGRATION"
    )
    assert set(integration_job["case_ids"]) == calibration_cases | selection_cases
    assert set(integration_job["case_ids"]).isdisjoint(excluded_cases)


def test_phase2_declares_bounded_clustering_attach_and_matched_serial_resources() -> (
    None
):
    protocol = build_protocol_manifest(default_paths())
    manifest = build_job_manifest(protocol)
    phase2 = [row for row in manifest["jobs"] if row["phase_index"] == 2]
    small = {
        row["configuration_id"]
        for row in phase2
        if row["job_kind"] == "successive_halving_runtime"
        and row["configuration_id"].endswith("_SMALL")
    }
    resources = {
        row["configuration_id"]: row
        for row in phase2
        if row["job_kind"] == "resource_runtime"
    }

    assert {
        "R2_ONE_SHARED_MODEL_SMALL",
        "C1_CLUSTER_THRESHOLD_025_SMALL",
        "C2_CLUSTER_THRESHOLD_045_SMALL",
        "C3_SHORT_ATTACH_GAP_025_SMALL",
        "C4_SHORT_ATTACH_GAP_075_SMALL",
    } <= small
    assert "C0_CLUSTER_ATTACH_HISTORICAL_SMALL" not in small
    assert "W150_H075_SMALL" not in small
    phase2_small_rows = [
        row
        for row in phase2
        if row["job_kind"] == "successive_halving_runtime"
        and row["configuration_id"].endswith("_SMALL")
    ]
    tuning_identities = {
        controller.canonical_sha256(row["runtime_tuning"]) for row in phase2_small_rows
    }
    assert len(tuning_identities) == len(phase2_small_rows)
    r1_accuracy = [
        row
        for row in phase2
        if row["configuration_id"] == "R1_TWO_INDEPENDENT_MODELS_SMALL"
    ]
    assert len(r1_accuracy) == 1
    assert r1_accuracy[0]["job_kind"] == "runtime_accuracy"
    assert set(resources) == {
        "R1_TWO_INDEPENDENT_MODELS_MATCHED_SERIAL_RESOURCE",
        "R2_ONE_SHARED_MODEL_MATCHED_SERIAL_RESOURCE",
    }
    assert all(row["serial"] is True for row in resources.values())
    assert {
        row["runtime_tuning"]["redim_execution_strategy"] for row in resources.values()
    } == {"R1_TWO_INDEPENDENT_MODELS", "R2_ONE_SHARED_MODEL"}
    assert manifest["successive_halving"]["phase_2"] == {
        "small_candidates": 10,
        "medium_max": 4,
        "full_max": 2,
        "fixed_execution_strategy": "R2_ONE_SHARED_MODEL",
        "duplicate_executable_tunings_allowed": False,
        "r1_accuracy_reference_outside_promotion": True,
    }


def test_runtime_boundary_stop_has_direct_durable_file_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    protocol = build_protocol_manifest(paths)
    manifest = build_job_manifest(protocol)
    job = next(
        H2Job.from_jsonable(row)
        for row in manifest["jobs"]
        if row["configuration_id"] == "R1_TWO_INDEPENDENT_MODELS_SMALL"
    )
    paths.workspace.mkdir(parents=True)
    paths.stop_path.write_text("{}", encoding="utf-8")
    observed: dict[str, object] = {}

    class _Queued:
        spec = SimpleNamespace(
            job_id=job.job_id,
            result_relative_path=f"jobs/{job.job_id}/result",
        )
        completed_cases = 0
        completed_audio_sec = 0.0
        cache_hits = 0
        result_sha256 = None

    class _Store:
        def __init__(self, _path: Path) -> None:
            pass

        def list_jobs(self):
            return (_Queued(),)

    def fake_run_one(_workspace, _manifest, spec, executor, _lock, _event):
        def fake_execute(
            _spec,
            _cases,
            _output,
            _progress,
            stop_requested,
            **_kwargs,
        ):
            observed["stop"] = stop_requested()
            return {"state": "stopped", "completed_cases": 0}

        monkeypatch.setattr(
            "app.h2_product_program.execution.execute_evaluation_job",
            fake_execute,
        )
        return executor(spec, (), tmp_path / "result", lambda **_k: None, lambda: False)

    monkeypatch.setattr("app.h2_product_program.execution.EvaluationStateStore", _Store)
    monkeypatch.setattr(
        "app.h2_product_program.execution.load_cases_for_job", lambda *_a, **_k: ()
    )
    monkeypatch.setattr(
        "app.h2_product_program.execution.evaluation_controller._run_one",
        fake_run_one,
    )

    result = run_runtime_job(
        paths,
        job,
        protocol=protocol,
        stop_event=threading.Event(),
        progress_lock=threading.Lock(),
    )

    assert observed["stop"] is True
    assert result["state"] == "stopped"


def test_app_validation_is_scheduled_before_freeze_and_checksum_validated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    protocol = build_protocol_manifest(paths)
    manifest = build_job_manifest(protocol)
    jobs = tuple(H2Job.from_jsonable(row) for row in manifest["jobs"])
    app_job = next(job for job in jobs if job.job_kind == "app_validation")
    freeze_job = next(job for job in jobs if job.job_kind == "freeze")

    assert app_job.phase_index == 6
    assert app_job.serial is True
    assert app_job.job_id in freeze_job.dependencies

    def passed(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        stdout = "19 passed in 1.00s\n" if "pytest" in command else ""
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(controller, "_run_app_validation_command", passed)
    selection_unsigned = {
        "schema_version": "h2-development-default-mode-selection.v1",
        "status": "COMPLETE",
        "development_only": True,
        "evaluation_material_inspected": False,
        "weighted_composite_used": False,
        "selected_default_mode": "H2_SESSION_MEMORY_ENHANCED",
    }
    selection = {
        **selection_unsigned,
        "selection_identity_sha256": controller.canonical_sha256(selection_unsigned),
    }
    tuning = H2RuntimeTuning()
    selected_runtime = {
        "runtime_tuning": tuning.to_jsonable(),
        "runtime_tuning_identity_sha256": tuning.identity_sha256,
    }
    monkeypatch.setattr(
        controller,
        "_select_development_default_mode",
        lambda *_args: selection,
    )
    monkeypatch.setattr(
        controller,
        "_selected_runtime_configuration",
        lambda *_args: selected_runtime,
    )
    state: dict[str, object] = {}
    result = controller._handle_app_validation(
        paths,
        app_job,
        protocol=protocol,
        state=state,
        jobs=jobs,
    )
    state_row = {
        "result_path": result["result_path"],
        "result_sha256": result["result_sha256"],
    }
    receipt = read_json(Path(str(result["result_path"])))

    assert result["state"] == "complete"
    assert receipt["schema_version"] == "h2-app-validation-result.v1"
    assert receipt["validation"] == {
        "status": "PASS",
        "passed_count": 19,
        "failed_count": 0,
        "python_compile_passed": True,
        "ruff_check_passed": True,
    }
    assert receipt["physical_microphone_performance_claimed"] is False
    assert (
        controller._validate_app_validation_result(
            paths,
            app_job,
            state_row,
            protocol=protocol,
            state=state,
            jobs=jobs,
        )
        == []
    )

    first_test = next(iter(receipt["test_hashes"]))
    receipt["test_hashes"][first_test] = "0" * 64
    write_json_atomic(Path(str(result["result_path"])), receipt)
    errors = controller._validate_app_validation_result(
        paths,
        app_job,
        state_row,
        protocol=protocol,
        state=state,
        jobs=jobs,
    )
    assert any("current checksum differs" in error for error in errors)


def test_default_mode_selection_uses_matched_development_results_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    modes = (
        "H2_KNOWN_ONLY",
        "H2_SESSION_ANONYMOUS",
        "H2_SESSION_MEMORY_ENHANCED",
    )
    jobs = tuple(
        H2Job(
            job_id=f"mode_{index}",
            phase_index=5,
            phase_name="TRANSCRIPT_UI",
            job_kind="post_selection_mode_validation",
            split="development",
            pipeline_id="fullpipe_v1_ag_dr_ir",
            configuration_id=f"{mode}_DEVELOPMENT",
            mode=mode,
            case_ids=("case_a", "case_b"),
            audio_duration_sec=12.0,
            runtime_tuning=H2RuntimeTuning(product_mode=mode).to_jsonable(),
        )
        for index, mode in enumerate(modes)
    )
    state_rows: dict[str, object] = {}
    roots: dict[str, Path] = {}
    for job in jobs:
        root = paths.results_root / job.mode
        checksum = root / "checksums.json"
        write_json_atomic(checksum, {"mode": job.mode})
        roots[job.mode] = root
        state_rows[job.job_id] = {
            "state": "COMPLETE",
            "result_path": str(root),
            "result_sha256": controller.sha256_file(checksum),
        }
    metrics = {
        "H2_KNOWN_ONLY": {
            "wrong_known_time_sec": 0.2,
            "stranger_false_known_time_sec": 0.1,
        },
        "H2_SESSION_ANONYMOUS": {
            "wrong_known_time_sec": 0.1,
            "stranger_false_known_time_sec": 0.1,
        },
        "H2_SESSION_MEMORY_ENHANCED": {
            "wrong_known_time_sec": 0.0,
            "stranger_false_known_time_sec": 0.1,
        },
    }
    monkeypatch.setattr(
        controller,
        "validate_result_tree",
        lambda _root: SimpleNamespace(reusable=True),
    )
    monkeypatch.setattr(
        controller,
        "metric_vector_from_result",
        lambda root: {
            metric_id: metrics[root.name].get(metric_id)
            for metric_id, _view, _direction in controller.METRIC_PRIORITY
        },
    )

    selected = controller._select_development_default_mode(
        paths, {"jobs": state_rows}, jobs
    )

    assert selected["selected_default_mode"] == "H2_SESSION_MEMORY_ENHANCED"
    assert selected["development_only"] is True
    assert selected["evaluation_material_inspected"] is False
    unsigned = dict(selected)
    digest = unsigned.pop("selection_identity_sha256")
    assert digest == controller.canonical_sha256(unsigned)


def test_demo_launch_automatically_uses_the_checksum_bound_frozen_binding(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    default_mode = "H2_SESSION_ANONYMOUS"
    freeze_unsigned = {
        "schema_version": "h2-frozen-development-policy.v1",
        "default_product_mode": default_mode,
    }
    freeze_identity = controller.canonical_sha256(freeze_unsigned)
    write_json_atomic(
        paths.freeze_path,
        {
            **freeze_unsigned,
            "freeze_identity_sha256": freeze_identity,
        },
    )
    tuning = H2RuntimeTuning()
    selected_runtime = {
        "runtime_tuning": tuning.to_jsonable(),
        "runtime_tuning_identity_sha256": tuning.identity_sha256,
    }
    binding_path = (
        paths.summary_root / "frozen_configurations/h2_demo_runtime_binding.frozen.json"
    )
    binding = controller.build_h2_demo_runtime_binding_payload(
        lifecycle="FROZEN",
        default_product_mode=default_mode,
        configurations=controller._demo_binding_configurations(
            selected_runtime,
            source_result_sha256="a" * 64,
            freeze_identity_sha256=freeze_identity,
        ),
        provenance={"freeze_identity_sha256": freeze_identity},
    )
    write_json_atomic(binding_path, binding)

    launched = controller.launch_demo(paths, dry_run=True)

    assert launched["configuration_status"] == "FROZEN_SCIENTIFIC_CONFIGURATION"
    assert launched["runtime_binding_path"] == str(binding_path)
    assert launched["runtime_binding_sha256"] == controller.sha256_file(binding_path)
    assert "--h2-runtime-config" in launched["command"]
    assert "--h2-runtime-config-sha256" in launched["command"]


def test_milestones_are_restart_idempotent_and_plan_is_explicit(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.workspace.mkdir(parents=True)
    state: dict[str, object] = {"milestone_ids": []}
    first = controller._record_milestone(
        paths,
        state,
        milestone_id="phase-complete:test",
        kind="PHASE_COMPLETE",
        detail="test phase complete",
    )
    second = controller._record_milestone(
        paths,
        state,
        milestone_id="phase-complete:test",
        kind="PHASE_COMPLETE",
        detail="test phase complete",
    )
    planned = controller.plan(paths)

    assert first == second
    assert (paths.workspace / controller.MILESTONES_FILE).read_text().count("\n") == 1
    assert planned["timing_estimate"]["bounded_smoke_measured"] is False
    assert planned["total_expected_audio_hours"] > 0
    assert planned["total_expected_inference_units"] > 0


def test_powershell_contract_exposes_resume_monitor_and_open_monitor() -> None:
    root = Path(__file__).resolve().parents[1]
    run_script = (root / "scripts/run_h2_product_program.ps1").read_text(
        encoding="utf-8"
    )
    monitor_script = (root / "scripts/monitor_h2_product_program.ps1").read_text(
        encoding="utf-8"
    )
    read_only_monitor = (
        root / "scripts/monitor_h2_product_program_readonly.ps1"
    ).read_text(encoding="utf-8")
    milestone_watcher = (root / "scripts/watch_h2_milestones.ps1").read_text(
        encoding="utf-8"
    )
    package_watcher = (
        root / "scripts/watch_and_augment_h2_final_package.ps1"
    ).read_text(encoding="utf-8")

    assert "'Resume'" in run_script
    assert "[switch]$OpenMonitor" in run_script
    assert "ArgumentList.Add" in run_script
    assert "H2_BACKGROUND_ARGUMENTS_JSON" in run_script
    assert "h2_windows_atomic_retry_bootstrap.py" in run_script
    assert "H2_ATOMIC_RETRY_POLICY_ROOT" in run_script
    assert "H2_ATOMIC_RETRY_EVENT_LOG" in run_script
    assert "Join-Path $ResolvedWorkspace 'logs'" in run_script
    assert "Ensure-H2FinalPackageWatcher" in run_script
    assert "watch_and_augment_h2_final_package.ps1" in run_script
    assert "FinalPackageWatcherPid" in run_script
    assert "LATEST_H2_AUGMENTED_PACKAGE.json" in run_script
    assert "[switch]$Follow" in monitor_script
    assert "$IntervalSeconds" in monitor_script
    assert "[string]$Config" in monitor_script
    assert "[switch]$NoMilestoneSound" in monitor_script
    assert "monitor_h2_product_program_readonly.ps1" in monitor_script
    assert "[IO.FileShare]::Delete" in read_only_monitor
    assert "Get-H2FileSha256" in read_only_monitor
    assert "IncludeLiveCaseStatus" in read_only_monitor
    assert "DURABLE_CASE_COUNTERS" in read_only_monitor
    assert "current_job_percentage" in read_only_monitor
    assert "monitor_writes_scientific_state = $false" in read_only_monitor
    assert "h2_program_run.lock.owner.json" in read_only_monitor
    assert "controller_host_process_fallback" in read_only_monitor
    assert "controller_descendant_worker_fallback" in read_only_monitor
    assert "Get-H2WorkerFleetSample" in read_only_monitor
    assert "app\\.full_pipeline\\.worker_main" in read_only_monitor
    assert "worker_detection_source" in read_only_monitor
    assert "This does not mean the controller is stuck." in read_only_monitor
    assert "sampled_host_process_id" in read_only_monitor
    assert "ConvertTo-H2UtcDateTime" in read_only_monitor
    assert "overall_percentage" in read_only_monitor
    assert "neural_inference_percentage" in read_only_monitor
    assert "policy_replay_percentage" in read_only_monitor
    assert "bootstrap_percentage" in read_only_monitor
    assert "milestones.jsonl" in read_only_monitor
    assert "SystemSounds]::Exclamation.Play()" in read_only_monitor
    assert "NoMilestoneSound" in read_only_monitor
    assert "Read-H2JsonSharedDelete" in milestone_watcher
    assert "[IO.FileShare]::Delete" in milestone_watcher
    assert "Read-H2JsonSharedDelete" in package_watcher
    assert "[IO.FileShare]::Delete" in package_watcher
    assert "Get-H2FileSha256" in package_watcher
    assert "Write-H2JsonAtomic" in package_watcher
    assert "final_augmented_collection.json" in package_watcher
    assert "LATEST_H2_AUGMENTED_PACKAGE.json" in package_watcher
    assert "h2-final-augmented-collection-pointer.v1" in package_watcher
    assert "source_native_zip_sha256" in package_watcher
    assert "preferred_upload_artifact = 'augmented_collection'" in package_watcher
    assert package_watcher.index("-Path $PackageCollectionPointerPath") < (
        package_watcher.index("-Path $WorkspaceCollectionPointerPath")
    )
    assert "app.h2_product_program" not in read_only_monitor
    assert "runtime_cases" in read_only_monitor
    assert "current_case_percentage" in read_only_monitor
    assert "current_case_heartbeat_age_sec" in read_only_monitor
    assert "embedding_calls" in read_only_monitor
    assert "queue_depth_source" in read_only_monitor
    assert "queue_backpressure_policy" in read_only_monitor
    assert "dropped_frame_count" in read_only_monitor
    assert "Measure-H2DynamicCampaignProgress" in read_only_monitor
    assert "campaign_progress_active_plan_units" in read_only_monitor
    assert "predeclared_manifest_percentage" in read_only_monitor
    assert "h2-read-only-monitor.v7" in read_only_monitor
    assert "Get-H2FinalPackageStatus" in read_only_monitor
    assert "final_augmented_collection.json" in read_only_monitor
    assert "final_package_upload_path" in read_only_monitor
    assert "UPLOAD THIS FILE TO CHATGPT:" in read_only_monitor
    assert "TerminalPackageReady" in read_only_monitor
    assert "worker_cpu_core_percent" in read_only_monitor
    assert "failed_jobs" in read_only_monitor
    assert "recovered_failed_attempts" in read_only_monitor
    assert "checksum-valid case shard seals" in read_only_monitor


def test_read_only_monitor_validates_terminal_augmented_upload_pointer(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/monitor_h2_product_program_readonly.ps1"
    workspace = tmp_path / "workspace"
    results = tmp_path / "results"
    package_root = tmp_path / "packages"
    summaries = package_root / "campaign"
    workspace.mkdir()
    results.mkdir()
    summaries.mkdir(parents=True)
    job_id = "terminal_fixture_job"
    (workspace / "program_state.json").write_text(
        json.dumps(
            {
                "status": "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM",
                "started_at_utc": "2026-08-29T00:00:00Z",
                "current_phase_name": "FINAL_COLLECTION",
                "current_job_id": job_id,
                "target_wall_hours": 192.0,
                "target_is_advisory_only": True,
                "jobs": {job_id: {"state": "COMPLETE"}},
            }
        ),
        encoding="utf-8",
    )
    (workspace / "campaign_progress.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "job_id": job_id,
                        "completed_cases": 1,
                        "planned_cases": 1,
                        "percentage": 100.0,
                    }
                ],
                "failed_jobs": 0,
                "failures": 0,
                "retries": 0,
                "rolling_rtf": 0.1,
                "latest_activity": "terminal collection complete",
                "updated_at_utc": "2026-08-29T01:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (workspace / "job_manifest.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "job_id": job_id,
                        "job_kind": "runtime_evaluation",
                        "case_ids": ["case_1"],
                        "audio_duration_sec": 1.0,
                        "pipeline_id": "fullpipe_v1_ag_dr_ir",
                        "runtime_tuning": {},
                        "configuration_id": "H2_TERMINAL_FIXTURE",
                        "mode": "file_simulation",
                        "split": "evaluation",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (workspace / "protocol_manifest.json").write_text("{}", encoding="utf-8")
    upload = package_root / "h2_terminal_fixture_with_plots.zip"
    upload.write_bytes(b"checksum-bound augmented fixture")
    receipt = upload.with_suffix(upload.suffix + ".receipt.json")
    receipt.write_text("{}", encoding="utf-8")
    upload_sha256 = hashlib.sha256(upload.read_bytes()).hexdigest()
    pointer = workspace / "final_augmented_collection.json"
    package_pointer = package_root / "LATEST_H2_AUGMENTED_PACKAGE.json"
    pointer_payload = {
                "schema_version": "h2-final-augmented-collection-pointer.v1",
                "status": "VALID",
                "source_program_status": "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM",
                "workspace": str(workspace.resolve()),
                "package_root": str(package_root.resolve()),
                "workspace_pointer_path": str(pointer.resolve()),
                "package_pointer_path": str(package_pointer.resolve()),
                "publication_order": [
                    "package_root_pointer",
                    "workspace_terminal_commit_pointer",
                ],
                "controller_program_state_preserved": True,
                "scientific_content_unchanged": True,
                "preferred_upload_artifact": "augmented_collection",
                "augmented_collection": {
                    "upload_path": str(upload.resolve()),
                    "sha256": upload_sha256,
                    "receipt_path": str(receipt.resolve()),
                },
            }
    package_pointer.write_text(json.dumps(pointer_payload), encoding="utf-8")
    pointer.write_text(
        json.dumps(pointer_payload),
        encoding="utf-8",
    )

    def snapshot() -> dict[str, object]:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-Once",
                "-Json",
                "-Workspace",
                str(workspace),
                "-ResultsRoot",
                str(results),
                "-SummaryRoot",
                str(summaries),
                "-Config",
                str(root / "configs/automated_evaluation/h2_product_program.v1.yaml"),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        return json.loads(completed.stdout)

    valid = snapshot()
    assert valid["schema_version"] == "h2-read-only-monitor.v7"
    assert valid["final_package_status"] == "VALID", valid["final_package_detail"]
    assert valid["final_package_upload_path"] == str(upload.resolve())
    assert valid["final_package_sha256"] == upload_sha256
    assert valid["monitor_writes_scientific_state"] is False

    upload.write_bytes(b"corrupted after pointer publication")
    invalid = snapshot()
    assert invalid["final_package_status"] == "INVALID"
    assert "checksum differs" in str(invalid["final_package_detail"])


def test_follow_monitor_waits_through_not_prepared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshots = iter(
        (
            {"status": "NOT_PREPARED"},
            {"status": "COMPLETE"},
        )
    )
    calls = 0

    def fake_status(_paths: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return next(snapshots)

    monkeypatch.setattr(h2_cli.controller, "status", fake_status)
    monkeypatch.setattr(h2_cli.time, "sleep", lambda _seconds: None)

    assert h2_cli._watch(object(), interval_sec=0.5, as_json=True) == 0
    assert calls == 2


def test_audit_blocks_an_active_scientific_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        controller,
        "_current_process_audit",
        lambda: {
            "completed": True,
            "other_campaigns": [
                {
                    "pid": 1234,
                    "command_line": "python -m app.h2_product_program Run",
                }
            ],
        },
    )

    result = controller.audit(_paths(tmp_path))

    assert result["valid"] is False
    assert result["status"] == "BLOCKED_ACTIVE_CAMPAIGN_TRANSITION"
    assert result["concurrent_campaign_warning"] is True


def test_run_transition_gate_fails_before_auto_prepare_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)

    def blocked(_paths_value: object) -> dict[str, object]:
        raise controller.H2ProgramError("BLOCKED_ACTIVE_CAMPAIGN_TRANSITION")

    monkeypatch.setattr(controller, "_require_launch_transition", blocked)

    with pytest.raises(
        controller.H2ProgramError, match="BLOCKED_ACTIVE_CAMPAIGN_TRANSITION"
    ):
        controller.run(paths, maximum_jobs=0)
    assert not paths.workspace.exists()


def test_smoke_transition_gate_fails_before_any_write_or_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    reserve_checked = False

    def blocked(_paths_value: object) -> dict[str, object]:
        raise controller.H2ProgramError("BLOCKED_ACTIVE_CAMPAIGN_TRANSITION")

    def reserve(_paths_value: object) -> None:
        nonlocal reserve_checked
        reserve_checked = True

    monkeypatch.setattr(controller, "_require_launch_transition", blocked)
    monkeypatch.setattr(controller, "_require_storage_reserve", reserve)

    with pytest.raises(
        controller.H2ProgramError, match="BLOCKED_ACTIVE_CAMPAIGN_TRANSITION"
    ):
        controller.smoke(paths)
    assert reserve_checked is False
    assert not paths.workspace.exists()


@pytest.mark.parametrize("missing", [False, True])
def test_evidence_audit_fails_on_hash_mismatch_or_missing_exact_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: bool
) -> None:
    paths = _paths(tmp_path)
    artifact = tmp_path / ("missing.json" if missing else "changed.json")
    if not missing:
        artifact.write_text('{"changed":true}\n', encoding="utf-8")
    monkeypatch.setattr(
        controller,
        "read_yaml",
        lambda _path: {
            "immutable": {
                "path": str(artifact),
                "sha256": "0" * 64,
            }
        },
    )
    job = H2Job(
        job_id="evidence",
        phase_index=0,
        phase_name="AUDIT_BASELINE",
        job_kind="evidence_audit",
        split="none",
        pipeline_id="NOT_APPLICABLE",
        configuration_id="EVIDENCE",
        mode="NOT_APPLICABLE",
        case_ids=(),
        audio_duration_sec=0.0,
        runtime_tuning={},
    )

    result = controller._handle_evidence_audit(paths, job)
    receipt = read_json(Path(str(result["result_path"])))

    assert result["state"] == "failed"
    assert receipt["status"] == "FAILED"
    assert receipt["failure_count"] == 1
    assert receipt["failures"][0]["artifact_id"] == "historical:immutable"


def test_promotion_artifact_is_authoritative_for_validate_and_best_selection(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    controller.prepare(paths)
    state = read_json(paths.state_path)
    decision = {
        "schema_version": "h2-development-promotion.v1",
        "status": "COMPLETE",
        "development_only": True,
        "evaluation_material_inspected": False,
        "weighted_composite_used": False,
        "required_safety_metrics": sorted(controller.REQUIRED_SAFETY_METRICS),
        "required_short_turn_metrics": sorted(controller.REQUIRED_SHORT_TURN_METRICS),
        "required_promotion_metrics": sorted(controller.REQUIRED_PROMOTION_METRICS),
        "selected_candidates": ["SELECTED"],
    }
    decision_path = paths.workspace / "promotions" / "phase_1_full.json"
    write_json_atomic(decision_path, decision)
    state["promotions"]["phase_1_full"] = {
        **decision,
        "decision_path": str(decision_path),
        "decision_sha256": controller.sha256_file(decision_path),
    }
    write_json_atomic(paths.state_path, state)
    selected = H2Job(
        job_id="selected",
        phase_index=1,
        phase_name="SEGMENTATION_FRONTIER",
        job_kind="successive_halving_runtime",
        split="development",
        pipeline_id="fullpipe_v1_ag_dr_ir",
        configuration_id="SELECTED_FULL",
        mode="H2_SESSION_MEMORY_ENHANCED",
        case_ids=("case",),
        audio_duration_sec=1.0,
        runtime_tuning=H2RuntimeTuning().to_jsonable(),
    )
    local_state = {
        **state,
        "jobs": {**state["jobs"], "selected": {"state": "COMPLETE"}},
    }
    assert (
        controller._best_promoted_full(paths, local_state, (selected,), 1) == selected
    )

    decision_path.write_text(
        decision_path.read_text(encoding="utf-8").replace('"SELECTED"', '"MUTATED"'),
        encoding="utf-8",
    )
    checked = controller.validate(paths, verify_results=False)
    assert checked["valid"] is False
    assert any("checksum differs" in error for error in checked["errors"])
    with pytest.raises(controller.H2ProgramError, match="checksum differs"):
        controller._best_promoted_full(paths, local_state, (selected,), 1)


def test_status_retains_last_known_queue_snapshot_and_monitor_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _paths(tmp_path)
    controller.prepare(paths)
    state = read_json(paths.state_path)
    manifest = read_json(paths.jobs_path)
    runtime = next(
        H2Job.from_jsonable(row)
        for row in manifest["jobs"]
        if row["job_kind"] in RUNTIME_KINDS and row["split"] != "evaluation"
    )
    state["status"] = "RUNNING"
    state["started_at_utc"] = controller._utc_now()
    state["current_job_id"] = runtime.job_id
    state["current_phase_index"] = runtime.phase_index
    state["current_phase_name"] = runtime.phase_name
    state["jobs"][runtime.job_id].update(
        {
            "state": "RUNNING",
            "latest_output": str(tmp_path / "latest output.json"),
        }
    )
    write_json_atomic(paths.state_path, state)
    queue_row = {
        "spec": {
            "case_count": len(runtime.case_ids),
            "audio_duration_sec": runtime.audio_duration_sec,
        },
        "completed_cases": 1,
        "completed_audio_sec": 2.0,
        "current_case_id": runtime.case_ids[0],
        "latest_activity": "running bounded case",
        "rolling_rtf": 0.4,
        "cpu_percent": 25.0,
        "rss_mb": 512.0,
        "queue_depth": 0,
        "cache_hits": 3,
        "retry_count": 1,
    }
    monkeypatch.setattr(
        controller,
        "_live_status_queue_rows",
        lambda _paths_value, _jobs: {runtime.job_id: queue_row},
    )
    live = controller.status(paths)
    assert live["queue_snapshot_source"] == "LIVE"

    def broken_queue(_paths_value: object, _jobs: object) -> object:
        raise RuntimeError("queue temporarily locked")

    monkeypatch.setattr(controller, "_live_status_queue_rows", broken_queue)
    stale = controller.status(paths)
    assert stale["queue_snapshot_source"] == "LAST_KNOWN"
    assert stale["queue_snapshot_stale"] is True
    assert "queue temporarily locked" in str(stale["queue_snapshot_error"])
    assert stale["current_case_id"] == runtime.case_ids[0]
    assert stale["current_backend"]["identity_embedding"] == (
        "redimnet2_b2_speaker_embedding"
    )
    assert stale["total_jobs"] == stale["active_planned_jobs"]
    assert stale["estimated_finish_utc"] is not None

    h2_cli._print_monitor(stale)
    rendered = capsys.readouterr().out
    assert "H2 PROGRAM" in rendered
    assert "jobs=" in rendered and "cases=" in rendered and "audio=" in rendered
    assert "backends ASR=" in rendered
    assert "RTF=0.4" in rendered and "CPU=25.0%" in rendered
    assert "failures=0" in rendered and "retries=1" in rendered
    assert "queue_snapshot=LAST_KNOWN" in rendered
    assert "ERROR=RuntimeError: queue temporarily locked" in rendered


def test_powershell_wrapper_round_trips_spaced_custom_paths(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/run_h2_product_program.ps1"
    workspace = tmp_path / "workspace with spaces"
    results = tmp_path / "results with spaces"
    summaries = tmp_path / "summaries with spaces"
    config = root / "configs/automated_evaluation/h2_product_program.v1.yaml"
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Action",
            "Plan",
            "-Workspace",
            str(workspace),
            "-ResultsRoot",
            str(results),
            "-SummaryRoot",
            str(summaries),
            "-Config",
            str(config),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "PLANNED_NOT_RUN"
    assert not workspace.exists()


def test_powershell_wrapper_rejects_dry_run_for_mutating_action(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/run_h2_product_program.ps1"
    workspace = tmp_path / "must remain absent"
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Action",
            "Prepare",
            "-Workspace",
            str(workspace),
            "-DryRun",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "-DryRun is supported only with -Action LaunchDemo" in completed.stderr
    assert not workspace.exists()


def test_milestone_notifier_dry_run_creates_no_operational_state(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/watch_h2_milestones.ps1"
    workspace = tmp_path / "existing workspace"
    workspace.mkdir()
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Workspace",
            str(workspace),
            "-DryRun",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "PASS"
    assert payload["scientific_files_modified"] is False
    assert not (workspace / "milestone_notifier").exists()


@pytest.mark.skipif(
    Path.cwd().drive.casefold() == "c:", reason="non-C check needs another drive"
)
def test_non_c_paths_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        controller.audit(_paths(tmp_path))
