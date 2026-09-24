"""GUI-only synthetic contracts; see README_CAPTION_DISPLAY.md. No audio/models."""
from copy import deepcopy
import tkinter as tk
import unittest
from unittest.mock import patch

from prototype.app.caption_display import IdentityLabels, continues
from prototype.app.ui import PrototypeUI, TouchScroll, prepare_dpi_awareness
from prototype.tests.test_ui import StubController, sample_rows, widgets


class IdentityDisplayTests(unittest.TestCase):
    def test_closed_assumed_name_is_visible_immediately_even_without_voice(self):
        labels=IdentityLabels();r=dict(id='a',label='Alex · assumed',profile_id=None,display_profile_id='uuid1',
            closed_group_display=True,identity_status='unavailable')
        self.assertEqual(labels.label(r,'selected_closed',0.),'Alex · assumed')
        r.update(label='Blair · assumed',display_profile_id='uuid2')
        self.assertEqual(labels.label(r,'selected_closed',.05),'Blair · assumed')
        self.assertEqual(labels.label(r,'selected_focus',.1),'Unknown · voice unavailable')
        r.update(closed_group_display=False,display_profile_id=None,label='Unknown')
        self.assertEqual(labels.label(r,'selected_closed',.2),'Unknown · voice unavailable')

    def test_pending_bound_survives_native_segment_replacement_and_jitter(self):
        labels = IdentityLabels()
        r = dict(id='segment1', caption_key='epoch/turn1', label='Unknown')
        self.assertIn('•••', labels.label(r, 'open_with_names', 1))
        for index in range(1, 14):
            r.update(id=f'segment{index}', label='Alex' if index%2 else 'Unknown')
            labels.prune([r])
            shown = labels.label(r, 'open_with_names', 1+index/10)
        self.assertEqual(shown, 'Unknown')
        self.assertEqual(len(labels.turns), 1)

    def test_name_is_stable_but_never_retained_after_disagreement(self):
        labels=IdentityLabels();r=dict(id='a',label='Alex',profile_id='uuid1')
        self.assertIn('•••',labels.label(r,'enrolled_names',1))
        self.assertEqual(labels.label(r,'enrolled_names',1.2),'Alex')
        r['label']='Unknown'; self.assertNotIn('Alex',labels.label(r,'enrolled_names',1.3))
        self.assertEqual(labels.label(r,'enrolled_names',2.2),'Unknown')
        r.update(label='Blair',profile_id='uuid2')
        self.assertEqual(labels.label(r,'enrolled_names',3),'Unknown')
        self.assertEqual(labels.label(r,'enrolled_names',3.2),'Blair')
        r['identity_status']='unavailable'
        self.assertEqual(labels.label(r,'enrolled_names',3.3),'Unknown · voice unavailable')

    def test_numbered_variant_and_caption_only_no_pending(self):
        labels=IdentityLabels();r=dict(id='a',label='Speaker_2')
        self.assertEqual(labels.label(r,'anonymous_conversation',1),'Unknown')
        self.assertIn('•••',labels.label(r,'anonymous_conversation',1,True))
        self.assertEqual(labels.label(r,'anonymous_conversation',1.2,True),'Speaker_2')
        self.assertEqual(labels.label(r,'caption_only',1.2),'Transcription')

    def test_grouping_requires_supported_contiguous_same_turn_and_track(self):
        a=dict(id='a',caption_key='turn1',track_id=2,profile_id='uuid1',ownership_state='supported_history',token_range=[0,2])
        b=dict(a,id='b',token_range=[2,4])
        self.assertTrue(continues(a,b,'Alex','Alex'))
        for field,value in [('track_id',3),('caption_key','turn2'),('ownership_state','pending'),('profile_id','uuid2'),('handoff',True),('token_range',[3,5])]:
            self.assertFalse(continues(a,dict(b,**{field:value}),'Alex','Alex'))
        self.assertFalse(continues(a,b,'Unknown','Unknown'))


class CaptionWidgetTests(unittest.TestCase):
    def setUp(self):
        prepare_dpi_awareness();self.root=tk.Tk();self.c=StubController();self.ui=PrototypeUI(self.root,self.c)
        self.root.geometry('+30+30');self.root.update()
    def tearDown(self):
        self.ui.close();self.ui.poll()
    def draw(self, rows):
        self.c.data['rows']=rows;self.ui.snapshot=self.c.snapshot();self.ui._render_rows(rows);self.root.update_idletasks()

    def test_closed_widget_does_not_replace_assumed_name_with_unknown_or_pending(self):
        self.c.data['mode']='selected_closed'
        self.draw([dict(id='closed1',caption_key='turn1',label='Alex · assumed',display_profile_id='p1',
            closed_group_display=True,identity_status='unavailable',profile_id=None,raw_asr_text='SHORT WORDS')])
        self.assertEqual(self.ui._row_cache['closed1'][0],'Alex · assumed')
        self.assertIn('Short words',self.ui.caption_text.get('1.0','end'))

    def test_segment_replacement_keeps_history_marks_and_raw_rows(self):
        rows=sample_rows(35);self.draw(rows);old=dict(self.ui._marks)
        self.ui._follow_live=False;self.ui.caption_text.yview(old['row-9'][0]);self.root.update_idletasks()
        anchor=self.ui.caption_text.get('@0,0','@0,0 lineend')
        rows[-2:]=[dict(id='owned1',label='Alex',raw_asr_text='LATER WORDS'),dict(id='pending',label='Unknown',raw_asr_text='AND MORE')]
        raw=deepcopy(rows);self.draw(rows)
        self.assertEqual(rows,raw)
        for rid in [f'row-{i}' for i in range(33)]:self.assertEqual(self.ui._marks[rid],old[rid])
        self.assertEqual(self.ui.caption_text.get('@0,0','@0,0 lineend'),anchor)
        self.assertEqual(self.ui._render_order,[r['id'] for r in rows])

    def test_grouped_cards_preserve_ids_and_break_at_handoff_or_unknown(self):
        self.c.data['mode']='open_with_names'
        base=dict(label='Alex',profile_id='p1',track_id=1,caption_key='turn',ownership_state='supported_history')
        rows=[dict(base,id='a',raw_asr_text='FIRST',token_range=[0,1]),dict(base,id='b',raw_asr_text='SECOND',token_range=[1,2]),
              dict(base,id='c',label='Blair',track_id=2,profile_id='p2',raw_asr_text='THIRD',token_range=[2,3])]
        with patch('prototype.app.ui.time.perf_counter',return_value=10) as clock:
            self.draw(rows);clock.return_value=10.3;self.draw(rows)
            self.assertEqual(self.ui._row_cache['b'][0],'')
            self.assertEqual(self.ui._row_cache['c'][0],'Blair')
            self.assertEqual(set(self.ui._marks),{'a','b','c'})
            rows[1]['label']='Unknown';clock.return_value=12;self.draw(rows)
            self.assertEqual(self.ui._row_cache['b'][0],'Unknown')

    def test_smoothing_uses_one_fixed_deadline_and_latest_revision(self):
        self.ui.preferences['display_smoothing_ms']=150
        first=[dict(id='a',label='Unknown',raw_asr_text='ONE')]
        last=[dict(id='a',label='Unknown',raw_asr_text='ONE TWO THREE')]
        with patch.object(self.root,'after',return_value='fixture-timer') as after, patch.object(self.root,'after_cancel'):
            self.ui._queue_rows(first);self.ui._queue_rows(last)
            after.assert_called_once_with(150,self.ui._flush_rows)
            self.assertNotIn('a',self.ui._marks)
            self.ui._flush_rows()
        self.assertIn('One two three',self.ui.caption_text.get('1.0','end'))
        self.assertEqual(first[0]['raw_asr_text'],'ONE')
        self.assertIsNone(self.ui._pending_rows)

    def test_empty_populated_people_settings_scroll_and_back_at_both_sizes(self):
        for zoom in (1,1.25):
            self.ui._preference('preview_zoom',zoom)
            m=self.ui.measure_client();self.assertEqual((m['physical_width'],m['physical_height']),(round(480*zoom),round(800*zoom)))
            positions=[]
            for people in ([],[dict(id=f'person{i}',name='A very long name with many parts '*4) for i in range(20)]):
                self.ui.snapshot['people']=people;self.ui.show_people();self.root.update_idletasks()
                self.assertEqual(self.ui.actions['people'].cget('relief'),'sunken')
                positions.append((self.ui.actions['back'].winfo_rootx(),self.ui.actions['back'].winfo_rooty()))
                area=next(w for w in widgets(self.ui.dialog_page) if isinstance(w,TouchScroll))
                extent=area.canvas.bbox('all');self.assertEqual(extent[3],area.inner.winfo_reqheight())
                area.canvas.yview_moveto(1);self.root.update_idletasks()
                self.assertGreaterEqual(area.canvas.yview()[1],.999)
            self.ui.show_settings();self.root.update_idletasks()
            self.assertEqual(self.ui.actions['settings'].cget('relief'),'sunken')
            self.assertEqual((self.ui.actions['back'].winfo_rootx(),self.ui.actions['back'].winfo_rooty()),positions[0])
            self.assertEqual(positions[0],positions[1])
            self.ui.home();self.draw([dict(id='long',raw_asr_text='LONG PARAGRAPH '*150,label='Unknown')])
            self.assertIsNotNone(self.ui.caption_text.bbox('end-1c'))

    def test_close_cancels_smoothing_and_keeps_controller_calls_bounded(self):
        self.ui.preferences['display_smoothing_ms']=300
        self.ui._queue_rows(sample_rows(1));self.assertIsNotNone(self.ui._display_handle)
        self.ui.close();self.assertIsNone(self.ui._display_handle)
        self.assertEqual(self.c.calls,[('close',(),{})])

    def test_zoom_keeps_identity_deadline_and_active_mode(self):
        self.c.data['mode']='open_with_names';rows=[dict(id='one',caption_key='turn',label='Unknown',raw_asr_text='HELLO')]
        with patch('prototype.app.ui.time.perf_counter',return_value=10) as clock:
            self.draw(rows);clock.return_value=12;self.draw(rows)
            self.assertEqual(self.ui._row_cache['one'][0],'Unknown')
            self.ui._preference('preview_zoom',1.25)
            self.assertEqual(self.ui._row_cache['one'][0],'Unknown')
        self.assertEqual(self.ui.mode_label.cget('text'),'All enrolled · numbered Unknowns')
        self.root.update()
        self.assertEqual((self.ui.shell.winfo_width(),self.ui.shell.winfo_height()),(600,1000))


if __name__=='__main__':unittest.main()
