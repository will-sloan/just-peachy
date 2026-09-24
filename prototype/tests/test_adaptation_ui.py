"""Actual portrait widgets with disclosed controller stub. See README_ADAPTATION.md."""
import gc,sys,tkinter as tk,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
from prototype.app.ui import PrototypeUI,prepare_dpi_awareness
from prototype.tests.test_ui import StubController,widgets

class ReferenceStub(StubController):
    def adaptation_action(self,action,**kw):
        self._record('adaptation_action',action,kw)
        if action in ('collect','use'):self.data.setdefault('adaptation',{})['collect' if action=='collect' else 'enabled']=kw['enabled']

class AdaptationUITests(unittest.TestCase):
    def setUp(self):
        prepare_dpi_awareness();self.root=tk.Tk();self.c=ReferenceStub();self.ui=PrototypeUI(self.root,self.c);self.root.update()
    def tearDown(self):self.ui.close();self.ui.poll();self.ui=None;self.root=None;gc.collect()
    def labels(self):return '\n'.join(w.cget('text') for w in widgets(self.root) if isinstance(w,tk.Label))
    def test_default_off_and_enable_requires_explicit_click_without_start(self):
        self.ui.show_adaptation();self.root.update();self.assertIn('Off',self.ui.actions['reference_collect'].cget('text'))
        self.ui.actions['reference_collect'].invoke();self.root.update()
        self.assertFalse(any(c[0]=='adaptation_action' for c in self.c.calls))
        self.assertIn('consenting participants',self.labels());self.ui.actions['confirm'].invoke();self.ui.poll();self.root.update()
        self.assertTrue(self.c.data['adaptation']['collect']);self.assertFalse(any(c[0]=='start_live' for c in self.c.calls))
        self.assertEqual((self.ui.measure_client()['physical_width'],self.ui.measure_client()['physical_height']),(480,800))
    def test_review_empty_and_freeze_are_visible(self):
        self.ui.show_reference_candidates();self.root.update();self.assertIn('No candidates',self.labels())
        self.c.data['adaptation']=dict(frozen='motion',usable_sec=2.5,confirmed_sec=1.25)
        self.ui.poll();self.ui.show_adaptation();self.root.update()
        self.assertIn('FROZEN: motion',self.labels());self.assertIn('2.50s',self.labels());self.assertIn('confirmed 1.25s',self.labels())
        self.assertIn('bank',self.ui.actions['reference_use'].cget('text'))

if __name__=='__main__':unittest.main()
