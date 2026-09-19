"""Read-only, persistent official XVF host telemetry with honest host timestamps.

One subprocess executes a finite file of read commands. It is stopped at the
requested duration, or sooner by stop(). Do not run other XVF control commands
until wait() returns: the firmware command queues are shared, not per client.

Each timestamp is when this process receives a complete flushed stdout line.
It is NOT a device sample time, USB request boundary, or atomic multi-field
snapshot. Repeated values are retained; they do not establish DSP freshness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import statistics
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Sequence

DEFAULT_FIELDS = ("AEC_AZIMUTH_VALUES", "AEC_SPENERGY_VALUES")
ALL_FIELDS = DEFAULT_FIELDS + ("AUDIO_MGR_SELECTED_AZIMUTHS",)
FIELD_COUNTS = dict(zip(ALL_FIELDS, (4, 4, 2)))
TIMING_SEMANTICS = (
    "Host complete-line arrival using perf_counter_ns; producer explicitly "
    "flushes replies. No device timestamp, per-request start/end bounds, "
    "atomic multi-field snapshot, fixed-rate guarantee, or freshness inference."
)


def parse_reply(text: str) -> dict | None:
    """Parse the three supported official text replies, preserving raw text."""
    parts = text.strip().split(maxsplit=1)
    if not parts or parts[0] not in FIELD_COUNTS:
        return None
    command = parts[0]
    # TYPE_RADIANS is rendered as '1.45655 (83.45 deg)'; values are radians.
    payload = re.sub(r"\([^)]*\)", "", parts[1] if len(parts) == 2 else "")
    tokens = payload.split()
    values: list[float | None] = []
    finite: list[bool] = []
    error = None
    if len(tokens) != FIELD_COUNTS[command]:
        error = f"Expected {FIELD_COUNTS[command]} values; received {len(tokens)}"
    try:
        for token in tokens:
            value = float(token)
            finite.append(math.isfinite(value))
            values.append(value if math.isfinite(value) else None)
    except ValueError as exc:
        error = str(exc)
    return {
        "command": command,
        "raw_reply": text.rstrip("\r\n"),
        "values": values,
        "finite": finite,
        "parse_ok": error is None,
        "parse_error": error,
        "units": "radians" if "AZIMUTH" in command else "vendor_speech_energy_units",
        "beam_order": (
            ["processed_speaker_doa", "auto_select"]
            if command == "AUDIO_MGR_SELECTED_AZIMUTHS"
            else ["focused_1", "focused_2", "free_running", "auto_select"]
        ),
    }


def _percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    data = sorted(values)
    position = (len(data) - 1) * percent / 100
    lo = math.floor(position)
    hi = math.ceil(position)
    return data[lo] + (data[hi] - data[lo]) * (position - lo)


def summarize_rows(rows: Sequence[dict], fields: Sequence[str]) -> dict:
    output = {}
    for name in fields:
        selected = [row for row in rows if row["command"] == name]
        stamps = [row["host_line_arrival_monotonic_ns"] for row in selected]
        intervals = [(b - a) / 1e9 for a, b in zip(stamps, stamps[1:])]
        output[name] = {
            "count": len(selected),
            "first_host_line_arrival_monotonic_ns": stamps[0] if stamps else None,
            "last_host_line_arrival_monotonic_ns": stamps[-1] if stamps else None,
            "mean_arrival_rate_hz": ((len(stamps) - 1) * 1e9 / (stamps[-1] - stamps[0]))
            if len(stamps) > 1 and stamps[-1] > stamps[0] else None,
            "interval_median_s": statistics.median(intervals) if intervals else None,
            "interval_p95_s": _percentile(intervals, 95),
            "interval_min_s": min(intervals) if intervals else None,
            "interval_max_s": max(intervals) if intervals else None,
            "parse_errors": sum(not row["parse_ok"] for row in selected),
            "nonfinite_values": sum(sum(not value for value in row["finite"]) for row in selected),
        }
    return output


class TelemetryLogger:
    """A finite read-only batch that can be used beside an audio stream.

    start() returns immediately after child launch. stop() is idempotent and
    requests termination without blocking. wait(timeout=5) returns the final
    result, or None if still running. on_row executes on a separate daemon
    dispatcher; use a fast callback (for example queue.put_nowait for a GUI).
    The complete authoritative log is retained even if a UI callback is slow.
    """

    def __init__(self, host: str | Path, output_dir: str | Path,
                 fields: Sequence[str] = DEFAULT_FIELDS, duration_s: float = 30.0,
                 max_queries_per_second_hint: float = 1000.0,
                 on_row: Callable[[dict], None] | None = None):
        self.host = Path(host).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.fields = tuple(fields)
        if not self.fields or len(set(self.fields)) != len(self.fields):
            raise ValueError("Choose one to three distinct telemetry fields")
        if any(name not in ALL_FIELDS for name in self.fields):
            raise ValueError("Only the explicitly supported read-only telemetry fields are allowed")
        if not math.isfinite(duration_s) or not 0 < duration_s <= 3600:
            raise ValueError("duration_s must be finite, positive, and at most 3600")
        if not math.isfinite(max_queries_per_second_hint) or not 1 <= max_queries_per_second_hint <= 10000:
            raise ValueError("Command-file sizing hint must be between 1 and 10000 queries/s")
        self.duration_s = float(duration_s)
        # This sizes a finite input file; it neither sets nor promises a rate.
        self.sets = math.ceil(self.duration_s * max_queries_per_second_hint / len(self.fields)) + 2
        self.on_row = on_row
        self.rows: list[dict] = []
        self.latest: dict[str, dict] = {}
        self.result: dict | None = None
        self._stop = threading.Event()
        self._done = threading.Event()
        self._lock = threading.Lock()
        self._callback_queue: queue.Queue = queue.Queue(maxsize=1000)
        self._callback_end = threading.Event()
        self._errors: list[str] = []
        self._callback_errors: list[str] = []
        self._callback_drops = 0
        self._callback_count = 0
        self._order_errors = 0
        self._unparsed_lines = 0
        self._partial_lines = 0
        self._started = False
        self._stop_reason: str | None = None
        self._process: subprocess.Popen | None = None

    def start(self) -> "TelemetryLogger":
        if self._started:
            raise RuntimeError("Each TelemetryLogger can only be started once")
        self._started = True
        self.output_dir.mkdir(parents=True, exist_ok=False)
        command_file = self.output_dir / "commands.txt"
        with command_file.open("x", encoding="ascii", newline="\n") as stream:
            block = "\n".join(self.fields) + "\n"
            for _ in range(self.sets):
                stream.write(block)
        self.argv = [str(self.host), "-u", "usb", "--execute-command-list", str(command_file)]
        self.start_monotonic_ns = time.perf_counter_ns()
        self.start_utc = datetime.now(timezone.utc).isoformat()
        self.executable_sha256 = None
        self._stderr = (self.output_dir / "stderr.bin").open("xb")
        try:
            self.executable_sha256 = hashlib.sha256(self.host.read_bytes()).hexdigest()
            self._process = subprocess.Popen(
                self.argv, cwd=self.host.parent, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=self._stderr, shell=False, bufsize=0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as exc:
            self._errors.append(f"launch: {exc!r}")
            self._stderr.close()
            (self.output_dir / "stdout.bin").write_bytes(b"")
            (self.output_dir / "received_telemetry.jsonl").write_text("", encoding="utf-8")
            self._finish(None, False, False)
            return self
        self._reader = threading.Thread(target=self._read_stdout, name="xvf-telemetry-reader", daemon=True)
        self._reader.start()
        self._callback_thread = None
        if self.on_row is not None:
            self._callback_thread = threading.Thread(target=self._dispatch_callbacks,
                                                     name="xvf-telemetry-ui", daemon=True)
            self._callback_thread.start()
        self._manager = threading.Thread(target=self._manage, name="xvf-telemetry-manager", daemon=True)
        self._manager.start()
        return self

    def _read_stdout(self) -> None:
        try:
            with (self.output_dir / "stdout.bin").open("xb") as raw_file, \
                 (self.output_dir / "received_telemetry.jsonl").open("x", encoding="utf-8") as jsonl:
                while True:
                    raw = self._process.stdout.readline()
                    if not raw:
                        break
                    stamp = time.perf_counter_ns()
                    raw_file.write(raw)
                    if not raw.endswith(b"\n"):
                        self._partial_lines += 1
                        continue  # Preserve but do not mislabel an interrupted line as a reply.
                    text = raw.decode("utf-8-sig", errors="replace").strip()
                    row = parse_reply(text)
                    if row is None:
                        self._unparsed_lines += 1
                        continue  # Startup and diagnostic lines remain in stdout.bin.
                    index = len(self.rows)
                    expected = self.fields[index % len(self.fields)]
                    in_order = row["command"] == expected
                    self._order_errors += not in_order
                    row.update(sequence=index, host_line_arrival_monotonic_ns=stamp,
                               expected_command=expected, command_order_ok=in_order)
                    jsonl.write(json.dumps(row, allow_nan=False) + "\n")
                    self.rows.append(row)
                    with self._lock:
                        self.latest[row["command"]] = row
                    if self.on_row is not None:
                        try:
                            self._callback_queue.put_nowait(dict(row))
                        except queue.Full:
                            self._callback_drops += 1
        except Exception as exc:
            self._errors.append(f"stdout reader: {exc!r}")
            self._stop.set()

    def _dispatch_callbacks(self) -> None:
        while not self._callback_end.is_set() or not self._callback_queue.empty():
            try:
                row = self._callback_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                self.on_row(row)
                self._callback_count += 1
            except Exception as exc:
                if len(self._callback_errors) < 20:
                    self._callback_errors.append(repr(exc))

    def _manage(self) -> None:
        intended_stop = False
        forced_kill = False
        deadline = self.start_monotonic_ns / 1e9 + self.duration_s
        process = self._process
        try:
            while process.poll() is None:
                remaining = deadline - time.perf_counter()
                if remaining <= 0 or self._stop.is_set():
                    self._stop_reason = self._stop_reason or ("duration_elapsed" if remaining <= 0 else "reader_error")
                    # A terminating signal is expected for a duration-bounded command file.
                    intended_stop = not self._errors
                    try:
                        process.terminate()
                    except OSError:
                        if process.poll() is None:
                            raise
                    break
                self._stop.wait(min(0.02, remaining))
            try:
                code = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                forced_kill = True
                process.kill()
                code = process.wait(timeout=2)
            self._reader.join(timeout=2)
            if self._reader.is_alive():
                self._errors.append("stdout reader did not finish after child exit")
            process.stdout.close()
        except Exception as exc:
            self._errors.append(f"manager: {exc!r}")
            code = process.poll()
        finally:
            if process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=2)
                except Exception as exc:
                    self._errors.append(f"cleanup: {exc!r}")
            self._stderr.close()
            self._callback_end.set()
            if self._callback_thread is not None:
                self._callback_thread.join(timeout=0.5)
            self._finish(code, intended_stop, forced_kill)

    def _finish(self, code: int | None, intended_stop: bool, forced_kill: bool) -> None:
        end = time.perf_counter_ns()
        expected_count = self.sets * len(self.fields)
        per_field = summarize_rows(self.rows, self.fields)
        all_seen = all(per_field[name]["count"] > 0 for name in self.fields)
        prefix_ok = self._order_errors == 0 and len(self.rows) <= expected_count
        stderr_bytes = (self.output_dir / "stderr.bin").stat().st_size
        early_exhaustion = code == 0 and not intended_stop and not self._errors
        good = (not self._errors and all_seen and prefix_ok and not stderr_bytes
                and all(value["parse_errors"] == 0 for value in per_field.values())
                and (intended_stop or code == 0) and not forced_kill and not early_exhaustion)
        self.result = {
            "status": "PASS" if good else "FAIL",
            "argv": self.argv, "fields": list(self.fields), "duration_requested_s": self.duration_s,
            "start_utc": self.start_utc, "start_monotonic_ns": self.start_monotonic_ns,
            "end_monotonic_ns": end, "elapsed_s": (end - self.start_monotonic_ns) / 1e9,
            "exit_code": code, "intended_stop": intended_stop, "stop_reason": self._stop_reason,
            "forced_kill": forced_kill, "errors": list(self._errors),
            "source_executable_sha256": self.executable_sha256,
            "timing_semantics": TIMING_SEMANTICS,
            "planned_command_count": expected_count, "reply_count": len(self.rows),
            "received_prefix_in_order": prefix_ok, "command_order_errors": self._order_errors,
            "complete_command_file_received": prefix_ok and len(self.rows) == expected_count,
            "planned_tail_not_received": max(0, expected_count - len(self.rows)),
            "tail_semantics": "At intentional stop the remaining file tail was not attempted; it is not a count of lost device responses.",
            "early_command_file_exhaustion": early_exhaustion,
            "coverage_note": "Command file exhausted before requested duration; increase sizing hint." if early_exhaustion else None,
            "unparsed_stdout_lines": self._unparsed_lines,
            "incomplete_final_stdout_lines": self._partial_lines,
            "stderr_bytes": stderr_bytes, "per_field": per_field,
            "callback_delivered_count": self._callback_count,
            "callback_queue_drops": self._callback_drops,
            "callback_errors": list(self._callback_errors),
            "callback_log_semantics": "Callbacks are for display; received_telemetry.jsonl is the authoritative complete reply log.",
        }
        try:
            with (self.output_dir / "result.json").open("x", encoding="utf-8") as stream:
                json.dump(self.result, stream, indent=2, allow_nan=False)
        finally:
            self._done.set()

    def stop(self, reason: str = "requested_stop") -> None:
        if not self._done.is_set():
            self._stop_reason = self._stop_reason or reason
            self._stop.set()

    def wait(self, timeout: float = 5.0) -> dict | None:
        if not self._started:
            raise RuntimeError("Call start() before wait()")
        if not 0 <= timeout <= 60:
            raise ValueError("wait timeout must be between zero and 60 seconds")
        return self.result if self._done.wait(timeout) else None

    def snapshot(self) -> dict:
        with self._lock:
            return {name: dict(row) for name, row in self.latest.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_host = Path(__file__).resolve().parents[1] / "tools/xvf321/binary/host_v3.0.0/win32/xvf_host.exe"
    parser.add_argument("--host", type=Path, default=default_host)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--fields", nargs="+", choices=ALL_FIELDS, default=DEFAULT_FIELDS)
    parser.add_argument("--with-selected", action="store_true")
    args = parser.parse_args()
    fields = tuple(args.fields)
    if args.with_selected and ALL_FIELDS[2] not in fields:
        fields += (ALL_FIELDS[2],)
    logger = TelemetryLogger(args.host, args.output, fields, args.seconds).start()
    try:
        while logger.wait(timeout=1) is None:
            pass
    except KeyboardInterrupt:
        logger.stop("keyboard_interrupt")
        if logger.wait(timeout=6) is None:
            raise RuntimeError("Telemetry process did not stop within six seconds")
    print(json.dumps(logger.result, indent=2, allow_nan=False))
    return 0 if logger.result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
