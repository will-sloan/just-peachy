"""Finite callback playback with source-continuity receipts.

The callback uses prebuilt audio and preallocated numerical receipt storage.
PortAudio timestamps describe the host audio stream, not calibrated acoustics.
An empty callback-status list does not prove physical playback had no glitches.
"""
from datetime import datetime, timezone
import ctypes
import math
import os
import threading
import time

import numpy as np
import sounddevice as sd

RATE = 48000
REQUESTED_LATENCY_S = 0.15
START_DELAY_S = 1.5
STATUS_NAMES = ("input_underflow", "input_overflow", "output_underflow",
                "output_overflow", "priming_output")


def _load_ole32():
    api = ctypes.WinDLL("ole32.dll")
    api.CoInitializeEx.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    api.CoInitializeEx.restype = ctypes.c_int32
    api.CoUninitialize.argtypes = ()
    api.CoUninitialize.restype = None
    return api


class _ComApartment:
    """Balance this thread's COM reference without disturbing another owner.

    PortAudio's WASAPI callback StartStream marshals COM interfaces on its
    calling thread. PortAudio initialization on the main thread is insufficient.
    STA matches the installed PortAudio CoInitialize helper. An already-created
    incompatible apartment is retained, as in that helper.
    """

    def __init__(self, receipt):
        self.receipt = receipt
        self.api = None
        self.owned = False
        self.thread_id = threading.get_ident()

    def open(self):
        if os.name != "nt":
            self.receipt["com_apartment"] = {"required": False}
            return
        self.api = _load_ole32()
        value = int(self.api.CoInitializeEx(None, 2)) & 0xffffffff
        state = {"required": True, "requested_model": "COINIT_APARTMENTTHREADED",
                 "calling_thread_id": self.thread_id, "hresult_hex": f"0x{value:08X}",
                 "reference_acquired": False, "reference_released": False}
        self.receipt["com_apartment"] = state
        if value in (0, 1):  # S_OK and S_FALSE both acquire one reference.
            self.owned = True
            state["reference_acquired"] = True
            state["result"] = "initialized" if value == 0 else "already_initialized_same_model"
        elif value == 0x80010106:  # RPC_E_CHANGED_MODE: no reference acquired.
            state["result"] = "using_existing_different_model"
        else:
            state["result"] = "failed"
            raise OSError(f"Playback thread CoInitializeEx failed: 0x{value:08X}")

    def close(self):
        if self.owned:
            if threading.get_ident() != self.thread_id:
                raise RuntimeError("COM cleanup must run on the initializing playback thread")
            self.api.CoUninitialize()
            self.owned = False
            self.receipt["com_apartment"]["reference_released"] = True


