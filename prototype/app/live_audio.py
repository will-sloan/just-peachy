"""Explicit opt-in XVF3800 microphone source. See docs/LIVE_AUDIO.md.

No microphone or USB access occurs at import. Paths come from site config.
Only start(consent=True) may change documented routing and open capture.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone

import numpy as np
from .windows_audio import endpoint_snapshot, compare_defaults


class LiveAudioError(RuntimeError):
    pass


class LiveGap(LiveAudioError):
    """The session is incomplete: stop, then begin a fresh recognizer epoch."""


@dataclass(frozen=True)
class LiveConfig:
    host_executable: str
    lease_path: str
    endpoint_name: str | None = None
    endpoint_id: str | None = None
    hostapi: str = "Windows WASAPI" if os.name == "nt" else "ALSA"
    tap: str = "O0"
    native_rate: int = 48000
    block_frames: int = 480
    reserve_seconds: float = 10.0
    control_timeout_seconds: float = 8.0
    evidence_dir: str | None = None
    normal_microphone_gain: float = 10.0
    normal_system_delay: int = -32
    expected_asr_gain: float = 1.0

    def __post_init__(self):
        if not isinstance(self.host_executable, str) or not self.host_executable.strip():
            raise ValueError("Configure the installed matching XMOS host_executable path in external live_config.json")
        if not isinstance(self.lease_path, str) or not self.lease_path.strip():
            raise ValueError("Configure lease_path: reuse the existing project hardware lease where installed")
        if self.hostapi not in ("Windows WASAPI", "Windows WDM-KS", "ALSA"):
            raise ValueError("Choose explicit Windows WASAPI/WDM-KS or ALSA; system-default aliases are not supported")
        if not 1 <= self.control_timeout_seconds <= 30:
            raise ValueError("control timeout must be 1..30 seconds")
        if self.tap not in ("O0", "O1"):
            raise ValueError("tap must be O0 or O1; channels are never averaged")
        if self.native_rate != 48000 or self.block_frames not in (480, 960):
            raise ValueError("This matched UA io48 adapter requires 48k and 480/960 frame blocks")
        if not 1 <= self.reserve_seconds <= 120:
            raise ValueError("raw reserve must be 1..120 seconds")
        if self.normal_microphone_gain != 10.0 or self.normal_system_delay != -32:
            raise ValueError("Only the matched v3.2.1 product microphone baseline is currently qualified")
        if self.expected_asr_gain != 1.0:
            raise ValueError("O0 host +3dB is bound to verified device ASR gain 1.0")


@dataclass(frozen=True)
class LiveBlock:
    audio: np.ndarray
    model_start_sample: int
    native_start_frame: int
    native_frames: int
    callback_monotonic_ns: int
    adc_time_seconds: float
    delivery_monotonic_ns: int
    resampler_delay_seconds: float
    source_lag_seconds: float
    epoch: int = 0


class DeviceLease:
    """Interoperates with existing measurement_app byte-zero Windows lock."""
    def __init__(self, path):
        self.path = Path(path)
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0, 2)
            if not handle.tell():
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as exc:
            handle.close()
            raise LiveAudioError("XVF device lease is owned; stop the owning project session first") from exc
        self.handle = handle
        return self

    def close(self):
        if self.handle is not None:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()
                self.handle = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *args):
        self.close()


READBACKS = ("VERSION", "AEC_MIC_ARRAY_TYPE", "AEC_NUM_MICS", "AEC_MIC_ARRAY_GEO",
             "USB_BIT_DEPTH", "AUDIO_MGR_MIC_GAIN", "AUDIO_MGR_REF_GAIN", "AUDIO_MGR_SYS_DELAY",
             "I2S_INPUT_PACKED", "AUDIO_MGR_OP_PACKED", "AUDIO_MGR_OP_UPSAMPLE",
             "AUDIO_MGR_OP_L", "AUDIO_MGR_OP_R", "AEC_ASROUTONOFF", "AEC_ASROUTGAIN")
LIVE_SETTABLE = frozenset(("I2S_INPUT_PACKED", "AUDIO_MGR_OP_PACKED", "AUDIO_MGR_MIC_GAIN",
                          "AUDIO_MGR_SYS_DELAY", "AEC_ASROUTONOFF", "AUDIO_MGR_OP_UPSAMPLE",
                          "AUDIO_MGR_OP_L", "AUDIO_MGR_OP_R"))


class HostControl:
    """Matched command tool, serialized timeout-bounded calls; no shell."""
    def __init__(self, config: LiveConfig):
        self.config = config
        self.executable = Path(config.host_executable).resolve(strict=True)
        self.lock = threading.Lock()
        self.receipts = []

    def query(self, command, *values):
        if command not in READBACKS and command != "BLD_MSG":
            raise LiveAudioError("Command is outside the live adapter allowlist")
        if values and command not in LIVE_SETTABLE:
            raise LiveAudioError("This adapter cannot write firmware identity, topology, USB bit depth or unowned DSP controls")
        argv = [str(self.executable), "-u", "usb", command, *map(str, values)]
        with self.lock:
            start = time.monotonic_ns()
            proc = subprocess.run(argv, cwd=self.executable.parent, capture_output=True,
                                  timeout=self.config.control_timeout_seconds,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            out, err = proc.stdout.decode("utf-8-sig", "replace"), proc.stderr.decode("utf-8-sig", "replace")
            self.receipts.append({"command": command, "arguments": list(values), "exit_code": proc.returncode,
                                  "stdout": out, "stderr": err, "elapsed_seconds": (time.monotonic_ns()-start)/1e9})
            if proc.returncode or err.strip():
                raise LiveAudioError(f"{command} failed: {err or out}")
            return out

    def values(self, command):
        lines = [s for s in self.query(command).splitlines() if s.startswith(command + " ")]
        if len(lines) != 1:
            raise LiveAudioError(f"Missing or ambiguous readback for {command}")
        result = []
        for token in lines[0].strip("\x00 ").split()[1:]:
            enum = re.search(r"\[(-?\d+)\]", token)
            if enum:
                result.append(int(enum.group(1)))
            else:
                try:
                    result.append(int(token))
                except ValueError:
                    result.append(float(token))
        if not all(math.isfinite(v) for v in result):
            raise LiveAudioError("Nonfinite device readback: " + command)
        return result

    def set(self, command, values):
        self.query(command, *values)
        actual = self.values(command)
        if len(actual) != len(values) or any(not math.isclose(a, b, abs_tol=1e-6) for a, b in zip(actual, values)):
            raise LiveAudioError(f"{command} readback mismatch: {actual} != {values}")

    def snapshot(self, *, best_effort=False):
        result = {}
        errors = {}
        inactive = False
        for name in ("VERSION", "USB_BIT_DEPTH", "BLD_MSG", *(n for n in READBACKS if n not in ("VERSION", "USB_BIT_DEPTH"))):
            if inactive:
                errors[name] = "NOT_ATTEMPTED: audio-loop readback requires an active consented input stream"
                continue
            try:
                result[name] = self.query(name) if name == "BLD_MSG" else self.values(name)
            except Exception as exc:
                if not best_effort:
                    raise
                errors[name] = str(exc)
                inactive = "audio loop is active" in str(exc) or "SERVICER_QUEUE_FULL" in str(exc)
        if errors:
            result["read_errors"] = errors
        return result


def inventory(config: LiveConfig | None = None) -> dict:
    """Audio enumeration + optional leased USB reads; never opens capture."""
    import sounddevice as sd
    apis = sd.query_hostapis()
    devices = [dict(d, hostapi_name=apis[d["hostapi"]]["name"]) for d in sd.query_devices()
               if re.search(r"XVF3800|XMOS", d["name"], re.I)]
    result = {"utc": datetime.now(timezone.utc).isoformat(), "audio_streams_opened": 0,
              "device_setters": 0, "endpoints": devices, "windows_audio": endpoint_snapshot()}
    if config is not None:
        with DeviceLease(config.lease_path):
            control = HostControl(config)
            result["device"] = control.snapshot(best_effort=True)
            result["tool_sha256"] = hashlib.sha256(control.executable.read_bytes()).hexdigest()
            result["tool_files"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in (control.executable, control.executable.with_name("command_map.dll"),
                                              control.executable.with_name("device_usb.dll")) if p.is_file()}
            result["commands"] = control.receipts
    return result


def resolve_endpoint(config: LiveConfig, state: dict) -> dict:
    """Re-resolve stable name/Windows ID, rejecting ambiguity, never defaults."""
    endpoints = [d for d in state["endpoints"] if d["max_input_channels"] >= 2
                 and d["hostapi_name"] == config.hostapi]
    if config.endpoint_name:
        endpoints = [d for d in endpoints if d["name"] == config.endpoint_name]
    if len(endpoints) != 1:
        raise LiveAudioError("Choose one explicit XVF capture endpoint; none or multiple candidates found")
    selected = dict(endpoints[0])
    if os.name == "nt":
        win = state["windows_audio"]
        if win["status"] != "PASS":
            raise LiveAudioError("Windows endpoint identity is unavailable; cannot safely bind XVF")
        physical = [d for d in win["capture_endpoints"] if re.search(r"XVF3800|XMOS", d.get("name") or "", re.I)]
        # Vendor host uses first VID/PID match, with no serial selector. Never
        # write it when several boards could receive a command.
        if len(physical) != 1:
            raise LiveAudioError("Multiple/no XVF physical endpoints: matching vendor control tool cannot safely address one; resolve the hardware ambiguity")
        match = physical[0]
        if match["name"] != selected["name"]:
            raise LiveAudioError("PortAudio endpoint cannot be bound unambiguously to Windows endpoint ID")
        if config.endpoint_id and config.endpoint_id != match["endpoint_id"]:
            raise LiveAudioError("Selected XVF endpoint is absent or changed; explicit re-selection is required")
        selected["endpoint_id"] = match["endpoint_id"]
    elif len([d for d in state["endpoints"] if d["max_input_channels"] >= 2 and d["hostapi_name"] == config.hostapi]) != 1:
        raise LiveAudioError("Linux multi-device control addressing is not qualified; select a unique physical XVF")
    return selected


class LiveRoute:
    def __init__(self, control, config):
        self.control, self.config = control, config
        self.before = {}
        self.changed = []
        self.applied = {}

    def apply(self):
        self.before = self.control.snapshot()
        b = self.before
        if b["VERSION"] != [3, 2, 1] or b["AEC_NUM_MICS"] != [4] or "ua-io48" not in b["BLD_MSG"]:
            raise LiveAudioError("This adapter requires the inspected XVF 3.2.1 UA 48k four-microphone build")
        if b["AEC_MIC_ARRAY_TYPE"] not in ([1], [2]):
            raise LiveAudioError("Unknown array topology; no geometry changes are permitted")
        if len(b["USB_BIT_DEPTH"]) != 2 or any(v not in (16, 24, 32) for v in b["USB_BIT_DEPTH"]):
            raise LiveAudioError("Unknown current USB format; adapter never changes bit depth")
        if b["AEC_ASROUTGAIN"] != [self.config.expected_asr_gain]:
            raise LiveAudioError("Device ASR gain is not unity; inspect domain before applying host +3dB")
        desired = {"I2S_INPUT_PACKED": [0], "AUDIO_MGR_OP_PACKED": [0, 0],
                   "AUDIO_MGR_MIC_GAIN": [10.0], "AUDIO_MGR_SYS_DELAY": [-32],
                   "AEC_ASROUTONOFF": [1], "AUDIO_MGR_OP_UPSAMPLE": [1, 1],
                   "AUDIO_MGR_OP_L": [7, 3], "AUDIO_MGR_OP_R": [6, 3]}
        for name, values in desired.items():
            if b[name] != values:
                # Register intent before issuing setter: timeout can mean a
                # successful write with a lost reply. Restoration still runs.
                self.changed.append(name)
                self.applied[name] = values
                self.control.set(name, values)
        return {"before": b, "applied": desired, "changed": self.changed,
                "tap": self.config.tap, "channel_index": 0 if self.config.tap == "O0" else 1,
                "host_gain_db": 3.0 if self.config.tap == "O0" else 0.0,
                "device_asr_gain": b["AEC_ASROUTGAIN"], "native_rate": 48000,
                "model_rate": 16000, "render_streams": 0,
                "baseline": "XMOS 3.2.1 product/control_param_values.yaml mic=10 delay=-32",
                "mic_baseline_is_room_calibration": False}

    def restore(self):
        result = {}
        # Reverse order reestablishes routes before packed mode. Never enable
        # packed input/output until capture has already stopped.
        for name in reversed(self.changed):
            try:
                current = self.control.values(name)
                if current == self.before[name]:
                    result[name] = "ALREADY_RESTORED"
                elif current != self.applied[name]:
                    result[name] = "EXTERNAL_CHANGE_NOT_OVERWRITTEN"
                else:
                    self.control.set(name, self.before[name])
                    result[name] = "RESTORED"
            except Exception as exc:
                result[name] = "FAILED: " + str(exc)
                for pending in self.changed:
                    if pending not in result:
                        result[pending] = "NOT_ATTEMPTED_AFTER_CONTROL_FAILURE"
                break
        return result


class StreamingDecimator:
    """Stateful 48k -> 16k anti-alias FIR, continuous across callback blocks."""
    def __init__(self):
        from scipy.signal import firwin
        self.taps = firwin(97, 7200, fs=48000).astype(np.float64)
        self.state = np.zeros(len(self.taps) - 1)
        self.native_count = 0
        self.delay_seconds = (len(self.taps)-1)/2/48000

    def convert(self, audio):
        from scipy.signal import lfilter
        filtered, self.state = lfilter(self.taps, [1.0], audio, zi=self.state)
        offset = (-self.native_count) % 3
        self.native_count += len(audio)
        return filtered[offset::3].astype(np.float32)


class XVFLiveSource:
    """Single owner, preallocated callback ring, input-only UAC stream.

    Call read from a dedicated producer/normalizer thread. None means timeout
    or completed; status()['finished'] distinguishes them. A LiveGap requires
    stopping this source and a new source/recognizer epoch; no fallback/retry
    captures unattended speech. Stop rejects new samples, restores route while
    the input-only clock remains active, then closes stream and releases lease.
    """
    def __init__(self, config: LiveConfig, *, status_callback=None, sd_module=None):
        self.config = config
        self.status_callback = status_callback or (lambda kind, data: None)
        self.sd = sd_module
        self.stream = None
        self.lease = None
        self.control = None
        self.route = None
        self.metadata = {}
        self._read_seq = self._write_seq = 0
        self._native_frames = self._model_samples = self._dropped_frames = 0
        self._fault = None
        self._stopped = False
        self._started = False
        self._done = threading.Event()
        self._receipt = None
        self._max_lag = 0.0
        self._route_ready = False
        self._priming_frames = 0
        self._priming_status_events = 0
        self._last_callback_ns = 0
        self._started_ns = 0
        self._stop_lock = threading.RLock()
        self._cancel_requested = threading.Event()

    def start(self, *, consent=False):
        with self._stop_lock:
            return self._start_owned(consent=consent)

    def _start_owned(self, *, consent=False):
        if consent is not True:
            raise LiveAudioError("Explicit in-app microphone consent is required")
        if self._started or self._stopped:
            raise LiveAudioError("Create a fresh live source for each listening epoch")
        import sounddevice as sd
        self.sd = self.sd or sd
        self.lease = DeviceLease(self.config.lease_path).acquire()
        self.metadata["defaults_before"] = endpoint_snapshot()
        try:
            # Refresh only under the hardware lease and before any app stream.
            # PortAudio's process-local enumeration can otherwise survive USB
            # removal/reinsertion with obsolete indices.
            self.sd._terminate()
            self.sd._initialize()
            state = inventory()
            selected = resolve_endpoint(self.config, state)
            self.metadata["endpoint"] = selected
            self.sd.check_input_settings(device=selected["index"], channels=2, dtype="float32", samplerate=48000)
            capacity = math.ceil(self.config.reserve_seconds * 48000 / self.config.block_frames)
            self._ring = np.empty((capacity, self.config.block_frames, 2), dtype=np.float32)
            self._frames = np.zeros(capacity, dtype=np.int32)
            self._native_start = np.zeros(capacity, dtype=np.int64)
            self._clock = np.zeros(capacity, dtype=np.int64)
            self._adc = np.zeros(capacity, dtype=np.float64)
            self._capacity = capacity
            self._converter = StreamingDecimator()
            self._gain = np.float32(10 ** (3/20) if self.config.tap == "O0" else 1)
            kwargs = {}
            if self.config.hostapi == "Windows WASAPI":
                kwargs["extra_settings"] = self.sd.WasapiSettings(exclusive=True, auto_convert=False)
            self.stream = self.sd.InputStream(device=selected["index"], samplerate=48000,
                                             channels=2, dtype="float32", blocksize=self.config.block_frames,
                                             latency=0.1, callback=self._callback, **kwargs)
            self.stream.start()
            self._started_ns = time.monotonic_ns()
            # Some UA firmware commands need an active USB input clock. Until
            # route verification the callback discards these priming frames;
            # they cannot enter a journal, model or personal enrollment.
            self.control = HostControl(self.config)
            self.route = LiveRoute(self.control, self.config)
            self.metadata["route"] = self.route.apply()
            # Drain pre-route driver buffering while admission stays disabled.
            # This is bounded startup settling, never live sample pacing.
            time.sleep(float(self.stream.latency) + 2*self.config.block_frames/48000)
            if self._cancel_requested.is_set():
                raise LiveAudioError("Start cancelled; restoring device before releasing capture")
            if self._fault or not self.stream.active:
                raise LiveAudioError(self._fault or "Input-only stream stopped during route setup")
            self._route_ready = True
            self._started = True
            self.metadata.update(actual_stream_rate=self.stream.samplerate, actual_latency=self.stream.latency,
                                 resampler_delay_seconds=self._converter.delay_seconds,
                                 raw_ring_bytes=int(self._ring.nbytes), raw_ring_capacity_seconds=capacity*self.config.block_frames/48000,
                                 defaults_after_start=endpoint_snapshot(), started_monotonic_ns=time.monotonic_ns())
            self.metadata["timestamps_calibrated_to_acoustic_arrival"] = False
            self.status_callback("source_started", self.metadata)
            return self.metadata
        except Exception:
            self.stop()
            raise

    def _callback(self, indata, frames, time_info, status):
        # No disk, inference, GUI, USB, string-formatting, or sample allocation.
        if not self._route_ready:
            self._priming_frames += frames
            self._priming_status_events += int(bool(status))
            self._last_callback_ns = time.monotonic_ns()
            return
        if status or frames > self.config.block_frames or self._write_seq-self._read_seq >= self._capacity:
            self._fault = "INPUT_STATUS_GAP" if status else "CALLBACK_SIZE_OR_RAW_RING_OVERFLOW"
            self._dropped_frames += frames
            raise self.sd.CallbackAbort
        slot = self._write_seq % self._capacity
        np.copyto(self._ring[slot, :frames], indata)
        self._frames[slot] = frames
        self._native_start[slot] = self._native_frames
        self._clock[slot] = time.monotonic_ns()
        self._last_callback_ns = int(self._clock[slot])
        self._adc[slot] = time_info.inputBufferAdcTime
        self._native_frames += frames
        self._write_seq += 1  # Publish after all samples and metadata are ready.

    def read(self, timeout=0.25):
        if not self._started:
            if self._stopped:
                return None
            raise LiveAudioError("Source has not started")
        deadline = time.monotonic() + max(0, timeout)
        while self._read_seq == self._write_seq:
            if self._fault:
                raise LiveGap(self._fault)
            if self._stopped:
                return None
            if not self.stream.active:
                self._fault = "DEVICE_DISCONNECTED_OR_STREAM_STOPPED"
                raise LiveGap(self._fault)
            if time.monotonic_ns() - (self._last_callback_ns or self._started_ns) > 2_000_000_000:
                self._fault = "DEVICE_NO_CALLBACK_FOR_2_SECONDS"
                raise LiveGap(self._fault)
            if time.monotonic() >= deadline:
                return None
            time.sleep(min(.005, max(0, deadline-time.monotonic())))
        slot = self._read_seq % self._capacity
        n = int(self._frames[slot])
        # Copy before releasing slot. Every allocation/filter is off callback.
        mono = self._ring[slot, :n, 0 if self.config.tap == "O0" else 1].copy()
        native_start, callback_ns, adc = int(self._native_start[slot]), int(self._clock[slot]), float(self._adc[slot])
        self._read_seq += 1
        audio = self._converter.convert(mono) * self._gain
        delivered = time.monotonic_ns()
        lag = max(0.0, (delivered-callback_ns)/1e9)
        self._max_lag = max(self._max_lag, lag)
        block = LiveBlock(audio, self._model_samples, native_start, n, callback_ns, adc, delivered,
                          self._converter.delay_seconds, lag)
        self._model_samples += len(audio)
        return block

    def status(self):
        return {"started": self._started, "finished": self._done.is_set(), "fault": self._fault,
                "raw_frames": self._native_frames, "converted_samples": self._model_samples,
                "priming_frames_discarded_before_route_verified": self._priming_frames,
                "priming_status_events": self._priming_status_events,
                "dropped_frames": self._dropped_frames, "pending_raw_blocks": self._write_seq-self._read_seq,
                "maximum_source_lag_seconds": self._max_lag, "render_streams": 0,
                "evaluation_firmware_restart_note": "If evaluation firmware is used, its eight-hour limit requires a safe restart between sessions; this adapter never resets mid-utterance."}

    def wait(self, timeout=None):
        return self._done.wait(timeout)

    def stop(self):
        self._cancel_requested.set()
        with self._stop_lock:
            return self._stop_owned()

    def _stop_owned(self):
        if self._receipt is not None:
            return self._receipt
        self._stopped = True
        self._route_ready = False
        errors = []
        # UA control servicing needs the audio clock. No samples are admitted
        # during restoration; close the input stream immediately afterwards.
        restored = self.route.restore() if self.route is not None else {}
        if self.stream is not None:
            try:
                self.stream.stop()
            except Exception as exc:
                errors.append("stream_stop: " + str(exc))
            try:
                self.stream.close()
            except Exception as exc:
                errors.append("stream_close: " + str(exc))
            # A driver can reject both stop and close. Do not let another
            # process take the lease while this input stream is still active.
            # Keep the incomplete stop retryable instead of caching success.
            try:
                still_active = bool(self.stream.active)
            except Exception:
                still_active = not bool(getattr(self.stream, "closed", False))
            if still_active:
                self._fault = self._fault or "STREAM_REMAINS_ACTIVE_AFTER_CLOSE"
                raise LiveAudioError("Input stream remains active after close; hardware lease retained for cleanup retry: " + "; ".join(errors))
        if self.lease is not None:
            self.lease.close()
        after = endpoint_snapshot()
        self._done.set()
        self._receipt = {"status": self.status(), "route_restoration": restored, "errors": errors,
                         "metadata": self.metadata, "defaults_after_stop": after,
                         "default_output_comparison": compare_defaults(self.metadata.get("defaults_before", {}), after),
                         "commands": self.control.receipts if self.control else []}
        if self.config.evidence_dir:
            folder = Path(self.config.evidence_dir)
            folder.mkdir(parents=True, exist_ok=True)
            name = "live_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + ".json"
            (folder/name).write_text(json.dumps(self._receipt, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        self.status_callback("source_stopped", self._receipt)
        return self._receipt

    finish = stop


def summarize_live_integrity(source: XVFLiveSource) -> dict:
    """Authoritative capture/restoration gate after stop, without hardware I/O.

    Enrollment callers must not infer completeness solely from read exceptions:
    a callback can overflow while the consumer is inside a quality-model call.
    An explicit user stop may leave an unconsumed tail; this is counted and must
    not be represented as accepted speech. It does not corrupt the saved prefix.
    """
    status = source.status()
    receipt = source._receipt or {}
    restoration = receipt.get("route_restoration", {})
    failed_restore = {k: v for k, v in restoration.items() if v not in ("RESTORED", "ALREADY_RESTORED")}
    reasons = []
    if not status.get("started"):
        reasons.append("SOURCE_NEVER_STARTED")
    if not status.get("finished"):
        reasons.append("SOURCE_NOT_STOPPED")
    if status.get("fault"):
        reasons.append(str(status["fault"]))
    if status.get("dropped_frames", 0):
        reasons.append("DROPPED_NATIVE_FRAMES")
    if receipt.get("errors"):
        reasons.append("STREAM_STOP_OR_CLOSE_ERROR")
    if failed_restore:
        reasons.append("DEVICE_RESTORATION_REQUIRES_REVIEW")
    return {"ok": not reasons, "reasons": reasons, "status": status,
            "restoration_ok": not failed_restore, "restoration_issues": failed_restore,
            "unconsumed_tail_blocks": status.get("pending_raw_blocks", 0),
            "tail_disposition": "Not included in converted/accepted speech; intentional stop boundary",
            "endpoint": source.metadata.get("endpoint"), "route": source.metadata.get("route"),
            "native_sample_rate": source.metadata.get("actual_stream_rate"),
            "resampler_delay_seconds": source.metadata.get("resampler_delay_seconds")}


def main():
    parser = argparse.ArgumentParser(description="Read-only XVF inventory. This command never captures audio.")
    parser.add_argument("--config", type=Path, help="JSON object matching LiveConfig, optional for audio-only inventory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = LiveConfig(**json.loads(args.config.read_text(encoding="utf-8-sig"))) if args.config else None
    result = inventory(config)
    text = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text+"\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
