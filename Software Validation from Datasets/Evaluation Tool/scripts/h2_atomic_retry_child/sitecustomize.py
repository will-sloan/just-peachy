"""Propagate bounded Windows ``os.replace`` retries to H2 child workers.

Python imports ``sitecustomize`` during interpreter startup when this directory
is on ``PYTHONPATH``.  The H2 bootstrap adds only this directory, so isolated
enrollment/model workers receive the same operational publication protection
as the controller without changing scientific configuration or payload bytes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time


EVENT_SCHEMA = "h2-windows-atomic-publication-event.v1"
RETRYABLE_WINERRORS = frozenset({5, 32, 33})
RETRY_DELAYS_SEC = (0.05, 0.10, 0.20, 0.40, 0.80, 1.60, 2.00, 2.00)
_ORIGINAL_REPLACE = os.replace


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_event(event: dict[str, object]) -> None:
    raw_path = os.environ.get("H2_ATOMIC_RETRY_EVENT_LOG", "").strip()
    if not raw_path:
        return
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema_version": EVENT_SCHEMA,
        "at_utc": _utc_now(),
        "process_id": os.getpid(),
        "policy_scope": "child_process_sitecustomize",
        **event,
    }
    payload = (
        json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    with path.open("ab") as stream:
        stream.write(payload)
        stream.flush()


def _retrying_replace(
    source: object, destination: object, *args: object, **kwargs: object
) -> None:
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


if os.name == "nt":
    os.replace = _retrying_replace  # type: ignore[assignment]
