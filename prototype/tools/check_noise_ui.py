"""Real controller route controls and portrait screenshots, no capture. See README_NOISE.md."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
from app.controller import Controller
from app.paths import default_models_root,sha256
from app.ui import PrototypeUI,prepare_dpi_awareness,TouchScroll
from prototype.tests.test_ui import widgets
from prototype.tests.native_ui_check import capture
import tkinter as tk

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);c=Controller(args.output/'data',default_models_root());root=ui=None
    try:
        prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,c);root.geometry('+25+25');root.attributes('-topmost',True);root.lift();root.update()
        assert c.settings.get('enhancement_route','bypass')=='bypass'
        ui.show_noise();capture(root,args.output/'01_bypass.png')
        for route in ('asr','identity','both'):
            ui.actions['noise_'+route].invoke();c.commands.join();ui.poll();root.update()
            assert not c.error and c.settings['enhancement_route']==route and c.engine is None
        capture(root,args.output/'02_both.png')
        scroll=next(w for w in widgets(root) if isinstance(w,TouchScroll) and w.winfo_ismapped())
        scroll.canvas.yview_moveto(1);root.update();capture(root,args.output/'03_explanation.png')
        geometry=ui.measure_client();assert (geometry['physical_width'],geometry['physical_height'])==(480,800)
        c.noise_route('bypass');c.commands.join();ui.poll();assert not c.error
        report=dict(status='PASS',scope='Actual Controller and installed helper loading; idle UI, no speech/device test',
            client=geometry,enhancer_loads=c.models.enhancer_loads,asr_loads=c.models.asr_loads,speaker_loads=c.models.speaker_loads,
            microphone=False,playback=False,final_route=c.settings['enhancement_route'],
            code_sha256={p.relative_to(ROOT).as_posix():sha256(p) for p in (ROOT/'app/ui.py',ROOT/'app/noise_ui.py',ROOT/'app/controller.py',Path(__file__))})
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
