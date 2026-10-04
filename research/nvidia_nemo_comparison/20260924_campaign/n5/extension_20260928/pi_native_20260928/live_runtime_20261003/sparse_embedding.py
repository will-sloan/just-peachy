"""Opt-in scheduling of existing exact clean D1 windows. See README_SPARSE_EMBEDDING.md."""
from collections import deque
import math

from profiles import RuntimeSelection


class SparseCleanTurnSchedule:
    """One engine-thread owner; no model, audio or identity-threshold changes."""
    def __init__(self, timeline, refresh_seconds, emit, *, history_limit=256):
        if type(history_limit) is not int or not 1 <= history_limit <= 4096:
            raise ValueError("Bounded schedule history required")
        if type(refresh_seconds) not in (int, float) or not math.isfinite(refresh_seconds) or not .5 <= refresh_seconds <= 120:
            raise ValueError("Refresh must be from 0.5 to 120 seconds")
        self.timeline = timeline
        self.original = timeline.exclusive_windows
        self.refresh_seconds = float(refresh_seconds)
        self.emit = emit
        self.history = deque(maxlen=history_limit)
        self.considered = {}
        self.queried = {}
        self.runs = {}
        self.pending = {}
        self.counts = dict(considered=0, scheduled=0, skipped=0, evaluated=0)

    def _record(self, event):
        event = dict(event, embedding_schedule="sparse_clean_turn",
                     refresh_seconds=self.refresh_seconds,
                     counters=dict(self.counts), native_qualified=False)
        self.history.append(event)
        self.emit(event)

    @staticmethod
    def _coordinates(candidate):
        if len(candidate) != 4:
            raise ValueError("Expected installed exclusive-window tuple")
        slot, start, end, run_start = candidate
        if type(slot) is not int or not 0 <= slot < 8:
            raise ValueError("Invalid native speaker slot")
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, end, run_start)):
            raise ValueError("Finite source coordinates required")
        if not 0 <= run_start <= start < end or end-start < .5-1e-6 or end-start > 2.+1e-6:
            raise ValueError("Expected genuine 0.5-to-2-second exclusive window")
        return slot, float(start), float(end), float(run_start)

    def exclusive_windows(self, last_query, **kwargs):
        defaults = dict(minimum_sec=.5, hop_sec=.5, maximum_sec=2.)
        if any(k not in defaults or v != defaults[k] for k, v in kwargs.items()):
            raise ValueError("Sparse schedule preserves installed clean-window geometry")
        cursor = dict(self.considered)
        for slot, end in last_query.items():
            if type(slot) is not int or not 0 <= slot < 8 or not math.isfinite(end):
                raise ValueError("Invalid queried source cursor")
            cursor[slot] = max(cursor.get(slot, -math.inf), end)
        floor = max(0., self.timeline.end-self.timeline.reserve_sec)
        self.pending = {key: value for key, value in self.pending.items() if key[2]/16000 >= floor}
        selected = []
        # The installed selector still determines every candidate waveform.
        # A separate considered cursor consumes skipped hops without claiming
        # that an embedding was computed or changing _n2_last_query.
        for candidate in self.original(cursor, **kwargs):
            slot, start, end, run_start = self._coordinates(candidate)
            if end <= self.considered.get(slot, -math.inf)+1e-6:
                continue
            if end > self.timeline.end+1e-6:
                raise ValueError("Embedding candidate is ahead of observed source")
            previous = self.runs.get(slot)
            first = previous is None or run_start > previous["considered_end"]+1e-6
            if first:
                previous = dict(run_start=run_start, considered_end=end, scheduled_end=-math.inf)
                self.runs[slot] = previous
            previous["considered_end"] = end
            self.considered[slot] = end
            self.counts["considered"] += 1
            due = first or end-previous["scheduled_end"] >= self.refresh_seconds-1e-6
            first_sample, last_sample = round(start*16000), round(end*16000)
            event = dict(event="embedding_schedule_decision", status="scheduled" if due else "skipped",
                         model_slot=slot, source_start_sample=first_sample,
                         source_end_sample=last_sample, sample_rate=16000,
                         run_start_sample=round(previous["run_start"]*16000),
                         observed_run_start_sample=round(run_start*16000),
                         source_cursor_sample=round(self.timeline.end*16000),
                         reason="first_eligible_clean_turn" if first else
                                "refresh_due" if due else "refresh_not_due",
                         embedding_computed=False)
            if due:
                if len(self.pending) >= 512:
                    raise RuntimeError("Bounded embedding schedule pending limit reached")
                self.pending[(slot, first_sample, last_sample)] = event
                previous["scheduled_end"] = end
                self.counts["scheduled"] += 1
                selected.append(candidate)
            else:
                self.counts["skipped"] += 1
            self._record(event)
        return selected

    def evaluated(self, payload):
        """Called only after the real engine emits its existing embedding receipt."""
        slot = payload.get("model_slot")
        start, end = payload.get("source_start_sec"), payload.get("source_end_sec")
        if type(slot) is not int or any(type(v) not in (int, float) or not math.isfinite(v) for v in (start, end)):
            raise ValueError("Actual embedding receipt lacks exact source provenance")
        key = (slot, round(start*16000), round(end*16000))
        decision = self.pending.pop(key, None)
        if decision is None:
            raise ValueError("Actual embedding was not scheduled on this source interval")
        if not payload.get("actual_selected_window") or not payload.get("event_id"):
            raise ValueError("Genuine installed embedding receipt required")
        self.queried[slot] = end
        self.counts["evaluated"] += 1
        self._record(dict(event="embedding_schedule_evaluated", status="evaluated",
                          model_slot=slot, source_start_sample=key[1], source_end_sample=key[2],
                          sample_rate=16000, run_start_sample=decision["run_start_sample"],
                          evidence_event_id=payload["event_id"], embedding_computed=True))


def attach_sparse_schedule(engine, emit):
    """Attach after engine.begin and before input starts; emit takes one dict.

    Continuous is a no-op. All successful embedding receipts remain produced
    by the installed engine. The helper records additional schedule provenance.
    """
    selection = RuntimeSelection(**engine.mode_configuration["selection"])
    selection.validate()
    if selection.embedding_schedule == "continuous":
        return None
    if getattr(engine, "_sparse_embedding_schedule", None) is not None:
        raise RuntimeError("Sparse schedule already attached")
    if getattr(engine, "n2_diarization", None) != "D1" or engine._anonymous_native_only():
        raise ValueError("Actual D1 named engine required")
    timeline = engine._n2_timeline
    if timeline.end or engine._n2_last_query:
        raise ValueError("Attach before source processing begins")
    schedule = SparseCleanTurnSchedule(timeline, selection.embedding_refresh_seconds, emit)
    original_emit = engine._emit
    def observed_emit(kind, elapsed, payload):
        result = original_emit(kind, elapsed, payload)
        if kind == "research_embedding":
            schedule.evaluated(payload)
        return result
    timeline.exclusive_windows = schedule.exclusive_windows
    engine._emit = observed_emit
    engine._sparse_embedding_schedule = schedule
    return schedule
