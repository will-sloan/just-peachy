"""Path discovery and rebasing utilities.

Normalized metadata currently stores absolute paths from the machine that
produced the parquet files. These helpers rebase those paths through stable
project anchors so the tool can run from another checkout location.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
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

ROOT_VARIABLES = {
    "repository": "JP_REPO_ROOT",
    "data": "JP_DATA_ROOT",
    "model": "JP_MODEL_ROOT",
    "run": "JP_RUN_ROOT",
    "training": "JP_TRAINING_ROOT",
}


class RootResolutionError(ValueError):
    """Raised when an explicitly configured portable root cannot be used."""


@dataclass(frozen=True)
class RootLocation:
    """One resolved physical root and the source that selected it."""

    name: str
    environment_variable: str
    path: Path
    source: str
    exists: bool


def repository_root() -> RootLocation:
    """Resolve the checkout root without relying on the process working directory."""

    return _root_location(
        "repository",
        _module_repository_root(),
        require_existing_default=True,
        validator=_looks_like_repository_root,
    )


def data_root() -> RootLocation:
    """Resolve the root that contains normalized metadata and raw datasets."""

    return _root_location(
        "data",
        repository_root().path / "Software Validation from Datasets",
        require_existing_default=False,
        validator=_looks_like_project_root,
    )


def model_root() -> RootLocation:
    """Resolve the physical ``models`` root while retaining logical ``models/...`` paths."""

    return _root_location(
        "model",
        repository_root().path / "models",
        require_existing_default=False,
        validator=None,
    )


def run_root() -> RootLocation:
    """Resolve the optional root used by the Evaluation Tool's ordinary ``runs`` output."""

    return _root_location(
        "run",
        tool_root_from_repository(repository_root().path) / "runs",
        require_existing_default=False,
        validator=None,
    )


def training_root() -> RootLocation:
    """Reserve a portable training workspace root without activating training behavior."""

    return _root_location(
        "training",
        repository_root().path / "training",
        require_existing_default=False,
        validator=None,
    )


def root_diagnostic() -> list[RootLocation]:
    """Return all configured roots without opening data, models, or starting work."""

    return [repository_root(), data_root(), model_root(), run_root(), training_root()]


def find_repository_root(start: Path | None = None) -> Path:
    """Find the checkout root from an explicit path or the installed module location.

    ``start`` is retained for callers that already provide an explicit location.
    With no explicit value this intentionally does *not* inspect ``Path.cwd()``.
    """

    configured = os.environ.get(ROOT_VARIABLES["repository"])
    if configured:
        return repository_root().path
    if start is None:
        return repository_root().path
    start_path = start.resolve()
    for candidate in (start_path, *start_path.parents):
        if _looks_like_repository_root(candidate):
            return candidate
    raise FileNotFoundError(
        f"Could not find Just-Peachy repository root from {start_path}. "
        f"Set {ROOT_VARIABLES['repository']} to an existing checkout root."
    )


def tool_root_from_repository(repository: Path) -> Path:
    """Return the Evaluation Tool directory for a checkout root."""

    return repository / "Software Validation from Datasets" / "Evaluation Tool"


def resolve_model_path_from_logical(path_value: str | Path) -> Path:
    """Map a logical model path to its physical local path without changing its text.

    The committed configuration convention is ``models/...``.  An external
    ``JP_MODEL_ROOT`` replaces only the physical directory represented by that
    prefix; it is never serialized back into a scientific artifact.
    """

    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0].lower() == "models":
        return model_root().path / Path(*parts[1:])
    return repository_root().path / path


def resolve_data_path_from_logical(path_value: str | Path) -> Path:
    """Map a project-relative dataset/resource path to the configured data root."""

    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return data_root().path / path


def _root_location(
    name: str,
    default: Path,
    *,
    require_existing_default: bool,
    validator,
) -> RootLocation:
    variable = ROOT_VARIABLES[name]
    configured = os.environ.get(variable)
    source = "environment override" if configured else "default"
    path = Path(configured).expanduser() if configured else default
    path = path.resolve()
    exists = path.is_dir()
    if configured and not exists:
        raise RootResolutionError(
            f"Configured {variable} cannot be used because the directory does not exist: {path}"
        )
    if configured and validator is not None and not validator(path):
        expected = "Just-Peachy repository root" if name == "repository" else f"valid {name} root"
        raise RootResolutionError(
            f"Configured {variable} is not a {expected}: {path}"
        )
    if require_existing_default and not exists:
        raise RootResolutionError(f"Default {name} root does not exist: {path}")
    return RootLocation(name, variable, path, source, exists)


def _module_repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _looks_like_repository_root(path: Path) -> bool:
    return tool_root_from_repository(path).is_dir()


def find_project_root(start: Path | None = None) -> Path:
    """Find the ``Software Validation from Datasets`` project root."""

    if start is None:
        configured_data_root = data_root()
        if _looks_like_project_root(configured_data_root.path):
            return configured_data_root.path
        raise FileNotFoundError(
            "Could not find project root at "
            f"{configured_data_root.path}. Set {ROOT_VARIABLES['data']} to the directory "
            "containing Normalized Metadata and Raw Datasets (Not formatted), or pass "
            "--project-root."
        )

    start_path = start.resolve()
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
        and any(
            (path / alias).is_dir()
            for alias in PROJECT_ANCHOR_ALIASES["RawDatasets"]
        )
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
    canonical = project_root / relative
    if canonical.exists() or not relative.parts:
        return canonical

    # Historical normalized metadata uses the portable ``RawDatasets`` anchor,
    # while the checked-out data directory may use one of the accepted aliases.
    # Keep the public relative-path contract unchanged and resolve through the
    # first existing local alias at runtime.
    first = relative.parts[0]
    aliases = PROJECT_ANCHOR_ALIASES.get(first, ())
    for alias in aliases:
        candidate = project_root / alias / Path(*relative.parts[1:])
        if candidate.exists():
            return candidate
    return canonical


def safe_relative_to(path: Path, root: Path) -> str:
    """Return a POSIX-style relative path when possible, else an absolute string."""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        try:
            return Path(os.path.relpath(path.resolve(), root.resolve())).as_posix()
        except ValueError:
            return path.resolve().as_posix()


def _main() -> None:
    """Print the non-invasive root diagnostic used by operators and tests."""

    import json

    print(
        json.dumps(
            [
                {
                    "root": location.name,
                    "environment_variable": location.environment_variable,
                    "path": str(location.path),
                    "source": location.source,
                    "exists": location.exists,
                }
                for location in root_diagnostic()
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    _main()
