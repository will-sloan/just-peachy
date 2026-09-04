"""Launch the H2 controller with bounded Windows atomic-publication retries.

This is an operational reliability shim, not scientific pipeline logic.  It
only retries ``os.replace`` when Windows reports a transient sharing/access
violation and otherwise preserves the original exception and behavior.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import threading
import time
from typing import NoReturn


SCHEMA = "h2-windows-atomic-publication-policy.v1"
EVENT_SCHEMA = "h2-windows-atomic-publication-event.v1"
RETRYABLE_WINERRORS = frozenset({5, 32, 33})
RETRY_DELAYS_SEC = (0.05, 0.10, 0.20, 0.40, 0.80, 1.60, 2.00, 2.00)
CHILD_POLICY_RELATIVE_PATH = Path("h2_atomic_retry_child") / "sitecustomize.py"
_ORIGINAL_REPLACE = os.replace
_LOG_LOCK = threading.Lock()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_event(event: dict[str, object]) -> None:
    raw_path = os.environ.get("H2_ATOMIC_RETRY_EVENT_LOG", "").strip()
    if not raw_path:
        return
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(
        {"schema_version": EVENT_SCHEMA, "at_utc": _utc_now(), **event}
    ) + b"\n"
    with _LOG_LOCK:
        with path.open("ab") as stream:
            stream.write(payload)
            stream.flush()


def _retrying_replace(source: object, destination: object, *args: object, **kwargs: object) -> None:
    for attempt, delay_sec in enumerate((*RETRY_DELAYS_SEC, None), start=1):
        try:
            _ORIGINAL_REPLACE(source, destination, *args, **kwargs)
            if attempt > 1:
                _append_event(
                    {
                        "status": "RECOVERED",
                        "attempts": attempt,
                        "source": str(source),
                        "destination": str(destination),
                    }
                )
            return
        except PermissionError as exc:
            winerror = getattr(exc, "winerror", None)
            if os.name != "nt" or winerror not in RETRYABLE_WINERRORS or delay_sec is None:
                if attempt > 1:
                    _append_event(
                        {
                            "status": "EXHAUSTED",
                            "attempts": attempt,
                            "winerror": winerror,
                            "source": str(source),
                            "destination": str(destination),
                        }
                    )
                raise
            _append_event(
                {
                    "status": "RETRYING",
                    "attempt": attempt,
                    "delay_sec": delay_sec,
                    "winerror": winerror,
                    "source": str(source),
                    "destination": str(destination),
                }
            )
            time.sleep(delay_sec)


def _write_policy_bytes_atomic(destination: Path, payload: bytes) -> None:
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _configure_child_process_retry(script_path: Path) -> Path:
    """Make the bounded retry policy load in isolated Python workers.

    ``os.replace`` monkeypatches are process-local.  The H2 controller launches
    enrollment and model workers in separate Python interpreters, so the
    operational policy is propagated through a dedicated ``sitecustomize``
    directory on ``PYTHONPATH``.  Child interpreters inherit that environment;
    scientific configuration and payload bytes are unchanged.
    """

    child_policy = script_path.parent / CHILD_POLICY_RELATIVE_PATH
    if not child_policy.is_file():
        raise RuntimeError(f"Windows child atomic-retry policy is missing: {child_policy}")
    policy_directory = str(child_policy.parent.resolve())
    inherited = os.environ.get("PYTHONPATH", "")
    entries = [entry for entry in inherited.split(os.pathsep) if entry]
    normalized = {os.path.normcase(os.path.abspath(entry)) for entry in entries}
    if os.path.normcase(os.path.abspath(policy_directory)) not in normalized:
        os.environ["PYTHONPATH"] = os.pathsep.join([policy_directory, *entries])
    os.environ["H2_ATOMIC_RETRY_CHILD_POLICY_SHA256"] = _sha256_file(child_policy)
    return child_policy


def _install_policy_receipt(script_path: Path, child_policy_path: Path) -> None:
    raw_root = os.environ.get("H2_ATOMIC_RETRY_POLICY_ROOT", "").strip()
    if not raw_root:
        return
    root = Path(raw_root)
    root.mkdir(parents=True, exist_ok=True)
    raw_event_log = os.environ.get("H2_ATOMIC_RETRY_EVENT_LOG", "").strip()
    event_log = Path(raw_event_log) if raw_event_log else None
    if event_log is not None:
        event_log.parent.mkdir(parents=True, exist_ok=True)
        event_log.touch(exist_ok=True)
    core: dict[str, object] = {
        "schema_version": SCHEMA,
        "platform_scope": "Windows only; other platforms use os.replace unchanged",
        "launcher_source": str(script_path),
        "launcher_sha256": _sha256_file(script_path),
        "child_process_propagation": "PYTHONPATH_sitecustomize",
        "child_sitecustomize_source": str(child_policy_path.resolve()),
        "child_sitecustomize_sha256": _sha256_file(child_policy_path),
        "retryable_winerrors": sorted(RETRYABLE_WINERRORS),
        "retry_delays_sec": list(RETRY_DELAYS_SEC),
        "maximum_added_wait_sec": sum(RETRY_DELAYS_SEC),
        "operation_scope": "os.replace only",
        "event_log": str(event_log) if event_log is not None else None,
        "scientific_inference_or_metric_change": False,
        "frozen_runtime_source_tree_change": False,
        "purpose": (
            "Recover transient Windows sharing violations while publishing "
            "validation, progress, status, and other atomic JSON artifacts."
        ),
    }
    document = {**core, "policy_sha256": hashlib.sha256(_canonical_bytes(core)).hexdigest()}
    destination = root / "windows_atomic_publication_policy.json"
    payload = json.dumps(document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    if destination.is_file():
        existing_payload = destination.read_bytes()
        existing = json.loads(existing_payload.decode("utf-8"))
        if existing != document:
            unsigned_existing = dict(existing)
            observed_signature = unsigned_existing.pop("policy_sha256", None)
            expected_signature = hashlib.sha256(
                _canonical_bytes(unsigned_existing)
            ).hexdigest()
            if (
                existing.get("schema_version") != SCHEMA
                or observed_signature != expected_signature
                or existing.get("scientific_inference_or_metric_change") is not False
                or existing.get("frozen_runtime_source_tree_change") is not False
            ):
                raise RuntimeError(
                    "Existing Windows atomic-publication policy is not a valid "
                    "non-scientific predecessor"
                )
            archive = root / "superseded_atomic_publication_policies"
            archive.mkdir(parents=True, exist_ok=True)
            archived = archive / f"windows_atomic_publication_policy.{observed_signature}.json"
            if archived.is_file():
                if archived.read_bytes() != existing_payload:
                    raise RuntimeError("Archived Windows atomic-publication policy differs")
            else:
                _write_policy_bytes_atomic(archived, existing_payload)
            _write_policy_bytes_atomic(destination, payload)
        return
    _write_policy_bytes_atomic(destination, payload)


def main() -> NoReturn:
    script_path = Path(__file__).resolve()
    tool_root = script_path.parent.parent
    if str(tool_root) not in sys.path:
        sys.path.insert(0, str(tool_root))
    if os.name == "nt":
        os.replace = _retrying_replace  # type: ignore[assignment]
    child_policy_path = _configure_child_process_retry(script_path)
    _install_policy_receipt(script_path, child_policy_path)
    runpy.run_module("app.h2_product_program", run_name="__main__", alter_sys=True)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
