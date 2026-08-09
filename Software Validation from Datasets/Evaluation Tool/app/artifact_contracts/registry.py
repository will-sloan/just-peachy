"""Runtime access to released, versioned campaign artifact contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping

import yaml


ARTIFACT_REGISTRY_VERSION = "artifact-registry.v1"
LATEST_ARTIFACT_REGISTRY_VERSION = "artifact-registry.v2"
SUPPORTED_ARTIFACT_REGISTRY_VERSIONS = frozenset(
    {ARTIFACT_REGISTRY_VERSION, LATEST_ARTIFACT_REGISTRY_VERSION}
)
CHECKSUMS_SCHEMA_VERSION = "checksums.v1"
SCENARIO_TYPES = frozenset(
    {
        "asr",
        "vad_only",
        "embedding_extraction",
        "speaker_verification",
        "diarization",
        "synthetic_executor",
    }
)
SCENARIO_CAPABILITIES = frozenset({"word_timestamps", "telemetry"})


class ArtifactRegistryError(ValueError):
    """Raised when an artifact registry or requested artifact is invalid."""


@dataclass(frozen=True)
class ArtifactDefinition:
    """One immutable artifact definition from a released registry."""

    artifact_id: str
    scope: str
    path: str
    producer: str
    format: str
    schema_version: str
    status: str
    condition: str
    validation_rules: tuple[str, ...]
    checksum_policy: str
    privacy_classification: str
    downstream_consumers: tuple[str, ...]
    registry_version: str

    @property
    def is_pattern(self) -> bool:
        return "*" in self.path

    def matches(self, relative_path: str) -> bool:
        normalized = normalize_artifact_path(relative_path)
        return PurePosixPath(normalized).match(self.path)


@dataclass(frozen=True)
class ScenarioProfile:
    """Required artifact IDs for one scenario type."""

    scenario_type: str
    required_artifacts: tuple[str, ...]


@dataclass(frozen=True)
class ArtifactRegistry:
    """Validated runtime artifact registry."""

    schema_version: str
    checksum_manifest_schema_version: str
    hash_algorithm: str
    temporary_file_marker: str
    allowed_formats: frozenset[str]
    privacy_classes: frozenset[str]
    artifacts: tuple[ArtifactDefinition, ...]
    scenario_profiles: Mapping[str, ScenarioProfile]
    source_path: Path

    @classmethod
    def load(cls, path: Path | str | None = None) -> "ArtifactRegistry":
        tool_root = Path(__file__).resolve().parents[2]
        source = (
            Path(path).resolve()
            if path is not None
            else tool_root
            / "configs"
            / "automated_evaluation"
            / "artifact_registry.v1.yaml"
        )
        raw = _load_registry_mapping(source)
        if not isinstance(raw, Mapping):
            raise ArtifactRegistryError("artifact registry must be a YAML mapping")
        registry_version = str(raw.get("schema_version") or "")
        if registry_version not in SUPPORTED_ARTIFACT_REGISTRY_VERSIONS:
            raise ArtifactRegistryError("unsupported artifact registry version")
        allowed_formats = _string_set(raw, "allowed_formats")
        privacy_classes = _string_set(raw, "privacy_classes")
        raw_artifacts = raw.get("artifacts")
        if not isinstance(raw_artifacts, list):
            raise ArtifactRegistryError("artifact registry artifacts must be a list")
        artifacts = tuple(
            _artifact_definition(
                item,
                allowed_formats,
                privacy_classes,
                registry_version=registry_version,
            )
            for item in raw_artifacts
        )
        ids = [item.artifact_id for item in artifacts]
        if len(ids) != len(set(ids)):
            raise ArtifactRegistryError("artifact IDs must be unique")
        paths = [(item.scope, item.path) for item in artifacts]
        if len(paths) != len(set(paths)):
            raise ArtifactRegistryError("artifact scope/path pairs must be unique")
        raw_profiles = raw.get("scenario_profiles")
        if not isinstance(raw_profiles, Mapping):
            raise ArtifactRegistryError("scenario_profiles must be a mapping")
        profiles: dict[str, ScenarioProfile] = {}
        known_ids = set(ids)
        for scenario_type, value in raw_profiles.items():
            if scenario_type not in SCENARIO_TYPES or not isinstance(value, Mapping):
                raise ArtifactRegistryError(f"invalid scenario profile {scenario_type!r}")
            required = _string_tuple(value, "required_artifacts")
            unknown = set(required) - known_ids
            if unknown:
                raise ArtifactRegistryError(
                    f"scenario profile {scenario_type} references unknown artifacts: "
                    f"{sorted(unknown)}"
                )
            profiles[str(scenario_type)] = ScenarioProfile(
                scenario_type=str(scenario_type),
                required_artifacts=required,
            )
        if set(profiles) != SCENARIO_TYPES:
            raise ArtifactRegistryError("every released scenario type requires a profile")
        registry = cls(
            schema_version=registry_version,
            checksum_manifest_schema_version=_required_text(
                raw, "checksum_manifest_schema_version"
            ),
            hash_algorithm=_required_text(raw, "hash_algorithm"),
            temporary_file_marker=_required_text(raw, "temporary_file_marker"),
            allowed_formats=allowed_formats,
            privacy_classes=privacy_classes,
            artifacts=artifacts,
            scenario_profiles=profiles,
            source_path=source,
        )
        if registry.checksum_manifest_schema_version != CHECKSUMS_SCHEMA_VERSION:
            raise ArtifactRegistryError("unsupported checksum manifest schema version")
        if registry.hash_algorithm != "sha256":
            raise ArtifactRegistryError("released artifact registries require SHA-256")
        for profile in registry.scenario_profiles.values():
            for artifact_id in profile.required_artifacts:
                if registry.get(artifact_id).scope != "scenario":
                    raise ArtifactRegistryError(
                        f"scenario profile references campaign artifact {artifact_id}"
                    )
        return registry

    @classmethod
    def load_version(cls, version: str) -> "ArtifactRegistry":
        """Load a released registry by public version identifier."""

        if version not in SUPPORTED_ARTIFACT_REGISTRY_VERSIONS:
            raise ArtifactRegistryError(f"unsupported artifact registry version {version!r}")
        tool_root = Path(__file__).resolve().parents[2]
        suffix = version.rsplit(".", 1)[-1]
        return cls.load(
            tool_root
            / "configs"
            / "automated_evaluation"
            / f"artifact_registry.{suffix}.yaml"
        )

    def get(self, artifact_id: str) -> ArtifactDefinition:
        for definition in self.artifacts:
            if definition.artifact_id == artifact_id:
                return definition
        raise ArtifactRegistryError(f"unknown artifact ID {artifact_id!r}")

    def match(self, scope: str, relative_path: str) -> ArtifactDefinition:
        normalized = normalize_artifact_path(relative_path)
        matches = [
            definition
            for definition in self.artifacts
            if definition.scope == scope and definition.matches(normalized)
        ]
        if not matches:
            raise ArtifactRegistryError(
                f"unregistered {scope} artifact path {normalized!r}"
            )
        if len(matches) > 1:
            raise ArtifactRegistryError(
                f"ambiguous {scope} artifact path {normalized!r}: "
                f"{[item.artifact_id for item in matches]}"
            )
        return matches[0]

    def definitions_for_scope(self, scope: str) -> tuple[ArtifactDefinition, ...]:
        if scope not in {"campaign", "scenario"}:
            raise ArtifactRegistryError(f"invalid artifact scope {scope!r}")
        return tuple(item for item in self.artifacts if item.scope == scope)

    def required_artifact_ids(self, resolved_scenario: Mapping[str, object]) -> tuple[str, ...]:
        scenario_type = scenario_type_from_resolved(resolved_scenario)
        required = set(self.scenario_profiles[scenario_type].required_artifacts)
        active = active_component_families(resolved_scenario)
        capabilities = scenario_capabilities(resolved_scenario)
        if "asr" in active and scenario_type != "synthetic_executor":
            required.add("utterance_predictions")
        if "vad" in active and scenario_type == "vad_only":
            required.add("vad_regions")
        if "speaker_embedding" in active:
            required.update({"embedding_index", "embedding_npz"})
        if "speaker_matching" in active:
            required.add("similarity_scores")
        if "diarization" in active:
            required.update({"segments_rttm", "diarization_diagnostics"})
        if "word_timestamps" in capabilities:
            required.add("words")
        if "telemetry" in capabilities:
            required.add("resource_usage")
            if self.schema_version == LATEST_ARTIFACT_REGISTRY_VERSION:
                required.update(
                    {"component_spans", "resource_summary", "resource_availability"}
                )
        return tuple(sorted(required))


def scenario_type_from_resolved(resolved_scenario: Mapping[str, object]) -> str:
    """Return the explicit or deterministically inferred scenario type."""

    contract = resolved_scenario.get("artifact_contract")
    if isinstance(contract, Mapping) and contract.get("scenario_type") is not None:
        value = str(contract["scenario_type"])
        if value not in SCENARIO_TYPES:
            raise ArtifactRegistryError(f"unsupported scenario type {value!r}")
        return value
    active = active_component_families(resolved_scenario)
    if "speaker_matching" in active:
        return "speaker_verification"
    if "diarization" in active:
        return "diarization"
    if "speaker_embedding" in active:
        return "embedding_extraction"
    if "asr" in active:
        return "asr"
    if "vad" in active:
        return "vad_only"
    raise ArtifactRegistryError(
        "scenario type cannot be inferred; synthetic scenarios require "
        "artifact_contract.scenario_type=synthetic_executor"
    )


def active_component_families(
    resolved_scenario: Mapping[str, object],
) -> frozenset[str]:
    pipeline = resolved_scenario.get("pipeline")
    components = pipeline.get("components") if isinstance(pipeline, Mapping) else None
    if not isinstance(components, Mapping):
        return frozenset()
    return frozenset(
        str(family)
        for family, raw in components.items()
        if isinstance(raw, Mapping) and raw.get("enabled") is True
    )


def scenario_capabilities(resolved_scenario: Mapping[str, object]) -> frozenset[str]:
    contract = resolved_scenario.get("artifact_contract")
    values = contract.get("capabilities") if isinstance(contract, Mapping) else None
    if values is None:
        return frozenset()
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ArtifactRegistryError("artifact_contract.capabilities must be a string list")
    capabilities = frozenset(values)
    unknown = capabilities - SCENARIO_CAPABILITIES
    if unknown:
        raise ArtifactRegistryError(f"unsupported artifact capabilities: {sorted(unknown)}")
    return capabilities


def normalize_artifact_path(value: str | Path) -> str:
    """Normalize and validate one scope-relative artifact path."""

    text = str(value).strip().replace("\\", "/")
    windows = PureWindowsPath(text)
    if not text or windows.drive or windows.root or text.startswith("/"):
        raise ArtifactRegistryError(f"artifact path must be relative: {value!r}")
    path = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ArtifactRegistryError(f"unsafe artifact path: {value!r}")
    return path.as_posix()


def _artifact_definition(
    raw: object,
    allowed_formats: frozenset[str],
    privacy_classes: frozenset[str],
    *,
    registry_version: str,
) -> ArtifactDefinition:
    if not isinstance(raw, Mapping):
        raise ArtifactRegistryError("each artifact definition must be a mapping")
    definition = ArtifactDefinition(
        artifact_id=_required_text(raw, "id"),
        scope=_required_text(raw, "scope"),
        path=normalize_artifact_path(_required_text(raw, "path")),
        producer=_required_text(raw, "producer"),
        format=_required_text(raw, "format"),
        schema_version=_required_text(raw, "schema_version"),
        status=_required_text(raw, "status"),
        condition=_required_text(raw, "condition"),
        validation_rules=_string_tuple(raw, "validation_rules"),
        checksum_policy=_required_text(raw, "checksum_policy"),
        privacy_classification=_required_text(raw, "privacy_classification"),
        downstream_consumers=_string_tuple(raw, "downstream_consumers"),
        registry_version=registry_version,
    )
    if definition.scope not in {"campaign", "scenario"}:
        raise ArtifactRegistryError(f"invalid scope for {definition.artifact_id}")
    if definition.format not in allowed_formats:
        raise ArtifactRegistryError(f"invalid format for {definition.artifact_id}")
    if definition.status not in {"mandatory", "conditional"}:
        raise ArtifactRegistryError(f"invalid status for {definition.artifact_id}")
    if definition.checksum_policy not in {"sha256", "detached_sha256", "self_excluded"}:
        raise ArtifactRegistryError(
            f"invalid checksum policy for {definition.artifact_id}"
        )
    if definition.privacy_classification not in privacy_classes:
        raise ArtifactRegistryError(
            f"invalid privacy classification for {definition.artifact_id}"
        )
    return definition


def registry_for_scenario(scenario_root: Path) -> ArtifactRegistry:
    """Select the declared registry for an existing scenario, defaulting to v1."""

    root = scenario_root.resolve()
    for relative in ("checksums.json", "status.json", "run_config.yaml"):
        path = root / relative
        if not path.is_file():
            continue
        try:
            if path.suffix == ".yaml":
                value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            else:
                import json

                value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, yaml.YAMLError):
            continue
        if isinstance(value, Mapping):
            version = value.get("artifact_registry_version")
            if isinstance(version, str) and version in SUPPORTED_ARTIFACT_REGISTRY_VERSIONS:
                return ArtifactRegistry.load_version(version)
    return ArtifactRegistry.load()


def registry_for_campaign(campaign_root: Path) -> ArtifactRegistry:
    """Select the registry declared by a campaign manifest, defaulting to v1."""

    path = campaign_root.resolve() / "campaign_manifest.json"
    if path.is_file():
        try:
            import json

            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            value = None
        if isinstance(value, Mapping):
            version = value.get("artifact_registry_version")
            if isinstance(version, str) and version in SUPPORTED_ARTIFACT_REGISTRY_VERSIONS:
                return ArtifactRegistry.load_version(version)
    return ArtifactRegistry.load()


def _load_registry_mapping(source: Path, seen: frozenset[Path] = frozenset()) -> Mapping[str, object]:
    resolved = source.resolve()
    if resolved in seen:
        raise ArtifactRegistryError("artifact registry inheritance cycle")
    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ArtifactRegistryError(f"cannot read artifact registry {resolved}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ArtifactRegistryError("artifact registry must be a YAML mapping")
    extends = raw.get("extends")
    if extends is None:
        return dict(raw)
    if not isinstance(extends, str) or not extends.strip():
        raise ArtifactRegistryError("artifact registry extends must be a relative path")
    base_path = (resolved.parent / extends).resolve()
    try:
        base_path.relative_to(resolved.parent.resolve())
    except ValueError as exc:
        raise ArtifactRegistryError("artifact registry extends escapes its config directory") from exc
    base = dict(_load_registry_mapping(base_path, seen | {resolved}))
    merged = dict(base)
    for key, value in raw.items():
        if key not in {"extends", "artifact_overrides", "append_artifacts"}:
            merged[key] = value

    artifacts = [dict(item) for item in base.get("artifacts", []) if isinstance(item, Mapping)]
    overrides = raw.get("artifact_overrides") or {}
    if not isinstance(overrides, Mapping):
        raise ArtifactRegistryError("artifact_overrides must be a mapping")
    by_id = {str(item.get("id")): index for index, item in enumerate(artifacts)}
    for artifact_id, changes in overrides.items():
        if str(artifact_id) not in by_id or not isinstance(changes, Mapping):
            raise ArtifactRegistryError(f"invalid artifact override {artifact_id!r}")
        index = by_id[str(artifact_id)]
        artifacts[index].update(dict(changes))
    appended = raw.get("append_artifacts") or []
    if not isinstance(appended, list) or any(not isinstance(item, Mapping) for item in appended):
        raise ArtifactRegistryError("append_artifacts must be a mapping list")
    artifacts.extend(dict(item) for item in appended)
    merged["artifacts"] = artifacts
    return merged


def _required_text(value: Mapping[str, object], field: str) -> str:
    raw = value.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise ArtifactRegistryError(f"missing required registry field {field}")
    return raw.strip()


def _string_tuple(value: Mapping[str, object], field: str) -> tuple[str, ...]:
    raw = value.get(field)
    if not isinstance(raw, list) or not raw or any(not isinstance(item, str) for item in raw):
        raise ArtifactRegistryError(f"registry field {field} must be a non-empty string list")
    return tuple(item.strip() for item in raw)


def _string_set(value: Mapping[str, object], field: str) -> frozenset[str]:
    return frozenset(_string_tuple(value, field))
