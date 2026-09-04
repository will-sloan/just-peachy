"""Immutable candidate bundles, common-demo overlay, reports, and compact ZIP."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import zipfile
from typing import Mapping, Sequence

import yaml

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline.provenance import runtime_identities
from app.full_pipeline_demo.presets import PresetCatalog
from app.full_pipeline_evaluation.io import checksum_map, sha256_file, write_json_atomic

from . import (
    LICENSE_DOCUMENT,
    MATRIX_PATH,
    PI_SHORTLIST_FILE,
    REPORT_CHECKSUMS_FILE,
    RUNTIME_PATH,
    TOOL_ROOT,
    scope_fields,
)
from .io import (
    HardeningError,
    directory_sha256,
    ensure_c,
    write_bytes_once,
    write_csv,
    write_json_once,
    write_text_once,
)


def package_candidates(
    *,
    workspace_root: Path,
    authorization: Mapping[str, object],
    selection: Mapping[str, object],
    evidence_index: Mapping[str, object],
) -> dict[str, object]:
    root = ensure_c(workspace_root, label="Prompt-7 workspace")
    report_root = root / "report"
    bundle_root = root / "candidate_bundles"
    report_root.mkdir(parents=True, exist_ok=True)
    bundle_root.mkdir(parents=True, exist_ok=True)
    readiness = {
        str(row["pipeline_id"]): bool(row.get("software_ready"))
        for row in evidence_index.get("candidates", [])
        if isinstance(row, Mapping)
    }
    roles = selection.get("roles")
    candidates = selection.get("candidates")
    if not isinstance(roles, Mapping) or not isinstance(candidates, list):
        raise HardeningError("selection roles/candidates are missing")
    selected = {
        str(role): str(pipeline)
        for role, pipeline in roles.items()
        if pipeline is not None
    }
    if not selected or any(
        not readiness.get(pipeline, False) for pipeline in selected.values()
    ):
        raise HardeningError(
            "BLOCKED_PRODUCTION_CANDIDATE: selected candidate is not software-ready"
        )
    frozen = authorization.get("frozen_pipeline_configs")
    if not isinstance(frozen, Mapping):
        raise HardeningError("authorization frozen config reference is missing")
    frozen_root = ensure_c(
        str(frozen.get("path") or ""), label="frozen pipeline configs", must_exist=True
    )
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    presets = PresetCatalog(matrix)
    candidate_rows = {
        str(row["pipeline_id"]): dict(row)
        for row in candidates
        if isinstance(row, Mapping)
    }
    for role, pipeline in selected.items():
        candidate = candidate_rows.get(pipeline)
        if (
            not isinstance(candidate, Mapping)
            or candidate.get("production_role_eligible") is not True
            or candidate.get("runtime_binding_status") != "BOUND_FROZEN_ANCHOR"
        ):
            raise HardeningError(
                f"selected role is not an attested runnable frozen anchor: {role}"
            )
    overlay_rows = []
    for role in ("PRIMARY", "FALLBACK", "ALTERNATIVE"):
        pipeline = selected.get(role)
        if pipeline is None:
            continue
        preset = presets.get(pipeline).to_dict()
        overlay_rows.append(
            {
                "pipeline_id": pipeline,
                "selected_role": role,
                "software_ready": True,
                "production_role_eligible": True,
                "runtime_binding_status": "BOUND_FROZEN_ANCHOR",
                "unknown_only_policy_executed": False,
                "user_friendly_name": preset["display_name"],
                "technical_id": pipeline,
            }
        )
    overlay_path = report_root / "common_demo_production_catalog.yaml"
    _write_yaml_once(
        overlay_path,
        {
            "schema_version": "full-pipeline-common-demo-production-overlay.v1",
            **scope_fields(),
            "status": "PASS",
            "roles": {
                role: selected.get(role)
                for role in ("PRIMARY", "FALLBACK", "ALTERNATIVE")
            },
            "default_pipeline_id": selected["PRIMARY"],
            "presets": overlay_rows,
            "common_demo_overlay_consumed": True,
            "overlay_is_additive": True,
        },
    )
    overlay_sha256 = sha256_file(overlay_path)
    catalog_rows: list[dict[str, object]] = []
    bundle_refs: list[dict[str, object]] = []
    for role in ("PRIMARY", "FALLBACK", "ALTERNATIVE"):
        pipeline = selected.get(role)
        if pipeline is None:
            continue
        candidate = candidate_rows[pipeline]
        binding = candidate.get("runtime_binding")
        if not isinstance(binding, Mapping):
            raise HardeningError(f"candidate runtime binding is absent: {pipeline}")
        selection_row = matrix.resolve(pipeline)
        preset = presets.get(pipeline).to_dict()
        destination = bundle_root / role.casefold()
        destination.mkdir(parents=True, exist_ok=True)
        source_config = frozen_root / f"{pipeline}.yaml"
        if not source_config.is_file():
            raise HardeningError(f"frozen candidate config is missing: {pipeline}")
        _copy_or_verify(source_config, destination / "frozen_pipeline_config.yaml")
        bundle_overlay = destination / "common_demo_production_catalog.yaml"
        _copy_or_verify(overlay_path, bundle_overlay)
        production_preset = {
            "schema_version": "full-pipeline-production-candidate-preset.v1",
            **scope_fields(),
            "pipeline_id": pipeline,
            "technical_id": pipeline,
            "selected_role": role,
            "user_friendly_name": preset["display_name"],
            "protocol_version": selection_row.protocol_version,
            "pipeline_config_sha256": selection_row.pipeline_config_sha256,
            "runtime_config_sha256": selection_row.runtime_config_sha256,
            "frozen_config_path": str(
                (destination / "frozen_pipeline_config.yaml").resolve()
            ),
            "frozen_config_sha256": sha256_file(
                destination / "frozen_pipeline_config.yaml"
            ),
            "scientific_thresholds_changed": False,
            "implicit_downloads_allowed": False,
            "offline_execution_required": True,
            "runtime_binding_status": binding.get("binding_status"),
            "freeze_identity_sha256": binding.get("freeze_identity_sha256"),
            "decision_policy_sha256": binding.get("decision_policy_sha256"),
            "common_demo_overlay_path": "common_demo_production_catalog.yaml",
            "common_demo_overlay_sha256": overlay_sha256,
            "xvf_hooks_enabled": False,
            "fine_tuning_hooks_enabled": False,
        }
        _write_yaml_once(destination / "production_candidate.yaml", production_preset)
        asset_manifest = _asset_manifest(selection_row, binding)
        write_json_once(destination / "asset_manifest.json", asset_manifest)
        write_json_once(
            destination / "environment_manifest.json",
            _environment_manifest(selection_row, binding),
        )
        _write_yaml_once(
            destination / "demo_preset.yaml",
            {
                "schema_version": "full-pipeline-production-demo-preset.v1",
                **scope_fields(),
                "selected_role": role,
                "common_demo_preset": preset,
                "production_overlay_only": True,
                "model_choices_duplicated_in_ui": False,
            },
        )
        baseline = {
            "schema_version": "full-pipeline-production-candidate-baseline.v1",
            **scope_fields(),
            "pipeline_id": pipeline,
            "selected_role": role,
            "software_ready": True,
            "selection_metrics": candidate.get("metrics"),
            "acceptance": next(
                row
                for row in evidence_index["candidates"]
                if isinstance(row, Mapping) and row.get("pipeline_id") == pipeline
            ),
            "thresholds_changed": False,
        }
        write_json_once(destination / "result_baseline.json", baseline)
        write_text_once(
            destination / "launch.ps1",
            _launch_script(
                pipeline,
                root,
                overlay_sha256=overlay_sha256,
            ),
        )
        write_text_once(destination / "validate.ps1", _validate_script(pipeline))
        write_text_once(destination / "health.ps1", _health_script(pipeline, root))
        write_text_once(
            destination / "KNOWN_LIMITATIONS.md",
            _candidate_limitations(role, pipeline, candidate),
        )
        write_text_once(
            destination / "TROUBLESHOOTING.md",
            _candidate_troubleshooting(pipeline),
        )
        checksums = {
            "schema_version": "full-pipeline-production-candidate-checksums.v1",
            **scope_fields(),
            "pipeline_id": pipeline,
            "entries": checksum_map(destination, exclude=("checksums.json",)),
            "model_binaries_included": False,
            "credentials_included": False,
        }
        write_json_atomic(destination / "checksums.json", checksums)
        _validate_bundle(destination, pipeline)
        bundle_refs.append(
            {
                "role": role,
                "pipeline_id": pipeline,
                "path": str(destination.resolve()),
                "checksums_sha256": sha256_file(destination / "checksums.json"),
            }
        )
        catalog_rows.append(
            {
                "pipeline_id": pipeline,
                "role": role,
                "selected_role": role,
                "software_ready": True,
                "production_role_eligible": True,
                "runtime_binding_status": "BOUND_FROZEN_ANCHOR",
                "unknown_only_policy_executed": False,
                "user_friendly_name": preset["display_name"],
                "technical_id": pipeline,
                "license_status": "REVIEW_REQUIRED",
                "license_provenance_status": candidate.get("component_license_risks"),
                "repository_redistribution_status": candidate.get(
                    "repository_redistribution_status"
                ),
                "intended_role": _role_intent(role),
                "selection_reason": _role_reason(role),
                "bundle_path": str(destination.resolve()),
                "bundle_checksums_sha256": sha256_file(destination / "checksums.json"),
            }
        )

    not_worth = [
        {
            "pipeline_id": str(row["pipeline_id"]),
            "reason": str(
                row.get("production_role_ineligibility_reason")
                or row.get("ineligibility_reason")
                or "reliability_constraint_failed"
            ),
        }
        for row in candidates
        if isinstance(row, Mapping) and row.get("production_role_eligible") is not True
    ]
    catalog = {
        "schema_version": "full-pipeline-production-candidate-catalog.v1",
        **scope_fields(),
        "status": "PASS",
        "roles": {
            role: selected.get(role) for role in ("PRIMARY", "FALLBACK", "ALTERNATIVE")
        },
        "candidates": catalog_rows,
        "candidate_count": len(catalog_rows),
        "not_worth_continuing": not_worth,
        "technical_and_licensing_rankings_separate": True,
        "weighted_score_used": False,
        "final_beaker_hardware_readiness_claimed": False,
    }
    _write_yaml_once(report_root / "production_candidate_catalog.yaml", catalog)
    write_csv(report_root / "production_candidate_summary.csv", catalog_rows)
    _write_ranking_outputs(report_root, candidates)
    write_json_once(
        report_root / "licensing_provenance.json",
        {
            "schema_version": "full-pipeline-production-licensing-provenance.v1",
            **scope_fields(),
            "license_document": {
                "path": str(LICENSE_DOCUMENT.resolve()),
                "sha256": sha256_file(LICENSE_DOCUMENT),
            },
            "candidates": catalog_rows,
            "technical_ranking_used_as_legal_conclusion": False,
            "repository_redistribution_status": "UNRESOLVED_NO_REPOSITORY_LICENSE_FILE",
        },
    )
    for role in ("PRIMARY", "FALLBACK", "ALTERNATIVE"):
        pipeline = selected.get(role)
        write_text_once(
            report_root / f"{role}_PIPELINE.md",
            _role_document(role, pipeline, candidate_rows.get(pipeline or "")),
        )
    _write_program_docs(report_root, catalog_rows, root)
    shortlist_path = report_root / PI_SHORTLIST_FILE
    from .controller import _evidence_files
    from .pi_shortlist import build_pi_shortlist

    shortlist = build_pi_shortlist(
        authorization=authorization,
        desktop_selection=selection,
        evidence_files=_evidence_files(authorization),
        desktop_roles_source=report_root / "production_candidate_catalog.yaml",
    )
    write_json_once(shortlist_path, shortlist)
    report_checksums_path = report_root / REPORT_CHECKSUMS_FILE
    write_json_atomic(
        report_checksums_path,
        {
            "schema_version": "full-pipeline-production-report-checksums.v1",
            **scope_fields(),
            "status": "PASS",
            "entries": checksum_map(
                report_root,
                exclude=(REPORT_CHECKSUMS_FILE,),
            ),
            "raspberry_pi_candidate_shortlist": {
                "path": str(shortlist_path.resolve()),
                "sha256": sha256_file(shortlist_path),
            },
        },
    )
    package = root / "packages/full_pipeline_production_candidates_reduced_8day_v1.zip"
    _compact_zip(root, package)
    value = {
        "schema_version": "full-pipeline-production-candidate-packaging.v1",
        **scope_fields(),
        "status": "PASS",
        "catalog_path": str(
            (report_root / "production_candidate_catalog.yaml").resolve()
        ),
        "candidate_bundles": bundle_refs,
        "compact_zip_path": str(package.resolve()),
        "compact_zip_sha256": sha256_file(package),
        "common_demo_overlay_path": str(overlay_path.resolve()),
        "common_demo_overlay_sha256": overlay_sha256,
        "raspberry_pi_candidate_shortlist": {
            "path": str(shortlist_path.resolve()),
            "sha256": sha256_file(shortlist_path),
        },
        "report_checksums": {
            "path": str(report_checksums_path.resolve()),
            "sha256": sha256_file(report_checksums_path),
        },
        "raw_audio_included": False,
        "model_binaries_included": False,
        "credentials_included": False,
        "biometric_vectors_included": False,
    }
    write_json_atomic(root / "packaging.json", value)
    return value


def validate_candidate_bundle(
    root: Path, *, pipeline_id: str | None = None
) -> dict[str, object]:
    bundle = ensure_c(root, label="candidate bundle", must_exist=True)
    preset = yaml.safe_load(
        (bundle / "production_candidate.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(preset, Mapping):
        raise HardeningError("candidate preset is invalid")
    observed = str(preset.get("pipeline_id") or "")
    if pipeline_id is not None and observed != pipeline_id:
        raise HardeningError("candidate bundle pipeline ID differs")
    _validate_bundle(bundle, observed)
    return {
        "schema_version": "full-pipeline-production-candidate-validation.v1",
        **scope_fields(),
        "status": "PASS",
        "pipeline_id": observed,
        "bundle_root": str(bundle),
        "checksums_sha256": sha256_file(bundle / "checksums.json"),
    }


def _asset_manifest(
    selection: object, binding: Mapping[str, object]
) -> dict[str, object]:
    components = {
        "asr": dict(selection.asr),
        "anonymous_diarization": dict(selection.diarization),
        "diarization_embedding": dict(selection.diarization_embedding),
        "identity": dict(selection.identity),
    }
    return {
        "schema_version": "full-pipeline-production-candidate-assets.v1",
        **scope_fields(),
        "pipeline_id": selection.pipeline_id,
        "components": components,
        "runtime_component_identities": {
            key: value.to_contract()
            for key, value in runtime_identities(
                selection,
                evaluation_root=TOOL_ROOT,
            ).items()
        },
        "frozen_runtime_component_identities": binding.get(
            "runtime_component_identities"
        ),
        "external_asset_attestations": binding.get("external_assets"),
        "frozen_config_sha256": binding.get("frozen_config_sha256"),
        "freeze_identity_sha256": binding.get("freeze_identity_sha256"),
        "decision_policy_sha256": binding.get("decision_policy_sha256"),
        "implicit_downloads_allowed": False,
        "offline_execution_required": True,
        "model_binaries_packaged": False,
        "assets_must_exist_before_launch": True,
    }


def _environment_manifest(
    selection: object, binding: Mapping[str, object]
) -> dict[str, object]:
    profiles = sorted(
        {
            str(component.get("environment_profile"))
            for component in (
                selection.asr,
                selection.diarization,
                selection.diarization_embedding,
                selection.identity,
            )
            if component.get("environment_profile")
        }
    )
    return {
        "schema_version": "full-pipeline-production-candidate-environments.v1",
        **scope_fields(),
        "pipeline_id": selection.pipeline_id,
        "coordinator_environment": "repository_.venv",
        "isolated_environment_profiles": profiles,
        "component_environment_declarations": {
            key: {
                field: component.get(field)
                for field in (
                    "environment_profile",
                    "segmentation_environment_profile",
                    "embedding_environment_profile",
                    "requirements_path",
                    "requirements_sha256",
                    "package_identity",
                    "implementation_path",
                )
                if component.get(field) is not None
            }
            for key, component in {
                "asr": selection.asr,
                "anonymous_diarization": selection.diarization,
                "diarization_embedding": selection.diarization_embedding,
                "identity": selection.identity,
            }.items()
        },
        "implicit_environment_creation_allowed": False,
        "environment_interpreter_attestations": binding.get("environment_interpreters"),
        "network_downloads_allowed": False,
        "offline_environment_flags": {
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "JP_OFFLINE_NO_DOWNLOAD": "1",
        },
    }


def _write_ranking_outputs(root: Path, candidates: Sequence[object]) -> None:
    rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    technical = [
        {
            **scope_fields(),
            "pipeline_id": row["pipeline_id"],
            "rank": row.get("technical_rank"),
            "reliability_eligible": row.get("reliability_eligible"),
            "reason": row.get("ineligibility_reason")
            or "ordered_priority_and_pareto_policy",
            "basis": "full_pipeline_constraint_pareto_selection.v1 priorities 1-12; no composite score",
        }
        for row in sorted(
            rows,
            key=lambda item: (
                int(item.get("technical_rank") or 999),
                str(item["pipeline_id"]),
            ),
        )
    ]
    licensing = [
        {
            **scope_fields(),
            "pipeline_id": row["pipeline_id"],
            "rank": row.get("licensing_rank"),
            "deployment_status": "REVIEW_REQUIRED",
            "readiness_class": "UNRESOLVED_REPOSITORY_AND_COMPONENT_REVIEW",
            "basis": row.get("component_license_risks"),
        }
        for row in sorted(
            rows,
            key=lambda item: (
                int(item.get("licensing_rank") or 999),
                str(item["pipeline_id"]),
            ),
        )
    ]
    pareto = [
        {
            **scope_fields(),
            "pipeline_id": row["pipeline_id"],
            "on_frontier": row.get("pareto_frontier", False),
            "reason": (
                "nondominated_on_predeclared_metrics"
                if row.get("pareto_frontier")
                else "dominated_or_reliability_ineligible"
            ),
        }
        for row in rows
    ]
    write_csv(root / "technical_ranking.csv", technical)
    write_csv(root / "licensing_ranking.csv", licensing)
    write_csv(root / "pareto_frontier.csv", pareto)


def _launch_script(
    pipeline: str,
    root: Path,
    *,
    overlay_sha256: str,
) -> str:
    wrapper = TOOL_ROOT / "scripts/run_full_pipeline_demo.ps1"
    return f'''[CmdletBinding()]
param(
    [ValidateSet("Demo","File","Live","EnrollImport")][string]$Mode = "Demo",
    [string]$InputPath,
    [string]$Device,
    [double]$DurationSec = 30,
    [string]$ExportRoot,
    [string]$EnrollmentRoot,
    [string]$DisplayName,
    [string]$SpeakerId,
    [string]$Wav1,
    [string]$Wav2,
    [string]$Wav3
)
$ErrorActionPreference = "Stop"
$wrapper = "{wrapper}"
& "$PSScriptRoot\\validate.ps1"
$env:JP_FULL_PIPELINE_PRODUCTION_CATALOG = "$PSScriptRoot\\common_demo_production_catalog.yaml"
$env:JP_FULL_PIPELINE_PRODUCTION_CATALOG_SHA256 = "{overlay_sha256}"
if ($Mode -eq "Demo") {{ & $wrapper -Action Demo; exit $LASTEXITCODE }}
if ($Mode -eq "File") {{ & $wrapper -Action File -PipelineId "{pipeline}" -InputPath $InputPath -DurationSec $DurationSec -ExportRoot $ExportRoot -EnrollmentRoot $EnrollmentRoot; exit $LASTEXITCODE }}
if ($Mode -eq "Live") {{ & $wrapper -Action Live -PipelineId "{pipeline}" -Device $Device -DurationSec $DurationSec -ExportRoot $ExportRoot -EnrollmentRoot $EnrollmentRoot; exit $LASTEXITCODE }}
if ($Mode -eq "EnrollImport") {{ & $wrapper -Action EnrollImport -PipelineId "{pipeline}" -DisplayName $DisplayName -SpeakerId $SpeakerId -Wav1 $Wav1 -Wav2 $Wav2 -Wav3 $Wav3 -EnrollmentRoot $EnrollmentRoot; exit $LASTEXITCODE }}
'''


def _validate_script(pipeline: str) -> str:
    python = TOOL_ROOT.parents[1] / ".venv/Scripts/python.exe"
    return f'''$ErrorActionPreference = "Stop"
& "{python}" -m app.full_pipeline_production_hardening validate-bundle --bundle-root "$PSScriptRoot" --pipeline-id "{pipeline}"
exit $LASTEXITCODE
'''


def _health_script(pipeline: str, root: Path) -> str:
    wrapper = TOOL_ROOT / "scripts/run_full_pipeline_production_hardening.ps1"
    return f'''$ErrorActionPreference = "Stop"
& "{wrapper}" -Action Health -WorkspaceRoot "{root}" -PipelineId "{pipeline}"
exit $LASTEXITCODE
'''


def _candidate_limitations(
    role: str, pipeline: str, candidate: Mapping[str, object]
) -> str:
    return f"""# Known limitations — {role} / {pipeline}

