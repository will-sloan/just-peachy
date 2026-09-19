"""Python lifecycle/UI wrapper for the qualified read-only queued XVF adapter."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

from .telemetry import DEFAULT_FIELDS, TelemetryLogger, summarize_rows


class QueuedTelemetryLogger(TelemetryLogger):
    """Same public lifecycle as TelemetryLogger, with QPC USB transaction bounds.

    This backend accepts the full AEC angle and energy arrays only. Use the
    ordinary official backend when requesting selected-angle telemetry too.
    wait_ready() lets a caller start this process before an audio stream and
    wait for the first successful measurement, avoiding PowerShell startup in
    the audio acquisition interval. Do not issue another XVF command meanwhile.
    """

    def __init__(self, host, output_dir, fields=DEFAULT_FIELDS, duration_s=30.0,
                 max_queries_per_second_hint=1000.0, on_row=None):
        if tuple(fields) != DEFAULT_FIELDS:
            raise ValueError("Queued backend requires the two full AEC angle and energy fields in DEFAULT_FIELDS order")
        super().__init__(host, output_dir, fields, duration_s, max_queries_per_second_hint, on_row)
        self._ready = threading.Event()
        self._stop_monotonic = None
        self._native_result = None

    def start(self):
        if self._started:
            raise RuntimeError("Each logger can only be started once")
        self._started = True
        self.output_dir.mkdir(parents=True, exist_ok=False)
        base = Path(__file__).resolve().parent
        script = base / "experimental_queue/Run-Queued-Telemetry.ps1"
        powershell = Path("C:/Windows/SysWOW64/WindowsPowerShell/v1.0/powershell.exe")
        self.native_dir = self.output_dir / "native"
        self.stop_file = self.output_dir / "stop.request"
        snapshot = self.output_dir / "source"
        snapshot.mkdir()
        for source in (Path(__file__), base / "telemetry.py", script, script.with_name("QueuedTelemetry.cs")):
            shutil.copy2(source, snapshot / source.name)
        self.source_hashes = {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir()}
        self.library_hashes = {name: hashlib.sha256((self.host.parent/name).read_bytes()).hexdigest()
                               for name in ("device_usb.dll", "command_map.dll")}
        self.argv = [str(powershell), "-NoProfile", "-NonInteractive", "-File", str(script),
                     "-OutputDirectory", str(self.native_dir), "-Seconds", str(self.duration_s),
                     "-StopFile", str(self.stop_file)]
        self.start_monotonic_ns = time.perf_counter_ns()
        self.start_utc = datetime.now(timezone.utc).isoformat()
        self.executable_sha256 = hashlib.sha256(powershell.read_bytes()).hexdigest()
        self._stderr = (self.output_dir / "stderr.bin").open("xb")
        try:
            self._process = subprocess.Popen(self.argv, cwd=base.parent, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=self._stderr, shell=False, bufsize=0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as exc:
            self._errors.append(f"launch: {exc!r}")
            self._stderr.close()
            (self.output_dir / "stdout.bin").write_bytes(b"")
            (self.output_dir / "received_telemetry.jsonl").write_text("", encoding="utf-8")
            self._finalize_native(None, False)
            return self
        self._reader = threading.Thread(target=self._read_native, name="xvf-queued-reader", daemon=True)
        self._reader.start()
        self._callback_thread = None
        if self.on_row is not None:
            self._callback_thread = threading.Thread(target=self._dispatch_callbacks, name="xvf-queued-ui", daemon=True)
            self._callback_thread.start()
        self._manager = threading.Thread(target=self._manage_native, name="xvf-queued-manager", daemon=True)
        self._manager.start()
        return self

    def _read_native(self):
        try:
            with (self.output_dir / "stdout.bin").open("xb") as raw_file, \
                 (self.output_dir / "received_telemetry.jsonl").open("x", encoding="utf-8") as jsonl:
                while True:
                    raw = self._process.stdout.readline()
                    if not raw:
                        break
                    arrival = time.perf_counter_ns()
                    raw_file.write(raw)
                    try:
                        native = json.loads(raw.decode("utf-8-sig"))
                    except (ValueError, UnicodeError):
                        self._unparsed_lines += 1
                        continue
                    if native.get("phase") != "measurement" or native.get("command") not in DEFAULT_FIELDS:
                        continue
                    row = dict(native)
                    row.update(sequence=len(self.rows), host_line_arrival_monotonic_ns=arrival,
                               host_response_end_monotonic_ns=native["response_end_monotonic_ns"],
                               raw_reply=raw.decode("utf-8-sig").strip(), parse_ok=True, parse_error=None,
                               timestamp_semantics="Host transaction completion; separate line-arrival stamp retained.")
                    jsonl.write(json.dumps(row, allow_nan=False) + "\n")
                    self.rows.append(row)
                    with self._lock:
                        self.latest[row["command"]] = row
                    self._ready.set()
                    if self.on_row is not None:
                        try:
                            self._callback_queue.put_nowait(dict(row))
                        except queue.Full:
                            self._callback_drops += 1
        except Exception as exc:
            self._errors.append(f"native stdout reader: {exc!r}")
            self.stop("reader_error")

    def _manage_native(self):
        process = self._process
        forced = False
        code = None
        try:
            hard_deadline = self.start_monotonic_ns / 1e9 + self.duration_s + 20
            while process.poll() is None:
                now = time.perf_counter()
                if now > hard_deadline or (self._stop_monotonic is not None and now > self._stop_monotonic + 8):
                    forced = True
                    self._errors.append("Native process exceeded bounded completion; forced termination invalidates capture")
                    process.kill()
                    break
                time.sleep(0.02)
            code = process.wait(timeout=3)
            self._reader.join(timeout=3)
            if self._reader.is_alive():
                self._errors.append("Reader remained alive after process exit")
                return  # No completion signal: callers must not freeze files while a writer is live.
            process.stdout.close()
        except Exception as exc:
            self._errors.append(f"native manager: {exc!r}")
        finally:
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    return  # Completion remains pending; hardware ownership has not been released.
            self._stderr.close()
            self._callback_end.set()
            if self._callback_thread is not None:
                self._callback_thread.join(timeout=0.5)
            if not self._reader.is_alive():
                self._finalize_native(code, forced)

    def _finalize_native(self, code, forced):
        try:
            self._native_result = json.loads((self.native_dir / "result.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            self._errors.append(f"Native result.json was not finalized correctly: {exc!r}")
        inspection_path = self.native_dir / "command_map_inspection.json"
        try:
            inspection = json.loads(inspection_path.read_text(encoding="utf-8-sig"))
            for name, key in (("device_usb.dll", "device_usb_sha256"), ("command_map.dll", "command_map_sha256")):
                if inspection[key] != self.library_hashes[name]:
                    self._errors.append(f"Library hash changed between wrapper and native inspection: {name}")
        except (OSError, ValueError, KeyError) as exc:
            self._errors.append(f"Native library inspection was not finalized correctly: {exc!r}")
        native = self._native_result or {}
        # Summaries based on transaction completion are separately named from
        # Python line-arrival intervals. Do not mix the two clocks' semantics.
        transaction_rows = [dict(row, host_line_arrival_monotonic_ns=row["response_end_monotonic_ns"]) for row in self.rows]
        per_field = summarize_rows(transaction_rows, self.fields)
        for name in self.fields:
            expected = native.get("per_field", {}).get(name, {}).get("count")
            if expected is None or per_field[name]["count"] != expected:
                self._errors.append(f"Native/received reply count mismatch for {name}")
        stderr_bytes = (self.output_dir / "stderr.bin").stat().st_size
        good = (code == 0 and native.get("status") == "PASS" and not self._errors
                and not forced and stderr_bytes == 0)
        self.result = {
            "status": "PASS" if good else "FAIL", "backend": "queued_official_c_transport",
            "argv": self.argv, "fields": list(self.fields), "duration_requested_s": self.duration_s,
            "start_utc": self.start_utc, "start_monotonic_ns": self.start_monotonic_ns,
            "end_monotonic_ns": time.perf_counter_ns(), "exit_code": code, "forced_termination": forced,
            "stop_reason": self._stop_reason, "errors": list(self._errors), "stderr_bytes": stderr_bytes,
            "reply_count": len(self.rows), "per_field": per_field,
            "per_field_interval_basis": "host response completion, not Python stdout line-arrival",
            "host_line_arrival_statistics": summarize_rows(self.rows, self.fields),
            "native_result": native, "native_evidence_directory": str(self.native_dir),
            "source_sha256": self.source_hashes, "official_library_sha256": self.library_hashes,
            "callback_delivered_count": self._callback_count, "callback_queue_drops": self._callback_drops,
            "callback_errors": list(self._callback_errors),
            "timing_semantics": "QPC host USB transaction bounds; no device sample timestamp, frame counter or atomic paired-frame guarantee.",
        }
        try:
            with (self.output_dir / "result.json").open("x", encoding="utf-8") as stream:
                json.dump(self.result, stream, indent=2, allow_nan=False)
        finally:
            self._done.set()

    def stop(self, reason="requested_stop"):
        if self._done.is_set() or self._stop_monotonic is not None:
            return
        self._stop_reason = reason
        self._stop_monotonic = time.perf_counter()
        self._stop.set()
        if self._started:
            self.stop_file.write_text(reason, encoding="utf-8")

    def wait_ready(self, timeout=5.0):
        if not self._started:
            raise RuntimeError("Call start first")
        if not 0 <= timeout <= 60:
            raise ValueError("Ready timeout must be within zero to 60 seconds")
        return self._ready.wait(timeout)


def create_telemetry_logger(host, output_dir, fields=DEFAULT_FIELDS, duration_s=30.0, on_row=None):
    """Fast full-angle/energy default; explicit selected-angle requests use CLI."""
    backend = QueuedTelemetryLogger if tuple(fields) == DEFAULT_FIELDS else TelemetryLogger
    return backend(host, output_dir, fields=fields, duration_s=duration_s, on_row=on_row)
