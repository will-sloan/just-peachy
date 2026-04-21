"""Conservative transcript normalization helpers for VOiCES."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextNormalizationConfig:
    lowercase: bool = True
    strip_whitespace: bool = True
    collapse_whitespace: bool = True


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str, config: TextNormalizationConfig | None = None) -> str:
    """Return a conservative normalized version of transcript text."""
    cfg = config or TextNormalizationConfig()
    normalized = text
    if cfg.lowercase:
        normalized = normalized.lower()
    if cfg.strip_whitespace:
        normalized = normalized.strip()
    if cfg.collapse_whitespace:
        normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized
