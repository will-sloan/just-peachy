"""Bounded speaker-label revisions; text is emitted immediately. See README_PIPELINES.md."""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import asdict, dataclass
from functools import lru_cache
from copy import deepcopy
import hashlib
import json


@dataclass(frozen=True)
class SampleInterval:
    session_id: str
    source_id: str
    start_sample: int
    end_sample: int
    sample_rate: int = 16000

    def validate(self):
        if not all(type(v) is str and 0 < len(v) <= 128 for v in (self.session_id, self.source_id)):
            raise ValueError("Bounded session/source identity required")
        if (type(self.start_sample) is not int or type(self.end_sample) is not int or
                not 0 <= self.start_sample < self.end_sample <= 2**63 - 1 or
                type(self.sample_rate) is not int or not 1 <= self.sample_rate <= 192000):
            raise ValueError("Exact half-open sample interval required")
        return self


@dataclass(frozen=True)
class SpeakerSpan:
    interval: SampleInterval
    speaker: str

    def validate(self):
        self.interval.validate()
        if type(self.speaker) is not str or not 0 < len(self.speaker) <= 128:
            raise ValueError("Bounded producer-local speaker ID required")
        return self


def _overlap(a, b):
    return max(0, min(a.end_sample, b.end_sample) - max(a.start_sample, b.start_sample))


def _identity(interval):
    return interval.session_id, interval.source_id, interval.sample_rate


def align_speakers(reference, refinement, *, minimum_overlap_samples=1280):
    """One-to-one maximum-overlap mapping; tied/weak mappings remain unknown.

    Slots belong to each producer. Identically named slots do not imply identity.
    A bit-mask dynamic program bounds the search to eight labels per producer.
    """
    if type(minimum_overlap_samples) is not int or minimum_overlap_samples < 1:
        raise ValueError("Positive sample evidence floor required")
    if len(reference) > 512 or len(refinement) > 512:
        raise ValueError("Bounded alignment input required")
    all_spans = tuple(reference) + tuple(refinement)
    for span in all_spans:
        span.validate()
    if len({_identity(s.interval) for s in all_spans}) > 1:
        raise ValueError("Cannot align different sessions, sources or sample clocks")
    left = sorted({s.speaker for s in refinement})
    right = sorted({s.speaker for s in reference})
    if len(left) > 8 or len(right) > 8:
        raise ValueError("At most eight slots per producer")
    weights = [[sum(_overlap(a.interval, b.interval) for a in refinement if a.speaker == l
                    for b in reference if b.speaker == r) for r in right] for l in left]

    def solve(forbidden=None):
        @lru_cache(None)
        def walk(row, used):
            if row == len(left):
                return 0, ()
            score, tail = walk(row + 1, used)
            best = score, (-1,) + tail
            for column in range(len(right)):
                if used & (1 << column) or forbidden == (row, column):
                    continue
                score, tail = walk(row + 1, used | (1 << column))
                candidate = score + weights[row][column], (column,) + tail
                if candidate[0] > best[0]:
                    best = candidate
            return best
        return walk(0, 0)

    score, assignment = solve()
    mapping = {}
    for row, column in enumerate(assignment):
        if column < 0 or weights[row][column] < minimum_overlap_samples:
            continue
        # No arbitrary label is chosen when an equally good permutation exists.
        if solve((row, column))[0] == score:
            continue
        total = sum(weights[row])
        if weights[row][column] * 2 <= total:
            continue
        mapping[left[row]] = right[column]
    return mapping


