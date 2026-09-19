"""Bounded native panel or30min actual portrait GUI soak. See tools/README.md."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ.setdefault(key,'1')
from app.paths import atomic_json,default_models_root,sha256
from app.controller import Controller


def short_snapshot(c):
    s=c.snapshot();m=s['metrics']
    return {'utc':datetime.now(timezone.utc).isoformat(),'state':s['state'],'mode':s['mode'],
        'recipe':s['recipe'],'epoch':s['epoch'],'rows':len(s['rows']),'error':s['error'],
        'rss_mib':m.get('rss_mib'),'threads':m.get('threads'),'cpu_seconds':m.get('cpu_seconds'),
        'asr_lag_sec':m.get('asr_lag_sec'),'source_seconds':(c.file_offset+(getattr(c.engine._source,'sent',0) if c.engine else 0))/16000,
        'source_samples':c.file_offset+(getattr(c.engine._source,'sent',0) if c.engine else 0),
        'model_cache':{'asr_loads':c.models.asr_loads,'speaker_loads':c.models.speaker_loads,'streams':c.models.streams},
        'completed_sessions':m.get('completed_sessions')}


def binding():
    return {str(p.relative_to(ROOT)).replace('\\','/'):sha256(p) for folder in ('app','vendor','config') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def close(c):
    if not c.closed:c.close();c.commands.join();c.worker.join(10)
    if not c.closed:raise RuntimeError('Application close failed: '+str(c.error))


def panel(a):
    jobs=[('S45_08_07','O0','balanced','anonymous_conversation',0),
          ('S45_03_03','O0','classic','anonymous_conversation',0),
          ('S45_02_10','O0','patient','enrolled_names',0),
          ('S45_11_03','O1','balanced','open_with_names',0),
          ('S45_06_06','O0','fast','caption_only',15.53),
          ('S45_12_20','O0','balanced','selected_focus',0)]
    result={'scope':'6existing scenes; native source-paced pipeline; no physical capture','jobs':[],'source_bindings':binding()}
    c=Controller(a.output/'private_data',a.models)
    try:
        for scene,tap,recipe,mode,delay in jobs:
            c.writer_delay=delay;c.switch(mode=mode,recipe=recipe,tap=tap,strict=False);c.commands.join()
            if c.error:raise RuntimeError(c.error)
            wav=a.inputs/scene/(tap+'.wav');c.start_file(wav);c.commands.join()
            if c.error:raise RuntimeError(c.error)
            (c.engine.session_dir/'PINNED').touch()
            begun=time.perf_counter()
            while c.state in ('RUNNING','STARTING','STOPPING'):
                if time.perf_counter()-begun>150:raise TimeoutError('Native panel did not finish')
                time.sleep(.5)
            engine=c.engine;state=c.snapshot()
            import soundfile as sf
            info=sf.info(wav)
            row={'scene':scene,'tap':tap,'recipe':recipe,'mode':mode,'source_sha256':sha256(wav),
                'source_frames':info.frames,'delivered_frames':engine._journal.committed_samples,
                'state':state['state'],'error':state['error'],'session':str(engine.session_dir),
                'elapsed_sec':time.perf_counter()-begun,'writer_delay_injected_sec':delay,
                'caption_rows':[r for r in state['rows'] if r['id'].startswith(engine.session_dir.name)],
                'telemetry':engine.telemetry(),'model_cache':state['metrics'].get('model_cache'),
                'writer_counts':[{'accepted':w.accepted,'completed':w.completed,'max_depth':w.max_depth,'error':w.error} for w in engine.text_writers]}
            row['pass']=not row['error'] and row['state']=='STOPPED' and row['source_frames']==row['delivered_frames'] and all(w['accepted']==w['completed'] and not w['error'] for w in row['writer_counts'])
            result['jobs'].append(row);atomic_json(a.output/'PANEL_PROGRESS.json',{'done':len(result['jobs']),'total':len(jobs),'last':scene,'pass':row['pass']})
            if not row['pass']:break
    finally:close(c)
    result['source_unchanged']=binding()==result['source_bindings']
    result['pass']=len(result['jobs'])==len(jobs) and all(j['pass'] for j in result['jobs'])
    atomic_json(a.output/'PANEL_RESULT.json',result)
    print(json.dumps({'panel_pass':result['pass'],'jobs':len(result['jobs']),'output':str(a.output)}))
    return 0 if result['pass'] else 1


def sustained(a):
    import tkinter as tk
    from app.ui import PrototypeUI,prepare_dpi_awareness
    import soundfile as sf
    frames=sf.info(a.wav).frames
    if frames<1800*16000:raise ValueError('Sustained source must contain at least30min')
    c=Controller(a.output/'private_data',a.models)
    c.switch(mode='anonymous_conversation',recipe='balanced');c.commands.join()
    prepare_dpi_awareness();root=tk.Tk();window=PrototypeUI(root,c)
    root.title('Just Peachy — AUTOMATED FILE ACCEPTANCE — no microphone')
    started=time.perf_counter();samples=[];errors=[];switches=[];bound=binding()
    plan=[('caption_only','fast'),('anonymous_conversation','classic'),('enrolled_names','patient'),
          ('open_with_names','balanced'),('selected_focus','balanced')]*4
    last_log=-60;next_switch=90*16000;switch_pending=False;closed_requested=False
    c.start_file(a.wav)
    def tick():
        nonlocal last_log,next_switch,switch_pending,closed_requested
        try:
            elapsed=time.perf_counter()-started
            snapshot=short_snapshot(c);source=snapshot['source_samples']
            if c.engine and c.engine.session_dir:(c.engine.session_dir/'PINNED').touch(exist_ok=True)
            if elapsed-last_log>=60:
                samples.append(dict(elapsed_sec=elapsed,**snapshot));last_log=elapsed
                atomic_json(a.output/'SOAK_PROGRESS.json',{'stage':'30minute actualGUI mixedmode source','elapsed_sec':elapsed,
                    'source_percent':round(source/frames*100,2),'switches':len(switches),'target_switches':20,
                    'latest':snapshot,'approx_source_remaining_sec':max(0,(frames-source)/16000)})
            if c.error and not errors:errors.append(c.error)
            if errors or elapsed>2700:
                if not closed_requested:c.close();closed_requested=True
            elif not closed_requested and not c.commands.unfinished_tasks:
                if c.state=='RUNNING' and source>=next_switch and len(switches)<20:
                    mode,recipe=plan[len(switches)]
                    switches.append({'at_source_sample':source,'requested_mode':mode,'recipe':recipe,'elapsed_sec':elapsed})
                    c.switch(mode=mode,recipe=recipe,strict=False);next_switch+=90*16000
                elif c.state=='STOPPED' and source>=frames:
                    c.close();closed_requested=True
            if c.closed:
                result={'scope':'Actual Tk GUI, existing long WAV, source-paced20controlled transitions, no microphone',
                    'elapsed_sec':elapsed,'source_frames':frames,'delivered_frames':source,
                    'source_duration_sec':frames/16000,'switches':switches,'resource_samples':samples,
                    'errors':errors,'final':snapshot,'actual_client':[root.winfo_width(),root.winfo_height()],
                    'source_bindings':bound,'source_unchanged':binding()==bound,
                    'caption_final_rows':sum(r['final'] for r in c.snapshot()['rows']),
                    'output_default_observations':c.output_defaults,
                    'pass':not errors and source==frames and len(switches)==20}
                atomic_json(a.output/'SOAK_RESULT.json',result);root.destroy();return
        except Exception as exc:
            errors.append(repr(exc))
            if not closed_requested:c.close();closed_requested=True
        root.after(250,tick)
    root.after(250,tick)
    try:root.mainloop()
    finally:close(c)
    result=json.loads((a.output/'SOAK_RESULT.json').read_text())
    print(json.dumps({'soak_pass':result['pass'],'elapsed_sec':result['elapsed_sec'],'output':str(a.output)}))
    return 0 if result['pass'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('panel','sustained'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--models',type=Path,default=default_models_root())
    p.add_argument('--inputs',type=Path);p.add_argument('--wav',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    raise SystemExit(panel(a) if a.command=='panel' else sustained(a))
