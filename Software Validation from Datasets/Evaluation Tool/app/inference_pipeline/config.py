"""YAML-backed configuration contracts for the inference pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from app.inference_pipeline.errors import ContractValidationError, MissingRequiredFieldError
from app.inference_pipeline.typing import JsonObject, JsonValue


COMPONENT_SLOTS = (
    "vad",
    "segmentation",
    "asr",
    "speaker_embedding",
    "speaker_matching",
)


class ConfigValidationError(ContractValidationError):
    """Raised when an inference pipeline config is malformed."""


@dataclass(frozen=True)
class ComponentConfig:
    """Configuration for one swappable pipeline component."""

    name: str
    enabled: bool = True
    adapter: str | None = None
    params: JsonObject | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ConfigValidationError("component name must be a non-empty string")
        if self.params is None:
            object.__setattr__(self, "params", {})
        else:
            object.__setattr__(self, "params", _json_object(self.params, "params"))

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, object],
        slot: str | None = None,
    ) -> "ComponentConfig":
        """Create a component config from YAML data."""

        data = _unwrap_component_mapping(mapping)
        if slot is not None:
            declared_slot = data.get("slot")
            if declared_slot is not None and str(declared_slot) != slot:
                raise ConfigValidationError(
                    f"component file declares slot {declared_slot!r}, expected {slot!r}"
                )
        if "name" not in data:
            raise MissingRequiredFieldError("component config missing required field 'name'")
        return cls(
            name=str(data["name"]),
            enabled=_optional_bool(data.get("enabled"), default=True),
            adapter=_optional_string(data.get("adapter")),
            params=_optional_json_object(data.get("params"), "params"),
            notes=_optional_string(data.get("notes")),
        )

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation."""

        return {
            "name": self.name,
            "enabled": self.enabled,
            "adapter": self.adapter,
            "params": dict(self.params or {}),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RuntimeOptions:
    """Runtime options that apply across selected components."""

    device: str = "cpu"
    sample_rate_hz: int = 16000
    max_batch_size: int = 1
    num_threads: int = 1
    precision: str = "float32"
    dry_run: bool = True
    allow_model_downloads: bool = False
    cache_dir: str | None = None

    def __post_init__(self) -> None:
        _validate_positive_int(self.sample_rate_hz, "sample_rate_hz")
        _validate_positive_int(self.max_batch_size, "max_batch_size")
        _validate_positive_int(self.num_threads, "num_threads")
        if not self.device.strip():
            raise ConfigValidationError("runtime.device must be non-empty")
        if self.precision not in {"float32", "float16", "int8"}:
            raise ConfigValidationError("runtime.precision must be float32, float16, or int8")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object] | None) -> "RuntimeOptions":
        """Create runtime options from YAML data."""

        data = dict(mapping or {})
        return cls(
            device=str(data.get("device", "cpu")),
            sample_rate_hz=_int_value(data.get("sample_rate_hz", 16000), "sample_rate_hz"),
            max_batch_size=_int_value(data.get("max_batch_size", 1), "max_batch_size"),
            num_threads=_int_value(data.get("num_threads", 1), "num_threads"),
            precision=str(data.get("precision", "float32")),
            dry_run=_optional_bool(data.get("dry_run"), default=True),
            allow_model_downloads=_optional_bool(
                data.get("allow_model_downloads"),
                default=False,
            ),
            cache_dir=_optional_string(data.get("cache_dir")),
        )

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation."""

        return {
            "device": self.device,
            "sample_rate_hz": self.sample_rate_hz,
            "max_batch_size": self.max_batch_size,
            "num_threads": self.num_threads,
            "precision": self.precision,
            "dry_run": self.dry_run,
            "allow_model_downloads": self.allow_model_downloads,
            "cache_dir": self.cache_dir,
        }


@dataclass(frozen=True)
class PipelineConfig:
    """Complete inference pipeline configuration for one run profile."""

    config_name: str
    profile: str
    components: dict[str, ComponentConfig]
    runtime: RuntimeOptions
    notes: str | None = None
    future: bool = False

    def __post_init__(self) -> None:
        if not self.config_name.strip():
            raise ConfigValidationError("config_name must be non-empty")
        if not self.profile.strip():
            raise ConfigValidationError("profile must be non-empty")
        missing = [slot for slot in COMPONENT_SLOTS if slot not in self.components]
        if missing:
            raise MissingRequiredFieldError(
                f"pipeline config missing component slot(s): {', '.join(missing)}"
            )
        extra = [slot for slot in self.components if slot not in COMPONENT_SLOTS]
        if extra:
            raise ConfigValidationError(
                f"pipeline config contains unknown component slot(s): {', '.join(extra)}"
            )

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, object],
        *,
        config_dir: Path | None = None,
        tool_root: Path | None = None,
    ) -> "PipelineConfig":
        """Create a pipeline config from a mapping loaded from YAML."""

        if "components" not in mapping:
            raise MissingRequiredFieldError("pipeline config missing required field 'components'")
        components = _components_from_mapping(
            _mapping_value(mapping["components"], "components"),
            config_dir=config_dir,
            tool_root=tool_root,
        )
        return cls(
            config_name=str(mapping.get("config_name") or mapping.get("name") or "unnamed"),
            profile=str(mapping.get("profile") or "default"),
            components=components,
            runtime=RuntimeOptions.from_mapping(
                _optional_mapping_value(mapping.get("runtime"), "runtime")
            ),
            notes=_optional_string(mapping.get("notes")),
            future=_optional_bool(mapping.get("future"), default=False),
        )

    @classmethod
    def from_yaml_path(cls, path: Path | str) -> "PipelineConfig":
        """Load a pipeline config from a YAML file."""

        config_path = Path(path).resolve()
        data = _load_yaml_mapping(config_path)
        tool_root = Path(__file__).resolve().parents[2]
        return cls.from_mapping(
            data,
            config_dir=config_path.parent,
            tool_root=tool_root,
        )

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation."""

        return {
            "config_name": self.config_name,
            "profile": self.profile,
            "notes": self.notes,
            "future": self.future,
            "runtime": self.runtime.to_jsonable(),
            "components": {
                slot: component.to_jsonable()
                for slot, component in self.components.items()
            },
        }


