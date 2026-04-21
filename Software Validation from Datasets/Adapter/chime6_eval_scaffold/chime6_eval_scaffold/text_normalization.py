"""Transcript normalization helpers for CHiME-6."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass


@dataclass(frozen=True)
class TextNormalizationConfig:
    lowercase: bool = True
    strip_whitespace: bool = True
    collapse_whitespace: bool = True
    remove_bracketed_events: bool = True
    remove_punctuation: bool = True


_WHITESPACE_RE = re.compile(r"\s+")
_BRACKETED_RE = re.compile(r"\[[^\]]*\]")
_PUNCT_TRANSLATION = str.maketrans("", "", string.punctuation)


def normalize_text(text: str, config: TextNormalizationConfig | None = None) -> str:
    """Return a normalized version of transcript text."""
    cfg = config or TextNormalizationConfig()
    normalized = text

    if cfg.remove_bracketed_events:
        normalized = _BRACKETED_RE.sub(" ", normalized)

    if cfg.lowercase:
        normalized = normalized.lower()

    if cfg.remove_punctuation:
        normalized = normalized.translate(_PUNCT_TRANSLATION)

    if cfg.strip_whitespace:
        normalized = normalized.strip()

    if cfg.collapse_whitespace:
        normalized = _WHITESPACE_RE.sub(" ", normalized)

    return normalized
