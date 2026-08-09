"""Versioned canonical JSON and portable path normalization."""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import math
from pathlib import PurePosixPath, PureWindowsPath
import re
import unicodedata
from typing import Mapping, Sequence


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented by the v1 contract."""


def canonical_json_bytes(value: object) -> bytes:
    """Serialize one JSON value using scenario-canonicalization.v1 rules.

    Mapping keys are NFC-normalized and sorted by Unicode code point. Array
    order is significant and preserved. Integers and floats remain distinct,
    explicit null remains distinct from an absent mapping key, and all strings
    are emitted as UTF-8 without ASCII escaping.
    """

    return _encode(value).encode("utf-8")


def canonical_sha256(value: object) -> str:
    """Return the uppercase SHA-256 of canonical JSON bytes."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


def stable_rank(seed: int, dataset_key: str, source_recording_id: str, utt_id: str) -> str:
    """Return the order-independent Stage 2 selection rank."""

    payload = {
        "dataset_key": dataset_key,
        "seed": seed,
        "source_recording_id": source_recording_id,
        "utterance_id": utt_id,
    }
    return canonical_sha256(payload)


def normalize_project_relative_path(value: str) -> str:
    """Normalize a project-relative Windows or POSIX path to portable POSIX form."""

    text = unicodedata.normalize("NFC", str(value).strip())
    if not text:
        raise CanonicalizationError("project-relative path must be non-empty")
    windows = PureWindowsPath(text)
    if windows.drive or windows.root or text.startswith(("/", "\\")):
        raise CanonicalizationError(f"absolute path is forbidden in public identity: {value!r}")
    normalized = text.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = PurePosixPath(normalized)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise CanonicalizationError(f"unsafe project-relative path: {value!r}")
    return path.as_posix()


def _encode(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _encode_float(value)
    if isinstance(value, str):
        return json.dumps(
            unicodedata.normalize("NFC", value),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    if isinstance(value, (datetime, date)):
        raise CanonicalizationError(
            "timestamps are not permitted in v1 scenario or manifest identity payloads"
        )
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise CanonicalizationError("canonical mapping keys must be strings")
            key = unicodedata.normalize("NFC", raw_key)
            if key in normalized:
                raise CanonicalizationError(
                    f"mapping contains duplicate keys after Unicode normalization: {key!r}"
                )
            normalized[key] = item
        return "{" + ",".join(
            f"{_encode(key)}:{_encode(normalized[key])}" for key in sorted(normalized)
        ) + "}"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    raise CanonicalizationError(f"unsupported canonical value type: {type(value).__name__}")


def _encode_float(value: float) -> str:
    if not math.isfinite(value):
        raise CanonicalizationError("non-finite floats are forbidden")
    if value == 0.0:
        return "0.0"
    text = repr(value).lower()
    if "e" in text:
        mantissa, exponent = text.split("e", 1)
        if "." not in mantissa:
            mantissa += ".0"
        sign = ""
        if exponent.startswith(("+", "-")):
            sign = "-" if exponent[0] == "-" else ""
            exponent = exponent[1:]
        exponent = exponent.lstrip("0") or "0"
        text = f"{mantissa}e{sign}{exponent}"
    elif "." not in text:
        text += ".0"
    if not re.fullmatch(r"-?(?:0|[1-9]\d*)\.\d+(?:e-?\d+)?", text):
        raise CanonicalizationError(f"float cannot be normalized safely: {value!r}")
    return text
