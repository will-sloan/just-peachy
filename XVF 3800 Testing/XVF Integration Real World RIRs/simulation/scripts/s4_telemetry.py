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

import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from measurement_app.telemetry import ALL_FIELDS, TelemetryLogger, summarize_rows
DEFAULT_FIELDS = ALL_FIELDS


class S4QueuedTelemetryLogger(TelemetryLogger):
    """One physical owner starts this logger while holding the existing XVF lease.

    Same start/wait_ready/stop/wait/rows lifecycle as S3. Three complete arrays,
    nominal 20 Hz each, single persistent official queued transport. All host
    timestamps are availability bounds; internal DSP observation time is unknown.
    """
    def __init__(self, host, output_dir, fields=DEFAULT_FIELDS, duration_s=30.0,
                 rate_hz_per_field=20.0, on_row=None, **kwargs):
        if tuple(fields) != DEFAULT_FIELDS:
            raise ValueError("S4 requires AEC angles, AEC energy and both selected angles in fixed order")
        if not math.isfinite(rate_hz_per_field) or not 1 <= rate_hz_per_field <= 30:
            raise ValueError("Rate must be between 1 and 30 Hz per field")
        super().__init__(host, output_dir, fields, duration_s, 3 * rate_hz_per_field, on_row)
        self.rate_hz_per_field = rate_hz_per_field
        self._ready = threading.Event()
        self._seen_fields = set()
        self._stop_monotonic = None
        self._native_result = None

    def start(self):
        if self._started:
            raise RuntimeError("Each logger can only be started once")
        self._started = True
        self.output_dir.mkdir(parents=True, exist_ok=False)
        base = Path(__file__).resolve().parent
        script = base / "s4_native/Run-S4-Telemetry.ps1"
        powershell = Path("C:/Windows/SysWOW64/WindowsPowerShell/v1.0/powershell.exe")
        self.native_dir = self.output_dir / "native"
        self.stop_file = self.output_dir / "stop.request"
        snapshot = self.output_dir / "source"
        snapshot.mkdir()
        for source in (Path(__file__), ROOT / "measurement_app/telemetry.py", script, script.with_name("S4QueuedTelemetry.cs")):
            shutil.copy2(source, snapshot / source.name)
        self.source_hashes = {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir()}
        self.library_hashes = {name: hashlib.sha256((self.host.parent/name).read_bytes()).hexdigest()
                               for name in ("device_usb.dll", "command_map.dll")}
        self.argv = [str(powershell), "-NoProfile", "-NonInteractive", "-File", str(script),
                     "-OutputDirectory", str(self.native_dir), "-Seconds", str(self.duration_s),
                     "-StopFile", str(self.stop_file), "-DllDirectory", str(self.host.parent),
                     "-RateHz", str(self.rate_hz_per_field)]
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
                 (self.output_dir / "received_telemetry.jsonl").open("x", encoding="utf-8") as jsonl, \
                 (self.output_dir / "normalized_observations.jsonl").open("x", encoding="utf-8") as normalized_jsonl:
                while True:
                    raw = self._process.stdout.readline()
                    if not raw:
                        break
                    arrival = time.perf_counter_ns()
                    raw_file.write(raw)
                    if not raw.endswith(b"\n"):
                        self._errors.append("Incomplete native stdout line retained in stdout.bin")
                        continue
                    try:
                        native = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
                    except (ValueError, UnicodeError):
                        self._unparsed_lines += 1
                        self._errors.append("Invalid native JSON retained in stdout.bin")
                        continue
                    if native.get("phase") != "measurement" or native.get("command") not in DEFAULT_FIELDS:
                        continue
                    row = dict(native)
                    row.update(receipt_sequence=len(self.rows), host_line_arrival_monotonic_ns=arrival,
                               host_response_end_monotonic_ns=native["response_end_monotonic_ns"],
                               raw_reply=raw.decode("utf-8-sig").strip(), parse_ok=True, parse_error=None,
                               timestamp_semantics="Host transaction completion; separate line-arrival stamp retained.")
                    if len(row.get("values", [])) != (2 if row["command"] == DEFAULT_FIELDS[2] else 4):
                        row.update(parse_ok=False, parse_error="Wrong native value count")
                        self._errors.append("Wrong native value count")
                    jsonl.write(json.dumps(row, allow_nan=False) + "\n")
                    normalized_jsonl.write(json.dumps(normalize_observation(row), allow_nan=False) + "\n")
                    self.rows.append(row)
                    with self._lock:
                        self.latest[row["command"]] = row
                    self._seen_fields.add(row["command"])
                    if self._seen_fields == set(self.fields):
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
            "status": "PASS" if good else "FAIL", "backend": "s4_three_field_queued_official_c_transport",
            "requested_rate_hz_per_field": self.rate_hz_per_field,
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


