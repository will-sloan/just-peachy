"""Cross-process exclusion for full-pipeline campaign controller invocations."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from types import TracebackType


class HostRunLockError(RuntimeError):
    """Raised when another controller invocation owns the host run lock."""


class HostRunLock:
    """Hold one non-blocking OS lock for the lifetime of a controller run.

    A controller invocation may still execute two accuracy jobs in its own
    process.  Excluding a second controller process prevents a resource job
    from overlapping an accuracy job and prevents separate invocations from
    exceeding the host-wide concurrency policy.
    """

    def __init__(self, path: Path, *, measurement_mode: str) -> None:
        self.path = Path(path)
        self.measurement_mode = str(measurement_mode)
        self._handle: object | None = None

    def __enter__(self) -> HostRunLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        handle = self.path.open("r+b")
        try:
            _try_lock(handle)
        except OSError as exc:
            handle.close()
            owner = _read_owner(_owner_path(self.path))
            detail = f"; owner={owner}" if owner else ""
            raise HostRunLockError(
                "another full-pipeline evaluation controller is active on this host"
                f"{detail}"
            ) from exc

        self._handle = handle
        owner = {
            "schema_version": "full-pipeline-host-run-lock.v1",
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "measurement_mode": self.measurement_mode,
        }
        owner_path = _owner_path(self.path)
        temporary = owner_path.with_name(f".{owner_path.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(
                json.dumps(owner, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.replace(temporary, owner_path)
        except Exception:
            temporary.unlink(missing_ok=True)
            self._handle = None
            try:
                _unlock(handle)
            finally:
                handle.close()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            _owner_path(self.path).unlink(missing_ok=True)
            _unlock(handle)
        finally:
            handle.close()


def _read_owner(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _owner_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.owner.json")


def _try_lock(handle: object) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        if handle.read(1) == b"":
            handle.seek(0)
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: object) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