def _components_from_mapping(
    mapping: Mapping[str, object],
    *,
    config_dir: Path | None,
    tool_root: Path | None,
) -> dict[str, ComponentConfig]:
    components: dict[str, ComponentConfig] = {}
    for slot in COMPONENT_SLOTS:
        if slot not in mapping:
            continue
        value = mapping[slot]
        if isinstance(value, str):
            component_mapping = _load_component_reference(
                value,
                config_dir=config_dir,
                tool_root=tool_root,
            )
            components[slot] = ComponentConfig.from_mapping(component_mapping, slot=slot)
            continue
        components[slot] = ComponentConfig.from_mapping(
            _mapping_value(value, f"components.{slot}"),
            slot=slot,
        )
    return components


def _load_component_reference(
    reference: str,
    *,
    config_dir: Path | None,
    tool_root: Path | None,
) -> Mapping[str, object]:
    candidate_paths: list[Path] = []
    reference_path = Path(reference)
    if reference_path.is_absolute():
        candidate_paths.append(reference_path)
    else:
        if config_dir is not None:
            candidate_paths.append(config_dir / reference_path)
        if tool_root is not None:
            candidate_paths.append(tool_root / reference_path)

    for candidate_path in candidate_paths:
        if candidate_path.is_file():
            return _load_yaml_mapping(candidate_path)

    searched = ", ".join(str(path) for path in candidate_paths)
    raise ConfigValidationError(f"component config reference not found: {reference} ({searched})")


def _load_yaml_mapping(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return _mapping_value(data, str(path))


def _unwrap_component_mapping(mapping: Mapping[str, object]) -> Mapping[str, object]:
    if "component" in mapping:
        return _mapping_value(mapping["component"], "component")
    return mapping


def _mapping_value(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ConfigValidationError(f"{field_name} must be a mapping")
    return value


def _optional_mapping_value(value: object, field_name: str) -> Mapping[str, object] | None:
    if value is None:
        return None
    return _mapping_value(value, field_name)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    raise ConfigValidationError(f"expected boolean value, got {value!r}")


def _int_value(value: object, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError(f"runtime.{field_name} must be an integer") from exc


def _validate_positive_int(value: int, field_name: str) -> None:
    if value < 1:
        raise ConfigValidationError(f"runtime.{field_name} must be >= 1")


def _optional_json_object(value: object, field_name: str) -> JsonObject | None:
    if value is None:
        return None
    return _json_object(value, field_name)


def _json_object(value: object, field_name: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ConfigValidationError(f"{field_name} must be a mapping")
    return {str(key): _jsonable(item) for key, item in value.items()}


def _jsonable(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value]
    return str(value)

