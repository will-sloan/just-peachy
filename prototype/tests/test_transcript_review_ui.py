"""Actual touch widgets with disclosed stub. See README_TRANSCRIPT_REVIEW.md."""
import gc,sys,tkinter as tk,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
from prototype.app.ui import PrototypeUI,prepare_dpi_awareness
from prototype.tests.test_ui import StubController,widgets
from app.transcript_review import finite_review

class ReviewStub(StubController):
    def review_action(self,action,**kw):
        self._record('review_action',action,kw)
        if action=='switch':self.data.setdefault('audio_review',{})['enabled']=kw['enabled']
        if action=='cancel':self.data.setdefault('audio_review',{}).update(status='CANCELLED',result=None)

class ReviewUITests(unittest.TestCase):
    def setUp(self):
        prepare_dpi_awareness();self.root=tk.Tk();self.c=ReviewStub();self.ui=PrototypeUI(self.root,self.c);self.root.update()
    def tearDown(self):self.ui.close();self.ui.poll();self.ui=None;self.root=None;gc.collect()
    def labels(self):return '\n'.join(w.cget('text') for w in widgets(self.root) if isinstance(w,tk.Label))
    def test_default_off_and_no_implicit_record_or_inference(self):
        self.ui.show_audio_review();self.root.update();self.assertIn('Off',self.ui.actions['audio_review_switch'].cget('text'))
        self.ui.actions['audio_review_switch'].invoke();self.ui.poll();self.root.update()
        self.assertTrue(self.c.data['audio_review']['enabled']);self.assertFalse(any(c[0]=='start_live' for c in self.c.calls))
        self.assertIn('Language helper: not installed',self.labels())
        self.assertEqual((self.ui.measure_client()['physical_width'],self.ui.measure_client()['physical_height']),(480,800))
    def test_highlights_and_explicit_adoption_then_cancel(self):
        r=finite_review(dict(original='we can meet at 15',conversation='c',epoch_id='e',source_start_sample=0,source_end_sample=16000),'you cannot meet at 50',{})
        self.c.data['audio_review']=dict(enabled=True,status='READY',result=r)
        self.ui.poll();self.ui.show_audio_review();self.root.update()
        self.assertIn('− we can',self.labels());self.assertIn('+ you cannot',self.labels())
        self.ui.actions['audio_review_adopt_redecode'].invoke();self.root.update();self.assertIn('I listened',self.labels())
        self.assertFalse(any(c[0]=='review_action' and c[1][0]=='adopt' for c in self.c.calls))
        self.ui.actions['cancel'].invoke();self.root.update();self.ui.actions['audio_review_cancel'].invoke()
        self.assertIsNone(self.c.data['audio_review']['result'])

if __name__=='__main__':unittest.main()
