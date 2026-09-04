from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.full_pipeline_evaluation.protocol import load_cases
from app.full_pipeline_evaluation.io import sha256_file
from app.full_pipeline_evaluation.planning import matrix
from app.full_pipeline_extended_evaluation import (
    DEFAULT_ENROLLMENT_REGISTRY,
    DEFAULT_PROTOCOL_ROOT,
    MANDATORY_ANCHORS,
    RELIABILITY_FAULTS,
)
from app.full_pipeline_extended_evaluation.protocol import (
    PANEL_CAPS,
    build_bounded_plan,
    plan_specs,
    validate_plan,
)


def _execution_proof() -> dict[str, object]:
    return {
        "execution_contract_validation": "EXACT_LIVE_MATCH",
        "live_result_affecting_code_sha256": "b" * 64,
        "checksums_sha256": "c" * 64,
        "pipeline_freeze_identity_sha256s": {
            pipeline_id: "d" * 64 for pipeline_id in matrix().pipeline_ids
        },
    }


def _deployment_context(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    steering = root / "RASPBERRY_PI_DEPLOYMENT_STEERING.json"
    prompt5 = root / "all18_deployment_evidence.json"
    extended = root / "extended_set.yaml"
    steering.write_text("{}\n", encoding="utf-8")
    prompt5.write_text("{}\n", encoding="utf-8")
    extended.write_text("extended_pipeline_ids: []\n", encoding="utf-8")
    return {
        "raspberry_pi_deployment_steering": {
            "path": str(steering),
            "sha256": sha256_file(steering),
        },
        "prompt5_deployment_evidence": {
            "path": str(prompt5),
            "sha256": sha256_file(prompt5),
        },
        "prompt4_extended_set": {
            "path": str(extended),
            "sha256": sha256_file(extended),
            "mandatory_pipeline_ids": list(MANDATORY_ANCHORS),
            "additional_challenger_pipeline_ids": [],
            "extended_pipeline_ids": list(MANDATORY_ANCHORS),
        },
        "predeclared_membership_unchanged_after_heldout": True,
        "deployment_evidence_used_as_filter": False,
    }


@pytest.fixture(scope="module")
def bounded_plan(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    cases = load_cases(DEFAULT_PROTOCOL_ROOT, split="evaluation")
    summary = json.loads(
        (DEFAULT_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8")
    )
    enrollment = [
        json.loads(line)
        for line in DEFAULT_ENROLLMENT_REGISTRY.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    workspace = tmp_path_factory.mktemp("prompt6-plan")
    return build_bounded_plan(
        cases,
        protocol_summary=summary,
        extended_pipeline_ids=MANDATORY_ANCHORS,
        workspace_root=workspace,
        decision_policy_registry_sha256="a" * 64,
        enrollment_rows=enrollment,
        frozen_execution_contract=_execution_proof(),
        deployment_context=_deployment_context(workspace / "deployment-inputs"),
    )


def test_bounded_plan_has_exact_caps_and_six_anchors(
    bounded_plan: dict[str, object],
) -> None:
    validate_plan(bounded_plan)
    assert bounded_plan["scope_class"] == "BOUNDED_REDUCED"
    assert bounded_plan["original_full_scope_complete"] is False
    assert bounded_plan["pipeline_ids"] == list(MANDATORY_ANCHORS)
    assert bounded_plan["panel_caps"] == PANEL_CAPS
    assert {
        key: value["selected_count"]
        for key, value in bounded_plan["selection_inventory"].items()
    } == PANEL_CAPS
    assert bounded_plan["selection_seed"] == 3800
    assert bounded_plan["outcome_dependent_selection"] is False
    assert (
        bounded_plan["prompt5_scientific_outcome_tables_opened_for_selection"] is False
    )
    assert bounded_plan["prompt5_deployment_evidence_opened_for_reporting"] is True
    assert bounded_plan["deployment_evidence_used_as_filter"] is False
    assert bounded_plan["nominal_stage_planning_target_hours"] == 30
    assert bounded_plan["elapsed_time_kill_switch_enabled"] is False
    assert (
        bounded_plan["frozen_execution_contract"]["execution_contract_validation"]
        == "EXACT_LIVE_MATCH"
    )


def test_stateful_long_reliability_and_resource_caps_are_exact(
    bounded_plan: dict[str, object],
) -> None:
    jobs = bounded_plan["jobs"]
    for pipeline_id in MANDATORY_ANCHORS:
        pipeline_jobs = [
            row for row in jobs if row["spec"]["pipeline_id"] == pipeline_id
        ]
        long_jobs = [row for row in pipeline_jobs if row["panel_id"] == "long_session"]
        reliability = [row for row in pipeline_jobs if row["panel_id"] == "reliability"]
        resources = [
            row for row in pipeline_jobs if row["panel_id"] == "serial_resources"
        ]
        assert len(long_jobs) == 2
        assert all(row["target_duration_sec"] == 1800.0 for row in long_jobs)
        assert all(row["runtime_pace"] == 1.0 for row in long_jobs)
        assert (
            len(
                {
                    row["source_provenance"]["provenance_identity_sha256"]
                    for row in long_jobs
                }
            )
            == 2
        )
        assert {row["fault_id"] for row in reliability} == set(RELIABILITY_FAULTS)
        assert all(30.0 <= row["target_duration_sec"] <= 60.0 for row in reliability)
        assert len(resources) == 1
        assert resources[0]["warmup_duration_sec"] == 60.0
        assert resources[0]["measured_duration_sec"] == 300.0
    assert all(spec.split == "evaluation" for spec in plan_specs(bounded_plan))


def test_hardening_plan_has_outcome_independent_required_roles(
    bounded_plan: dict[str, object],
) -> None:
    hardening = bounded_plan["hardening_input_plan"]
    long_input = hardening["long_input"]
    assert hardening["outcome_independent"] is True
    assert long_input["target_duration_sec"] == 3600.0
    assert set(long_input["roles"]) == {
        "deterministic_replay",
        "controlled_loopback",
        "repeated_session",
        "soak",
    }
    assert len(hardening["enrollment_samples"]) == 3
    assert len({row["input_id"] for row in hardening["enrollment_samples"]}) == 3
    assert all(
        row["roles"] == ["enrollment_sample"] for row in hardening["enrollment_samples"]
    )


def test_plan_rejects_development_cases_before_building_jobs(tmp_path: Path) -> None:
    summary = json.loads(
        (DEFAULT_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8")
    )
    cases = load_cases(DEFAULT_PROTOCOL_ROOT, split="development")
    with pytest.raises(Exception, match="untouched evaluation metadata"):
        build_bounded_plan(
            cases,
            protocol_summary=summary,
            extended_pipeline_ids=MANDATORY_ANCHORS,
            workspace_root=tmp_path,
            decision_policy_registry_sha256="a" * 64,
            enrollment_rows=[],
            frozen_execution_contract=_execution_proof(),
            deployment_context={},
        )
