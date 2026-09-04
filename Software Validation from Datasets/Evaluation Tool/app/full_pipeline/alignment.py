"""Deterministic causal transcript/speaker alignment and relabelling.

This module operates on timestamped transcript spans.  It deliberately leaves a
span unlabelled when speaker timing cannot be resolved; it never assigns delayed
text to whichever speaker happened to be most recently observed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from typing import Iterable, Mapping, Sequence


ALIGNMENT_UNALIGNED = "unaligned"
ALIGNMENT_ALIGNED = "aligned"
ALIGNMENT_IDENTITY_RELABELLED = "identity_relabelled"
ALIGNMENT_NO_SPEAKER_EVIDENCE = "no_speaker_evidence"
ALIGNMENT_TIMESTAMP_INSUFFICIENT = "timestamp_resolution_insufficient"
ALIGNMENT_AMBIGUOUS = "ambiguous_speaker_overlap"

TIMING_PROVENANCE = {
    "word",
    "segment",
    "accepted_audio_interval",
    "estimated",
    "missing",
}


@dataclass(frozen=True, order=True)
class TimeInterval:
    start_sec: float
    end_sec: float

    def __post_init__(self) -> None:
        _validate_interval(self.start_sec, self.end_sec, "time interval")


@dataclass(frozen=True, order=True)
class SpeakerRegion:
    """One causal anonymous-speaker region on the source-audio clock."""

    start_sec: float
    end_sec: float
    anonymous_speaker_id: str
    speaker_label: str
    source_event_id: str

    def __post_init__(self) -> None:
        _validate_interval(self.start_sec, self.end_sec, "speaker region")
        for name, value in (
            ("anonymous_speaker_id", self.anonymous_speaker_id),
            ("speaker_label", self.speaker_label),
            ("source_event_id", self.source_event_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")


@dataclass(frozen=True)
class TranscriptSpan:
    """Stable transcript span with explicit alignment uncertainty."""

    span_id: str
    text: str
    start_sec: float | None
    end_sec: float | None
    state: str = "provisional"
    timing_provenance: str = "word"
    anonymous_speaker_id: str | None = None
    speaker_label: str | None = None
    alignment_status: str = ALIGNMENT_UNALIGNED
    source_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.span_id.strip():
            raise ValueError("span_id must be non-empty")
        if self.state not in {"provisional", "committed", "final"}:
            raise ValueError("span state must be provisional, committed, or final")
        if self.timing_provenance not in TIMING_PROVENANCE:
            raise ValueError(f"unsupported timing provenance: {self.timing_provenance}")
        if (self.start_sec is None) != (self.end_sec is None):
            raise ValueError("span timestamps must both be present or both be absent")
        if self.start_sec is not None and self.end_sec is not None:
            _validate_interval(self.start_sec, self.end_sec, "transcript span")
        if self.timing_provenance == "missing" and self.start_sec is not None:
            raise ValueError("missing timing provenance requires null timestamps")
        if self.anonymous_speaker_id is None and self.speaker_label is not None:
            raise ValueError("speaker_label requires anonymous_speaker_id")
        if (
            self.anonymous_speaker_id is not None
            and not self.anonymous_speaker_id.strip()
        ):
            raise ValueError("anonymous_speaker_id must be non-empty when present")
        if self.speaker_label is not None and not self.speaker_label.strip():
            raise ValueError("speaker_label must be non-empty when present")
        object.__setattr__(
            self,
            "source_event_ids",
            tuple(
                sorted(
                    {
                        str(value)
                        for value in self.source_event_ids
                        if str(value).strip()
                    }
                )
            ),
        )

    def to_jsonable(self) -> dict[str, object]:
        return {
            "span_id": self.span_id,
            "text": self.text,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "state": self.state,
            "timing_provenance": self.timing_provenance,
            "anonymous_speaker_id": self.anonymous_speaker_id,
            "speaker_label": self.speaker_label,
            "alignment_status": self.alignment_status,
            "source_event_ids": list(self.source_event_ids),
        }


@dataclass(frozen=True)
class TranscriptRevision:
    """One explicit, checksum-bound transcript snapshot transition."""

    transcript_id: str
    revision_id: str
    revision_number: int
    supersedes_revision_id: str | None
    operation: str
    target_span_ids: tuple[str, ...]
    before_snapshot_sha256: str
    after_snapshot_sha256: str
    spans: tuple[TranscriptSpan, ...]
    caused_by_event_ids: tuple[str, ...]
    reason: str
    source_time_sec: float
    uncertain_span_ids: tuple[str, ...]

    def to_jsonable(self) -> dict[str, object]:
        return {
            "transcript_id": self.transcript_id,
            "revision": {
                "revision_id": self.revision_id,
                "revision_number": self.revision_number,
                "supersedes_revision_id": self.supersedes_revision_id,
                "corrected_event_ids": list(self.caused_by_event_ids),
                "reason": self.reason,
            },
            "operation": self.operation,
            "target_span_ids": list(self.target_span_ids),
            "before_snapshot_sha256": self.before_snapshot_sha256,
            "after_snapshot_sha256": self.after_snapshot_sha256,
            "spans": [value.to_jsonable() for value in self.spans],
            "caused_by_event_ids": list(self.caused_by_event_ids),
            "source_time_sec": self.source_time_sec,
            "uncertain_span_ids": list(self.uncertain_span_ids),
        }


def stable_span_id(
    *,
    transcript_id: str,
    source_event_ids: Sequence[str],
    start_sec: float | None,
    end_sec: float | None,
    source_ordinal: int,
) -> str:
    """Build a stable ID that is independent of revisable transcript text."""

    if not transcript_id.strip() or source_ordinal < 0:
        raise ValueError("transcript_id must be non-empty and source_ordinal >= 0")
    payload = {
        "transcript_id": transcript_id,
        "source_event_ids": sorted(set(source_event_ids)),
        "start_sec": start_sec,
        "end_sec": end_sec,
        "source_ordinal": source_ordinal,
    }
    return f"span_{_canonical_sha256(payload)[:20]}"


class TranscriptSpeakerAligner:
    """Maintain deterministic transcript snapshots and causal speaker revisions."""

    def __init__(
        self,
        transcript_id: str,
        spans: Iterable[TranscriptSpan] = (),
    ) -> None:
        if not transcript_id.strip():
            raise ValueError("transcript_id must be non-empty")
        self.transcript_id = transcript_id
        materialized = tuple(sorted(spans, key=_span_sort_key))
        span_ids = [value.span_id for value in materialized]
        if len(span_ids) != len(set(span_ids)):
            raise ValueError("transcript contains duplicate span IDs")
        self._spans: dict[str, TranscriptSpan] = {
            value.span_id: value for value in materialized
        }
        self._revision_number = 0
        self._last_revision_id: str | None = None
        self._last_source_time_sec: float | None = None
        self._sealed_span_ids: set[str] = set()

    @property
    def spans(self) -> tuple[TranscriptSpan, ...]:
        return tuple(sorted(self._spans.values(), key=_span_sort_key))

    @property
    def snapshot_sha256(self) -> str:
        return _snapshot_sha256(self.spans)

    @property
    def revision_number(self) -> int:
        """Return the latest committed transcript revision number."""

        return self._revision_number

    @property
    def last_revision_id(self) -> str | None:
        """Return the latest committed revision identity, if any."""

        return self._last_revision_id

    def append_spans(
        self,
        spans: Iterable[TranscriptSpan],
        *,
        caused_by_event_ids: Sequence[str],
        source_time_sec: float,
    ) -> TranscriptRevision | None:
        """Append new ASR spans with an explicit revision."""

        self._validate_causal_call(caused_by_event_ids, source_time_sec)
        additions = tuple(sorted(spans, key=_span_sort_key))
        if not additions:
            return None
        if len({value.span_id for value in additions}) != len(additions):
            raise ValueError("append contains duplicate span IDs")
        duplicate = sorted(
            value.span_id for value in additions if value.span_id in self._spans
        )
        if duplicate:
            raise ValueError(f"span IDs already exist: {duplicate}")
        updated = dict(self._spans)
        updated.update({value.span_id: value for value in additions})
        return self._commit_revision(
            updated,
            operation="append",
            target_span_ids=[value.span_id for value in additions],
            caused_by_event_ids=caused_by_event_ids,
            reason="asr_span_append",
            source_time_sec=source_time_sec,
        )

    def replace_spans(
        self,
        spans: Iterable[TranscriptSpan],
        *,
        replaced_span_ids: Sequence[str],
        caused_by_event_ids: Sequence[str],
        source_time_sec: float,
        reason: str = "asr_hypothesis_revision",
    ) -> TranscriptRevision | None:
        """Replace one ASR hypothesis without disturbing other utterances.

        Callers provide the exact previous hypothesis span IDs.  This avoids a
        global "latest transcript" overwrite and makes endpoint-separated ASR
        lines independently revisable.
        """

        self._validate_causal_call(caused_by_event_ids, source_time_sec)
        removals = tuple(sorted(set(str(value) for value in replaced_span_ids)))
        additions = tuple(sorted(spans, key=_span_sort_key))
        if len({value.span_id for value in additions}) != len(additions):
            raise ValueError("replacement contains duplicate span IDs")
        unknown = [value for value in removals if value not in self._spans]
        if unknown:
            raise ValueError(f"replacement names unknown span IDs: {unknown}")
        retained = {
            key: value for key, value in self._spans.items() if key not in removals
        }
        collisions = [value.span_id for value in additions if value.span_id in retained]
        if collisions:
            raise ValueError(
                f"replacement span IDs collide with retained spans: {collisions}"
            )
        updated = {**retained, **{value.span_id: value for value in additions}}
        if (
            _snapshot_sha256(tuple(sorted(updated.values(), key=_span_sort_key)))
            == self.snapshot_sha256
        ):
            return None
        return self._commit_revision(
            updated,
            operation="replace",
            target_span_ids=tuple((*removals, *(value.span_id for value in additions))),
            caused_by_event_ids=caused_by_event_ids,
            reason=reason,
            source_time_sec=source_time_sec,
        )

    def align_regions(
        self,
        regions: Sequence[SpeakerRegion],
        *,
        caused_by_event_ids: Sequence[str],
        source_time_sec: float,
    ) -> TranscriptRevision | None:
        """Align spans using overlap on the source clock.

        A span overlapping multiple anonymous speakers remains explicitly
        ambiguous.  Missing timestamps remain explicitly unresolved.
        """

        self._validate_causal_call(caused_by_event_ids, source_time_sec)
        ordered_regions = tuple(sorted(regions))
        for region in ordered_regions:
            if region.end_sec > source_time_sec:
                raise ValueError("speaker region extends beyond the causal source time")
        updated = dict(self._spans)
        targets: list[str] = []
        for span in self.spans:
            if span.span_id in self._sealed_span_ids:
                continue
            replacement = self._aligned_span(span, ordered_regions, source_time_sec)
            if replacement != span:
                updated[span.span_id] = replacement
                targets.append(span.span_id)
        if not targets:
            return None
        return self._commit_revision(
            updated,
            operation="speaker_relabel",
            target_span_ids=targets,
            caused_by_event_ids=caused_by_event_ids,
            reason="timestamp_overlap_alignment",
            source_time_sec=source_time_sec,
        )

    def relabel_identity(
        self,
        *,
        anonymous_speaker_id: str,
        speaker_label: str,
        effective_intervals: Sequence[TimeInterval],
        caused_by_event_ids: Sequence[str],
        source_time_sec: float,
        reason: str = "identity_state_revision",
    ) -> TranscriptRevision | None:
        """Relabel only causally affected spans for one anonymous speaker."""

        if not anonymous_speaker_id.strip() or not speaker_label.strip():
            raise ValueError("anonymous_speaker_id and speaker_label must be non-empty")
        self._validate_causal_call(caused_by_event_ids, source_time_sec)
        intervals = tuple(sorted(effective_intervals))
        if not intervals:
            raise ValueError(
                "identity relabelling requires explicit effective intervals"
            )
        if any(value.end_sec > source_time_sec for value in intervals):
            raise ValueError("effective interval extends beyond the causal source time")
        updated = dict(self._spans)
        targets: list[str] = []
        for span in self.spans:
            if span.span_id in self._sealed_span_ids:
                continue
            if span.anonymous_speaker_id != anonymous_speaker_id:
                continue
            if span.start_sec is None or span.end_sec is None:
                continue
            if span.end_sec > source_time_sec:
                continue
            if not any(
                _overlap(span.start_sec, span.end_sec, value.start_sec, value.end_sec)
                > 0
                for value in intervals
            ):
                continue
            replacement = replace(
                span,
                speaker_label=speaker_label,
                alignment_status=ALIGNMENT_IDENTITY_RELABELLED,
                source_event_ids=tuple((*span.source_event_ids, *caused_by_event_ids)),
            )
            if replacement != span:
                updated[span.span_id] = replacement
                targets.append(span.span_id)
        if not targets:
            return None
        return self._commit_revision(
            updated,
            operation="speaker_relabel",
            target_span_ids=targets,
            caused_by_event_ids=caused_by_event_ids,
            reason=reason,
            source_time_sec=source_time_sec,
        )

    def seal_existing_spans(self) -> tuple[str, ...]:
        """Make the current transcript immutable across an anonymous-memory reset."""

        sealed = tuple(value.span_id for value in self.spans)
        self._sealed_span_ids.update(sealed)
        return sealed

    def seal_spans_ending_at_or_before(self, source_time_sec: float) -> tuple[str, ...]:
        """Bound retroactive correction while preserving readable transcript text."""

        if source_time_sec < 0 or not math.isfinite(source_time_sec):
            raise ValueError("source_time_sec must be finite and >= 0")
        sealed = tuple(
            value.span_id
            for value in self.spans
            if value.end_sec is not None and value.end_sec <= source_time_sec
        )
        self._sealed_span_ids.update(sealed)
        return sealed

    def reset(self) -> None:
        """Delete transcript text/revisions without changing model state."""

        self._spans.clear()
        self._revision_number = 0
        self._last_revision_id = None
        self._last_source_time_sec = None
        self._sealed_span_ids.clear()

    def _aligned_span(
        self,
        span: TranscriptSpan,
        regions: Sequence[SpeakerRegion],
        source_time_sec: float,
    ) -> TranscriptSpan:
        if span.start_sec is None or span.end_sec is None:
            return replace(
                span,
                anonymous_speaker_id=None,
                speaker_label=None,
                alignment_status=ALIGNMENT_TIMESTAMP_INSUFFICIENT,
            )
        if span.end_sec > source_time_sec:
            return span
        overlaps: dict[str, float] = {}
        matched: dict[str, list[SpeakerRegion]] = {}
        for region in regions:
            duration = _overlap(
                span.start_sec, span.end_sec, region.start_sec, region.end_sec
            )
            if duration <= 0:
                continue
            overlaps[region.anonymous_speaker_id] = (
                overlaps.get(region.anonymous_speaker_id, 0.0) + duration
            )
            matched.setdefault(region.anonymous_speaker_id, []).append(region)
        if not overlaps:
            return replace(
                span,
                anonymous_speaker_id=None,
                speaker_label=None,
                alignment_status=ALIGNMENT_NO_SPEAKER_EVIDENCE,
            )
        if len(overlaps) > 1:
            event_ids = tuple(
                event_id
                for speaker_id in sorted(matched)
                for event_id in sorted(
                    {value.source_event_id for value in matched[speaker_id]}
                )
            )
            return replace(
                span,
                anonymous_speaker_id=None,
                speaker_label=None,
                alignment_status=ALIGNMENT_AMBIGUOUS,
                source_event_ids=tuple((*span.source_event_ids, *event_ids)),
            )
        speaker_id = next(iter(overlaps))
        selected_regions = sorted(matched[speaker_id])
        labels = {value.speaker_label for value in selected_regions}
        if len(labels) != 1:
            return replace(
                span,
                anonymous_speaker_id=None,
                speaker_label=None,
                alignment_status=ALIGNMENT_AMBIGUOUS,
                source_event_ids=tuple(
                    (
                        *span.source_event_ids,
                        *(value.source_event_id for value in selected_regions),
                    )
                ),
            )
        return replace(
            span,
            anonymous_speaker_id=speaker_id,
            speaker_label=next(iter(labels)),
            alignment_status=ALIGNMENT_ALIGNED,
            source_event_ids=tuple(
                (
                    *span.source_event_ids,
                    *(value.source_event_id for value in selected_regions),
                )
            ),
        )

    def _commit_revision(
        self,
        updated: Mapping[str, TranscriptSpan],
        *,
        operation: str,
        target_span_ids: Sequence[str],
        caused_by_event_ids: Sequence[str],
        reason: str,
        source_time_sec: float,
    ) -> TranscriptRevision:
        before = self.snapshot_sha256
        new_spans = tuple(sorted(updated.values(), key=_span_sort_key))
        after = _snapshot_sha256(new_spans)
        if before == after:
            raise RuntimeError("attempted to publish a no-op transcript revision")
        revision_number = self._revision_number + 1
        targets = tuple(sorted(set(target_span_ids)))
        causes = tuple(sorted(set(caused_by_event_ids)))
        revision_payload = {
            "transcript_id": self.transcript_id,
            "revision_number": revision_number,
            "supersedes_revision_id": self._last_revision_id,
            "operation": operation,
            "target_span_ids": targets,
            "before_snapshot_sha256": before,
            "after_snapshot_sha256": after,
            "caused_by_event_ids": causes,
            "reason": reason,
            "source_time_sec": source_time_sec,
        }
        revision_id = f"trrev_{_canonical_sha256(revision_payload)[:20]}"
        uncertain = tuple(
            value.span_id
            for value in new_spans
            if value.alignment_status
            in {ALIGNMENT_TIMESTAMP_INSUFFICIENT, ALIGNMENT_AMBIGUOUS}
        )
        revision = TranscriptRevision(
            transcript_id=self.transcript_id,
            revision_id=revision_id,
            revision_number=revision_number,
            supersedes_revision_id=self._last_revision_id,
            operation=operation,
            target_span_ids=targets,
            before_snapshot_sha256=before,
            after_snapshot_sha256=after,
            spans=new_spans,
            caused_by_event_ids=causes,
            reason=reason,
            source_time_sec=source_time_sec,
            uncertain_span_ids=uncertain,
        )
        self._spans = dict(updated)
        self._revision_number = revision_number
        self._last_revision_id = revision_id
        self._last_source_time_sec = source_time_sec
        return revision

    def _validate_causal_call(
        self, caused_by_event_ids: Sequence[str], source_time_sec: float
    ) -> None:
        if source_time_sec < 0 or not math.isfinite(source_time_sec):
            raise ValueError("source_time_sec must be finite and >= 0")
        if (
            self._last_source_time_sec is not None
            and source_time_sec < self._last_source_time_sec
        ):
            raise ValueError(
                "transcript revisions must be monotonic on the source clock"
            )
        causes = [str(value).strip() for value in caused_by_event_ids]
        if not causes or any(not value for value in causes):
            raise ValueError("transcript revision requires causal event IDs")
        if len(causes) != len(set(causes)):
            raise ValueError("causal event IDs must be unique")


def _span_sort_key(span: TranscriptSpan) -> tuple[int, float, float, str]:
    if span.start_sec is None or span.end_sec is None:
        return (1, 0.0, 0.0, span.span_id)
    return (0, span.start_sec, span.end_sec, span.span_id)


def _snapshot_sha256(spans: Sequence[TranscriptSpan]) -> str:
    return _canonical_sha256(
        [value.to_jsonable() for value in sorted(spans, key=_span_sort_key)]
    )


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_interval(start_sec: float, end_sec: float, label: str) -> None:
    if not math.isfinite(start_sec) or not math.isfinite(end_sec):
        raise ValueError(f"{label} timestamps must be finite")
    if start_sec < 0 or end_sec <= start_sec:
        raise ValueError(f"{label} must satisfy 0 <= start < end")


def _overlap(
    left_start: float, left_end: float, right_start: float, right_end: float
) -> float:
    return max(0.0, min(left_end, right_end) - max(left_start, right_start))
