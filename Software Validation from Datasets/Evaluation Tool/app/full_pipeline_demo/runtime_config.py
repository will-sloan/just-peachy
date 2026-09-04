"""Strict scientific-runtime configuration binding for the H2 demo.

The demo is allowed to run without a binding for engineering work, but that
path is explicitly non-final.  Scientific sessions load either one frozen
per-mode configuration emitted by the H2 controller or an inline multi-mode
demo binding whose entire payload has a canonical SHA-256 identity.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from app.full_pipeline.product_modes import H2ProductMode, H2RuntimeTuning

from .h2_ux import H2_DEFAULT_PRODUCT_MODE, require_h2_pipeline_id


DEMO_BINDING_SCHEMA_VERSION = "h2-demo-runtime-binding.v1"
FROZEN_MODE_SCHEMA_VERSION = "h2-frozen-product-configuration.v1"
CONFIG_STATUS_SCHEMA_VERSION = "full-pipeline-demo-scientific-config-status.v1"

_BINDING_LIFECYCLES = frozenset(
    {"DEVELOPMENT_SELECTED", "FROZEN", "FINAL_VALIDATED"}
)
_BINDING_KEYS = frozenset(
    {
        "schema_version",
        "lifecycle",
        "default_product_mode",
        "configurations",
        "binding_identity_sha256",
        "validation_identity_sha256",
        "provenance",
    }
)
_ENTRY_KEYS = frozenset(
    {
        "pipeline_id",
        "mode",
        "runtime_tuning",
        "runtime_tuning_identity_sha256",
        "configuration_id",
        "freeze_identity_sha256",
        "source_result_sha256",
    }
)
_FROZEN_KEYS = frozenset(
    {
        "schema_version",
        "mode",
        "pipeline_id",
        "freeze_identity_sha256",
        "runtime_tuning",
        "runtime_tuning_identity_sha256",
    }
)


class DemoRuntimeConfigError(ValueError):
    """The selected demo runtime configuration is invalid or stale."""


@dataclass(frozen=True)
class DemoRuntimeSelection:
    """One exact pipeline/mode tuning plus its user-visible claim boundary."""

    pipeline_id: str
    product_mode: str | None
    runtime_tuning: H2RuntimeTuning | None
    status: str
    source_path: Path | None
    source_file_sha256: str | None
    expected_file_sha256: str | None
    source_schema_version: str | None
    binding_identity_sha256: str | None
    lifecycle: str | None
    final_scientific_validation: bool

    @property
    def runtime_tuning_identity_sha256(self) -> str | None:
        return (
            self.runtime_tuning.identity_sha256
            if self.runtime_tuning is not None
            else None
        )

    def runtime_tuning_payload(self) -> dict[str, object] | None:
        """Return the complete tuning with its identity rechecked by the factory."""

        if self.runtime_tuning is None:
            return None
        return {
            **self.runtime_tuning.to_jsonable(),
            "identity_sha256": self.runtime_tuning.identity_sha256,
        }

    def status_payload(self) -> dict[str, object]:
        return {
            "schema_version": CONFIG_STATUS_SCHEMA_VERSION,
            "status": self.status,
            "pipeline_id": self.pipeline_id,
            "product_mode": self.product_mode,
            "source_path": str(self.source_path) if self.source_path else None,
            "source_file_sha256": self.source_file_sha256,
            "expected_file_sha256": self.expected_file_sha256,
            "source_schema_version": self.source_schema_version,
            "binding_identity_sha256": self.binding_identity_sha256,
            "lifecycle": self.lifecycle,
            "runtime_tuning_identity_sha256": (
                self.runtime_tuning_identity_sha256
            ),
            "final_scientific_validation": self.final_scientific_validation,
            "engineering_baseline": self.status
            == "ENGINEERING_BASELINE_NOT_FINAL",
        }


@dataclass(frozen=True)
class _BoundEntry:
    pipeline_id: str
    mode: str
    runtime_tuning: H2RuntimeTuning


@dataclass(frozen=True)
class H2DemoRuntimeBinding:
    """A verified file identity and all exact pipeline/mode entries it binds."""

    source_path: Path
    source_file_sha256: str
    expected_file_sha256: str | None
    source_schema_version: str
    binding_identity_sha256: str
    lifecycle: str
    default_product_mode: str
    entries: Mapping[tuple[str, str], _BoundEntry]

    def select(
        self, pipeline_id: str, product_mode: str | None = None
    ) -> DemoRuntimeSelection:
        try:
            current_sha = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        except OSError as exc:
            raise DemoRuntimeConfigError(
                f"scientific runtime binding is no longer readable: {self.source_path}"
            ) from exc
        if current_sha != self.source_file_sha256:
            raise DemoRuntimeConfigError(
                "scientific runtime binding changed after it was loaded: "
                f"expected {self.source_file_sha256}, got {current_sha}"
            )
        require_h2_pipeline_id(pipeline_id)
        mode = product_mode or self.default_product_mode
        try:
            normalized_mode = H2ProductMode(mode).value
        except ValueError as exc:
            raise DemoRuntimeConfigError(f"unsupported H2 product mode: {mode}") from exc
        try:
            entry = self.entries[(pipeline_id, normalized_mode)]
        except KeyError as exc:
            available = ", ".join(
                f"{candidate_pipeline}/{candidate_mode}"
                for candidate_pipeline, candidate_mode in sorted(self.entries)
            )
            raise DemoRuntimeConfigError(
                "scientific runtime binding has no exact entry for "
                f"{pipeline_id}/{normalized_mode}; available: {available}"
            ) from exc
        status = {
            "DEVELOPMENT_SELECTED": "DEVELOPMENT_SELECTED_NOT_FINAL",
            "FROZEN": "FROZEN_SCIENTIFIC_CONFIGURATION",
            "FINAL_VALIDATED": "FINAL_VALIDATED_SCIENTIFIC_CONFIGURATION",
        }[self.lifecycle]
        return DemoRuntimeSelection(
            pipeline_id=entry.pipeline_id,
            product_mode=entry.mode,
            runtime_tuning=entry.runtime_tuning,
            status=status,
            source_path=self.source_path,
            source_file_sha256=self.source_file_sha256,
            expected_file_sha256=self.expected_file_sha256,
            source_schema_version=self.source_schema_version,
            binding_identity_sha256=self.binding_identity_sha256,
            lifecycle=self.lifecycle,
            final_scientific_validation=self.lifecycle == "FINAL_VALIDATED",
        )


def engineering_baseline_selection(
    pipeline_id: str, product_mode: str | None = None
) -> DemoRuntimeSelection:
    """Build the explicit non-final baseline used when no binding is supplied."""

    try:
        require_h2_pipeline_id(pipeline_id)
    except ValueError:
        # Retained historical matrix mechanics can still exercise a non-H2
        # runtime, but no H2 mode/tuning is invented for it.
        return DemoRuntimeSelection(
            pipeline_id=pipeline_id,
            product_mode=None,
            runtime_tuning=None,
            status="ENGINEERING_BASELINE_NOT_FINAL",
            source_path=None,
            source_file_sha256=None,
            expected_file_sha256=None,
            source_schema_version=None,
            binding_identity_sha256=None,
            lifecycle=None,
            final_scientific_validation=False,
        )
    mode = H2ProductMode(product_mode or H2_DEFAULT_PRODUCT_MODE)
    tuning = H2RuntimeTuning(product_mode=mode)
    return DemoRuntimeSelection(
        pipeline_id=pipeline_id,
        product_mode=mode.value,
        runtime_tuning=tuning,
        status="ENGINEERING_BASELINE_NOT_FINAL",
        source_path=None,
        source_file_sha256=None,
        expected_file_sha256=None,
        source_schema_version=None,
        binding_identity_sha256=None,
        lifecycle=None,
        final_scientific_validation=False,
    )


def load_h2_demo_runtime_binding(
    path: Path, *, expected_sha256: str | None = None
) -> H2DemoRuntimeBinding:
    """Load one strict JSON binding and verify all nested identities."""

    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    payload_bytes = source.read_bytes()
    if len(payload_bytes) > 5 * 1024 * 1024:
        raise DemoRuntimeConfigError("demo runtime binding exceeds 5 MiB")
    actual_sha = hashlib.sha256(payload_bytes).hexdigest()
    expected = _optional_sha256(expected_sha256, "expected file SHA-256")
    if expected is not None and actual_sha != expected:
        raise DemoRuntimeConfigError(
            "demo runtime binding file SHA-256 mismatch: "
            f"expected {expected}, got {actual_sha}"
        )
    try:
        value = json.loads(
            payload_bytes.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DemoRuntimeConfigError(
            f"demo runtime binding is not strict UTF-8 JSON: {source}"
        ) from exc
    if not isinstance(value, Mapping):
        raise DemoRuntimeConfigError("demo runtime binding must be a JSON object")
    schema = str(value.get("schema_version") or "")
    if schema == FROZEN_MODE_SCHEMA_VERSION:
        return _load_frozen_mode(
            source,
            actual_sha=actual_sha,
            expected_sha=expected,
            value=value,
        )
    if schema == DEMO_BINDING_SCHEMA_VERSION:
        return _load_multi_mode_binding(
            source,
            actual_sha=actual_sha,
            expected_sha=expected,
            value=value,
        )
    raise DemoRuntimeConfigError(f"unsupported demo runtime binding schema: {schema}")


def build_h2_demo_runtime_binding_payload(
    *,
    lifecycle: str,
    default_product_mode: str,
    configurations: Sequence[Mapping[str, object]],
    validation_identity_sha256: str | None = None,
    provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a canonical controller/app handoff payload using the loader schema."""

    unsigned: dict[str, object] = {
        "schema_version": DEMO_BINDING_SCHEMA_VERSION,
        "lifecycle": lifecycle,
        "default_product_mode": default_product_mode,
        "configurations": [dict(row) for row in configurations],
    }
    if validation_identity_sha256 is not None:
        unsigned["validation_identity_sha256"] = validation_identity_sha256
    if provenance is not None:
        unsigned["provenance"] = dict(provenance)
    return {**unsigned, "binding_identity_sha256": canonical_sha256(unsigned)}


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_frozen_mode(
    source: Path,
    *,
    actual_sha: str,
    expected_sha: str | None,
    value: Mapping[str, object],
) -> H2DemoRuntimeBinding:
    _require_exact_keys(value, _FROZEN_KEYS, "frozen per-mode configuration")
    pipeline_id = str(value.get("pipeline_id") or "")
    require_h2_pipeline_id(pipeline_id)
    mode, tuning = _validated_entry(value)
    freeze_identity = _required_sha256(
        value.get("freeze_identity_sha256"), "freeze_identity_sha256"
    )
    return H2DemoRuntimeBinding(
        source_path=source,
        source_file_sha256=actual_sha,
        expected_file_sha256=expected_sha,
        source_schema_version=FROZEN_MODE_SCHEMA_VERSION,
        binding_identity_sha256=freeze_identity,
        lifecycle="FROZEN",
        default_product_mode=mode,
        entries=MappingProxyType(
            {(pipeline_id, mode): _BoundEntry(pipeline_id, mode, tuning)}
        ),
    )


