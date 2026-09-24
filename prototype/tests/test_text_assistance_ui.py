"""Actual Tk / stub text-assistance controls. See README_TEXT_ASSISTANCE.md."""
import argparse
import gc
import json
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
from prototype.app.ui import PrototypeUI,prepare_dpi_awareness
from prototype.app.text_assistance import TextAssistance
from prototype.tests.test_ui import StubController


class TextStub(StubController):
    def __init__(self,path):
        super().__init__();self.text=TextAssistance(path)
    def snapshot(self):
        self.data['text_assistance']={**self.text.snapshot(self.data['people']), 'recent':getattr(self,'recent',[])}
        return super().snapshot()
    def text_assistance_action(self,action,**values):
        self._record('text_assistance_action',action,**values);self.text.change(action,values,self.data['people'])
    def session_action(self,action,**values):self._record('session_action',action,**values)


class TextUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();prepare_dpi_awareness();self.root=tk.Tk()
        self.c=TextStub(Path(self.temp.name)/'vocab.json');self.ui=PrototypeUI(self.root,self.c);self.root.update()
    def tearDown(self):
        self.ui.close();self.ui.poll();self.ui=None;self.root=None;gc.collect();self.temp.cleanup()
    def test_switches_bias_reason_and_touch_keyboard_approval(self):
        self.ui.show_settings();self.ui.actions['text_assistance'].invoke()
        self.assertEqual(str(self.ui.actions['text_bias']['state']),'disabled')
        self.ui.actions['text_enabled'].invoke();self.ui.poll()
        self.assertTrue(self.c.text.config['enabled']);self.assertFalse(self.c.text.config['automatic'])
        self.ui.actions['vocab_add'].invoke();self.ui.actions['vocab_preferred'].invoke()
        self.ui.keyboard_value.insert('1.0','captions');self.ui.actions['keyboard_done'].invoke()
        self.ui.actions['vocab_save'].invoke();self.ui.poll()
        self.assertEqual(self.c.text.config['entries'][0]['preferred'],'captions')
        self.assertEqual(self.ui.measure_client()['physical_width'],480)
    def test_corrected_marker_off_baseline_and_identity_unmodified(self):
        row={'id':'u','final':True,'label':'Amir','naming_state':'confirmed','raw_asr_text':'EMIR JOINED PEACHY',
             'final_punctuated_display_text':'Emir joined Peachy.','optional_corrected_text':'Amir joined Peachy.',
             'show_corrected_text':False}
        label,baseline,_=self.ui._display_row(row)
        row['show_corrected_text']=True;newlabel,text,_=self.ui._display_row(row)
        self.assertEqual(label,newlabel);self.assertEqual(text,'✎ Amir joined Peachy.')
        self.assertEqual(baseline,'Emir joined Peachy.');self.assertEqual(row['raw_asr_text'],'EMIR JOINED PEACHY')


def screenshots(out):
    from prototype.tests.native_ui_check import capture
    out.mkdir(parents=True,exist_ok=False);prepare_dpi_awareness();root=tk.Tk();c=TextStub(out/'vocab_fixture.json')
    ui=PrototypeUI(root,c);root.geometry('+30+30');root.update();ui.show_text_assistance()
    capture(root,out/'01_settings_stub.png');ui._new_vocab();ui._vocab_draft.update(preferred='Amir',alias='Emir',context='Peachy',kind='name');ui._draw_vocab()
    capture(root,out/'02_approval_stub.png')
    c.text.change('switch',{'enabled':True},c.data['people'])
    r=c.text.analyze('The camptions are visible.',[])
    c.recent=[{'caption_key':'fixture/u1','raw':'THE CAMPTIONS ARE VISIBLE','final':'The camptions are visible.','assistance':r}]
    ui.poll();ui.show_text_review();capture(root,out/'03_review_stub.png')
    (out/'UI_SCOPE.json').write_text(json.dumps({'scope':'Actual Tk with explicit stub, no mic/model/audio','client':ui.measure_client()},indent=2))
    ui.close();ui.poll()


if __name__=='__main__':
    if '--screenshots' in sys.argv:
        p=argparse.ArgumentParser();p.add_argument('--screenshots',type=Path,required=True);screenshots(p.parse_args().screenshots)
    else:unittest.main()
