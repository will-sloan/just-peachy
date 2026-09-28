"""Saved-source lane fragmentation regressions; README_STABLE_ASR_CHUNKS_V1.md."""
from types import SimpleNamespace
import unittest
import numpy as np
from app.n3_pipeline import StreamingASRLane


class FragmentationTests(unittest.TestCase):
    def run_lane(self,fragments,*,gain=1.,fail_after=None):
        samples=np.arange(3377,dtype=np.float32)/32768
        sizes=iter(fragments);emitted=[];failures=[]
        class Journal:
            finished=False;committed_samples=len(samples);duration_sec=len(samples)/16000
            def read(self,cursor,count):
                limit=next(sizes,count)
                block=samples[cursor:cursor+min(count,limit)]
                if cursor+len(block)==len(samples):self.finished=True
                if fail_after is not None and cursor>=fail_after:lane._state='FAILED'
                return block
        class Stream:
            input_samples=0;decode_ms=0.;padding_seconds=0.;closed=False
            def __init__(self):self.blocks=[]
            def feed(self,x):
                self.blocks.append(x.copy());self.input_samples+=len(x)
                return [dict(raw_text='fixture',final=True,utterance=len(self.blocks)-1,input_end_sec=self.input_samples/16000)]
            def finish_events(self):return []
            def close(self):self.closed=True
        lane=StreamingASRLane();lane._state='RUNNING';lane._journal=Journal()
        lane.config=SimpleNamespace(sample_rate=16000,journal_read_ms=100,input_gain=gain,partial_display_min_interval_sec=0.)
        lane._research_profile=SimpleNamespace(xvf=SimpleNamespace(mode='none'))
        lane._started_monotonic=0.;lane._research_asr_available_sec=0.;lane._telemetry={};lane._research_v2=False
        lane.resident=SimpleNamespace(asr_document={'variant':'test-no-model'})
        lane._emit=lambda *args:None
        lane._publish_final=lambda asr,text,at,index,ms:emitted.append((text,at,index))
        lane._fail=failures.append
        stream=Stream();lane._asr_loop(stream)
        return stream,emitted,failures,samples

    def test_arbitrary_reads_and_empty_wakes_match_full_blocks(self):
        fragmented,events,errors,samples=self.run_lane([0,320,0,320,7,313,640,11,989,100,0,500,177])
        contiguous,reference,other_errors,_=self.run_lane([1600,1600,177])
        self.assertEqual(errors,[]);self.assertEqual(other_errors,[])
        self.assertEqual([len(b) for b in fragmented.blocks],[1600,1600,177])
        self.assertEqual(events,reference);self.assertTrue(fragmented.closed)
        np.testing.assert_array_equal(np.concatenate(fragmented.blocks),samples)
        for a,b in zip(fragmented.blocks,contiguous.blocks):np.testing.assert_array_equal(a,b)

    def test_gain_applied_once_after_gather(self):
        stream,_,errors,samples=self.run_lane([320]*11,gain=2.)
        self.assertEqual(errors,[])
        np.testing.assert_array_equal(np.concatenate(stream.blocks),samples*np.float32(2))

    def test_failure_during_gather_is_not_silent_completion(self):
        stream,_,errors,_=self.run_lane([320]*11,fail_after=320)
        self.assertEqual(stream.input_samples,0);self.assertTrue(stream.closed)
        self.assertEqual(len(errors),1);self.assertIn('session failure',errors[0])


if __name__=='__main__':unittest.main()
