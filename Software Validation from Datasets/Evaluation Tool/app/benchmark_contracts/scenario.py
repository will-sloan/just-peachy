"""Scenario-definition.v1 construction, expansion, validation, and hashing."""

from __future__ import annotations

from copy import deepcopy
import math
from pathlib import PurePosixPath
from typing import Mapping, Sequence

import yaml

from app.benchmark_contracts.canonical import (
    canonical_sha256,
    normalize_project_relative_path,
)
from app.benchmark_contracts.policy import validate_augmentation_request
from app.benchmark_contracts.versions import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    HASH_VERSION,
    MANIFEST_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCORING_POLICY_VERSION,
    SELECTION_SEED,
)
from app.inference_pipeline.resolver import ResolvedPipeline


class ScenarioValidationError(ValueError):
    """Raised when a scenario cannot satisfy scenario-definition.v1."""


IDENTITY_FIELDS = (
    "schema_version",
    "canonicalization_version",
    "hash_version",
    "hash_algorithm",
    "benchmark_manifest",
    "panel",
    "tier",
    "dataset_slice",
    "condition",
    "pipeline",
    "seed",
    "repetition",
    "runtime",
    "timeout_policy",
    "resource_policy",
    "scoring_policy_version",
    "failure_policy",
)
NON_IDENTITY_FIELDS = frozenset(
    {
        "scenario_id",
        "scenario_hash",
        "worker",
        "worker_id",
        "machine",
        "machine_id",
        "absolute_paths",
        "output_path",
        "output_root",
        "start_time",
        "started_at",
        "retry_number",
        "attempt",
        "references",
    }
)


def pipeline_identity_from_resolution(resolution: ResolvedPipeline) -> dict[str, object]:
    """Freeze result-affecting config/model contents without loading any model."""

    resolved_contents = resolution.pipeline_config.to_jsonable()
    components: dict[str, object] = {}
    models: dict[str, object] = {}
    for family in sorted(resolution.component_identities):
        identity = resolution.component_identities[family]
        if not isinstance(identity, Mapping):
            raise ScenarioValidationError(f"component identity {family} must be a mapping")
        component_config = resolved_contents["components"][family]
        component = {
            "family": family,
            "name": identity.get("name"),
            "enabled": bool(identity.get("enabled")),
            "implementation_class": identity.get("implementation_class"),
            "adapter": component_config.get("adapter"),
            "config_contents": component_config,
            "config_contents_sha256": canonical_sha256(component_config),
            "source_config_sha256": identity.get("source_config_sha256"),
            "qualification_status": identity.get("qualification_status"),
        }
        components[family] = component
        model_identity = identity.get("model_identity")
        assets = identity.get("model_asset_identity")
        models[family] = {
            "model_identity": deepcopy(model_identity),
            "assets": [
                {
                    "configured_identity": item.get("configured_identity"),
                    "expected_bytes": item.get("expected_bytes"),
                    "expected_sha256": item.get("expected_sha256"),
                    "present": item.get("present"),
                    "observed_bytes": item.get("observed_bytes"),
                    "observed_sha256": item.get("observed_sha256"),
                    "hash_matches": item.get("hash_matches"),
                }
                for item in assets or []
                if isinstance(item, Mapping)
            ],
        }
    selected_contents = yaml.safe_load(
        resolution.selected_config_path.read_text(encoding="utf-8")
    )
    if not isinstance(selected_contents, Mapping):
        raise ScenarioValidationError("selected inference config must be a mapping")
    return {
        "pipeline_id": resolution.pipeline_config.config_name,
        "environment_profile": resolution.environment_profile,
        "selected_config_contents": dict(selected_contents),
        "selected_config_sha256": resolution.selected_config_sha256,
        "resolved_config_contents": resolved_contents,
        "resolved_config_sha256": canonical_sha256(resolved_contents),
        "components": components,
        "models": models,
    }


def scenario_identity_payload(scenario: Mapping[str, object]) -> dict[str, object]:
    """Extract only the public result-affecting v1 identity fields."""

    missing = [field for field in IDENTITY_FIELDS if field not in scenario]
    if missing:
        raise ScenarioValidationError(f"scenario missing identity fields: {missing}")
    payload = {field: deepcopy(scenario[field]) for field in IDENTITY_FIELDS}
    manifest = _mapping(payload, "benchmark_manifest")
    payload["benchmark_manifest"] = {
        "schema_version": manifest.get("schema_version"),
        "manifest_id": manifest.get("manifest_id"),
        "sha256": manifest.get("sha256"),
    }
    data_slice = _mapping(payload, "dataset_slice")
    data_slice.pop("row_count", None)
    payload["dataset_slice"] = data_slice
    return _normalize_relative_paths(payload)


