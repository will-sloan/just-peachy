"""Text normalization around the learned punctuation model."""

from __future__ import annotations

import re


_SENTENCE_START = re.compile(r"(^|[.!?]\s+)([a-z])")
_STANDALONE_I = re.compile(r"\bi\b")
_QUESTION_START = re.compile(
    r"^(?:who|what|when|where|why|how|is|are|am|was|were|do|does|did|"
    r"can|could|would|will|shall|should|may|might|must|have|has|had)\b",
    re.IGNORECASE,
)


def prepare_for_punctuation(raw_text: str) -> str:
    """Normalize Sherpa's uppercase hypothesis for the punctuation model."""

    text = " ".join(str(raw_text).strip().split())
    if not text:
        return ""
    return text.lower()


def format_partial_display(raw_text: str) -> str:
    """Make unstable partial text readable without guessing punctuation."""

    text = prepare_for_punctuation(raw_text)
    if not text:
        return ""
    text = _SENTENCE_START.sub(
        lambda match: match.group(1) + match.group(2).upper(), text
    )
    text = _STANDALONE_I.sub("I", text)
    return text


def finalize_punctuation_output(restored_text: str, raw_text: str) -> str:
    """Sanitize learned output and guarantee a readable final endpoint.

    The CNN-BiLSTM sometimes leaves a short final chunk unpunctuated. A period
    remains a conservative fallback, but question marks and sentence casing
    now come from the learned model. The preserved raw ASR field is untouched.
    """

    text = " ".join(str(restored_text).strip().split())
    if not text:
        text = format_partial_display(raw_text)
    text = _STANDALONE_I.sub("I", text)
    if text and text[-1] not in ".?!":
        text = text.rstrip(",;:")
        text += "?" if _QUESTION_START.match(prepare_for_punctuation(raw_text)) else "."
    return text


__all__ = [
    "finalize_punctuation_output",
    "format_partial_display",
    "prepare_for_punctuation",
]