def _load_multi_mode_binding(
    source: Path,
    *,
    actual_sha: str,
    expected_sha: str | None,
    value: Mapping[str, object],
) -> H2DemoRuntimeBinding:
    _require_allowed_keys(
        value,
        _BINDING_KEYS,
        required={
            "schema_version",
            "lifecycle",
            "default_product_mode",
            "configurations",
            "binding_identity_sha256",
        },
        label="multi-mode demo binding",
    )
    lifecycle = str(value.get("lifecycle") or "")
    if lifecycle not in _BINDING_LIFECYCLES:
        raise DemoRuntimeConfigError(f"unsupported binding lifecycle: {lifecycle}")
    validation_identity = value.get("validation_identity_sha256")
    if validation_identity is not None:
        _required_sha256(validation_identity, "validation_identity_sha256")
    if lifecycle == "FINAL_VALIDATED" and validation_identity is None:
        raise DemoRuntimeConfigError(
            "FINAL_VALIDATED binding requires validation_identity_sha256"
        )
    supplied_identity = _required_sha256(
        value.get("binding_identity_sha256"), "binding_identity_sha256"
    )
    unsigned = dict(value)
    unsigned.pop("binding_identity_sha256", None)
    calculated_identity = canonical_sha256(unsigned)
    if supplied_identity != calculated_identity:
        raise DemoRuntimeConfigError("binding_identity_sha256 mismatch")
    try:
        default_mode = H2ProductMode(str(value["default_product_mode"])).value
    except ValueError as exc:
        raise DemoRuntimeConfigError("invalid default_product_mode") from exc
    rows = value.get("configurations")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise DemoRuntimeConfigError("configurations must be a non-empty array")
    entries: dict[tuple[str, str], _BoundEntry] = {}
    pipelines: set[str] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise DemoRuntimeConfigError(f"configurations[{index}] is not an object")
        _require_allowed_keys(
            raw,
            _ENTRY_KEYS,
            required={
                "pipeline_id",
                "mode",
                "runtime_tuning",
                "runtime_tuning_identity_sha256",
            },
            label=f"configurations[{index}]",
        )
        pipeline_id = str(raw.get("pipeline_id") or "")
        require_h2_pipeline_id(pipeline_id)
        mode, tuning = _validated_entry(raw)
        for key in (
            "freeze_identity_sha256",
            "source_result_sha256",
        ):
            if raw.get(key) is not None:
                _required_sha256(raw[key], key)
        key = (pipeline_id, mode)
        if key in entries:
            raise DemoRuntimeConfigError(
                f"duplicate scientific runtime entry: {pipeline_id}/{mode}"
            )
        entries[key] = _BoundEntry(pipeline_id, mode, tuning)
        pipelines.add(pipeline_id)
    missing_default = sorted(
        pipeline for pipeline in pipelines if (pipeline, default_mode) not in entries
    )
    if missing_default:
        raise DemoRuntimeConfigError(
            "default_product_mode lacks an exact entry for: "
            + ", ".join(missing_default)
        )
    return H2DemoRuntimeBinding(
        source_path=source,
        source_file_sha256=actual_sha,
        expected_file_sha256=expected_sha,
        source_schema_version=DEMO_BINDING_SCHEMA_VERSION,
        binding_identity_sha256=supplied_identity,
        lifecycle=lifecycle,
        default_product_mode=default_mode,
        entries=MappingProxyType(entries),
    )


