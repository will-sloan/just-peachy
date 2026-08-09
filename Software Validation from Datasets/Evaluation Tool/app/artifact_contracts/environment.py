"""Versioned static environment fingerprint collection for result compatibility."""

from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import importlib.metadata
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Mapping, Sequence

from app.benchmark_contracts.canonical import canonical_sha256


ENVIRONMENT_FINGERPRINT_SCHEMA_VERSION = "environment-fingerprint.v1"


class EnvironmentFingerprintError(ValueError):
    """Raised when an environment fingerprint is incomplete or inconsistent."""


def collect_environment_fingerprint(
    repository_root: Path,
    *,
    profile_identity: str,
    model_hashes: Mapping[str, object],
    component_config_hashes: Mapping[str, object],
    captured_at: datetime | None = None,
) -> dict[str, object]:
    """Collect static host/software identity without sampling runtime telemetry."""

    captured = captured_at or datetime.now(timezone.utc)
    packages = _package_freeze()
    now_local = captured.astimezone()
    payload: dict[str, object] = {
        "schema_version": ENVIRONMENT_FINGERPRINT_SCHEMA_VERSION,
        "captured_at_utc": _rfc3339_utc(captured),
        "git": _git_identity(repository_root),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python": {
            "executable": str(Path(sys.executable).resolve()),
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "packages": {
            "profile_identity": profile_identity,
            "freeze": packages,
            "freeze_sha256": canonical_sha256(packages),
        },
        "hardware": {
            "cpu": platform.processor() or platform.machine() or "unknown",
            "logical_cpu_count": os.cpu_count(),
            "ram_bytes": _total_ram_bytes(),
        },
        "accelerator": _accelerator_identity(),
        "model_hashes": _normalized_hash_mapping(model_hashes, "model_hashes"),
        "component_config_hashes": _normalized_hash_mapping(
            component_config_hashes, "component_config_hashes"
        ),
        "clock": {
            "timezone_name": now_local.tzname(),
            "utc_offset_seconds": int((now_local.utcoffset() or timezone.utc.utcoffset(now_local)).total_seconds()),
            "wall_clock": time.get_clock_info("time").implementation,
            "wall_clock_resolution_sec": time.get_clock_info("time").resolution,
            "monotonic_clock": time.get_clock_info("monotonic").implementation,
            "monotonic_resolution_sec": time.get_clock_info("monotonic").resolution,
        },
    }
    return finalize_environment_fingerprint(payload)


