"""Accounting conservation/error/concurrency checks; README_COMPONENT_COSTS_V1.md."""
import threading
import unittest
from types import SimpleNamespace
from component_costs_v1 import CallCosts, KEYS


class CounterTests(unittest.TestCase):
    def test_zero_output_error_and_elapsed(self):
        wall=iter((1., 3., 4., 9.)); cpu=iter((10., 11., 20., 22.))
        c=CallCosts(lambda: next(wall), lambda: next(cpu))
        value=SimpleNamespace(probabilities=[])
        self.assertIs(c.call('diarizer_push',lambda: value,samples=160),value)
        error=RuntimeError('fixture')
        def fail():raise error
        with self.assertRaises(RuntimeError) as caught:c.call('asr_accept',fail,samples=80)
        self.assertIs(caught.exception,error)
        rows=c.snapshot()['rows']
        self.assertEqual(rows['diarizer_push']['zero_output_calls'],1)
        self.assertEqual(rows['diarizer_push']['successful_samples'],160)
        r=rows['asr_accept']
        self.assertEqual((r['completed'],r['errors'],r['attempted_samples'],r['successful_samples']),(1,1,80,0))
        self.assertEqual((r['wall_seconds'],r['calling_thread_cpu_seconds']),(5.,2.))

    def test_bounded_concurrent_snapshot(self):
        c=CallCosts();ready=threading.Event();release=threading.Event()
        def blocked():ready.set();release.wait(2);return 17
        worker=threading.Thread(target=lambda:c.call('embedding',blocked,samples=8000))
        worker.start();self.assertTrue(ready.wait(2))
        snap=c.snapshot();self.assertEqual(snap['rows']['embedding']['in_flight'],1)
        snap['rows']['embedding']['started']=999
        release.set();worker.join(2);self.assertFalse(worker.is_alive())
        for _ in range(1000):c.call('asr_accept',lambda:None,samples=320)
        rows=c.snapshot()['rows'];self.assertEqual(set(rows),set(KEYS))
        self.assertEqual(rows['asr_accept']['successful_samples'],320000)
        self.assertEqual((rows['embedding']['started'],rows['embedding']['in_flight']),(1,0))

    def test_native_frames_and_validation(self):
        c=CallCosts()
        c.call('diarizer_finish',lambda:SimpleNamespace(probabilities=[[],[],[]]))
        self.assertEqual(c.snapshot()['rows']['diarizer_finish']['output_frames'],3)
        with self.assertRaises(ValueError):c.call('unbounded_key',lambda:None)
        with self.assertRaises(ValueError):c.call('embedding',lambda:None,samples=-1)


if __name__=='__main__':unittest.main()
