"""Conservative transcript normalization helpers for Hi Fi TTS."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass


@dataclass(frozen=True)
class TextNormalizationConfig:
    lowercase: bool = True
    strip_whitespace: bool = True
    collapse_whitespace: bool = True
    remove_punctuation: bool = False


_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_TRANSLATION = str.maketrans("", "", string.punctuation)


def normalize_text(text: str, config: TextNormalizationConfig | None = None) -> str:
    """Return a conservative normalized version of transcript text.

    For Hi Fi TTS, the manifest already provides `text` and `text_normalized`.
    This helper is mainly used to produce a consistent fallback comparison field.
    """
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
