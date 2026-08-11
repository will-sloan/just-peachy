"""Machine and complete worker-assignment preflight for launch-day decisions.

The preflight is deliberately read-only except for a short output-writability probe.
It never downloads a model, installs a package, reads a credential value, or runs
inference.  A launch is ready only when every scenario in the assignment passes.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import Iterable, Mapping, Sequence

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version
import psutil
import soundfile as sf

from app.artifact_contracts.atomic import file_sha256
from app.artifact_contracts.registry import scenario_type_from_resolved
from app.benchmark_contracts.manifest_io import read_manifest
from app.benchmark_contracts.scenario import validate_scenario
from app.campaign_exchange.assignments import validate_worker_assignment
from app.campaign_exchange.common import read_yaml_mapping
from app.campaign_executor.runtime import _resolve_and_verify_pipeline
from app.inference_pipeline.catalog import ComponentCatalog, ComponentCatalogEntry


MACHINE_PROFILE_SCHEMA_VERSION = "launch-machine-profile.v1"
LAUNCH_PREFLIGHT_SCHEMA_VERSION = "launch-assignment-preflight.v1"
ESTIMATION_POLICY_VERSION = "launch-estimation-policy.v1"

_QUALIFIED_STATUSES = {"qualified", "qualified_with_warnings", "contract_qualified"}
_GIB = 1024**3
_DEFAULT_MINIMUM_RAM_BYTES = 8 * _GIB
_DEFAULT_DISK_RESERVE_BYTES = 5 * _GIB
_AUDIO_BOUND_TOLERANCE_SECONDS = 0.100
_PACKAGE_IMPORT_NAMES = {
    "openai-whisper": "whisper",
    "pyyaml": "yaml",
    "scikit-learn": "sklearn",
}
_EXECUTOR_SUPPORTED_SCENARIO_TYPES = frozenset({"asr"})
_CREDENTIAL_GROUPS = {
    "pyannote": ("PYANNOTE_LICENSE_ACCEPTED", "PYANNOTE_AUTH_TOKEN"),
    "falcon": ("PICOVOICE_LICENSE_ACCEPTED", "PICOVOICE_ACCESS_KEY"),
}


class LaunchReadinessError(RuntimeError):
    """Raised when launch evidence cannot be produced safely."""


def credential_readiness() -> dict[str, str]:
    """Return presence-only readiness for credential-gated backends."""

    return {
        backend: (
            "READY"
            if all(bool(os.environ.get(name)) for name in requirements)
            else "MISSING"
        )
        for backend, requirements in _CREDENTIAL_GROUPS.items()
    }


def collect_machine_profile(
    *,
    machine_id: str,
    repository_root: Path,
    project_root: Path,
    environment_profile: str,
    output_root: Path,
    selected_device: str | None = None,
    execution_dtype: str | None = None,
    credential_names: Sequence[str] = (),
) -> dict[str, object]:
    """Capture a privacy-safe, secret-free launch profile for the current machine."""

    machine = _machine_id(machine_id)
    repository = repository_root.resolve()
    project = project_root.resolve()
    output = output_root.resolve()
    git = _git_profile(repository)
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(
        output if output.exists() else _nearest_existing_parent(output)
    )
    torch_profile = _torch_profile()
    gpus = _nvidia_gpus()
    ffmpeg = _ffmpeg_profile()
    credentials = [
        {"name": name, "present": bool(os.environ.get(name)), "value_recorded": False}
        for name in sorted(set(credential_names))
    ]
    profile: dict[str, object] = {
        "schema_version": MACHINE_PROFILE_SCHEMA_VERSION,
        "captured_at_utc": _utc_now(),
        "machine_id": machine,
        "host_fingerprint": hashlib.sha256(
            f"{socket.gethostname()}|{platform.node()}".encode("utf-8")
        )
        .hexdigest()
        .upper()[:16],
        "privacy": {
            "raw_hostname_recorded": False,
            "credential_values_recorded": False,
            "absolute_dataset_paths_recorded": False,
        },
        "repository": git,
        "paths": {
            "repository_root": _portable_location(repository, repository),
            "project_root": _portable_location(project, repository),
            "output_root": _portable_location(output, repository),
        },
        "environment": {
            "profile": environment_profile,
            "python": _portable_location(Path(sys.executable).resolve(), repository),
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "conda_available": shutil.which("conda") is not None,
            "virtual_environment_active": bool(os.environ.get("VIRTUAL_ENV")),
        },
        "operating_system": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
        },
        "hardware": {
            "cpu": platform.processor() or platform.machine(),
            "physical_cpu_count": psutil.cpu_count(logical=False),
            "logical_cpu_count": psutil.cpu_count(logical=True),
            "ram_total_bytes": int(memory.total),
            "ram_available_bytes": int(memory.available),
            "disk_total_bytes": int(disk.total),
            "disk_free_bytes": int(disk.free),
            "gpus": gpus,
        },
        "runtime": {"torch": torch_profile, "ffmpeg": ffmpeg},
        "credentials": credentials,
    }
    profile["execution_policy"] = {
        "environment_profile": environment_profile,
        "selected_device": selected_device,
        "execution_dtype": execution_dtype,
        "implicit_device_fallback_allowed": False,
    }
    identity = _canonical_json_bytes(
        {key: value for key, value in profile.items() if key != "captured_at_utc"}
    )
    profile["profile_sha256"] = hashlib.sha256(identity).hexdigest().upper()
    return profile


def preflight_worker_assignment(
    *,
    campaign_root: Path,
    assignment_path: Path,
    repository_root: Path,
    project_root: Path,
    machine_profile: Mapping[str, object],
    expected_environment_profile: str,
    estimated_rtf: float = 0.235,
    estimated_rtf_low: float = 0.20,
    estimated_rtf_high: float = 0.35,
    minimum_free_disk_reserve_bytes: int = _DEFAULT_DISK_RESERVE_BYTES,
    inspect_audio_headers: bool = True,
) -> dict[str, object]:
    """Preflight every assigned scenario and return launch evidence.

    The report cannot be ready when even one assigned scenario was not inspected.
    Audio files and model assets are cached while checking so repeated conditions do
    not repeatedly read the same large files.
    """

    root = campaign_root.resolve()
    assignment_file = assignment_path.resolve()
    repository = repository_root.resolve()
    project = project_root.resolve()
    assignment = read_yaml_mapping(assignment_file)
    actual_commit = str(
        _mapping(machine_profile.get("repository"), "machine repository").get("commit")
        or ""
    )
    # Validate immutable assignment content first. Commit/profile differences are
    # launch blockers, but must still produce a complete diagnostic report.
    assignment_validation = validate_worker_assignment(root, assignment_file)
    scenario_ids = [str(value) for value in assignment_validation["scenario_ids"]]
    campaign_manifest_path = root / "campaign_manifest.json"
    campaign_manifest = _read_json_mapping(campaign_manifest_path)
    scenarios = {
        scenario_id: _read_json_mapping(
            root / "scenarios" / scenario_id / "resolved_scenario.json"
        )
        for scenario_id in scenario_ids
    }
    for scenario in scenarios.values():
        validate_scenario(scenario)

    shared_checks: list[dict[str, object]] = []
    shared_checks.append(
        _check(
            "assignment_integrity",
            True,
            f"{len(scenario_ids)} immutable scenario identities validated",
        )
    )
    shared_checks.append(
        _check(
            "repository_commit",
            actual_commit == assignment["expected_git_commit"],
            (f"actual={actual_commit}; expected={assignment['expected_git_commit']}"),
        )
    )
    repository_profile = _mapping(machine_profile.get("repository"), "repository")
    shared_checks.append(
        _check(
            "repository_clean",
            not bool(repository_profile.get("dirty")),
            (
                "Git worktree is clean"
                if not bool(repository_profile.get("dirty"))
                else "Git worktree contains tracked or untracked changes"
            ),
        )
    )
    shared_checks.append(
        _check(
            "environment_profile",
            expected_environment_profile == assignment["expected_environment_profile"],
            f"active profile is {expected_environment_profile}",
        )
    )
    shared_checks.append(
        _check(
            "machine_assignment_identity",
            machine_profile.get("machine_id") == assignment["worker_id"],
            (
                f"machine={machine_profile.get('machine_id')}; "
                f"assignment_worker={assignment['worker_id']}"
            ),
        )
    )
    output_check = _output_writable(root)
    shared_checks.append(output_check)

    catalog = ComponentCatalog.load()
    component_entries = {(item.family, item.name): item for item in catalog.entries}
    active_entries = _active_component_entries(scenarios.values(), component_entries)
    component_checks = _component_checks(
        active_entries,
        scenarios.values(),
        expected_environment_profile=expected_environment_profile,
        machine_profile=machine_profile,
    )
    runtime_checks = _execution_runtime_checks(
        scenarios.values(),
        expected_environment_profile=expected_environment_profile,
        machine_profile=machine_profile,
    )
    shared_checks.extend(runtime_checks)
    package_checks = _package_checks(active_entries)
    credential_checks = _credential_checks(active_entries)
    model_asset_checks = _model_asset_checks(scenarios.values(), repository)

    manifest_cache: dict[str, list[dict[str, object]]] = {}
    audio_cache: dict[str, dict[str, object]] = {}
    pipeline_cache: dict[str, tuple[bool, str]] = {}
    rir_cache: dict[str, dict[str, object]] = {}
    scenario_reports: list[dict[str, object]] = []
    global_unique_audio: set[str] = set()
    total_item_executions = 0
    total_audio_seconds = 0.0
    total_estimated_disk = 0
    total_runtime_point = 0.0
    total_runtime_low = 0.0
    total_runtime_high = 0.0

    for scenario_id in scenario_ids:
        scenario = scenarios[scenario_id]
        blockers: list[str] = []
        scenario_type = scenario_type_from_resolved(scenario)
        if scenario_type not in _EXECUTOR_SUPPORTED_SCENARIO_TYPES:
            blockers.append(f"executor_support:{scenario_type}")
        manifest_identity = _mapping(
            scenario.get("benchmark_manifest"), "manifest identity"
        )
        manifest_name = Path(str(manifest_identity["path"])).name
        manifest_path = root / "benchmark_manifests" / manifest_name
        manifest_key = str(manifest_path)
        if manifest_key not in manifest_cache:
            manifest_cache[manifest_key] = read_manifest(manifest_path)
        rows = _select_rows(manifest_cache[manifest_key], scenario)
        expected_rows = int(
            _mapping(scenario["dataset_slice"], "dataset slice")["row_count"]
        )
        if len(rows) != expected_rows:
            blockers.append(f"manifest_row_count:{len(rows)}_of_{expected_rows}")

        scenario_audio_seconds = sum(float(row["duration_sec"]) for row in rows)
        scenario_unique_audio: set[str] = set()
        missing_audio: list[str] = []
        unreadable_audio: list[str] = []
        invalid_bounds: list[str] = []
        for row in rows:
            relative = _portable_relative_path(str(row["audio_path_project_relative"]))
            scenario_unique_audio.add(relative)
            global_unique_audio.add(relative)
            if relative not in audio_cache:
                audio_cache[relative] = _inspect_audio(
                    project / PurePosixPath(relative),
                    inspect_header=inspect_audio_headers,
                )
            audio = audio_cache[relative]
            if not audio["exists"]:
                missing_audio.append(relative)
                continue
            if not audio["readable"]:
                unreadable_audio.append(relative)
                continue
            if inspect_audio_headers and not _bounds_fit_audio(row, audio):
                invalid_bounds.append(relative)
        if missing_audio:
            blockers.append(f"missing_audio:{len(set(missing_audio))}")
        if unreadable_audio:
            blockers.append(f"unreadable_audio:{len(set(unreadable_audio))}")
        if invalid_bounds:
            blockers.append(f"invalid_audio_bounds:{len(set(invalid_bounds))}")

        pipeline_key = str(
            _mapping(scenario["pipeline"], "pipeline").get("resolved_config_sha256")
            or scenario_id
        )
        if pipeline_key not in pipeline_cache:
            try:
                _resolve_and_verify_pipeline(project, scenario)
            except Exception as exc:  # noqa: BLE001 - diagnostic boundary
                pipeline_cache[pipeline_key] = (
                    False,
                    f"{type(exc).__name__}: {_safe_message(exc)}",
                )
            else:
                pipeline_cache[pipeline_key] = (
                    True,
                    "frozen pipeline identity resolved",
                )
        pipeline_ok, pipeline_detail = pipeline_cache[pipeline_key]
        if not pipeline_ok:
            blockers.append("pipeline_resolution")

        rir_check = _scenario_rir_check(scenario, project, rir_cache)
        if not rir_check["ready"]:
            blockers.append("rir_asset")

        estimate = _scenario_estimate(
            audio_seconds=scenario_audio_seconds,
            item_count=len(rows),
            estimated_rtf=estimated_rtf,
            estimated_rtf_low=estimated_rtf_low,
            estimated_rtf_high=estimated_rtf_high,
        )
        total_item_executions += len(rows)
        total_audio_seconds += scenario_audio_seconds
        total_estimated_disk += int(estimate["disk_bytes"])
        total_runtime_point += float(estimate["runtime_seconds"])
        total_runtime_low += float(estimate["runtime_low_seconds"])
        total_runtime_high += float(estimate["runtime_high_seconds"])
        scenario_reports.append(
            {
                "scenario_id": scenario_id,
                "scenario_hash": scenario["scenario_hash"],
                "panel": scenario["panel"],
                "tier": scenario["tier"],
                "dataset": _mapping(scenario["dataset_slice"], "dataset slice")[
                    "dataset"
                ],
                "condition_id": _mapping(scenario["condition"], "condition")["id"],
                "scenario_type": scenario_type,
                "item_count": len(rows),
                "audio_seconds": round(scenario_audio_seconds, 6),
                "unique_audio_file_count": len(scenario_unique_audio),
                "audio": {
                    "expected": len(scenario_unique_audio),
                    "missing": len(set(missing_audio)),
                    "unreadable": len(set(unreadable_audio)),
                    "invalid_bounds": len(set(invalid_bounds)),
                    "missing_examples": sorted(set(missing_audio))[:10],
                    "unreadable_examples": sorted(set(unreadable_audio))[:10],
                    "invalid_bound_examples": sorted(set(invalid_bounds))[:10],
                },
                "pipeline": {"ready": pipeline_ok, "detail": pipeline_detail},
                "rir": rir_check,
                "estimate": estimate,
                "local_blockers": sorted(set(blockers)),
                "scenario_specific_ready": not blockers,
            }
        )

    required_disk = total_estimated_disk + minimum_free_disk_reserve_bytes
    hardware = _mapping(machine_profile.get("hardware"), "hardware")
    free_disk = int(hardware.get("disk_free_bytes") or 0)
    disk_check = _check(
        "disk_capacity",
        free_disk >= required_disk,
        (f"{free_disk} bytes free; {required_disk} bytes required including reserve"),
    )
    shared_checks.append(disk_check)
    ram_bytes = int(hardware.get("ram_total_bytes") or 0)
    shared_checks.append(
        _check(
            "system_ram",
            ram_bytes >= _DEFAULT_MINIMUM_RAM_BYTES,
            f"{ram_bytes} bytes installed; {_DEFAULT_MINIMUM_RAM_BYTES} minimum",
        )
    )

    global_requirements_ready = all(
        bool(item["ready"])
        for item in (
            shared_checks
            + component_checks
            + package_checks
            + credential_checks
            + model_asset_checks
        )
    )
    for item in scenario_reports:
        item["ready"] = global_requirements_ready and not item["local_blockers"]

    ready_count = sum(bool(item["ready"]) for item in scenario_reports)
    scenario_specific_ready_count = sum(
        bool(item["scenario_specific_ready"]) for item in scenario_reports
    )
    blocked_count = len(scenario_reports) - ready_count
    complete_coverage = len(scenario_reports) == len(scenario_ids)
    blockers = _blocker_summary(
        shared_checks,
        component_checks,
        package_checks,
        credential_checks,
        model_asset_checks,
        scenario_reports,
    )
    ready = complete_coverage and blocked_count == 0 and not blockers
    return {
        "schema_version": LAUNCH_PREFLIGHT_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "verdict": "READY_TO_LAUNCH" if ready else "NOT_READY_TO_LAUNCH",
        "machine_id": machine_profile["machine_id"],
        "machine_profile_sha256": machine_profile["profile_sha256"],
        "campaign": {
            "campaign_id": campaign_manifest["campaign_id"],
            "campaign_manifest_sha256": file_sha256(campaign_manifest_path),
            "scenario_count": len(campaign_manifest["scenario_ids"]),
        },
        "assignment": {
            "assignment_id": assignment["assignment_id"],
            "assignment_sha256": assignment["assignment_sha256"],
            "worker_id": assignment["worker_id"],
            "expected_git_commit": assignment["expected_git_commit"],
            "expected_environment_profile": assignment["expected_environment_profile"],
        },
        "coverage": {
            "assigned_scenario_count": len(scenario_ids),
            "preflighted_scenario_count": len(scenario_reports),
            "ready_scenario_count": ready_count,
            "blocked_scenario_count": blocked_count,
            "scenario_specific_ready_count": scenario_specific_ready_count,
            "complete_assignment_preflight": complete_coverage,
            "item_execution_count": total_item_executions,
            "unique_source_audio_file_count": len(global_unique_audio),
            "audio_seconds": round(total_audio_seconds, 6),
            "audio_hours": round(total_audio_seconds / 3600.0, 6),
        },
        "checks": {
            "shared": shared_checks,
            "components": component_checks,
            "packages": package_checks,
            "credentials": credential_checks,
            "model_assets": model_asset_checks,
        },
        "estimates": {
            "policy_version": ESTIMATION_POLICY_VERSION,
            "basis": "Machine A Whisper Base CPU observation; Machine B remains provisional until measured",
            "rtf_point": estimated_rtf,
            "rtf_low": estimated_rtf_low,
            "rtf_high": estimated_rtf_high,
            "per_scenario_initialization_point_seconds": 20.0,
            "runtime_seconds": round(total_runtime_point, 3),
            "runtime_low_seconds": round(total_runtime_low, 3),
            "runtime_high_seconds": round(total_runtime_high, 3),
            "artifact_disk_bytes": total_estimated_disk,
            "minimum_free_disk_reserve_bytes": minimum_free_disk_reserve_bytes,
            "required_free_disk_bytes": required_disk,
            "observed_free_disk_bytes": free_disk,
        },
        "blockers": blockers,
        "scenarios": scenario_reports,
    }


def _active_component_entries(
    scenarios: Iterable[Mapping[str, object]],
    catalog: Mapping[tuple[str, str], ComponentCatalogEntry],
) -> list[ComponentCatalogEntry]:
    identities: set[tuple[str, str]] = set()
    for scenario in scenarios:
        pipeline = _mapping(scenario["pipeline"], "pipeline")
        components = _mapping(pipeline["components"], "components")
        for family, raw in components.items():
            component = _mapping(raw, f"component {family}")
            if bool(component.get("enabled")):
                identities.add((str(family), str(component["name"])))
    missing = sorted(identity for identity in identities if identity not in catalog)
    if missing:
        raise LaunchReadinessError(
            f"frozen components are absent from catalog: {missing}"
        )
    return [catalog[identity] for identity in sorted(identities)]


def _component_checks(
    entries: Sequence[ComponentCatalogEntry],
    scenarios: Iterable[Mapping[str, object]],
    *,
    expected_environment_profile: str,
    machine_profile: Mapping[str, object],
) -> list[dict[str, object]]:
    os_name = str(
        _mapping(machine_profile.get("operating_system"), "operating system").get(
            "system"
        )
        or ""
    ).lower()
    hardware = _mapping(machine_profile.get("hardware"), "hardware")
    torch_runtime = _mapping(
        _mapping(machine_profile.get("runtime", {}), "runtime").get("torch", {}),
        "torch runtime",
    )
    requested_pairs = {
        (
            _device_family(_mapping(scenario["runtime"], "runtime")["device"]),
            str(_mapping(scenario["runtime"], "runtime")["dtype"]).lower(),
        )
        for scenario in scenarios
    }
    checks: list[dict[str, object]] = []
    for entry in entries:
        reasons: list[str] = []
        if entry.qualification_status not in _QUALIFIED_STATUSES:
            reasons.append(f"qualification={entry.qualification_status}")
        if expected_environment_profile not in entry.environment_profiles:
            reasons.append(f"profile={expected_environment_profile}")
        supported_os = {value.lower() for value in entry.supported_operating_systems}
        if supported_os and os_name not in supported_os:
            reasons.append(f"os={os_name}")
        supported_device_dtype = {
            value.lower() for value in entry.device_dtype_settings
        }
        for device, dtype in requested_pairs:
            if device == "cpu" and not bool(entry.hardware_requirements.get("cpu")):
                reasons.append("cpu_not_supported")
            if device.startswith("cuda"):
                if not bool(
                    entry.hardware_requirements.get("cuda")
                    or entry.hardware_requirements.get("gpu")
                ):
                    reasons.append("cuda_not_supported")
                if not bool(torch_runtime.get("cuda_available")):
                    reasons.append("cuda_runtime_unavailable")
                if not hardware.get("gpus"):
                    reasons.append("gpu_not_detected")
            requested = f"{device}/{dtype}"
            if supported_device_dtype and requested not in supported_device_dtype:
                reasons.append(f"unsupported={requested}")
        checks.append(
            {
                "id": f"component:{entry.family}:{entry.name}",
                "family": entry.family,
                "name": entry.name,
                "qualification_status": entry.qualification_status,
                "ready": not reasons,
                "detail": "; ".join(reasons) if reasons else "qualified and compatible",
            }
        )
    return checks


def _execution_runtime_checks(
    scenarios: Iterable[Mapping[str, object]],
    *,
    expected_environment_profile: str,
    machine_profile: Mapping[str, object],
) -> list[dict[str, object]]:
    pairs = {
        (
            _normalized_device(_mapping(scenario["runtime"], "runtime")["device"]),
            str(_mapping(scenario["runtime"], "runtime")["dtype"]).strip().lower(),
        )
        for scenario in scenarios
    }
    checks: list[dict[str, object]] = []
    expected_family = "cuda" if expected_environment_profile == "core-cuda" else "cpu"
    families = {_device_family(device) for device, _dtype in pairs}
    checks.append(
        _check(
            "profile_device_consistency",
            families == {expected_family},
            f"profile={expected_environment_profile}; scenario_device_families={sorted(families)}",
        )
    )
    execution_policy = _mapping(
        machine_profile.get("execution_policy", {}), "execution policy"
    )
    selected_device = execution_policy.get("selected_device")
    selected_dtype = execution_policy.get("execution_dtype")
    if selected_device is not None:
        checks.append(
            _check(
                "selected_device_identity",
                {_normalized_device(selected_device)} == {device for device, _dtype in pairs},
                f"machine={selected_device}; scenarios={sorted(device for device, _dtype in pairs)}",
            )
        )
    if selected_dtype is not None:
        checks.append(
            _check(
                "selected_dtype_identity",
                {str(selected_dtype).strip().lower()} == {dtype for _device, dtype in pairs},
                f"machine={selected_dtype}; scenarios={sorted(dtype for _device, dtype in pairs)}",
            )
        )
    if expected_family != "cuda":
        return checks

    runtime = _mapping(machine_profile.get("runtime", {}), "runtime")
    torch_runtime = _mapping(runtime.get("torch", {}), "torch runtime")
    version = str(torch_runtime.get("version") or "")
    checks.extend(
        [
            _check(
                "cuda_torch_build",
                bool(torch_runtime.get("available"))
                and bool(torch_runtime.get("cuda_runtime"))
                and "+cpu" not in version.lower(),
                f"torch={version or None}; cuda_runtime={torch_runtime.get('cuda_runtime')}",
            ),
            _check(
                "cuda_runtime_available",
                bool(torch_runtime.get("cuda_available")),
                f"torch.cuda.is_available={bool(torch_runtime.get('cuda_available'))}",
            ),
            _check(
                "cuda_device_open",
                bool(torch_runtime.get("allocation_probe_succeeded")),
                str(torch_runtime.get("allocation_probe_reason") or "CUDA allocation probe passed"),
            ),
        ]
    )
    device_count = int(torch_runtime.get("device_count") or 0)
    requested_indices = {
        _cuda_index(device) for device, _dtype in pairs if _device_family(device) == "cuda"
    }
    checks.append(
        _check(
            "cuda_device_index",
            bool(requested_indices)
            and all(index is not None and 0 <= index < device_count for index in requested_indices),
            f"requested={sorted(index for index in requested_indices if index is not None)}; device_count={device_count}",
        )
    )
    return checks


def _package_checks(
    entries: Sequence[ComponentCatalogEntry],
) -> list[dict[str, object]]:
    requirements = sorted(
        {value for entry in entries for value in entry.required_packages}
    )
    checks: list[dict[str, object]] = []
    for raw in requirements:
        requirement = Requirement(raw)
        name = requirement.name
        if name.lower() == "ffmpeg":
            profile = _ffmpeg_profile()
            observed = profile.get("version")
            compatible = bool(profile["available"]) and _version_matches(
                str(observed or ""), requirement
            )
            checks.append(
                {
                    "id": f"system:{name}",
                    "requirement": raw,
                    "observed_version": observed,
                    "ready": compatible,
                    "detail": (
                        "FFmpeg executable is available"
                        if compatible
                        else "required FFmpeg executable/version is unavailable"
                    ),
                }
            )
            continue
        try:
            observed = metadata.version(name)
        except metadata.PackageNotFoundError:
            observed = None
        import_name = _PACKAGE_IMPORT_NAMES.get(name.lower(), name.replace("-", "_"))
        importable = _module_importable(import_name)
        compatible = observed is not None and _version_matches(observed, requirement)
        checks.append(
            {
                "id": f"package:{name}",
                "requirement": raw,
                "observed_version": observed,
                "import_name": import_name,
                "importable": importable,
                "ready": compatible and importable,
                "detail": (
                    "installed, importable, and version-compatible"
                    if compatible and importable
                    else "package is missing, not importable, or version-incompatible"
                ),
            }
        )
    return checks


def _credential_checks(
    entries: Sequence[ComponentCatalogEntry],
) -> list[dict[str, object]]:
    names = sorted(
        {name for entry in entries for name in entry.credential_requirements}
    )
    return [
        {
            "id": f"credential:{name}",
            "name": name,
            "present": bool(os.environ.get(name)),
            "value_recorded": False,
            "ready": bool(os.environ.get(name)),
            "detail": "present"
            if os.environ.get(name)
            else "required environment variable absent",
        }
        for name in names
    ]


def _model_asset_checks(
    scenarios: Iterable[Mapping[str, object]], repository_root: Path
) -> list[dict[str, object]]:
    assets: dict[str, Mapping[str, object]] = {}
    for scenario in scenarios:
        models = _mapping(
            _mapping(scenario["pipeline"], "pipeline")["models"], "models"
        )
        for raw_model in models.values():
            model = _mapping(raw_model, "model")
            raw_assets = model.get("assets")
            if not isinstance(raw_assets, list):
                continue
            for raw_asset in raw_assets:
                asset = _mapping(raw_asset, "model asset")
                configured = str(
                    asset.get("configured_identity") or asset.get("path") or ""
                )
                if configured:
                    assets.setdefault(configured, asset)
    checks: list[dict[str, object]] = []
    for configured, asset in sorted(assets.items()):
        relative = str(asset.get("path") or configured.split("|", 1)[0])
        path_ok = _is_portable_relative(relative)
        path = repository_root / PurePosixPath(relative) if path_ok else repository_root
        present = path_ok and path.is_file()
        observed_bytes = path.stat().st_size if present else None
        expected_bytes = _optional_int(asset.get("expected_bytes"))
        size_matches = present and (
            expected_bytes is None or observed_bytes == expected_bytes
        )
        expected_hash = str(asset.get("expected_sha256") or "").upper() or None
        observed_hash = file_sha256(path) if present and expected_hash else None
        hash_matches = present and (
            expected_hash is None or observed_hash == expected_hash
        )
        checks.append(
            {
                "id": f"model_asset:{relative}",
                "path": relative,
                "expected_bytes": expected_bytes,
                "observed_bytes": observed_bytes,
                "expected_sha256": expected_hash,
                "observed_sha256": observed_hash,
                "ready": bool(path_ok and present and size_matches and hash_matches),
                "detail": (
                    "asset exists and identity matches"
                    if path_ok and present and size_matches and hash_matches
                    else "asset missing, non-portable, or identity mismatch"
                ),
            }
        )
    return checks


def _select_rows(
    rows: Sequence[Mapping[str, object]], scenario: Mapping[str, object]
) -> list[dict[str, object]]:
    data_slice = _mapping(scenario["dataset_slice"], "dataset slice")
    filters = _mapping(data_slice["filters"], "dataset filters")
    selected = []
    for row in rows:
        if row.get("dataset") != data_slice["dataset"]:
            continue
        if row.get("benchmark_tier") != scenario["tier"]:
            continue
        if row.get("panel") != scenario["panel"]:
            continue
        if any(
            row.get(key) != value for key, value in filters.items() if value is not None
        ):
            continue
        selected.append(dict(row))
    selected.sort(
        key=lambda item: (
            str(item.get("selection_rank") or ""),
            str(item.get("recording_id") or ""),
            str(item.get("utt_id") or ""),
        )
    )
    return selected


def _inspect_audio(path: Path, *, inspect_header: bool) -> dict[str, object]:
    if not path.is_file():
        return {"exists": False, "readable": False, "reason": "missing"}
    if not inspect_header:
        return {"exists": True, "readable": True, "reason": None}
    try:
        info = sf.info(str(path))
    except Exception as exc:  # noqa: BLE001 - external decoder boundary
        return {
            "exists": True,
            "readable": False,
            "reason": f"{type(exc).__name__}: {_safe_message(exc)}",
        }
    duration = float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
    return {
        "exists": True,
        "readable": bool(info.frames > 0 and info.samplerate > 0 and info.channels > 0),
        "reason": None,
        "sample_rate_hz": int(info.samplerate),
        "channels": int(info.channels),
        "frames": int(info.frames),
        "duration_seconds": duration,
        "format": str(info.format),
        "subtype": str(info.subtype),
    }


def _bounds_fit_audio(row: Mapping[str, object], audio: Mapping[str, object]) -> bool:
    start = float(row.get("start_sec") or 0.0)
    end = float(row.get("end_sec") or 0.0)
    available = float(audio.get("duration_seconds") or 0.0)
    return (
        start >= 0.0
        and end > start
        and end <= available + _AUDIO_BOUND_TOLERANCE_SECONDS
    )


def _scenario_rir_check(
    scenario: Mapping[str, object],
    project_root: Path,
    cache: dict[str, dict[str, object]],
) -> dict[str, object]:
    condition = _mapping(scenario["condition"], "condition")
    raw_rir = condition.get("rir")
    if raw_rir is None:
        return {"required": False, "ready": True, "detail": "no RIR required"}
    rir = _mapping(raw_rir, "RIR")
    relative = _portable_relative_path(str(rir["relative_path"]))
    expected_hash = str(rir["sha256"]).upper()
    cache_key = f"{relative}|{expected_hash}"
    if cache_key not in cache:
        path = project_root / PurePosixPath(relative)
        present = path.is_file()
        observed = file_sha256(path) if present else None
        cache[cache_key] = {
            "required": True,
            "rir_id": rir["rir_id"],
            "environment": rir["environment"],
            "resolved_identifier": rir["resolved_identifier"],
            "relative_path": relative,
            "expected_sha256": expected_hash,
            "observed_sha256": observed,
            "ready": present and observed == expected_hash,
            "detail": (
                "exact RIR asset exists and hash matches"
                if present and observed == expected_hash
                else "exact RIR asset is missing or hash differs"
            ),
        }
    return dict(cache[cache_key])


def _scenario_estimate(
    *,
    audio_seconds: float,
    item_count: int,
    estimated_rtf: float,
    estimated_rtf_low: float,
    estimated_rtf_high: float,
) -> dict[str, object]:
    point = audio_seconds * estimated_rtf + 20.0
    low = audio_seconds * estimated_rtf_low + 15.0
    high = audio_seconds * estimated_rtf_high + 60.0
    # No source audio is copied. This budgets typed metrics, logs, plots, reports,
    # one-second telemetry, and a 2x uncertainty factor.
    raw_disk = 12 * 1024**2 + item_count * 64 * 1024 + high * 4096
    disk = int(raw_disk * 2.0)
    return {
        "runtime_seconds": round(point, 3),
        "runtime_low_seconds": round(low, 3),
        "runtime_high_seconds": round(high, 3),
        "disk_bytes": disk,
    }


def _blocker_summary(
    shared: Sequence[Mapping[str, object]],
    components: Sequence[Mapping[str, object]],
    packages: Sequence[Mapping[str, object]],
    credentials: Sequence[Mapping[str, object]],
    assets: Sequence[Mapping[str, object]],
    scenarios: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    for item in [*shared, *components, *packages, *credentials, *assets]:
        if not bool(item.get("ready")):
            blockers.append(
                {
                    "scope": "assignment",
                    "id": item.get("id"),
                    "detail": item.get("detail"),
                }
            )
    grouped: dict[str, list[str]] = defaultdict(list)
    for scenario in scenarios:
        for blocker in scenario["local_blockers"]:
            grouped[str(blocker)].append(str(scenario["scenario_id"]))
    for blocker, scenario_ids in sorted(grouped.items()):
        blockers.append(
            {
                "scope": "scenario",
                "id": blocker,
                "scenario_count": len(scenario_ids),
                "scenario_examples": scenario_ids[:10],
            }
        )
    return blockers


def _git_profile(repository_root: Path) -> dict[str, object]:
    commit = _git(repository_root, "rev-parse", "HEAD")
    branch = _git(repository_root, "branch", "--show-current")
    status = _git(repository_root, "status", "--porcelain=v1", "--untracked-files=all")
    changes = [line for line in status.splitlines() if line.strip()]
    return {
        "commit": commit,
        "branch": branch,
        "dirty": bool(changes),
        "changed_path_count": len(changes),
    }


def _git(repository_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise LaunchReadinessError(f"Git probe failed: {arguments}") from exc
    return result.stdout.strip()


def _torch_profile() -> dict[str, object]:
    try:
        import torch
    except Exception as exc:  # noqa: BLE001 - optional runtime dependency
        return {
            "available": False,
            "version": None,
            "cuda_available": False,
            "reason": f"{type(exc).__name__}: {_safe_message(exc)}",
        }
    available = bool(torch.cuda.is_available())
    device_count = int(torch.cuda.device_count()) if available else 0
    allocation_probe_succeeded = False
    allocation_probe_reason: str | None = "CUDA unavailable"
    device_names: list[str] = []
    if available:
        device_names = [str(torch.cuda.get_device_name(index)) for index in range(device_count)]
        try:
            probe = torch.empty(1, device="cuda:0")
            torch.cuda.synchronize(0)
            del probe
        except Exception as exc:  # noqa: BLE001 - hardware diagnostic boundary
            allocation_probe_reason = f"{type(exc).__name__}: {_safe_message(exc)}"
        else:
            allocation_probe_succeeded = True
            allocation_probe_reason = None
    return {
        "available": True,
        "version": str(torch.__version__),
        "cuda_available": available,
        "cuda_runtime": str(torch.version.cuda) if torch.version.cuda else None,
        "cudnn_version": (
            int(torch.backends.cudnn.version())
            if torch.backends.cudnn.version() is not None
            else None
        ),
        "device_count": device_count,
        "device_names": device_names,
        "allocation_probe_succeeded": allocation_probe_succeeded,
        "allocation_probe_reason": allocation_probe_reason,
        "reason": None,
    }


def _normalized_device(value: object) -> str:
    device = str(value).strip().lower()
    return "cuda:0" if device == "cuda" else device


def _device_family(value: object) -> str:
    device = _normalized_device(value)
    return "cuda" if device.startswith("cuda:") else device


def _cuda_index(value: object) -> int | None:
    device = _normalized_device(value)
    if not device.startswith("cuda:"):
        return None
    try:
        return int(device.split(":", 1)[1])
    except ValueError:
        return None


def _nvidia_gpus() -> list[dict[str, object]]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return []
    query = "index,name,uuid,memory.total,driver_version,power.limit"
    try:
        result = subprocess.run(
            [
                executable,
                f"--query-gpu={query}",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in result.stdout.splitlines():
        values = [value.strip() for value in line.split(",")]
        if len(values) != 6:
            continue
        rows.append(
            {
                "index": int(values[0]),
                "name": values[1],
                "uuid": values[2],
                "memory_total_mib": _optional_float(values[3]),
                "driver_version": values[4],
                "power_limit_watts": _optional_float(values[5]),
            }
        )
    return rows


def _ffmpeg_profile() -> dict[str, object]:
    executable = shutil.which("ffmpeg")
    if executable is None:
        return {"available": False, "version": None, "reason": "not found on PATH"}
    try:
        result = subprocess.run(
            [executable, "-version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "version": None,
            "reason": f"{type(exc).__name__}: {_safe_message(exc)}",
        }
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    match = re.search(r"ffmpeg version\s+([0-9]+(?:\.[0-9]+){1,3})", first_line)
    return {
        "available": True,
        "version": match.group(1) if match else None,
        "reason": None if match else "version could not be parsed",
    }


def _output_writable(campaign_root: Path) -> dict[str, object]:
    probe_root = campaign_root / "audit" / "launch_readiness"
    try:
        probe_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=probe_root,
            delete=False,
            prefix=".write-probe-",
        ) as handle:
            handle.write("launch readiness probe\n")
            temporary = Path(handle.name)
        temporary.unlink()
    except OSError as exc:
        return _check(
            "output_writable", False, f"{type(exc).__name__}: {_safe_message(exc)}"
        )
    return _check("output_writable", True, "campaign output location is writable")


def _check(identifier: str, ready: bool, detail: str) -> dict[str, object]:
    return {"id": identifier, "ready": bool(ready), "detail": detail}


def _version_matches(observed: str, requirement: Requirement) -> bool:
    try:
        return not requirement.specifier or Version(observed) in requirement.specifier
    except InvalidVersion:
        return False


def _module_importable(name: str) -> bool:
    try:
        __import__(name)
    except Exception:  # noqa: BLE001 - import compatibility is the check
        return False
    return True


def _portable_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if not _is_portable_relative(normalized):
        raise LaunchReadinessError(f"non-portable project-relative path: {value!r}")
    return normalized


def _is_portable_relative(value: str) -> bool:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    return (
        bool(normalized)
        and not path.is_absolute()
        and ".." not in path.parts
        and ":" not in path.parts[0]
    )


def _portable_location(path: Path, repository_root: Path) -> str:
    try:
        relative = path.relative_to(repository_root)
    except ValueError:
        return f"external:{path.name}"
    value = relative.as_posix()
    return "<repository>" if value == "." else f"<repository>/{value}"


def _nearest_existing_parent(path: Path) -> Path:
    current = path
    while not current.exists() and current.parent != current:
        current = current.parent
    if not current.exists():
        raise LaunchReadinessError(f"no existing parent for output path: {path.name}")
    return current


def _read_json_mapping(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LaunchReadinessError(f"expected JSON object: {path.name}")
    return value


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise LaunchReadinessError(f"{label} must be a mapping")
    return value


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_message(exc: BaseException) -> str:
    text = str(exc).replace("\r", " ").replace("\n", " ").strip()
    return text[:300]


def _machine_id(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", normalized):
        raise LaunchReadinessError("machine ID must be 1-32 lowercase safe characters")
    return normalized


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
