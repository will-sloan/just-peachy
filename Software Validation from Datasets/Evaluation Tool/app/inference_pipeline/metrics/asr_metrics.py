"""ASR benchmark metric helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from app.inference_pipeline.asr.metrics import (
    consecutive_duplicate_token_rate,
    empty_output_rate,
    hallucinated_output_rate,
    repeated_ngram_rate,
    repeated_word_rate,
)
from app.inference_pipeline.asr.base import normalize_text
from app.scoring.wer import compute_wer


@dataclass(frozen=True)
class ASRExample:
    """One qualitative ASR example selected from a benchmark run."""

    recording_id: str
    utt_id: str
    reference_text: str
    hypothesis_text: str
    wer: float | None
    repeated_word_rate: float
    empty_output: bool

    def to_jsonable(self) -> dict[str, object]:
        return {
            "recording_id": self.recording_id,
            "utt_id": self.utt_id,
            "reference_text": self.reference_text,
            "hypothesis_text": self.hypothesis_text,
            "wer": self.wer,
            "repeated_word_rate": self.repeated_word_rate,
            "empty_output": self.empty_output,
        }


def character_error_rate(reference: str, hypothesis: str) -> float | None:
    """Compute a simple normalized character edit distance."""

    reference_norm = normalize_text(reference).replace(" ", "")
    hypothesis_norm = normalize_text(hypothesis).replace(" ", "")
    if not reference_norm:
        return 0.0 if not hypothesis_norm else 1.0
    return _edit_distance(reference_norm, hypothesis_norm) / len(reference_norm)


def aggregate_cer(
    records: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
) -> float | None:
    """Compute aggregate CER over matched prediction rows with references."""

    predictions_by_key = _predictions_by_key(predictions)
    total_distance = 0
    total_reference_chars = 0
    for record in records:
        reference = normalize_text(str(record.get("reference_text") or "")).replace(" ", "")
        if not reference:
            continue
        prediction = predictions_by_key.get(_record_key(record))
        hypothesis = normalize_text(str((prediction or {}).get("text") or "")).replace(" ", "")
        total_distance += _edit_distance(reference, hypothesis)
        total_reference_chars += len(reference)
    if total_reference_chars == 0:
        return None
    return total_distance / total_reference_chars


def aggregate_wer(
    records: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
) -> float | None:
    """Compute aggregate WER over matched prediction rows with references."""

    predictions_by_key = _predictions_by_key(predictions)
    total_errors = 0
    total_reference_words = 0
    for record in records:
        reference = normalize_text(str(record.get("reference_text") or ""))
        if not reference:
            continue
        prediction = predictions_by_key.get(_record_key(record))
        hypothesis = normalize_text(str((prediction or {}).get("text") or ""))
        result = compute_wer(reference, hypothesis)
        total_errors += result.errors
        total_reference_words += result.reference_words
    if total_reference_words == 0:
        return None
    return total_errors / total_reference_words


def prediction_examples(
    records: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
) -> list[ASRExample]:
    """Build deterministic per-record examples for qualitative reporting."""

    predictions_by_key = _predictions_by_key(predictions)
    examples: list[ASRExample] = []
    for record in records:
        prediction = predictions_by_key.get(_record_key(record), {})
        hypothesis = normalize_text(str(prediction.get("text") or ""))
        reference = normalize_text(str(record.get("reference_text") or ""))
        wer = compute_wer(reference, hypothesis).wer if reference else None
        examples.append(
            ASRExample(
                recording_id=str(record.get("recording_id")),
                utt_id=str(record.get("utt_id") or record.get("recording_id")),
                reference_text=reference,
                hypothesis_text=hypothesis,
                wer=wer,
                repeated_word_rate=repeated_word_rate(hypothesis),
                empty_output=not bool(hypothesis),
            )
        )
    return examples


def select_qualitative_examples(examples: Sequence[ASRExample]) -> dict[str, ASRExample | None]:
    """Select best, median, worst, stutter, empty, and hallucination examples."""

    if not examples:
        return {
            "best": None,
            "median": None,
            "worst": None,
            "high_stutter": None,
            "empty_output": None,
            "hallucination": None,
        }
    by_wer = sorted(
        examples,
        key=lambda item: (
            float("inf") if item.wer is None else item.wer,
            item.recording_id,
            item.utt_id,
        ),
    )
    by_stutter = sorted(
        examples,
        key=lambda item: (-item.repeated_word_rate, item.recording_id, item.utt_id),
    )
    empty = next((item for item in examples if item.empty_output), None)
    hallucination = next(
        (
            item
            for item in examples
            if not item.reference_text and bool(item.hypothesis_text)
        ),
        None,
    )
    return {
        "best": by_wer[0],
        "median": by_wer[len(by_wer) // 2],
        "worst": by_wer[-1],
        "high_stutter": by_stutter[0],
        "empty_output": empty,
        "hallucination": hallucination,
    }


def text_quality_metrics(
    outputs: Sequence[str],
    *,
    silence_flags: Sequence[bool] | None = None,
) -> dict[str, float | None]:
    """Return ASR text diagnostic rates."""

    joined = " ".join(outputs)
    return {
        "repeated_word_rate": repeated_word_rate(joined),
        "repeated_ngram_rate": repeated_ngram_rate(joined),
        "consecutive_duplicate_token_rate": consecutive_duplicate_token_rate(joined),
        "empty_output_rate": empty_output_rate(outputs),
        "hallucinated_output_rate": (
            hallucinated_output_rate(outputs, silence_flags=silence_flags)
            if silence_flags is not None
            else None
        ),
    }


def failure_rate(
    *,
    attempted_count: int,
    failed_count: int,
    skipped_count: int,
    invalid_output_count: int,
    empty_output_count: int,
) -> float:
    """Return the fraction of attempted records with unusable output."""

    if attempted_count <= 0:
        return 0.0
    failures = failed_count + skipped_count + invalid_output_count + empty_output_count
    return min(1.0, failures / attempted_count)


def runtime_realtime_factor(runtime_sec: float | None, audio_duration_sec: float | None) -> float | None:
    """Compute runtime real-time factor."""

    if runtime_sec is None or audio_duration_sec is None or audio_duration_sec <= 0:
        return None
    return runtime_sec / audio_duration_sec


def throughput_items_per_sec(written_count: int, runtime_sec: float | None) -> float | None:
    """Compute utterance throughput."""

    if runtime_sec is None or runtime_sec <= 0:
        return None
    return written_count / runtime_sec


def composite_score(
    *,
    wer: float | None,
    realtime_factor: float | None,
    failure_rate_value: float,
    memory_mb: float | None,
) -> float:
    """Rank prototypes by accuracy, speed, reliability, and memory."""

    accuracy_score = 0.5 if wer is None else max(0.0, 1.0 - min(wer, 1.0))
    speed_score = 0.5 if realtime_factor is None else 1.0 / (1.0 + max(0.0, realtime_factor))
    reliability_score = max(0.0, 1.0 - min(failure_rate_value, 1.0))
    memory_score = 0.5 if memory_mb is None else 1.0 / (1.0 + max(0.0, memory_mb) / 1000.0)
    return round(
        100.0
        * (
            0.55 * accuracy_score
            + 0.25 * speed_score
            + 0.15 * reliability_score
            + 0.05 * memory_score
        ),
        4,
    )


def total_audio_duration_sec(records: Sequence[Mapping[str, object]]) -> float:
    """Return best-effort total audio duration from selected records."""

    total = 0.0
    for record in records:
        duration = _record_duration(record)
        if duration is not None:
            total += duration
    return total


def _record_duration(record: Mapping[str, object]) -> float | None:
    start = _optional_float(record.get("start_sec"))
    end = _optional_float(record.get("end_sec"))
    if start is not None and end is not None and end >= start:
        return end - start
    for key in ("duration_sec", "duration_sec_audio", "source_duration_sec"):
        value = _optional_float(record.get(key))
        if value is not None:
            return value
    return None


def _predictions_by_key(
    predictions: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    return {
        (
            str(prediction.get("recording_id")),
            str(prediction.get("utt_id") or prediction.get("recording_id")),
        ): prediction
        for prediction in predictions
    }


def _record_key(record: Mapping[str, object]) -> tuple[str, str]:
    return (
        str(record.get("recording_id")),
        str(record.get("utt_id") or record.get("recording_id")),
    )


def _edit_distance(reference: str, hypothesis: str) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, reference_char in enumerate(reference, start=1):
        current = [i]
        for j, hypothesis_char in enumerate(hypothesis, start=1):
            substitution = previous[j - 1] + (reference_char != hypothesis_char)
            insertion = current[j - 1] + 1
            deletion = previous[j] + 1
            current.append(min(substitution, insertion, deletion))
        previous = current
    return previous[-1]


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
