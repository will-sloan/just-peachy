"""Validation of the amendment, command adapters, and stage evidence gates."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import (
    ADAPTER_CONFIG_SCHEMA,
    AMENDMENT_SCHEMA,
    ARTIFACT_MANIFEST_SCHEMA,
    COMPLETION_MARKERS,
    GATE_SCHEMA,
    MATERIAL_PATH_CLASSES,
    MINIMUM_FREE_GIB,
    PROMPTS,
    REQUIRED_GATE_NAMES,
    RESERVED_ORIGINAL_MARKERS,
    SCOPE_CLASS,
    SCOPE_ID,
    SHARED_CONTINGENCY_HOURS,
    STAGE_BUDGET_HOURS,
    STAGE_COMPLETION_SCHEMA,
    TOTAL_BUDGET_HOURS,
)
from .storage import (
    ProgramContractError,
    canonical_sha256,
    expand_tokens,
    file_sha256,
    load_json,
    resolve_c_only_path,
    validate_command_paths,
    validate_no_off_c_drive_reference,
)


@dataclass(frozen=True)
class StageAdapter:
    prompt_index: int
    adapter_id: str
    readiness: str
    not_ready_reason: str | None
    contract_sha256: str
    expected_duration_hours: float
    cwd: Path | None
    stage_workspace: Path | None
    completion_record: Path | None
    progress_record: Path | None
    controller_log: Path | None
    start_command: tuple[str, ...]
    resume_command: tuple[str, ...]
    stop_command: tuple[str, ...]
    validate_command: tuple[str, ...]
    restart_policy: str
    stop_grace_seconds: int
    environment: Mapping[str, str]
    material_paths: Mapping[str, tuple[Path, ...]]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class AdapterConfiguration:
    path: Path
    evaluation_tool_root: Path
    program_workspace: Path
    amendment_path: Path
    poll_interval_seconds: float
    stages: Mapping[int, StageAdapter]
    raw_sha256: str


@dataclass(frozen=True)
class ValidatedCompletion:
    prompt_index: int
    marker: str
    path: Path
    sha256: str
    artifact_manifest_path: Path
    artifact_manifest_sha256: str
    artifact_count: int
    adapter_contract_sha256: str


_DYNAMIC_COMMAND_TOKENS = {
    "PREDECESSOR_COMPLETION_PATH": "__JP8_DYNAMIC_PREDECESSOR_COMPLETION_PATH__",
    "PREDECESSOR_COMPLETION_SHA256": "__JP8_DYNAMIC_PREDECESSOR_COMPLETION_SHA256__",
    "PREDECESSOR_COMPLETION_MARKER": "__JP8_DYNAMIC_PREDECESSOR_COMPLETION_MARKER__",
}


def validate_amendment(path: Path) -> dict[str, Any]:
    resolved = resolve_c_only_path(path, must_exist=True, label="scope amendment")
    amendment = load_json(resolved)
    errors: list[str] = []

    def expect(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    expect(amendment.get("schema_version") == AMENDMENT_SCHEMA, "amendment schema")
    expect(amendment.get("amendment_id") == SCOPE_ID, "amendment ID")
    scope = amendment.get("scope") if isinstance(amendment.get("scope"), dict) else {}
    expect(scope.get("scope_class") == SCOPE_CLASS, "bounded scope class")
    expect(scope.get("total_wall_target_hours") == TOTAL_BUDGET_HOURS, "192-hour total")
    raw_budgets = (
        scope.get("stage_budget_hours")
        if isinstance(scope.get("stage_budget_hours"), dict)
        else {}
    )
    for prompt, expected in STAGE_BUDGET_HOURS.items():
        expect(raw_budgets.get(f"prompt_{prompt}") == expected, f"Prompt {prompt} budget")
    expect(
        raw_budgets.get("shared_contingency") == SHARED_CONTINGENCY_HOURS,
        "shared contingency",
    )
    expect(scope.get("stage_budget_sum_hours") == TOTAL_BUDGET_HOURS, "budget sum")
    expect(scope.get("automatic_transition_prompts") == [5, 6, 7, 8], "transition list")
    storage = (
        amendment.get("storage_policy")
        if isinstance(amendment.get("storage_policy"), dict)
        else {}
    )
    expect(storage.get("allowed_drive") == "C:\\", "C:-only drive")
    expect(storage.get("other_drives_allowed") is False, "other drives prohibited")
    expect(
        storage.get("minimum_free_space_reserve_gib") == MINIMUM_FREE_GIB,
        "35 GiB reserve",
    )
    expect(
        storage.get("junction_or_symlink_to_other_drive_allowed") is False,
        "off-drive links prohibited",
    )
    labels = (
        amendment.get("required_artifact_labels")
        if isinstance(amendment.get("required_artifact_labels"), dict)
        else {}
    )
    expect(labels.get("scope_id") == SCOPE_ID, "artifact scope ID")
    expect(labels.get("scope_class") == SCOPE_CLASS, "artifact scope class")
    expect(labels.get("original_full_scope_complete") is False, "bounded interpretation")
    markers = (
        amendment.get("completion_markers")
        if isinstance(amendment.get("completion_markers"), dict)
        else {}
    )
    for prompt, expected in COMPLETION_MARKERS.items():
        expect(markers.get(f"prompt_{prompt}") == expected, f"Prompt {prompt} marker")
    expect(
        set(amendment.get("reserved_original_completion_markers", []))
        == RESERVED_ORIGINAL_MARKERS,
        "reserved original completion markers",
    )
    invariants = (
        amendment.get("scientific_invariants")
        if isinstance(amendment.get("scientific_invariants"), dict)
        else {}
    )
    expect(invariants.get("maximum_concurrent_accuracy_jobs") == 2, "two-job accuracy cap")
    expect(invariants.get("standardized_resource_jobs_serial") is True, "serial resources")
    expect(invariants.get("heldout_firewall_preserved") is True, "held-out firewall")
    expect(invariants.get("speaker_level_bootstrap_required") is True, "speaker bootstrap")
    if errors:
        raise ProgramContractError("Invalid eight-day amendment:\n- " + "\n- ".join(errors))
    return amendment


def load_adapter_configuration(path: Path) -> AdapterConfiguration:
    config_path = resolve_c_only_path(
        path, base=Path.cwd(), must_exist=True, label="adapter configuration"
    )
    raw = load_json(config_path)
    if raw.get("schema_version") != ADAPTER_CONFIG_SCHEMA:
        raise ProgramContractError(
            f"Adapter schema must be {ADAPTER_CONFIG_SCHEMA}: {config_path}"
        )
    if raw.get("scope_id") != SCOPE_ID or raw.get("scope_class") != SCOPE_CLASS:
        raise ProgramContractError("Adapter configuration is not bound to the eight-day scope")
    if raw.get("original_full_scope_complete") is not False:
        raise ProgramContractError("Adapter configuration must preserve bounded-scope labeling")

    root = resolve_c_only_path(
        str(raw.get("evaluation_tool_root", "")),
        must_exist=True,
        label="evaluation_tool_root",
    )
    workspace = resolve_c_only_path(
        str(raw.get("program_workspace", "")),
        label="program_workspace",
    )
    amendment_path = resolve_c_only_path(
        str(raw.get("amendment_path", "")),
        must_exist=True,
        label="amendment_path",
    )
    amendment = validate_amendment(amendment_path)
    canonical_root = resolve_c_only_path(
        str(amendment["storage_policy"]["canonical_evaluation_tool_root"]),
        must_exist=True,
        label="amendment canonical evaluation root",
    )
    if root != canonical_root:
        raise ProgramContractError(
            f"evaluation_tool_root must equal the amendment's canonical root: {canonical_root}"
        )
    expected_amendment = root / "runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json"
    if amendment_path != expected_amendment.resolve(strict=True):
        raise ProgramContractError(
            f"amendment_path must be the canonical machine authority: {expected_amendment}"
        )
    if not workspace.is_relative_to(root):
        raise ProgramContractError(
            f"program_workspace must remain beneath the canonical Evaluation Tool root: {workspace}"
        )
    poll = float(raw.get("poll_interval_seconds", 10.0))
    if not 1.0 <= poll <= 300.0:
        raise ProgramContractError("poll_interval_seconds must be between 1 and 300")
    variables = {
        "TOOL_ROOT": str(root),
        "PROGRAM_WORKSPACE": str(workspace),
        "AMENDMENT_PATH": str(amendment_path),
    }
    raw_stages = raw.get("stages") if isinstance(raw.get("stages"), dict) else {}
    unknown = set(raw_stages) - {str(prompt) for prompt in PROMPTS}
    if unknown:
        raise ProgramContractError(f"Unknown prompt adapters: {sorted(unknown)}")
    stages: dict[int, StageAdapter] = {}
    for prompt in PROMPTS:
        stage_raw = raw_stages.get(str(prompt))
        if stage_raw is None:
            stage_raw = {
                "adapter_id": f"prompt_{prompt}_missing",
                "readiness": "NOT_READY",
                "not_ready_reason": "adapter_not_configured",
                "expected_duration_hours": STAGE_BUDGET_HOURS[prompt],
            }
        if not isinstance(stage_raw, dict):
            raise ProgramContractError(f"Prompt {prompt} adapter must be an object")
        stages[prompt] = _load_stage_adapter(
            prompt=prompt,
            raw=stage_raw,
            base_variables=variables,
            root=root,
            program_workspace=workspace,
        )
    return AdapterConfiguration(
        path=config_path,
        evaluation_tool_root=root,
        program_workspace=workspace,
        amendment_path=amendment_path,
        poll_interval_seconds=poll,
        stages=stages,
        raw_sha256=file_sha256(config_path),
    )


def _load_stage_adapter(
    *,
    prompt: int,
    raw: Mapping[str, Any],
    base_variables: Mapping[str, str],
    root: Path,
    program_workspace: Path,
) -> StageAdapter:
    adapter_id = str(raw.get("adapter_id", "")).strip()
    if not adapter_id:
        raise ProgramContractError(f"Prompt {prompt} adapter_id is required")
    readiness = str(raw.get("readiness", "NOT_READY"))
    if readiness not in {"READY", "NOT_READY"}:
        raise ProgramContractError(f"Prompt {prompt} readiness must be READY or NOT_READY")
    reason = raw.get("not_ready_reason")
    if readiness == "NOT_READY" and not isinstance(reason, str):
        raise ProgramContractError(f"Prompt {prompt} NOT_READY adapter needs not_ready_reason")
    expected = float(raw.get("expected_duration_hours", STAGE_BUDGET_HOURS[prompt]))
    if not 0 < expected <= STAGE_BUDGET_HOURS[prompt]:
        raise ProgramContractError(
            f"Prompt {prompt} expected_duration_hours must be >0 and <= {STAGE_BUDGET_HOURS[prompt]}"
        )
    contract_hash = canonical_sha256(raw)
    variables = dict(base_variables)
    variables["PROMPT_INDEX"] = str(prompt)
    variables["ADAPTER_CONTRACT_SHA256"] = contract_hash

    def optional_path(key: str, *, label: str) -> Path | None:
        value = raw.get(key)
        if value in (None, ""):
            return None
        expanded = expand_tokens(str(value), variables)
        return resolve_c_only_path(expanded, base=root, label=label)

    stage_workspace = optional_path("stage_workspace", label=f"Prompt {prompt} workspace")
    if stage_workspace is not None:
        variables["STAGE_WORKSPACE"] = str(stage_workspace)
    elif readiness == "READY":
        raise ProgramContractError(f"Prompt {prompt} READY adapter needs stage_workspace")
    else:
        variables["STAGE_WORKSPACE"] = str(program_workspace / f"prompt_{prompt}")

    cwd = optional_path("cwd", label=f"Prompt {prompt} cwd")
    completion = optional_path(
        "completion_record", label=f"Prompt {prompt} completion_record"
    )
    progress = optional_path("progress_record", label=f"Prompt {prompt} progress_record")
    controller_log = optional_path("controller_log", label=f"Prompt {prompt} controller_log")

    variables.update(_DYNAMIC_COMMAND_TOKENS)
    variables.update(
        {
            "COMPLETION_RECORD": str(completion) if completion else "",
            "PROGRESS_RECORD": str(progress) if progress else "",
            "CONTROLLER_LOG": str(controller_log) if controller_log else "",
        }
    )

    def command(key: str) -> tuple[str, ...]:
        value = raw.get(key, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            raise ProgramContractError(f"Prompt {prompt} {key} must be an argv array")
        expanded = tuple(expand_tokens(str(token), variables) for token in value)
        validate_command_paths(expanded, base=cwd or root, label=f"Prompt {prompt} {key}")
        return expanded

    start = command("start_command")
    resume = command("resume_command")
    stop = command("stop_command")
    validate = command("validate_command")
    restart_policy = str(raw.get("restart_policy", "NOT_SUPPORTED"))
    if restart_policy not in {"RESUME_COMMAND", "RERUN_IDEMPOTENT", "NOT_SUPPORTED"}:
        raise ProgramContractError(f"Prompt {prompt} has invalid restart_policy")
    grace = int(raw.get("stop_grace_seconds", 300))
    if not 5 <= grace <= 3600:
        raise ProgramContractError(f"Prompt {prompt} stop_grace_seconds must be 5..3600")
    environment_raw = raw.get("environment", {})
    if not isinstance(environment_raw, dict):
        raise ProgramContractError(f"Prompt {prompt} environment must be an object")
    environment = {
        str(key): expand_tokens(str(value), variables)
        for key, value in environment_raw.items()
    }
    for key, value in environment.items():
        validate_no_off_c_drive_reference(
            value, label=f"Prompt {prompt} environment.{key}"
        )

    material_raw = raw.get("material_paths", {})
    if not isinstance(material_raw, dict):
        raise ProgramContractError(f"Prompt {prompt} material_paths must be an object")
    if readiness == "READY" and set(material_raw) != set(MATERIAL_PATH_CLASSES):
        raise ProgramContractError(
            f"Prompt {prompt} READY adapter must declare exactly these material path classes: "
            + ", ".join(MATERIAL_PATH_CLASSES)
        )
    material: dict[str, tuple[Path, ...]] = {}
    for path_class, values in material_raw.items():
        if path_class not in MATERIAL_PATH_CLASSES:
            raise ProgramContractError(
                f"Prompt {prompt} has unknown material path class {path_class}"
            )
        if not isinstance(values, list):
            raise ProgramContractError(
                f"Prompt {prompt} material_paths.{path_class} must be an array"
            )
        material[path_class] = tuple(
            resolve_c_only_path(
                expand_tokens(str(value), variables),
                base=root,
                label=f"Prompt {prompt} {path_class}",
            )
            for value in values
        )
        if path_class not in {"inputs", "checkpoints"}:
            for resolved in material[path_class]:
                if not resolved.is_relative_to(root):
                    raise ProgramContractError(
                        f"Prompt {prompt} {path_class} output must remain beneath "
                        f"the canonical Evaluation Tool root: {resolved}"
                    )
    for path_class in MATERIAL_PATH_CLASSES:
        material.setdefault(path_class, ())

    if readiness == "READY":
        missing = [
            name
            for name, value in {
                "cwd": cwd,
                "completion_record": completion,
                "progress_record": progress,
                "controller_log": controller_log,
            }.items()
            if value is None
        ]
        if missing:
            raise ProgramContractError(
                f"Prompt {prompt} READY adapter is missing: {', '.join(missing)}"
            )
        if not start or not stop or not validate:
            raise ProgramContractError(
                f"Prompt {prompt} READY adapter requires start, stop, and validate commands"
            )
        if restart_policy == "RESUME_COMMAND" and not resume:
            raise ProgramContractError(
                f"Prompt {prompt} RESUME_COMMAND policy requires resume_command"
            )
        if restart_policy == "NOT_SUPPORTED":
            raise ProgramContractError(
                f"Prompt {prompt} READY adapter must declare a restart-safe policy"
            )
        declared = {path for paths in material.values() for path in paths}
        for label, required in {
            "stage_workspace": stage_workspace,
            "cwd": cwd,
            "completion_record": completion,
            "progress_record": progress,
            "controller_log": controller_log,
        }.items():
            if required not in declared:
                raise ProgramContractError(
                    f"Prompt {prompt} {label} must also appear in material_paths"
                )
        if not material["temporary"]:
            raise ProgramContractError(f"Prompt {prompt} must declare a C:-only temporary path")

    return StageAdapter(
        prompt_index=prompt,
        adapter_id=adapter_id,
        readiness=readiness,
        not_ready_reason=str(reason) if reason is not None else None,
        contract_sha256=contract_hash,
        expected_duration_hours=expected,
        cwd=cwd,
        stage_workspace=stage_workspace,
        completion_record=completion,
        progress_record=progress,
        controller_log=controller_log,
        start_command=start,
        resume_command=resume,
        stop_command=stop,
        validate_command=validate,
        restart_policy=restart_policy,
        stop_grace_seconds=grace,
        environment=environment,
        material_paths=material,
        raw=raw,
    )


def validate_stage_completion(
    *,
    adapter: StageAdapter,
    predecessor: ValidatedCompletion | None,
) -> ValidatedCompletion:
    prompt = adapter.prompt_index
    if adapter.readiness != "READY":
        raise ProgramContractError(
            f"Prompt {prompt} adapter is NOT_READY and cannot produce completion"
        )
    if adapter.completion_record is None:
        raise ProgramContractError(f"Prompt {prompt} completion record is not configured")
    path = resolve_c_only_path(
        adapter.completion_record,
        must_exist=True,
        label=f"Prompt {prompt} completion record",
    )
    record = load_json(path)
    errors: list[str] = []
    declared_paths = {
        declared
        for path_group in adapter.material_paths.values()
        for declared in path_group
    }

    def expect(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    expect(record.get("schema_version") == STAGE_COMPLETION_SCHEMA, "completion schema")
    expect(record.get("scope_id") == SCOPE_ID, "scope ID")
    expect(record.get("scope_class") == SCOPE_CLASS, "scope class")
    expect(record.get("original_full_scope_complete") is False, "bounded scope label")
    expect(record.get("prompt_index") == prompt, "prompt index")
    expect(record.get("status") == "COMPLETE", "COMPLETE status")
    expect(record.get("completion_marker") == COMPLETION_MARKERS[prompt], "exact marker")
    expect(record.get("completion_marker") not in RESERVED_ORIGINAL_MARKERS, "not original marker")
    expect(record.get("adapter_id") == adapter.adapter_id, "adapter ID")
    expect(
        record.get("adapter_contract_sha256") == adapter.contract_sha256,
        "adapter contract hash",
    )
    predecessor_record = record.get("predecessor")
    if predecessor is None:
        expect(predecessor_record is None, "Prompt 4 predecessor must be null")
    elif isinstance(predecessor_record, dict):
        expect(
            predecessor_record.get("prompt_index") == predecessor.prompt_index,
            "predecessor prompt index",
        )
        expect(predecessor_record.get("completion_marker") == predecessor.marker, "predecessor marker")
        expect(
            _same_path(predecessor_record.get("completion_record_path"), predecessor.path),
            "predecessor completion path",
        )
        expect(
            predecessor_record.get("completion_record_sha256") == predecessor.sha256,
            "predecessor completion hash",
        )
    else:
        errors.append("predecessor binding is missing")

    manifest_ref = record.get("artifact_manifest")
    manifest_path: Path | None = None
    manifest_hash = ""
    if not isinstance(manifest_ref, dict):
        errors.append("artifact_manifest reference is missing")
    else:
        try:
            manifest_path = resolve_c_only_path(
                str(manifest_ref.get("path", "")),
                must_exist=True,
                label=f"Prompt {prompt} artifact manifest",
            )
            manifest_hash = file_sha256(manifest_path)
            expect(manifest_ref.get("sha256") == manifest_hash, "artifact manifest hash")
            expect(
                _covered_by_declared_path(manifest_path, declared_paths),
                "artifact manifest covered by material_paths",
            )
        except ProgramContractError as exc:
            errors.append(str(exc))

    gate_refs = record.get("gate_records")
    gate_paths: set[Path] = set()
    if not isinstance(gate_refs, dict):
        errors.append("gate_records object is missing")
    else:
        expect(set(gate_refs) == set(REQUIRED_GATE_NAMES), "exact required gate set")
        for gate_name in REQUIRED_GATE_NAMES:
            ref = gate_refs.get(gate_name)
            if not isinstance(ref, dict):
                errors.append(f"{gate_name} gate reference is missing")
                continue
            try:
                gate_path = resolve_c_only_path(
                    str(ref.get("path", "")),
                    must_exist=True,
                    label=f"Prompt {prompt} {gate_name} gate",
                )
                gate_paths.add(gate_path)
                expect(
                    _covered_by_declared_path(gate_path, declared_paths),
                    f"{gate_name} covered by material_paths",
                )
                expect(ref.get("sha256") == file_sha256(gate_path), f"{gate_name} hash")
                gate = load_json(gate_path)
                expect(gate.get("schema_version") == GATE_SCHEMA, f"{gate_name} schema")
                expect(gate.get("gate") == gate_name, f"{gate_name} name")
                expect(gate.get("status") == "PASS", f"{gate_name} PASS")
                expect(gate.get("prompt_index") == prompt, f"{gate_name} prompt")
                expect(gate.get("scope_id") == SCOPE_ID, f"{gate_name} scope")
            except ProgramContractError as exc:
                errors.append(str(exc))

    artifact_count = 0
    artifact_paths: set[Path] = set()
    if manifest_path is not None:
        try:
            manifest = load_json(manifest_path)
            expect(
                manifest.get("schema_version") == ARTIFACT_MANIFEST_SCHEMA,
                "artifact manifest schema",
            )
            expect(manifest.get("scope_id") == SCOPE_ID, "artifact manifest scope")
            expect(manifest.get("scope_class") == SCOPE_CLASS, "artifact manifest class")
            expect(manifest.get("original_full_scope_complete") is False, "artifact bounded label")
            expect(manifest.get("prompt_index") == prompt, "artifact manifest prompt")
            artifacts = manifest.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                errors.append("artifact manifest must contain at least one artifact")
            else:
                for index, artifact in enumerate(artifacts):
                    if not isinstance(artifact, dict):
                        errors.append(f"artifact {index} is not an object")
                        continue
                    try:
                        artifact_path = resolve_c_only_path(
                            str(artifact.get("path", "")),
                            must_exist=True,
                            label=f"Prompt {prompt} artifact {index}",
                        )
                        artifact_paths.add(artifact_path)
                        expect(
                            _covered_by_declared_path(artifact_path, declared_paths),
                            f"artifact {index} covered by material_paths",
                        )
                        expect(
                            artifact.get("sha256") == file_sha256(artifact_path),
                            f"artifact {index} hash",
                        )
                        expect(artifact.get("required") is True, f"artifact {index} required flag")
                        artifact_count += 1
                    except ProgramContractError as exc:
                        errors.append(str(exc))
        except ProgramContractError as exc:
            errors.append(str(exc))
    expect(gate_paths.issubset(artifact_paths), "all gate records included in artifact manifest")

    if errors:
        raise ProgramContractError(
            f"Prompt {prompt} completion validation failed:\n- " + "\n- ".join(errors)
        )
    assert manifest_path is not None
    return ValidatedCompletion(
        prompt_index=prompt,
        marker=COMPLETION_MARKERS[prompt],
        path=path,
        sha256=file_sha256(path),
        artifact_manifest_path=manifest_path,
        artifact_manifest_sha256=manifest_hash,
        artifact_count=artifact_count,
        adapter_contract_sha256=adapter.contract_sha256,
    )


def _same_path(raw: object, expected: Path) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        return resolve_c_only_path(raw, must_exist=True) == expected.resolve(strict=True)
    except ProgramContractError:
        return False


def _covered_by_declared_path(path: Path, declared_paths: set[Path]) -> bool:
    resolved = path.resolve(strict=True)
    for declared in declared_paths:
        candidate = declared.resolve(strict=declared.exists())
        if resolved == candidate:
            return True
        # Only an explicitly declared directory may cover descendants. For a future
        # output directory, the suffix-free declaration is treated as that directory.
        if (candidate.is_dir() or not candidate.suffix) and resolved.is_relative_to(candidate):
            return True
    return False


def adapter_environment(
    *,
    config: AdapterConfiguration,
    adapter: StageAdapter,
    predecessor: ValidatedCompletion | None,
) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(adapter.environment)
    temporary = adapter.material_paths.get("temporary", ())
    if not temporary:
        raise ProgramContractError(f"Prompt {adapter.prompt_index} has no temporary path")
    temp_path = temporary[0]
    temp_path.mkdir(parents=True, exist_ok=True)
    environment.update(
        {
            "TEMP": str(temp_path),
            "TMP": str(temp_path),
            "TMPDIR": str(temp_path),
            "JP8_SCOPE_ID": SCOPE_ID,
            "JP8_SCOPE_CLASS": SCOPE_CLASS,
            "JP8_ORIGINAL_FULL_SCOPE_COMPLETE": "false",
            "JP8_PROMPT_INDEX": str(adapter.prompt_index),
            "JP8_COMPLETION_MARKER": COMPLETION_MARKERS[adapter.prompt_index],
            "JP8_ADAPTER_ID": adapter.adapter_id,
            "JP8_ADAPTER_CONTRACT_SHA256": adapter.contract_sha256,
            "JP8_PROGRAM_WORKSPACE": str(config.program_workspace),
            "JP8_STAGE_WORKSPACE": str(adapter.stage_workspace),
            "JP8_COMPLETION_RECORD": str(adapter.completion_record),
            "JP8_PROGRESS_RECORD": str(adapter.progress_record),
            "JP8_PREDECESSOR_PROMPT_INDEX": (
                str(predecessor.prompt_index) if predecessor else ""
            ),
            "JP8_PREDECESSOR_COMPLETION_MARKER": predecessor.marker if predecessor else "",
            "JP8_PREDECESSOR_COMPLETION_PATH": str(predecessor.path) if predecessor else "",
            "JP8_PREDECESSOR_COMPLETION_SHA256": predecessor.sha256 if predecessor else "",
        }
    )
    # Never inherit an off-drive cache override into a C:-only campaign. A stage
    # needing one of these caches must declare a C: path explicitly in its adapter.
    for key in (
        "HF_HOME",
        "HUGGINGFACE_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "TORCH_HOME",
        "XDG_CACHE_HOME",
        "PIP_CACHE_DIR",
        "NUMBA_CACHE_DIR",
    ):
        value = environment.get(key)
        if not value:
            continue
        try:
            validate_no_off_c_drive_reference(value, label=f"environment {key}")
        except ProgramContractError:
            environment.pop(key, None)
    return environment


def materialize_command(
    *,
    command: Sequence[str],
    adapter: StageAdapter,
    predecessor: ValidatedCompletion | None,
) -> tuple[str, ...]:
    replacements = {
        _DYNAMIC_COMMAND_TOKENS["PREDECESSOR_COMPLETION_PATH"]: (
            str(predecessor.path) if predecessor else ""
        ),
        _DYNAMIC_COMMAND_TOKENS["PREDECESSOR_COMPLETION_SHA256"]: (
            predecessor.sha256 if predecessor else ""
        ),
        _DYNAMIC_COMMAND_TOKENS["PREDECESSOR_COMPLETION_MARKER"]: (
            predecessor.marker if predecessor else ""
        ),
    }
    materialized: list[str] = []
    for token in command:
        value = token
        for dynamic, replacement in replacements.items():
            if dynamic in value and not replacement:
                raise ProgramContractError(
                    f"Prompt {adapter.prompt_index} command requires a predecessor where none exists"
                )
            value = value.replace(dynamic, replacement)
        materialized.append(value)
    validate_command_paths(
        materialized,
        base=adapter.cwd or Path.cwd(),
        label=f"Prompt {adapter.prompt_index} runtime command",
    )
    return tuple(materialized)


def template_configuration(*, evaluation_tool_root: Path) -> dict[str, Any]:
    root = resolve_c_only_path(
        evaluation_tool_root, must_exist=True, label="template evaluation root"
    )
    workspace = root / "automated_runs/full_pipeline_prompts_4_8_eight_day_v1"
    amendment = root / "runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json"
    return {
        "schema_version": ADAPTER_CONFIG_SCHEMA,
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": False,
        "evaluation_tool_root": str(root),
        "program_workspace": str(workspace),
        "amendment_path": str(amendment),
        "poll_interval_seconds": 10,
        "stages": {
            str(prompt): {
                "adapter_id": f"prompt_{prompt}_adapter_pending",
                "readiness": "NOT_READY",
                "not_ready_reason": "bounded_stage_adapter_not_installed",
                "expected_duration_hours": STAGE_BUDGET_HOURS[prompt],
            }
            for prompt in PROMPTS
        },
    }
