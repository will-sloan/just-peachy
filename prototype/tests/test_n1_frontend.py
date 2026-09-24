"""Withdrawn Tk EVENT fixtures; never map a desktop window. README_N1_FRONTEND.md."""
from copy import deepcopy
import tkinter as tk
import unittest
from unittest.mock import patch

from prototype.app.backends import BASELINE_BACKEND_ID, backend_catalog, backend_status
from prototype.app.caption_display import active_caption_rows
from prototype.app.mode_policy import MODE_METADATA
from prototype.app.ui import PrototypeUI
from prototype.tests.n1_event_fixtures import row, scenarios


class EventController:
    def __init__(self):
        self.calls = []
        self.data = dict(state='IDLE', status='Synthetic EVENT fixture · no audio', rows=[], people=[],
            mode='enrolled_names', recipe='balanced', tap='O0', strict=False, selected_ids=[],
            settings={}, metrics={}, enrollment={}, backend_id=BASELINE_BACKEND_ID,
            backends=backend_catalog(), mode_metadata=deepcopy(MODE_METADATA))
    def snapshot(self):
        result = deepcopy(self.data)
        result['backend'] = backend_status(result['backend_id'], result['mode'], result['tap'])
        return result
    def select_backend(self, identifier):
        self.calls.append(('select_backend', identifier)); self.data['backend_id'] = identifier
    def settings_update(self, values): self.data['settings'].update(values)
    def close(self): self.data['state'] = 'CLOSED'
    def switch(self, **values): self.calls.append(('switch', values)); self.data.update(values)
    def start_live(self, **values): raise AssertionError('A hardware entry point was reached')


class WithdrawnRoot(tk.Tk):
    """Load Tk without entering its event loop; withdraw before any idle mapping."""
    def __init__(self):
        super().__init__(useTk=False)
        self.tk.call('package', 'require', 'Tk')
        self.tk.call('wm', 'withdraw', '.')
        self._loadtk()
    def deiconify(self): raise AssertionError('Headless fixture must never map a window')
    wm_deiconify = deiconify


