"""Private Tk hook and real pre-start application checks. README_PACED_APPLICATION_CELL.md."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import threading
import time
import unittest


class PacedApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('N4_PACED_CELL_ADMISSION'):raise unittest.SkipTest('Use the private launcher')
        here=Path(__file__).resolve().parent;sys.path.insert(0,str(here))
        from common import load,verify
        from metric_process import pin,identity
        cls.admission=load(os.environ['N4_PACED_CELL_ADMISSION']);cls.output=Path(cls.admission['output'])
        for b in cls.admission['code']:verify(b)
        verify(cls.admission['source']);doc=load(cls.admission['source']['path']);cls.source=Path(doc['prototype'])
        sys.path[:0]=[str(cls.source),str(cls.source/'vendor')]
        from paced_application_cell import private_desktop
        cls.desktop=private_desktop();cls.owner=identity(pin());cls.prepared=[]

    @classmethod
    def tearDownClass(cls):
        from common import freeze
        freeze(cls.output/'CHECKS.json',dict(owner=cls.owner,desktop=cls.desktop,prepared_cells=cls.prepared,
            source_events_are_fixtures=True,source_or_model_execution=False,integrated_N4_cells=0))

    def setUp(self):
        import tkinter as tk
        from app.ui import PrototypeUI,prepare_dpi_awareness
        from prototype.tests.test_n1_frontend import EventController
        prepare_dpi_awareness();self.root=tk.Tk();self.c=EventController()
        self.c.data.update(mode='anonymous_conversation',saved_audio_only=True)
        self.ui=PrototypeUI(self.root,self.c,allow_auto_start=False);self.root.update()
        if self.ui._poll_handle:self.root.after_cancel(self.ui._poll_handle);self.ui._poll_handle=None
        self.observer=None
        class Clock:
            origin=None
            def snapshot(s):return dict(source_event_clock_available=s.origin is not None,source_epoch_monotonic_sec=s.origin)
        self.clock=Clock()

    def tearDown(self):
        if self.observer is not None and not self.observer.closed:self.observer.close()
        self.ui._closed=True;self.root.destroy()

    def attach(self):
        from paced_viewport import PacedViewport
        self.observer=PacedViewport(self.ui,self.clock,self.output/self._testMethodName)
        return self.observer

    def row(self,**kwargs):
        from prototype.tests.n1_event_fixtures import row
        value=row('fixture','Research speaker',kwargs.pop('text','A short caption.'),0,1,caption='fixture',final=False)
        value.update(kwargs);return value

    def draw(self,rows,**values):
        self.c.data.update(rows=deepcopy(rows),**values);self.ui.snapshot=self.c.snapshot()
        self.ui._render_rows(self.c.data['rows']);self.root.update_idletasks()

    def pump(self,seconds=.25):
        until=time.perf_counter()+seconds
        while time.perf_counter()<until:self.root.update();time.sleep(.01)

    def test_final_state_without_rewrite_and_no_extra_label_advancement(self):
        from viewport_ledger_v2 import expand_summary
        o=self.attach();r=self.row();self.draw([r]);edits=self.ui._active_pane.edits
        state=deepcopy(self.ui._identity_labels.__dict__);data=deepcopy(self.c.data)
        o._capture('manual');self.assertEqual(self.ui._identity_labels.__dict__,state);self.assertEqual(self.c.data,data)
        r['final']=True;self.draw([r]);self.assertEqual(edits,self.ui._active_pane.edits)
        from common import load
        o.close();expanded=expand_summary(o.ledger.path,load(o.output/'SUMMARY.json'))
        self.assertIsNotNone(expanded['spans'][r['span_ids'][0]]['first_final_visible'])
        self.assertEqual(o.render_calls,2);self.assertIsNone(o.failure)

    def test_periodic_scroll_observation_uses_original_source_clock(self):
        o=self.attach();self.clock.origin=time.perf_counter()-.1
        r=self.row(text=' '.join(f'line{i} with many words to wrap.' for i in range(70)));self.draw([r])
        self.ui._active_pane.follow=False;self.ui.active_text.yview_moveto(1.);self.pump()
        self.assertGreater(o.periodic_calls,0);self.assertEqual(o.ledger.origin,self.clock.origin)
        from viewport_ledger_v2 import expand_summary
        from common import load
        o.close();expanded=expand_summary(o.ledger.path,load(o.output/'SUMMARY.json'))
        latest=expanded['spans'][r['span_ids'][0]]['latest']['row']['panes']['active']
        self.assertTrue(latest['caption_visible']);self.assertFalse(latest['heading_visible'])

    def test_pending_strict_change_is_deferred_until_real_render(self):
        o=self.attach();r=self.row(selected=False);self.draw([r],strict=False)
        count=o.ledger.samples;self.ui.snapshot['strict']=True;o._capture('timer')
        self.assertEqual(o.ledger.samples,count);self.assertEqual(o.deferred_context,1)
        self.draw([r],strict=True);self.assertIsNone(o.failure)
        self.assertNotIn('fixture',self.ui._marks)

    def test_changed_source_origin_invalidates_preserved_prefix(self):
        o=self.attach();self.draw([self.row()]);self.clock.origin=time.perf_counter()-.1;o._capture('manual')
        count=o.ledger.samples;self.clock.origin+=.01;o._capture('manual')
        self.assertEqual(o.ledger.samples,count)
        with self.assertRaises(RuntimeError):o.check()
        self.assertEqual(o.close()['status'],'FAILED_PRESERVED_PREFIX')

    def test_foreign_hook_is_preserved_and_timer_is_cancelled(self):
        o=self.attach();self.draw([self.row()]);foreign=lambda *a,**k:None;self.ui._render_rows=foreign
        result=o.close();self.assertEqual(result['status'],'FAILED_PRESERVED_PREFIX')
        self.assertIs(self.ui._render_rows,foreign);self.assertIsNone(o.timer)

    def test_original_render_exception_propagates_and_remains_failed(self):
        def fail(*a,**k):raise RuntimeError('fixture render failure')
        self.ui._render_rows=fail;o=self.attach()
        with self.assertRaisesRegex(RuntimeError,'fixture render failure'):self.draw([self.row()])
        result=o.close();self.assertEqual(result['failure']['where'],'original_render')
        self.assertIs(self.ui._render_rows,fail)

    def test_wrong_thread_is_rejected_before_accessing_tk(self):
        o=self.attach();errors=[]
        def attempt():
            try:o._capture('manual')
            except ValueError as exc:errors.append(str(exc))
        t=threading.Thread(target=attempt);t.start();t.join(3)
        self.assertFalse(t.is_alive());self.assertEqual(len(errors),1);self.assertEqual(o.ledger.samples,0)

    def test_real_application_prepare_and_close_for_three_engine_families(self):
        from common import bind,load
        from controller_projection import forbid_inference
        from mode_galleries import backend_contract
        from paced_application_cell import ApplicationCell
        catalog=load(self.admission['catalog']['path']);job=self.admission['job']
        with forbid_inference():
            for family in ('PrototypeEngine','N2Engine','N3IdentityEngine'):
                entry=next(r for r in catalog['backends'] if r['implemented'] and backend_contract(catalog,r['key'],'open_with_names')['engine']==family)
                contract=backend_contract(catalog,entry['key'],'open_with_names')
                folder=self.output/'prepared'/family;cell=ApplicationCell(folder,job,contract)
                try:
                    prepared=cell.prepare(source=self.source,models_root=folder/'NO_MODEL_PAYLOAD',runtimes=self.admission['runtimes'],gallery_preparation=self.admission['gallery_preparation'])
                    self.assertEqual(cell.c.backend_id,prepared['backend_id']);self.assertIsNone(cell.c.engine)
                    self.assertIsNone(cell.c.consumer);self.assertEqual(prepared['logical_client'],[480,800])
                    self.assertFalse(cell.c.collect_references);self.assertFalse(cell.c.use_references)
                    self.assertFalse(cell.started);cell.check()
                finally:result=cell.close()
                self.assertEqual(result['status'],'PREPARED_ONLY_CLOSED',str(result))
                self.assertTrue(result['controller_worker_exited']);self.assertFalse(result['source_start_requested'])
                self.assertFalse(result['complete_N4_acceptance'])
                self.prepared.append(dict(engine=family,prepared=bind(folder/'PREPARED.json'),result=bind(folder/'RESULT.json')))
