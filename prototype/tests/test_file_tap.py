"""Prepared-file tap identity regressions; no inference/device access. See README."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor')]
from app.controller import Controller


def controller(kind='file', state='RUNNING', tap='O0'):
    c = Controller.__new__(Controller)
    c.source_kind = kind
    c.state = state
    c.tap = tap
    c.file_path = Path('O0.wav')
    c.file_offset = 1600
    c.mode = 'anonymous_conversation'
    c.recipe = 'balanced'
    c.epoch = 1
    c.selected_ids = []
    c.strict = False
    c.transitions = []
    c.store = SimpleNamespace(list=lambda: [])
    c._ensure_no_enrollment = Mock()
    c._stop_session = Mock()
    c._start_session = Mock()
    c._observe_output = Mock()
    return c


class PreparedTapTests(unittest.TestCase):
    def test_running_file_cannot_relabel_its_audio(self):
        c = controller()
        with self.assertRaisesRegex(ValueError, 'prepared.*WAV'):
            c._do_switch(None, None, 'O1', None, None)
        self.assertEqual(c.tap, 'O0')
        self.assertEqual(c.state, 'RUNNING')
        self.assertEqual(c.file_offset, 1600)
        c._stop_session.assert_not_called()
        c._start_session.assert_not_called()
        self.assertEqual(c.transitions, [])

    def test_same_file_tap_recipe_switch_remains_available(self):
        c = controller()
        with patch('soundfile.info', return_value=SimpleNamespace(frames=32000)):
            c._do_switch(None, 'patient', 'O0', None, None)
        c._stop_session.assert_called_once()
        c._start_session.assert_called_once()
        self.assertEqual(c.recipe, 'patient')

    def test_live_tap_switch_keeps_stop_restart_boundary(self):
        c = controller(kind='live')
        c._do_switch(None, None, 'O1', None, None)
        c._stop_session.assert_called_once()
        c._start_session.assert_called_once()
        self.assertEqual(c.tap, 'O1')

    def test_idle_tap_selection_does_not_start_capture(self):
        c = controller(kind=None, state='IDLE')
        c._do_switch(None, None, 'O1', None, None)
        self.assertEqual(c.tap, 'O1')
        c._start_session.assert_not_called()

    def test_known_wav_mismatch_rejected_before_engine_or_stop(self):
        for filename in ('O0.wav', 'o0.WAV', 'O0_continuous.wav'):
            with self.subTest(filename=filename):
                c = controller(tap='O1')
                with self.assertRaisesRegex(ValueError, 'O0.*O1'):
                    c._do_start_file(filename)
                c._stop_session.assert_not_called()
                c._start_session.assert_not_called()
                self.assertEqual(c.file_offset, 1600)

    def test_reverse_mismatch_also_rejected(self):
        c = controller()
        with self.assertRaisesRegex(ValueError, 'O1.*O0'):
            c._do_start_file('O1.wav')
        c._start_session.assert_not_called()

    def test_matched_prepared_file_starts_at_zero(self):
        c = controller()
        c._do_start_file('O0.wav')
        c._start_session.assert_called_once()
        self.assertEqual(c.file_offset, 0)
        self.assertEqual(c.file_path.name, 'O0.wav')

    def test_arbitrary_name_uses_explicit_declared_tap(self):
        c = controller(tap='O1')
        c._do_start_file('prepared scenario.wav')
        c._start_session.assert_called_once()
        self.assertEqual(c.tap, 'O1')


if __name__ == '__main__':
    unittest.main()
