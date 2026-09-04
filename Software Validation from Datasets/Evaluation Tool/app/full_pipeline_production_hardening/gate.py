"""Prompt-5/6 scientific-evidence and Prompt-7 input admission gate."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping
import wave

import yaml

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline.provenance import runtime_identities
from app.full_pipeline_development.freeze import _model_asset_identity
from app.full_pipeline_development.policies import (
    audit_frozen_anchor_policies,
    resolve_decision_policy_contract,
    validate_development_policy_registry,
)
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    sha256_bytes,
)
from app.full_pipeline_deployment_evidence import (
    DeploymentEvidenceError,
    load_deployment_steering,
    steering_ref,
    validate_deployment_evidence_document,
)

from . import (
    ANCHOR_PIPELINES,
    DEFAULT_AMENDMENT,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    LICENSE_DOCUMENT,
    MATRIX_PATH,
    PROMPT5_MARKER,
    PROMPT5_REQUIRED_FILES,
    PROMPT6_MARKER,
    PROMPT6_REQUIRED_FILES,
    PROMPT7_MARKER,
    PI_DEPLOYMENT_STEERING_SHA256,
    RUNTIME_PATH,
    SCOPE_CLASS,
    SCOPE_ID,
    SELECTION_POLICY_DOCUMENT,
    scope_fields,
)
from .io import (
    HardeningError,
    directory_sha256,
    ensure_c,
    read_json,
    sha256_file,
)
from .universal import CompletionEvidence, single_artifact, validate_completion


def validate_prerequisites(
    *,
    prompt6_marker: Path | str,
    prompt5_marker: Path | str | None = None,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    state_path = ensure_c(
        program_state_path, label="full-pipeline program state", must_exist=True
    )
    state = read_json(state_path)
    _validate_state(state)
    prompt5_path = _prompt5_path(prompt5_marker, state)
    p5 = validate_completion(
        prompt5_path,
        prompt_index=5,
        marker=PROMPT5_MARKER,
        required_basenames=PROMPT5_REQUIRED_FILES,
    )
    p6 = validate_completion(
        prompt6_marker,
        prompt_index=6,
        marker=PROMPT6_MARKER,
        required_basenames=PROMPT6_REQUIRED_FILES,
    )
    _validate_chain(p5, p6)
    _validate_state_bindings(state, p5=p5, p6=p6)
    amendment_file = ensure_c(
        amendment_path, label="eight-day amendment", must_exist=True
    )
    _validate_amendment(read_json(amendment_file))
    authorization_path = single_artifact(p5, "prompt5_authorization.json")
    authorization = read_json(authorization_path)
    (
        extended_set,
        extended_set_reference,
        frozen,
        registry,
        runtime_bindings,
    ) = _validate_prompt5_authorization(authorization)
    hardening_inputs = _validate_hardening_inputs(
        single_artifact(p6, "hardening_input_manifest.json")
    )
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    if set(extended_set) - set(matrix.pipeline_ids):
        raise HardeningError("predeclared extended set contains an unknown pipeline")
    deployment = _validate_deployment_inputs(
        p5=p5,
        p6=p6,
        extended_pipeline_ids=extended_set,
        matrix=matrix,
        steering_path=pi_deployment_steering_path,
        extended_set_reference=extended_set_reference,
    )
    core = {
        "schema_version": "full-pipeline-production-hardening-authorization.v1",
        **scope_fields(),
        "status": "AUTHORIZED_NOT_STARTED",
        "prompt5_completion": _completion_ref(p5),
        "prompt6_completion": _completion_ref(p6),
        "program_state": {"path": str(state_path), "sha256": sha256_file(state_path)},
        "amendment": {
            "path": str(amendment_file),
            "sha256": sha256_file(amendment_file),
        },
        "selection_policy": {
            "policy_id": "full_pipeline_constraint_pareto_selection.v1",
            "path": str(SELECTION_POLICY_DOCUMENT.resolve()),
            "sha256": sha256_file(SELECTION_POLICY_DOCUMENT),
            "weighted_score_used": False,
        },
        "license_evidence": {
            "path": str(LICENSE_DOCUMENT.resolve()),
            "sha256": sha256_file(LICENSE_DOCUMENT),
            "technical_ranking_separate": True,
        },
        "matrix": {
            **matrix.status(),
            "path": str(MATRIX_PATH.resolve()),
            "sha256": sha256_file(MATRIX_PATH),
        },
        "predeclared_extended_pipeline_ids": extended_set,
        "predeclared_extended_set": extended_set_reference,
        "six_anchor_pipeline_ids": list(ANCHOR_PIPELINES),
        "frozen_pipeline_configs": frozen,
        "decision_policy_registry": registry,
        "runtime_candidate_bindings": runtime_bindings,
        "hardening_inputs": hardening_inputs,
        "deployment_steering": deployment["steering_reference"],
        "prompt5_deployment_evidence": deployment["prompt5_reference"],
        "prompt6_deployment_evidence": deployment["prompt6_reference"],
        "deployment_input_binding": deployment["input_binding"],
        "held_out_thresholds_changed": False,
        "fine_tuning_hooks_enabled": False,
        "xvf_hooks_enabled": False,
        "outcomes_opened_by_gate": False,
    }
    from app.full_pipeline_evaluation.io import canonical_json_bytes, sha256_bytes

    return {
        **core,
        "authorization_identity_sha256": sha256_bytes(canonical_json_bytes(core)),
    }


def _validate_deployment_inputs(
    *,
    p5: CompletionEvidence,
    p6: CompletionEvidence,
    extended_pipeline_ids: list[str],
    matrix: FullPipelineMatrix,
    steering_path: Path | str,
    extended_set_reference: Mapping[str, str],
) -> dict[str, object]:
    """Admit exact checksum-manifest-discovered P5/P6 deployment evidence."""

    steering_file = ensure_c(
        steering_path,
        label="Raspberry Pi deployment steering",
        must_exist=True,
    )
    try:
        steering = load_deployment_steering(
            steering_file,
            expected_prompt_index=7,
            expected_sha256=PI_DEPLOYMENT_STEERING_SHA256,
        )
    except DeploymentEvidenceError as exc:
        raise HardeningError(f"deployment steering validation failed: {exc}") from exc
    steering_reference = steering_ref(steering_file, steering)
    p5_path = single_artifact(p5, "all18_deployment_evidence.json")
    p6_path = single_artifact(p6, "extended_deployment_evidence.json")
    p5_reference = {"path": str(p5_path), "sha256": sha256_file(p5_path)}
    p6_reference = {"path": str(p6_path), "sha256": sha256_file(p6_path)}
    try:
        p5_document = validate_deployment_evidence_document(
            read_json(p5_path),
            schema_version="full-pipeline-all18-deployment-evidence.v1",
            prompt_index=5,
            expected_pipeline_ids=matrix.pipeline_ids,
            steering=steering,
        )
        p6_document = validate_deployment_evidence_document(
            read_json(p6_path),
            schema_version="full-pipeline-extended-deployment-evidence.v1",
            prompt_index=6,
            expected_pipeline_ids=extended_pipeline_ids,
            steering=steering,
        )
    except DeploymentEvidenceError as exc:
        raise HardeningError(
            f"upstream deployment evidence validation failed: {exc}"
        ) from exc
    if (
        p5_document.get("steering_authority") != steering_reference
        or p6_document.get("steering_authority") != steering_reference
    ):
        raise HardeningError("upstream deployment steering references differ")
    if p6_document.get("prompt5_deployment_evidence") != p5_reference:
        raise HardeningError("Prompt-6 deployment evidence does not bind Prompt 5")
    predeclared = p6_document.get("predeclared_membership")
    if (
        not isinstance(predeclared, Mapping)
        or predeclared.get("pipeline_ids") != extended_pipeline_ids
        or int(predeclared.get("pipeline_count") or -1) != len(extended_pipeline_ids)
        or predeclared.get("membership_changed_after_heldout") is not False
        or predeclared.get("deployment_evidence_used_as_filter") is not False
    ):
        raise HardeningError("Prompt-6 deployment membership binding differs")
    return {
        "steering_reference": steering_reference,
        "prompt5_reference": p5_reference,
        "prompt6_reference": p6_reference,
        "input_binding": {
            "deployment_steering_path": steering_reference["path"],
            "deployment_steering_sha256": steering_reference["sha256"],
            "deployment_steering_schema_version": steering_reference["schema_version"],
            "deployment_steering_id": steering_reference["steering_id"],
            "deployment_steering_status": steering_reference["status"],
            "prompt5_deployment_evidence_path": p5_reference["path"],
            "prompt5_deployment_evidence_sha256": p5_reference["sha256"],
            "prompt6_deployment_evidence_path": p6_reference["path"],
            "prompt6_deployment_evidence_sha256": p6_reference["sha256"],
            "predeclared_extended_set_path": extended_set_reference["path"],
            "predeclared_extended_set_sha256": extended_set_reference["sha256"],
        },
    }


def _validate_state(value: Mapping[str, object]) -> None:
    if (
        value.get("scope_id") != SCOPE_ID
        or value.get("scope_class") != SCOPE_CLASS
        or value.get("original_full_scope_complete") is not False
    ):
        raise HardeningError("PROGRAM_STATE bounded scope differs")
    if value.get("status") != PROMPT6_MARKER:
        raise HardeningError("PROGRAM_STATE has not reached bounded Prompt 6")
    if int(value.get("current_prompt_index") or -1) != 6:
        raise HardeningError("PROGRAM_STATE current_prompt_index is not 6")
    if [int(item) for item in value.get("remaining_prompt_indices", [])] != [7, 8]:
        raise HardeningError("PROGRAM_STATE remaining prompts are not [7, 8]")
    completion = value.get("completion_state")
    if not isinstance(completion, Mapping):
        raise HardeningError("PROGRAM_STATE completion_state is absent")
    if completion.get("prompt_5") != PROMPT5_MARKER:
        raise HardeningError("PROGRAM_STATE Prompt-5 marker differs")
    if completion.get("prompt_6") != PROMPT6_MARKER:
        raise HardeningError("PROGRAM_STATE Prompt-6 marker differs")
    if (
        completion.get("prompt_5_scope_id") != SCOPE_ID
        or completion.get("prompt_6_scope_id") != SCOPE_ID
        or completion.get("prompt_5_original_full_scope_complete") is not False
        or completion.get("prompt_6_original_full_scope_complete") is not False
    ):
        raise HardeningError("PROGRAM_STATE completion scope bindings differ")


def _validate_state_bindings(
    value: Mapping[str, object],
    *,
    p5: CompletionEvidence,
    p6: CompletionEvidence,
) -> None:
    expected = {
        "prompt_5_completion_record": str(p5.path),
        "prompt_5_completion_record_sha256": p5.sha256,
        "prompt_6_completion_record": str(p6.path),
        "prompt_6_completion_record_sha256": p6.sha256,
    }
    for key, item in expected.items():
        if value.get(key) != item:
            raise HardeningError(f"PROGRAM_STATE {key} differs from admitted evidence")


def _prompt5_path(supplied: Path | str | None, state: Mapping[str, object]) -> Path:
    raw = supplied or state.get("prompt_5_completion_record")
    if not raw:
        raise HardeningError(
            "Prompt-5 completion path is absent; pass --prompt5-marker or retain it in PROGRAM_STATE"
        )
    return ensure_c(str(raw), label="Prompt-5 completion", must_exist=True)


def _validate_chain(p5: CompletionEvidence, p6: CompletionEvidence) -> None:
    predecessor = p6.record.get("predecessor")
    if not isinstance(predecessor, Mapping):
        raise HardeningError("Prompt-6 completion lacks its Prompt-5 predecessor")
    expected = {
        "prompt_index": 5,
        "completion_marker": PROMPT5_MARKER,
        "completion_record_path": str(p5.path),
        "completion_record_sha256": p5.sha256,
    }
    for key, value in expected.items():
        if predecessor.get(key) != value:
            raise HardeningError(f"Prompt-6 predecessor {key} differs")


def _validate_amendment(value: Mapping[str, object]) -> None:
    if value.get("amendment_id") != SCOPE_ID:
        raise HardeningError("eight-day amendment ID differs")
    scope = value.get("scope")
    storage = value.get("storage_policy")
    markers = value.get("completion_markers")
    if not all(isinstance(item, Mapping) for item in (scope, storage, markers)):
        raise HardeningError("eight-day amendment sections are absent")
    assert isinstance(scope, Mapping)
    assert isinstance(storage, Mapping)
    assert isinstance(markers, Mapping)
    budgets = scope.get("stage_budget_hours")
    if not isinstance(budgets, Mapping) or float(budgets.get("prompt_7") or 0) != 12:
        raise HardeningError("Prompt-7 amended nominal planning target is not 12 hours")
    if scope.get("scope_class") != SCOPE_CLASS:
        raise HardeningError("amended scope class differs")
    if (
        storage.get("allowed_drive") != "C:\\"
        or storage.get("other_drives_allowed") is not False
    ):
        raise HardeningError("amendment does not enforce C:-only storage")
    if int(storage.get("minimum_free_space_reserve_gib") or 0) != 35:
        raise HardeningError("amendment free-space reserve differs")
    if markers.get("prompt_7") != PROMPT7_MARKER:
        raise HardeningError("amendment Prompt-7 marker differs")


def _validate_prompt5_authorization(
    value: Mapping[str, object],
) -> tuple[
    list[str],
    dict[str, str],
    dict[str, object],
    dict[str, object],
    dict[str, dict[str, object]],
]:
    if value.get("scope_id") != SCOPE_ID or value.get("scope_class") != SCOPE_CLASS:
        raise HardeningError("Prompt-5 authorization scope differs")
    extended = value.get("extended_set")
    frozen = value.get("frozen_pipeline_configs")
    registry_ref = value.get("decision_policy_registry")
    if not all(isinstance(item, Mapping) for item in (extended, frozen, registry_ref)):
        raise HardeningError(
            "Prompt-5 authorization lacks extended set/frozen configs/policy registry"
        )
    assert isinstance(extended, Mapping)
    assert isinstance(frozen, Mapping)
    assert isinstance(registry_ref, Mapping)
    extended_path = _validated_file_ref(extended, "predeclared extended set")
    document = yaml.safe_load(extended_path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, Mapping):
        raise HardeningError("extended_set.yaml is not an object")
    values = [str(item) for item in document.get("extended_pipeline_ids", [])]
    if not set(ANCHOR_PIPELINES).issubset(values) or not 6 <= len(values) <= 8:
        raise HardeningError("extended set is outside the frozen six-plus-two contract")
    if len(values) != len(set(values)):
        raise HardeningError("extended set contains duplicate pipeline IDs")
    root = ensure_c(
        str(frozen.get("path") or ""), label="frozen pipeline configs", must_exist=True
    )
    checksums = ensure_c(
        str(frozen.get("checksums_path") or ""),
        label="frozen pipeline checksums",
        must_exist=True,
    )
    if not root.is_dir() or checksums.parent != root:
        raise HardeningError("frozen pipeline config root/checksum layout differs")
    if frozen.get("checksums_sha256") != sha256_file(checksums):
        raise HardeningError("frozen pipeline checksum document differs")
    yaml_ids = {path.stem for path in root.glob("*.yaml")}
    if len(yaml_ids) != 18:
        raise HardeningError("frozen pipeline config root is not exact all-18")
    checksum_document = read_json(checksums)
    if checksum_document.get("pipeline_count") != 18 or checksum_document.get(
        "entries"
    ) != checksum_map(root, exclude=("checksums.json",)):
        raise HardeningError("frozen pipeline config checksum map differs")

    registry_path = _validated_file_ref(
        registry_ref, "frozen development decision-policy registry"
    )
    registry_value = read_json(registry_path)
    try:
        validate_development_policy_registry(registry_value)
    except Exception as exc:
        raise HardeningError(
            f"frozen decision-policy registry is invalid: {exc}"
        ) from exc
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    runtime_bindings = _validate_frozen_runtime_bindings(
        extended_pipeline_ids=values,
        frozen_root=root,
        registry=registry_value,
        matrix=matrix,
    )
    return (
        values,
        {"path": str(extended_path), "sha256": sha256_file(extended_path)},
        {
            "path": str(root),
            "checksums_path": str(checksums),
            "checksums_sha256": sha256_file(checksums),
            "pipeline_count": 18,
        },
        {
            "path": str(registry_path),
            "sha256": sha256_file(registry_path),
            "registry_identity_sha256": registry_value.get("registry_identity_sha256"),
        },
        runtime_bindings,
    )


def _validate_frozen_runtime_bindings(
    *,
    extended_pipeline_ids: list[str],
    frozen_root: Path,
    registry: Mapping[str, object],
    matrix: FullPipelineMatrix,
) -> dict[str, dict[str, object]]:
    anchor_audit = audit_frozen_anchor_policies(evaluation_root=MATRIX_PATH.parents[2])
    if anchor_audit.get("status") != "PASS":
        raise HardeningError(
            "frozen anchor policy audit failed: "
            + "; ".join(str(item) for item in anchor_audit.get("errors", []))
        )
    matrix_document = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(matrix_document, Mapping):
        raise HardeningError("authoritative matrix YAML is not an object")
    registry_entries = {
        str(row.get("pipeline_id")): dict(row)
        for row in registry.get("entries", [])
        if isinstance(row, Mapping)
    }
    bindings: dict[str, dict[str, object]] = {}
    asset_digest_cache: dict[tuple[Path, str], str] = {}
    for pipeline_id in extended_pipeline_ids:
        config_path = frozen_root / f"{pipeline_id}.yaml"
        if not config_path.is_file():
            raise HardeningError(f"frozen pipeline YAML is missing: {pipeline_id}")
        document = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(document, Mapping):
            raise HardeningError(f"frozen pipeline YAML is invalid: {pipeline_id}")
        core = {
            str(key): item
            for key, item in document.items()
            if str(key) != "freeze_identity_sha256"
        }
        freeze_identity = sha256_bytes(canonical_json_bytes(core))
        if document.get("freeze_identity_sha256") != freeze_identity:
            raise HardeningError(f"frozen pipeline identity differs: {pipeline_id}")
        selection = matrix.resolve(pipeline_id)
        _validate_frozen_config_against_runtime(
            pipeline_id=pipeline_id,
            document=document,
            selection=selection,
            matrix_document=matrix_document,
        )
        is_anchor = pipeline_id in ANCHOR_PIPELINES
        if is_anchor:
            expected_policy = resolve_decision_policy_contract(
                pipeline_id, realized_gallery_size=10
            )
            binding_status = "BOUND_FROZEN_ANCHOR"
            role_eligible = True
            exclusion_reason = None
        else:
            entry = registry_entries.get(pipeline_id)
            if entry is None:
                raise HardeningError(
                    f"challenger lacks exact frozen registry entry: {pipeline_id}"
                )
            expected_policy = {
                **entry,
                "decision_policy_sha256": entry["calibration_identity_sha256"],
                "calibration_protocol_id": registry["protocol_id"],
                "calibration_result_sha256": entry["calibration_identity_sha256"],
                "target_fpir": 0.01,
                "threshold_scope": "exact_pipeline_and_frozen_gallery_request",
            }
            binding_status = "EXCLUDED_UNRESOLVED_COMMON_DEMO_GALLERY_BINDING"
            role_eligible = False
            exclusion_reason = (
                "current common demo live/file constructors do not bind the frozen "
                "challenger registry and exact realized gallery size; Unknown-only "
                "fallback is forbidden for production-role acceptance"
            )
        if document.get("identity_policy") != expected_policy:
            raise HardeningError(
                f"frozen decision policy differs from its exact source: {pipeline_id}"
            )
        external_assets, environments = _validate_external_runtime_assets(
            selection, digest_cache=asset_digest_cache
        )
        bindings[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "hybrid_label": selection.hybrid_label,
            "frozen_anchor": is_anchor,
            "binding_status": binding_status,
            "production_role_eligible": role_eligible,
            "exclusion_reason": exclusion_reason,
            "frozen_config_path": str(config_path.resolve()),
            "frozen_config_sha256": sha256_file(config_path),
            "freeze_identity_sha256": freeze_identity,
            "pipeline_config_sha256": selection.pipeline_config_sha256,
            "runtime_config_sha256": selection.runtime_config_sha256,
            "decision_policy_sha256": expected_policy.get("decision_policy_sha256"),
            "decision_policy": dict(expected_policy),
            "model_assets": document.get("model_assets"),
            "runtime_component_identities": {
                key: identity.to_contract()
                for key, identity in runtime_identities(
                    selection,
                    evaluation_root=MATRIX_PATH.parents[2],
                    decision_policy_sha256=str(
                        expected_policy.get("decision_policy_sha256") or ""
                    ),
                ).items()
            },
            "external_assets": external_assets,
            "environment_interpreters": environments,
            "unknown_only_fallback_allowed": False,
        }
    if any(
        not bindings[pipeline_id]["production_role_eligible"]
        for pipeline_id in ANCHOR_PIPELINES
    ):
        raise HardeningError(
            "one or more mandatory frozen anchors is not role-eligible"
        )
    return bindings


def _validate_frozen_config_against_runtime(
    *,
    pipeline_id: str,
    document: Mapping[str, object],
    selection: object,
    matrix_document: Mapping[str, object],
) -> None:
    if document.get("pipeline_id") != pipeline_id:
        raise HardeningError(f"frozen pipeline ID differs: {pipeline_id}")
    if (
        document.get("evaluation_material_inspected") is not False
        or document.get("evaluation_retuning_allowed") is not False
    ):
        raise HardeningError(f"frozen firewall fields differ: {pipeline_id}")
    if document.get("pipeline_config_sha256_before_development_freeze") != getattr(
        selection, "pipeline_config_sha256"
    ):
        raise HardeningError(
            f"current pipeline config differs from freeze: {pipeline_id}"
        )
    aliases = document.get("aliases")
    expected_aliases = {
        "asr": selection.asr_alias,
        "anonymous_diarization": selection.diarization_alias,
        "identity": selection.identity_alias,
        "hybrid": selection.hybrid_label,
    }
    if aliases != expected_aliases:
        raise HardeningError(f"frozen pipeline aliases differ: {pipeline_id}")
    asr = document.get("asr")
    diarization = document.get("anonymous_diarization_and_clustering")
    if not isinstance(asr, Mapping) or asr.get("component") != dict(selection.asr):
        raise HardeningError(f"frozen ASR identity differs: {pipeline_id}")
    if not isinstance(diarization, Mapping) or diarization.get("component") != dict(
        selection.diarization
    ):
        raise HardeningError(f"frozen diarization identity differs: {pipeline_id}")
    expected_assets = _model_asset_identity(matrix_document, selection)
    if document.get("model_assets") != expected_assets:
        raise HardeningError(f"frozen model identities differ: {pipeline_id}")
    enrollment = document.get("enrollment_policy")
    if not isinstance(enrollment, Mapping) or any(
        enrollment.get(key) != item
        for key, item in dict(selection.enrollment_policy).items()
    ):
        raise HardeningError(f"frozen enrollment policy differs: {pipeline_id}")
    source_hashes = document.get("source_hashes")
    if (
        not isinstance(source_hashes, Mapping)
        or source_hashes.get("matrix_sha256") != sha256_file(MATRIX_PATH)
        or source_hashes.get("runtime_config_sha256") != sha256_file(RUNTIME_PATH)
    ):
        raise HardeningError(f"frozen source hashes differ: {pipeline_id}")
    code = document.get("result_affecting_code")
    if not isinstance(code, Mapping) or not isinstance(code.get("files"), Mapping):
        raise HardeningError(
            f"frozen result-affecting code identity is absent: {pipeline_id}"
        )
    expected_entries = dict(code["files"])
    observed_entries: dict[str, str] = {}
    for relative, expected in expected_entries.items():
        path = ensure_c(
            MATRIX_PATH.parents[2] / str(relative),
            label=f"frozen result-affecting source {relative}",
            must_exist=True,
        )
        observed = sha256_file(path)
        if observed != expected:
            raise HardeningError(
                f"result-affecting source changed after freeze: {relative}"
            )
        observed_entries[str(relative)] = observed
    if code.get("sha256") != sha256_bytes(canonical_json_bytes(observed_entries)):
        raise HardeningError(
            f"frozen result-affecting code hash differs: {pipeline_id}"
        )


def _validate_external_runtime_assets(
    selection: object, *, digest_cache: dict[tuple[Path, str], str]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    repository_root = MATRIX_PATH.parents[4]
    references: list[tuple[str, Path, str, str]] = []
    asr_asset = selection.asr.get("model_asset")
    if not isinstance(asr_asset, Mapping):
        raise HardeningError(f"ASR model asset is absent: {selection.pipeline_id}")
    references.append(
        (
            "asr_model",
            repository_root / str(asr_asset["storage_path"]),
            str(asr_asset["installed_tree_sha256"]),
            "tree",
        )
    )
    matrix_document = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8")) or {}
    segmentation = matrix_document.get("shared_segmentation_asset")
    if not isinstance(segmentation, Mapping):
        raise HardeningError("shared segmentation asset is absent")
    references.append(
        (
            "segmentation_model",
            repository_root / str(segmentation["storage_path"]),
            str(segmentation["installed_tree_sha256"]),
            "tree",
        )
    )
    identities = {
        str(
            selection.diarization_embedding.get("backend_id")
        ): selection.diarization_embedding,
        str(selection.identity.get("backend_id")): selection.identity,
    }
    for backend_id, identity in identities.items():
        asset_path = identity.get("model_asset_path")
        if not asset_path:
            raise HardeningError(f"model asset path is absent: {backend_id}")
        path = repository_root / str(asset_path)
        expected = identity.get("model_asset_sha256")
        scope = "file" if path.suffix else "tree"
        if expected:
            references.append(
                (f"speaker_embedding:{backend_id}", path, str(expected), scope)
            )
        else:
            affecting = identity.get("result_affecting_files")
            if not isinstance(affecting, Mapping) or not affecting:
                raise HardeningError(
                    f"model asset identity is incomplete: {backend_id}"
                )
            for relative, file_sha in affecting.items():
                references.append(
                    (
                        f"speaker_embedding:{backend_id}:{relative}",
                        path / str(relative),
                        str(file_sha),
                        "file",
                    )
                )
        official_source = identity.get("official_source_path")
        official_sha = identity.get("official_source_tree_sha256")
        if official_source and official_sha:
            references.append(
                (
                    f"speaker_embedding_source:{backend_id}",
                    repository_root / str(official_source),
                    str(official_sha),
                    "tree",
                )
            )
    external_assets: list[dict[str, object]] = []
    seen: set[tuple[Path, str]] = set()
    for component, raw_path, expected, scope in references:
        path = ensure_c(raw_path, label=f"{component} asset", must_exist=True)
        key = (path, scope)
        if key in seen:
            continue
        seen.add(key)
        observed = digest_cache.get(key)
        if observed is None:
            observed = directory_sha256(path) if scope == "tree" else sha256_file(path)
            digest_cache[key] = observed
        if observed.casefold() != expected.casefold():
            raise HardeningError(f"locked external asset differs: {component}: {path}")
        external_assets.append(
            {
                "component": component,
                "path": str(path),
                "sha256": observed,
                "sha256_scope": scope,
            }
        )
    from app.controlled_diarization.runner import interpreter_for_profile

    profiles = sorted(
        {
            str(value)
            for value in (
                selection.asr.get("environment_profile"),
                selection.diarization.get("segmentation_environment_profile"),
                selection.diarization.get("embedding_environment_profile"),
                selection.identity.get("environment_profile"),
            )
            if value
        }
    )
    environments: list[dict[str, object]] = []
    for profile in profiles:
        interpreter = interpreter_for_profile(profile)
        if interpreter is None:
            raise HardeningError(f"unknown runtime environment profile: {profile}")
        path = ensure_c(interpreter, label=f"{profile} interpreter", must_exist=True)
        environments.append(
            {
                "environment_profile": profile,
                "interpreter_path": str(path),
                "interpreter_sha256": sha256_file(path),
            }
        )
    return external_assets, environments


def _validate_hardening_inputs(path: Path) -> dict[str, object]:
    value = read_json(path)
    for key, expected in {
        "schema_version": "full-pipeline-hardening-input-manifest.v1",
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": False,
        "outcome_independent": True,
    }.items():
        if value.get(key) != expected:
            raise HardeningError(f"hardening input manifest {key} differs")
    raw_inputs = value.get("inputs")
    if not isinstance(raw_inputs, list) or not raw_inputs:
        raise HardeningError("hardening input manifest inputs are empty")
    inputs: list[dict[str, object]] = []
    roles: dict[str, list[dict[str, object]]] = {}
    ids: set[str] = set()
    for index, raw in enumerate(raw_inputs):
        if not isinstance(raw, Mapping):
            raise HardeningError(f"hardening input {index} is not an object")
        input_id = str(raw.get("input_id") or "").strip()
        if not input_id or input_id in ids:
            raise HardeningError(f"hardening input {index} ID is absent/duplicate")
        ids.add(input_id)
        audio_path = ensure_c(
            str(raw.get("path") or ""),
            label=f"hardening input {input_id}",
            must_exist=True,
        )
        if not audio_path.is_file():
            raise HardeningError(f"hardening input is not a file: {audio_path}")
        if str(raw.get("sha256") or "").casefold() != sha256_file(audio_path):
            raise HardeningError(f"hardening input checksum differs: {input_id}")
        duration = float(raw.get("duration_sec") or 0.0)
        input_roles = [str(item) for item in raw.get("roles", [])]
        if duration <= 0 or not input_roles:
            raise HardeningError(f"hardening input duration/roles invalid: {input_id}")
        audio = _wav_metadata(audio_path)
        observed_duration = float(audio["duration_sec"])
        if abs(duration - observed_duration) > max(
            0.01, 1.0 / int(audio["sample_rate_hz"])
        ):
            raise HardeningError(
                f"hardening input declared duration differs from WAV: {input_id}"
            )
        row = {
            "input_id": input_id,
            "path": str(audio_path),
            "sha256": sha256_file(audio_path),
            "duration_sec": observed_duration,
            "declared_duration_sec": duration,
            "audio_format": audio,
            "roles": input_roles,
            "capture_method": raw.get("capture_method"),
            "loopback_input_device": raw.get("loopback_input_device"),
            "playback_output_device": raw.get("playback_output_device"),
        }
        inputs.append(row)
        for role in input_roles:
            roles.setdefault(role, []).append(row)
    minimums = {
        "deterministic_replay": 300.0,
        "controlled_loopback": 600.0,
        "repeated_session": 120.0,
        "soak": 3600.0,
    }
    for role, minimum in minimums.items():
        if not any(
            float(row["duration_sec"]) >= minimum for row in roles.get(role, [])
        ):
            raise HardeningError(
                f"hardening input role {role} lacks {minimum:.0f}s WAV"
            )
    enrollment = roles.get("enrollment_sample", [])
    if len({str(row["input_id"]) for row in enrollment}) < 3:
        raise HardeningError(
            "hardening inputs require three distinct enrollment samples"
        )
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "inputs": inputs,
        "required_roles": sorted([*minimums, "enrollment_sample"]),
    }


def _wav_metadata(path: Path) -> dict[str, object]:
    if path.suffix.casefold() != ".wav":
        raise HardeningError(f"hardening input is not a WAV: {path}")
    try:
        with wave.open(str(path), "rb") as stream:
            channels = stream.getnchannels()
            sample_width = stream.getsampwidth()
            sample_rate = stream.getframerate()
            frame_count = stream.getnframes()
            compression = stream.getcomptype()
    except (wave.Error, EOFError, OSError) as exc:
        raise HardeningError(f"hardening input WAV is invalid: {path}: {exc}") from exc
    if (
        channels != 1
        or sample_width != 2
        or sample_rate != 16000
        or frame_count <= 0
        or compression != "NONE"
    ):
        raise HardeningError(
            f"hardening WAV must be mono 16-kHz 16-bit uncompressed PCM: {path}"
        )
    return {
        "container": "WAV",
        "codec": "PCM_S16LE",
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate_hz": sample_rate,
        "frame_count": frame_count,
        "duration_sec": frame_count / sample_rate,
    }


def _validated_file_ref(raw: Mapping[str, object], label: str) -> Path:
    path = ensure_c(str(raw.get("path") or ""), label=label, must_exist=True)
    if not path.is_file() or raw.get("sha256") != sha256_file(path):
        raise HardeningError(f"{label} reference differs")
    return path


def _completion_ref(value: CompletionEvidence) -> dict[str, object]:
    return {
        "prompt_index": value.prompt_index,
        "completion_marker": value.marker,
        "path": str(value.path),
        "sha256": value.sha256,
        "artifact_count": len(value.artifacts),
    }


__all__ = ["validate_prerequisites"]
