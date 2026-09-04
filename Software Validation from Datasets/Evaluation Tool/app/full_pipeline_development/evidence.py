"""Checksum-bound composition of separate Prompt-4 development campaigns.

Prompt 4 deliberately measures accuracy (at most two concurrent jobs) and
resources (exactly one concurrent job) in separate controller workspaces.  A
single scientific report still needs one manifest and one analysis index.  The
helpers in this module combine those already-complete controller artifacts;
they never execute inference and never inspect held-out evaluation material.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline_evaluation import controller
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    read_json,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import manifest_jobs, matrix
from app.full_pipeline_evaluation.store import utc_now

from .freeze import freeze_all_pipeline_configs
from .policies import validate_development_policy_registry


COMBINED_CAMPAIGN_SCHEMA_VERSION = (
    "full-pipeline-development-combined-campaign.v1"
)
COMBINED_CAMPAIGN_IDENTITY_SCHEMA_VERSION = (
    "full-pipeline-development-combined-campaign-identity.v1"
)
COMBINED_ANALYSIS_SCHEMA_VERSION = "full-pipeline-evaluation-analysis.v1"
COMBINED_EVIDENCE_SCHEMA_VERSION = "full-pipeline-development-combined-evidence.v1"

_IDENTITY_FIELDS = (
    "full_protocol_id",
    "development_identity",
    "evaluation_identity",
    "matrix_sha256",
    "runtime_config_sha256",
    "scorer_version",
    "result_contract_version",
    "implementation_identity",
    "seed",
    "decision_policy_registry_sha256",
)


class DevelopmentEvidenceError(RuntimeError):
    """Separate development campaigns cannot form one valid evidence set."""


def combine_development_evidence(
    *,
    output_workspace_root: Path,
    accuracy_workspace_root: Path,
    resource_workspace_root: Path,
    accuracy_analysis: Mapping[str, object] | None = None,
    resource_analysis: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate and combine complete accuracy and serial-resource campaigns.

    ``accuracy_analysis`` and ``resource_analysis`` may be the values returned
    by :func:`app.full_pipeline_evaluation.controller.analyze`.  When omitted,
    that function is called for the corresponding workspace.  Supplied values
    must exactly match the on-disk controller analysis, so the combined
    identity always binds checksum-addressable source artifacts.

    The destination receives ``campaign_manifest.json`` and
    ``analysis/analysis.json``.  Physical source-workspace paths are not part
    of the combined campaign identity; source campaign IDs, artifact
    checksums, job specifications, and result checksums are.
    """

    output = Path(output_workspace_root).resolve()
    accuracy_root = Path(accuracy_workspace_root).resolve()
    resource_root = Path(resource_workspace_root).resolve()
    if len({output, accuracy_root, resource_root}) != 3:
        raise DevelopmentEvidenceError(
            "combined, accuracy, and resource workspaces must be distinct"
        )
    accuracy = _validated_source_campaign(
        role="accuracy",
        expected_mode="accuracy",
        workspace=accuracy_root,
        supplied_analysis=accuracy_analysis,
    )
    resources = _validated_source_campaign(
        role="resources",
        expected_mode="resources",
        workspace=resource_root,
        supplied_analysis=resource_analysis,
    )
    _require_matching_scientific_identities(accuracy["manifest"], resources["manifest"])

    accuracy_manifest = accuracy["manifest"]
    resource_manifest = resources["manifest"]
    source_references = [accuracy["reference"], resources["reference"]]
    jobs = _combined_jobs(
        accuracy_manifest,
        resource_manifest,
        accuracy_campaign_id=str(accuracy_manifest["campaign_id"]),
        resource_campaign_id=str(resource_manifest["campaign_id"]),
    )
    rows = _combined_rows(
        accuracy["analysis"],
        resources["analysis"],
        accuracy_campaign_id=str(accuracy_manifest["campaign_id"]),
        resource_campaign_id=str(resource_manifest["campaign_id"]),
    )
    if {str(row["job_id"]) for row in jobs} != {
        str(row["job_id"]) for row in rows
    }:
        raise DevelopmentEvidenceError(
            "combined manifest jobs and checksum-validated analysis rows differ"
        )

    case_index = _combined_case_index(accuracy_manifest, resource_manifest)
    result_checksums = {
        str(row["job_id"]): _sha256(
            row.get("result_checksums_sha256"),
            f"{row.get('job_id')} result checksum",
        )
        for row in rows
    }
    result_set_sha256 = sha256_bytes(canonical_json_bytes(result_checksums))
    expected_pipelines = list(matrix().pipeline_ids)
    identity_core: dict[str, object] = {
        "identity_schema_version": COMBINED_CAMPAIGN_IDENTITY_SCHEMA_VERSION,
        **{field: accuracy_manifest[field] for field in _IDENTITY_FIELDS},
        "campaign_stage": "prompt4_combined_development_evidence",
        "selected_pipeline_ids": expected_pipelines,
        "measurement_modes": ["accuracy", "resources"],
        "source_campaigns": source_references,
        "selected_case_ids": sorted(case_index),
        "case_index": case_index,
        "jobs": jobs,
        "development_result_set_sha256": result_set_sha256,
        "development_only": True,
        "evaluation_material_inspected": False,
    }
    combined_identity = sha256_bytes(canonical_json_bytes(identity_core))
    campaign_id = f"full_pipeline_development_combined_{combined_identity[:12]}"
    combined_manifest: dict[str, object] = {
        "schema_version": COMBINED_CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "campaign_identity_sha256": combined_identity,
        **identity_core,
        "pipeline_count": len(expected_pipelines),
        "job_count": len(jobs),
        "case_count": len(case_index),
        "parallelism_policy": {
            "accuracy_maximum_jobs": 2,
            "resource_measurement_jobs": 1,
            "resource_results_comparable_only_with_serial_resource_results": True,
            "memory_gate_required": True,
        },
        "production_winner_selected": False,
        "held_out_evaluation_allowed": False,
        "model_inference_performed_by_combination": False,
    }

    combined_analysis: dict[str, object] = {
        "schema_version": COMBINED_ANALYSIS_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "campaign_identity_sha256": combined_identity,
        "created_at_utc": utc_now(),
        "complete_result_count": len(rows),
        "accuracy_result_count": sum(
            row["measurement_mode"] == "accuracy" for row in rows
        ),
        "resource_result_count": sum(
            row["measurement_mode"] == "resources" for row in rows
        ),
        "pipeline_ids": expected_pipelines,
        "protocol_ids": sorted({str(row["protocol_id"]) for row in rows}),
        "development_result_set_sha256": result_set_sha256,
        "weighted_composite_score_created": False,
        "resource_comparison_policy": (
            "only measurement_mode=resources serial jobs are mutually comparable"
        ),
        "source_campaigns": source_references,
        "evaluation_material_inspected": False,
        "rows": rows,
    }
    _write_or_verify(output / "campaign_manifest.json", combined_manifest)
    _write_or_verify(output / "analysis/analysis.json", combined_analysis)
    return {
        "schema_version": COMBINED_EVIDENCE_SCHEMA_VERSION,
        "status": "PASS",
        "campaign_id": campaign_id,
        "campaign_identity_sha256": combined_identity,
        "development_result_set_sha256": result_set_sha256,
        "pipeline_count": len(expected_pipelines),
        "job_count": len(jobs),
        "accuracy_job_count": combined_analysis["accuracy_result_count"],
        "resource_job_count": combined_analysis["resource_result_count"],
        "campaign_manifest": str(output / "campaign_manifest.json"),
        "analysis": str(output / "analysis/analysis.json"),
        "development_only": True,
        "evaluation_material_inspected": False,
        "model_inference_performed": False,
    }


