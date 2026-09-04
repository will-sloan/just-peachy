"""Validate the Task-1 decision and held-out anonymous-diarization inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Mapping

import yaml

from app.hybrid_final_evaluation.contracts import (
    CORPORA,
    FINAL_DIARIZATION_ROOT,
    FROZEN_HYBRID_PATH,
    POLICY_ROOT,
    PRODUCT_PROTOCOL_ROOT,
    RESULT_ROOT,
    TASK1_ROOT,
    TOOL_ROOT,
    FinalHybridEvaluationError,
    atomic_json,
    file_sha256,
    frozen_sha256_path,
    now_utc,
    read_json,
    read_jsonl,
)


REQUIRED_FINALIST_FIELDS = {
    "hybrid_combination_id",
    "diarization_pipeline_id",
    "diarization_configuration_sha256",
    "identity_backend_id",
    "identity_backend",
    "scientific_enrollment_policy_sha256",
    "score_threshold",
    "margin_threshold",
    "minimum_evidence_sec",
    "quality_gate",
    "overlap_policy",
    "label_display_policy",
    "confirmation",
    "expiry_session_policy",
    "gallery_calibration_policy",
}


def load_frozen() -> dict[str, object]:
    if not FROZEN_HYBRID_PATH.is_file():
        raise FinalHybridEvaluationError(f"Task-1 frozen selection is missing: {FROZEN_HYBRID_PATH}")
    return yaml.safe_load(FROZEN_HYBRID_PATH.read_text(encoding="utf-8"))


def selected_finalists(selection: Mapping[str, object] | None = None) -> tuple[dict[str, object], ...]:
    value = selection or load_frozen()
    return tuple(dict(row) for row in value.get("selected_finalists") or [])


def validate_frozen_decision(*, write_result: bool = True) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    evidence: dict[str, object] = {}
    try:
        frozen = load_frozen()
    except Exception as exc:
        frozen = {}
        errors.append(str(exc))

    observed_frozen_sha = file_sha256(FROZEN_HYBRID_PATH).lower() if FROZEN_HYBRID_PATH.is_file() else None
    expected_frozen_sha = None
    if frozen_sha256_path().is_file():
        expected_frozen_sha = frozen_sha256_path().read_text(encoding="utf-8").strip().split()[0].lower()
    if not expected_frozen_sha or observed_frozen_sha != expected_frozen_sha:
        errors.append("Task-1 frozen-selection checksum mismatch")
    evidence["frozen_hybrid_selection"] = {
        "path": str(FROZEN_HYBRID_PATH),
        "sha256": observed_frozen_sha,
        "sidecar_sha256": expected_frozen_sha,
    }

    finalists = selected_finalists(frozen) if frozen else ()
    ids = [str(row.get("hybrid_combination_id")) for row in finalists]
    if not 2 <= len(finalists) <= 3 or ids != list(frozen.get("selected_hybrid_combination_ids") or []):
        errors.append("Task-1 finalist membership/order is invalid")
    if frozen.get("selection_status") != "FROZEN_DEVELOPMENT_ONLY":
        errors.append("Task-1 selection status is not FROZEN_DEVELOPMENT_ONLY")
    if frozen.get("evaluation_authorized") is not True or frozen.get("EVALUATION_NOT_INSPECTED") is not True:
        errors.append("Task-1 evaluation firewall/authorization is invalid")
    if frozen.get("controlled_hybrid_evaluation_run") is not False:
        errors.append("Task-1 claims controlled hybrid evaluation was already run")
    for row in finalists:
        missing = sorted(REQUIRED_FINALIST_FIELDS - set(row))
        if missing:
            errors.append(f"{row.get('hybrid_combination_id')}: frozen fields missing: {missing}")
        if str(row.get("label_display_policy")) != "ADAPTIVE":
            errors.append(f"{row.get('hybrid_combination_id')}: unsupported frozen label policy")
        if str(row.get("overlap_policy")) != "exclude_predicted_overlap_for_identity_primary_include_diagnostic":
            errors.append(f"{row.get('hybrid_combination_id')}: unsupported frozen overlap policy")
        policy_path = POLICY_ROOT / f"{row.get('identity_backend_id')}.scientific.yaml"
        observed = file_sha256(policy_path).lower() if policy_path.is_file() else None
        if observed != str(row.get("scientific_enrollment_policy_sha256", "")).lower():
            errors.append(f"{row.get('hybrid_combination_id')}: scientific enrollment-policy checksum mismatch")

    identity_files = [
        TASK1_ROOT / "analysis" / name
        for name in (
            "hybrid_combination_summary.csv",
            "overlay_results.csv",
            "calibration_results.csv",
            "bootstrap_intervals.csv",
        )
    ]
    if all(path.is_file() for path in identity_files):
        development_identity = hashlib.sha256(
            "".join(file_sha256(path).lower() for path in identity_files).encode("ascii")
        ).hexdigest()
        if development_identity != frozen.get("development_result_identity_sha256"):
            errors.append("Task-1 development-result identity mismatch")
    else:
        development_identity = None
        errors.append("Task-1 development analysis identity inputs are incomplete")
    evidence["development_result_identity_sha256"] = development_identity

    source_checks = []
    for row in frozen.get("source_code_result_affecting_hashes") or []:
        path = TOOL_ROOT / str(row.get("path"))
        observed = file_sha256(path).lower() if path.is_file() else None
        valid = observed == str(row.get("sha256", "")).lower()
        source_checks.append({"path": str(path), "expected_sha256": row.get("sha256"), "observed_sha256": observed, "valid": valid})
        if not valid:
            errors.append(f"Task-1 result-affecting source changed: {row.get('path')}")
    evidence["task1_source_checks"] = source_checks

    frozen_diar = dict(frozen.get("frozen_diarization_selection") or {})
    diar_path = Path(str(frozen_diar.get("path") or ""))
    observed_diar_sha = file_sha256(diar_path).lower() if diar_path.is_file() else None
    if observed_diar_sha != str(frozen_diar.get("sha256", "")).lower():
        errors.append("upstream frozen standalone-diarization selection mismatch")
    evidence["frozen_diarization_selection"] = {"path": str(diar_path), "sha256": observed_diar_sha}

    protocol_summary_path = PRODUCT_PROTOCOL_ROOT / "protocol_summary.json"
    if not protocol_summary_path.is_file():
        errors.append("Hybrid Product V2 protocol summary is missing")
        protocol_summary = {}
    else:
        protocol_summary = read_json(protocol_summary_path)
        if protocol_summary.get("protocol_id") != dict(frozen.get("protocol_ids") or {}).get("hybrid_product_v2"):
            errors.append("Hybrid Product V2 protocol identity mismatch")
    evidence["protocol_summary_sha256"] = file_sha256(protocol_summary_path).lower() if protocol_summary_path.is_file() else None

    manifest_evidence: dict[str, object] = {}
    frozen_configs = {str(row.get("diarization_pipeline_id")): str(row.get("diarization_configuration_sha256")).lower() for row in finalists}
    for corpus, settings in CORPORA.items():
        benchmark_root = Path(settings["benchmark_root"])
        cases_path = benchmark_root / "evaluation" / "case_manifest.jsonl"
        overlays_path = PRODUCT_PROTOCOL_ROOT / corpus / "evaluation" / "identity_overlays.jsonl"
        cases = read_jsonl(cases_path) if cases_path.is_file() else []
        overlays = read_jsonl(overlays_path) if overlays_path.is_file() else []
        if len(overlays) != len(cases) * 3:
            errors.append(f"{corpus}: held-out overlay count does not equal three per case")
        if any(row.get("tier") != "evaluation" or row.get("evaluation_locked") is not True for row in cases):
            errors.append(f"{corpus}: case manifest lacks held-out evaluation locks")
        if any(row.get("tier") != "evaluation" or row.get("evaluation_only") is not True for row in overlays):
            errors.append(f"{corpus}: overlay manifest lacks held-out evaluation locks")
        manifest_evidence[corpus] = {
            "case_count": len(cases),
            "overlay_count": len(overlays),
            "case_manifest_sha256": file_sha256(cases_path).lower() if cases_path.is_file() else None,
            "overlay_manifest_sha256": file_sha256(overlays_path).lower() if overlays_path.is_file() else None,
        }
        scope = str(settings["diarization_scope"])
        for case in cases:
            for pipeline, expected_config in frozen_configs.items():
                root = FINAL_DIARIZATION_ROOT / scope / "evaluation" / pipeline / str(case["case_id"])
                try:
                    run = read_json(root / "run.json")
                    identity = read_json(root / "resolved_pipeline_identity.json")
                    observed_config = str(identity.get("configuration_sha256") or identity.get("pipeline_configuration_sha256") or run.get("pipeline_configuration_sha256") or "").lower()
                    if run.get("status") != "succeeded" or run.get("tier") != "evaluation" or run.get("pipeline_id") != pipeline:
                        raise ValueError("run status/tier/pipeline mismatch")
                    if str(run.get("benchmark_audio_sha256", "")).lower() != str(case.get("audio_sha256", "")).lower():
                        raise ValueError("audio identity mismatch")
                    if observed_config != expected_config:
                        raise ValueError("frozen diarization configuration mismatch")
                    if not (root / "predictions" / "segments.rttm").is_file():
                        raise ValueError("segments.rttm missing")
                except Exception as exc:
                    errors.append(f"invalid held-out anonymous diarization result {corpus}/{pipeline}/{case.get('case_id')}: {exc}")
    evidence["evaluation_manifests"] = manifest_evidence

    final_diar_manifest = FINAL_DIARIZATION_ROOT / "analysis" / "analysis_manifest.json"
    if final_diar_manifest.is_file():
        diar_analysis = read_json(final_diar_manifest)
        if diar_analysis.get("controlled_evaluation_run") is not True or diar_analysis.get("evaluation_tuning_performed") is not False:
            errors.append("final standalone diarization analysis is not an untouched evaluation")
        evidence["standalone_diarization_analysis_sha256"] = file_sha256(final_diar_manifest).lower()
    else:
        errors.append("final standalone diarization analysis manifest is missing")

    repo_root = TOOL_ROOT.parent.parent
    git = _git_snapshot(repo_root)
    if git.get("dirty_paths"):
        warnings.append("repository has pre-existing result-affecting and operator-owned dirty state; exact frozen hashes remain authoritative")
    evidence["repository"] = git
    evidence["native_scope"] = {
        "chime6": "CHIME6_HYBRID_NOT_SCIENTIFICALLY_SUPPORTED: Task 1 did not prove source-time/synchronized-duplicate disjointness",
        "voices": "NOT_SUPPORTED: Task 1 did not freeze a far-field identity enrollment/probe protocol",
    }
    result = {
        "schema_version": "hybrid-final-frozen-validation.v1",
        "created_at_utc": now_utc(),
        "status": "VALID" if not errors else "FAIL",
        "selected_finalists": ids,
        "errors": errors,
        "warnings": warnings,
        "evidence": evidence,
    }
    if write_result:
        RESULT_ROOT.mkdir(parents=True, exist_ok=True)
        atomic_json(RESULT_ROOT / "validation.json", result)
    return result


def require_valid_decision() -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    validation = validate_frozen_decision()
    if validation["status"] != "VALID":
        raise FinalHybridEvaluationError(f"BLOCKED_INVALID_FROZEN_HYBRID_DECISION: {validation['errors'][:5]}")
    frozen = load_frozen()
    return frozen, selected_finalists(frozen)


def _git_snapshot(repo_root: Path) -> dict[str, object]:
    def run(*args: str) -> str:
        completed = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        return completed.stdout.strip()
    dirty = [line for line in run("status", "--short").splitlines() if line]
    return {
        "branch": run("branch", "--show-current"),
        "head_sha": run("rev-parse", "HEAD"),
        "dirty": bool(dirty),
        "dirty_paths": dirty,
    }
