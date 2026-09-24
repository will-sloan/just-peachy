"""Sample/clock regressions and failure drainage; see README_LIVE_TIMING.md."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import numpy as np

from app.live_audio import LiveBlock, StreamingDecimator
from app.live_timing import CaptureTimeline, LiveTimingError
from edge_speech_pipeline.runtime import PipelineEngine


def block(native_start=0,n=480,callback=100_110_000_000,**kw):
    m0=(native_start+2)//3;m1=(native_start+n+2)//3
    data=dict(audio=np.zeros(m1-m0,np.float32),model_start_sample=m0,
        native_start_frame=native_start,native_frames=n,callback_monotonic_ns=17,
        adc_time_seconds=100.22,delivery_monotonic_ns=18,
        resampler_delay_seconds=.001,source_lag_seconds=0,epoch=7,
        callback_perf_counter_ns=callback,callback_current_time_seconds=100.11,
        priming_native_frames=0)
    data.update(kw)
    return LiveBlock(**data)


class LiveTimingTests(unittest.TestCase):
    def test_old_path_rejects_valid_delayed_first_callback_but_frame_bound_passes(self):
        # Eleven fixed callbacks per 110ms WASAPI packet. The first callback
        # was delayed 25ms; a later packet was not. No missing samples.
        first=block(callback=100_135_000_000)
        clock=CaptureTimeline({'stream_start_perf_counter_ns':100_000_000_000},first)
        old_origin=first.callback_perf_counter_ns/1e9-.11
        for i in range(22):
            b=block(i*480,callback=100_135_000_000 if i<11 else 100_220_000_000)
            clock.accept(b,b.callback_perf_counter_ns)
        self.assertGreater(clock.model_end/16000-(100.220-old_origin),.024)
        self.assertEqual((clock.native_end,clock.model_end),(10560,3520))
        self.assertEqual(clock.start_ns,100_000_000_000)

    def test_priming_count_is_distinct_and_fixed(self):
        b=block(callback=100_510_000_000,priming_native_frames=24000)
        clock=CaptureTimeline({'stream_start_perf_counter_ns':100_000_000_000},b)
        clock.accept(b,b.callback_perf_counter_ns)
        self.assertAlmostEqual(clock.native_origin,100.5)
        with self.assertRaisesRegex(LiveTimingError,'priming origin'):
            clock.accept(block(480,callback=100_520_000_000,priming_native_frames=24001),100_530_000_000)

    def test_irregular_sizes_final_partial_and_real_decimator_exact_samples(self):
        converter=StreamingDecimator();n0=0;m0=0;expected=[];actual=[]
        sizes=[1,2,479,121,960,17,481,1]
        source=np.sin(np.arange(sum(sizes),dtype=np.float32)*.05)
        clock=CaptureTimeline({'stream_start_perf_counter_ns':100_000_000_000},block())
        for n in sizes:
            out=converter.convert(source[n0:n0+n]);actual.extend(out)
            stamp=100_000_000_000+((n0+n)*1_000_000_000+47999)//48000
            b=block(n0,n,stamp,audio=out,model_start_sample=m0)
            clock.accept(b,stamp)
            self.assertLessEqual((m0+len(out))/16000,stamp/1e9-clock.origin+1e-12)
            n0+=n;m0+=len(out)
        one=StreamingDecimator().convert(source)
        np.testing.assert_allclose(actual,one,rtol=0,atol=1e-7)
        self.assertEqual(clock.model_end,(n0+2)//3)

    def test_consumer_delay_cannot_hide_impossible_callback(self):
        b=block(n=960,callback=100_010_000_000)
        clock=CaptureTimeline({'stream_start_perf_counter_ns':100_000_000_000},b)
        with self.assertRaisesRegex(LiveTimingError,'ahead'):
            clock.accept(b,110_000_000_000)
        self.assertEqual(clock.model_end,0)
        self.assertEqual(clock.rows[-1]['native_lead_ns'],10_000_000)

    def test_discontinuity_duplicate_epoch_clock_and_resampler_mismatch_fail(self):
        changes=[{'native_start_frame':1}, {'model_start_sample':1},
            {'epoch':8}, {'callback_perf_counter_ns':99_000_000_000},
            {'audio':np.zeros(159,np.float32)}]
        for change in changes:
            clock=CaptureTimeline({'stream_start_perf_counter_ns':100_000_000_000},block())
            with self.subTest(change=change.keys()),self.assertRaises(LiveTimingError):
                clock.accept(replace(block(),**change),101_000_000_000)

    def test_invalid_priming_gap_fails_and_trace_is_bounded(self):
        with self.assertRaisesRegex(LiveTimingError,'priming discontinuity'):
            CaptureTimeline({'stream_start_perf_counter_ns':100_000_000_000,'priming_status_events':1},block())
        clock=CaptureTimeline({'stream_start_perf_counter_ns':100_000_000_000},block())
        for i in range(100):
            stamp=100_000_000_000+(i+1)*10_000_000
            clock.accept(block(i*480,callback=stamp),stamp+5_000_000_000)
        self.assertEqual(len(clock.snapshot()['recent_blocks']),64)

    def test_failed_source_stop_still_drains_lanes_and_closes_handles(self):
        # Exercise the real watcher after an already-reported source failure.
        # The pre-fix watcher raises at stop(), skipping these joins/finish.
        worker=SimpleNamespace(join=Mock(),is_alive=lambda:False,name='fixture-asr')
        scheduler=SimpleNamespace(finish=Mock(),snapshot=lambda:{},worker=None)
        writer=SimpleNamespace(close=Mock(),closed=True)
        engine=SimpleNamespace(_state='FAILED',_journal=SimpleNamespace(finished=True),
            _source=SimpleNamespace(stop=Mock(side_effect=RuntimeError('original timing error'))),
            _threads=[worker],_research_v3=False,_research_v2=True,_scheduler=scheduler,
            _s6d_punctuation=None,_s6d_writer=None,_bundle_acquired=False,
            _finalization_error=None,_telemetry={},_write_revised_transcript=Mock(),
            _write_summary=Mock(),_event_handle=writer,_transcript_handle=None,
            _readable_transcript_handle=None,_fail=Mock())
        PipelineEngine._watch_session(engine)
        worker.join.assert_called_once();scheduler.finish.assert_called_once()
        engine._write_revised_transcript.assert_called_once();writer.close.assert_called_once()
        self.assertEqual(engine._state,'FAILED')
        self.assertEqual(str(engine._finalization_error),'original timing error')


if __name__=='__main__':unittest.main()
