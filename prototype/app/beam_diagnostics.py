"""Bounded read-only beam telemetry, shared by display and the live adapter.

The live source supplies a serialized, timeout-bounded getter after consent and
route verification. See docs/BEAM_DIAGNOSTICS.md for lifecycle and run commands.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re
import threading
import time
from typing import Callable


FIELD_COUNTS = {
    "AEC_AZIMUTH_VALUES": 4,
    "AEC_SPENERGY_VALUES": 4,
    "AUDIO_MGR_SELECTED_AZIMUTHS": 2,
}
# A stable color identifies a hardware output, never a person or speaker count.
BEAMS = (
    {"id": "focused_1", "label": "Focused 1", "field": "AEC_AZIMUTH_VALUES", "index": 0, "color": "#18a4e0", "radius": 1.0},
    {"id": "focused_2", "label": "Focused 2", "field": "AEC_AZIMUTH_VALUES", "index": 1, "color": "#eb8a23", "radius": .88},
    {"id": "free_running", "label": "Scanning", "field": "AEC_AZIMUTH_VALUES", "index": 2, "color": "#a079dd", "radius": .76},
    {"id": "auto_select", "label": "AEC auto-select", "field": "AEC_AZIMUTH_VALUES", "index": 3, "color": "#31b780", "radius": .64},
    {"id": "processed_output", "label": "Processed output", "field": "AUDIO_MGR_SELECTED_AZIMUTHS", "index": 0, "color": "#e45b82", "radius": .95},
    {"id": "selected_auto", "label": "Selected auto", "field": "AUDIO_MGR_SELECTED_AZIMUTHS", "index": 1, "color": "#8b9562", "radius": .82},
)


def parse_values(command: str, reply: str) -> list[float | None]:
    """Parse official radians replies, retaining unavailable values as None."""
    if command not in FIELD_COUNTS:
        raise ValueError("Unsupported diagnostic getter")
    lines = [line.strip().strip("\x00") for line in reply.splitlines()
             if line.strip().startswith(command + " ")]
    if len(lines) != 1:
        raise ValueError("Missing or ambiguous diagnostic readback: " + command)
    tokens = re.sub(r"\([^)]*\)", "", lines[0][len(command):]).split()
    if len(tokens) != FIELD_COUNTS[command]:
        raise ValueError("Unexpected diagnostic value count: " + command)
    result = []
    for token in tokens:
        value = float(token)
        result.append(value if math.isfinite(value) else None)
    return result


def native_angle_degrees(value: float | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    angle = math.degrees(value)
    # Official text rounds radians. Tolerate only its endpoint print precision.
    if not -0.0001 <= angle <= 180.0001:
        return None
    return min(180.0, max(0.0, angle))


def arrow_tip(angle_deg: float, center_x: float, center_y: float, radius: float) -> tuple[float, float]:
    """Board-frame semicircle: MIC3/0 right, MIC0/180 left, folded 90 up."""
    if isinstance(angle_deg, bool) or not math.isfinite(angle_deg) or not 0 <= angle_deg <= 180:
        raise ValueError("Display angle must be finite and within 0..180 degrees")
    radians = math.radians(angle_deg)
    return center_x + radius * math.cos(radians), center_y - radius * math.sin(radians)


class BeamDiagnostics:
    """Bounded read-only sampling, with constant-size latest state.

    Ordinary rotation uses at most two getter calls/second. Fast mode uses at
    most five three-getter groups/second; each group is explicitly non-atomic.

    read_values(command) must acquire the live HostControl lock, use its bounded
    timeout and suppress unbounded command receipts. No firmware writes occur.
    stop() joins before the owner may restore routing or release the USB lease.
    """
    def __init__(self, read_values: Callable[[str], list[float | None]], *,
                 interval_seconds: float = .5, stale_after_seconds: float = 2.5,
                 clock: Callable[[], float] = time.perf_counter,
                 on_sample=None, fast=False):
        if not math.isfinite(interval_seconds) or interval_seconds < .5:
            raise ValueError("Diagnostic getters are capped at two calls per second")
        if not math.isfinite(stale_after_seconds) or not .5 <= stale_after_seconds <= 10:
            raise ValueError("Diagnostic stale timeout must be 0.5..10 seconds")
        self.read_values = read_values
        self.interval_seconds = float(interval_seconds)
        self.stale_after_seconds = float(stale_after_seconds)
        self.clock = clock
        self.on_sample = on_sample
        self.fast = bool(fast)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.thread: threading.Thread | None = None
        self._state = "IDLE"
        self._error: str | None = None
        self._fields: dict[str, dict] = {}
        self._counts = {"queries": 0, "successful_queries": 0, "invalid_values": 0, "errors": 0}

    def start(self) -> "BeamDiagnostics":
        with self._lock:
            if self.thread is not None or self._state != "IDLE":
                raise RuntimeError("Use a fresh diagnostic worker for each live source")
            self._state = "WAITING"
            self.thread = threading.Thread(target=self._run, name="proto-beam-diagnostics", daemon=True)
            self.thread.start()
        return self

    def _sample(self, command: str) -> None:
        started = self.clock()
        with self._lock:
            self._counts["queries"] += 1
        try:
            values = list(self.read_values(command))
            if len(values) != FIELD_COUNTS[command]:
                raise ValueError("Unexpected diagnostic value count: " + command)
            normalized = [float(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
                          and math.isfinite(value) else None for value in values]
            completed = self.clock()
            with self._lock:
                self._fields[command] = {"values": normalized, "request_started_monotonic_sec": started,
                                         "received_monotonic_sec": completed}
                self._counts["successful_queries"] += 1
                self._counts["invalid_values"] += sum(value is None for value in normalized)
                self._state = "RUNNING"
            if self.on_sample is not None:
                self.on_sample(command, normalized, started, completed)
        except Exception as exc:
            with self._lock:
                self._error = f"{command}: {type(exc).__name__}: {exc}"[:500]
                self._counts["errors"] += 1
                self._state = "UNAVAILABLE"
            self._stop.set()

    def _run(self) -> None:
        fields = tuple(FIELD_COUNTS)
        index = 0
        while not self._stop.is_set():
            cycle_started = self.clock()
            if self.fast:
                # One finite non-atomic group; never poll in the audio callback.
                for command in fields:
                    if self._stop.is_set():
                        break
                    self._sample(command)
            else:
                self._sample(fields[index % len(fields)])
                index += 1
            # Wait after completion. Slow getters cannot cause catch-up bursts.
            delay = max(.02, .2-(self.clock()-cycle_started)) if self.fast else self.interval_seconds
            if self._stop.wait(delay):
                break

    def set_fast(self, enabled):
        self.fast = bool(enabled)

    def stop(self, timeout: float = 10.0) -> bool:
        self._stop.set()
        thread = self.thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        joined = thread is None or not thread.is_alive()
        with self._lock:
            if self._state != "UNAVAILABLE":
                self._state = "STOPPED" if joined else "STOPPING"
        return joined

    def snapshot(self) -> dict:
        now = self.clock()
        with self._lock:
            fields = deepcopy(self._fields)
            state, error, counts = self._state, self._error, dict(self._counts)
        active = state in {"WAITING", "RUNNING"} and not self._stop.is_set()
        for row in fields.values():
            age = now - row["received_monotonic_sec"]
            row.update(age_sec=max(0.0, age), recent=active and 0 <= age <= self.stale_after_seconds)
        arrows = []
        for beam in BEAMS:
            row = fields.get(beam["field"], {})
            value = row.get("values", [None] * FIELD_COUNTS[beam["field"]])[beam["index"]]
            angle = native_angle_degrees(value)
            if row.get("recent") and angle is not None:
                arrows.append({**beam, "angle_deg": angle, "age_sec": row["age_sec"], "scope": "diagnostic_only"})
        return {"state": state, "error": error, "fields": fields, "arrows": arrows,
                "counters": counts, "stale_after_seconds": self.stale_after_seconds,
                "query_interval_seconds": self.interval_seconds,
                "sampling": "bounded groups; at most 5 groups/second" if self.fast else "low-rate diagnostic rotation",
                "timestamp_scope": "host receipt; DSP observation age unknown",
                "angle_frame": "native folded linear 0..180 degrees; MIC3=0, MIC0=180",
                "person_association": "unavailable", "affects_identity_or_asr": False}
