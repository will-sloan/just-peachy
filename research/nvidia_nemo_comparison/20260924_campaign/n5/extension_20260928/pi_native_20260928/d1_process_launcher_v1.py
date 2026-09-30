"""Fresh native process per saved D1 run; README_D1_PROCESS_LAUNCH_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

MANIFEST_SHA = '35911765d993ef2befa06de7172a3b65e54f772150bd26f0e02099f5834e7f1e'


def ticks(pid):
    try:return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:return None


def identity():
    return dict(pid=os.getpid(), start_ticks=ticks(os.getpid()),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def sha(raw):return hashlib.sha256(raw).hexdigest()


def registry(root):
    from d1_process_entry_v1 import Registry
    return Registry((root/'code/D1_MODE_ENTRY_MANIFEST_V1.json').read_bytes(), MANIFEST_SHA)


def read_small(path):
    if path.stat().st_size > 32768:raise ValueError('Oversized launcher metadata')
    return json.loads(path.read_bytes())


def child(root):
    from field_child_deadline_v1 import ChildAlarm, validate
    from field_sidecar_budget_v1 import GroupWriter
    import resource
    root=Path(root).resolve();a=read_small(root/'control/ADMISSION.json')
    threading.stack_size(1024**2)
    assert resource.getrlimit(resource.RLIMIT_AS)==(768*1024**2,)*2
    assert resource.getrlimit(resource.RLIMIT_STACK)==(1024**2,)*2
    assert os.sched_getaffinity(0)=={2,3}
    for pin in a['files']:
        assert sha(Path(pin['path']).read_bytes())==pin['sha256']
    meta=GroupWriter(root/'launch_meta',a['launch_metadata_limits'])
    packet=read_small(root/'launch_meta/REQUEST.json')
    assert set(packet)=={'request','deadline','parent'}
    value=validate(packet['deadline'],a)
    assert packet['parent']['boot_id']==a['boot_id'] and ticks(packet['parent']['pid'])==packet['parent']['start_ticks']
    owner=identity();meta.json('ENTRY_OWNER.json',owner)
    alarm=ChildAlarm(value,a).arm();began=time.monotonic();result=None
    try:
        while not (root/'launch_meta/ACK.json').exists():
            validate(value,a)
            if ticks(packet['parent']['pid'])!=packet['parent']['start_ticks']:raise RuntimeError('Launcher parent disappeared')
            time.sleep(.005)
        ack=read_small(root/'launch_meta/ACK.json')
        assert ack==dict(owner=owner,request_sha256=sha((root/'launch_meta/REQUEST.json').read_bytes()))
        reg=registry(root);request=reg.validate(packet['request'])
        assert request['mode']==a['admitted_mode'] and request['session_id']==root.name
        from d1_process_application_v1 import run
        result=run(root,a,request,reg)
        result.update(child_owner=owner,parent_acknowledged_before_constructor=True,
            child_seconds=time.monotonic()-began,child_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        meta.json('CHILD_RESULT.json',result)
        return 0
    except BaseException as exc:
        import traceback
        meta.json('CHILD_FAILURE.json',dict(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc()[-16000:]))
        raise
    finally:
        alarm.close()


def run(root,admission):
    from field_sidecar_budget_v1 import GroupWriter
    from field_child_deadline_v1 import create, spawn, supervise, remaining
    import tkinter as tk
    root=Path(root);a=admission
    for name in ('launch_meta','launch_logs'):(root/name).mkdir()
    meta=GroupWriter(root/'launch_meta',a['launch_metadata_limits'])
    logs=GroupWriter(root/'launch_logs',a['launch_log_limits'])
    logs.write('child.log',b'')
    reg=registry(root);selected=None;launched=False;proc=None;watch=None;watch_result={};abort=threading.Event()
    assert 'libnemo_speech_' not in Path('/proc/self/maps').read_text() and 'libggml' not in Path('/proc/self/maps').read_text()
    top=tk.Tk(screenName=':0');top.withdraw();callback_errors=[]
    top.report_callback_exception=lambda k,v,t:callback_errors.append(k.__name__+': '+str(v))
    label=tk.Label(top,text='Choose a saved diarizer mode. Live input unavailable.');label.pack()
    buttons={}
    def choose(mode):
        nonlocal selected
        if launched:raise RuntimeError('Current child must close before a new entry')
        selected=reg.request(mode,root.name)
        label.config(text=mode+' saved input; fresh process required.')
        start.config(state='normal' if mode==a['admitted_mode'] else 'disabled')
    def launch():
        nonlocal launched,proc,watch
        if launched or selected is None or selected['mode']!=a['admitted_mode']:raise RuntimeError('Mode not admitted')
        request=reg.validate(selected);value=create(a)
        meta.json('REQUEST.json',dict(request=request,deadline=value,parent=identity()))
        launched=True
        proc=spawn([sys.executable,'-B',str(root/'code/d1_process_launcher_v1.py'),'--child',str(root)],value,a,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0,close_fds=True)
        os.set_blocking(proc.stdout.fileno(),False)
        def monitor():
            try:
                while proc.poll() is None and not abort.is_set() and remaining(value)>0:abort.wait(.01)
                watch_result.update(supervise(proc,value,a,abort=abort.is_set()))
            except BaseException as exc:watch_result['error']=repr(exc)
        watch=threading.Thread(target=monitor,name='d1-entry-deadline',daemon=True);watch.start()
        start.config(state='disabled')
        for button in buttons.values():button.config(state='disabled')
        label.config(text='Saved diarizer child started.')
    for mode in ('streaming','chunk52','delayed'):
        button=tk.Button(top,text=mode,command=lambda m=mode:choose(m));button.pack();buttons[mode]=button
    start=tk.Button(top,text='Open saved run',state='disabled',command=launch);start.pack()
    received=0;acknowledged=False;owner=None;output_failed=False
    def pump():
        top.update()
        assert top.state()=='withdrawn' and not top.winfo_ismapped() and not callback_errors,callback_errors
    def drain():
        nonlocal received,output_failed
        if output_failed:return
        while True:
            block=proc.stdout.read(16384)
            if not block:return
            try:logs.write('child.log',block,append=True)
            except BaseException as exc:
                abort.set();output_failed=True
                retained=False
                try:meta.write('REJECTED_OUTPUT.bin',block);retained=True
                finally:
                    meta.json('OUTPUT_FAILURE.json',dict(error=repr(exc),rejected_bytes=len(block),
                        rejected_sha256=sha(block),rejected_retained=retained,remaining_pipe_tail_retained=False))
                raise
            received+=len(block)
    try:
        buttons[a['admitted_mode']].invoke();pump();assert selected['mode']==a['admitted_mode']
        start.invoke();pump();assert proc is not None and watch is not None
        while proc.poll() is None:
            pump();drain()
            path=root/'launch_meta/ENTRY_OWNER.json'
            if path.exists() and not acknowledged:
                owner=read_small(path)
                assert set(owner)=={'pid','boot_id','start_ticks'}
                assert owner['pid']==proc.pid and owner['boot_id']==a['boot_id'] and ticks(proc.pid)==owner['start_ticks']
                meta.json('ACK.json',dict(owner=owner,request_sha256=sha((root/'launch_meta/REQUEST.json').read_bytes())))
                acknowledged=True
            time.sleep(.005)
        watch.join(3);assert not watch.is_alive() and 'error' not in watch_result,watch_result
        drain();proc.stdout.close()
        assert acknowledged and proc.returncode==0 and not watch_result['terminate_sent'] and not watch_result['kill_sent']
        assert ticks(proc.pid)!=owner['start_ticks']
        assert 'libnemo_speech_' not in Path('/proc/self/maps').read_text() and 'libggml' not in Path('/proc/self/maps').read_text()
        assert sum(max((root/n).stat().st_size,(root/n).stat().st_blocks*512) for n in ('launch_meta','launch_logs'))<=a['launch_directory_reserve_bytes']
        result=read_small(root/'launch_meta/CHILD_RESULT.json')
        assert result['status']=='PASS_FRESH_PROCESS_STREAMING_ENTRY_START_STOP_ONLY'
        assert result['child_owner']==owner and result['mode_entry_request']==selected
        result.update(launcher_parent=identity(),child_reaped=True,child_pipe_closed=True,
            child_deadline_watcher_joined=True,child_supervision=watch_result,launcher_selection_buttons=True,
            launcher_start_button=True,child_owner_acknowledged=True,child_output_bytes=received,
            fresh_process_mode_entry=True)
        meta.json('LAUNCH_CLOSURE.json',dict(owner=owner,watcher=watch_result,pipe_closed=True,
            reaped=True,acknowledged=True,output_bytes=received,selection=selected))
        return result
    except BaseException:
        abort.set()
        raise
    finally:
        if proc is not None:
            if proc.poll() is None:abort.set()
            if watch is not None:watch.join(5)
            if watch is not None and watch.is_alive():raise RuntimeError('Child watcher remains active')
            if proc.poll() is None:raise RuntimeError('Child still active')
            if not proc.stdout.closed:
                try:drain()
                finally:proc.stdout.close()
        top.destroy()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--child',type=Path,required=True)
    args=parser.parse_args();raise SystemExit(child(args.child))
