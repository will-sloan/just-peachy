"""Hardware-blocked campaign startup and backend contracts. See README_N1.md."""
from pathlib import Path
import sys
import tempfile
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.controller import Controller
from app.backends import BASELINE_BACKEND_ID, backend_catalog


class SafeStartTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='n1-safe-start-');self.addCleanup(self.temp.cleanup)
        self.no_audio=patch('app.windows_audio.endpoint_snapshot',side_effect=AssertionError('Audio enumeration forbidden'))
        self.no_audio.start();self.addCleanup(self.no_audio.stop)
        self.controller=Controller(Path(self.temp.name)/'data',Path(self.temp.name)/'models',saved_audio_only=True)
        self.addCleanup(self.finish)

    def finish(self):
        c=self.controller
        if not c.closed:c.close();c.commands.join();c.worker.join(10)

    def test_idle_start_does_not_touch_hardware_or_models(self):
        c=self.controller
        self.assertEqual(c.state,'IDLE');self.assertIsNone(c.imu)
        self.assertEqual(c.models.asr_loads,0);self.assertEqual(c.models.speaker_loads,0)
        with self.assertRaisesRegex(RuntimeError,'disabled'):c.start_live(consent=True)
        with self.assertRaisesRegex(RuntimeError,'disabled'):c.enrollment_start('Fixture',consent=True)
        self.assertEqual(c.snapshot()['backend_id'],BASELINE_BACKEND_ID)

    def test_backend_selection_is_independent_and_unimplemented_cannot_load(self):
        c=self.controller;old=(c.mode,c.recipe,c.tap)
        candidate=next(b for b in backend_catalog() if not b['implemented'])
        c.select_backend(candidate['manifest_id']);c.commands.join()
        self.assertEqual((c.mode,c.recipe,c.tap),old);self.assertEqual(c.state,'IDLE')
        self.assertFalse(c.snapshot()['backend']['available'])
        c.source_kind='file'
        with self.assertRaises(ValueError):c._start_session()
        self.assertEqual(c.models.asr_loads,0)
        c.select_backend(BASELINE_BACKEND_ID);c.commands.join()
        self.assertTrue(c.snapshot()['backend']['available'])

    def test_gui_receipts_are_bounded_and_persist_first_application_separately(self):
        c=self.controller
        session=Path(self.temp.name)/'session';session.mkdir()
        c.engine=SimpleNamespace(session_dir=session)
        try:
            for serial in range(260):
                c.record_presentation({'span_ids':['word-1'],'label':'Pending' if serial==0 else 'Alex',
                    'applied_monotonic_sec':float(serial),'first_gui_labels':{'word-1':'Pending'}})
            self.assertEqual(len(c.metrics['gui_presentation_recent']),256)
            lines=(session/'gui_presentation.jsonl').read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(lines),260)
            self.assertEqual(json.loads(lines[0])['label'],'Pending')
            self.assertIn('not measured',json.loads(lines[-1])['scope'])
        finally:c.engine=None


if __name__=='__main__':unittest.main()