def freeze_development_outputs(
    *,
    combined_workspace_root: Path,
    policy_registry: Mapping[str, object] | Path,
    runtime_anchor_qualification: Mapping[str, object],
    frozen_config_root: Path,
    alignment_buffering_policy: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Freeze all 18 configs from validated combined development evidence.

    The caller must supply the explicit, passing runtime-anchor qualification
    attestation required by :func:`freeze_all_pipeline_configs`.  This wrapper
    adds no inference and performs no winner selection.
    """

    root = Path(combined_workspace_root).resolve()
    manifest = read_json(root / "campaign_manifest.json")
    analysis = read_json(root / "analysis/analysis.json")
    _validate_combined_pair(manifest, analysis)
    registry = (
        read_json(Path(policy_registry).resolve())
        if isinstance(policy_registry, Path)
        else dict(policy_registry)
    )
    validate_development_policy_registry(registry)
    if registry.get("protocol_id") != manifest.get("full_protocol_id"):
        raise DevelopmentEvidenceError(
            "decision-policy registry belongs to another full protocol"
        )
    if registry.get("development_identity_sha256") != manifest.get(
        "development_identity"
    ):
        raise DevelopmentEvidenceError(
            "decision-policy registry belongs to another development partition"
        )
    result = freeze_all_pipeline_configs(
        policy_registry=registry,
        protocol_id=str(manifest["full_protocol_id"]),
        development_protocol_sha256=str(manifest["development_identity"]),
        development_result_set_sha256=str(
            manifest["development_result_set_sha256"]
        ),
        output_root=Path(frozen_config_root),
        runtime_anchor_qualification=dict(runtime_anchor_qualification),
        alignment_buffering_policy=alignment_buffering_policy,
    )
    return {
        **result,
        "combined_campaign_id": manifest["campaign_id"],
        "combined_campaign_identity_sha256": manifest[
            "campaign_identity_sha256"
        ],
        "development_result_set_sha256": manifest[
            "development_result_set_sha256"
        ],
        "evaluation_material_inspected": False,
        "production_winner_selected": False,
    }


def _validated_source_campaign(
    *,
    role: str,
    expected_mode: str,
    workspace: Path,
    supplied_analysis: Mapping[str, object] | None,
) -> dict[str, object]:
    manifest_path = workspace / "campaign_manifest.json"
    if not manifest_path.is_file():
        raise DevelopmentEvidenceError(f"{role} campaign manifest is missing")
    checked = controller.validate(workspace_root=workspace, verify_audio=False)
    if checked.get("valid") is not True:
        errors = checked.get("errors")
        raise DevelopmentEvidenceError(f"{role} campaign validation failed: {errors}")
    manifest = read_json(manifest_path)
    _validate_source_manifest(manifest, role=role, expected_mode=expected_mode)
    analysis = (
        controller.analyze(workspace_root=workspace)
        if supplied_analysis is None
        else dict(supplied_analysis)
    )
    analysis_path = workspace / "analysis/analysis.json"
    if not analysis_path.is_file():
        raise DevelopmentEvidenceError(f"{role} controller analysis is missing")
    on_disk_analysis = read_json(analysis_path)
    if canonical_json_bytes(analysis) != canonical_json_bytes(on_disk_analysis):
        raise DevelopmentEvidenceError(
            f"supplied {role} analysis differs from the controller artifact"
        )
    _validate_source_analysis(
        analysis,
        manifest=manifest,
        role=role,
        expected_mode=expected_mode,
    )
    reference = {
        "role": role,
        "campaign_id": manifest["campaign_id"],
        "campaign_identity_sha256": _sha256(
            manifest.get("campaign_identity_sha256"),
            f"{role} campaign identity",
        ),
        "campaign_manifest_sha256": sha256_file(manifest_path),
        # Controller analysis contains a creation time and physical result-root
        # paths.  Bind its scientific content, not those machine-local fields,
        # so re-running Analyze cannot change the combined campaign identity.
        "analysis_scientific_sha256": _analysis_scientific_sha256(analysis),
        "measurement_mode": expected_mode,
        "campaign_stage": manifest.get("campaign_stage"),
        "job_count": manifest.get("job_count"),
        "case_count": manifest.get("case_count"),
        "development_only": True,
    }
    return {"manifest": manifest, "analysis": analysis, "reference": reference}


def _validate_source_manifest(
    manifest: Mapping[str, object], *, role: str, expected_mode: str
) -> None:
    expected_pipelines = tuple(matrix().pipeline_ids)
    selected = tuple(str(value) for value in manifest.get("selected_pipeline_ids", ()))
    if selected != expected_pipelines or manifest.get("pipeline_count") != 18:
        raise DevelopmentEvidenceError(f"{role} campaign is not exact all-18")
    modes = tuple(str(value) for value in manifest.get("measurement_modes", ()))
    if modes != (expected_mode,):
        raise DevelopmentEvidenceError(
            f"{role} campaign must contain {expected_mode} jobs only"
        )
    if not str(manifest.get("campaign_stage") or "").startswith("prompt4_"):
        raise DevelopmentEvidenceError(f"{role} campaign is not a Prompt-4 stage")
    jobs = manifest_jobs(manifest)
    if not jobs or len(jobs) != manifest.get("job_count"):
        raise DevelopmentEvidenceError(f"{role} campaign job inventory is incomplete")
    if any(job.split != "development" for job in jobs):
        raise DevelopmentEvidenceError(f"{role} campaign contains held-out jobs")
    if any(job.measurement_mode != expected_mode for job in jobs):
        raise DevelopmentEvidenceError(f"{role} campaign mixes measurement modes")
    if {job.pipeline_id for job in jobs} != set(expected_pipelines):
        raise DevelopmentEvidenceError(f"{role} campaign job coverage is not all-18")
    cases = manifest.get("case_index")
    if not isinstance(cases, Mapping) or not cases:
        raise DevelopmentEvidenceError(f"{role} campaign case index is absent")
    for case_id, raw in cases.items():
        if not isinstance(raw, Mapping):
            raise DevelopmentEvidenceError(f"{role} case {case_id} is invalid")
        split = str(raw.get("split") or raw.get("partition") or "")
        if split != "development":
            raise DevelopmentEvidenceError(
                f"{role} campaign contains held-out case {case_id}"
            )
    parallelism = manifest.get("parallelism_policy")
    if not isinstance(parallelism, Mapping):
        raise DevelopmentEvidenceError(f"{role} parallelism policy is absent")
    if expected_mode == "resources" and parallelism.get(
        "resource_measurement_jobs"
    ) != 1:
        raise DevelopmentEvidenceError(
            "resource evidence is not attested as serial measurement"
        )


def _validate_source_analysis(
    analysis: Mapping[str, object],
    *,
    manifest: Mapping[str, object],
    role: str,
    expected_mode: str,
) -> None:
    if analysis.get("schema_version") != "full-pipeline-evaluation-analysis.v1":
        raise DevelopmentEvidenceError(f"{role} controller analysis schema differs")
    if analysis.get("campaign_id") != manifest.get("campaign_id"):
        raise DevelopmentEvidenceError(f"{role} analysis campaign identity differs")
    raw_rows = analysis.get("rows")
    if not isinstance(raw_rows, list) or not all(
        isinstance(row, Mapping) for row in raw_rows
    ):
        raise DevelopmentEvidenceError(f"{role} analysis rows are invalid")
    rows = [dict(row) for row in raw_rows]
    expected_jobs = {job.job_id: job for job in manifest_jobs(manifest)}
    actual = {str(row.get("job_id") or ""): row for row in rows}
    if len(actual) != len(rows) or set(actual) != set(expected_jobs):
        raise DevelopmentEvidenceError(
            f"{role} analysis does not cover every campaign job exactly once"
        )
    if analysis.get("complete_result_count") != len(expected_jobs):
        raise DevelopmentEvidenceError(f"{role} campaign is not fully complete")
    for job_id, row in actual.items():
        spec = expected_jobs[job_id]
        expected_values = {
            "pipeline_id": spec.pipeline_id,
            "protocol_id": spec.protocol_id,
            "source_key": spec.source_key,
            "split": "development",
            "measurement_mode": expected_mode,
        }
        for field, expected in expected_values.items():
            if row.get(field) != expected:
                raise DevelopmentEvidenceError(
                    f"{role} {job_id}: {field} differs from the manifest"
                )
        _sha256(row.get("result_checksums_sha256"), f"{job_id} result checksum")
        if row.get("evaluation_material_inspected") not in {None, False}:
            raise DevelopmentEvidenceError(
                f"{role} {job_id}: evaluation material was inspected"
            )


def _require_matching_scientific_identities(
    accuracy: Mapping[str, object], resources: Mapping[str, object]
) -> None:
    for field in _IDENTITY_FIELDS:
        if accuracy.get(field) != resources.get(field):
            raise DevelopmentEvidenceError(
                f"accuracy/resource scientific identity differs: {field}"
            )


def _analysis_scientific_sha256(analysis: Mapping[str, object]) -> str:
    core = dict(analysis)
    core.pop("created_at_utc", None)
    raw_rows = core.get("rows")
    if not isinstance(raw_rows, list):
        raise DevelopmentEvidenceError("controller analysis rows are absent")
    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise DevelopmentEvidenceError("controller analysis row is invalid")
        row = dict(raw)
        row.pop("result_root", None)
        rows.append(row)
    core["rows"] = sorted(rows, key=_job_sort_key)
    return sha256_bytes(canonical_json_bytes(core))


def _combined_jobs(
    accuracy: Mapping[str, object],
    resources: Mapping[str, object],
    *,
    accuracy_campaign_id: str,
    resource_campaign_id: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for role, campaign_id, manifest in (
        ("accuracy", accuracy_campaign_id, accuracy),
        ("resources", resource_campaign_id, resources),
    ):
        for job in manifest_jobs(manifest):
            rows.append(
                {
                    **job.to_jsonable(),
                    "source_campaign_role": role,
                    "source_campaign_id": campaign_id,
                }
            )
    _require_unique_job_ids(rows, "source campaign manifests")
    return sorted(rows, key=_job_sort_key)


def _combined_rows(
    accuracy: Mapping[str, object],
    resources: Mapping[str, object],
    *,
    accuracy_campaign_id: str,
    resource_campaign_id: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for role, campaign_id, analysis in (
        ("accuracy", accuracy_campaign_id, accuracy),
        ("resources", resource_campaign_id, resources),
    ):
        raw_rows = analysis.get("rows")
        assert isinstance(raw_rows, list)
        rows.extend(
            {
                **dict(row),
                "source_campaign_role": role,
                "source_campaign_id": campaign_id,
                "evaluation_material_inspected": False,
            }
            for row in raw_rows
            if isinstance(row, Mapping)
        )
    _require_unique_job_ids(rows, "source analyses")
    return sorted(rows, key=_job_sort_key)


def _combined_case_index(
    accuracy: Mapping[str, object], resources: Mapping[str, object]
) -> dict[str, object]:
    combined: dict[str, object] = {}
    for manifest in (accuracy, resources):
        raw = manifest.get("case_index")
        assert isinstance(raw, Mapping)
        for case_id, value in raw.items():
            key = str(case_id)
            if key in combined and canonical_json_bytes(combined[key]) != canonical_json_bytes(
                value
            ):
                raise DevelopmentEvidenceError(
                    f"case {key} differs between accuracy and resource campaigns"
                )
            combined[key] = value
    return dict(sorted(combined.items()))


def _validate_combined_pair(
    manifest: Mapping[str, object], analysis: Mapping[str, object]
) -> None:
    if manifest.get("schema_version") != COMBINED_CAMPAIGN_SCHEMA_VERSION:
        raise DevelopmentEvidenceError("combined campaign schema differs")
    identity = manifest.get("campaign_identity_sha256")
    core = {
        key: value
        for key, value in manifest.items()
        if key
        not in {
            "schema_version",
            "campaign_id",
            "campaign_identity_sha256",
            "pipeline_count",
            "job_count",
            "case_count",
            "parallelism_policy",
            "production_winner_selected",
            "held_out_evaluation_allowed",
            "model_inference_performed_by_combination",
        }
    }
    if sha256_bytes(canonical_json_bytes(core)) != identity:
        raise DevelopmentEvidenceError("combined campaign identity differs")
    if manifest.get("campaign_id") != f"full_pipeline_development_combined_{str(identity)[:12]}":
        raise DevelopmentEvidenceError("combined campaign ID differs")
    if analysis.get("campaign_id") != manifest.get("campaign_id"):
        raise DevelopmentEvidenceError("combined analysis belongs to another campaign")
    rows = analysis.get("rows")
    if not isinstance(rows, list):
        raise DevelopmentEvidenceError("combined analysis rows are absent")
    result_checksums = {
        str(row.get("job_id") or ""): _sha256(
            row.get("result_checksums_sha256"),
            f"{row.get('job_id')} result checksum",
        )
        for row in rows
        if isinstance(row, Mapping)
    }
    if len(result_checksums) != len(rows):
        raise DevelopmentEvidenceError("combined analysis contains duplicate/invalid rows")
    result_identity = sha256_bytes(canonical_json_bytes(result_checksums))
    if result_identity != manifest.get("development_result_set_sha256"):
        raise DevelopmentEvidenceError("combined development result set differs")
    if analysis.get("development_result_set_sha256") != result_identity:
        raise DevelopmentEvidenceError("combined analysis result identity differs")


def _require_unique_job_ids(rows: Sequence[Mapping[str, object]], label: str) -> None:
    values = [str(row.get("job_id") or "") for row in rows]
    if any(not value for value in values) or len(values) != len(set(values)):
        raise DevelopmentEvidenceError(f"{label} contain duplicate/empty job IDs")


def _job_sort_key(row: Mapping[str, object]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("measurement_mode") or ""),
        str(row.get("pipeline_id") or ""),
        str(row.get("protocol_id") or ""),
        str(row.get("source_key") or ""),
        str(row.get("job_id") or ""),
    )


def _write_or_verify(path: Path, value: Mapping[str, object]) -> None:
    destination = Path(path)
    if destination.is_file():
        existing = read_json(destination)
        # ``created_at_utc`` is presentation metadata; permit an idempotent
        # repeat when all scientific and result-bearing fields are identical.
        if destination.name == "analysis.json":
            left = dict(existing)
            right = dict(value)
            left.pop("created_at_utc", None)
            right.pop("created_at_utc", None)
            equal = canonical_json_bytes(left) == canonical_json_bytes(right)
        else:
            equal = canonical_json_bytes(existing) == canonical_json_bytes(value)
        if not equal:
            raise DevelopmentEvidenceError(
                f"immutable combined artifact differs: {destination}"
            )
        return
    write_json_atomic(destination, dict(value))


def _sha256(value: object, label: str) -> str:
    digest = str(value or "").lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise DevelopmentEvidenceError(f"{label} is not SHA-256")
    return digest


__all__ = [
    "COMBINED_ANALYSIS_SCHEMA_VERSION",
    "COMBINED_CAMPAIGN_SCHEMA_VERSION",
    "COMBINED_EVIDENCE_SCHEMA_VERSION",
    "DevelopmentEvidenceError",
    "combine_development_evidence",
    "freeze_development_outputs",
]
