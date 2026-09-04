"""Fail-closed Prompt-5 predecessor and frozen extended-set admission gate."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import yaml

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_development.policies import (
    validate_development_policy_registry,
)
from app.full_pipeline_deployment_evidence import (
    DeploymentEvidenceError,
    load_deployment_steering,
    steering_ref,
    validate_deployment_evidence_document,
)
from app.full_pipeline_evaluation.io import canonical_json_bytes, sha256_bytes
from app.full_pipeline_evaluation.planning import MATRIX_PATH, RUNTIME_CONFIG_PATH
from app.full_pipeline_core_evaluation.gate import (
    _validate_frozen_configs as _validate_live_frozen_configs,
)

from . import (
    DEFAULT_AMENDMENT,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    MANDATORY_ANCHORS,
    PI_DEPLOYMENT_STEERING_SHA256,
    PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA,
    PROMPT5_COMPLETION_MARKER,
    PROMPT6_COMPLETION_MARKER,
    SCOPE_CLASS,
    SCOPE_ID,
    scope_fields,
)
from .io import (
    ExtendedEvaluationError,
    ensure_c_drive,
    read_json,
    sha256_file,
    verify_ref,
)


COMPLETION_SCHEMA = "full-pipeline-eight-day-stage-completion.v1"
MANIFEST_SCHEMA = "full-pipeline-eight-day-artifact-manifest.v1"
GATE_SCHEMA = "full-pipeline-eight-day-gate.v1"
EXPECTED_GATE_NAMES = {
    "hash_validation",
    "firewall_validation",
    "prerequisite_validation",
}


def validate_prompt5_predecessor(
    predecessor_path: Path | str,
    *,
    expected_sha256: str | None = None,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
    deployment_steering_sha256: str = PI_DEPLOYMENT_STEERING_SHA256,
) -> dict[str, object]:
    """Validate Prompt 5 and its deployment-only evidence without selection.

    The universal inventory is rehashed.  Only the Prompt-5 authorization and
    checksum-bound deployment-evidence report are parsed; scientific outcome
    tables remain unopened and cannot affect the already-frozen extended set.
    """

    if str(deployment_steering_sha256).casefold() != PI_DEPLOYMENT_STEERING_SHA256:
        raise ExtendedEvaluationError(
            "Prompt-6 requires the exact authoritative deployment steering SHA-256"
        )

    predecessor_file = ensure_c_drive(
        predecessor_path, label="Prompt-5 predecessor", must_exist=True
    )
    if (
        expected_sha256 is not None
        and sha256_file(predecessor_file) != str(expected_sha256).casefold()
    ):
        raise ExtendedEvaluationError("orchestrator Prompt-5 predecessor hash differs")
    predecessor = read_json(predecessor_file)
    _expect(predecessor, "schema_version", COMPLETION_SCHEMA)
    _expect(predecessor, "status", "COMPLETE")
    _expect(predecessor, "completion_marker", PROMPT5_COMPLETION_MARKER)
    _expect(predecessor, "prompt_index", 5)
    _require_scope(predecessor, "Prompt-5 completion")
    manifest, artifact_paths = _verify_universal_refs(predecessor)
    authorization_path = _find_authorization(artifact_paths)
    prompt5_deployment_path = _find_prompt5_deployment_evidence(artifact_paths)
    authorization = read_json(authorization_path)
    artifacts = _validate_authorization(authorization)
    extended = _validate_extended_set(Path(str(artifacts["extended_set"]["path"])))
    registry = _validate_file_artifact(
        artifacts["decision_policy_registry"], "decision-policy registry"
    )
    registry_document = read_json(Path(str(registry["path"])))
    validate_development_policy_registry(registry_document)
    frozen = _validate_frozen_configs(
        artifacts["frozen_pipeline_configs"],
        policy_registry=registry_document,
    )
    _validate_amendment(
        ensure_c_drive(amendment_path, label="eight-day amendment", must_exist=True)
    )
    _validate_program_state(
        ensure_c_drive(
            program_state_path, label="full-pipeline program state", must_exist=True
        ),
        predecessor_file,
    )
    try:
        steering = load_deployment_steering(
            deployment_steering_path,
            expected_prompt_index=6,
            expected_sha256=deployment_steering_sha256,
        )
        prompt5_deployment = read_json(prompt5_deployment_path)
        matrix_pipeline_ids = FullPipelineMatrix(
            MATRIX_PATH, RUNTIME_CONFIG_PATH
        ).pipeline_ids
        validate_deployment_evidence_document(
            prompt5_deployment,
            schema_version=PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA,
            prompt_index=5,
            expected_pipeline_ids=matrix_pipeline_ids,
            steering=steering,
        )
    except DeploymentEvidenceError as exc:
        raise ExtendedEvaluationError(
            f"Prompt-5 deployment evidence admission failed: {exc}"
        ) from exc
    steering_reference = steering_ref(deployment_steering_path, steering)
    if prompt5_deployment.get("steering_authority") != steering_reference:
        raise ExtendedEvaluationError(
            "Prompt-5 deployment evidence used a different steering authority"
        )
    prompt5_deployment_reference = {
        "path": str(prompt5_deployment_path),
        "sha256": sha256_file(prompt5_deployment_path),
        "schema_version": PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA,
        "status": "PASS",
        "pipeline_count": len(matrix_pipeline_ids),
    }
    core = {
        "schema_version": "full-pipeline-extended-authorization.v1",
        **scope_fields(),
        "status": "AUTHORIZED_NOT_STARTED",
        "prompt5_completion_marker": PROMPT5_COMPLETION_MARKER,
        "prompt5_completion_path": str(predecessor_file),
        "prompt5_completion_sha256": sha256_file(predecessor_file),
        "prompt5_artifact_manifest_path": str(
            ensure_c_drive(
                str(predecessor["artifact_manifest"]["path"]),
                label="Prompt-5 artifact manifest",
                must_exist=True,
            )
        ),
        "prompt5_artifact_manifest_sha256": sha256_file(
            Path(str(predecessor["artifact_manifest"]["path"]))
        ),
        "prompt5_scientific_outcome_tables_opened_for_selection": False,
        "prompt5_deployment_evidence_opened_for_reporting": True,
        "prompt5_outcome_dependent_selection": False,
        "authorization_path": str(authorization_path),
        "authorization_sha256": sha256_file(authorization_path),
        "frozen_pipeline_configs": frozen,
        "decision_policy_registry": registry,
        "extended_set": {
            "path": str(artifacts["extended_set"]["path"]),
            "sha256": str(artifacts["extended_set"]["sha256"]),
            **extended,
        },
        "raspberry_pi_deployment_steering": steering_reference,
        "prompt5_deployment_evidence": prompt5_deployment_reference,
        "development_summary": _validate_file_artifact(
            artifacts["development_summary"], "development summary"
        ),
        "universal_artifact_count_rehashed": len(manifest["artifacts"]),
    }
    return {
        **core,
        "authorization_identity_sha256": sha256_bytes(canonical_json_bytes(core)),
    }


def validate_saved_authorization(
    value: Mapping[str, object],
    *,
    predecessor_path: Path | str,
    expected_sha256: str | None = None,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
    deployment_steering_sha256: str = PI_DEPLOYMENT_STEERING_SHA256,
) -> dict[str, object]:
    current = validate_prompt5_predecessor(
        predecessor_path,
        expected_sha256=expected_sha256,
        program_state_path=program_state_path,
        amendment_path=amendment_path,
        deployment_steering_path=deployment_steering_path,
        deployment_steering_sha256=deployment_steering_sha256,
    )
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(current):
        raise ExtendedEvaluationError(
            "saved Prompt-6 authorization differs because a bound input changed"
        )
    return current


def _verify_universal_refs(
    completion: Mapping[str, object],
) -> tuple[dict[str, object], tuple[Path, ...]]:
    raw_manifest = completion.get("artifact_manifest")
    if not isinstance(raw_manifest, Mapping):
        raise ExtendedEvaluationError("Prompt-5 artifact-manifest reference is absent")
    manifest_path = verify_ref(raw_manifest, label="Prompt-5 artifact manifest")
    manifest = read_json(manifest_path)
    _expect(manifest, "schema_version", MANIFEST_SCHEMA)
    _expect(manifest, "prompt_index", 5)
    _require_scope(manifest, "Prompt-5 artifact manifest")
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ExtendedEvaluationError("Prompt-5 artifact manifest is empty")
    artifact_paths: list[Path] = []
    for index, raw in enumerate(raw_artifacts):
        if not isinstance(raw, Mapping) or raw.get("required") is not True:
            raise ExtendedEvaluationError(
                f"Prompt-5 artifact entry {index} is not required/bound"
            )
        artifact_paths.append(verify_ref(raw, label=f"Prompt-5 artifact {index}"))
    raw_gates = completion.get("gate_records")
    if not isinstance(raw_gates, Mapping) or set(raw_gates) != EXPECTED_GATE_NAMES:
        raise ExtendedEvaluationError("Prompt-5 gate inventory differs")
    inventory = set(artifact_paths)
    for name in sorted(EXPECTED_GATE_NAMES):
        raw = raw_gates[name]
        if not isinstance(raw, Mapping):
            raise ExtendedEvaluationError(f"Prompt-5 {name} gate reference is invalid")
        path = verify_ref(raw, label=f"Prompt-5 {name} gate")
        if path not in inventory:
            raise ExtendedEvaluationError(f"Prompt-5 {name} gate is not manifested")
        gate = read_json(path)
        _expect(gate, "schema_version", GATE_SCHEMA)
        _expect(gate, "prompt_index", 5)
        _expect(gate, "gate", name)
        _expect(gate, "status", "PASS")
        _require_scope(gate, f"Prompt-5 {name} gate")
    return manifest, tuple(artifact_paths)


def _find_authorization(paths: tuple[Path, ...]) -> Path:
    matches = [path for path in paths if path.name == "prompt5_authorization.json"]
    if len(matches) != 1:
        raise ExtendedEvaluationError(
            "Prompt-5 artifact manifest must contain one prompt5_authorization.json"
        )
    return matches[0]


def _find_prompt5_deployment_evidence(paths: tuple[Path, ...]) -> Path:
    matches = [path for path in paths if path.name == "all18_deployment_evidence.json"]
    if len(matches) != 1:
        raise ExtendedEvaluationError(
            "Prompt-5 artifact manifest must contain exactly one direct "
            "all18_deployment_evidence.json"
        )
    return matches[0]


def _validate_authorization(
    value: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    if value.get("schema_version") != "full-pipeline-core-evaluation-authorization.v1":
        raise ExtendedEvaluationError("Prompt-5 authorization schema differs")
    _require_scope(value, "Prompt-5 authorization")
    if (
        value.get("held_out_predictions_inspected") is not False
        or value.get("held_out_inference_started") is not False
    ):
        raise ExtendedEvaluationError("Prompt-5 authorization firewall differs")
    required = (
        "frozen_pipeline_configs",
        "decision_policy_registry",
        "extended_set",
        "development_summary",
    )
    result: dict[str, Mapping[str, object]] = {}
    for key in required:
        raw = value.get(key)
        if not isinstance(raw, Mapping):
            raise ExtendedEvaluationError(f"Prompt-5 authorization lacks {key}")
        result[key] = raw
    return result


def _validate_extended_set(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, Mapping):
        raise ExtendedEvaluationError("extended_set.yaml root is not an object")
    mandatory = tuple(str(item) for item in value.get("mandatory_pipeline_ids", []))
    challengers = tuple(
        str(item) for item in value.get("additional_challenger_pipeline_ids", [])
    )
    extended = tuple(str(item) for item in value.get("extended_pipeline_ids", []))
    if set(mandatory) != set(MANDATORY_ANCHORS) or len(mandatory) != 6:
        raise ExtendedEvaluationError("extended set mandatory six anchors differ")
    if len(challengers) > 2 or len(set(challengers)) != len(challengers):
        raise ExtendedEvaluationError("extended set challenger bound differs")
    if extended != mandatory + challengers or len(set(extended)) != len(extended):
        raise ExtendedEvaluationError("extended set ordering/membership differs")
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    if set(extended) - set(matrix.pipeline_ids):
        raise ExtendedEvaluationError("extended set contains unknown pipelines")
    if value.get("evaluation_material_inspected") is not False:
        raise ExtendedEvaluationError("extended set lacks development-only firewall")
    return {
        "mandatory_pipeline_ids": list(mandatory),
        "additional_challenger_pipeline_ids": list(challengers),
        "extended_pipeline_ids": list(extended),
        "pipeline_count": len(extended),
    }


def _validate_frozen_configs(
    raw: Mapping[str, object],
    *,
    policy_registry: Mapping[str, object],
) -> dict[str, object]:
    """Require the exact live execution proof used by the Prompt-5 firewall.

    A checksum-valid freeze is not enough: a signed YAML can still differ from
    the matrix, runtime configuration, policies, assets, or result-affecting
    code that the live worker will execute.  Delegating to the Prompt-5 proof
    keeps both stages on one fail-closed execution contract.
    """

    try:
        proof = _validate_live_frozen_configs(
            raw,
            policy_registry=policy_registry,
        )
    except Exception as exc:
        raise ExtendedEvaluationError(
            f"frozen/live execution contract validation failed: {exc}"
        ) from exc
    if proof.get("execution_contract_validation") != "EXACT_LIVE_MATCH":
        raise ExtendedEvaluationError("frozen/live execution proof is not exact")
    code_sha = str(proof.get("live_result_affecting_code_sha256") or "").casefold()
    if len(code_sha) != 64:
        raise ExtendedEvaluationError("live result-affecting code proof is absent")
    return dict(proof)


def _validate_file_artifact(raw: Mapping[str, object], label: str) -> dict[str, str]:
    path = ensure_c_drive(str(raw.get("path") or ""), label=label, must_exist=True)
    if (
        not path.is_file()
        or sha256_file(path) != str(raw.get("sha256") or "").casefold()
    ):
        raise ExtendedEvaluationError(f"{label} hash differs")
    return {"path": str(path), "sha256": sha256_file(path)}


def _validate_amendment(path: Path) -> None:
    value = read_json(path)
    _expect(value, "amendment_id", SCOPE_ID)
    scope = value.get("scope")
    storage = value.get("storage_policy")
    markers = value.get("completion_markers")
    if not all(isinstance(item, Mapping) for item in (scope, storage, markers)):
        raise ExtendedEvaluationError("eight-day amendment sections are missing")
    assert isinstance(scope, Mapping)
    assert isinstance(storage, Mapping)
    assert isinstance(markers, Mapping)
    if (
        scope.get("scope_class") != SCOPE_CLASS
        or int(
            scope.get("stage_budget_hours", {}).get("prompt_6", 0)  # type: ignore[union-attr]
        )
        != 30
    ):
        raise ExtendedEvaluationError("Prompt-6 amendment budget differs")
    if (
        storage.get("allowed_drive") != "C:\\"
        or int(storage.get("minimum_free_space_reserve_gib") or 0) != 35
    ):
        raise ExtendedEvaluationError("Prompt-6 storage amendment differs")
    if (
        markers.get("prompt_5") != PROMPT5_COMPLETION_MARKER
        or markers.get("prompt_6") != PROMPT6_COMPLETION_MARKER
    ):
        raise ExtendedEvaluationError("Prompt-5/6 amended marker differs")


def _validate_program_state(path: Path, predecessor_path: Path) -> None:
    value = read_json(path)
    if (
        value.get("status") != PROMPT5_COMPLETION_MARKER
        or int(value.get("current_prompt_index") or -1) != 5
    ):
        raise ExtendedEvaluationError("PROGRAM_STATE has not reached bounded Prompt 5")
    if value.get("remaining_prompt_indices") != [6, 7, 8]:
        raise ExtendedEvaluationError("PROGRAM_STATE remaining prompts differ")
    state = value.get("completion_state")
    if (
        not isinstance(state, Mapping)
        or state.get("prompt_5") != PROMPT5_COMPLETION_MARKER
    ):
        raise ExtendedEvaluationError("PROGRAM_STATE completion_state.prompt_5 differs")
    if value.get("prompt_5_completion_record") != str(predecessor_path):
        raise ExtendedEvaluationError("PROGRAM_STATE Prompt-5 completion path differs")
    if value.get("prompt_5_completion_record_sha256") != sha256_file(predecessor_path):
        raise ExtendedEvaluationError("PROGRAM_STATE Prompt-5 completion hash differs")


def _require_scope(value: Mapping[str, object], label: str) -> None:
    for key, expected in scope_fields().items():
        if value.get(key) != expected:
            raise ExtendedEvaluationError(f"{label} {key} differs")


def _expect(value: Mapping[str, object], key: str, expected: object) -> None:
    if value.get(key) != expected:
        raise ExtendedEvaluationError(
            f"{key} differs: expected={expected!r}, observed={value.get(key)!r}"
        )


__all__ = ["validate_prompt5_predecessor", "validate_saved_authorization"]
