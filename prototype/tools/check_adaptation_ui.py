"""Real touch controls/controller, synthetic isolated profiles. See README_ADAPTATION.md."""
import argparse,json,sys,time,tkinter as tk
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor'),str(ROOT/'tests')]
import numpy as np
from app.controller import Controller
from app.paths import default_models_root,sha256
from app.ui import PrototypeUI,prepare_dpi_awareness
from app.reference_adaptation import SessionBank,BaseAnchors
from test_people import ROUTE,quality
from test_adaptation import event,audio
from prototype.tests.native_ui_check import capture

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    c=Controller(args.output/'data',default_models_root());ui=root=None
    try:
        v=np.eye(192,dtype=np.float32)[0];person=c.store.save('UI fixture',v,quality(),ROUTE);c.route=lambda:dict(ROUTE)
        c.switch(mode='enrolled_names',recipe='balanced');c.commands.join();assert not c.error,c.error
        prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,c);root.geometry('+25+25');root.attributes('-topmost',True);root.lift();root.update()
        def poll():c.commands.join();ui.poll();root.update();assert not c.error,c.error
        def screenshot(name):root.lift();root.update();capture(root,args.output/(name+'.png'))
        ui.show_adaptation();screenshot('01_default_off')
        ui.actions['reference_collect'].invoke();assert not c.collect_references
        ui.actions['confirm'].invoke();poll();assert c.collect_references and c.engine is None
        bank=c._adaptation_prepare(None);candidate=bank.observe(event(v),audio(),ROUTE,{'source':'synthetic UI fixture, not accuracy evidence'})
        poll();ui.show_reference_candidates();screenshot('02_pending_review')
        ui.actions['reference_candidate_'+candidate['id']].invoke();screenshot('03_confirm_person')
        ui.actions['reference_confirm_'+person['id']].invoke();ui.actions['confirm'].invoke();poll()
        ui.show_reference_candidates();ui.actions['reference_select_'+candidate['id']].invoke()
        screenshot('04_selected');ui.actions['reference_promote'].invoke();ui.actions['confirm'].invoke();poll()
        assert len(c.store.gallery(ROUTE).environment_bank)==1
        assert 'reference_undo_'+person['id'] in ui.actions # Appears without navigating away after async promotion.
        ui.actions['reference_use'].invoke();ui.actions['confirm'].invoke();poll()
        screenshot('05_matching_on');assert c.use_references and c.engine is None
        ui.show_adaptation();ui.actions['reference_undo_'+person['id']].invoke();ui.actions['confirm'].invoke();poll()
        ui.show_adaptation();screenshot('06_after_undo');assert not c.store.gallery(ROUTE).environment_bank and not c.use_references
        geom=ui.measure_client();assert (geom['physical_width'],geom['physical_height'])==(480,800)
        report=dict(status='PASS',scope='Real Controller and 480x800 widgets, disclosed synthetic profiles; no speech/device or accuracy claim',
            client=geom,promotion_and_undo=True,implicit_capture=False,asr_loads=c.models.asr_loads,speaker_loads=c.models.speaker_loads,
            code_sha256={p.relative_to(ROOT).as_posix():sha256(p) for p in (ROOT/'app/ui.py',ROOT/'app/adaptation_ui.py',ROOT/'app/controller.py',Path(__file__))})
        (args.output/'UI_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
    finally:
        if ui:
            ui.close();deadline=time.monotonic()+15
            while not ui._closed and time.monotonic()<deadline:root.update();time.sleep(.01)
            assert ui._closed
        elif root:root.destroy()
        if not c.closed:c.close()
        c.commands.join();c.worker.join(10)

if __name__=='__main__':main()
