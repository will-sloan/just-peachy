"""Runtime view of the Stage 0 component registry and active YAML fragments."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Mapping

import yaml

from app.inference_pipeline.config import COMPONENT_SLOTS, ConfigValidationError
from app.inference_pipeline.registry import REGISTERED_COMPONENTS
from app.inference_pipeline.typing import JsonObject


CATALOG_SCHEMA_VERSION = "component-catalog.v1"


class ComponentCatalogError(ConfigValidationError):
    """Raised when the Stage 0 registry and executable component catalog diverge."""


@dataclass(frozen=True)
class ComponentCatalogEntry:
    """One executable component plus its configuration and readiness provenance."""

    family: str
    name: str
    implementation_class: str
    implementation_path: str
    registry_adapter_class: str | None
    source_config_path: str | None
    source_config_sha256: str | None
    required_packages: tuple[str, ...]
    required_assets: tuple[str, ...]
    credential_requirements: tuple[str, ...]
    environment_profiles: tuple[str, ...]
    supported_operating_systems: tuple[str, ...]
    hardware_requirements: JsonObject
    device_dtype_settings: tuple[str, ...]
    input_contract: str
    output_contract: str
    compatibility_rules: tuple[str, ...]
    supported_parameters: tuple[str, ...]
    qualification_status: str
    qualification_evidence: str
    qualification_backend_id: str | None
    final_use_category: str
    model_identity: JsonObject
    model_asset_identity: tuple[JsonObject, ...]
    configured_component: JsonObject | None

    def to_jsonable(self) -> JsonObject:
        """Return a stable machine-readable catalog row."""

        return {
            "family": self.family,
            "name": self.name,
            "implementation_class": self.implementation_class,
            "implementation_path": self.implementation_path,
            "registry_adapter_class": self.registry_adapter_class,
            "source_config_path": self.source_config_path,
            "source_config_sha256": self.source_config_sha256,
            "required_packages": list(self.required_packages),
            "required_assets": list(self.required_assets),
            "credential_requirements": list(self.credential_requirements),
            "environment_profiles": list(self.environment_profiles),
            "supported_operating_systems": list(self.supported_operating_systems),
            "hardware_requirements": dict(self.hardware_requirements),
            "device_dtype_settings": list(self.device_dtype_settings),
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "compatibility_rules": list(self.compatibility_rules),
            "supported_parameters": list(self.supported_parameters),
            "qualification_status": self.qualification_status,
            "qualification_evidence": self.qualification_evidence,
            "qualification_backend_id": self.qualification_backend_id,
            "final_use_category": self.final_use_category,
            "model_identity": dict(self.model_identity),
            "model_asset_identity": [dict(item) for item in self.model_asset_identity],
            "configured_component": (
                dict(self.configured_component)
                if self.configured_component is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ComponentCatalog:
    """Runtime-readable component inventory derived from existing sources."""

    registry_path: Path
    registry_sha256: str
    registry_version: str
    entries: tuple[ComponentCatalogEntry, ...]

    @classmethod
    def load(cls, registry_path: Path | str | None = None) -> "ComponentCatalog":
        """Load and integrity-check the default Stage 0 registry."""

        tool_root = _tool_root()
        path = (
            Path(registry_path).resolve()
            if registry_path is not None
            else tool_root / "configs" / "automated_evaluation" / "component_registry.v1.yaml"
        )
        data = _yaml_mapping(path)
        if data.get("schema_version") != "component-registry.v1":
            raise ComponentCatalogError(
                f"unsupported component registry schema: {data.get('schema_version')!r}"
            )
        raw_components = data.get("components")
        if not isinstance(raw_components, list):
            raise ComponentCatalogError("component registry 'components' must be a list")

        entries: list[ComponentCatalogEntry] = []
        for raw in raw_components:
            if not isinstance(raw, Mapping):
                raise ComponentCatalogError("component registry entry must be a mapping")
            family = str(raw.get("family") or "")
            if family not in COMPONENT_SLOTS:
                continue
            entries.append(_catalog_entry(raw, tool_root=tool_root))

        catalog_keys = {(entry.family, entry.name) for entry in entries}
        runtime_keys = {
            (family, name)
            for family, components in REGISTERED_COMPONENTS.items()
            for name in components
        }
        if catalog_keys != runtime_keys:
            missing = sorted(runtime_keys - catalog_keys)
            extra = sorted(catalog_keys - runtime_keys)
            raise ComponentCatalogError(
                f"catalog/runtime registry mismatch; missing={missing}, extra={extra}"
            )
        if len(catalog_keys) != len(entries):
            raise ComponentCatalogError("component catalog contains duplicate family/name entries")

        return cls(
            registry_path=path,
            registry_sha256=_sha256(path),
            registry_version=str(data.get("registry_version") or ""),
            entries=tuple(sorted(entries, key=lambda entry: (entry.family, entry.name))),
        )

    def get(self, family: str, name: str) -> ComponentCatalogEntry:
        """Return one executable component or fail with known names."""

        for entry in self.entries:
            if entry.family == family and entry.name == name:
                return entry
        known = sorted(entry.name for entry in self.entries if entry.family == family)
        raise ComponentCatalogError(
            f"unknown component {family}.{name}; known {family} components: {known}"
        )

    def by_family(self, family: str) -> tuple[ComponentCatalogEntry, ...]:
        """Return all entries for one component family."""

        if family not in COMPONENT_SLOTS:
            raise ComponentCatalogError(f"unknown component family {family!r}")
        return tuple(entry for entry in self.entries if entry.family == family)

    def to_jsonable(self) -> JsonObject:
        """Return catalog metadata and all runtime component rows."""

        return {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "source_registry": {
                "path": _relative_to_tool(self.registry_path),
                "sha256": self.registry_sha256,
                "registry_version": self.registry_version,
            },
            "components": [entry.to_jsonable() for entry in self.entries],
        }


def _catalog_entry(
    raw: Mapping[str, object],
    *,
    tool_root: Path,
) -> ComponentCatalogEntry:
    family = str(raw.get("family") or "")
    name = str(raw.get("name") or "")
    source_config_path = _optional_text(raw.get("config_path"))
    source_config_sha256 = _optional_text(raw.get("config_sha256"))
    configured_component: JsonObject | None = None
    params: Mapping[str, object] = {}
    if source_config_path is not None:
        path = tool_root / source_config_path
        if not path.is_file():
            raise ComponentCatalogError(f"component source config is missing: {source_config_path}")
        actual_hash = _sha256(path)
        if source_config_sha256 is None or actual_hash != source_config_sha256.upper():
            raise ComponentCatalogError(
                f"component source hash mismatch for {family}.{name}: "
                f"registry={source_config_sha256}, actual={actual_hash}"
            )
        config_data = _yaml_mapping(path)
        component = config_data.get("component", config_data)
        if not isinstance(component, Mapping):
            raise ComponentCatalogError(f"component config is not a mapping: {source_config_path}")
        if str(component.get("slot") or "") != family or str(component.get("name") or "") != name:
            raise ComponentCatalogError(
                f"component config identity mismatch for {family}.{name}: {source_config_path}"
            )
        configured_component = _json_mapping(component)
        component_params = component.get("params")
        params = component_params if isinstance(component_params, Mapping) else {}
    elif source_config_sha256 is not None:
        raise ComponentCatalogError(
            f"component {family}.{name} has a hash without a source config path"
        )

    readiness = raw.get("readiness")
    if not isinstance(readiness, Mapping):
        raise ComponentCatalogError(f"component {family}.{name} has no readiness mapping")
    assets = _string_tuple(raw.get("model_assets"))
    return ComponentCatalogEntry(
        family=family,
        name=name,
        implementation_class=str(raw.get("implementation_class") or ""),
        implementation_path=str(raw.get("implementation_path") or ""),
        registry_adapter_class=_optional_text(raw.get("registry_adapter_class")),
        source_config_path=source_config_path,
        source_config_sha256=source_config_sha256.upper() if source_config_sha256 else None,
        required_packages=_string_tuple(raw.get("packages")),
        required_assets=assets,
        credential_requirements=_string_tuple(raw.get("credential_requirements")),
        environment_profiles=_string_tuple(raw.get("environment_profiles"))
        or ("core-cpu",),
        supported_operating_systems=_string_tuple(raw.get("supported_os")),
        hardware_requirements=_json_mapping(raw.get("hardware_support")),
        device_dtype_settings=_string_tuple(raw.get("device_dtype_support")),
        input_contract=str(raw.get("input_contract") or ""),
        output_contract=str(raw.get("output_contract") or ""),
        compatibility_rules=_string_tuple(raw.get("compatibility_constraints")),
        supported_parameters=_string_tuple(raw.get("supported_parameters"))
        or tuple(sorted(str(key) for key in params)),
        qualification_status=str(readiness.get("status") or ""),
        qualification_evidence=str(readiness.get("evidence") or ""),
        qualification_backend_id=_optional_text(raw.get("qualification_backend_id")),
        final_use_category=str(raw.get("intended_final_use_category") or ""),
        model_identity=_model_identity(name, params),
        model_asset_identity=tuple(
            _asset_identity(asset, repository_root=tool_root.parents[1]) for asset in assets
        ),
        configured_component=configured_component,
    )


def _model_identity(name: str, params: Mapping[str, object]) -> JsonObject:
    keys = (
        "model_family",
        "model_name",
        "model_size",
        "model_source",
        "model_type",
        "architecture",
        "model_path",
        "cache_dir",
        "language",
    )
    identity = {key: _json_value(params[key]) for key in keys if params.get(key) is not None}
    if not identity:
        identity["component_name"] = name
    return identity


def _asset_identity(asset: str, *, repository_root: Path) -> JsonObject:
    if asset.startswith("stage8:"):
        return _stage8_asset_identity(asset.split(":", 1)[1], repository_root)
    parts = asset.split("|")
    configured_path = parts[0]
    identity: JsonObject = {"configured_identity": asset, "path": configured_path}
    for part in parts[1:]:
        if part.isdigit():
            identity["expected_bytes"] = int(part)
        elif part.lower().startswith("sha256:"):
            identity["expected_sha256"] = part.split(":", 1)[1].upper()

    if (
        configured_path.startswith("models/")
        and "..." not in configured_path
        and "{" not in configured_path
    ):
        path = repository_root / configured_path
        identity["present"] = path.exists()
        if path.is_file():
            identity["observed_bytes"] = path.stat().st_size
            if identity.get("expected_sha256") is not None:
                identity["observed_sha256"] = _sha256(path)
                identity["hash_matches"] = (
                    identity["observed_sha256"] == identity["expected_sha256"]
                )
        elif path.is_dir():
            identity["asset_type"] = "directory"
    else:
        identity["present"] = None
    return identity


def _stage8_asset_identity(asset_id: str, repository_root: Path) -> JsonObject:
    inventory_path = (
        repository_root
        / "Software Validation from Datasets"
        / "Evaluation Tool"
        / "runs"
        / "extended_backend_qualification"
        / "model_asset_inventory.json"
    )
    identity: JsonObject = {
        "configured_identity": f"stage8:{asset_id}",
        "asset_id": asset_id,
        "inventory_path": (
            "runs/extended_backend_qualification/model_asset_inventory.json"
        ),
        "present": False,
    }
    if not inventory_path.is_file():
        return identity
    import json

    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    assets = payload.get("assets") if isinstance(payload, Mapping) else None
    if not isinstance(assets, list):
        return identity
    row = next(
        (
            item
            for item in assets
            if isinstance(item, Mapping) and str(item.get("asset_id")) == asset_id
        ),
        None,
    )
    if row is None:
        return identity
    observed_sha = row.get("sha256")
    identity.update(
        {
            "path": row.get("storage_path"),
            "present": bool(row.get("present")),
            "observed_bytes": row.get("size_bytes"),
            "observed_sha256": (
                str(observed_sha).upper() if observed_sha is not None else None
            ),
            "verification_status": row.get("verification_status"),
        }
    )
    return identity


def _yaml_mapping(path: Path) -> Mapping[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, Mapping):
        raise ComponentCatalogError(f"expected YAML mapping in {path}")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise ComponentCatalogError(f"expected a list, got {type(value).__name__}")
    return tuple(str(item) for item in value)


def _json_mapping(value: object) -> JsonObject:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ComponentCatalogError(f"expected a mapping, got {type(value).__name__}")
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return str(value)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _relative_to_tool(path: Path) -> str:
    try:
        return path.resolve().relative_to(_tool_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _tool_root() -> Path:
    return Path(__file__).resolve().parents[2]
