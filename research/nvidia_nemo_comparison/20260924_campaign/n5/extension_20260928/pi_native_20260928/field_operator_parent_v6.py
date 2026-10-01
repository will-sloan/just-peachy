"""Visible fresh-process parent; README_FIELD_OPERATOR_QUALIFICATION_V5.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import threading
import time
from field_operator_entry_v6 import identity,ticks,sha,small,sink,available_ram,capture_closed
from field_child_deadline_v1 import ChildAlarm,validate,remaining,spawn,supervise

MANIFEST_SHA='35911765d993ef2befa06de7172a3b65e54f772150bd26f0e02099f5834e7f1e'

def run(root):
    root=Path(root).resolve();a=small(root/'control/ADMISSION.json');cfg=small(root/'config/CONFIG.json')
    if a['scope']!='OPERATOR_LIVE_DATA_COMPOSITION' or a['capture'] is not True:raise ValueError('Operator admission')
    if resource.getrlimit(resource.RLIMIT_AS)!=(768*1024**2,)*2 or resource.getrlimit(resource.RLIMIT_STACK)!=(1024**2,)*2:
        raise ValueError('Parent inherited AS/stack envelope')
    if os.sched_getaffinity(0)!={2,3}:raise ValueError('Parent CPU envelope')
    owner=identity()
    if owner['boot_id']!=a['boot_id']:raise ValueError('Parent boot')
    for row in a['files']:
        path=Path(row['path'])
        if path.is_symlink() or path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:raise ValueError('Parent input drift')
    binding=a['operator_parent']
    if type(binding) is not dict or set(binding)!={'mode','manifest_path','manifest_sha256'} or binding['mode']!='delayed' or binding['manifest_sha256']!=MANIFEST_SHA:
        raise ValueError('Exact explicit parent mode/manifest')
    if not any(r['path']==binding['manifest_path'] and r['sha256']==MANIFEST_SHA for r in a['files']):
        raise ValueError('Mode manifest not admitted')
    from d1_process_entry_v1 import Registry
    registry=Registry(Path(binding['manifest_path']).read_bytes(),MANIFEST_SHA)
    if registry.request('delayed',root.name)['mode']!='delayed':raise ValueError('Mode registry drift')
    def unmapped():
        maps=Path('/proc/self/maps').read_text()
        if 'libnemo_speech_' in maps or 'libggml' in maps:raise RuntimeError('Parent mapped a model library')
    unmapped()
    control=sink(root,'control');meta=sink(root,'parent_control');logs=sink(root,'logs')
    control.json('OWNER.json',owner)
    deadline=validate(cfg['deadline'],a);alarm=ChildAlarm(deadline,a).arm()
    top=None;proc=None;watch=None;abort=threading.Event();watch_result={};returning=[]
    callbacks=[];child_owner=None;acknowledged=False;launched=False;reaped=False;received=0;output_failed=False;result=None
    def monitor():
        try:
            while proc.poll() is None and not abort.is_set() and remaining(deadline)>0:abort.wait(.01)
            watch_result.update(supervise(proc,deadline,a,abort=abort.is_set()))
        except BaseException as exc:watch_result['error']=repr(exc)[:512]
    def drain():
        nonlocal received,output_failed
        if output_failed or proc is None:return
        while True:
            block=proc.stdout.read(16384)
            if not block:return
            try:logs.write('child.log',block,append=True)
            except BaseException:
                abort.set();output_failed=True;raise
            received+=len(block)
    try:
        while not (root/'control/ACK.json').exists():
            validate(deadline,a)
            if remaining(deadline)<180:raise TimeoutError('Parent ACK useful lifetime')
            time.sleep(.01)
        if small(root/'control/ACK.json')!=dict(owner=owner,admission_sha256=sha(root/'control/ADMISSION.json')):
            raise RuntimeError('Parent gate ACK')
        import tkinter as tk
        from d1_visible_controls_v2 import visible,window_state,check_box
        top=tk.Tk(screenName=':0');top.withdraw()
        top.report_callback_exception=lambda k,v,t:callbacks.append(k.__name__+': '+str(v)[:512])
        top.configure(background='#111827')
        tk.Label(top,text='Just Peachy',font=('DejaVu Sans',24),bg='#111827',fg='white').pack(pady=20)
        tk.Label(top,text='Nemotron-3 Diarizer',font=('DejaVu Sans',16),bg='#111827',fg='white').pack(pady=8)
        notice=tk.Label(top,text='Delayed mode / one recording\nStart recording inside the next screen.',wraplength=432,
                        font=('DejaVu Sans',13),bg='#111827',fg='white');notice.pack(pady=16)
        def launch():
            nonlocal proc,watch,launched
            if launched or returning or remaining(deadline)<180:raise RuntimeError('Fresh child/time admission required')
            unmapped();launched=True
            packet=dict(parent=owner,mode='delayed',admission_sha256=sha(root/'control/ADMISSION.json'),
                        method_binding_sha256=hashlib.sha256(json.dumps(a['d1_binding'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
            meta.json('REQUEST.json',packet)
            command=[sys.executable,'-B',str(root/'code/field_operator_entry_v6.py'),'--root',str(root)]
            proc=spawn(command,deadline,a,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0,close_fds=True)
            os.set_blocking(proc.stdout.fileno(),False)
            threading.stack_size(1048576)
            watch=threading.Thread(target=monitor,name='operator-child-deadline',daemon=True);watch.start()
            open_button.configure(state='disabled');top.withdraw()
        open_button=tk.Button(top,text='Open Delayed',command=launch,font=('DejaVu Sans',16),height=2)
        open_button.pack(fill='x',padx=16,pady=12)
        for label in ('Streaming / unavailable for live use','Chunk 52 / unavailable for live use'):
            tk.Button(top,text=label,state='disabled',font=('DejaVu Sans',12),height=2).pack(fill='x',padx=16,pady=6)
        def close():
            if proc is not None and proc.poll() is None:
                notice.configure(text='Return from the recording screen first.');return
            if not returning:returning.append('PARENT_CLOSE')
        close_button=tk.Button(top,text='Close',command=close,font=('DejaVu Sans',16),height=2)
        close_button.pack(side='bottom',fill='x',padx=16,pady=16);top.protocol('WM_DELETE_WINDOW',close)
        def stable():
            visible(top);states=[];count=0;end=time.monotonic()+3
            while time.monotonic()<end:
                top.update();state=window_state(top)
                if not states or states[-1]!=state:
                    if len(states)>=16:raise RuntimeError('Parent geometry state cap')
                    states.append(state)
                count=count+1 if state['viewable'] and state['geometry']=='480x800+0+0' and state['x']==state['y']==0 else 0
                if count>=10:return dict(states=states,stable_observations=count)
                time.sleep(.02)
            raise RuntimeError('Parent visible geometry')
        first=stable()
        first['open_button']=check_box(top,open_button);first['close_button']=check_box(top,close_button)
        from field_operator_qualification_v2 import CONTRACT
        if a.get('qualification')!=CONTRACT:raise ValueError('Exact qualification contract')
        returned=None
        open_button.invoke()
        while not returning:
            top.update();validate(deadline,a)
            if callbacks:raise RuntimeError('Parent callback: '+str(callbacks))
            if available_ram()<192*1024**2:raise RuntimeError('Parent sampled RAM stop')
            if proc is not None:
                drain()
                if (root/'parent_control/OWNER.json').exists() and not acknowledged:
                    child_owner=small(root/'parent_control/OWNER.json')
                    if child_owner!=dict(pid=proc.pid,boot_id=a['boot_id'],start_ticks=ticks(proc.pid)):
                        raise RuntimeError('Exact child ownership')
                    # OWNER is atomically visible before its guard is released.
                    # Probe only; never retry a rejected publication. Child has no
                    # remaining parent_control writer until it receives this ACK.
                    import fcntl
                    with (root/'parent_control/.budget.guard').open('rb') as ready_guard:
                        ready_end=time.monotonic()+2
                        while True:
                            validate(deadline,a)
                            if ticks(proc.pid)!=child_owner['start_ticks']:raise RuntimeError('Child disappeared before ready barrier')
                            try:fcntl.flock(ready_guard,fcntl.LOCK_SH|fcntl.LOCK_NB)
                            except BlockingIOError:
                                if time.monotonic()>=ready_end:raise TimeoutError('Child startup guard not released')
                                time.sleep(.002)
                            else:
                                fcntl.flock(ready_guard,fcntl.LOCK_UN)
                                break
                    meta.json('ACK.json',dict(owner=child_owner,request_sha256=sha(root/'parent_control/REQUEST.json')))
                    acknowledged=True
                if proc.poll() is not None and not reaped:
                    watch.join(3);drain();proc.stdout.close();reaped=True
                    if watch.is_alive() or 'error' in watch_result or not acknowledged or proc.returncode!=0 or watch_result.get('terminate_sent') or watch_result.get('kill_sent'):
                        raise RuntimeError('Child did not return naturally: '+repr(watch_result))
                    if ticks(proc.pid)==child_owner['start_ticks'] or not capture_closed():raise RuntimeError('Child/capture remains')
                    child=small(root/'receipts/RESULT.json');closure=small(root/'receipts/APPLICATION_CLOSURE.json')
                    if child['status']!='INTERACTIVE_RETURN_REQUESTED' or not closure['controller_closed'] or not closure['worker_joined'] or closure['pending_commands'] or closure['physical']['open_writable_descriptors']:
                        raise RuntimeError('Child logical closure incomplete')
                    unmapped();returned=stable()
                    notice.configure(text='Recording process closed.\nCapture is off. This admission is used.')
                    check_box(top,close_button);close_button.invoke()
            if remaining(deadline)<65 and (proc is None or reaped):returning.append('ADMISSION_END')
            time.sleep(.01)
        result=dict(status='PASS_PARENT_RETURN_ONLY' if reaped else 'IDLE_PARENT_CLOSED',owner=owner,
            child_owner=child_owner,child_reaped=reaped,child_acknowledged=acknowledged,
            watcher=watch_result,initial_geometry=first,returned_geometry=returned,
            child_output_bytes=received,capture_closed=capture_closed(),model_libraries_unmapped=True,
            accepted_field_runtime=False,repeated_modes_qualified=False)
        meta.json('RESULT.json',result)
    except BaseException as exc:
        abort.set()
        try:meta.json('FAILURE.json',dict(error=type(exc).__name__+': '+str(exc)[:1024],child_output_tail_retained=not output_failed))
        except Exception:pass
        raise
    finally:
        abort.set()
        if proc is not None:
            if watch is not None:watch.join(32)
            if watch is not None and watch.is_alive():raise RuntimeError('Parent watcher remains')
            if proc.poll() is None:raise RuntimeError('Child remains; outer gate retains ownership')
            if not proc.stdout.closed:
                try:drain()
                finally:proc.stdout.close()
        if top is not None:top.destroy()
        alarm.close()
        sink(root,'closure').json('launcher.json',dict(owner=owner,child_owner=child_owner,
            child_reaped=proc is None or proc.poll() is not None,watcher_joined=watch is None or not watch.is_alive(),
            capture_closed=capture_closed(),work_complete=True,logical_success=result is not None))
    return 0
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    raise SystemExit(run(parser.parse_args().root))
