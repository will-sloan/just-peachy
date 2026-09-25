"""Portable stream sample/tail/control tests without models; README_A1_PORTABLE.md."""
import unittest
import numpy as np
from a1_onnx_v2 import OnnxRecognizer,Result


class StreamTests(unittest.TestCase):
    def owner(self,text=''):
        class Service:
            def reset_state(s):s.calls=[]
            def transcribe(s,pcm):
                s.calls.append(pcm);return Result(text if len(s.calls)==1 else '',len(s.calls)==1 and '<EOU>' in text)
        owner=OnnxRecognizer.__new__(OnnxRecognizer);owner.service=Service();owner.active=None;owner.serial=0
        return owner

    def test_empty_stream_does_not_decode_or_invent_padding(self):
        owner=self.owner();stream=owner.stream()
        self.assertEqual(stream.feed(np.empty(0,np.float32)),[])
        self.assertEqual(stream.finish_events(),[]);self.assertEqual(owner.service.calls,[])
        self.assertEqual(stream.input_samples,0);stream.close()

    def test_one_sample_has_exact_pcm_tail_and_idempotent_finish(self):
        owner=self.owner();stream=owner.stream();stream.feed(np.array([.25],np.float32))
        stream.finish_events();self.assertEqual(stream.input_samples,1)
        self.assertEqual(len(owner.service.calls),17)
        first=np.frombuffer(owner.service.calls[0],dtype='<i2')
        self.assertEqual(first[0],8192);self.assertFalse(np.any(first[1:]))
        self.assertTrue(all(not np.any(np.frombuffer(p,dtype='<i2')) for p in owner.service.calls[1:]))
        self.assertEqual(stream.finish_events(),[]);self.assertEqual(len(owner.service.calls),17)
        stream.close()
        with self.assertRaises(RuntimeError):stream.feed(np.zeros(1,np.float32))

    def test_words_on_both_sides_of_eou_and_exact_replay_are_preserved(self):
        owner=self.owner('alpha<EOU>beta');results=[]
        for _ in range(2):
            stream=owner.stream();rows=stream.feed(np.zeros(1280,np.float32));rows+=stream.finish_events()
            results.append([(r['raw_text'],r['final'],r.get('control_token')) for r in rows]);stream.close()
        self.assertEqual(results[0],results[1])
        self.assertEqual([r[0] for r in results[0] if r[1]],['alpha','beta'])


if __name__=='__main__':unittest.main(verbosity=2)