def _validated_entry(value: Mapping[str, object]) -> tuple[str, H2RuntimeTuning]:
    raw_tuning = value.get("runtime_tuning")
    if not isinstance(raw_tuning, Mapping):
        raise DemoRuntimeConfigError("runtime_tuning must be an object")
    try:
        tuning = H2RuntimeTuning.from_mapping(raw_tuning)
    except (TypeError, ValueError) as exc:
        raise DemoRuntimeConfigError(f"invalid H2 runtime_tuning: {exc}") from exc
    try:
        mode = H2ProductMode(str(value.get("mode") or "")).value
    except ValueError as exc:
        raise DemoRuntimeConfigError("invalid configuration mode") from exc
    if tuning.product_mode.value != mode:
        raise DemoRuntimeConfigError(
            "configuration mode conflicts with runtime_tuning.product_mode"
        )
    supplied_identity = _required_sha256(
        value.get("runtime_tuning_identity_sha256"),
        "runtime_tuning_identity_sha256",
    )
    if supplied_identity != tuning.identity_sha256:
        raise DemoRuntimeConfigError("runtime_tuning_identity_sha256 mismatch")
    return mode, tuning


def _require_exact_keys(
    value: Mapping[str, object], allowed: frozenset[str], label: str
) -> None:
    _require_allowed_keys(value, allowed, required=set(allowed), label=label)


