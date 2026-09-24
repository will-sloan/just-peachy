"""Actual portrait widgets, disclosed stub diagnostics. See README_NOISE.md."""
import gc,sys,tkinter as tk,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
from prototype.app.ui import PrototypeUI,prepare_dpi_awareness
from prototype.tests.test_ui import StubController,widgets

class NoiseStub(StubController):
    def noise_route(self,value):self._record('noise_route',value);self.data['settings']['enhancement_route']=value

class NoiseUITests(unittest.TestCase):
    def setUp(self):
        prepare_dpi_awareness();self.root=tk.Tk();self.c=NoiseStub();self.ui=PrototypeUI(self.root,self.c);self.root.update()
    def tearDown(self):self.ui.close();self.ui.poll();self.ui=None;self.root=None;gc.collect()
    def labels(self):return '\n'.join(w.cget('text') for w in widgets(self.root) if isinstance(w,tk.Label))
    def test_four_routes_default_bypass_and_no_implicit_start(self):
        self.ui.show_noise();self.root.update()
        self.assertIn('Bypass',self.ui.actions['noise_bypass'].cget('text'))
        for route in ('asr','identity','both','bypass'):
            self.ui.actions['noise_'+route].invoke();self.ui.poll();self.root.update()
            self.assertEqual(self.c.data['settings']['enhancement_route'],route)
        self.assertFalse(any(c[0]=='start_live' for c in self.c.calls))
        self.assertIn('separate reference domain',self.labels())
        self.assertEqual((self.ui.measure_client()['physical_width'],self.ui.measure_client()['physical_height']),(480,800))
    def test_unavailable_and_freshness_are_visible_without_noise_probability(self):
        self.c.data['noise']=dict(observations={'beam':dict(state='unknown',source_start_sample=None)},
            actions=['continuous raw captions'],fallback=dict(reason='helper failed'))
        self.ui.poll();self.ui.show_noise();self.root.update()
        self.assertIn('beam: unknown',self.labels());self.assertIn('Helper fallback: helper failed',self.labels())
        self.assertIn('do not prove noise',self.labels())

if __name__=='__main__':unittest.main()
