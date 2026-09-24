"""Model composition registry, independent of modes, recipes and input taps.

No models or devices are imported/opened. See README_BACKENDS.md.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .mode_policy import MODES, SPATIAL_PARENTS

CONFIG = Path(__file__).resolve().parents[1] / "config" / "backends.json"
CONTRACT = "just-peachy.caption-event.v1"


def manifest_id(composition):
    """Any model/runtime/preprocessing edit creates a different immutable ID."""
    payload = json.dumps(composition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load():
    document = json.loads(CONFIG.read_text(encoding="utf-8"))
    rows = document["backends"]
    seen = set()
    for row in rows:
        if row["manifest_id"] != manifest_id(row["composition"]):
            raise ValueError("Backend manifest content/hash mismatch: " + row["key"])
        if row["manifest_id"] in seen:
            raise ValueError("Duplicate backend manifest ID")
        seen.add(row["manifest_id"])
        # These decisions belong to the common controller, never a model manifest.
        if set(row["composition"]) & {"mode", "recipe", "tap", "selected_ids", "seat_truth", "roster"}:
            raise ValueError("Model manifests cannot contain user intent or scoring truth")
    return rows


_BACKENDS = _load()
BASELINE_BACKEND_ID = next(row["manifest_id"] for row in _BACKENDS if row["key"] == "baseline")


def _entry(backend_id):
    row = next((row for row in _BACKENDS if row["manifest_id"] == backend_id), None)
    if row is None:
        raise ValueError("Unknown backend manifest ID")
    return row


def backend_manifest(backend_id):
    row = _entry(backend_id)
    return {"manifest_id": row["manifest_id"], "composition": deepcopy(row["composition"])}


def backend_catalog():
    """Availability describes this executable; candidate downloads do not enable it."""
    return [dict(deepcopy(row), id=row["manifest_id"], available=row["implemented"],
                 event_contract=CONTRACT, compatible_modes=list(MODES), taps=["O0", "O1"])
            for row in _BACKENDS]


def backend_status(backend_id, mode="caption_only", tap="O0", *, recorded_spatial=False):
    row = _entry(backend_id)
    status = dict(deepcopy(row), id=backend_id, available=row["implemented"],
                  event_contract=CONTRACT, compatible_modes=list(MODES), taps=["O0", "O1"])
    if mode not in MODES:
        status.update(available=False, reason="Unknown logical mode.")
    elif tap not in ("O0", "O1"):
        status.update(available=False, reason="Input tap must be O0 or O1.")
    elif not row["implemented"]:
        status["reason"] = row["reason"]
    elif mode in SPATIAL_PARENTS and not recorded_spatial:
        status.update(available=False, reason="This spatial mode requires matching recorded direction telemetry; none is bound to the source.")
    return status


def require_backend(backend_id, mode="caption_only", tap="O0", *, recorded_spatial=False):
    status = backend_status(backend_id, mode, tap, recorded_spatial=recorded_spatial)
    if not status["available"]:
        raise ValueError(status["label"] + ": " + status["reason"])
    return status
