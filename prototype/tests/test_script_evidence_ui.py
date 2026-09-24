"""Task09 real Tk with disclosed fixture snapshots. See README_SCRIPT_EVIDENCE.md."""
import argparse,json,time,gc
from pathlib import Path
import sys,tkinter as tk,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor'),str(ROOT/'tests')]
from prototype.app.ui import PrototypeUI,prepare_dpi_awareness,TouchScroll
from prototype.tests.test_ui import StubController,widgets
from app.script_evidence import preview
from test_script_evidence import fixture


class ScriptStub(StubController):
    def enrollment_script_note(self,text):
        self._record('enrollment_script_note',text)
        self.data['enrollment']['script_evidence']['user_corrections'].append({'text':text,'revision':1})
    def script_review(self,person_id):self._record('script_review',person_id)


class ScriptUITests(unittest.TestCase):
    def setUp(self):
        prepare_dpi_awareness();self.root=tk.Tk();self.controller=ScriptStub()
        self.controller.data['enrollment']=dict(state='READY',can_save=True,target_sec=None,script_evidence=preview(fixture()[2]))
        self.ui=PrototypeUI(self.root,self.controller);self.root.update()
    def tearDown(self):
        self.ui.close();self.ui.poll();self.ui=None;self.root=None;gc.collect()
    def labels(self):return '\n'.join(w.cget('text') for w in widgets(self.root) if isinstance(w,tk.Label))

    def test_toggle_review_note_and_portrait(self):
        self.ui.show_advanced();self.ui.actions['text_aware_references'].invoke()
        self.assertTrue(self.controller.data['settings']['text_aware_references'])
        self.assertFalse(any(c[0]=='start_live' for c in self.controller.calls))
        self.ui.show_enrollment_progress();self.ui.actions['script_review'].invoke()
        self.assertIn('Independently decoded',self.labels());self.assertIn('Original retained',self.labels())
        self.ui.actions['script_note'].invoke();self.ui.keyboard_value.insert('1.0','Review only')
        self.ui.actions['keyboard_done'].invoke();self.ui.poll();self.root.update()
        self.assertIn('Review note: Review only',self.labels())
        self.assertEqual(self.ui.measure_client()['physical_width'],480)
        self.assertEqual(self.ui.measure_client()['physical_height'],800)
        self.ui.actions['script_review_back'].invoke()
        self.assertEqual(str(self.ui.actions['enrollment_save']['state']),'normal')

    def test_comparison_is_advisory_and_wrong_stored_person_is_not_shown(self):
        self.controller.data['reference_comparison']=dict(monotonic_sec=time.perf_counter(),
            candidates=[dict(name='Test',base=.61,alternate=.59),dict(name='Other',base=.2,alternate=None)])
        self.ui.poll();self.ui.show_reference_comparison();self.root.update()
        self.assertIn('base 0.610 / alternate 0.590',self.labels());self.assertIn('not probabilities',self.labels())
        self.assertIn('alternate unavailable',self.labels())
        self.controller.data['metrics']['stored_script_review']=dict(person_id='old',document=preview(fixture('Private prior script')[2]))
        self.ui.poll();self.ui.show_script_review('new')
        self.assertNotIn('Private prior script',self.labels())


def screenshots(native,directory):
    """Display real native evidence through the actual controller; no capture."""
    import shutil
    from app.controller import Controller
    from app.paths import default_models_root
    from prototype.tests.native_ui_check import capture
    directory.mkdir(parents=True,exist_ok=False)
    data=directory/'private_ui_data';data.mkdir()
    shutil.copytree(native/'people',data/'people')
    shutil.copy2(native/'DATA_SCHEMA.json',data/'DATA_SCHEMA.json')
    controller=Controller(data,default_models_root());root=None;ui=None
    try:
        prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,controller);root.geometry('+30+30');root.update()
        ui.show_advanced();capture(root,directory/'01_advanced.png')
        ui.actions['text_aware_references'].invoke();controller.commands.join();ui.poll()
        person=controller.store.list()[0];ui.show_script_review(person['id']);controller.commands.join();ui.poll();root.update()
        assert controller.error is None
        capture(root,directory/'02_native_coverage.png')
        scroll=next(w for w in widgets(root) if isinstance(w,TouchScroll) and w.winfo_ismapped())
        scroll.canvas.yview_moveto(1);root.update();capture(root,directory/'03_native_coverage_tail.png')
        # Frozen comparison from the actual native model receipt; not a live query.
        report=json.loads((native/'NATIVE_SCRIPT_CHECK.json').read_text())
        record=report['queries'][0]['base_alternate']
        if ui._poll_handle:root.after_cancel(ui._poll_handle);ui._poll_handle=None
        ui.snapshot['reference_comparison']=record
        ui.show_reference_comparison();root.update_idletasks();capture(root,directory/'04_native_scores_frozen.png')
        geometry=ui.measure_client();assert (geometry['physical_width'],geometry['physical_height'])==(480,800)
        (directory/'UI_CHECK.json').write_text(json.dumps(dict(status='PASS',client=geometry,
            scope='Actual controller loaded copied native fixture profiles and handled review/settings; score page is a frozen native receipt snapshot, not live inference',
            native_receipt=str(native/'NATIVE_SCRIPT_CHECK.json'),microphone=False,models_loaded_by_ui=False),indent=2))
    finally:
        controller.close();controller.worker.join(10)
        if ui:ui.poll()
        elif root:root.destroy()


if __name__=='__main__':
    if '--native-evidence' in sys.argv:
        p=argparse.ArgumentParser();p.add_argument('--native-evidence',type=Path,required=True);p.add_argument('--screenshots',type=Path,required=True)
        args=p.parse_args();screenshots(args.native_evidence,args.screenshots)
    else:unittest.main()
