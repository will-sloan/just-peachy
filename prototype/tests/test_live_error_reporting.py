"""Preserve originating failures through live cleanup. See tests/README.md."""
from pathlib import Path
import queue
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'vendor')]
from app.buffers import MemoryJournal
from app.controller import Controller


class LiveErrorReportingTests(unittest.TestCase):
    def test_journal_retains_primary_failure_through_cleanup(self):
        journal = MemoryJournal(reserve_sec=1)
        journal.finish('primary timing failure')
        journal.finish('secondary source closure')
        journal.finish()
        self.assertEqual(journal.fatal_error, 'primary timing failure')

    def test_controller_shows_lane_failure_instead_of_shutdown_symptom(self):
        controller = Controller.__new__(Controller)
        controller.epoch = 1; controller.error = None; controller.state = 'RUNNING'
        controller.metrics = {'events_consumed': 0, 'completed_sessions': 0}
        controller.models = SimpleNamespace(asr_loads=1, speaker_loads=0, streams=1)
        events = queue.Queue()
        events.put(SimpleNamespace(event_type='failure', payload={'reason': 'primary timing failure'}))
        events.put(SimpleNamespace(event_type='fatal', payload={'reason': 'secondary source closure'}))
        engine = SimpleNamespace(events=events, _finalization_thread=SimpleNamespace(is_alive=lambda: False),
            record_s6d_consumer_closure=lambda reason: None, session_dir='synthetic', state='FAILED',
            telemetry=lambda: {}, _research_gallery=None, _finalization_error=None)
        controller._consume(engine, 1)
        self.assertEqual(controller.state, 'ERROR')
        self.assertEqual(controller.error, 'primary timing failure')


if __name__ == '__main__':
    unittest.main()