def _require_allowed_keys(
    value: Mapping[str, object],
    allowed: frozenset[str],
    *,
    required: set[str],
    label: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        raise DemoRuntimeConfigError(
            f"{label} has unsupported keys: {', '.join(unknown)}"
        )
    if missing:
        raise DemoRuntimeConfigError(
            f"{label} is missing required keys: {', '.join(missing)}"
        )


def _optional_sha256(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _required_sha256(value, label)


def _required_sha256(value: object, label: str) -> str:
    text = str(value or "").casefold()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise DemoRuntimeConfigError(f"{label} must be a 64-character SHA-256")
    return text


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise DemoRuntimeConfigError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _reject_json_constant(value: str) -> None:
    raise DemoRuntimeConfigError(f"non-finite JSON constant is forbidden: {value}")


__all__ = [
    "CONFIG_STATUS_SCHEMA_VERSION",
    "DEMO_BINDING_SCHEMA_VERSION",
    "FROZEN_MODE_SCHEMA_VERSION",
    "DemoRuntimeConfigError",
    "DemoRuntimeSelection",
    "H2DemoRuntimeBinding",
    "build_h2_demo_runtime_binding_payload",
    "canonical_sha256",
    "engineering_baseline_selection",
    "load_h2_demo_runtime_binding",
]