def create_telemetry_logger(host, output_dir, fields=DEFAULT_FIELDS, duration_s=30.0,
                            on_row=None, rate_hz_per_field=20.0):
    return S4QueuedTelemetryLogger(host, output_dir, fields, duration_s,
                                  rate_hz_per_field=rate_hz_per_field, on_row=on_row)


TIMING_TELEMETRY_POLICY = {
    "schema_version": "jp_s4_causal_telemetry_policy_v1",
    "requested_rate_hz_per_field": 20,
    "required_raw_fields": list(DEFAULT_FIELDS),
    "max_receipt_age_s": 0.25,
    "max_transaction_duration_s": 0.25,
    "max_response_to_receipt_s": 0.25,
    "long_gap_s": 0.25,
    "live_primary_field": "AUDIO_MGR_SELECTED_AZIMUTHS",
    "live_primary_value_index": 0,
    "live_fallback": "spatial_unavailable; audio and text continue",
    "selected_index_0_nan": "documented_no_fixed_beam_speech",
    "constant_angle_implies_stale": False,
    "new_reply_proves_new_dsp_frame": False,
    "internal_dsp_observation_time": "unknown_not_exposed",
    "causal_time_basis": "host_line_arrival_monotonic_ns",
    "future_interpolation": False,
    "ground_truth_allowed_in_live_adapter": False,
    "direction_metrics": {
        "first_sector_hit": "first valid matching observation after interval start; pre-existing match recorded separately",
        "sustained_acquisition": "first time with at least 0.5 seconds continuous valid matching causal sector",
        "sustained_duration_s": 0.5,
        "speech_coverage": "valid causal observation duration / scored speech interval duration",
        "sector_occupancy": "matching valid causal duration / scored speech interval duration",
        "off_delay": "first unavailable/no-speech/changed-sector after speech end; right-censor at next speech or observation end",
        "missing_or_wrong_sector_resets_sustained_acquisition": True,
        "never_acquired": "retain null acquisition and censored=true; do not drop the case",
        "manual_5_degree_label_is_scoring_tolerance": False,
    },
    "timelines": ["dry_source_schedule", "rir_retained_preonset_convention", "recaptured_input_samples",
                  "processed_output_samples", "host_telemetry_availability"],
    "rir_preonset_s": 0.05,
    "rir_preonset_is_physical_travel_time": False,
    "callback_map_basis": "exact containing callback after four-mic transport alignment; no future or edge extrapolation",
    "callback_uncertainty": "retained callback block span and inter-callback gap are temporal granularity, not calibrated physical latency bounds",
    "fitted_angle_or_energy_time_shift": False,
}