- This is a bounded desktop software candidate, not final Beaker hardware readiness.
- Real XVF metadata, energy, AoA, and processed-audio integration remain disabled.
- Fine-tuning hooks exist only as future handoff points and remain disabled.
- Frozen scientific thresholds were not changed; real-device recalibration may require a new protocol.
- Repository redistribution rights remain unresolved because the repository has no project-level license.
- Component review flags: `{json.dumps(candidate.get("component_license_risks"), sort_keys=True)}`.
- Model binaries, credentials, audio, and biometric vectors are not packaged.
"""


def _candidate_troubleshooting(pipeline: str) -> str:
    return f"""# Troubleshooting — {pipeline}

Run `validate.ps1` before launch. A failure is actionable evidence; do not download or
substitute a model implicitly. Verify the recorded environment profiles, exact asset
hashes, C: free-space reserve, microphone format/device, and enrollment backend/model
identity. Use `health.ps1` for a model-free bundle/status check. A stopped session is
restartable; preserve its failure log and start a new immutable session.
"""


def _role_document(
    role: str, pipeline: str | None, candidate: Mapping[str, object] | None
) -> str:
    if pipeline is None:
        return f"# {role.title()} pipeline\n\nThis optional role was intentionally left unfilled because no additional candidate added defensible value.\n"
    return f"""# {role.title()} pipeline