def scenario_identity(scenario: Mapping[str, object]) -> tuple[str, str]:
    """Return full SHA-256 and scenario_<first-12-hex>."""

    validate_scenario(scenario, require_identity=False)
    digest = canonical_sha256(scenario_identity_payload(scenario))
    return digest, f"scenario_{digest[:12].lower()}"


def finalize_scenario(scenario: Mapping[str, object]) -> dict[str, object]:
    """Validate one requested scenario and attach its immutable ID/hash."""

    result = deepcopy(dict(scenario))
    digest, scenario_id = scenario_identity(result)
    result["scenario_hash"] = digest
    result["scenario_id"] = scenario_id
    validate_scenario(result, require_identity=True)
    return result


def expand_scenarios(
    *,
    manifest_identity: Mapping[str, object],
    manifest_rows: Sequence[Mapping[str, object]],
    pipeline_identities: Sequence[Mapping[str, object]],
    condition_sets: Mapping[str, Sequence[Mapping[str, object]]],
    repetitions: int = 1,
    timeout_policy: Mapping[str, object] | None = None,
    resource_policy: Mapping[str, object] | None = None,
    failure_policy: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    """Expand manifest slices and named conditions into canonical scenarios."""

    if repetitions <= 0:
        raise ScenarioValidationError("repetitions must be positive")
    if not manifest_rows:
        return []
    slices: dict[tuple[str, ...], list[Mapping[str, object]]] = {}
    for row in manifest_rows:
        panel = str(row.get("panel") or "")
        tier = str(row.get("benchmark_tier") or "")
        dataset = str(row.get("dataset") or "")
        role = str(row.get("role") or "")
        protocol = str(row.get("protocol_condition") or "")
        key = (panel, tier, dataset, role if panel == "speaker_protocol" else "", protocol)
        slices.setdefault(key, []).append(row)

    scenarios: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for key in sorted(slices):
        panel, tier, dataset, role, protocol = key
        rows = slices[key]
        conditions = _conditions_for_slice(
            panel,
            tier,
            protocol,
            condition_sets,
        )
        for condition in conditions:
            for row in rows:
                validate_augmentation_request(row, condition)
            for pipeline in pipeline_identities:
                runtime_config = _mapping(pipeline, "resolved_config_contents").get("runtime")
                if not isinstance(runtime_config, Mapping):
                    raise ScenarioValidationError("pipeline identity missing runtime contents")
                runtime = {
                    "device": str(runtime_config.get("device") or "cpu"),
                    "dtype": str(runtime_config.get("precision") or "float32"),
                    "batch_size": int(runtime_config.get("max_batch_size") or 1),
                    "settings": dict(runtime_config),
                }
                for repetition in range(1, repetitions + 1):
                    data_slice: dict[str, object] = {
                        "dataset": dataset,
                        "slice_id": _slice_id(panel, tier, dataset, role, protocol),
                        "filters": {
                            "panel": panel,
                            "benchmark_tier": tier,
                            "role": role or None,
                            "protocol_condition": protocol or None,
                        },
                        "row_count": len(rows),
                    }
                    requested = {
                        "schema_version": SCENARIO_SCHEMA_VERSION,
                        "canonicalization_version": CANONICALIZATION_VERSION,
                        "hash_version": HASH_VERSION,
                        "hash_algorithm": HASH_ALGORITHM,
                        "benchmark_manifest": dict(manifest_identity),
                        "panel": panel,
                        "tier": tier,
                        "dataset_slice": data_slice,
                        "condition": deepcopy(dict(condition)),
                        "pipeline": deepcopy(dict(pipeline)),
                        "seed": SELECTION_SEED,
                        "repetition": repetition,
                        "runtime": runtime,
                        "timeout_policy": dict(
                            timeout_policy
                            or {"timeout_seconds": 14400, "on_timeout": "fail_scenario"}
                        ),
                        "resource_policy": dict(
                            resource_policy
                            or {
                                "sample_interval_seconds": 1.0,
                                "gpu_concurrency": 1,
                                "collect_cpu": True,
                                "collect_gpu": True,
                            }
                        ),
                        "scoring_policy_version": SCORING_POLICY_VERSION,
                        "failure_policy": dict(
                            failure_policy
                            or {
                                "continue_after_item_failure": True,
                                "max_item_retries": 0,
                                "max_missing_prediction_rate": 0.05,
                            }
                        ),
                    }
                    scenario = finalize_scenario(requested)
                    if scenario["scenario_id"] in seen_ids:
                        raise ScenarioValidationError(
                            f"scenario ID collision: {scenario['scenario_id']}"
                        )
                    seen_ids.add(str(scenario["scenario_id"]))
                    scenarios.append(scenario)
    return sorted(scenarios, key=lambda item: str(item["scenario_id"]))


def validate_scenario(
    scenario: Mapping[str, object],
    *,
    require_identity: bool = True,
) -> None:
    """Validate required v1 fields and reject unknown/broken contract versions."""

    if scenario.get("schema_version") != SCENARIO_SCHEMA_VERSION:
        raise ScenarioValidationError("unsupported scenario schema version")
    if scenario.get("canonicalization_version") != CANONICALIZATION_VERSION:
        raise ScenarioValidationError("unsupported canonicalization version")
    if scenario.get("hash_version") != HASH_VERSION:
        raise ScenarioValidationError("unsupported scenario hash version")
    if scenario.get("hash_algorithm") != HASH_ALGORITHM:
        raise ScenarioValidationError("unsupported hash algorithm")
    missing = [field for field in IDENTITY_FIELDS if field not in scenario]
    if missing:
        raise ScenarioValidationError(f"scenario missing fields: {missing}")
    if scenario.get("panel") not in {
        "controlled_clean",
        "native_robustness",
        "speaker_protocol",
    }:
        raise ScenarioValidationError("invalid scenario panel")
    if scenario.get("tier") not in {"small", "standard", "large"}:
        raise ScenarioValidationError("invalid scenario tier")
    if scenario.get("seed") != SELECTION_SEED:
        raise ScenarioValidationError("scenario seed must be 3800")
    if not isinstance(scenario.get("repetition"), int) or int(scenario["repetition"]) <= 0:
        raise ScenarioValidationError("scenario repetition must be a positive integer")
    manifest = _mapping(scenario, "benchmark_manifest")
    for field in ("schema_version", "manifest_id", "sha256"):
        if not manifest.get(field):
            raise ScenarioValidationError(f"benchmark manifest missing {field}")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ScenarioValidationError("unsupported benchmark manifest schema version")
    if not _is_sha256(manifest.get("sha256")):
        raise ScenarioValidationError("benchmark manifest SHA-256 is invalid")
    expected_manifest_id = f"manifest_{str(manifest['sha256'])[:12].lower()}"
    if manifest.get("manifest_id") != expected_manifest_id:
        raise ScenarioValidationError("benchmark manifest ID does not match its SHA-256")
    data_slice = _mapping(scenario, "dataset_slice")
    for field in ("dataset", "slice_id", "filters"):
        if field not in data_slice:
            raise ScenarioValidationError(f"dataset slice missing {field}")
    if not isinstance(data_slice.get("filters"), Mapping):
        raise ScenarioValidationError("dataset slice filters must be a mapping")
    row_count = data_slice.get("row_count")
    if row_count is not None and (
        not isinstance(row_count, int) or isinstance(row_count, bool) or row_count <= 0
    ):
        raise ScenarioValidationError("dataset slice row count must be positive")
    condition = _mapping(scenario, "condition")
    for field in ("id", "augmentation", "noise_type", "snr_db", "rir"):
        if field not in condition:
            raise ScenarioValidationError(f"condition must explicitly include {field}")
    _validate_condition(condition)
    runtime = _mapping(scenario, "runtime")
    for field in ("device", "dtype", "batch_size", "settings"):
        if field not in runtime:
            raise ScenarioValidationError(f"runtime missing {field}")
    pipeline = _mapping(scenario, "pipeline")
    for field in (
        "pipeline_id",
        "selected_config_contents",
        "selected_config_sha256",
        "resolved_config_contents",
        "resolved_config_sha256",
        "components",
        "models",
    ):
        if field not in pipeline:
            raise ScenarioValidationError(f"pipeline identity missing {field}")
    environment_profile = pipeline.get("environment_profile")
    if environment_profile is not None and (
        not isinstance(environment_profile, str) or not environment_profile.strip()
    ):
        raise ScenarioValidationError("pipeline environment profile must be non-empty")
    if not _is_sha256(pipeline.get("selected_config_sha256")):
        raise ScenarioValidationError("selected config SHA-256 is invalid")
    resolved_contents = pipeline["resolved_config_contents"]
    if not isinstance(resolved_contents, Mapping):
        raise ScenarioValidationError("resolved config contents must be a mapping")
    expected_resolved_hash = canonical_sha256(resolved_contents)
    if pipeline.get("resolved_config_sha256") != expected_resolved_hash:
        raise ScenarioValidationError("resolved config contents do not match their SHA-256")
    components = pipeline.get("components")
    if not isinstance(components, Mapping):
        raise ScenarioValidationError("pipeline components must be a mapping")
    for family, raw_component in components.items():
        if not isinstance(raw_component, Mapping):
            raise ScenarioValidationError(f"pipeline component {family} must be a mapping")
        if raw_component.get("family") != family:
            raise ScenarioValidationError(f"pipeline component family mismatch for {family}")
        if "config_contents" not in raw_component:
            raise ScenarioValidationError(f"pipeline component {family} missing config contents")
        expected_component_hash = canonical_sha256(raw_component["config_contents"])
        if raw_component.get("config_contents_sha256") != expected_component_hash:
            raise ScenarioValidationError(
                f"pipeline component {family} contents do not match their SHA-256"
            )
        source_hash = raw_component.get("source_config_sha256")
        if source_hash is not None and not _is_sha256(source_hash):
            raise ScenarioValidationError(
                f"pipeline component {family} source config SHA-256 is invalid"
            )
    models = pipeline.get("models")
    if not isinstance(models, Mapping):
        raise ScenarioValidationError("pipeline models must be a mapping")
    if set(models) != set(components):
        raise ScenarioValidationError("pipeline model and component families must match")
    _validate_model_hashes(models)
    resolved_runtime = resolved_contents.get("runtime")
    if not isinstance(resolved_runtime, Mapping):
        raise ScenarioValidationError("resolved config runtime must be a mapping")
    if runtime.get("settings") != resolved_runtime:
        raise ScenarioValidationError("scenario runtime settings must match resolved config")
    if runtime.get("device") != resolved_runtime.get("device"):
        raise ScenarioValidationError("scenario device must match resolved config")
    if runtime.get("dtype") != resolved_runtime.get("precision"):
        raise ScenarioValidationError("scenario dtype must match resolved config")
    if runtime.get("batch_size") != resolved_runtime.get("max_batch_size"):
        raise ScenarioValidationError("scenario batch size must match resolved config")
    for policy_name in ("timeout_policy", "resource_policy", "failure_policy"):
        if not _mapping(scenario, policy_name):
            raise ScenarioValidationError(f"{policy_name} must not be empty")
    scenario_identity_payload(scenario)
    if require_identity:
        digest, scenario_id = scenario_identity_payload_hash(scenario)
        if scenario.get("scenario_hash") != digest or scenario.get("scenario_id") != scenario_id:
            raise ScenarioValidationError("stored scenario ID/hash does not match canonical payload")


def scenario_identity_payload_hash(scenario: Mapping[str, object]) -> tuple[str, str]:
    digest = canonical_sha256(scenario_identity_payload(scenario))
    return digest, f"scenario_{digest[:12].lower()}"


def _validate_condition(condition: Mapping[str, object]) -> None:
    condition_id = condition.get("id")
    if not isinstance(condition_id, str) or not condition_id.strip():
        raise ScenarioValidationError("condition ID must be a non-empty string")
    augmentation = condition.get("augmentation")
    if augmentation not in {"none", "noise", "reverb", "reverb_noise"}:
        raise ScenarioValidationError("invalid condition augmentation")
    noise_type = condition.get("noise_type")
    snr_db = condition.get("snr_db")
    rir = condition.get("rir")
    uses_noise = augmentation in {"noise", "reverb_noise"}
    uses_rir = augmentation in {"reverb", "reverb_noise"}
    if uses_noise:
        if noise_type not in {"white", "pink"} or not _is_number(snr_db):
            raise ScenarioValidationError(
                "noise conditions require white/pink noise and a finite numeric SNR"
            )
    elif noise_type is not None or snr_db is not None:
        raise ScenarioValidationError("non-noise conditions require null noise type and SNR")
    if uses_rir:
        if not isinstance(rir, Mapping):
            raise ScenarioValidationError("reverberation conditions require an RIR identity")
        for field in (
            "rir_id",
            "environment",
            "resolved_identifier",
            "relative_path",
            "sha256",
        ):
            if not rir.get(field):
                raise ScenarioValidationError(f"RIR identity missing {field}")
        relative_path = normalize_project_relative_path(str(rir["relative_path"]))
        if PurePosixPath(relative_path).name != rir.get("resolved_identifier"):
            raise ScenarioValidationError("RIR path does not match its resolved identifier")
        if not _is_sha256(rir.get("sha256")):
            raise ScenarioValidationError("RIR SHA-256 is invalid")
    elif rir is not None:
        raise ScenarioValidationError("non-reverberation conditions require a null RIR")


def _validate_model_hashes(models: Mapping[str, object]) -> None:
    for family, raw_model in models.items():
        if not isinstance(raw_model, Mapping):
            raise ScenarioValidationError(f"pipeline model {family} must be a mapping")
        assets = raw_model.get("assets")
        if not isinstance(assets, list):
            raise ScenarioValidationError(f"pipeline model {family} assets must be a list")
        for index, asset in enumerate(assets):
            if not isinstance(asset, Mapping):
                raise ScenarioValidationError(
                    f"pipeline model {family} asset {index} must be a mapping"
                )
            for field in ("expected_sha256", "observed_sha256"):
                value = asset.get(field)
                if value is not None and not _is_sha256(value):
                    raise ScenarioValidationError(
                        f"pipeline model {family} asset {index} has invalid {field}"
                    )
            if asset.get("hash_matches") is True and (
                asset.get("expected_sha256") != asset.get("observed_sha256")
            ):
                raise ScenarioValidationError(
                    f"pipeline model {family} asset {index} hash match is inconsistent"
                )


def _conditions_for_slice(
    panel: str,
    tier: str,
    protocol_condition: str,
    condition_sets: Mapping[str, Sequence[Mapping[str, object]]],
) -> Sequence[Mapping[str, object]]:
    if panel == "native_robustness":
        return _required_condition_set(condition_sets, "native_only")
    if panel == "speaker_protocol":
        if protocol_condition == "degraded":
            return _required_condition_set(condition_sets, "speaker_degraded")
        clean = [
            condition
            for condition in _required_condition_set(condition_sets, "smoke")
            if condition.get("id") == "clean"
        ]
        if len(clean) != 1:
            raise ScenarioValidationError("smoke condition set must contain one clean condition")
        return clean
    return _required_condition_set(
        condition_sets,
        "smoke" if tier == "small" else "core_controlled",
    )


def _required_condition_set(
    condition_sets: Mapping[str, Sequence[Mapping[str, object]]],
    name: str,
) -> Sequence[Mapping[str, object]]:
    values = condition_sets.get(name)
    if values is None:
        raise ScenarioValidationError(f"missing condition set {name}")
    return values


def _slice_id(panel: str, tier: str, dataset: str, role: str, protocol: str) -> str:
    parts = [panel, tier, dataset]
    if role:
        parts.append(role)
    if protocol:
        parts.append(protocol)
    return ":".join(parts)


def _mapping(value: Mapping[str, object], key: str) -> dict[str, object]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise ScenarioValidationError(f"scenario field {key} must be a mapping")
    return deepcopy(dict(item))


def _normalize_relative_paths(value: object, key: str | None = None) -> object:
    if isinstance(value, Mapping):
        return {
            str(item_key): _normalize_relative_paths(item, str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_relative_paths(item, key) for item in value]
    if isinstance(value, tuple):
        return [_normalize_relative_paths(item, key) for item in value]
    if isinstance(value, str) and key in {
        "relative_path",
        "audio_path_project_relative",
        "source_audio_path_project_relative",
    }:
        return normalize_project_relative_path(value)
    return value


def _is_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789ABCDEF" for char in text)


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
