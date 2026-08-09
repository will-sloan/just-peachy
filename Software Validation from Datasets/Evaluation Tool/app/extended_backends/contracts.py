"""Versioned Stage 8 contracts and validation helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


QUALIFICATION_STATUSES = frozenset(
    {
        "qualified",
        "qualified_with_warnings",
        "unavailable_package",
        "unavailable_asset",
        "credential_required",
        "licence_action_required",
        "platform_required",
        "cuda_required",
        "configuration_error",
        "runtime_failure",
        "contract_failure",
        "unsuitable",
        "deferred",
    }
)

REQUIRED_PROFILE_FIELDS = frozenset(
    {
        "purpose",
        "operating_systems",
        "python_version",
        "requirements",
        "installation_command",
        "validation_command",
        "supported_components",
        "incompatible_components",
        "model_assets",
        "credential_requirements",
        "hardware",
        "expected_verifier_output",
    }
)

REQUIRED_ASSET_FIELDS = frozenset(
    {
        "component",
        "backend",
        "model_name",
        "model_version",
        "source",
        "licence",
        "artifact_filename",
        "expected_sha256",
        "acquisition_method",
        "storage_path",
        "environment_profile",
        "credential_requirement",
        "required_files",
    }
)


def validate_environment_profiles(payload: Mapping[str, object]) -> None:
    """Validate required profile fields without adding a runtime JSON dependency."""

    if payload.get("schema_version") != "extended-environment-profiles.v1":
        raise ValueError("environment profile schema_version must be v1")
    profiles = payload.get("profiles")
    if not isinstance(profiles, Mapping) or not profiles:
        raise ValueError("environment profiles must be a non-empty mapping")
    for profile_id, value in profiles.items():
        if not isinstance(value, Mapping):
            raise ValueError(f"profile {profile_id!r} must be a mapping")
        missing = REQUIRED_PROFILE_FIELDS - set(value)
        if missing:
            raise ValueError(
                f"profile {profile_id!r} is missing: {', '.join(sorted(missing))}"
            )
        if not isinstance(value.get("operating_systems"), Sequence):
            raise ValueError(f"profile {profile_id!r} operating_systems must be a list")


def validate_model_asset_registry(payload: Mapping[str, object]) -> None:
    """Validate the source model-asset registry."""

    if payload.get("schema_version") != "model-asset-registry.v1":
        raise ValueError("model asset registry schema_version must be v1")
    if payload.get("hash_algorithm") != "sha256":
        raise ValueError("model asset registry hash_algorithm must be sha256")
    assets = payload.get("assets")
    if not isinstance(assets, Mapping) or not assets:
        raise ValueError("model asset registry assets must be non-empty")
    for asset_id, value in assets.items():
        if not isinstance(value, Mapping):
            raise ValueError(f"asset {asset_id!r} must be a mapping")
        missing = REQUIRED_ASSET_FIELDS - set(value)
        if missing:
            raise ValueError(
                f"asset {asset_id!r} is missing: {', '.join(sorted(missing))}"
            )
        expected = value.get("expected_sha256")
        if expected is not None and (
            len(str(expected)) != 64
            or any(character not in "0123456789abcdef" for character in str(expected))
        ):
            raise ValueError(f"asset {asset_id!r} has an invalid expected SHA-256")


def validate_qualification_payload(payload: Mapping[str, object]) -> None:
    """Validate secret policy and the stable qualification result envelope."""

    if payload.get("schema_version") != "extended-backend-qualification.v1":
        raise ValueError("qualification schema_version must be v1")
    secret_audit = payload.get("secret_audit")
    if not isinstance(secret_audit, Mapping):
        raise ValueError("qualification secret_audit is required")
    if secret_audit.get("values_serialized") is not False:
        raise ValueError("qualification artifacts must never serialize credential values")
    if secret_audit.get("credential_presence_only") is not True:
        raise ValueError("qualification artifacts must record credential presence only")
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("qualification results must be a list")
    for result in results:
        if not isinstance(result, Mapping):
            raise ValueError("qualification result rows must be mappings")
        status = result.get("status")
        if status not in QUALIFICATION_STATUSES:
            raise ValueError(f"unsupported qualification status: {status!r}")
        if "credential_value" in result or "token" in result or "access_key" in result:
            raise ValueError("qualification result contains a prohibited secret field")
