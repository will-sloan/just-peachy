"""Visible Save/Open on a copied closed 120-second archive; README_FIELD_SAVED_ACTIONS_V1.md."""
import argparse
from pathlib import Path
import os,resource,time,threading,traceback,json
from datetime import datetime,timezone
from field_live_entry_v7 import identity,ticks,sha,small,sink,available_ram,capture_closed
from field_child_deadline_v1 import validate,remaining,ChildAlarm

def worker(root):
    root=Path(root).resolve();a=small(root/'control/ADMISSION.json');cfg=small(root/'config/CONFIG.json')
    owner=identity();control=sink(root,'control');receipts=sink(root,'receipts')
    if a['scope']!='SAVED_COPY_VISIBLE_SAVE_OPEN' or a['capture'] is not False:raise ValueError('Saved-only admission required')
    if resource.getrlimit(resource.RLIMIT_AS)!=(768*1024**2,)*2 or resource.getrlimit(resource.RLIMIT_STACK)!=(1048576,)*2 or os.sched_getaffinity(0)!={2,3}:raise ValueError('Worker envelope')
    if owner['boot_id']!=a['boot_id'] or not capture_closed():raise ValueError('Boot/capture precondition')
    control.json('OWNER.json',owner)
    cgroup=next(s.split(':',2)[2] for s in Path('/proc/self/cgroup').read_text().splitlines() if s.startswith('0::'))
    quota,period=(Path('/sys/fs/cgroup')/cgroup.lstrip('/')/'cpu.max').read_text().split()
    if quota=='max' or int(quota)/int(period)>2:raise ValueError('CPU quota')
    deadline=validate(cfg['deadline'],a);alarm=ChildAlarm(deadline,a).arm();threading.stack_size(1048576)
    controller=context=tkroot=None;began=time.monotonic()
    result=dict(status='FAILED_PRESERVED',owner=owner,capture_opened=False,models_loaded=False,physical_touch_tested=False)
    cleanup=[]
    try:
        while not (root/'control/ACK.json').exists():
            if remaining(deadline)<60:raise TimeoutError('Owner ACK')
            time.sleep(.01)
        if small(root/'control/ACK.json')!=dict(owner=owner,admission_sha256=sha(root/'control/ADMISSION.json')):raise ValueError('ACK identity')
        result['owner_ack_before_constructor']=True
        for row in a['files']:
            p=Path(row['path'])
            if p.is_symlink() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise ValueError('Admitted input changed')
        from field_saved_controller_v1 import create
        controller,context=create(root,a)
        from app.ui import PrototypeUI
        from d1_visible_controls_v2 import visible,window_state,check_box
        import tkinter as tk
        class SavedUI(PrototypeUI):
            def _show_status(self):
                super()._show_status()
                self.preview_label.configure(text='Nemotron-3 / saved history')
            def home(self):
                super().home()
                self.actions['start_stop'].configure(state='disabled',text='Capture off')
        tkroot=tk.Tk(screenName=':0');tkroot.withdraw();callback=[]
        tkroot.report_callback_exception=lambda k,v,t:callback.append(k.__name__+': '+str(v)[:512])
        ui=SavedUI(tkroot,controller,allow_auto_start=False);visible(tkroot)
        def pump():
            validate(deadline,a);tkroot.update()
            if callback or controller.error or context['outputs'].stop_event.is_set():raise RuntimeError('Saved UI/controller failure: '+str(callback or controller.error))
            if available_ram()<192*1024**2 or not capture_closed():raise RuntimeError('Saved resource/capture guard')
        def complete():
            while controller.commands.unfinished_tasks:pump();time.sleep(.02)
            pump()
        stable=0;states=[];end=time.monotonic()+3
        while time.monotonic()<end:
            pump();s=window_state(tkroot)
            if not states or states[-1]!=s:states.append(s)
            if len(states)>16:raise RuntimeError('Geometry state bound')
            stable=stable+1 if s['viewable'] and s['geometry']=='480x800+0+0' and s['x']==s['y']==0 else 0
            if stable>=10:break
            time.sleep(.02)
        if stable<10:raise RuntimeError('Visible geometry')
        identifier=a['saved_copy']['conversation'];store=controller.session_store
        before=store.metadata(identifier)
        if before['state']!='DRAFT' or before['pinned'] or store.active:raise RuntimeError('Copied closed draft required')
        ui.poll();ui.show_session(identifier);pump()
        save_box=check_box(tkroot,ui.actions['session_pin'])
        ui.actions['session_pin'].invoke();complete()
        after=store.metadata(identifier)
        if after['state']!='SAVED' or after['pinned'] is not True:raise RuntimeError('Actual Save did not persist')
        changes={k for k in set(before)|set(after) if before.get(k)!=after.get(k)}
        if changes-{'state','pinned','updated_utc'}:raise RuntimeError('Unexpected Save metadata mutation')
        ui.poll();ui.show_session(identifier);pump()
        open_box=check_box(tkroot,ui.actions['session_open'])
        ui.actions['session_open'].invoke();complete();ui.poll()
        if controller.opened_conversation!=identifier or controller.state!='STOPPED':raise RuntimeError('Actual Open not observed')
        # All archive payload bytes remain exact; only the copied conversation metadata was saved.
        checked=0
        for row in a['saved_copy']['files']:
            original=Path(row['source']);copied=root/row['relative']
            if sha(original)!=row['sha256'] or original.stat().st_size!=row['bytes']:raise RuntimeError('Immutable source changed')
            if copied.name!='conversation.json' and (sha(copied)!=row['sha256'] or copied.stat().st_size!=row['bytes']):raise RuntimeError('Copied payload changed')
            checked+=1
        if controller.engine is not None or controller.archive is not None or controller.models.asr_loads or controller.models.speaker_loads:
            raise RuntimeError('Saved actions acquired runtime')
        receipts.json('SAVE_REOPEN.json',dict(status='PASS_ACTUAL_VISIBLE_SAVE_OPEN_COPIED_ARCHIVE',conversation=identifier,
            source_root=a['saved_copy']['source_root'],copied_files_verified=checked,save_button=save_box,open_button=open_box,
            state=after['state'],pinned=after['pinned'],changed_metadata_fields=sorted(changes),
            opened_id=controller.opened_conversation,caption_rows=len(controller.rows),caption_links=len(controller.session_rows),
            source_samples=1920000,audio_duration_seconds=120,original_preserved=True,capture_closed=True,
            model_loads=0,geometry=dict(states=states,stable_observations=stable)))
        result['status']='PASS_ACTUAL_VISIBLE_SAVE_OPEN_COPIED_ARCHIVE'
    except BaseException as exc:
        result['error']=type(exc).__name__+': '+str(exc)[:1024]
        sink(root,'failure').write('worker.bin',traceback.format_exc().encode()[:65536])
    finally:
        if controller is not None:
            try:
                controller.close();end=time.monotonic()+45
                while (controller.commands.unfinished_tasks or controller.worker.is_alive()) and time.monotonic()<end:
                    if tkroot is not None:tkroot.update()
                    time.sleep(.02)
                controller.worker.join(.1)
                if not controller.closed or controller.worker.is_alive() or controller.commands.unfinished_tasks:raise RuntimeError('Controller cleanup incomplete')
            except BaseException as exc:cleanup.append(repr(exc)[:512])
        if tkroot is not None:
            try:tkroot.destroy()
            except Exception as exc:cleanup.append(repr(exc)[:512])
        alarm.close()
    physical=context['guard'].census() if context else None
    if cleanup or not capture_closed() or (physical and (physical['failures'] or physical['open_writable_descriptors'])):
        result['status']='FAILED_PRESERVED'
    receipts.json('APPLICATION_CLOSURE.json',dict(controller_closed=bool(controller and controller.closed),
        worker_joined=bool(controller and not controller.worker.is_alive()),pending_commands=None if controller is None else controller.commands.unfinished_tasks,
        capture_closed=capture_closed(),physical=physical,configuration_attempts=context['configuration'].attempts if context else None))
    result.update(cleanup_errors=cleanup,seconds=time.monotonic()-began,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    receipts.json('RESULT.json',result)
    sink(root,'closure').json('worker.json',dict(owner=owner,work_complete=True,logical_success=result['status']!='FAILED_PRESERVED'))
    print(json.dumps(dict(status=result['status'],error=result.get('error'))))
    return int(result['status']=='FAILED_PRESERVED')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    raise SystemExit(worker(p.parse_args().root))
