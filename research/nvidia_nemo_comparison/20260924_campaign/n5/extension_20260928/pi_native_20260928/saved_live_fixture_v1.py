"""Saved-input substitute for the live adapter, never hardware. See README_B01_LIVE_CONTROLLER_V1.md."""
import copy
import hashlib
import json
import threading
import time
from pathlib import Path


def install(L, root):
    import numpy as np
    import soundfile as sf
    from unittest.mock import patch
    metadata = json.loads((root/'ROUTE_FIXTURE.json').read_text())
    class SavedLiveFixture:
        fixture_only = True
        def __init__(self, config):
            self.config = config
            self.lease = None
            self.beam_diagnostics = None
            self.stop_event = threading.Event()
            self.converter = L.StreamingDecimator()
            self.sent = self.native = self.calls = 0
            self.work = 0.
            self.digest = hashlib.sha256()
            self.input_digest = hashlib.sha256()
            self.handle = None
            self.finished = False
        def start(self, consent=False):
            assert consent is True
            self.handle = sf.SoundFile(root/'source.wav')
            assert self.handle.samplerate == 16000 and self.handle.channels == 1
            self.start_ns = time.perf_counter_ns()
            value = copy.deepcopy(metadata)
            value.update(stream_start_perf_counter_ns=self.start_ns,priming_status_events=0,
                         fixture_only=True,actual_hardware_opened=False)
            value['route']['fixture_only'] = True
            return value
        def read(self, timeout=.25):
            if self.stop_event.is_set() or self.finished:
                return None
            raw = self.handle.read(160,dtype='float32')
            if not len(raw):
                self.finished = True
                return None
            # Original 1x source pacing, actual host timestamps, no clock mocking.
            target = self.start_ns/1e9+(self.sent+len(raw))/16000
            if self.stop_event.wait(max(0.,target-time.perf_counter())):
                return None
            expanded = np.repeat(raw,3)
            before = time.perf_counter()
            audio = self.converter.convert(expanded)
            self.work += time.perf_counter()-before
            callback = time.perf_counter_ns()
            block = L.LiveBlock(audio=audio,model_start_sample=self.sent,native_start_frame=self.native,
                native_frames=len(expanded),callback_monotonic_ns=time.monotonic_ns(),
                adc_time_seconds=self.native/48000,delivery_monotonic_ns=time.monotonic_ns(),
                resampler_delay_seconds=.001,source_lag_seconds=max(0.,callback/1e9-target),
                epoch=0,callback_perf_counter_ns=callback,callback_current_time_seconds=(self.native+len(expanded))/48000,
                priming_native_frames=0)
            self.sent += len(audio)
            self.native += len(expanded)
            self.calls += 1
            self.digest.update(audio.tobytes())
            self.input_digest.update(expanded.tobytes())
            assert self.converter.native_count==self.native==self.sent*3
            return block
        @property
        def conversion(self):
            return dict(native_samples=self.native,model_samples=self.sent,calls=self.calls,
                work_seconds=self.work,output_float32_sha256=self.digest.hexdigest(),
                input_float32_sha256=self.input_digest.hexdigest(),filter_delay_seconds=.001,
                constructed_only=True,no_appended_tail=True,fixture_only=True)
        def status(self):
            return dict(finished=self.finished,converted_samples=self.sent,dropped_frames=0,
                fault=None,fixture_only=True,priming_frames_discarded_before_route_verified=0)
        def stop(self):
            self.stop_event.set()
            self.finished = True
            if self.handle is not None:
                self.handle.close()
            return dict(status=self.status(),errors=[],commands=[],route_restoration={},fixture_only=True)
    def integrity(source):
        assert isinstance(source,SavedLiveFixture)
        return dict(ok=source.finished,reasons=[] if source.finished else ['FIXTURE_NOT_CLOSED'],
            restoration_ok=True,restoration_issues=[],fixture_only=True,actual_hardware_tested=False)
    # Both patches are deliberately narrow; the real LivePipelineSource,
    # CaptureTimeline, controller, model workers and drainage are exercised.
    return [patch.object(L,'XVFLiveSource',SavedLiveFixture),patch.object(L,'summarize_live_integrity',integrity)]
