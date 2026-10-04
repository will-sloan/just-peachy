"""Conservative D1/primary permutation bridge. See README_OPTIONAL_REFINER.md."""
from __future__ import annotations

from collections import OrderedDict, deque
import hashlib
import json
import math

from correction import SampleInterval, SpeakerSpan, align_speakers

RATE = 16000
PREFIX = "optional-d1:"


def sample(seconds):
    if type(seconds) not in (float, int) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Finite source timestamp required")
    return round(seconds * RATE)


def exclusive_union(spans):
    """Union duplicate observations; remove conflicting primary-track intervals."""
    edges = {}
    for start, end, track in spans:
        if start < end:
            edges.setdefault(start, []).append((track, 1))
            edges.setdefault(end, []).append((track, -1))
    active, result, previous = {}, [], None
    for position in sorted(edges):
        labels = [key for key, value in active.items() if value > 0]
        if previous is not None and previous < position and len(labels) == 1:
            label = labels[0]
            if result and result[-1][1] == previous and result[-1][2] == label:
                result[-1] = result[-1][0], position, label
            else:
                result.append((previous, position, label))
        for label, delta in edges[position]:
            active[label] = active.get(label, 0) + delta
        previous = position
    return result


class RefinerLabelBridge:
    """No text buffering. Return exact existing S7 label-revision payloads only.

    Input rows must come from the pinned installed S7 snapshot, not untrusted
    external identities. Primary labels are anchors; this bridge's own revisions
    cannot become anchors. D1 silence/overlap never votes for a named identity.
    """
    def __init__(self, session_id, source_id, revision_window_seconds):
        SampleInterval(session_id, source_id, 0, 1).validate()
        if type(revision_window_seconds) is not int or not 1 <= revision_window_seconds <= 300:
            raise ValueError("Bounded revision window required")
        self.session_id, self.source_id = session_id, source_id
        self.window = revision_window_seconds
        self.runs = deque()
        self.next_frame = self.received = self.watermark = self.serial = 0
        self.signatures = OrderedDict()
        self.last_mapping = {}
        self.status = 'waiting_for_d1_evidence'
        self.last_alignment = None

    def append(self, frame_start, masks, received_samples):
        if (type(frame_start) is not int or frame_start != self.next_frame or
                type(masks) is not bytes or len(masks) > 8192 or
                type(received_samples) is not int or received_samples < self.received):
            raise ValueError("Exact contiguous D1 frame/source clock required")
        if frame_start + len(masks) > received_samples // 160 + 1:
            raise ValueError("D1 frames exceed received audio")
        for offset, mask in enumerate(masks):
            start = (frame_start + offset) * 160
            end = min(start + 160, received_samples)
            if end <= start:  # Exact EOF's overhang frame carries no source audio.
                continue
            if self.runs and self.runs[-1][1] == start and self.runs[-1][2] == mask:
                self.runs[-1] = self.runs[-1][0], end, mask
            else:
                self.runs.append((start, end, mask))
        self.next_frame += len(masks)
        self.received = received_samples
        self.advance(max(self.watermark, received_samples))
        if len(self.runs) > self.window * 100 + 2:
            raise ValueError("D1 activity retention capacity exceeded")

    def advance(self, watermark):
        if type(watermark) is not int or watermark < self.watermark:
            raise ValueError("Monotonic committed source watermark required")
        self.watermark = watermark
        floor = max(0, watermark - self.window * RATE)
        while self.runs and self.runs[0][1] <= floor:
            self.runs.popleft()
        if self.runs and self.runs[0][0] < floor:
            _, end, mask = self.runs[0]
            self.runs[0] = floor, end, mask
        for key, (_, end) in list(self.signatures.items()):
            if end <= floor:
                del self.signatures[key]

    def _interval(self, start, end):
        return SampleInterval(self.session_id, self.source_id, start, end)

    def _associate(self, start, end):
        if end <= start or not self.runs or start < self.runs[0][0] or end > self.runs[-1][1]:
            return None
        covered = voiced = 0
        slots = set()
        for left, right, mask in self.runs:
            count = max(0, min(end, right)-max(start, left))
            if not count:
                continue
            covered += count
            if mask and mask & (mask-1):
                return None
            if mask:
                slots.add(str(mask.bit_length()-1))
                voiced += count
        # Same conservative exclusive association as the installed D1 timeline.
        if covered != end-start or len(slots) != 1 or voiced < min(1280, (end-start)/2):
            return None
        return next(iter(slots))

    def revisions(self, rows, *, watermark, now):
        """Read a fresh bounded S7 snapshot; never wait for D1 or create a caption."""
        self.advance(watermark)
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ValueError("Actual monotonic publication time required")
        if len(rows) > 128 or sum(len(row.get("word_spans", [])) for row in rows) > 512:
            self.status = 'abstained_caption_capacity'
            return []  # Capacity is an abstention, never guessed attribution.
        floor = max(0, watermark-self.window*RATE)
        anchors, anonymous = [], {}
        for row in rows:
            if row.get("session_id") != self.session_id:
                raise ValueError("Foreign caption session")
            for segment in row.get("segments", []):
                track, label = segment.get("track_id"), segment.get("anonymous_label")
                if isinstance(track, str) and isinstance(label, str) and 0 < len(label) <= 256:
                    anonymous[track] = label
            for word in row.get("word_spans", []):
                # A prior original identity may remain in speaker_history after
                # our correction. Skip our entries instead of feeding them back.
                history = word.get("speaker_history", [])
                primary = next((h for h in reversed(history) if isinstance(h.get("event_id"), str)
                                and not h["event_id"].startswith(PREFIX)), None)
                if not primary:
                    continue
                track, support = primary.get("track_id"), primary.get("source_evidence_span")
                if (not isinstance(track, str) or not 0 < len(track) <= 128 or
                        not isinstance(support, (list, tuple)) or len(support) != 2 or
                        primary.get("label") in (None, "Unknown", "Pending identity", "Mixed supported / pending")):
                    continue
                start, end = max(floor, sample(support[0])), min(watermark, sample(support[1]))
                if start < end:
                    anchors.append((start, end, track))
        reference = exclusive_union(anchors)
        refinement = [(a, b, str(mask.bit_length()-1)) for a, b, mask in self.runs
                      if mask and not mask & (mask-1)]
        if len(reference) > 512 or len(refinement) > 512 or len({x[2] for x in reference}) > 8:
            self.status = 'abstained_alignment_capacity'
            return []
        mapping = align_speakers([SpeakerSpan(self._interval(a,b),s) for a,b,s in reference],
                                 [SpeakerSpan(self._interval(a,b),s) for a,b,s in refinement])
        self.last_mapping = mapping
        self.status = 'mapped' if mapping else 'waiting_for_unambiguous_primary_mapping'
        evidence = dict(session_id=self.session_id, source_id=self.source_id, sample_rate=RATE,
                        primary_intervals=reference, d1_intervals=refinement, slot_mapping=mapping)
        evidence_raw = json.dumps(evidence, sort_keys=True,separators=(',',':')).encode()
        if len(evidence_raw)>32768:
            self.status='abstained_provenance_capacity'
            return []
        alignment_sha = hashlib.sha256(evidence_raw).hexdigest()
        self.last_alignment = alignment_sha,evidence_raw
        events = []
        for row in rows:
            for word in row.get("word_spans", []):
                start, end = sample(word["source_start_sec"]), sample(word["source_end_sec"])
                seen = word.get("first_seen_monotonic_sec")
                if (start < floor or end > watermark or start >= end or type(seen) not in (int,float)
                        or not math.isfinite(seen) or not 0 <= now-seen < self.window):
                    continue
                slot = self._associate(start, end)
                track = mapping.get(slot)
                if track is None:
                    continue
                history = word.get("speaker_history", [])
                current = history[-1] if history else {}
                # Retain actual primary known-name decisions on an unchanged
                # track. A changed track receives only its existing anonymous ID.
                if current.get("track_id") == track and not str(current.get("event_id", "")).startswith(PREFIX):
                    continue
                label = anonymous.get(track) or track
                key = (word["id"], row.get("text_revision_id"))
                signature = (track, label)
                if self.signatures.get(key, (None,None))[0] == signature:
                    continue
                self.serial += 1
                self.signatures[key] = signature, end
                while len(self.signatures) > 1024:
                    self.signatures.popitem(last=False)
                events.append(dict(event_id=PREFIX+str(self.serial), utterance_id=row["utterance_id"],
                    target_text_revision_id=row["text_revision_id"], target_span_ids=[word["id"]],
                    source_start_sec=start/RATE, source_end_sec=end/RATE,
                    target_source_start_sec=row["source_start_sec"], target_source_end_sec=row["source_end_sec"],
                    latest_label_time=now, available_at_sec=now, identity_version=self.serial,
                    latest_label=label, replacement_tracker_id=track, latest_anonymous_label=label,
                    latest_known_profile_id=None, latest_known_name=None, latest_naming_state="anonymous",
                    evidence_ids=["optional-d1-alignment:"+alignment_sha], association_reason="exclusive_d1_primary_permutation",
                    timing_kind="ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT", changes_raw_words=False,
                    publication_freshness="historical_caption_annotation_only",
                    optional_refiner=dict(profile="current_delayed", local_slot=slot, source_id=self.source_id,
                        start_sample=start, end_sample=end, sample_rate=RATE, alignment_sha256=alignment_sha,
                        alignment_record='optional-refiner/alignment/'+alignment_sha+'.json',
                        token_timing_is_acoustic=False)))
        return events