def normalize_observation(row: dict, policy: dict | None = None) -> dict:
    """Strict causal interchange record with no source/seat/identity arguments."""
    policy = policy or TIMING_TELEMETRY_POLICY
    name = row.get("command")
    counts = dict(zip(DEFAULT_FIELDS, (4, 4, 2)))
    values = row.get("values", [])
    failures = []
    if name not in counts:
        failures.append("unsupported_command")
    if not row.get("parse_ok", True) or not isinstance(values, list) or len(values) != counts.get(name):
        failures.append("invalid_reply_shape")
        values = values if isinstance(values, list) else []
    start = row.get("logical_request_start_monotonic_ns")
    end = row.get("response_end_monotonic_ns")
    receipt = row.get("host_line_arrival_monotonic_ns")
    stamps_valid = all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (start, end, receipt))
    duration = delivery = None
    if not stamps_valid or not start <= end <= receipt:
        failures.append("invalid_or_missing_host_time_bounds")
    else:
        duration, delivery = (end - start) / 1e9, (receipt - end) / 1e9
        if duration > policy["max_transaction_duration_s"]:
            failures.append("late_transaction")
        if delivery > policy["max_response_to_receipt_s"]:
            failures.append("late_line_delivery")
    parsed, reasons = [], []
    native_reasons = row.get("invalid_reasons", [])
    for index, value in enumerate(values):
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        reason = None
        if not numeric:
            # Null without an explicit native NaN reason cannot be labelled as
            # documented no-speech: it could be an invalid/failed decoded value.
            reason = native_reasons[index] if index < len(native_reasons) and native_reasons[index] else "missing_or_nonfinite_value"
        elif "AZIMUTH" in str(name) and not -1e-6 <= value <= math.pi + 1e-6:
            reason = "native_angle_out_of_range"
        elif name == "AEC_SPENERGY_VALUES" and value < 0:
            reason = "negative_energy"
        parsed.append(float(value) if numeric else None)
        reasons.append(reason)
    return {
        "schema_version": "jp_s4_causal_observation_v1", "command": name,
        "sequence": row.get("sequence"), "receipt_sequence": row.get("receipt_sequence"),
        "values": parsed, "value_invalid_reasons": reasons,
        "value_valid": [reason is None and not failures for reason in reasons],
        "transaction_valid": not failures, "transaction_invalid_reasons": failures,
        "request_start_monotonic_ns": start, "response_end_monotonic_ns": end,
        "available_monotonic_ns": receipt, "transaction_duration_s": duration,
        "response_to_receipt_s": delivery, "units": row.get("units"),
        "raw_reply": row.get("raw_reply"), "raw_response_base64": row.get("raw_response_base64"),
        "dsp_observation_monotonic_ns": None, "dsp_freshness": "unknown_not_exposed",
        "same_device_frame_proven": False,
    }


class CausalSpatialReader:
    """Receive raw observations, query at host time; never consult scene truth.

    All raw fields remain available for qualified diagnostics. Default selected
    processed DoA is exposed only when transaction, value and age are usable.
    A newer invalid reply masks an older valid one. Holding the same valid angle
    is permitted until the explicit age limit; it does not prove DSP freshness.
    """
    def __init__(self, policy=None):
        self.policy = dict(policy or TIMING_TELEMETRY_POLICY)
        self.rows = []

    def ingest(self, row):
        normalized = normalize_observation(row, self.policy)
        self.rows.append(normalized)
        return normalized

    def at(self, now_ns):
        if not isinstance(now_ns, int) or now_ns < 0:
            raise ValueError("Decision time must be a nonnegative host monotonic integer")
        latest = {}
        for row in self.rows:
            receipt = row["available_monotonic_ns"]
            if isinstance(receipt, int) and receipt <= now_ns:
                old = latest.get(row["command"])
                if old is None or receipt >= old["available_monotonic_ns"]:
                    latest[row["command"]] = row
        fields = {}
        for name in DEFAULT_FIELDS:
            row = latest.get(name)
            if row is None:
                fields[name] = {"state": "missing", "available": False, "values": [], "value_valid": []}
                continue
            age = (now_ns - row["available_monotonic_ns"]) / 1e9
            fresh = age <= self.policy["max_receipt_age_s"]
            valid = [v and fresh for v in row["value_valid"]]
            fields[name] = {**row, "receipt_age_s": age, "transaction_fresh": fresh,
                            "available": any(valid), "value_valid": valid,
                            "state": "available" if any(valid) else "age_gap" if not fresh else "invalid_or_no_speech"}
        primary = fields[self.policy["live_primary_field"]]
        index = self.policy["live_primary_value_index"]
        available = len(primary["value_valid"]) > index and primary["value_valid"][index]
        angle = math.degrees(primary["values"][index]) if available else None
        return {"decision_monotonic_ns": now_ns, "spatial_state": "available" if available else "spatial_unavailable",
                "native_angle_deg": angle, "fields": fields, "audio_text_allowed": True,
                "dsp_freshness": "unknown_not_exposed", "beam_id_is_person_id": False}


