"""Native bridge lifecycle/clock tests with mock capture; no models or microphone."""
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'vendor'))
from app.pipeline import LivePipelineSource
from app.buffers import MemoryJournal
from app.live_audio import LiveBlock


class FakeLive:
    def __init__(self, config):
        self.metadata={'route':{'tap':'O0','host_gain_db':3},'endpoint':{'endpoint_id':'test-only'}}
        self.finished=False;self.read_count=0;self.close_count=0
        self.start_error=config.get('start_error')
        self.stop_error=config.get('stop_error')
        self.block_count=config.get('block_count',1)
        self.current_time=config.get('current_time')
        self.adc_time=config.get('adc_time',0)
        delay_ns=int(config.get('reader_delay',.7)*1e9)
        self.callback_ns=time.monotonic_ns()-delay_ns
        self.callback_perf_ns=time.perf_counter_ns()-delay_ns
        self.metadata['actual_latency']=config.get('actual_latency',.11)
        self.metadata['stream_start_perf_counter_ns']=(self.callback_perf_ns-110_000_000
            if not config.get('no_start_clock') else None)

    def start(self,consent):
        assert consent is True
        if self.start_error:raise RuntimeError(self.start_error)
        return self.metadata

    def read(self, timeout):
        if self.read_count>=self.block_count:
            self.finished=True
            return None
        i=self.read_count
        self.read_count+=1
        return LiveBlock(np.zeros(160,np.float32),i*160,i*480,480,self.callback_ns,
                         self.adc_time+i*.01,time.monotonic_ns(),.001,.7,
                         callback_perf_counter_ns=self.callback_perf_ns,
                         callback_current_time_seconds=self.current_time)

    def status(self):return {'finished':self.finished}

    def stop(self):
        self.close_count+=1;self.finished=True
        if self.stop_error:raise RuntimeError(self.stop_error)
        return {'route_restoration':{}}


class BridgeTests(unittest.TestCase):
    def make(self, config=None):
        self.addCleanup(patch.stopall)
        patch('app.live_audio.XVFLiveSource',FakeLive).start()
        patch('app.live_audio.summarize_live_integrity',return_value={'ok':True,'reasons':[]}).start()
        events=[];journal=MemoryJournal(reserve_sec=1)
        bridge=LivePipelineSource(journal,config or {},lambda kind,data:events.append((kind,data)))
        return bridge,journal,events

    def test_verified_metadata_and_callback_clock_survive_bridge(self):
        source,journal,events=self.make();source.start()
        self.assertTrue(source.wait(3));source.stop()
        started=next(data for kind,data in events if kind=='source_started')
        self.assertEqual(started['route']['host_gain_db'],3)
        self.assertEqual(started['endpoint']['endpoint_id'],'test-only')
        self.assertGreater(time.perf_counter()-started['source_epoch_monotonic_sec'],.6)
        self.assertEqual(started['first_block_source_lag_sec'],.7)
        self.assertEqual(journal.committed_samples,160)
        self.assertTrue(journal.finished)
        self.assertFalse(source.thread.is_alive())
        self.assertEqual(source.live.close_count,1)

    def test_wasapi_buffered_packet_burst_uses_adc_age_not_block_duration(self):
        # Eleven 10ms callbacks arrive together from one 110ms host packet.
        # The old first-callback-minus-10ms epoch rejected the second block.
        source,journal,events=self.make({'block_count':11,'reader_delay':.002,
            'current_time':50.11,'adc_time':50.0})
        source.start();self.assertTrue(source.wait(3));source.stop()
        started=next(data for kind,data in events if kind=='source_started')
        self.assertEqual(journal.committed_samples,1760)
        self.assertIsNone(journal.fatal_error)
        self.assertEqual(started['source_clock_method'],'stream_start_counted_native_frames')
        expected=(source.live.callback_perf_ns-110_000_000)/1e9-2/48000
        self.assertAlmostEqual(started['source_epoch_monotonic_sec'],expected,places=8)
        self.assertGreaterEqual(time.perf_counter()-expected,journal.duration_sec)

    def test_missing_driver_timestamps_use_stream_frame_bound(self):
        source,journal,events=self.make()
        source.start();self.assertTrue(source.wait(3));source.stop()
        started=next(data for kind,data in events if kind=='source_started')
        self.assertEqual(started['source_clock_method'],'stream_start_counted_native_frames')
        self.assertIn('not_acoustic',started['source_clock_confidence'])
        self.assertIn('diagnostic_only',started['reported_latency_role'])

    def test_invalid_driver_timestamps_cannot_claim_adc_timing(self):
        for adc in (51.0,float('nan'),0):
            source,journal,events=self.make({'current_time':50.11,'adc_time':adc})
            source.start();self.assertTrue(source.wait(3));source.stop()
            started=next(data for kind,data in events if kind=='source_started')
            self.assertEqual(started['source_clock_method'],'stream_start_counted_native_frames')

    def test_no_valid_clock_fails_without_clamping_or_admitting_audio(self):
        source,journal,events=self.make({'actual_latency':None,'no_start_clock':True})
        source.start();self.assertTrue(source.wait(3))
        self.assertEqual(journal.committed_samples,0)
        self.assertIn('missing stream-start',journal.fatal_error)

    def test_impossible_later_burst_fails_without_rebasing_epoch(self):
        source,journal,events=self.make({'block_count':30,'reader_delay':.001,
            'current_time':50.11,'adc_time':50.0})
        source.start();self.assertTrue(source.wait(3))
        self.assertLess(journal.committed_samples,4800)
        self.assertIn('ahead of stream-start frame bound',journal.fatal_error)
        self.assertEqual(sum(kind=='source_started' for kind,_ in events),1)

    def test_primary_lane_failure_survives_secondary_closed_journal(self):
        source,journal,events=self.make()
        original=source.callback
        def close_on_start(kind,data):
            original(kind,data)
            if kind=='source_started':journal.finish('ASR lane failed: original timing failure')
        source.callback=close_on_start
        source.start();self.assertTrue(source.wait(3))
        self.assertEqual(journal.fatal_error,'ASR lane failed: original timing failure')
        fatal=next(data for kind,data in events if kind=='fatal')
        self.assertEqual(fatal['reason'],journal.fatal_error)
        self.assertIn('Audio arrived after source closure',fatal['secondary_errors'])

    def test_start_failure_closes_source_and_journal(self):
        source,journal,events=self.make({'start_error':'test startup failure'})
        with self.assertRaisesRegex(RuntimeError,'startup failure'):source.start()
        self.assertTrue(source.wait(.1));self.assertTrue(journal.finished)
        self.assertTrue(source.live.finished)
        self.assertEqual(source.live.close_count,1)
        self.assertIn('startup failure',journal.fatal_error)

    def test_stop_failure_is_not_successful_completion(self):
        source,journal,events=self.make({'stop_error':'test restore failure'})
        source.start();self.assertTrue(source.wait(3))
        with self.assertRaisesRegex(RuntimeError,'restore failure'):source.stop()
        self.assertFalse(source.thread.is_alive())
        self.assertIn('restore failure',journal.fatal_error)
        self.assertTrue(any(kind=='fatal' for kind,data in events))


if __name__=='__main__':unittest.main(verbosity=2)