- Pipeline: `{pipeline}`
- Intended role: {_role_intent(role)}
- Selection basis: {_role_reason(role)}
- Technical rank: `{candidate.get("technical_rank") if candidate else None}`
- Licensing rank: `{candidate.get("licensing_rank") if candidate else None}`
- Software-ready under bounded Prompt 7: **yes**
- Final Beaker hardware-ready: **not claimed**
- Thresholds changed: **no**
"""


def _write_program_docs(
    root: Path, rows: Sequence[Mapping[str, object]], workspace: Path
) -> None:
    role_lines = "\n".join(
        f"- {row['selected_role']}: run `{row['bundle_path']}\\launch.ps1`; "
        f"technical ID `{row['pipeline_id']}`."
        for row in rows
    )
    primary = next(
        str(row["bundle_path"]) for row in rows if row["selected_role"] == "PRIMARY"
    )
    write_text_once(
        root / "DEMO_RUNBOOK.md",
        f"""# Production-candidate demo runbook

{role_lines}

All modes reuse the common demo/runtime. No UI owns model inference. Example with
the primary bundle:

```powershell
$bundle = "{primary}"
& "$bundle\\validate.ps1"
& "$bundle\\launch.ps1" -Mode Demo
& "$bundle\\launch.ps1" -Mode File -InputPath "C:\\audio\\session.wav" -DurationSec 0 -ExportRoot "{workspace}\\manual_exports\\file"
& "$bundle\\launch.ps1" -Mode Live -Device "<device-id>" -DurationSec 30 -ExportRoot "{workspace}\\manual_exports\\live"
& "$bundle\\launch.ps1" -Mode EnrollImport -DisplayName "Alice" -SpeakerId "alice" -Wav1 "prompt_1=C:\\audio\\alice1.wav" -Wav2 "prompt_2=C:\\audio\\alice2.wav" -Wav3 "prompt_3=C:\\audio\\alice3.wav" -EnrollmentRoot "{workspace}\\manual_profiles"
& "$bundle\\health.ps1"
```

