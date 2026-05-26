"""Lightweight ASR diagnostic metrics."""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from app.inference_pipeline.asr.base import normalize_text


def tokens(text: str) -> list[str]:
    """Return normalized whitespace tokens."""

    return normalize_text(text).split()


def repeated_word_rate(text: str) -> float:
    """Fraction of tokens that repeat a previous token."""

    words = tokens(text)
    if not words:
        return 0.0
    counts = Counter(words)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated / len(words)


def repeated_ngram_rate(text: str, *, n: int = 2) -> float:
    """Fraction of n-grams that repeat a previous n-gram."""

    if n < 1:
        raise ValueError("n must be >= 1")
    words = tokens(text)
    if len(words) < n:
        return 0.0
    ngrams = [tuple(words[index:index + n]) for index in range(len(words) - n + 1)]
    counts = Counter(ngrams)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated / len(ngrams)


def consecutive_duplicate_token_rate(text: str) -> float:
    """Fraction of adjacent token transitions where the token is duplicated."""

    words = tokens(text)
    if len(words) < 2:
        return 0.0
    duplicates = sum(
        1
        for index in range(len(words) - 1)
        if words[index] == words[index + 1]
    )
    return duplicates / (len(words) - 1)


def empty_output_rate(outputs: Sequence[str]) -> float:
    """Fraction of outputs that are empty after normalization."""

    if not outputs:
        return 0.0
    empty = sum(1 for output in outputs if not normalize_text(output))
    return empty / len(outputs)


def hallucinated_output_rate(outputs: Sequence[str], *, silence_flags: Sequence[bool]) -> float:
    """Fraction of silent/noise samples with non-empty output."""

    pairs = list(zip(outputs, silence_flags, strict=False))
    silent_pairs = [(output, is_silent) for output, is_silent in pairs if is_silent]
    if not silent_pairs:
        return 0.0
    hallucinated = sum(1 for output, _is_silent in silent_pairs if normalize_text(output))
    return hallucinated / len(silent_pairs)
