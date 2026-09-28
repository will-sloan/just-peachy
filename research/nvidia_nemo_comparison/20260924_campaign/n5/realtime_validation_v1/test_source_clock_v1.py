"""Causal delivery and source-accounting regressions; README_SOURCE_CLOCK_V1.md."""
import unittest
from source_clock_v1 import Release, schedule, deliver


class FakeClock:
    def __init__(self): self.now = 0.0
    def read(self): return self.now
    def sleep(self, seconds): self.now += seconds


class ClockTests(unittest.TestCase):
    def test_final_partial_and_empty_source(self):
        rows = list(schedule(3201))
        self.assertEqual([(r.start_sample,r.end_sample) for r in rows], [(0,1600),(1600,3200),(3200,3201)])
        self.assertAlmostEqual(rows[-1].deadline_seconds, 3201/16000)
        self.assertEqual(list(schedule(0)), [])

    def test_jitter_never_releases_future_audio_or_reorders(self):
        rows = list(schedule(16000, mode='jitter'))
        self.assertTrue(all(r.deadline_seconds >= r.end_sample/16000 for r in rows))
        self.assertEqual([r.deadline_seconds for r in rows], sorted(r.deadline_seconds for r in rows))

    def test_bursts_wait_for_source_and_preserve_samples(self):
        rows = list(schedule(48001, mode='burst'))
        self.assertEqual(rows[0].deadline_seconds, 2)
        self.assertEqual(rows[-1].deadline_seconds, 4)
        self.assertEqual(sum(r.end_sample-r.start_sample for r in rows), 48001)

    def test_slow_consumer_lateness_does_not_accumulate_sleep_drift(self):
        clock = FakeClock(); actual = []
        def consume(row, available):
            actual.append(available)
            if len(actual) == 1: clock.now += .25
        deliver(schedule(4800), consume, clock=clock.read, sleep=clock.sleep)
        self.assertAlmostEqual(actual[0], .1)
        self.assertAlmostEqual(actual[1], .35)
        self.assertAlmostEqual(actual[2], .35)

    def test_early_wakeup_still_waits_until_due(self):
        clock = FakeClock(); observed = []
        deliver(schedule(1600), lambda r,t: observed.append(t), clock=clock.read,
                sleep=lambda s: clock.sleep(s/2 if s>.0001 else s))
        self.assertGreaterEqual(observed[0], .1)

    def test_cancellation_does_not_publish_pending_audio(self):
        clock = FakeClock(); actual=[]
        deliver(schedule(16000), lambda r,t: actual.append(t), clock=clock.read,
                sleep=clock.sleep, cancelled=lambda: clock.now >= .05)
        self.assertEqual(actual, [])

    def test_invalid_inputs_and_discontinuous_delivery_refused(self):
        for kwargs in [dict(frames=-1),dict(frames=True),dict(frames=1,speed=0),
                       dict(frames=1,speed=float('nan')),dict(frames=1,jitter=(-1,))]:
            with self.assertRaises(ValueError):list(schedule(**kwargs))
        with self.assertRaises(ValueError):
            deliver([Release(1,2,0)], lambda r,t: None)

    def test_accelerated_replay_is_explicit_not_1x(self):
        a=list(schedule(16000,speed=1)); b=list(schedule(16000,speed=2))
        self.assertEqual(a[-1].deadline_seconds,1)
        self.assertEqual(b[-1].deadline_seconds,.5)


if __name__ == '__main__': unittest.main()
