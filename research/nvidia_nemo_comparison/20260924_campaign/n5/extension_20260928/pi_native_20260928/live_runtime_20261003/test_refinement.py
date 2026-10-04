"""Injected-worker checks; no native admission is created. See README_PIPELINES.md."""
import threading
import time
import unittest

from correction import CaptionLedger, SampleInterval, SpeakerSpan
from profiles import RuntimeSelection
from refinement import RefinementCoordinator


def interval(start, end):
    return SampleInterval("test-session", "same-audio", start, end, 100)


class RefinementTests(unittest.TestCase):
    def setup_coordinator(self, worker, *, clock=time.monotonic):
        ledger = CaptionLedger("test-session", "same-audio", sample_rate=100)
        ledger.advance(200)
        selection = RuntimeSelection("nemotron", "anonymous", "saved", "official_very_low",
                                     True, True, "current_delayed")
        coordinator = RefinementCoordinator(ledger, selection, worker, source_pin="a" * 64, clock=clock)
        return ledger, coordinator

    def test_primary_never_waits_for_blocked_optional_worker_and_coalesces(self):
        entered, release = threading.Event(), threading.Event()
        def worker(job):
            entered.set()
            release.wait(2)
            return []
        ledger, coordinator = self.setup_coordinator(worker)
        coordinator.start()
        now = time.monotonic()
        self.assertTrue(coordinator.offer(interval(0, 150), now=now, deadline=now + 10))
        self.assertTrue(entered.wait(1))
        try:
            # Text result is obtained while the worker demonstrably cannot finish.
            result = coordinator.emit_primary(1, interval(0, 50), "Immediate text")
            self.assertFalse(release.is_set())
            self.assertEqual(result[0]["event"], "caption_added")
            self.assertTrue(coordinator.offer(interval(50, 180), now=time.monotonic(), deadline=now + 10))
            self.assertTrue(coordinator.offer(interval(80, 200), now=time.monotonic(), deadline=now + 10))
            self.assertEqual(coordinator.coalesced, 1)
            self.assertEqual(len(coordinator.queue.jobs), 1)
        finally:
            release.set()
            coordinator.close()

    def test_swapped_slots_keep_caption_id_and_duplicate_results_are_noops(self):
        result_ready = threading.Event()
        def worker(job):
            result_ready.set()
            return [SpeakerSpan(interval(0, 80), "B"), SpeakerSpan(interval(80, 200), "A")]
        ledger, coordinator = self.setup_coordinator(worker)
        ledger.apply_fast([SpeakerSpan(interval(0, 100), "A"), SpeakerSpan(interval(100, 200), "B")])
        first = coordinator.emit_primary(1, interval(80, 120), "same caption")[0]
        coordinator.start()
        try:
            now = time.monotonic()
            coordinator.offer(interval(0, 200), now=now, deadline=now + 10)
            self.assertTrue(result_ready.wait(1))
            # Worker completion publication is asynchronous; wait using an event
            # barrier on its lock with a bounded poll for this synthetic fixture.
            until = time.monotonic() + 1
            while not coordinator.results and time.monotonic() < until:
                time.sleep(.001)
            events = coordinator.poll(now=time.monotonic())
            revised = [v for v in events if v["event"] == "caption_revised"]
            self.assertEqual(len(revised), 1)
            self.assertEqual(revised[0]["caption_id"], first["caption_id"])
            self.assertEqual(revised[0]["speaker"], "speaker-2")
            self.assertEqual(coordinator.emit_primary(1, interval(80, 120), "same caption"), [])
            self.assertEqual(coordinator.poll(now=time.monotonic()), [])
        finally:
            coordinator.close()

    def test_stale_results_and_worker_errors_never_remove_text(self):
        ledger, coordinator = self.setup_coordinator(lambda job: [])
        first = coordinator.emit_primary(1, interval(0, 50), "preserved")[0]
        coordinator.results.append((1, "late", (), None))
        coordinator.results.append((3, "failed", (), "synthetic failure"))
        events = coordinator.poll(now=2)
        self.assertEqual(coordinator.late_results, 1)
        self.assertEqual(events[0]["event"], "refinement_failed")
        self.assertEqual(ledger.captions[first["caption_id"]]["text"], "preserved")

    def test_native_route_rejects_absent_measured_admission(self):
        ledger, coordinator = self.setup_coordinator(lambda job: [])
        with self.assertRaises(ValueError):
            RefinementCoordinator(ledger, coordinator.selection, lambda job: [],
                                  source_pin="a" * 64, native=True)


if __name__ == "__main__":
    unittest.main()
