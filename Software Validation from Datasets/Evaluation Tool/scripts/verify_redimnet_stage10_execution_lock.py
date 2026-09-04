"""Verify the targeted ReDimNet2 Stage 10 execution lock without running inference."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Mapping, Sequence

import yaml


SCHEMA_VERSION = "redimnet-stage10-execution-lock.v1"
TOOL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
DEFAULT_LOCK = (
    TOOL_ROOT
    / "runs"
    / "research_readiness"
    / "redimnet_stage10_execution_lock.json"
)


class ExecutionLockError(RuntimeError):
    """Raised when a locked dependency or execution prerequisite changed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _tree_identity(root: Path) -> tuple[str, int]:
    files = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix.lower() not in {".pyc", ".pyo"}
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    digest = hashlib.sha256()
    total_bytes = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        total_bytes += size
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(_sha256(path).lower().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest().upper(), total_bytes


def _yaml_selection(path: Path, entry: Mapping[str, object]) -> object:
    value: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in entry.get("selector", []):
        if not isinstance(value, Mapping) or str(key) not in value:
            raise ExecutionLockError(f"YAML selector is missing {key!r}: {path}")
        value = value[str(key)]
    match = entry.get("match")
    if match is not None:
        if not isinstance(value, list) or not isinstance(match, Mapping):
            raise ExecutionLockError(f"invalid list selector in execution lock: {path}")
        matches = [
            row
            for row in value
            if isinstance(row, Mapping)
            and all(row.get(str(key)) == expected for key, expected in match.items())
        ]
        if len(matches) != 1:
            raise ExecutionLockError(
                f"YAML list selector expected one match and found {len(matches)}: {path}"
            )
        value = matches[0]
    return value


def _repo_path(relative: str) -> Path:
    candidate = (REPOSITORY_ROOT / Path(relative)).resolve()
    if not candidate.is_relative_to(REPOSITORY_ROOT.resolve()):
        raise ExecutionLockError(f"repository dependency escapes checkout: {relative}")
    return candidate


def _model_path(logical: str) -> Path:
    configured = Path(logical)
    if configured.is_absolute():
        return configured.resolve()
    if configured.parts and configured.parts[0].lower() == "models":
        model_root = Path(
            os.environ.get("JP_MODEL_ROOT", str(REPOSITORY_ROOT / "models"))
        ).expanduser()
        return (model_root / Path(*configured.parts[1:])).resolve()
    return _repo_path(logical)


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _verify_git(lock: Mapping[str, object]) -> tuple[str, list[str]]:
    audited = str(lock["audited_git_sha"])
    if _git("cat-file", "-e", f"{audited}^{{commit}}", check=False).returncode != 0:
        raise ExecutionLockError(f"audited Git commit is unavailable: {audited}")
    if _git("merge-base", "--is-ancestor", audited, "HEAD", check=False).returncode != 0:
        raise ExecutionLockError("audited Git commit is not an ancestor of current HEAD")
    current = _git("rev-parse", "HEAD").stdout.strip()
    warnings: list[str] = []
    if current != audited:
        warnings.append(
            "HEAD is a descendant of the audited SHA; locked scientific dependencies "
            "must still match exactly."
        )
    return current, warnings


def _verify_repository_files(entries: Sequence[Mapping[str, object]]) -> None:
    for entry in entries:
        relative = str(entry["path"])
        path = _repo_path(relative)
        if not path.is_file():
            raise ExecutionLockError(f"locked repository file is missing: {relative}")
        expected_bytes = int(entry["bytes"])
        expected_sha = str(entry["sha256"]).upper()
        if path.stat().st_size != expected_bytes or _sha256(path) != expected_sha:
            raise ExecutionLockError(f"locked repository file changed: {relative}")
        dirty = _git("status", "--porcelain=v1", "--untracked-files=all", "--", relative)
        if dirty.stdout.strip():
            raise ExecutionLockError(f"locked result-affecting file is dirty: {relative}")


def _verify_yaml_selections(
    entries: Sequence[Mapping[str, object]], warnings: list[str]
) -> None:
    for entry in entries:
        relative = str(entry["path"])
        path = _repo_path(relative)
        if not path.is_file():
            raise ExecutionLockError(f"selected YAML dependency is missing: {relative}")
        value = _yaml_selection(path, entry)
        if _canonical_json_sha256(value) != str(entry["sha256"]).upper():
            raise ExecutionLockError(f"locked YAML selection changed: {entry['name']}")
        dirty = _git("status", "--porcelain=v1", "--untracked-files=all", "--", relative)
        if dirty.stdout.strip():
            warnings.append(
                f"{relative} is dirty outside or around a locked selector; the selected "
                f"{entry['name']} mapping still matches."
            )


def _verify_assets(entries: Sequence[Mapping[str, object]]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for entry in entries:
        logical = str(entry["logical_path"])
        path = _model_path(logical)
        kind = str(entry["kind"])
        if kind == "file":
            if not path.is_file():
                raise ExecutionLockError(f"locked model asset is missing: {logical}")
            actual_sha = _sha256(path)
            actual_bytes = path.stat().st_size
        elif kind == "tree":
            if not path.is_dir():
                raise ExecutionLockError(f"locked model source tree is missing: {logical}")
            actual_sha, actual_bytes = _tree_identity(path)
        else:
            raise ExecutionLockError(f"unsupported asset kind in lock: {kind}")
        if actual_sha != str(entry["sha256"]).upper():
            raise ExecutionLockError(f"locked model asset changed: {logical}")
        if actual_bytes != int(entry["bytes"]):
            raise ExecutionLockError(f"locked model asset size changed: {logical}")
        observed[str(entry["name"])] = actual_sha
    return observed


def _verify_manifest(lock: Mapping[str, object]) -> dict[str, object]:
    expected = lock["protocol"]
    if not isinstance(expected, Mapping):
        raise ExecutionLockError("protocol lock must be a mapping")
    root = _repo_path(str(expected["manifest_root"]))
    index_path = root / "speaker_protocol_manifest.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if payload.get("protocol_id") != expected["protocol_id"]:
        raise ExecutionLockError("Stage 10 protocol ID changed")
    if payload.get("benchmark_tier") != "large":
        raise ExecutionLockError("Stage 10 manifest is not the Large tier")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ExecutionLockError("Stage 10 manifest artifact index is invalid")
    for name, raw in artifacts.items():
        if not isinstance(raw, Mapping):
            raise ExecutionLockError(f"Stage 10 artifact entry is invalid: {name}")
        path = (root / str(raw["path"])).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ExecutionLockError(f"Stage 10 artifact is missing: {name}")
        if path.stat().st_size != int(raw["bytes"]):
            raise ExecutionLockError(f"Stage 10 artifact size changed: {name}")
        if _sha256(path) != str(raw["sha256"]).upper():
            raise ExecutionLockError(f"Stage 10 artifact hash changed: {name}")
    return payload


def _verify_environment(entry: Mapping[str, object]) -> dict[str, object]:
    interpreter = _repo_path(str(entry["python"])).resolve()
    if not interpreter.is_file():
        raise ExecutionLockError(f"ReDimNet environment is missing: {interpreter}")
    probe = (
        "import importlib.metadata as m,json,platform; "
        "import torch,torchaudio,numpy,scipy,sklearn,soundfile; "
        "print(json.dumps({'python':platform.python_version(),'packages':{"
        "'torch':torch.__version__,'torchaudio':torchaudio.__version__,"
        "'numpy':numpy.__version__,'scipy':scipy.__version__,"
        "'scikit-learn':sklearn.__version__,'soundfile':soundfile.__version__}}))"
    )
    completed = subprocess.run(
        [str(interpreter), "-c", probe],
        cwd=TOOL_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise ExecutionLockError(
            "ReDimNet environment import failed: "
            + (completed.stderr.strip() or completed.stdout.strip())
        )
    observed = json.loads(completed.stdout)
    if observed.get("python") != entry["python_version"]:
        raise ExecutionLockError("ReDimNet Python version changed")
    if observed.get("packages") != entry["packages"]:
        raise ExecutionLockError("ReDimNet package versions changed")
    return observed


def _verify_backend_identity(expected: Mapping[str, object]) -> dict[str, object]:
    sys.path.insert(0, str(TOOL_ROOT))
    from app.speaker_protocol.contracts import backend_identity

    identity = backend_identity(
        str(expected["component_id"]), int(expected["embedding_dimension"])
    ).to_jsonable()
    for field in (
        "backend_id",
        "environment_profile",
        "model_hash",
        "config_hash",
        "embedding_dimension",
        "identity_hash",
    ):
        if identity.get(field) != expected.get(field):
            raise ExecutionLockError(f"runtime backend identity changed: {field}")
    return identity


def verify(lock_path: Path) -> dict[str, object]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(lock, Mapping) or lock.get("schema_version") != SCHEMA_VERSION:
        raise ExecutionLockError(f"execution lock schema must be {SCHEMA_VERSION}")
    current_sha, warnings = _verify_git(lock)
    _verify_repository_files(lock["dependencies"]["repository_files"])
    _verify_yaml_selections(lock["dependencies"]["yaml_selections"], warnings)
    assets = _verify_assets(lock["assets"])
    manifest = _verify_manifest(lock)
    environment = _verify_environment(lock["environment"])
    identity = _verify_backend_identity(lock["backend"])
    warnings.extend(str(value) for value in lock.get("scope_warnings", []))
    return {
        "schema_version": "redimnet-stage10-execution-lock-verification.v1",
        "valid": True,
        "decision": lock["decision"],
        "audited_git_sha": lock["audited_git_sha"],
        "current_execution_sha": current_sha,
        "protocol_id": manifest["protocol_id"],
        "manifest_sha256": lock["protocol"]["manifest_sha256"],
        "checkpoint_sha256": assets["checkpoint"],
        "source_tree_sha256": assets["official_source_tree"],
        "backend_identity_hash": identity["identity_hash"],
        "environment": environment,
        "warnings": warnings,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args(argv)
    try:
        result = verify(args.lock.resolve())
    except (ExecutionLockError, FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
