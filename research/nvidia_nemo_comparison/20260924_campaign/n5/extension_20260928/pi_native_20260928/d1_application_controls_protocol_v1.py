"""Changed native controls only; README_D1_APPLICATION_CONTROLS_V1.md."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from types import SimpleNamespace
from typing import Any


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selected_class(path, class_name, methods, namespace):
    node = next(n for n in ast.parse(Path(path).read_bytes()).body if isinstance(n, ast.ClassDef) and n.name == class_name)
    body = [deepcopy(n) for n in node.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    assert {n.name for n in body} == set(methods)
    selected = ast.ClassDef(name=class_name, bases=[], keywords=[], body=body, decorator_list=[])
    tree = ast.fix_missing_locations(ast.Module(body=[selected], type_ignores=[]))
    exec(compile(tree, str(path)+':selected-d1-controls', 'exec'), namespace)
    return namespace[class_name]


def run(root, admission):
    import d1_application_controls_v1 as adapter
    from field_sidecar_budget_v1 import GroupWriter
    root = Path(root)
    binding = json.loads((root/'code/D1_APPLICATION_CONTROLS_BINDING_V1.json').read_bytes())
    installed = root.parent/binding['installed_relative_root']
    for name, key in [('controller.py','controller_sha256'),('ui.py','ui_sha256'),('n2_models.py','models_sha256')]:
        assert sha(installed/'app'/name) == binding[key]
    assert sha(root/'code/d1_modes_v1.py') == binding['selector_sha256']
    assert sha(root/'code/D1_MODE_CATALOG_V1.json') == binding['catalog_sha256']
    for name in admission['declared_passage_directories']:
        (root/name).mkdir()
    writer = GroupWriter(root/'passage', admission['passage_limits'])
    closer = GroupWriter(root/'passage_closure', admission['passage_closure_limits'])
    base = selected_class(installed/'app/controller.py', 'Controller', ['_enqueue','_commands'], dict(queue=queue))
    delegates = []
    base._start_session = lambda self:delegates.append('old_start')
    cls = adapter.controller_class(base)
    c = cls.__new__(cls)  # No unchanged Controller constructor or model bundles.
    c.closed=False;c.state='IDLE';c.engine=None;c.consumer=None;c.enrollment={'state':'IDLE'}
    c._n2_components={'diarization':'D1'};c.models=SimpleNamespace(diarizer=None)
    c.commands=queue.Queue(maxsize=1);c.error=None;c.status='Idle';c.initialize_d1_controls()
    c._do_noop=lambda:None
    selected_ui = selected_class(installed/'app/ui.py', 'PrototypeUI', ['_call'], dict(Any=Any))
    tkroot=None;threads=[];cases=[];finished=False
    original_maps=adapter.modes.mapped_paths

    def drain():
        deadline=time.monotonic()+2
        while c.commands.unfinished_tasks:
            assert time.monotonic()<deadline,'Changed command did not complete'
            time.sleep(.001)

    def start_worker():
        t=threading.Thread(target=c._commands);threads.append(t);t.start();return t

    def stop_worker(t):
        c.commands.put_nowait(None);t.join(2);assert not t.is_alive();assert c.commands.unfinished_tasks==0

    def reject(name, action, text):
        before=deepcopy(c._d1_selected)
        try:action()
        except RuntimeError as exc:
            assert text in str(exc),(name,str(exc))
            cases.append(dict(case=name,error=str(exc),selection_unchanged=c._d1_selected==before))
            assert c._d1_selected==before
        else:raise AssertionError(name+' accepted')

    try:
        tkroot=tk.Tk();tkroot.withdraw();tkroot.geometry('480x800')
        frames=[];notices=[]
        def page(self,title,*,scroll=True,back=None):
            f=tk.Frame(tkroot);f.pack();frames.append(f);return f
        selected_ui._page=page;selected_ui.show_modes=lambda self:None
        selected_ui._show_status=lambda self:notices.append(self._notice)
        UI=adapter.ui_class(selected_ui);u=UI.__new__(UI)
        u.controller=c;u._notice='';u._page('Mode')
        assert u._d1_navigation.winfo_class()=='Button'
        u._d1_navigation.invoke()
        panel=next(f for f in frames[-1].winfo_children() if isinstance(f,adapter.D1ModePanel))
        assert u.page=='diarizer_modes' and u._page_update==panel.refresh
        assert tkroot.state()=='withdrawn' and not tkroot.winfo_ismapped()
        assert set(panel.choices)=={'delayed','streaming','chunk52'} and str(panel.launch['state'])=='disabled'
        panel.choices['delayed'].invoke()
        assert c._d1_pending and c._d1_selected is None and 'selected' not in panel.choices['delayed']['text']
        reject('duplicate-pending',lambda:c.select_d1_mode('streaming'),'already queued')
        t=start_worker();drain();panel.refresh();stop_worker(t)
        assert c._d1_selected['id']=='delayed' and panel.choices['delayed']['text'].endswith(' · selected')
        cases.append(dict(case='actual-navigation-and-delayed-completion',pending_not_optimistic=True,command_thread_joined=True))

        panel.choices['streaming'].invoke();assert c._d1_pending
        c.state='RUNNING';t=start_worker();drain();panel.refresh()
        assert c._d1_selected['id']=='delayed' and c._d1_error and 'Stop the session' in panel.summary['text']
        c.commands.put_nowait(('noop',(),{}));drain();assert c.error is None and c._d1_error
        stop_worker(t);c.state='IDLE'
        cases.append(dict(case='queued-state-race',selection_unchanged=True,control_error_survives_command_reset=True,command_thread_joined=True))
        t=start_worker()
        for mode in ['streaming','chunk52']:
            panel.refresh();panel.choices[mode].invoke();drain();panel.refresh()
            assert c._d1_selected['id']==mode and str(panel.launch['state'])=='disabled'
            assert next(x for x in c.d1_snapshot()['modes'] if x['id']==mode)['native_factory_checked'] is False
            cases.append(dict(case='actual-choice-'+mode,selected=mode,native_factory_checked=False,launch_disabled=True))
        stop_worker(t)
        for state in ['RUNNING','STOPPING','ERROR']:
            c.state=state;reject('state-'+state,lambda:c.select_d1_mode('delayed'),'Stop the session')
        c.state='STOPPED';c.engine=object();reject('stopped-engine-owner',lambda:c.select_d1_mode('delayed'),'engine still owns');c.engine=None
        c.consumer=SimpleNamespace(is_alive=lambda:True);reject('stopped-consumer-owner',lambda:c.select_d1_mode('delayed'),'worker still owns');c.consumer=None
        c.enrollment['state']='RECORDING';reject('enrollment-owner',lambda:c.select_d1_mode('delayed'),'Finish enrollment');c.enrollment['state']='IDLE'
        c.models.diarizer=object();reject('resident-model',lambda:c.select_d1_mode('delayed'),'fresh process');c.models.diarizer=None
        adapter.modes.mapped_paths=lambda:['/retained/libnemo_speech_asr.so'];reject('mapped-runtime-fixture',lambda:c.select_d1_mode('delayed'),'fresh process');adapter.modes.mapped_paths=original_maps
        c._n2_components={'diarization':'D0'};reject('wrong-backend',lambda:c.select_d1_mode('delayed'),'Nemotron');c._n2_components={'diarization':'D1'}
        c.commands.put_nowait(('noop',(),{}));reject('full-command-queue',lambda:c.select_d1_mode('delayed'),'Too many pending');assert not c._d1_pending
        c.commands.get_nowait();c.commands.task_done()
        c.closed=True;assert u._call('select_d1_mode','delayed') is False;assert notices[-1]=='Application closed';c.closed=False
        cases.append(dict(case='actual-ui-call-closed',notice=notices[-1],no_queued_command=True))
        reject('start-blocked-before-old-loader',c._start_session,'not connected');assert not delegates
        request=c.d1_launch_request();assert not request['launchable'] and request['requires_fresh_process'] and request['requires_independent_session']
        request['selection']['geometry']['chunk_frames']=1;assert c.d1_launch_request()['selection']['geometry']['chunk_frames']==52
        cases.append(dict(case='detached-request-not-launchable',caller_mutation_isolated=True))
        panel.refresh();snapshot=c.d1_snapshot();assert not snapshot['launch_available']
        writer.json('CASES.json',cases);writer.json('CONTROL_SNAPSHOT.json',snapshot);writer.json('LAUNCH_REQUEST.json',c.d1_launch_request())
        finished=True
    finally:
        adapter.modes.mapped_paths=original_maps
        for t in threads:
            if t.is_alive():
                try:c.commands.put_nowait(None)
                except queue.Full:pass
                t.join(2)
        if tkroot is not None:tkroot.destroy()
        closer.json('CONTROL_CLOSURE.json',dict(all_command_threads_joined=all(not t.is_alive() for t in threads),
                    command_threads=len(threads),pending_commands=c.commands.unfinished_tasks,Tk_destroy_called=tkroot is not None,
                    checks_complete=finished,old_start_delegations=len(delegates)))
    assert all(not t.is_alive() for t in threads) and c.commands.unfinished_tasks==0
    return dict(status='PASS_D1_CONTROLS_WITHDRAWN_DETACHED_ONLY',cases=len(cases),expected_rejections=sum('error' in x for x in cases),
                actual_Tk_buttons=True,Tk_withdrawn=True,visible_rendering=False,physical_touch=False,
                selected_installed_queue_methods=True,selected_installed_UI_call=True,controller_constructor=False,
                command_threads=len(threads),all_command_threads_joined=True,pending_commands=0,
                models=False,capture=False,source_audio_samples=0,application_launchable=False,full_application_installed=False)
