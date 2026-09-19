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
        self.callback_ns=time.monotonic_ns()-700_000_000

    def start(self,consent):
        assert consent is True
        if self.start_error:raise RuntimeError(self.start_error)
        return self.metadata

    def read(self, timeout):
        if self.read_count:
            self.finished=True
            return None
        self.read_count+=1
        return LiveBlock(np.zeros(160,np.float32),0,0,480,self.callback_ns,0,time.monotonic_ns(),.001,.7)

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