class CaptionLedger:
    """Only recent revisions are resident; consumers upsert by caption_id.

    Source sequences must increase. A retry of a resident identical caption is
    idempotent; an expired sequence is ignored, so eviction cannot duplicate it.
    The caller persists emitted events and clocks the watermark on capture.
    """
    def __init__(self, session_id, source_id, *, sample_rate=16000,
                 revision_window_seconds=30, maximum_captions=256, maximum_spans=512):
        SampleInterval(session_id, source_id, 0, 1, sample_rate).validate()
        if type(revision_window_seconds) is not int or not 1 <= revision_window_seconds <= 300:
            raise ValueError("Revision window must be 1..300 seconds")
        if type(maximum_captions) is not int or not 1 <= maximum_captions <= 4096:
            raise ValueError("Bounded caption capacity required")
        if type(maximum_spans) is not int or not 1 <= maximum_spans <= 512:
            raise ValueError("Bounded span capacity required")
        self.identity = session_id, source_id, sample_rate
        self.window_samples = revision_window_seconds * sample_rate
        self.maximum_captions = maximum_captions
        self.maximum_spans = maximum_spans
        self.captions = OrderedDict()
        self.fast_spans = deque()
        self.watermark = 0
        self.high_sequence = -1
        self.fast_labels = {}
        self.dropped_refinements = self.evicted_captions = 0

    def _check(self, interval):
        interval.validate()
        if _identity(interval) != self.identity:
            raise ValueError("Exact session/source/sample clock mismatch")

    @staticmethod
    def _event(row, kind):
        return {**deepcopy(row), "event": kind}

    def advance(self, latest_sample):
        if type(latest_sample) is not int or not self.watermark <= latest_sample <= 2**63 - 1:
            raise ValueError("Monotonic exact source watermark required")
        self.watermark = latest_sample
        floor = max(0, latest_sample - self.window_samples)
        events = []
        for key, row in list(self.captions.items()):
            if row["interval"]["end_sample"] <= floor:
                row["status"] = "final" if row["status"] == "refined" else "fallback"
                row["revision"] += 1
                events.append(self._event(row, "caption_finalized"))
                del self.captions[key]
        self.fast_spans = deque(s for s in self.fast_spans if s.interval.end_sample > floor)
        return events

    expire = advance

    def add_caption(self, source_sequence, interval, text):
        self._check(interval)
        if type(source_sequence) is not int or source_sequence < 0:
            raise ValueError("Monotonic source caption sequence required")
        if type(text) is not str or len(text) > 8192:
            raise ValueError("Bounded text required")
        caption_id = f"{self.identity[0]}:caption-{source_sequence}"
        if source_sequence <= self.high_sequence:
            old = self.captions.get(caption_id)
            if old and (old["text"] != text or old["interval"] != asdict(interval)):
                raise ValueError("A caption ID cannot be reused for different text/audio")
            return []
        self.high_sequence = source_sequence
        events = self.advance(max(self.watermark, interval.end_sample))
        speaker = self._dominant(interval, self.fast_spans)
        row = dict(caption_id=caption_id, text=text, interval=asdict(interval),
                   speaker=speaker or "unknown", status="provisional", revision=0,
                   provenance={"producer": "fast" if speaker else "asr",
                               "label_scope": "session", "revision_window_samples": self.window_samples})
        if interval.end_sample <= max(0, self.watermark - self.window_samples):
            row["status"] = "fallback"
            events.append(self._event(row, "caption_added"))
            return events
        self.captions[caption_id] = row
        events.append(self._event(row, "caption_added"))
        while len(self.captions) > self.maximum_captions:
            _, oldest = self.captions.popitem(last=False)
            oldest["status"] = "fallback"
            oldest["revision"] += 1
            self.evicted_captions += 1
            events.append(self._event(oldest, "caption_finalized"))
        return events

    @staticmethod
    def _dominant(interval, spans):
        weights = {}
        for span in spans:
            weight = _overlap(interval, span.interval)
            weights[span.speaker] = weights.get(span.speaker, 0) + weight
        ordered = sorted(weights.items(), key=lambda v: (-v[1], v[0]))
        if not ordered or ordered[0][1] * 2 <= interval.end_sample - interval.start_sample:
            return None
        if len(ordered) > 1 and ordered[0][1] == ordered[1][1]:
            return None
        return ordered[0][0]

    def _spans(self, spans):
        if type(spans) not in (list, tuple) or len(spans) > self.maximum_spans:
            raise ValueError("Bounded span batch required")
        for span in spans:
            span.validate()
            self._check(span.interval)
            if span.interval.end_sample > self.watermark:
                raise ValueError("Span exceeds received audio watermark")
        # Disjoint intervals per slot avoid double-counting evidence on retries.
        ordered = sorted(spans, key=lambda s: (s.speaker, s.interval.start_sample))
        for a, b in zip(ordered, ordered[1:]):
            if a.speaker == b.speaker and a.interval.end_sample > b.interval.start_sample:
                raise ValueError("Overlapping evidence for the same producer slot")
        return tuple(spans)

    def apply_fast(self, spans):
        spans = self._spans(spans)
        new_labels = {s.speaker for s in spans} - self.fast_labels.keys()
        if len(self.fast_labels) + len(new_labels) > 8:
            raise ValueError("Eight persistent fast slots maximum")
        for label in sorted(new_labels):
            self.fast_labels[label] = f"speaker-{len(self.fast_labels) + 1}"
        floor = max(0, self.watermark - self.window_samples)
        existing = {(s.speaker, s.interval.start_sample, s.interval.end_sample) for s in self.fast_spans}
        for span in spans:
            canonical = SpeakerSpan(span.interval, self.fast_labels[span.speaker])
            key = canonical.speaker, canonical.interval.start_sample, canonical.interval.end_sample
            if canonical.interval.end_sample > floor and key not in existing:
                # Overlapping re-emissions are refused instead of inflating alignment weight.
                if any(s.speaker == canonical.speaker and _overlap(s.interval, canonical.interval)
                       for s in self.fast_spans):
                    raise ValueError("Fast evidence overlaps an existing interval")
                self.fast_spans.append(canonical)
                existing.add(key)
        while len(self.fast_spans) > self.maximum_spans:
            self.fast_spans.popleft()
        events = []
        for row in self.captions.values():
            if row["status"] != "provisional":
                continue
            speaker = self._dominant(SampleInterval(**row["interval"]), self.fast_spans)
            if speaker and row["speaker"] != speaker:
                row.update(speaker=speaker, revision=row["revision"] + 1,
                           provenance={"producer": "fast", "label_scope": "session"})
                events.append(self._event(row, "caption_revised"))
        return events

    def apply_refinement(self, pass_id, spans):
        if type(pass_id) is not str or not 0 < len(pass_id) <= 128:
            raise ValueError("Independent refinement pass ID required")
        spans = self._spans(spans)
        floor = max(0, self.watermark - self.window_samples)
        active = [s for s in spans if s.interval.start_sample >= floor]
        self.dropped_refinements += len(spans) - len(active)
        mapping = align_speakers(list(self.fast_spans), active,
                                 minimum_overlap_samples=max(1, self.identity[2] * 80 // 1000))
        mapped = [SpeakerSpan(s.interval, mapping[s.speaker]) for s in active if s.speaker in mapping]
        events = []
        alignment = {"slot_mapping": mapping,
                     "reference_intervals": [asdict(s) for s in self.fast_spans],
                     "refinement_intervals": [asdict(s) for s in active]}
        alignment_id = hashlib.sha256(json.dumps(alignment, sort_keys=True,
                                                separators=(",", ":")).encode()).hexdigest()
        for row in self.captions.values():
            interval = SampleInterval(**row["interval"])
            if interval.start_sample < floor:
                continue
            speaker = self._dominant(interval, mapped)
            if speaker is None:
                continue  # Preserve the fast/unknown fallback if late or ambiguous.
            if row["speaker"] == speaker and row["status"] == "refined":
                continue
            evidence = [dict(local_speaker=s.speaker, start_sample=max(interval.start_sample, s.interval.start_sample),
                             end_sample=min(interval.end_sample, s.interval.end_sample))
                        for s in active if mapping.get(s.speaker) == speaker and _overlap(interval, s.interval)]
            row.update(speaker=speaker, status="refined", revision=row["revision"] + 1,
                       provenance={"producer": "refinement", "pass_id": pass_id,
                                   "slot_mapping": mapping, "sample_evidence": evidence,
                                   "alignment_id": alignment_id,
                                   "source_id": self.identity[1], "sample_rate": self.identity[2]})
            events.append(self._event(row, "caption_revised"))
        if events:
            events.insert(0, dict(event="speaker_alignment", alignment_id=alignment_id,
                                 pass_id=pass_id, **alignment))
        return events
