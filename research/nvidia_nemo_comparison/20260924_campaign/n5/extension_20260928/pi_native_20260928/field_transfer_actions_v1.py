"""Visible export/delete/import/open on a copied closed 120-second archive; README_FIELD_TRANSFER_UI_V1.md."""
import argparse
from pathlib import Path
import os,resource,time,threading,traceback,json
from datetime import datetime,timezone
from field_live_entry_v7 import identity,ticks,sha,small,sink,available_ram,capture_closed
from field_child_deadline_v1 import validate,remaining,ChildAlarm

def worker(root):
    root=Path(root).resolve();a=small(root/'control/ADMISSION.json');cfg=small(root/'config/CONFIG.json')
    owner=identity();control=sink(root,'control');receipts=sink(root,'receipts')
    if a['scope']!='SAVED_COPY_VISIBLE_TRANSFER' or a['capture'] is not False:raise ValueError('Saved-only admission required')
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
        from field_transfer_controller_v1 import create
        controller,context=create(root,a)
        from app.ui import PrototypeUI
        from d1_visible_controls_v2 import visible,window_state,check_box
        import tkinter as tk
        # Extract the exact installed FieldUI class, preserving consent/import/UI methods.
        import ast
        from native import field_entry_v5 as entry
        tree=ast.parse(Path(entry.__file__).read_bytes())
        candidates=[n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='FieldUI']
        if len(candidates)!=1:raise RuntimeError('Installed FieldUI shape changed')
        env=dict(entry.__dict__,PrototypeUI=PrototypeUI)
        exec(compile(ast.fix_missing_locations(ast.Module(body=candidates,type_ignores=[])),
                     str(entry.__file__)+':actual-field-ui','exec'),env)
        class SavedUI(env['FieldUI']):
            def button(self,parent,text,command,*args,**kwargs):
                widget=super().button(parent,text,command,*args,**kwargs)
                if str(text).startswith('Export full evidence'):self.transfer_export=widget
                return widget
            def _show_status(self):
                super()._show_status()
                self.preview_label.configure(text='Nemotron-3 / saved transfer')
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
        if before['state']!='SAVED' or not before['pinned'] or store.active:raise RuntimeError('Copied saved archive required')
        buttons=[]
        def invoke(widget,label):
            pump()
            parent=widget.master;canvas=None
            while parent is not None:
                if isinstance(parent,tk.Canvas):canvas=parent;break
                parent=getattr(parent,'master',None)
            if canvas is not None:
                for unused in range(5):
                    pump();top=widget.winfo_rooty()-canvas.winfo_rooty()
                    if top>=0 and top+widget.winfo_height()<=canvas.winfo_height():break
                    box=canvas.bbox('all')
                    if not box or box[3]<=0:raise RuntimeError('Missing scroll region')
                    absolute=canvas.canvasy(top)
                    canvas.yview_moveto(max(0,min(1,(absolute-8)/box[3])))
            rectangle=check_box(tkroot,widget)
            if canvas is not None:
                top=widget.winfo_rooty()-canvas.winfo_rooty()
                if top<0 or top+widget.winfo_height()>canvas.winfo_height():raise RuntimeError('Control clipped by viewport')
            buttons.append(dict(action=label,rectangle=rectangle))
            widget.invoke();pump()
        ui.poll();ui.show_session(identifier);pump()
        invoke(ui.transfer_export,'full_export')
        invoke(ui.actions['confirm'],'export_consent')
        destination=str(root/'conversation_exports/transfer.zip')
        ui.keyboard_value.delete('1.0','end');ui.keyboard_value.insert('1.0',destination)
        invoke(ui.actions['keyboard_done'],'export_path_done');complete()
        if context['transfer']['phase']!=1 or not context['transfer']['binding']['readback']:
            raise RuntimeError('Actual full export/readback incomplete')
        ui.poll();ui.show_session(identifier);pump()
        invoke(ui.actions['session_delete'],'delete_copy')
        invoke(ui.actions['confirm'],'delete_confirmation');complete()
        if store.folder(identifier).exists() or context['transfer']['phase']!=2:
            raise RuntimeError('Actual copied delete incomplete')
        if any((root/'data/people').iterdir()):raise RuntimeError('People directory changed')
        ui.poll();ui.show_sessions();pump()
        invoke(ui.actions['session_import'],'import')
        invoke(ui.actions['confirm'],'import_consent')
        ui.keyboard_value.delete('1.0','end');ui.keyboard_value.insert('1.0',destination)
        invoke(ui.actions['keyboard_done'],'import_path_done');complete()
        if context['transfer']['phase']!=3 or controller.opened_conversation!=identifier:
            raise RuntimeError('Actual import/consumer reopen incomplete')
        ui.poll();ui.show_session(identifier);pump()
        invoke(ui.actions['session_open'],'reopen_import');complete();ui.poll()
        if context['transfer']['phase']!=4 or controller.state!='STOPPED':
            raise RuntimeError('Actual reopened state')
        checked=0
        for row in a['saved_copy']['files']:
            original=Path(row['source']);copied=root/row['relative']
            if sha(original)!=row['sha256'] or original.stat().st_size!=row['bytes']:
                raise RuntimeError('Immutable saved source changed')
            if sha(copied)!=row['sha256'] or copied.stat().st_size!=row['bytes']:
                raise RuntimeError('Imported exact payload changed')
            checked+=1
        if store.metadata(identifier)!=before:raise RuntimeError('Imported metadata not exact')
        if controller.engine is not None or controller.archive is not None or controller.models.asr_loads or controller.models.speaker_loads:
            raise RuntimeError('Transfer actions acquired runtime')
        stage=root/'data/.archive-imports'/a['transfer']['import_token']
        import_receipt=small(stage/'RECEIPT.json')
        if import_receipt['status']!='PUBLISHED' or import_receipt['consumer_validation']['raw_rows']!=0:
            raise RuntimeError('Actual import publication/consumer receipt')
        binding=context['transfer']['binding']
        receipts.json('SAVE_REOPEN.json',dict(status='PASS_ACTUAL_VISIBLE_EXPORT_DELETE_IMPORT_OPEN_COPY',
            conversation=identifier,source_root=a['saved_copy']['source_root'],original_and_import_files_verified=checked,
            actions=context['transfer']['actions'],buttons=buttons,physical_mutations=context['guard'].transfer_receipts,
            export=dict(bytes=binding['zip_bytes'],sha256=binding['zip_sha256'],files=binding['files'],readback=True),
            import_receipt=import_receipt,opened_id=controller.opened_conversation,caption_rows=len(controller.rows),
            source_samples=1920000,source_preserved=True,capture_closed=True,model_loads=0,
            geometry=dict(states=states,stable_observations=stable)))
        result['status']='PASS_ACTUAL_VISIBLE_EXPORT_DELETE_IMPORT_OPEN_COPY'
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
