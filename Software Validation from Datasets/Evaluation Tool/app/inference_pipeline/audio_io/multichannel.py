"""Channel policy handling for model-ready audio."""

from __future__ import annotations

import numpy as np

from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.typing import JsonObject


SUPPORTED_POLICIES = {"mono", "select", "preserve"}
PRESERVE_ALIASES = {"preserve", "preserve_all", "preserve-all"}


def apply_channel_policy(
    audio: np.ndarray,
    policy: str,
    channel_index: int | None = None,
) -> tuple[np.ndarray, JsonObject]:
    """Apply mono, select, or preserve policy to ``(samples, channels)`` audio."""

    if audio.ndim != 2:
        raise ContractValidationError("audio must have shape (samples, channels)")
    source_channels = int(audio.shape[1])
    normalized_policy = normalize_channel_policy(policy)

    if normalized_policy == "mono":
        selected = np.mean(audio, axis=1, keepdims=True).astype(np.float32)
        return selected, {
            "policy": "mono",
            "source_channels": source_channels,
            "output_channels": 1,
        }

    if normalized_policy == "select":
        index = require_channel_index(channel_index, source_channels)
        return audio[:, index : index + 1].astype(np.float32, copy=False), {
            "policy": "select",
            "channel_index": index,
            "source_channels": source_channels,
            "output_channels": 1,
        }

    return audio.astype(np.float32, copy=False), {
        "policy": "preserve",
        "source_channels": source_channels,
        "output_channels": source_channels,
    }


def normalize_channel_policy(policy: str | None) -> str:
    """Return a canonical channel policy name."""

    raw_policy = str(policy or "mono").strip().lower()
    if raw_policy in PRESERVE_ALIASES:
        return "preserve"
    if raw_policy in SUPPORTED_POLICIES:
        return raw_policy
    known = ", ".join(sorted(SUPPORTED_POLICIES))
    raise ContractValidationError(
        f"unsupported channel_policy {policy!r}; expected one of: {known}"
    )


def require_channel_index(channel_index: int | None, source_channels: int) -> int:
    """Validate and return a selected source channel index."""

    if channel_index is None:
        raise ContractValidationError("channel_index is required when channel_policy is 'select'")
    try:
        index = int(channel_index)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("channel_index must be an integer") from exc
    if index < 0:
        raise ContractValidationError("channel_index must be >= 0")
    if index >= source_channels:
        raise ContractValidationError("channel_index must be less than source channel count")
    return index
