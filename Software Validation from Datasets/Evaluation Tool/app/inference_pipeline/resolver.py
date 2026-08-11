"""Scenario-independent inference pipeline composition and provenance."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path
import platform
from typing import Mapping, Sequence

import yaml

from app.inference_pipeline.catalog import (
    CATALOG_SCHEMA_VERSION,
    ComponentCatalog,
    ComponentCatalogEntry,
)
from app.inference_pipeline.config import (
    COMPONENT_SLOTS,
    ComponentConfig,
    ConfigValidationError,
    PipelineConfig,
)
from app.inference_pipeline.registry import resolve_components
from app.inference_pipeline.typing import JsonObject
from app.utils.json_utils import write_json
from app.utils.run_artifacts import write_yaml


RESOLUTION_SCHEMA_VERSION = "resolved-inference-config.v1"
SELECTION_SCHEMA_VERSION = "configured-inference-selection.v1"
RUNTIME_OVERRIDE_FIELDS = {
    "allow_model_downloads",
    "cache_dir",
    "device",
    "dry_run",
    "max_batch_size",
    "num_threads",
    "precision",
    "sample_rate_hz",
}


class PipelineResolutionError(ConfigValidationError):
    """Raised when selected components cannot form a safe executable pipeline."""


@dataclass(frozen=True)
class OverrideRecord:
    """One explicit change from the composed source value to its final value."""

    path: str
    source_present: bool
    source_value: object
    requested_value: object
    final_value: object
    source_origin: str

    def to_jsonable(self) -> JsonObject:
        return {
            "path": self.path,
            "source_present": self.source_present,
            "source_value": _json_value(self.source_value),
            "requested_value": _json_value(self.requested_value),
            "final_value": _json_value(self.final_value),
            "source_origin": self.source_origin,
        }


@dataclass(frozen=True)
class ResolvedPipeline:
    """Executable config plus complete immutable resolution provenance."""

    selected_config_path: Path
    selected_config_sha256: str
    environment_profile: str
    pipeline_config: PipelineConfig
    catalog: ComponentCatalog
    component_sources: JsonObject
    component_identities: JsonObject
    component_overrides: JsonObject
    setting_overrides: JsonObject
    override_history: tuple[OverrideRecord, ...]
    warnings: tuple[str, ...]

    def selected_reference(self) -> JsonObject:
        return {
            "schema_version": SELECTION_SCHEMA_VERSION,
            "selected_inference_config": {
                "path": _portable_path(self.selected_config_path),
                "sha256": self.selected_config_sha256,
            },
            "source_component_registry": {
                "schema_version": CATALOG_SCHEMA_VERSION,
                "path": _portable_path(self.catalog.registry_path),
                "sha256": self.catalog.registry_sha256,
                "registry_version": self.catalog.registry_version,
            },
            "environment_profile": self.environment_profile,
            "component_overrides": dict(self.component_overrides),
            "setting_overrides": dict(self.setting_overrides),
        }

    def resolved_config_mapping(self) -> JsonObject:
        data = self.pipeline_config.to_jsonable()
        data["resolution"] = {
            "schema_version": RESOLUTION_SCHEMA_VERSION,
            "selected_config": self.selected_reference()["selected_inference_config"],
            "component_sources": dict(self.component_sources),
            "override_history": [item.to_jsonable() for item in self.override_history],
            "warnings": list(self.warnings),
            "implicit_model_downloads_prohibited": True,
            "environment_profile": self.environment_profile,
        }
        return data

    def component_identity_summary(self) -> JsonObject:
        return {
            "schema_version": "resolved-component-identities.v1",
            "components": dict(self.component_identities),
        }

    def write_artifacts(self, output_dir: Path) -> JsonObject:
        """Persist selected, resolved, identity, and warning artifacts."""

        output_dir.mkdir(parents=True, exist_ok=True)
        selected_path = output_dir / "selected_inference_config.json"
        resolved_path = output_dir / "resolved_inference_config.yaml"
        identities_path = output_dir / "component_identity_summary.json"
        warnings_path = output_dir / "configuration_warnings.json"
        write_json(selected_path, self.selected_reference())
        write_yaml(resolved_path, self.resolved_config_mapping())
        write_json(identities_path, self.component_identity_summary())
        write_json(
            warnings_path,
            {
                "schema_version": "configuration-warnings.v1",
                "count": len(self.warnings),
                "warnings": list(self.warnings),
            },
        )
        return {
            "selected_inference_config": selected_path,
            "resolved_inference_config": resolved_path,
            "component_identity_summary": identities_path,
            "configuration_warnings": warnings_path,
        }


def resolve_pipeline(
    selected_config_path: Path | str,
    *,
    component_overrides: Mapping[str, str] | None = None,
    setting_overrides: Mapping[str, object] | None = None,
    environment_profile: str | None = None,
    catalog: ComponentCatalog | None = None,
) -> ResolvedPipeline:
    """Compose an existing pipeline config without changing any source YAML."""

    selected_path = Path(selected_config_path).resolve()
    if not selected_path.is_file():
        raise FileNotFoundError(f"selected inference config does not exist: {selected_path}")
    catalog = catalog or ComponentCatalog.load()
    raw_selected = _yaml_mapping(selected_path)
    source_pipeline = PipelineConfig.from_yaml_path(selected_path)
    if source_pipeline.future:
        raise PipelineResolutionError(
            f"future-only inference config cannot be executed: {source_pipeline.config_name}"
        )

    composed = source_pipeline.to_jsonable()
    components = composed.get("components")
    if not isinstance(components, dict):
        raise PipelineResolutionError("composed pipeline has no component mapping")
    component_sources = _initial_component_sources(
        selected_path,
        raw_selected,
        source_pipeline,
        catalog,
    )
    history: list[OverrideRecord] = []
    selected_component_overrides = {
        str(key): str(value) for key, value in (component_overrides or {}).items()
    }
    for family, name in selected_component_overrides.items():
        if family not in COMPONENT_SLOTS:
            raise PipelineResolutionError(f"unknown component family override {family!r}")
        entry = catalog.get(family, name)
        source_component = deepcopy(components[family])
        replacement = _replacement_component(entry)
        components[family] = replacement
        component_sources[family] = _component_source(
            entry,
            source_type="component_override",
            fallback_path=catalog.registry_path,
        )
        history.append(
            OverrideRecord(
                path=f"components.{family}.name",
                source_present=True,
                source_value=source_component.get("name"),
                requested_value=name,
                final_value=replacement["name"],
                source_origin=_portable_path(selected_path),
            )
        )
        if source_component.get("enabled") != replacement.get("enabled"):
            history.append(
                OverrideRecord(
                    path=f"components.{family}.enabled",
                    source_present=True,
                    source_value=source_component.get("enabled"),
                    requested_value=replacement.get("enabled"),
                    final_value=replacement.get("enabled"),
                    source_origin=str(component_sources[family]["source_path"]),
                )
            )

    selected_setting_overrides = {
        str(key): _json_value(value) for key, value in (setting_overrides or {}).items()
    }
    for path, requested_value in selected_setting_overrides.items():
        _validate_override_path(path)
        source_present, source_value = _get_dotted(composed, path)
        _set_dotted(composed, path, requested_value)
        final_present, final_value = _get_dotted(composed, path)
        if not final_present:
            raise PipelineResolutionError(f"override did not produce a final value: {path}")
        history.append(
            OverrideRecord(
                path=path,
                source_present=source_present,
                source_value=source_value,
                requested_value=requested_value,
                final_value=final_value,
                source_origin=_override_origin(path, selected_path, component_sources),
            )
        )

    final_config = PipelineConfig.from_mapping(composed)
    resolve_components(final_config)
    _prohibit_model_downloads(final_config)
    resolved_environment = _resolve_environment_profile(
        final_config,
        catalog,
        requested=environment_profile,
    )
    warnings = _compatibility_warnings_and_errors(final_config, catalog)
    component_identities = _selected_component_identities(
        final_config,
        catalog,
        component_sources,
    )
    return ResolvedPipeline(
        selected_config_path=selected_path,
        selected_config_sha256=_sha256(selected_path),
        environment_profile=resolved_environment,
        pipeline_config=final_config,
        catalog=catalog,
        component_sources=component_sources,
        component_identities=component_identities,
        component_overrides=selected_component_overrides,
        setting_overrides=selected_setting_overrides,
        override_history=tuple(history),
        warnings=tuple(warnings),
    )


def parse_assignments(values: Sequence[str] | None, *, label: str) -> dict[str, object]:
    """Parse repeatable ``path=value`` CLI assignments using YAML scalar values."""

    result: dict[str, object] = {}
    for value in values or ():
        if "=" not in value:
            raise PipelineResolutionError(f"{label} must use key=value: {value!r}")
        key, raw_value = value.split("=", 1)
        key = key.strip()
        if not key or not raw_value.strip():
            raise PipelineResolutionError(f"{label} must use non-empty key=value: {value!r}")
        if key in result:
            raise PipelineResolutionError(f"duplicate {label} key: {key}")
        result[key] = yaml.safe_load(raw_value)
    return result


def _initial_component_sources(
    selected_path: Path,
    raw_selected: Mapping[str, object],
    pipeline: PipelineConfig,
    catalog: ComponentCatalog,
) -> JsonObject:
    raw_components = raw_selected.get("components")
    if not isinstance(raw_components, Mapping):
        raise PipelineResolutionError("selected config components must be a mapping")
    result: JsonObject = {}
    for family in COMPONENT_SLOTS:
        configured = pipeline.components[family]
        entry = catalog.get(family, configured.name)
        raw_value = raw_components.get(family)
        if isinstance(raw_value, str):
            source_path = _resolve_component_reference(selected_path, raw_value)
            source_type = "component_fragment"
        else:
            source_path = selected_path
            source_type = "pipeline_inline"
        result[family] = _component_source(
            entry,
            source_type=source_type,
            fallback_path=source_path,
            actual_source_path=source_path,
        )
    return result


def _component_source(
    entry: ComponentCatalogEntry,
    *,
    source_type: str,
    fallback_path: Path,
    actual_source_path: Path | None = None,
) -> JsonObject:
    path = actual_source_path
    if path is None and entry.source_config_path is not None:
        path = _tool_root() / entry.source_config_path
    path = path or fallback_path
    return {
        "family": entry.family,
        "name": entry.name,
        "source_type": source_type,
        "source_path": _portable_path(path),
        "source_sha256": _sha256(path),
        "registry_config_path": entry.source_config_path,
        "registry_config_sha256": entry.source_config_sha256,
    }


def _replacement_component(entry: ComponentCatalogEntry) -> JsonObject:
    if entry.configured_component is not None:
        component = deepcopy(dict(entry.configured_component))
        component.pop("slot", None)
        return ComponentConfig.from_mapping(component, slot=entry.family).to_jsonable()
    return {
        "name": entry.name,
        "enabled": False,
        "adapter": entry.registry_adapter_class,
        "params": {},
        "notes": "Disabled selection resolved from the runtime catalog.",
    }


def _compatibility_warnings_and_errors(
    config: PipelineConfig,
    catalog: ComponentCatalog,
) -> list[str]:
    warnings: list[str] = []
    active = {
        family: component
        for family, component in config.components.items()
        if component.enabled and not component.name.startswith("no_op_")
    }
    segmentation = active.get("segmentation")
    if segmentation is not None and segmentation.name == "vad_chunks":
        if "vad" not in active and "diarization" not in active:
            raise PipelineResolutionError(
                "vad_chunks requires an active VAD or diarization component"
            )
    if "speaker_matching" in active and "speaker_embedding" not in active:
        raise PipelineResolutionError(
            "speaker matching requires an active speaker embedding component"
        )

    device = _normalized_device(config.runtime.device)
    dtype = config.runtime.precision.strip().lower()
    if device.startswith("cuda"):
        for family, component in active.items():
            entry = catalog.get(family, component.name)
            if not bool(entry.hardware_requirements.get("cuda")):
                raise PipelineResolutionError(
                    f"{family}.{component.name} does not declare CUDA support"
                )

    current_os = platform.system().lower()
    for family, component in active.items():
        entry = catalog.get(family, component.name)
        if entry.qualification_status not in {
            "qualified",
            "qualified_with_warnings",
            "contract_qualified",
        }:
            warnings.append(
                f"{family}.{component.name} readiness={entry.qualification_status}; "
                "execution may report unavailable"
            )
        if entry.credential_requirements:
            warnings.append(
                f"{family}.{component.name} credential_required: "
                + ", ".join(entry.credential_requirements)
            )
        supported = tuple(item.lower() for item in entry.supported_operating_systems)
        if supported and not any(item == current_os for item in supported):
            warnings.append(
                f"{family}.{component.name} platform requirement {list(entry.supported_operating_systems)} "
                f"does not match {platform.system()}"
            )
        missing_assets = [
            str(asset.get("path"))
            for asset in entry.model_asset_identity
            if asset.get("present") is False
        ]
        if missing_assets:
            warnings.append(
                f"{family}.{component.name} asset_required: " + ", ".join(missing_assets)
            )
        params = component.params or {}
        component_device = params.get("device")
        if component_device is not None and _normalized_device(component_device) != device:
            raise PipelineResolutionError(
                f"{family}.{component.name} component device={component_device} differs "
                f"from runtime device={config.runtime.device}; implicit device fallback is prohibited"
            )
        component_dtype = params.get("dtype")
        if component_dtype is not None and str(component_dtype).strip().lower() != dtype:
            raise PipelineResolutionError(
                f"{family}.{component.name} component dtype={component_dtype} differs "
                f"from runtime precision={config.runtime.precision}; implicit dtype selection is prohibited"
            )
        provider = params.get("provider")
        if provider is not None and device.startswith("cuda") and str(provider).lower() == "cpu":
            raise PipelineResolutionError(
                f"{family}.{component.name} provider=cpu while runtime device is CUDA; "
                "implicit CPU fallback is prohibited"
            )
        device_family = _device_family(device)
        requested_device_dtype = f"{device_family}/{dtype}"
        supported_device_dtype = {
            value.strip().lower() for value in entry.device_dtype_settings
        }
        backend_compute_type = params.get("compute_type")
        declared_candidates = {requested_device_dtype, f"{device_family}/backend-default"}
        if backend_compute_type is not None:
            declared_candidates.add(
                f"{device_family}/{str(backend_compute_type).strip().lower()}"
            )
        if supported_device_dtype and not (
            declared_candidates & supported_device_dtype
        ):
            raise PipelineResolutionError(
                f"{family}.{component.name} does not declare support for "
                f"{requested_device_dtype} or its configured backend compute type"
            )

    if config.runtime.dry_run:
        warnings.append("runtime.dry_run=true; this configuration is not a real model run")
    if "asr" not in active:
        warnings.append("no real ASR component is active; output may be empty or contract-only")
    return warnings


def _resolve_environment_profile(
    config: PipelineConfig,
    catalog: ComponentCatalog,
    *,
    requested: str | None,
) -> str:
    active_entries = [
        catalog.get(family, component.name)
        for family, component in config.components.items()
        if component.enabled and not component.name.startswith("no_op_")
    ]
    device_family = _device_family(config.runtime.device)
    if requested is not None:
        profile = requested.strip()
        if not profile:
            raise PipelineResolutionError("environment profile must not be empty")
        incompatible = [
            f"{entry.family}.{entry.name}"
            for entry in active_entries
            if profile not in entry.environment_profiles
        ]
        if incompatible:
            raise PipelineResolutionError(
                f"environment profile {profile!r} is incompatible with: "
                + ", ".join(sorted(incompatible))
            )
        _validate_profile_device(profile, device_family)
        return profile

    if not active_entries:
        return "core-cpu"
    compatible = set(active_entries[0].environment_profiles)
    for entry in active_entries[1:]:
        compatible.intersection_update(entry.environment_profiles)
    if not compatible:
        names = ", ".join(
            sorted(f"{entry.family}.{entry.name}" for entry in active_entries)
        )
        raise PipelineResolutionError(
            "active components have no common environment profile: " + names
        )
    configured_profile = config.profile.strip()
    if configured_profile in compatible:
        _validate_profile_device(configured_profile, device_family)
        return configured_profile
    if device_family == "cuda":
        if "core-cuda" not in compatible:
            raise PipelineResolutionError(
                "CUDA runtime has no compatible core-cuda environment profile"
            )
        return "core-cuda"
    non_core = sorted(profile for profile in compatible if profile != "core-cpu")
    constrained = [
        entry
        for entry in active_entries
        if set(entry.environment_profiles) != {"core-cpu"}
        and "core-cpu" not in entry.environment_profiles
    ]
    if constrained and non_core:
        return non_core[0]
    if "core-cpu" in compatible:
        return "core-cpu"
    return sorted(compatible)[0]


def _normalized_device(value: object) -> str:
    device = str(value).strip().lower()
    if device == "cuda":
        return "cuda:0"
    return device


def _device_family(value: object) -> str:
    device = _normalized_device(value)
    return "cuda" if device.startswith("cuda:") else device


def _validate_profile_device(profile: str, device_family: str) -> None:
    if profile == "core-cuda" and device_family != "cuda":
        raise PipelineResolutionError(
            f"environment profile {profile!r} requires a CUDA runtime device"
        )
    if profile == "core-cpu" and device_family != "cpu":
        raise PipelineResolutionError(
            f"environment profile {profile!r} cannot execute runtime device {device_family!r}"
        )


def _prohibit_model_downloads(config: PipelineConfig) -> None:
    if config.runtime.allow_model_downloads:
        raise PipelineResolutionError("runtime.allow_model_downloads must remain false")
    for family, component in config.components.items():
        value = (component.params or {}).get("allow_model_downloads")
        if value not in (None, False):
            raise PipelineResolutionError(
                f"components.{family}.params.allow_model_downloads must remain false"
            )


def _selected_component_identities(
    config: PipelineConfig,
    catalog: ComponentCatalog,
    sources: JsonObject,
) -> JsonObject:
    result: JsonObject = {}
    for family in COMPONENT_SLOTS:
        component = config.components[family]
        entry = catalog.get(family, component.name)
        row = entry.to_jsonable()
        row["enabled"] = component.enabled
        row["resolved_adapter"] = component.adapter
        row["resolved_params"] = dict(component.params or {})
        row["source"] = dict(sources[family])
        result[family] = row
    return result


def _validate_override_path(path: str) -> None:
    parts = path.split(".")
    if (
        parts[0] == "runtime"
        and len(parts) == 2
        and parts[1] in RUNTIME_OVERRIDE_FIELDS
    ):
        return
    if len(parts) >= 3 and parts[0] == "components" and parts[1] in COMPONENT_SLOTS:
        if parts[2] in {"enabled", "adapter", "notes"} and len(parts) == 3:
            return
        if parts[2] == "params" and len(parts) >= 4:
            return
    raise PipelineResolutionError(
        "setting override must target a supported runtime field, "
        "components.<family>.enabled|adapter|notes, or components.<family>.params.<field>"
    )


def _get_dotted(mapping: Mapping[str, object], path: str) -> tuple[bool, object]:
    current: object = mapping
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _set_dotted(mapping: JsonObject, path: str, value: object) -> None:
    parts = path.split(".")
    current: JsonObject = mapping
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            raise PipelineResolutionError(f"cannot set nested override through {part!r}: {path}")
        current = child
    current[parts[-1]] = _json_value(value)


def _override_origin(path: str, selected_path: Path, sources: JsonObject) -> str:
    parts = path.split(".")
    if len(parts) > 1 and parts[0] == "components" and parts[1] in sources:
        return str(sources[parts[1]]["source_path"])
    return _portable_path(selected_path)


def _resolve_component_reference(selected_path: Path, reference: str) -> Path:
    reference_path = Path(reference)
    candidates = (
        (reference_path,)
        if reference_path.is_absolute()
        else (selected_path.parent / reference_path, _tool_root() / reference_path)
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise PipelineResolutionError(
        f"component reference cannot be resolved from selected config: {reference}"
    )


def _yaml_mapping(path: Path) -> Mapping[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, Mapping):
        raise PipelineResolutionError(f"expected YAML mapping in {path}")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    for root in (_tool_root(), _tool_root().parents[1]):
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    return resolved.as_posix()


def _json_value(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return str(value)


def _tool_root() -> Path:
    return Path(__file__).resolve().parents[2]
