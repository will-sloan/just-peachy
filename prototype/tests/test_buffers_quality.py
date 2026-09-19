"""Bounded storage/audio regression and incremental evidence tests. See README.md."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
import numpy as np
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'vendor')]
from app.buffers import MemoryJournal,AudioGap,AsyncText
from app.enrollment_quality import EnrollmentQuality


class Models:
    def __init__(self):self.segment_calls=self.embed_calls=0
    def segment(self,a,include_posteriors=True):
        self.segment_calls+=1
        return {'speech':np.ones(100),'overlap':np.zeros(100)}
    def embed(self,a):
        self.embed_calls+=1;v=np.zeros(192,np.float32);v[0]=1;return v


class BufferTests(unittest.TestCase):
    def test_two_independent_cursors_and_explicit_overflow(self):
        j=MemoryJournal(sample_rate=100,reserve_sec=2)
        j.append(np.arange(120,dtype=np.float32));np.testing.assert_equal(j.read(0,100),np.arange(100))
        np.testing.assert_equal(j.read(0,120),np.arange(120))
        j.append(np.arange(120,270,dtype=np.float32))
        with self.assertRaises(AudioGap):j.read(0,10)
        np.testing.assert_equal(j.read(100,170),np.arange(100,270))
        j.finish();self.assertEqual(j.read(270,10).size,0)

    def test_slow_disk_does_not_block_audio_or_event_producer(self):
        with tempfile.TemporaryDirectory() as d:
            writer=AsyncText(Path(d)/'events.jsonl',capacity=1024,delay_once=.35)
            journal=MemoryJournal(sample_rate=16000,reserve_sec=2)
            started=time.perf_counter()
            for i in range(100):writer.write(str(i)+'\n');journal.append(np.full(320,i,np.float32))
            elapsed=time.perf_counter()-started
            self.assertLess(elapsed,.25)
            np.testing.assert_equal(journal.read(31680,320),np.full(320,99,np.float32))
            writer.close();self.assertEqual(writer.completed,100)

    def test_journal_overflow_explicit_no_silent_drop(self):
        with tempfile.TemporaryDirectory() as d:
            writer=AsyncText(Path(d)/'events.jsonl',capacity=1,delay_once=.15)
            failed=False
            for i in range(100):
                try:writer.write('final or error record\n')
                except RuntimeError:failed=True;break
            self.assertTrue(failed);writer.close();self.assertEqual(writer.accepted,writer.completed)

    def test_incremental_unique_evidence_no_repeated_embedding(self):
        from types import SimpleNamespace
        models=Models();quality=EnrollmentQuality(models,SimpleNamespace(minimum_rms=.002),15)
        quality.process(np.full(160000,.05,np.float32));quality.process(np.full(80000,.05,np.float32))
        result,v=quality.result()
        self.assertEqual(models.segment_calls,2);self.assertEqual(models.embed_calls,30)
        self.assertEqual(result['usable_s'],15);self.assertTrue(result['can_save'])
        self.assertFalse(quality.result(gaps=1)[0]['can_save'])
        self.assertEqual(result['accepted_intervals'][-1],[14.5,15.])

    def test_silence_clipping_and_overlap_do_not_fill_target(self):
        from types import SimpleNamespace
        m=Models();q=EnrollmentQuality(m,SimpleNamespace(minimum_rms=.002),15)
        q.process(np.zeros(160000,np.float32));q.process(np.ones(160000,np.float32))
        self.assertEqual(q.result()[0]['usable_s'],0);self.assertFalse(q.result()[0]['can_save'])


if __name__=='__main__':unittest.main()
