"""Measure actual Tk presentation batching on a short synthetic text fixture.

No microphone, model, real people or USB. See README_CAPTION_PRESENTATION.md.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
from prototype.app.ui import PrototypeUI, prepare_dpi_awareness
from prototype.tests.test_ui import StubController
from prototype.tests.native_ui_check import capture as capture_client


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    import psutil
    proc=psutil.Process();begun=time.perf_counter();cpu=sum(proc.cpu_times()[:2])
    prepare_dpi_awareness();root=tk.Tk();c=StubController();ui=PrototypeUI(root,c)
    root.geometry('+25+25');root.attributes('-topmost',True);root.update()
    root.after_cancel(ui._poll_handle);ui._poll_handle=None
    words='THIS IS A SHORT SYNTHETIC DISPLAY TIMING FIXTURE WITH CONTINUOUS PARTIAL REVISIONS'.split()
    fixture=[dict(id='fixture',label='Unknown',raw_asr_text=' '.join(words[:i+1])) for i in range(len(words))]
    untouched=deepcopy(fixture);results=[];captures=[]
    def capture(name):
        root.update()
        path=args.output_dir/(name+'.png')
        capture_client(root,path)
        captures.append(str(path))
    render=ui._render_rows
    try:
        for delay in (0,150,300):
            ui.preferences['display_smoothing_ms']=delay;ui._applied_rows=None
            render([],force=True);arrivals=[];renders=[];first_batch=None;last_render=''
            def measured(rows,force=False):
                nonlocal last_render,first_batch
                render(rows,force=force)
                if rows and rows[0]['raw_asr_text'] != last_render:
                    stamp=time.perf_counter();last_render=rows[0]['raw_asr_text']
                    renders.append(dict(text=last_render,first_change_to_widget_ms=(stamp-first_batch)*1000,
                                        latest_change_to_widget_ms=(stamp-arrivals[-1])*1000))
                    first_batch=None
            ui._render_rows=measured
            def send(index):
                nonlocal first_batch
                now=time.perf_counter();arrivals.append(now)
                if first_batch is None:first_batch=now
                ui._queue_rows([fixture[index]])
            for index in range(len(fixture)):root.after(index*60,lambda i=index:send(i))
            root.after((len(fixture)-1)*60+delay+80,root.quit);root.mainloop()
            assert last_render==fixture[-1]['raw_asr_text'], 'Final text failed to flush'
            results.append(dict(requested_ms=delay,events=len(arrivals),render_batches=len(renders),observations=renders,
                                maximum_first_change_to_widget_ms=max(r['first_change_to_widget_ms'] for r in renders)))
        ui._render_rows=render;assert fixture==untouched
        c.data.update(mode='open_with_names',status='SYNTHETIC UI FIXTURE · no microphone / models',rows=[
            dict(id='long',label='Unknown',raw_asr_text='A LONG PARAGRAPH WITH A CAUTIOUS UNKNOWN LABEL. '*18),
            dict(id='pending',label='Unknown',raw_asr_text='WORDS APPEAR WHILE VOICE EVIDENCE IS COLLECTED')])
        ui.snapshot=c.snapshot();ui.preferences['display_smoothing_ms']=0;ui._show_status();render(c.data['rows']);capture('01_long_pending_MOCK')
        ui.show_people();capture('02_people_MOCK')
        ui.snapshot['people']=[dict(id='long-name-id',name='A very long personal name with many parts '*4)]
        ui.show_people();capture('03_long_name_MOCK')
        ui._preference('preview_zoom',1.25);ui.home();capture('04_comfort_MOCK')
        ui._preference('preview_zoom',1);ui._preference('caption_size','Extra large');ui._preference('theme','High contrast');ui.home();capture('05_accessibility_MOCK')
        ui._preference('caption_size','Compact');ui._preference('theme','Dark')
        ui.snapshot['spatial_view']=dict(state='RUNNING',speech=True,energy=.012,arrows=[
            dict(id='focused_1',angle_deg=35,age_sec=.1,fresh=True),dict(id='focused_2',angle_deg=145,age_sec=.2,fresh=True),
            dict(id='free_running',angle_deg=90,age_sec=.1,fresh=True),dict(id='processed_output',angle_deg=35,age_sec=.1,fresh=True,selected=True,speech=True)],
            associations=[dict(label='Alex (mock)',angle_deg=35,age_sec=.1,fresh=True,speaking=True),
                          dict(label='Blair (mock)',angle_deg=145,age_sec=4,fresh=False,speaking=False)])
        ui._preference('spatial_visualization',True);ui.home();ui._update_spatial_visualization(force=True);capture('06_fresh_and_stale_beams_MOCK')
        ui.snapshot['spatial_view']['state']='STOPPED';ui._update_spatial_visualization(force=True);capture('07_stale_beams_MOCK')
        result=dict(kind='SYNTHETIC TK DISPLAY ONLY; no inference accuracy claim',results=results,
            raw_fixture_unchanged=fixture==untouched,gui_poll_ms=ui.config['poll_ms'],client=ui.measure_client(),
            elapsed_sec=time.perf_counter()-begun,cpu_sec=sum(proc.cpu_times()[:2])-cpu,
            peak_rss_bytes=getattr(proc.memory_info(),'peak_wset',proc.memory_info().rss),screenshots=captures,
            source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'app/ui.py',ROOT/'app/caption_display.py',ROOT/'config/ui.json']})
        (args.output_dir/'PRESENTATION_CHECK.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:result[k] for k in ('elapsed_sec','cpu_sec','peak_rss_bytes','raw_fixture_unchanged')}))
        print(json.dumps([{k:r[k] for k in ('requested_ms','events','render_batches','maximum_first_change_to_widget_ms')} for r in results]))
    finally:
        ui._render_rows=render;ui.close();ui.poll()


if __name__=='__main__':main()