The demo supports file simulation, live microphone selection, local enrollment,
profile invalidation by backend/checkpoint, and labelled transcript/session export.
Model downloads remain disabled.
""",
    )
    write_text_once(
        root / "TROUBLESHOOTING.md",
        """# Production-candidate troubleshooting

Validate bundle checksums first. Preserve failures, never replace assets implicitly,
and use the restart-safe Prompt-7 controller after interruption. Check C: reserve,
isolated environments, exact model/checkpoint hashes, input devices, profile binding,
queue pressure, and clean worker shutdown. Licensing review is separate from runtime.
""",
    )
    write_text_once(
        root / "VALIDATION_CHECKLIST.md",
        """# Validation checklist

- [x] Two identical five-minute deterministic replays per selected candidate
- [x] Ten-minute controlled loopback/prerecorded-live-path run per candidate
- [x] Enrollment, backend/checkpoint invalidation, and export
- [x] Five repeated two-minute sessions per candidate
- [x] One sixty-minute soak per candidate
- [x] Six recovery faults per candidate
- [x] Startup self-test, health/status, restart, and clean shutdown
- [x] Frozen thresholds/config hashes unchanged
- [x] Model binaries, credentials, raw audio, and biometric vectors excluded
- [x] XVF and fine-tuning hooks disabled
""",
    )


def _role_intent(role: str) -> str:
    return {
        "PRIMARY": "best bounded safety/accuracy and user-experience architecture",
        "FALLBACK": "resource-efficient safety-nondominated fallback",
        "ALTERNATIVE": "cleaner-provenance or scientifically distinct alternative",
    }[role]


def _role_reason(role: str) -> str:
    return {
        "PRIMARY": "first reliable Pareto candidate under frozen ordered priorities",
        "FALLBACK": "lowest measured resource tuple among remaining safety-nondominated Pareto candidates",
        "ALTERNATIVE": "adds measured architectural/provenance value without duplicating another role",
    }[role]


def _validate_bundle(root: Path, pipeline: str) -> None:
    required = {
        "frozen_pipeline_config.yaml",
        "common_demo_production_catalog.yaml",
        "production_candidate.yaml",
        "asset_manifest.json",
        "environment_manifest.json",
        "demo_preset.yaml",
        "result_baseline.json",
        "launch.ps1",
        "validate.ps1",
        "health.ps1",
        "KNOWN_LIMITATIONS.md",
        "TROUBLESHOOTING.md",
        "checksums.json",
    }
    observed_files = {path.name for path in root.iterdir() if path.is_file()}
    if observed_files != required:
        raise HardeningError(
            "candidate bundle file inventory differs: "
            f"missing={sorted(required - observed_files)} "
            f"extra={sorted(observed_files - required)}"
        )
    checksums_path = root / "checksums.json"
    value = json.loads(checksums_path.read_text(encoding="utf-8"))
    if (
        value.get("schema_version") != "full-pipeline-production-candidate-checksums.v1"
        or value.get("pipeline_id") != pipeline
        or any(value.get(key) != item for key, item in scope_fields().items())
    ):
        raise HardeningError("candidate checksum pipeline differs")
    if value.get("entries") != checksum_map(root, exclude=("checksums.json",)):
        raise HardeningError("candidate bundle checksum map differs")
    preset = yaml.safe_load(
        (root / "production_candidate.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(preset, Mapping):
        raise HardeningError("candidate preset is not an object")
    if (
        preset.get("schema_version") != "full-pipeline-production-candidate-preset.v1"
        or preset.get("pipeline_id") != pipeline
        or any(preset.get(key) != item for key, item in scope_fields().items())
        or preset.get("scientific_thresholds_changed") is not False
        or preset.get("implicit_downloads_allowed") is not False
        or preset.get("offline_execution_required") is not True
        or preset.get("runtime_binding_status") != "BOUND_FROZEN_ANCHOR"
    ):
        raise HardeningError("candidate preset claims a threshold change")
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    current = matrix.resolve(pipeline)
    if (
        preset.get("pipeline_config_sha256") != current.pipeline_config_sha256
        or preset.get("runtime_config_sha256") != current.runtime_config_sha256
    ):
        raise HardeningError("candidate preset no longer matches matrix/runtime")
    frozen_path = root / "frozen_pipeline_config.yaml"
    if preset.get("frozen_config_sha256") != sha256_file(frozen_path):
        raise HardeningError("candidate frozen config checksum differs")
    overlay_path = root / str(preset.get("common_demo_overlay_path") or "")
    try:
        overlay_path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise HardeningError("candidate demo overlay escaped the bundle") from exc
    if not overlay_path.is_file() or preset.get(
        "common_demo_overlay_sha256"
    ) != sha256_file(overlay_path):
        raise HardeningError("candidate demo overlay checksum differs")
    overlay = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
    overlay_rows = overlay.get("presets") if isinstance(overlay, Mapping) else None
    if (
        not isinstance(overlay, Mapping)
        or overlay.get("schema_version")
        != "full-pipeline-common-demo-production-overlay.v1"
        or overlay.get("status") != "PASS"
        or any(overlay.get(key) != item for key, item in scope_fields().items())
        or not isinstance(overlay_rows, list)
        or not any(
            isinstance(row, Mapping)
            and row.get("pipeline_id") == pipeline
            and row.get("software_ready") is True
            for row in overlay_rows
        )
    ):
        raise HardeningError("candidate demo overlay contract differs")
    frozen = yaml.safe_load(frozen_path.read_text(encoding="utf-8")) or {}
    if not isinstance(frozen, Mapping):
        raise HardeningError("candidate frozen config is invalid")
    frozen_core = {
        str(key): item
        for key, item in frozen.items()
        if str(key) != "freeze_identity_sha256"
    }
    from app.full_pipeline_evaluation.io import canonical_json_bytes, sha256_bytes

    if (
        frozen.get("pipeline_id") != pipeline
        or frozen.get("freeze_identity_sha256")
        != sha256_bytes(canonical_json_bytes(frozen_core))
        or preset.get("freeze_identity_sha256") != frozen.get("freeze_identity_sha256")
        or preset.get("decision_policy_sha256")
        != dict(frozen.get("identity_policy") or {}).get("decision_policy_sha256")
    ):
        raise HardeningError("candidate frozen config identity differs")
    assets = json.loads((root / "asset_manifest.json").read_text(encoding="utf-8"))
    if (
        assets.get("schema_version") != "full-pipeline-production-candidate-assets.v1"
        or assets.get("pipeline_id") != pipeline
        or assets.get("implicit_downloads_allowed") is not False
        or assets.get("offline_execution_required") is not True
    ):
        raise HardeningError("candidate asset manifest differs")
    references = assets.get("external_asset_attestations")
    if not isinstance(references, list) or not references:
        raise HardeningError("candidate external asset attestations are absent")
    for raw in references:
        if not isinstance(raw, Mapping):
            raise HardeningError("candidate external asset row is invalid")
        path = ensure_c(
            str(raw.get("path") or ""),
            label="candidate external asset",
            must_exist=True,
        )
        scope = str(raw.get("sha256_scope") or "")
        observed = directory_sha256(path) if scope == "tree" else sha256_file(path)
        if scope not in {"tree", "file"} or observed != raw.get("sha256"):
            raise HardeningError(f"candidate external asset differs: {path}")
    environment = json.loads(
        (root / "environment_manifest.json").read_text(encoding="utf-8")
    )
    if (
        environment.get("schema_version")
        != "full-pipeline-production-candidate-environments.v1"
        or environment.get("pipeline_id") != pipeline
        or environment.get("network_downloads_allowed") is not False
        or environment.get("implicit_environment_creation_allowed") is not False
    ):
        raise HardeningError("candidate environment manifest differs")
    interpreters = environment.get("environment_interpreter_attestations")
    if not isinstance(interpreters, list) or not interpreters:
        raise HardeningError(
            "candidate environment interpreter attestations are absent"
        )
    for raw in interpreters:
        if not isinstance(raw, Mapping):
            raise HardeningError("candidate environment interpreter row is invalid")
        path = ensure_c(
            str(raw.get("interpreter_path") or ""),
            label="candidate environment interpreter",
            must_exist=True,
        )
        if raw.get("interpreter_sha256") != sha256_file(path):
            raise HardeningError(f"candidate environment interpreter differs: {path}")


def _write_yaml_once(path: Path, value: Mapping[str, object]) -> Path:
    payload = yaml.safe_dump(dict(value), sort_keys=False, allow_unicode=True).encode(
        "utf-8"
    )
    return write_bytes_once(path, payload)


def _copy_or_verify(source: Path, destination: Path) -> None:
    if destination.is_file():
        if sha256_file(source) != sha256_file(destination):
            raise HardeningError(f"immutable candidate copy differs: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _compact_zip(root: Path, destination: Path) -> None:
    allowed_roots = (root / "report", root / "candidate_bundles")
    files = [
        path
        for allowed in allowed_roots
        for path in allowed.rglob("*")
        if path.is_file()
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    with zipfile.ZipFile(
        temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(files, key=lambda item: item.as_posix()):
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    os.replace(temporary, destination)
    _validate_compact_zip(root, destination, files)


def _validate_compact_zip(
    root: Path, destination: Path, source_files: Sequence[Path]
) -> None:
    payload = destination.read_bytes()
    end_signature = b"PK\x05\x06"
    end_offset = payload.rfind(end_signature)
    if end_offset < 0 or end_offset + 22 > len(payload):
        raise HardeningError("compact ZIP end record is absent")
    comment_size = int.from_bytes(payload[end_offset + 20 : end_offset + 22], "little")
    if end_offset + 22 + comment_size != len(payload):
        raise HardeningError("compact ZIP contains trailing/unbound bytes")
    expected = {
        path.relative_to(root).as_posix(): path.read_bytes() for path in source_files
    }
    prohibited_suffixes = {
        ".wav",
        ".flac",
        ".mp3",
        ".pt",
        ".pth",
        ".ckpt",
        ".onnx",
        ".bin",
        ".npz",
        ".npy",
    }
    with zipfile.ZipFile(destination, "r") as archive:
        names = archive.namelist()
        if names != sorted(expected):
            raise HardeningError("compact ZIP member inventory/order differs")
        for name in names:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise HardeningError(f"compact ZIP contains unsafe path: {name}")
            if path.suffix.casefold() in prohibited_suffixes:
                raise HardeningError(f"compact ZIP contains prohibited payload: {name}")
            lowered = name.casefold()
            if any(
                token in lowered
                for token in ("credentials.json", "token.json", ".env", "id_rsa")
            ):
                raise HardeningError(
                    f"compact ZIP contains credential-like file: {name}"
                )
            if archive.read(name) != expected[name]:
                raise HardeningError(f"compact ZIP member bytes differ: {name}")


def validate_compact_package(
    workspace_root: Path, destination: Path
) -> dict[str, object]:
    root = ensure_c(workspace_root, label="Prompt-7 workspace", must_exist=True)
    package = ensure_c(destination, label="Prompt-7 compact ZIP", must_exist=True)
    files = [
        path
        for allowed in (root / "report", root / "candidate_bundles")
        for path in allowed.rglob("*")
        if path.is_file()
    ]
    _validate_compact_zip(root, package, files)
    return {
        "status": "PASS",
        "path": str(package),
        "sha256": sha256_file(package),
        "member_count": len(files),
    }


__all__ = [
    "package_candidates",
    "validate_candidate_bundle",
    "validate_compact_package",
]
