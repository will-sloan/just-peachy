"""Path discovery and rebasing utilities.

Normalized metadata currently stores absolute paths from the machine that
produced the parquet files. These helpers rebase those paths through stable
project anchors so the tool can run from another checkout location.
"""

from __future__ import annotations

import re
import os
from pathlib import Path, PureWindowsPath


PROJECT_ANCHOR_ALIASES = {
    "RawDatasets": (
        "RawDatasets",
        "Raw Datasets",
        "Raw Datasets (Not formatted)",
    ),
    "Normalized Metadata": (
        "Normalized Metadata",
    ),
}


def find_project_root(start: Path | None = None) -> Path:
    """Find the ``Software Validation from Datasets`` project root."""

    start_path = (start or Path.cwd()).resolve()
    candidates = [start_path, *start_path.parents]
    for candidate in candidates:
        if _looks_like_project_root(candidate):
            return candidate
        if candidate.name == "Evaluation Tool" and _looks_like_project_root(candidate.parent):
            return candidate.parent
    raise FileNotFoundError(
        "Could not find project root. Run from inside the project, or pass --project-root."
    )


def _looks_like_project_root(path: Path) -> bool:
    return (
        (path / "Normalized Metadata").is_dir()
        and _raw_datasets_root(path) is not None
    )


def tool_root(project_root: Path) -> Path:
    """Return the Evaluation Tool directory for a project root."""

    return project_root / "Evaluation Tool"


def path_parts_any_platform(path_value: str | Path) -> list[str]:
    """Split a Windows or POSIX path string into comparable path parts."""

    text = str(path_value).strip().strip('"').strip("'")
    if re.match(r"^[A-Za-z]:[\\/]", text) or "\\" in text:
        parts = list(PureWindowsPath(text).parts)
    else:
        parts = list(Path(text).parts)
    clean: list[str] = []
    for part in parts:
        if part in {"", "\\", "/"}:
            continue
        if re.match(r"^[A-Za-z]:\\?$", part):
            continue
        clean.append(part)
    return clean


def metadata_path_to_project_relative(
    metadata_path: str | Path | None,
    project_root: Path,
) -> Path | None:
    """Convert a metadata path to a project-root-relative path when possible."""

    if metadata_path is None:
        return None
    text = str(metadata_path).strip()
    if not text:
        return None

    native_path = Path(text)
    if native_path.is_absolute():
        try:
            return native_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            pass

    parts = path_parts_any_platform(text)
    lowered = [part.lower() for part in parts]
    for canonical_anchor, aliases in PROJECT_ANCHOR_ALIASES.items():
        for alias in aliases:
            alias_lower = alias.lower()
            if alias_lower in lowered:
                index = lowered.index(alias_lower)
                return Path(canonical_anchor, *parts[index + 1 :])

    if not native_path.is_absolute():
        return Path(text.replace("\\", "/"))
    return native_path


def resolve_metadata_path(metadata_path: str | Path | None, project_root: Path) -> Path | None:
    """Resolve a metadata path on the current machine."""

    relative = metadata_path_to_project_relative(metadata_path, project_root)
    if relative is None:
        return None
    if relative.is_absolute():
        return relative
    direct = project_root / relative
    if direct.exists() or not relative.parts:
        return direct
    if relative.parts[0] == "RawDatasets":
        raw_root = _raw_datasets_root(project_root)
        if raw_root is not None:
            return raw_root.joinpath(*relative.parts[1:])
    return direct


def _raw_datasets_root(project_root: Path) -> Path | None:
    for alias in PROJECT_ANCHOR_ALIASES["RawDatasets"]:
        candidate = project_root / alias
        if candidate.is_dir():
            return candidate
    return None


def safe_relative_to(path: Path, root: Path) -> str:
    """Return a POSIX-style relative path when possible, else an absolute string."""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        try:
            return Path(os.path.relpath(path.resolve(), root.resolve())).as_posix()
        except ValueError:
            return path.resolve().as_posix()
