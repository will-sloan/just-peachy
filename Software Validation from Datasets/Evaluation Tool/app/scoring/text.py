"""Prediction text normalization for scoring."""

from __future__ import annotations

import re
import string

from app.dataset_registry.registry import TextNormalizationSpec


_PUNCT_TRANSLATION = str.maketrans("", "", string.punctuation)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_for_scoring(text: object, spec: TextNormalizationSpec) -> str:
    """Normalize transcript text according to dataset-specific rules."""

    normalized = "" if text is None else str(text)
    if spec.lowercase:
        normalized = normalized.lower()
    if spec.remove_punctuation:
        normalized = normalized.translate(_PUNCT_TRANSLATION)
    if spec.strip_whitespace:
        normalized = normalized.strip()
    if spec.collapse_whitespace:
        normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized

