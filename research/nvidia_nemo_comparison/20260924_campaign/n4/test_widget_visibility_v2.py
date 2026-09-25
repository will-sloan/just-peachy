"""Import-path derivative for actual viewport tests. README_WIDGET_VISIBILITY_V2.md."""
from copy import deepcopy
import ctypes
import json
import os
from pathlib import Path
import sys
import time
import unittest

from .widget_visibility import snapshot,VisibilityHistory


class WidgetVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('N4_WIDGET_ADMISSION'):raise unittest.SkipTest('Use probe_widget_visibility.py; never create Tk on the input desktop')
        # Existing immutable evaluator readers use their script-local imports.
        # Admit that exact directory for this package-launched private child.
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from .common import load,verify
        from .metric_process import pin
        p=pin();cls.admission=load(os.environ['N4_WIDGET_ADMISSION']);cls.folder=Path(cls.admission['output'])
        for b in cls.admission['code']:verify(b)
        from prototype.tests.run_private_desktop import desktop_name,setup_api
        user=setup_api();name=desktop_name(user.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId()))
        if not name.startswith('codex-n1-'):raise ValueError('Refusing Tk outside private desktop')
        cls.desktop=name;cls.owner=dict(pid=p.pid,create_time=p.create_time())

    def setUp(self):
        import tkinter as tk
        from prototype.app.ui import PrototypeUI,prepare_dpi_awareness
        from prototype.tests.test_n1_frontend import EventController
        prepare_dpi_awareness();self.root=tk.Tk();self.c=EventController();self.c.data['mode']='anonymous_conversation'
        self.c.data['saved_audio_only']=True;self.c.data['status']='Private saved-output observation; no inference'
        self.ui=PrototypeUI(self.root,self.c,allow_auto_start=False);self.root.update()
        self.assertEqual((self.root.winfo_width(),self.root.winfo_height()),(480,800))
        self.assertEqual(self.ui.active_region.winfo_height(),184)

    def tearDown(self):
        self.ui._closed=True
        try:self.root.destroy()
        except Exception:pass

    def draw(self,rows,**values):
        self.c.data.update(rows=deepcopy(rows),**values);self.ui.snapshot=self.c.snapshot()
        self.ui._render_rows(self.c.data['rows']);self.root.update_idletasks()
        before=deepcopy(self.c.data);cache=deepcopy(self.ui._row_cache)
        labels=deepcopy(self.ui._identity_labels.__dict__)
        result=snapshot(self.ui,self.c.data['rows'])
        self.assertEqual(before,self.c.data);self.assertEqual(cache,self.ui._row_cache)
        self.assertEqual(labels,self.ui._identity_labels.__dict__)
        return result

    def row(self,key='r',text='A short caption.',**kwargs):
        from prototype.tests.n1_event_fixtures import row
        result=row(key,kwargs.pop('label','Research speaker'),text,kwargs.pop('start',0),kwargs.pop('end',1),
            caption=key,final=kwargs.pop('final',False))
        result.update(kwargs)
        return result

    def test_active_history_elision_and_hidden_heading(self):
        r=self.row();seen=self.draw([r]);item=seen['rows'][0]
        self.assertTrue(item['panes']['history']['present_in_widget'])
        self.assertFalse(item['panes']['history']['caption_visible'])
        self.assertTrue(item['panes']['active']['caption_visible'])
        self.assertFalse(seen['source_to_widget_latency_qualified'])

    def test_long_active_text_is_applied_but_heading_can_be_offscreen(self):
        r=self.row(text=' '.join(f'line{i} with many words to wrap.' for i in range(70)),label='Research speaker')
        seen=self.draw([r]);self.ui._active_pane.follow=False;self.ui.active_text.yview_moveto(1.0);self.root.update_idletasks()
        result=snapshot(self.ui,self.c.data['rows'])['rows'][0]['panes']['active']
        self.assertTrue(result['caption_visible']);self.assertFalse(result['heading_visible'])
        self.assertGreater(len(result['applied_caption_text']),result['caption_viewport']['visible_nonspace_characters'])
        self.assertLessEqual(seen['character_checks'],4096)

    def test_final_without_rewrite_and_row_retirement(self):
        row=self.row(final=False);history=VisibilityHistory();first=self.draw([row]);history.add(first)
        span=first['rows'][0]['span_ids'][0]
        self.assertIsNotNone(history.spans[span]['first_visible']);self.assertIsNone(history.spans[span]['first_final_visible'])
        edits=self.ui._active_pane.edits;row['final']=True;last=self.draw([row]);history.add(last)
        self.assertEqual(edits,self.ui._active_pane.edits);self.assertIsNotNone(history.spans[span]['first_final_visible'])
        history.add(self.draw([]));self.assertFalse(history.spans[span]['latest']['row']['caption_visible'])
        self.assertTrue(history.spans[span]['latest']['row']['removed_from_controller'])

    def test_strict_selection_preserves_missing_and_recoverable_words(self):
        row=self.row(selected=False);hidden=self.draw([row],strict=True)
        self.assertTrue(hidden['rows'][0]['strictly_filtered']);self.assertFalse(hidden['rows'][0]['caption_visible'])
        shown=self.draw([row],strict=False);self.assertTrue(shown['rows'][0]['caption_visible'])
        self.assertEqual(hidden['rows'][0]['raw_asr_text'],shown['rows'][0]['raw_asr_text'])

    def test_unicode_text_and_corrupt_widget_rejection(self):
        row=self.row(text='Café déjà vu — a peach 🍑 and 中文 words.')
        seen=self.draw([row]);self.assertTrue(seen['rows'][0]['caption_visible'])
        rid=str(row['id']);start,_=self.ui._marks[rid]
        self.ui.caption_text.configure(state='normal');self.ui.caption_text.insert(start,'CORRUPT');self.ui.caption_text.configure(state='disabled')
        with self.assertRaisesRegex(ValueError,'differs'):snapshot(self.ui,self.c.data['rows'])

    def test_history_scroll_changes_view_without_changing_caption(self):
        rows=[self.row(f'r{i}',f'Caption {i} with a full sentence.',start=i*3,end=i*3+2,final=True) for i in range(35)]
        self.draw(rows);self.ui._follow_live=False;self.ui.caption_text.yview_moveto(0);self.root.update_idletasks()
        a=snapshot(self.ui,self.c.data['rows']);self.ui.caption_text.yview_moveto(1);self.root.update_idletasks()
        b=snapshot(self.ui,self.c.data['rows'])
        self.assertTrue(a['rows'][0]['panes']['history']['caption_visible']);self.assertFalse(b['rows'][0]['panes']['history']['caption_visible'])
        self.assertEqual(a['rows'][0]['raw_asr_text'],b['rows'][0]['raw_asr_text'])
        with self.assertRaises(ValueError):snapshot(self.ui,rows,source_origin=1,source_clock='MODELED')

    def test_saved_composition_mode_tap_outputs(self):
        from .common import bind,freeze,load,verify
        from .integrated_scoring_adapter import read_artifact
        from prototype.app.backends import backend_catalog
        cases=[];keys={r['key']:r['id'] for r in backend_catalog()}
        for i,entry in enumerate(self.admission['saved_checks']):
            projected=read_artifact(entry['projection'])
            rows=projected['final_rows'];history=VisibilityHistory()
            first=self.draw(rows,mode=entry['mode'],tap=entry['tap'],backend_id=keys[entry['backend']],strict=False)
            history.add(first)
            until=time.perf_counter()+.23
            while time.perf_counter()<until:self.root.update();time.sleep(.01)
            last=self.draw(rows);history.add(last)
            self.assertEqual(len(last['rows']),len(rows))
            self.assertTrue(all(r['panes']['history']['present_in_widget'] for r in last['rows']))
            path=self.folder/'saved'/f'{i:03d}.json'
            freeze(path,dict(backend=entry['backend'],mode=entry['mode'],tap=entry['tap'],projection=entry['projection'],
                first=first,last=last,history=history.summary(),models_loaded=0,integrated_N4_cells=0))
            cases.append(bind(path))
        freeze(self.folder/'SAVED_OUTPUT_CHECKS.json',dict(status='PASS_SAVED_OUTPUT_TK_VIEWPORT_OBSERVATIONS',owner=self.owner,
            desktop=self.desktop,cases=cases,models_loaded=0,integrated_N4_cells=0,
            scope='Modeled saved Controller output rendered in actual Tk; no source-paced inference, hardware latency or physical scanout'))
