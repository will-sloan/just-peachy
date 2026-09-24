"""Real Controller/widget flow with labelled synthetic decoding. See README_TRANSCRIPT_REVIEW.md."""
import argparse,json,sys,time,tkinter as tk
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor'),str(ROOT/'tests')]
from test_transcript_review import ReviewControllerTests
from app.ui import PrototypeUI,prepare_dpi_awareness,TouchScroll
from app.paths import sha256
from prototype.tests.test_ui import widgets
from prototype.tests.native_ui_check import capture

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    fixture=ReviewControllerTests();fixture.setUp();c=fixture.c;ui=root=None
    try:
        c._do_review('switch',dict(enabled=False));prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,c)
        root.geometry('+25+25');root.attributes('-topmost',True);root.lift();root.update()
        def poll():c.commands.join();ui.poll();root.update();assert not c.error,c.error
        def snap(name):root.lift();root.update();capture(root,a.output/(name+'.png'))
        ui.show_audio_review(fixture.identifier,fixture.key);poll();snap('01_default_off')
        ui.actions['audio_review_switch'].invoke();poll();ui.actions['audio_review_request'].invoke();root.update()
        assert c.transcript_review.thread is None;ui.actions['confirm'].invoke();c.commands.join()
        c.transcript_review.thread.join(3);poll();assert c.review_snapshot()['status']=='READY'
        snap('02_review_top')
        scroll=next(w for w in widgets(root) if isinstance(w,TouchScroll) and w.winfo_ismapped());scroll.canvas.yview_moveto(1);root.update();snap('03_protected_changes')
        ui.actions['audio_review_adopt_redecode'].invoke();snap('04_explicit_confirmation')
        assert not c.session_store.metadata(fixture.identifier)['corrections']
        ui.actions['confirm'].invoke();poll();assert len(c.session_store.metadata(fixture.identifier)['corrections'])==1
        edit=c.session_store.metadata(fixture.identifier)['corrections'][0]
        c.session_action('undo_correction',identifier=fixture.identifier,edit_id=edit['id']);poll()
        assert c.session_store.metadata(fixture.identifier)['corrections'][-1]['reverts']==edit['id']
        assert sha256(c.session_store.epoch(fixture.identifier,fixture.epoch)/'events.jsonl')==fixture.event_hash
        geometry=ui.measure_client();assert (geometry['physical_width'],geometry['physical_height'])==(480,800)
        report=dict(status='PASS',scope='Actual Controller/touch/annotation workflow; synthetic decoder, not speech accuracy',
            client=geometry,explicit_review_and_adoption=True,undo_preserves_raw=True,microphone=False,playback=False,
            code_sha256={p.relative_to(ROOT).as_posix():sha256(p) for p in (ROOT/'app/ui.py',ROOT/'app/transcript_review_ui.py',ROOT/'app/transcript_review_controller.py',ROOT/'tests/test_transcript_review.py',Path(__file__))})
        (a.output/'UI_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
    finally:
        if ui:
            ui.close();deadline=time.monotonic()+15
            while not ui._closed and time.monotonic()<deadline:root.update();time.sleep(.01)
            assert ui._closed
        if not c.closed:fixture.tearDown()
        else:c.worker.join(3);fixture.tmp.cleanup()

if __name__=='__main__':main()