class _CallbackPlayer:
    """A testable callback; no device access, file writes or JSON conversion."""

    def __init__(self, signal, stop, max_callbacks=None):
        self.signal = signal
        self.stop = stop
        self.position = 0
        self.count = 0
        self.cancelled = False
        self.error = None
        # Explicit resource bound. Overflow fails visibly instead of losing logs.
        capacity = max_callbacks or (1024 + math.ceil(len(signal) / RATE * 2000))
        self.records = np.zeros(capacity, dtype=[
            ("source_start_frame", "i8"), ("buffer_frames", "i8"),
            ("source_frames", "i8"), ("host_callback_monotonic_ns", "i8"),
            ("output_buffer_dac_time_s", "f8"), ("current_time_s", "f8"),
            ("status_mask", "u1"), ("cancelled", "?"),
        ])

    def __call__(self, outdata, frames, time_info, status):
        try:
            outdata.fill(0)
            if self.count >= len(self.records):
                raise RuntimeError("Playback callback receipt capacity exceeded")
            if frames <= 0 or outdata.shape != (frames, self.signal.shape[1]):
                raise ValueError("Unexpected playback callback buffer shape")
            row = self.records[self.count]
            row["host_callback_monotonic_ns"] = time.perf_counter_ns()
            row["source_start_frame"] = self.position
            row["buffer_frames"] = frames
            row["output_buffer_dac_time_s"] = time_info.outputBufferDacTime
            row["current_time_s"] = time_info.currentTime
            mask = 0
            for bit, name in enumerate(STATUS_NAMES):
                if getattr(status, name):
                    mask |= 1 << bit
            row["status_mask"] = mask
            self.cancelled = self.cancelled or self.stop.is_set()
            row["cancelled"] = self.cancelled
            copied = 0 if self.cancelled else min(frames, len(self.signal) - self.position)
            if copied:
                outdata[:copied] = self.signal[self.position:self.position + copied]
            row["source_frames"] = copied
            self.position += copied
            self.count += 1
            finished = self.cancelled or self.position == len(self.signal)
        except BaseException as exc:
            self.error = exc
            # Preserve the first failure for the caller; never leave garbage audio.
            outdata.fill(0)
            raise sd.CallbackAbort
        if finished:
            # CallbackStop drains the buffers already generated, including this one.
            raise sd.CallbackStop

    def summarize(self):
        rows = []
        expected = 0
        contiguous = True
        for record in self.records[:self.count]:
            row = {name: record[name].item() for name in self.records.dtype.names}
            row["status_flags"] = [name for bit, name in enumerate(STATUS_NAMES)
                                   if row["status_mask"] & (1 << bit)]
            for name in ("output_buffer_dac_time_s", "current_time_s"):
                if not math.isfinite(row[name]):
                    row[name] = None
            contiguous = contiguous and row["source_start_frame"] == expected
            expected += row["source_frames"]
            rows.append(row)
        status_rows = [row for row in rows if row["status_mask"]]
        times = [row["host_callback_monotonic_ns"] for row in rows]
        gaps = np.diff(times) / 1e6 if len(times) > 1 else np.array([])
        dac_gaps = []
        for previous, current in zip(rows, rows[1:]):
            a, b = previous["output_buffer_dac_time_s"], current["output_buffer_dac_time_s"]
            if a is not None and b is not None:
                dac_gaps.append(b - a - previous["buffer_frames"] / RATE)
        source_rows = [row for row in rows if row["source_frames"]]
        first = source_rows[0]["output_buffer_dac_time_s"] if source_rows else None
        last = source_rows[-1] if source_rows else None
        end = (last["output_buffer_dac_time_s"] + last["source_frames"] / RATE
               if last and last["output_buffer_dac_time_s"] is not None else None)
        return {
            "frames_written": self.position,
            "frames_written_semantics": "Source frames submitted to PortAudio callback buffers; not a physical DAC frame counter",
            "callback_count": self.count,
            "callback_receipt_capacity": len(self.records),
            "callback_receipts": rows,
            "callback_status_events": status_rows,
            "underflows": [row["source_start_frame"] for row in rows
                           if "output_underflow" in row["status_flags"]],
            "source_frame_continuity": {
                "contiguous": bool(contiguous and expected == self.position),
                "submitted_source_frames": self.position,
                "expected_source_frames": len(self.signal),
                "all_source_frames_submitted": self.position == len(self.signal),
            },
            "host_callback_gap_ms": {
                "median": float(np.median(gaps)) if len(gaps) else None,
                "max": float(np.max(gaps)) if len(gaps) else None,
            },
            "estimated_source_start_output_dac_time_s": first,
            "estimated_source_end_output_dac_time_s": end,
            "output_dac_timestamp_gap_error_s": dac_gaps,
            "timing_scope": "PortAudio stream-time estimates and host callback arrival times; requires independent acoustic marker validation",
            "callback_status_limitation": "Installed WASAPI backend may not report every output underrun; empty flags are not proof of uninterrupted acoustic playback",
        }


