"""Touch enrollment widgets, explicit stub backend. See README_ENROLLMENT.md."""
import argparse
import json
from pathlib import Path
import sys
import tkinter as tk
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
from prototype.app.ui import PrototypeUI, prepare_dpi_awareness, TouchScroll
from prototype.tests.test_ui import StubController, widgets


class ParagraphUITests(unittest.TestCase):
    def setUp(self):
        prepare_dpi_awareness();self.root=tk.Tk();self.controller=StubController()
        self.ui=PrototypeUI(self.root,self.controller);self.root.update()
        self.ui.enrollment_form('Test person')

    def tearDown(self):
        self.ui.close();self.ui.poll()
        self.ui=None;self.root=None
        import gc
        gc.collect()

    def start(self):
        self.ui.actions['enroll_target_done'].invoke();self.ui.actions['enrollment_consent'].invoke()
        self.ui.actions['enrollment_start'].invoke();self.ui.poll();self.root.update()

    def test_fourth_option_uses_guide_only_in_paragraph_mode(self):
        for key in ('15','30','60','done'):self.assertIn('enroll_target_'+key,self.ui.actions)
        self.ui._set_paragraph('My unchanged, editable words');self.start()
        _,args,kw=self.controller.calls[-1]
        self.assertIsNone(args[1]);self.assertEqual(kw['paragraph'],'My unchanged, editable words')
        self.assertIn('Done',self.ui.actions['enrollment_stop'].cget('text'))
        self.assertIn('no timed target',self.ui.enroll_progress_label.cget('text'))

    def test_backlog_and_verified_animation_and_ready_gate(self):
        self.start();data=self.controller.data['enrollment'];self.ui._enroll_animation.last=0
        data.update(usable_s=2.,elapsed_s=8.,analyzed_s=3.,activity_s=5.,can_save=True)
        with patch('prototype.app.ui.time.monotonic',return_value=.08):self.ui.poll()
        self.assertLess(float(self.ui.enroll_progress['value']),2.)
        self.assertIn('pending quality: 5.0s',self.ui.enroll_progress_label.cget('text'))
        self.assertEqual(str(self.ui.actions['enrollment_save']['state']),'disabled')
        data.update(state='ANALYZING');self.ui.poll()
        self.assertEqual(str(self.ui.actions['enrollment_stop']['state']),'disabled')
        data.update(state='READY',evidence_status='limited_short_reference');self.ui.poll()
        self.assertEqual(str(self.ui.actions['enrollment_save']['state']),'normal')
        self.assertIn('Limited evidence',self.ui.enroll_progress_label.cget('text'))
        self.assertEqual(self.ui.measure_client()['physical_width'],480)
        self.assertEqual(self.ui.measure_client()['physical_height'],800)


def screenshots(directory):
    from prototype.tests.native_ui_check import capture
    directory.mkdir(parents=True,exist_ok=False)
    prepare_dpi_awareness();root=tk.Tk();controller=StubController();ui=PrototypeUI(root,controller)
    root.geometry('+30+30');root.update();ui.enrollment_form('Offline UI fixture')
    ui.actions['enroll_target_done'].invoke();root.update();capture(root,directory/'01_options.png')
    scroll=next(w for w in widgets(root) if isinstance(w,TouchScroll) and w.winfo_ismapped())
    scroll.canvas.yview_moveto(1);capture(root,directory/'02_consent.png')
    ui.actions['enrollment_consent'].invoke();ui.actions['enrollment_start'].invoke()
    controller.data['enrollment'].update(usable_s=2.,elapsed_s=8.,analyzed_s=3.,activity_s=5.)
    ui.poll();root.update();capture(root,directory/'03_pending_stub.png')
    controller.data['enrollment'].update(state='READY',elapsed_s=12.,analyzed_s=12.,usable_s=12.,activity_s=12.,can_save=True,
        evidence_status='limited_short_reference',script_estimate={'estimated_coverage':5/46,'estimated_agreement':10/85,'analyzed_audio_s':12})
    ui.poll();root.update();capture(root,directory/'04_done_stub.png')
    (directory/'UI_SCOPE.json').write_text(json.dumps({'scope':'Actual Tk, explicitly STUB data. No audio/device/model access.','client':ui.measure_client()},indent=2))
    ui.close();ui.poll()


if __name__=='__main__':
    if '--screenshots' in sys.argv:
        p=argparse.ArgumentParser();p.add_argument('--screenshots',type=Path,required=True)
        screenshots(p.parse_args().screenshots)
    else:unittest.main()
