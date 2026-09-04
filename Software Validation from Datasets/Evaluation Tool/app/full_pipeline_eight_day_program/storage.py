"""Durable JSON, hashing, locking, and C:-only path helpers."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import time
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4


class ProgramContractError(RuntimeError):
    """Raised when a program or adapter contract is unsafe or invalid."""


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str):
    from datetime import datetime, timezone

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ProgramContractError(f"Required JSON file is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProgramContractError(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProgramContractError(f"JSON root must be an object: {path}")
    return value


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _atomic_replace_with_retry(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def append_jsonl_durable(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(canonical_json_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_replace_with_retry(source: Path, destination: Path) -> None:
    """Tolerate short Windows sharing/AV holds without weakening atomicity."""

    delays = (0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.0)
    for attempt, delay in enumerate((*delays, 0.0)):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            transient_windows_share = os.name == "nt" and (
                isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {5, 32}
            )
            if not transient_windows_share or attempt >= len(delays):
                raise
            time.sleep(delay)


def expand_tokens(value: str, variables: Mapping[str, str]) -> str:
    expanded = value
    for name, replacement in variables.items():
        expanded = expanded.replace("${" + name + "}", replacement)
    if "${" in expanded:
        raise ProgramContractError(f"Unresolved adapter token in path/command: {expanded}")
    return expanded


def _drive(path: Path) -> str:
    return os.path.splitdrive(str(path))[0].upper()


def resolve_c_only_path(
    value: str | Path,
    *,
    base: Path | None = None,
    must_exist: bool = False,
    label: str = "path",
) -> Path:
    text = str(value).strip()
    if not text:
        raise ProgramContractError(f"{label} is empty")
    candidate = Path(text)
    if not candidate.is_absolute():
        if os.path.splitdrive(text)[0]:
            raise ProgramContractError(
                f"{label} uses an unsafe drive-relative path: {text}"
            )
        if base is None:
            raise ProgramContractError(f"{label} must be absolute: {text}")
        candidate = base / candidate
    try:
        resolved = candidate.resolve(strict=must_exist)
    except OSError as exc:
        raise ProgramContractError(f"Cannot resolve {label} {candidate}: {exc}") from exc
    if _drive(resolved) != "C:":
        raise ProgramContractError(
            f"{label} violates the C:-only contract: {candidate} -> {resolved}"
        )
    # resolve(strict=False) follows every existing ancestor, including Windows junctions.
    # Re-resolve the nearest existing ancestor explicitly so nonexistent leaves cannot
    # disguise a junction to another volume.
    ancestor = candidate
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if ancestor.exists():
        ancestor_resolved = ancestor.resolve(strict=True)
        if _drive(ancestor_resolved) != "C:":
            raise ProgramContractError(
                f"{label} has an ancestor resolving off C: {ancestor} -> {ancestor_resolved}"
            )
    return resolved


def validate_command_paths(argv: Iterable[str], *, base: Path, label: str) -> None:
    for index, token in enumerate(argv):
        if not isinstance(token, str) or not token:
            raise ProgramContractError(f"{label}[{index}] must be a nonempty string")
        if any(character in token for character in ("\x00", "\r", "\n")):
            raise ProgramContractError(f"{label}[{index}] contains a control character")
        path_token = Path(token)
        if path_token.is_absolute():
            resolve_c_only_path(path_token, base=base, label=f"{label}[{index}]")
        for drive in re.findall(r"(?i)([a-z]):[\\/]", token):
            if drive.upper() != "C":
                raise ProgramContractError(
                    f"{label}[{index}] embeds an off-C path: {token}"
                )


def validate_no_off_c_drive_reference(value: str, *, label: str) -> None:
    for drive in re.findall(r"(?i)([a-z]):[\\/]", value):
        if drive.upper() != "C":
            raise ProgramContractError(f"{label} embeds an off-C path: {value}")


def c_drive_free_bytes(path: Path) -> int:
    resolved = resolve_c_only_path(path, must_exist=True, label="free-space probe")
    return int(__import__("shutil").disk_usage(resolved).free)


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
    )
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == 259  # STILL_ACTIVE
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


class ControllerLock:
    """Atomic, restart-aware single-controller lock."""

    def __init__(
        self,
        path: Path,
        *,
        state_path: Path,
        pid_alive: Callable[[int], bool] = pid_is_alive,
    ) -> None:
        self.path = path
        self.state_path = state_path
        self.pid_alive = pid_alive
        self.token = uuid4().hex
        self.owned = False

    def acquire(self) -> dict[str, Any] | None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "full-pipeline-eight-day-controller-lock.v1",
            "token": self.token,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "acquired_at_utc": utc_now(),
            "state_path": str(self.state_path),
        }
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            existing = load_json(self.path)
            existing_pid = int(existing.get("pid", -1))
            if self.pid_alive(existing_pid):
                raise ProgramContractError(
                    f"Another eight-day controller is active (PID {existing_pid}): {self.path}"
                )
            token_text = re.sub(
                r"[^A-Za-z0-9_.-]", "_", str(existing.get("token", "unknown"))
            )[:96]
            archived = self.path.with_name(
                f"controller.lock.stale.{utc_now().replace(':', '').replace('-', '')}.{token_text}"
            )
            _atomic_replace_with_retry(self.path, archived)
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            stale = {"path": str(archived), "previous": existing}
        else:
            stale = None
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        self.owned = True
        return stale

    def heartbeat(self, *, child_pid: int | None = None) -> None:
        if not self.owned:
            return
        current = load_json(self.path)
        if current.get("token") != self.token:
            raise ProgramContractError("Controller lock ownership changed unexpectedly")
        current["heartbeat_at_utc"] = utc_now()
        current["child_pid"] = child_pid
        atomic_write_json(self.path, current)

    def release(self) -> None:
        if not self.owned:
            return
        try:
            current = load_json(self.path)
            if current.get("token") == self.token:
                self.path.unlink()
        finally:
            self.owned = False


class DurableNotifications:
    """Append-only, fsync-backed milestone notifications with deterministic IDs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._known_ids: set[str] = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ProgramContractError(
                        f"Milestone log contains invalid JSONL: {path}: {exc}"
                    ) from exc
                if isinstance(row, dict) and isinstance(row.get("event_id"), str):
                    self._known_ids.add(row["event_id"])

    def write(self, *, event_id: str, event_type: str, fields: Mapping[str, Any]) -> bool:
        if event_id in self._known_ids:
            return False
        row = {
            "schema_version": "full-pipeline-eight-day-milestone.v1",
            "event_id": event_id,
            "event_type": event_type,
            "recorded_at_utc": utc_now(),
            **fields,
        }
        append_jsonl_durable(self.path, row)
        self._known_ids.add(event_id)
        return True
