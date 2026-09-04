"""Cross-platform, explicit worker-interpreter discovery.

The resolver knows path layout only. It does not install an environment, fall
back to the calling interpreter, or imply that a model stack is ARM-qualified.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import re
from typing import Mapping

from app.utils.paths import repository_root

from .contracts import (
    SUPPORTED_ENVIRONMENT_PROFILES,
    WORKER_INTERPRETER_RESOLUTION_SCHEMA,
)


class InterpreterResolutionError(RuntimeError):
    """An environment profile cannot be resolved to an installed interpreter."""


def environment_override_name(profile: str) -> str:
    """Return the deterministic per-profile interpreter override name."""

    token = re.sub(r"[^A-Za-z0-9]+", "_", profile).strip("_").upper()
    return f"JP_WORKER_PYTHON_{token}"


@dataclass(frozen=True)
class InterpreterResolution:
    """One auditable interpreter-resolution result."""

    environment_profile: str
    path: Path | None
    source: str
    platform_system: str
    platform_machine: str
    path_layout: str
    exists: bool
    executable: bool
    status: str

    def to_jsonable(self) -> dict[str, object]:
        return {
            "schema_version": WORKER_INTERPRETER_RESOLUTION_SCHEMA,
            "environment_profile": self.environment_profile,
            "path": str(self.path) if self.path is not None else None,
            "source": self.source,
            "platform_system": self.platform_system,
            "platform_machine": self.platform_machine,
            "path_layout": self.path_layout,
            "exists": self.exists,
            "executable": self.executable,
            "status": self.status,
            "scientific_qualification_implied": False,
            "linux_arm64_qualification_implied": False,
        }


def resolve_worker_interpreter(
    profile: str,
    *,
    repository: Path | None = None,
    environ: Mapping[str, str] | None = None,
    system: str | None = None,
    machine: str | None = None,
    require_available: bool = True,
) -> InterpreterResolution:
    """Resolve one locked worker environment on Windows or POSIX.

    ``require_available=False`` is intended for model-free diagnostics. Worker
    launch always uses the default ``True`` and therefore fails before spawning
    when the environment is absent.
    """

    profile = profile.strip()
    system_name = (system or platform.system()).strip() or "UNKNOWN"
    machine_name = (machine or platform.machine()).strip() or "UNKNOWN"
    environment = os.environ if environ is None else environ

    if profile not in SUPPORTED_ENVIRONMENT_PROFILES:
        resolution = InterpreterResolution(
            environment_profile=profile,
            path=None,
            source="unsupported_profile",
            platform_system=system_name,
            platform_machine=machine_name,
            path_layout="UNKNOWN",
            exists=False,
            executable=False,
            status="UNSUPPORTED_PROFILE",
        )
        if require_available:
            raise InterpreterResolutionError(
                f"unsupported worker environment profile: {profile}"
            )
        return resolution

    repo = Path(repository) if repository is not None else repository_root().path
    override_name = environment_override_name(profile)
    override = str(environment.get(override_name, "")).strip()
    if override:
        candidate = Path(override).expanduser()
        source = override_name
        layout = "EXPLICIT_OVERRIDE"
    else:
        normalized_system = system_name.casefold()
        if normalized_system == "windows":
            executable_relative = Path("Scripts") / "python.exe"
            layout = "WINDOWS_VENV"
        elif normalized_system in {"linux", "darwin"}:
            executable_relative = Path("bin") / "python"
            layout = "POSIX_VENV"
        else:
            resolution = InterpreterResolution(
                environment_profile=profile,
                path=None,
                source="platform_layout",
                platform_system=system_name,
                platform_machine=machine_name,
                path_layout="UNSUPPORTED",
                exists=False,
                executable=False,
                status="UNSUPPORTED_PLATFORM",
            )
            if require_available:
                raise InterpreterResolutionError(
                    f"unsupported worker platform: {system_name}/{machine_name}"
                )
            return resolution
        environment_root = (
            repo / ".venv"
            if profile == "core-cpu"
            else repo / ".stage8-envs" / profile
        )
        candidate = environment_root / executable_relative
        source = "profile_default"

    exists = candidate.is_file()
    executable = exists and (
        system_name.casefold() == "windows" or os.access(candidate, os.X_OK)
    )
    status = "AVAILABLE" if executable else "ENVIRONMENT_UNAVAILABLE"
    resolution = InterpreterResolution(
        environment_profile=profile,
        path=candidate.resolve(strict=False),
        source=source,
        platform_system=system_name,
        platform_machine=machine_name,
        path_layout=layout,
        exists=exists,
        executable=executable,
        status=status,
    )
    if require_available and not executable:
        raise InterpreterResolutionError(
            f"environment unavailable: {profile}; expected {candidate} "
            f"(override with {override_name})"
        )
    return resolution

