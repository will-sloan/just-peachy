"""Bounded live adapter contracts; uses fake hardware only. See LIVE_AUDIO.md."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import numpy as np
from app import live_audio as L
from app.windows_audio import endpoint_snapshot, compare_defaults


NAME = "Echo Cancelling Speakerphone (XVF3800 Voice Processor)"
STATE = {"endpoints": [{"index": 22, "name": NAME, "max_input_channels": 2, "hostapi_name": "Windows WASAPI"}],
         "windows_audio": {"status": "PASS", "capture_endpoints": [{"name": NAME, "endpoint_id": "fixture-xvf"}]}}
INITIAL = {"VERSION": [3, 2, 1], "USB_BIT_DEPTH": [16, 16], "AEC_MIC_ARRAY_TYPE": [1],
           "AEC_NUM_MICS": [4], "AEC_MIC_ARRAY_GEO": [0.0]*12, "AUDIO_MGR_MIC_GAIN": [1],
           "AUDIO_MGR_REF_GAIN": [1.5], "AUDIO_MGR_SYS_DELAY": [0], "I2S_INPUT_PACKED": [1],
           "AUDIO_MGR_OP_PACKED": [1, 1], "AUDIO_MGR_OP_UPSAMPLE": [0, 0],
           "AUDIO_MGR_OP_L": [1, 0], "AUDIO_MGR_OP_R": [1, 1],
           "AEC_ASROUTONOFF": [0], "AEC_ASROUTGAIN": [1], "BLD_MSG": "BLD_MSG ua-io48-lin"}


class FakeControl:
    def __init__(self, config=None, initial=None):
        self.state = copy.deepcopy(initial or INITIAL)
        self.receipts = []
        self.fail_command = None
        self.stream = None

    def snapshot(self, **kwargs):
        if self.stream is not None and not self.stream.active:
            raise RuntimeError("audio loop inactive")
        return copy.deepcopy(self.state)

    def values(self, name):
        if self.stream is not None and not self.stream.active:
            raise RuntimeError("cannot restore after clock closes")
        return list(self.state[name])

    def set(self, name, values):
        self.state[name] = list(values)
        self.receipts.append((name, values))
        if name == self.fail_command:
            self.fail_command = None
            raise TimeoutError("write applied but response lost")


class FakeSD:
    class CallbackAbort(Exception):
        pass

    def __init__(self):
        self.streams = []

    def _terminate(self):
        pass

    def _initialize(self):
        pass

    def check_input_settings(self, **kwargs):
        assert kwargs["samplerate"] == 48000
        assert kwargs["channels"] == 2

    def WasapiSettings(self, **kwargs):
        assert kwargs == {"exclusive": True, "auto_convert": False}
        return kwargs

    def InputStream(self, **kwargs):
        owner = self
        class Stream:
            samplerate = 48000
            latency = 0.0
            active = False
            closed = False
            def start(self):
                self.active = True
            def stop(self):
                self.active = False
            def close(self):
                self.closed = True
            def send(self, left=0.1, right=0.2, status=False, frames=480):
                data = np.full((frames, 2), [left, right], dtype=np.float32)
                try:
                    kwargs["callback"](data, frames, types.SimpleNamespace(inputBufferAdcTime=10.0), status)
                except owner.CallbackAbort:
                    self.active = False
        result = Stream()
        self.streams.append(result)
        return result


class LiveAdapterTests(unittest.TestCase):
    def config(self, **kw):
        return L.LiveConfig("fixture-host-not-executed", str(Path(self.temp.name)/"hardware.lock"), **kw)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def start_fixture(self, **kw):
        sd = FakeSD()
        control = FakeControl()
        def make_control(cfg):
            control.stream = sd.streams[0]
            return control
        self.addCleanup(patch.stopall)
        patch.object(L, "inventory", return_value=copy.deepcopy(STATE)).start()
        patch.object(L, "HostControl", side_effect=make_control).start()
        source = L.XVFLiveSource(self.config(**kw), sd_module=sd)
        source.start(consent=True)
        self.addCleanup(source.stop)
        return source, sd.streams[0], control

    def test_consent_gate_does_not_touch_hardware(self):
        with patch.object(L, "DeviceLease") as lease:
            with self.assertRaisesRegex(L.LiveAudioError, "consent"):
                L.XVFLiveSource(self.config()).start()
            lease.assert_not_called()

    def test_lease_excludes_second_owner_and_releases(self):
        first = L.DeviceLease(self.config().lease_path).acquire()
        try:
            with self.assertRaises(L.LiveAudioError):
                L.DeviceLease(self.config().lease_path).acquire()
        finally:
            first.close()
        L.DeviceLease(self.config().lease_path).acquire().close()

    def test_resolves_fresh_index_and_rejects_missing_id(self):
        state = copy.deepcopy(STATE)
        state["endpoints"][0]["index"] = 81
        self.assertEqual(L.resolve_endpoint(self.config(endpoint_id="fixture-xvf"), state)["index"], 81)
        with self.assertRaises(L.LiveAudioError):
            L.resolve_endpoint(self.config(endpoint_id="removed-id"), state)
        state["windows_audio"]["capture_endpoints"].append({"name": NAME, "endpoint_id": "second"})
        with self.assertRaises(L.LiveAudioError):
            L.resolve_endpoint(self.config(), state)

    def test_no_pc_microphone_fallback(self):
        with self.assertRaises(L.LiveAudioError):
            L.resolve_endpoint(self.config(), {"endpoints": [], "windows_audio": {}})

    def test_partial_route_write_timeout_is_restored(self):
        control = FakeControl()
        route = L.LiveRoute(control, self.config())
        control.fail_command = "AUDIO_MGR_MIC_GAIN"
        with self.assertRaises(TimeoutError):
            route.apply()
        result = route.restore()
        self.assertTrue(all(v == "RESTORED" for v in result.values()))
        self.assertEqual(control.state, INITIAL)

    def test_external_parameter_change_not_overwritten(self):
        control = FakeControl()
        route = L.LiveRoute(control, self.config())
        route.apply()
        control.state["AUDIO_MGR_MIC_GAIN"] = [12]
        result = route.restore()
        self.assertEqual(result["AUDIO_MGR_MIC_GAIN"], "EXTERNAL_CHANGE_NOT_OVERWRITTEN")
        self.assertEqual(control.state["AUDIO_MGR_MIC_GAIN"], [12])

    def test_unknown_asr_gain_refuses_double_gain(self):
        control = FakeControl()
        control.state["AEC_ASROUTGAIN"] = [2]
        with self.assertRaisesRegex(L.LiveAudioError, "gain"):
            L.LiveRoute(control, self.config()).apply()
        self.assertEqual(control.receipts, [])

    def test_startup_frames_cannot_enter_model_before_route(self):
        original = FakeControl.snapshot
        def snapshot_with_priming(control, **kwargs):
            if control.stream is not None:
                control.stream.send(left=.9, right=.9)
            return original(control, **kwargs)
        with patch.object(FakeControl, "snapshot", snapshot_with_priming):
            source, stream, _ = self.start_fixture()
        self.assertEqual(source.status()["raw_frames"], 0)
        self.assertEqual(source.status()["priming_frames_discarded_before_route_verified"], 480)
        stream.send(left=.1, right=.2)
        self.assertLess(float(np.max(source.read().audio)), .2)

    def test_stop_during_start_serializes_restoration(self):
        sd, control = FakeSD(), FakeControl()
        reached, release = threading.Event(), threading.Event()
        original = control.snapshot
        def snapshot(**kwargs):
            reached.set()
            self.assertTrue(release.wait(2))
            return original(**kwargs)
        control.snapshot = snapshot
        def make_control(cfg):
            control.stream = sd.streams[0]
            return control
        source = L.XVFLiveSource(self.config(), sd_module=sd)
        errors = []
        def start():
            try:
                source.start(consent=True)
            except L.LiveAudioError as exc:
                errors.append(str(exc))
        with patch.object(L, "inventory", return_value=copy.deepcopy(STATE)), patch.object(L, "HostControl", side_effect=make_control):
            worker = threading.Thread(target=start)
            worker.start()
            self.assertTrue(reached.wait(2))
            stopper = threading.Thread(target=source.stop)
            stopper.start()
            self.assertTrue(source._cancel_requested.wait(1))
            release.set()
            worker.join(3)
            stopper.join(3)
        self.assertFalse(worker.is_alive() or stopper.is_alive())
        self.assertTrue(errors and "cancelled" in errors[0])
        self.assertEqual(control.state, INITIAL)
        self.assertTrue(sd.streams[0].closed)

    def test_stereo_demux_exact_single_gain_and_clocked_restore(self):
        for tap, expected in (("O0", .1*10**(3/20)), ("O1", .2)):
            source, stream, control = self.start_fixture(tap=tap)
            stream.send()
            block = source.read()
            self.assertEqual((len(block.audio), block.native_frames, block.model_start_sample), (160, 480, 0))
            self.assertAlmostEqual(float(block.audio[-1]), expected, places=6)
            self.assertEqual(block.resampler_delay_seconds, .001)
            first = source.stop()
            self.assertIs(first, source.stop())
            self.assertTrue(stream.closed)
            self.assertEqual(control.state, INITIAL)
            self.assertTrue(source.wait(.01))
            patch.stopall()

    def test_ring_overflow_is_visible_never_silent(self):
        source, stream, _ = self.start_fixture(reserve_seconds=1)
        for _ in range(101):
            stream.send()
        self.assertEqual(source.status()["dropped_frames"], 480)
        for _ in range(100):
            self.assertIsNotNone(source.read())
        with self.assertRaises(L.LiveGap):
            source.read()

    def test_integrity_gate_catches_overflow_before_consumer_observes_it(self):
        source, stream, _ = self.start_fixture(reserve_seconds=1)
        for _ in range(101):stream.send()
        source.stop()
        result=L.summarize_live_integrity(source)
        self.assertFalse(result['ok'])
        self.assertIn('DROPPED_NATIVE_FRAMES',result['reasons'])
        self.assertEqual(result['unconsumed_tail_blocks'],100)

    def test_integrity_gate_accepts_clean_stop_and_binds_actual_route(self):
        source, stream, _ = self.start_fixture()
        stream.send();source.read();source.stop()
        result=L.summarize_live_integrity(source)
        self.assertTrue(result['ok'])
        self.assertEqual(result['native_sample_rate'],48000)
        self.assertEqual(result['route']['host_gain_db'],3)

    def test_disconnect_requires_new_epoch_without_fallback(self):
        source, stream, _ = self.start_fixture()
        stream.active = False
        with self.assertRaisesRegex(L.LiveGap, "DISCONNECTED"):
            source.read()
        receipt = source.stop()
        self.assertTrue(any(v.startswith("FAILED") for v in receipt["route_restoration"].values()))

    def test_callback_stall_has_bounded_failure(self):
        source, stream, _ = self.start_fixture()
        source._last_callback_ns = time.monotonic_ns()-3_000_000_000
        with self.assertRaisesRegex(L.LiveGap, "NO_CALLBACK"):
            source.read()

    def test_resampler_invariant_across_irregular_chunks_and_antialias(self):
        from scipy.signal import lfilter
        rng = np.random.default_rng(34)
        data = rng.normal(0, .1, 12341).astype(np.float32)
        converter = L.StreamingDecimator()
        pieces, offset = [], 0
        for length in [1, 47, 481, 73, 812, 3, 999, 7001, 2924]:
            piece = data[offset:offset+length]
            if len(piece):
                pieces.append(converter.convert(piece))
            offset += length
        expected = lfilter(converter.taps, [1], data)[::3].astype(np.float32)
        np.testing.assert_allclose(np.concatenate(pieces), expected, atol=1e-7)
        t = np.arange(48000)/48000
        low = L.StreamingDecimator().convert(np.sin(2*np.pi*1000*t))[160:]
        high = L.StreamingDecimator().convert(np.sin(2*np.pi*12000*t))[160:]
        self.assertLess(np.sqrt(np.mean(high*high))/np.sqrt(np.mean(low*low)), .002)

    def test_default_endpoint_comparison_does_not_assert_cause(self):
        before = {"default_render": {k: {"endpoint_id": "a"} for k in ("console", "multimedia", "communications")}}
        after = copy.deepcopy(before)
        self.assertEqual(compare_defaults(before, after)["status"], "UNCHANGED")
        after["default_render"]["console"]["endpoint_id"] = "b"
        self.assertEqual(compare_defaults(before, after)["roles"]["console"]["status"], "CHANGED_CAUSE_UNDETERMINED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