def identity_hashes_from_resolved_scenario(
    resolved_scenario: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Extract component-config and practical model-asset hashes for a fingerprint."""

    pipeline = resolved_scenario.get("pipeline")
    if not isinstance(pipeline, Mapping):
        raise EnvironmentFingerprintError("resolved scenario pipeline is missing")
    raw_components = pipeline.get("components")
    raw_models = pipeline.get("models")
    if not isinstance(raw_components, Mapping) or not isinstance(raw_models, Mapping):
        raise EnvironmentFingerprintError("resolved scenario component/model identities are missing")
    component_hashes: dict[str, object] = {}
    for family, raw in raw_components.items():
        if not isinstance(raw, Mapping):
            raise EnvironmentFingerprintError(f"component identity {family} is invalid")
        component_hashes[str(family)] = {
            "config_contents": raw.get("config_contents_sha256"),
            "source_config": raw.get("source_config_sha256"),
        }
    model_hashes: dict[str, object] = {}
    for family, raw in raw_models.items():
        if not isinstance(raw, Mapping):
            raise EnvironmentFingerprintError(f"model identity {family} is invalid")
        assets = raw.get("assets")
        if not isinstance(assets, list):
            raise EnvironmentFingerprintError(f"model assets {family} are invalid")
        model_hashes[str(family)] = {
            f"asset_{index:03d}": (
                asset.get("observed_sha256") or asset.get("expected_sha256")
                if isinstance(asset, Mapping)
                else None
            )
            for index, asset in enumerate(assets)
        }
    return (
        _normalized_hash_mapping(model_hashes, "model_hashes"),
        _normalized_hash_mapping(component_hashes, "component_config_hashes"),
    )


def finalize_environment_fingerprint(value: Mapping[str, object]) -> dict[str, object]:
    """Attach and validate the stable environment identity hash."""

    result = dict(value)
    result.pop("fingerprint_id", None)
    result.pop("fingerprint_sha256", None)
    digest = canonical_sha256(environment_identity_payload(result))
    result["fingerprint_sha256"] = digest
    result["fingerprint_id"] = f"environment_{digest[:12].lower()}"
    validate_environment_fingerprint(result)
    return result


def environment_identity_payload(value: Mapping[str, object]) -> dict[str, object]:
    """Return stable fingerprint fields; collection time is audit-only."""

    payload = dict(value)
    payload.pop("fingerprint_id", None)
    payload.pop("fingerprint_sha256", None)
    payload.pop("captured_at_utc", None)
    return payload


def validate_environment_fingerprint(value: Mapping[str, object]) -> None:
    required = {
        "schema_version",
        "fingerprint_id",
        "fingerprint_sha256",
        "captured_at_utc",
        "git",
        "os",
        "python",
        "packages",
        "hardware",
        "accelerator",
        "model_hashes",
        "component_config_hashes",
        "clock",
    }
    missing = required - set(value)
    if missing:
        raise EnvironmentFingerprintError(f"fingerprint missing fields: {sorted(missing)}")
    if value.get("schema_version") != ENVIRONMENT_FINGERPRINT_SCHEMA_VERSION:
        raise EnvironmentFingerprintError("unsupported environment fingerprint schema")
    digest = canonical_sha256(environment_identity_payload(value))
    if value.get("fingerprint_sha256") != digest:
        raise EnvironmentFingerprintError("environment fingerprint content hash mismatch")
    if value.get("fingerprint_id") != f"environment_{digest[:12].lower()}":
        raise EnvironmentFingerprintError("environment fingerprint ID mismatch")
    git = _required_mapping(value, "git")
    _required_mapping(value, "os")
    python = _required_mapping(value, "python")
    packages = _required_mapping(value, "packages")
    hardware = _required_mapping(value, "hardware")
    _required_mapping(value, "accelerator")
    _required_mapping(value, "clock")
    if not isinstance(git.get("dirty"), bool) or not git.get("commit"):
        raise EnvironmentFingerprintError("fingerprint Git identity is incomplete")
    if not python.get("executable") or not python.get("version"):
        raise EnvironmentFingerprintError("fingerprint Python identity is incomplete")
    logical_cpu_count = hardware.get("logical_cpu_count")
    if logical_cpu_count is not None and (
        not isinstance(logical_cpu_count, int) or logical_cpu_count <= 0
    ):
        raise EnvironmentFingerprintError("invalid logical CPU count")
    _normalized_hash_mapping(value.get("model_hashes"), "model_hashes")
    _normalized_hash_mapping(value.get("component_config_hashes"), "component_config_hashes")
    freeze = packages.get("freeze")
    if not isinstance(freeze, list) or packages.get("freeze_sha256") != canonical_sha256(
        freeze
    ):
        raise EnvironmentFingerprintError("package freeze hash mismatch")
    captured = value.get("captured_at_utc")
    if not isinstance(captured, str) or not captured.endswith("Z"):
        raise EnvironmentFingerprintError("captured_at_utc must be RFC3339 UTC")
    try:
        datetime.fromisoformat(captured[:-1] + "+00:00")
    except ValueError as exc:
        raise EnvironmentFingerprintError("captured_at_utc must be RFC3339 UTC") from exc


def _git_identity(repository_root: Path) -> dict[str, object]:
    commit = _run_text(
        ["git", "rev-parse", "HEAD"], cwd=repository_root
    )
    if not commit:
        raise EnvironmentFingerprintError("repository Git commit is unavailable")
    status = _run_text(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repository_root,
        preserve_newlines=True,
    )
    lines = [line for line in status.splitlines() if line.strip()]
    return {
        "commit": commit.strip(),
        "dirty": bool(lines),
        "changed_path_count": len(lines),
    }


def _package_freeze() -> list[dict[str, str]]:
    packages = {
        distribution.metadata.get("Name", distribution.name): distribution.version
        for distribution in importlib.metadata.distributions()
    }
    return [
        {"name": str(name), "version": str(version)}
        for name, version in sorted(packages.items(), key=lambda item: item[0].lower())
    ]


def _accelerator_identity() -> dict[str, object]:
    rows = _run_text(
        [
            "nvidia-smi",
            "--query-gpu=index,name,uuid,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ],
        preserve_newlines=True,
        allow_failure=True,
    )
    gpus: list[dict[str, object]] = []
    driver_versions: set[str] = set()
    for line in rows.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 5:
            continue
        index, name, gpu_uuid, memory_total, driver = parts[:5]
        driver_versions.add(driver)
        try:
            total_vram_mib = float(memory_total)
        except ValueError:
            total_vram_mib = None
        gpus.append(
            {
                "index": index,
                "name": name,
                "uuid": gpu_uuid,
                "total_vram_mib": total_vram_mib,
            }
        )
    return {
        "gpus": gpus,
        "driver": ",".join(sorted(driver_versions)) or None,
        "cuda_runtime": _torch_cuda_runtime(),
    }


def _torch_cuda_runtime() -> str | None:
    try:
        import torch
    except (ImportError, OSError):
        return None
    value = getattr(getattr(torch, "version", None), "cuda", None)
    return str(value) if value is not None else None


def _total_ram_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.total_physical)
        return None
    try:
        sysconf = getattr(os, "sysconf")
        page_size = sysconf("SC_PAGE_SIZE")
        page_count = sysconf("SC_PHYS_PAGES")
    except (AttributeError, OSError, ValueError):
        return None
    return int(page_size * page_count)


def _normalized_hash_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise EnvironmentFingerprintError(f"{field} must be a mapping")
    normalized: dict[str, object] = {}
    for key, raw in value.items():
        if isinstance(raw, Mapping):
            normalized[str(key)] = _normalized_hash_mapping(raw, field)
        elif raw is None:
            normalized[str(key)] = None
        else:
            digest = str(raw).upper()
            if len(digest) != 64 or any(char not in "0123456789ABCDEF" for char in digest):
                raise EnvironmentFingerprintError(f"{field}.{key} is not SHA-256")
            normalized[str(key)] = digest
    return normalized


def _required_mapping(
    value: Mapping[str, object], field: str
) -> Mapping[str, object]:
    mapped = value.get(field)
    if not isinstance(mapped, Mapping):
        raise EnvironmentFingerprintError(f"fingerprint field {field} must be a mapping")
    return mapped


def _run_text(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    preserve_newlines: bool = False,
    allow_failure: bool = False,
) -> str:
    try:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            check=not allow_failure,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        if allow_failure:
            return ""
        raise EnvironmentFingerprintError(f"command failed: {command[0]}")
    text = result.stdout
    return text if preserve_newlines else text.strip()


def _rfc3339_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise EnvironmentFingerprintError("captured_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )
