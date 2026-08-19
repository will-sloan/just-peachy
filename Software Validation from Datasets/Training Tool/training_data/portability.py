"""Portable roots, logical paths, and Windows-to-WSL discovery helpers."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class PortabilityError(RuntimeError):
    """Raised when a configured machine boundary cannot be validated."""


@dataclass(frozen=True)
class PortableRoots:
    repository: Path
    data: Path
    training: Path
    models: Path
    runs: Path

    def as_mapping(self) -> dict[str, Path]:
        return {
            "JP_REPO_ROOT": self.repository,
            "JP_DATA_ROOT": self.data,
            "JP_TRAINING_ROOT": self.training,
            "JP_MODEL_ROOT": self.models,
            "JP_RUN_ROOT": self.runs,
        }


def portable_roots(repository_default: Path) -> PortableRoots:
    """Resolve all five public roots without depending on a username or drive."""
    repository = Path(os.environ.get("JP_REPO_ROOT", repository_default)).resolve()
    data = Path(
        os.environ.get(
            "JP_DATA_ROOT", repository / "Software Validation from Datasets"
        )
    ).resolve()
    training = Path(os.environ.get("JP_TRAINING_ROOT", repository / "training")).resolve()
    models = Path(os.environ.get("JP_MODEL_ROOT", repository / "models")).resolve()
    runs = Path(os.environ.get("JP_RUN_ROOT", training / "runs")).resolve()
    return PortableRoots(repository, data, training, models, runs)


def preferred_common_voice_root(roots: PortableRoots) -> Path:
    return (
        roots.data
        / "Raw Datasets (Not formatted)"
        / "Common Voice"
        / "cv-corpus-26.0-2026-06-12"
        / "prepared"
        / "en"
    )


def resolve_logical_path(
    value: str,
    roots: PortableRoots | Mapping[str, Path],
    *,
    use_asset_aliases: bool = True,
) -> Path:
    """Resolve ``JP_*:relative/path`` and apply safe external-asset aliases."""
    mapping = roots.as_mapping() if isinstance(roots, PortableRoots) else dict(roots)
    if ":" not in value:
        raise PortabilityError(f"Logical path has no root identifier: {value}")
    root_id, relative = value.split(":", 1)
    if root_id not in mapping:
        raise PortabilityError(f"Unsupported logical root: {root_id}")
    relative_path = Path(relative.replace("\\", "/"))
    candidate = Path(mapping[root_id]) / relative_path
    if use_asset_aliases and root_id == "JP_TRAINING_ROOT":
        legacy_prefix = Path(
            "datasets/common_voice/english/"
            "cv-corpus-26.0-2026-06-12/prepared/en"
        )
        try:
            tail = relative_path.relative_to(legacy_prefix)
        except ValueError:
            pass
        else:
            data_root = Path(mapping["JP_DATA_ROOT"])
            preferred = (
                data_root
                / "Raw Datasets (Not formatted)"
                / "Common Voice"
                / "cv-corpus-26.0-2026-06-12"
                / "prepared"
                / "en"
                / tail
            )
            if preferred.exists() or not candidate.exists():
                return preferred
    return candidate


def discover_wsl_distro(*, configured: str | None = None) -> str:
    """Return an explicit or default WSL distro after validating wslpath."""
    candidate = (configured or os.environ.get("JP_WSL_DISTRO", "")).strip()
    if not candidate:
        try:
            raw_output = subprocess.run(
                ["wsl.exe", "--list", "--verbose"],
                check=True,
                capture_output=True,
            ).stdout
            if isinstance(raw_output, str):
                listed = raw_output
            elif raw_output.startswith((b"\xff\xfe", b"\xfe\xff")):
                listed = raw_output.decode("utf-16")
            elif b"\x00" in raw_output[:64]:
                listed = raw_output.decode("utf-16-le")
            else:
                listed = raw_output.decode("utf-8")
        except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
            raise PortabilityError(
                "Set JP_WSL_DISTRO because the default WSL distro could not be discovered"
            ) from exc
        defaults = []
        for raw in listed.splitlines():
            line = raw.replace("\x00", "").strip()
            if line.startswith("*"):
                fields = line[1:].strip().split()
                if fields:
                    defaults.append(fields[0])
        if len(defaults) != 1:
            raise PortabilityError(
                "Set JP_WSL_DISTRO because WSL has no unique default distribution"
            )
        candidate = defaults[0]
    try:
        subprocess.run(
            ["wsl.exe", "-d", candidate, "--", "test", "-x", "/usr/bin/wslpath"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PortabilityError(
            f"Configured WSL distro does not provide /usr/bin/wslpath: {candidate}"
        ) from exc
    return candidate


def wsl_home(distro: str) -> str:
    """Discover the selected distro's home without assuming its Linux username."""
    try:
        completed = subprocess.run(
            ["wsl.exe", "-d", distro, "--", "sh", "-lc", 'printf %s "$HOME"'],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PortabilityError(f"Could not discover HOME in WSL distro {distro}") from exc
    value = completed.stdout.strip()
    if not value.startswith("/"):
        raise PortabilityError(f"WSL HOME is not an absolute Linux path: {value!r}")
    return value.rstrip("/")