class N1FrontendTests(unittest.TestCase):
    def setUp(self):
        self.root = WithdrawnRoot()
        self.c = EventController()
        self.ui = PrototypeUI(self.root, self.c, allow_auto_start=False)
        # Allocate the logical client entirely inside an unmapped root. This
        # permits layout/scroll checks without screen capture or focus changes.
        self.ui.shell.pack_forget()
        self.ui.shell.place(x=0, y=0, width=480, height=800)
        self.root.update_idletasks()
        self.clock = patch('prototype.app.ui.time.perf_counter', return_value=100)
        self.now = self.clock.start()
    def tearDown(self):
        self.clock.stop()
        self.assertEqual(self.root.state(), 'withdrawn')
        self.assertFalse(self.root.winfo_viewable())
        self.ui.close(); self.ui.poll()
    def draw(self, rows):
        original = deepcopy(rows)
        self.c.data['rows'] = rows
        self.ui.snapshot = self.c.snapshot()
        self.ui._render_rows(rows)
        self.root.update_idletasks()
        self.assertEqual(rows, original)
    def stabilize(self, rows):
        self.draw(rows); self.now.return_value += .3; self.draw(rows)

    def test_aba_interruption_and_late_correction_keep_separate_spans(self):
        fixture = scenarios()
        for rows in fixture['aba_and_short_interruption']: self.stabilize(rows)
        cache = self.ui._active_pane.values
        self.assertEqual([cache[rid][0] for rid in self.ui._active_pane.order], ['Alex','Blair','Alex'])
        marks = deepcopy(self.ui._active_pane.marks)
        corrected = fixture['late_correction'][-1]
        self.stabilize(corrected)
        self.assertEqual(self.ui._active_pane.marks, marks)
        self.assertEqual(self.ui._active_pane.values['aba-b'][0], 'Casey')
        self.assertEqual(self.ui._active_pane.values['aba-a1'][0], 'Alex')
        self.assertEqual(corrected[1]['first_shown_label'], 'Unknown')

    def test_simultaneous_event_windows_are_both_visible_and_independent(self):
        fixture = scenarios()['simultaneous_updates']
        for rows in fixture: self.stabilize(rows)
        self.assertEqual(self.ui._active_pane.order, ['sim-a', 'sim-b'])
        self.assertIn('The first ongoing message.', self.ui.active_text.get('1.0','end'))
        self.assertIn('A revised simultaneous message.', self.ui.active_text.get('1.0','end'))

    def test_history_scroll_is_unchanged_by_active_partial(self):
        rows = scenarios()['scrolling'][-1]
        self.stabilize(rows)
        self.ui._follow_live = False
        self.ui.caption_text.yview(self.ui._marks['history-15'][0])
        self.root.update_idletasks()
        before = self.ui.caption_text.get('@0,0', '@0,0 lineend')
        position = (self.ui.active_region.winfo_y(), self.ui.active_region.winfo_height())
        marks = deepcopy(self.ui._marks)
        changed = deepcopy(rows); changed[-1]['provisional_display_text'] += ' More words follow.'
        with patch.object(self.ui.caption_text, 'yview_moveto', wraps=self.ui.caption_text.yview_moveto) as moved:
            self.draw(changed)
            moved.assert_not_called()
        self.assertEqual(self.ui.caption_text.get('@0,0','@0,0 lineend'), before)
        self.assertEqual(self.ui._marks, marks)
        self.assertEqual((self.ui.active_region.winfo_y(), self.ui.active_region.winfo_height()), position)

    def test_large_paragraph_all_words_accessible_and_suffix_retains_mark(self):
        first, last = scenarios()['large_paragraph']
        self.stabilize(first)
        marks = deepcopy(self.ui._active_pane.marks)
        self.draw(last)
        self.assertEqual(self.ui._active_pane.marks, marks)
        self.assertIn('word0 ', self.ui.active_text.get('1.0','end'))
        self.assertIn('word419 New suffix.', self.ui.active_text.get('1.0','end'))
        self.assertLess(self.ui.active_text.yview()[0], self.ui.active_text.yview()[1])
        self.ui._scroll_active_to('moveto', 0)
        self.assertEqual(self.ui.active_text.yview()[0], 0)
        self.ui.back_to_live()
        self.assertTrue(self.ui._active_pane.follow)

    def test_backend_selection_preserves_mode_recipe_tap_and_blocks_start(self):
        chosen = next(item for item in backend_catalog() if not item['implemented'])
        before = [self.c.data[key] for key in ('mode','recipe','tap')]
        self.ui.show_backends(); self.ui._select_backend(chosen['manifest_id']); self.ui.poll()
        self.assertEqual([self.c.data[key] for key in ('mode','recipe','tap')], before)
        self.assertIn('BACKEND', self.ui.actions['backend'].cget('text'))
        self.assertIn('unavailable', self.ui.actions['backend'].cget('text'))
        self.ui.toggle_listening()
        self.assertEqual(self.c.calls, [('select_backend',chosen['manifest_id'])])
        self.ui.show_modes()
        for key, value in MODE_METADATA.items():
            if not value['advanced']: self.assertIn('mode_'+key, self.ui.actions)

    def test_fixed_logical_layout_idle_and_conditional_rescue(self):
        self.assertEqual((self.ui.shell.winfo_width(), self.ui.shell.winfo_height()), (480,800))
        self.assertEqual(self.ui.active_region.winfo_height(), 184)
        self.assertGreater(self.ui.caption_text.winfo_height(), 140)
        self.assertFalse(self.c.calls)
        self.assertEqual(self.ui.rescue.winfo_manager(), '')
        self.c.data['strict'] = True; self.ui.snapshot = self.c.snapshot(); self.ui._show_status()
        self.assertEqual(self.ui.rescue.winfo_manager(), 'pack')
        self.assertEqual(self.ui.active_region.winfo_height(), 184)

    def test_closed_assumption_and_pending_bound_are_preserved(self):
        pending = row('pending','Unknown','Only words are known.',0,1)
        pending.update(profile_id=None,track_id=None,ownership_state='pending')
        self.draw([pending]); self.assertIn('•••', self.ui._active_pane.values['pending'][0])
        self.now.return_value += 1.21; self.draw([pending])
        self.assertEqual(self.ui._active_pane.values['pending'][0], 'Unknown')
        assumed = dict(pending, label='Alex · assumed', closed_group_display=True, display_profile_id='fixture-Alex')
        self.c.data['mode'] = 'selected_closed'; self.draw([assumed])
        self.assertEqual(self.ui._active_pane.values['pending'][0], 'Alex · assumed')

    def test_same_snapshot_never_rewrites_active_pane(self):
        rows = [row('stable','Alex','The same text.',0,1)]
        self.stabilize(rows)
        edits = self.ui._active_pane.edits
        self.draw(rows)
        self.assertEqual(self.ui._active_pane.edits, edits)
        self.assertEqual(active_caption_rows(rows), rows)

    def test_gui_receipt_preserves_actual_first_label_and_late_revision(self):
        rows = [row('receipt','Alex','A timestamped display.',0,1)]
        self.draw(rows)
        first = deepcopy(self.ui.presentation_receipts[-1])
        self.assertIn('•••', first['label'])
        self.now.return_value += .3; self.draw(rows)
        named = self.ui.presentation_receipts[-1]
        self.assertEqual(named['label'], 'Alex')
        self.assertTrue(all(value == first['label'] for value in named['first_gui_labels'].values()))
        self.assertTrue(all(value == 1 for value in named['gui_label_revisions'].values()))
        self.assertEqual(named['applied_monotonic_sec'], 100.3)
        self.assertIn('physical scanout not measured', named['scope'])


if __name__ == '__main__': unittest.main()