class CallbackAvailabilityMap:
    """Exact frame-to-containing-callback lookup without edge clamping.

    A packed logical frame needs all three native frames, hence the +2 in
    decoded/source methods. Host callback completion is availability evidence,
    not a claim about acoustic emission or internal DSP observation time.
    """
    def __init__(self, callback_times, startup_native_frames=0, capture_minus_source_offset_samples=0):
        self.callbacks = list(callback_times)
        self.startup = int(startup_native_frames)
        self.offset = int(capture_minus_source_offset_samples)
        previous_end = None
        previous_time = None
        for row in self.callbacks:
            start, frames, stamp = row["first_native_frame"], row["frames"], row["host_callback_monotonic_ns"]
            if frames <= 0 or start < 0 or (previous_end is not None and start != previous_end):
                raise ValueError("Callback sample ranges are not positive and contiguous")
            if previous_time is not None and stamp < previous_time:
                raise ValueError("Callback host times decrease")
            previous_end, previous_time = start + frames, stamp

    def native_frame(self, frame):
        for i, row in enumerate(self.callbacks):
            if row["first_native_frame"] <= frame < row["first_native_frame"] + row["frames"]:
                gap = None if i == 0 else (row["host_callback_monotonic_ns"] - self.callbacks[i - 1]["host_callback_monotonic_ns"]) / 1e9
                return {"available": True, "native_frame": frame, "callback_index": i,
                        "available_monotonic_ns": row["host_callback_monotonic_ns"],
                        "within_callback_block_span_s": row["frames"] / 48000,
                        "preceding_callback_gap_s": gap, "device_or_acoustic_time_ns": None,
                        "timing_semantics": "containing callback completion; intra-block chronology unresolved"}
        return {"available": False, "native_frame": frame, "available_monotonic_ns": None,
                "reason": "outside_recorded_callback_ranges"}

    def decoded_sample(self, sample):
        return self.native_frame(self.startup + 3 * sample + 2)

    def recaptured_source_sample(self, sample):
        return self.decoded_sample(sample + self.offset)

    def written_source_sample(self, sample):
        return self.native_frame(3 * sample + 2)

    def processed_source_sample(self, sample, measured_relative_delay_samples):
        result = self.decoded_sample(sample + self.offset + measured_relative_delay_samples)
        result["relative_processed_delay_samples"] = measured_relative_delay_samples
        result["delay_is_absolute_device_latency"] = False
        return result


def main():
    """Offline normalization only; physical lifetime belongs to S4 owner."""
    import argparse
    parser = argparse.ArgumentParser(description="Normalize existing S4 raw telemetry offline; never opens hardware")
    parser.add_argument("--normalize-input", type=Path, required=True)
    parser.add_argument("--normalized-output", type=Path, required=True)
    args = parser.parse_args()
    count = 0
    with args.normalize_input.open(encoding="utf-8-sig") as source, args.normalized_output.open("x", encoding="utf-8") as output:
        for line in source:
            row = json.loads(line, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
            output.write(json.dumps(normalize_observation(row), allow_nan=False) + "\n")
            count += 1
    print(json.dumps({"status": "PASS", "normalized_rows": count, "output": str(args.normalized_output)}))


if __name__ == "__main__":
    main()
