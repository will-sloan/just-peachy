"""Opt-in S7 clocks and bounded asynchronous tracing. See README_RESEARCH_S7.md."""
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import queue
import threading
import time


@dataclass(frozen=True)
class S7Settings:
    schema_version: str = "edge-s7.v1"
    pacing: str = "absolute"
    instrumentation: str = "full"
    mode: str = "M1"
    presentation_enabled: bool = False
    trace_capacity: int = 16384
    availability_clock: str = "modeled"
    ownership_mode: str = "conservative_v1"

    def validate(self):
        if self.schema_version != "edge-s7.v1" or self.pacing not in {"absolute", "relative"}:
            raise ValueError("Unsupported S7 schema/pacing")
        if self.instrumentation not in {"light", "full"} or self.mode not in {f"M{i}" for i in range(8)}:
            raise ValueError("Unsupported S7 instrumentation/mode")
        if self.availability_clock not in {"modeled", "observed"}:
            raise ValueError("Unsupported S7 policy availability clock")
        if self.availability_clock == "observed" and self.pacing != "absolute":
            raise ValueError("Observed policy availability requires absolute source-end pacing")
        if self.ownership_mode not in {"conservative_v1", "supported_prefix_v2"}:
            raise ValueError("Unsupported S7 caption ownership mode")
        if type(self.presentation_enabled) is not bool or type(self.trace_capacity) is not int or not 256 <= self.trace_capacity <= 65536:
            raise ValueError("Invalid S7 bounded settings")
        return self

    def receipt(self):
        return asdict(self)

    @classmethod
    def load(cls, path):
        return cls(**json.loads(Path(path).read_bytes())).validate()


class TraceWriter:
    """No synchronous disk/JSON work in producer/model callbacks; overflow fails the run."""
    def __init__(self, path, session_id, capacity=16384):
        self.path = Path(path)
        self.session_id = session_id
        self.queue = queue.Queue(capacity)
        self.accepted = self.completed = self.overflow = self.max_depth = 0
        self.error = None
        self.closed = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name="edge-s7-trace", daemon=True)
        self.thread.start()

    def record(self, kind, **fields):
        row = {"schema": "edge-s7-clock.v1", "kind": kind, "session_id": self.session_id,
               "monotonic_sec": time.perf_counter(), **fields}
        with self.lock:
            if self.closed or self.error:
                raise RuntimeError("S7 trace closed/failed: " + str(self.error))
            try:
                self.queue.put_nowait(row)
            except queue.Full as exc:
                self.overflow += 1
                self.error = "TRACE_CAPACITY_EXHAUSTED"
                raise RuntimeError("S7 scientific clock trace overflow; run invalid") from exc
            self.accepted += 1
            self.max_depth = max(self.max_depth, self.queue.qsize())

    def _run(self):
        try:
            with self.path.open("x", encoding="utf-8", buffering=65536) as f:
                last_flush = time.perf_counter()
                while True:
                    row = self.queue.get()
                    try:
                        if row is None:
                            break
                        f.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
                        self.completed += 1
                        if time.perf_counter() - last_flush >= 1:
                            f.flush()
                            last_flush = time.perf_counter()
                    finally:
                        self.queue.task_done()
        except BaseException as exc:
            self.error = repr(exc)

    def close(self, timeout=30):
        if not self.closed:
            with self.lock:
                self.closed = True
            self.queue.put(None, timeout=timeout)
            self.thread.join(timeout)
        if self.thread.is_alive() or self.error or self.accepted != self.completed:
            raise RuntimeError("S7 trace failed to close: " + str(self.snapshot()))

    def snapshot(self):
        return {"accepted": self.accepted, "completed": self.completed, "overflow": self.overflow,
                "depth": self.queue.qsize(), "max_depth": self.max_depth, "error": self.error,
                "closed": self.closed, "thread_alive": self.thread.is_alive()}


class AbsolutePacer:
    """Single fixed source epoch; never releases a block before its end deadline."""
    def __init__(self, origin, sample_rate, stop_event, clock=time.perf_counter):
        if not math.isfinite(origin) or sample_rate <= 0:
            raise ValueError("Invalid source clock")
        self.origin, self.sample_rate = origin, sample_rate
        self.stop_event, self.clock = stop_event, clock

    def wait_for_end(self, end_sample):
        deadline = self.origin + end_sample / self.sample_rate
        while not self.stop_event.is_set():
            remaining = deadline - self.clock()
            if remaining <= 0:
                return deadline
            self.stop_event.wait(remaining)
        return None