def separate_playback(device, wave, gain_db, channel, stop, receipt):
    """Play one mono 48 kHz stimulus on an explicit endpoint/channel.

The caller owns the receipt and stop event. All errors stay in the receipt.
Completion requires the native finished callback after callback-buffer draining.
Cancellation requests callback draining, with a bounded abort fallback.
"""
    stream = player = apartment = None
    done = threading.Event()
    forced_abort = False
    receipt.update(completed=False, cancelled=False, drained=False, frames_written=0,
                   underflows=[], backend="PortAudio callback OutputStream",
                   requested_stream_latency_s=REQUESTED_LATENCY_S)
    try:
        if stop.wait(START_DELAY_S):
            receipt.update(cancelled_before_playback=True, cancelled=True)
            return
        if channel not in ("left", "right"):
            raise ValueError("Playback channel must be left or right")
        if not math.isfinite(gain_db):
            raise ValueError("Playback gain must be finite")
        source = np.asarray(wave)
        if source.ndim != 1 or not len(source) or not np.isfinite(source).all():
            raise ValueError("Playback requires a nonempty finite mono waveform")
        apartment = _ComApartment(receipt)
        apartment.open()
        description = dict(sd.query_devices(device))
        channels = min(2, int(description["max_output_channels"]))
        if channels < 1 or (channels < 2 and channel == "right"):
            raise ValueError("Selected endpoint does not provide the requested output channel")
        signal = np.zeros((len(source), channels), dtype=np.float32)
        signal[:, 0 if channel == "left" else 1] = source * 10 ** (gain_db / 20)
        if not np.isfinite(signal).all() or np.max(np.abs(signal)) > 1:
            raise ValueError("Playback gain would exceed finite digital full scale")
        sd.check_output_settings(device=device, channels=channels, dtype="float32", samplerate=RATE)
        receipt.update(device=description, sample_rate_hz=RATE, channels=channels,
                       channel=channel, requested_gain_db=gain_db,
                       source_frames=len(source), source_duration_s=len(source) / RATE)
        player = _CallbackPlayer(signal, stop)
        stream = sd.OutputStream(
            device=device, samplerate=RATE, channels=channels, dtype="float32",
            blocksize=0, latency=REQUESTED_LATENCY_S, callback=player,
            finished_callback=done.set, prime_output_buffers_using_stream_callback=True,
            clip_off=True, dither_off=True,
        )
        receipt["actual_stream_latency_s"] = float(stream.latency)
        receipt["start_utc"] = datetime.now(timezone.utc).isoformat()
        receipt["start_monotonic_ns"] = time.perf_counter_ns()
        stream.start()
        deadline = time.monotonic() + len(signal) / RATE + 5.0
        cancel_deadline = None
        while not done.wait(0.05):
            current = time.monotonic()
            if stop.is_set() and cancel_deadline is None:
                player.cancelled = True
                cancel_deadline = current + 1.5
            if cancel_deadline is not None and current >= cancel_deadline:
                forced_abort = True
                receipt["cancel_drain_timeout"] = True
                stream.abort()
                break
            if current >= deadline:
                forced_abort = True
                stream.abort()
                raise TimeoutError("Playback finished callback did not arrive within its duration plus 5 seconds")
        if player.error is not None:
            raise player.error
        receipt["native_finished_callback_received"] = done.is_set()
        receipt["drained"] = done.is_set() and not forced_abort
        receipt["cancelled"] = player.cancelled or stop.is_set()
        receipt["completed"] = bool(receipt["drained"] and not receipt["cancelled"]
                                    and player.position == len(signal))
    except BaseException as exc:
        receipt["error"] = repr(exc)
        receipt["completed"] = False
    finally:
        if stream is not None:
            try:
                stream.close()
            except BaseException as exc:
                receipt.setdefault("cleanup_errors", []).append(repr(exc))
                receipt["completed"] = False
        if apartment is not None:
            try:
                apartment.close()
            except BaseException as exc:
                receipt.setdefault("cleanup_errors", []).append(repr(exc))
                receipt["completed"] = False
        if player is not None:
            receipt.update(player.summarize())
            receipt["cancelled"] = player.cancelled or stop.is_set()
        receipt["forced_abort"] = forced_abort
        receipt["end_monotonic_ns"] = time.perf_counter_ns()
