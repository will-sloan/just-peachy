"""Conservative transcript normalization helpers."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass


@dataclass(frozen=True)
class TextNormalizationConfig:
    lowercase: bool = True
    strip_whitespace: bool = True
    collapse_whitespace: bool = True
    remove_punctuation: bool = True


_PUNCT_TRANSLATION = str.maketrans("", "", string.punctuation)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str, config: TextNormalizationConfig | None = None) -> str:
    """Return a conservative normalized version of transcript text."""
    cfg = config or TextNormalizationConfig()

    normalized = text

    if cfg.lowercase:
        normalized = normalized.lower()

    if cfg.remove_punctuation:
        normalized = normalized.translate(_PUNCT_TRANSLATION)

    if cfg.strip_whitespace:
        normalized = normalized.strip()

    if cfg.collapse_whitespace:
        normalized = _WHITESPACE_RE.sub(" ", normalized)

    return normalized


def safe_preview(text: str, max_len: int = 120) -> str:
    """Return a short preview string for logs and readmes."""
    clean = _WHITESPACE_RE.sub(" ", text.strip())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 3] + "..."
