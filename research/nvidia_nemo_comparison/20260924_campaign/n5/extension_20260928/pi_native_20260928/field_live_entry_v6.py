"""Actual visible live passage; read README_FIELD_LIVE_RECOVERED_V2.md."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import threading
import time
import traceback
import wave

from field_live_layout_v3 import specification, encoded, finite_json
from field_run_outputs_v1 import SlotGroup


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def identity():
    return dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def sink(root,group):
    rows=specification()['groups'][group]
    mapping={n:(v['maximum_bytes'],v['maximum_write_bytes'],v['mode']=='append') for n,v in rows.items()}
    return SlotGroup(Path(root)/group,dict(maximum_bytes=sum(v[0] for v in mapping.values()),
        maximum_file_bytes=max(v[0] for v in mapping.values()),maximum_write_bytes=max(v[1] for v in mapping.values()),
        maximum_files=len(mapping),minimum_free_bytes=5*1024**3),mapping)


def small(path):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>65536:raise ValueError('Bounded metadata required')
    return finite_json(path.read_bytes())


def worker(root):
    """Fresh systemd child. Gate ACK precedes all installed constructors."""
    from field_child_deadline_v1 import ChildAlarm,validate,remaining
    root=Path(root).resolve();a=small(root/'control/ADMISSION.json')
    cfg=small(root/'config/CONFIG.json');owner=identity()
    if owner['boot_id']!=a['boot_id'] or not datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']):
        raise RuntimeError('Owner boot/expiry changed')
    if a['scope']!='LIVE_SOURCE_MODEL_STORAGE_INTEGRATION' or a['capture'] is not True:
        raise RuntimeError('Genuine live capture admission required')
    if resource.getrlimit(resource.RLIMIT_AS)!=(768*1024**2,)*2 or resource.getrlimit(resource.RLIMIT_STACK)!=(1024**2,)*2:
        raise RuntimeError('AS/stack envelope')
    if os.sched_getaffinity(0)!={2,3}:raise RuntimeError('CPU envelope')
    for row in a['files']:
        path=Path(row['path'])
        if path.is_symlink() or path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
            raise RuntimeError('Changed admitted input: '+str(path))
    threading.stack_size(1024**2)
    control=sink(root,'control');receipts=sink(root,'receipts')
    control.json('OWNER.json',owner)
    cgroup=next(s.split(':',2)[2] for s in Path('/proc/self/cgroup').read_text().splitlines() if s.startswith('0::'))
    quota,period=(Path('/sys/fs/cgroup')/cgroup.lstrip('/')/'cpu.max').read_text().split()
    if quota=='max' or int(quota)/int(period)>2:raise RuntimeError('Shared CPU quota absent')
    control.json('LIVE_ENVELOPE.json',dict(owner=owner,as_limit=list(resource.getrlimit(resource.RLIMIT_AS)),
        stack_limit=list(resource.getrlimit(resource.RLIMIT_STACK)),affinity=sorted(os.sched_getaffinity(0)),
        cgroup=cgroup,cpu_max=[quota,period],initial_available_ram_bytes=available_ram()))
    deadline=validate(cfg['deadline'],a)
    alarm=ChildAlarm(deadline,a).arm()
    controller=context=tkroot=ui=engine=archive=source=None
    result=dict(status='FAILED_PRESERVED',owner=owner,quiet_functional_only=True,accuracy_tested=False,
                physical_touch_tested=False,offline_network_tested=False)
    cleanup_errors=[];began=time.monotonic()
    try:
        while not (root/'control/ACK.json').exists():
            validate(deadline,a)
            if remaining(deadline)<60:raise TimeoutError('Owner ACK not received in useful lifetime')
            time.sleep(.01)
        ack=small(root/'control/ACK.json')
        if ack!=dict(owner=owner,admission_sha256=sha(root/'control/ADMISSION.json')):
            raise RuntimeError('Exact owner ACK mismatch')
        result['owner_ack_before_constructor']=True
        from field_live_controller_v7 import create
        controller,context=create(root/'config/CONFIG.json')
        from app.ui import PrototypeUI
        from d1_visible_controls_v2 import visible,window_state,check_box
        import tkinter as tk

        class LiveUI(PrototypeUI):
            def _show_status(self):
                super()._show_status()
                self.preview_label.configure(text='Nemotron-3 Diarizer / Delayed')
            def show_modes(self):
                super().show_modes()
                for key,button in self.actions.items():
                    if key.startswith('mode_') and key!='mode_open_with_names':
                        button.configure(state='disabled')
            def show_backends(self):
                super().show_backends()
                for key,button in self.actions.items():
                    if key.startswith('backend_') and key!='backend_nemotron_hybrid':
                        button.configure(state='disabled')

        tkroot=tk.Tk(screenName=':0');tkroot.withdraw()
        callback_errors=[]
        tkroot.report_callback_exception=lambda k,v,t:callback_errors.append(k.__name__+': '+str(v)[:512])
        ui=LiveUI(tkroot,controller,allow_auto_start=False)
        visible(tkroot)
        states=[];stable=0;end=time.monotonic()+3
        while time.monotonic()<end:
            tkroot.update();state=window_state(tkroot)
            if not states or states[-1]!=state:
                if len(states)>=16:raise RuntimeError('Geometry state limit')
                states.append(state)
            stable=stable+1 if state['viewable'] and state['geometry']=='480x800+0+0' and state['x']==state['y']==0 else 0
            if stable>=10:break
            time.sleep(.02)
        if stable<10:raise RuntimeError('Actual live window failed geometry gate')
        result['visible_geometry']=dict(states=states,stable_observations=stable,start_button=check_box(tkroot,ui.actions['start_stop']))

        def pump():
            validate(deadline,a);tkroot.update()
            if callback_errors:raise RuntimeError('UI callback: '+str(callback_errors))
            if controller.error:raise RuntimeError(controller.error)
            if available_ram()<192*1024**2:raise RuntimeError('Available RAM sampled stop')
        def complete_command():
            while controller.commands.unfinished_tasks:
                pump();time.sleep(.02)
            pump()
        # The new conversation goes through the actual queued public workflow.
        controller.session_action('new',audio=True,consent=True,title='Private quiet integration')
        complete_command()
        conversation=controller.conversation_id
        if not controller.session_store.metadata(conversation)['audio_requested']:
            raise RuntimeError('Audio retention was not enabled')
        receipts.json('START_REQUEST.json',dict(owner=owner,conversation=conversation,backend=controller.backend_id,
            mode=controller.mode,recipe=controller.recipe,tap=controller.tap,diarizer='Nemotron-3',profile='native_v3_delayed',
            authority=cfg['authority'],authority_sha256=sha(cfg['authority']),capture=True,stop_samples=1920000))
        ui.actions['start_stop'].invoke();pump()
        # This confirmation invokes authorized quiet consent through the real UI.
        if 'confirm' not in ui.actions:raise RuntimeError('Actual microphone consent control missing')
        check_box(tkroot,ui.actions['confirm']);ui.actions['confirm'].invoke()
        complete_command()
        if controller.state!='RUNNING':raise RuntimeError('Start did not reach RUNNING')
        engine=controller.engine;archive=controller.archive;source=engine._source
        if archive is None or not archive.audio:raise RuntimeError('Live audio archive unavailable')
        capture_begin=time.monotonic()
        while source.sent<1920000:
            pump()
            if controller.state not in ('RUNNING','STOPPING'):raise RuntimeError('Unexpected live state')
            if time.monotonic()-capture_begin>140:raise TimeoutError('120 seconds of accepted source not reached')
            time.sleep(.04)
        ui.poll();ui.home();pump()
        result['stop_button']=check_box(tkroot,ui.actions['start_stop'])
        ui.actions['start_stop'].invoke();complete_command()
        if controller.engine is not None or controller.archive is not None or controller.state!='STOPPED':
            raise RuntimeError('Stop did not release the epoch')
        count=source.sent
        if not 1920000<=count<=2080000:raise RuntimeError('Source count')
        if not source.integrity or not source.integrity['ok']:raise RuntimeError('Source integrity failed')
        terminal=source.stop_receipt['terminal'];physical=terminal['source_close']
        if terminal['fault'] is not None or terminal['sent_samples']!=count:raise RuntimeError('Transport/source coverage')
        if not physical['stream_closed'] or not physical['lease_released'] or physical['errors']:
            raise RuntimeError('Physical source ownership remains')
        if any(v not in ('RESTORED','ALREADY_RESTORED') for v in physical['route_restoration'].values()):
            raise RuntimeError('Route restoration failed')
        if source.stop_receipt['child_exit']!=0 or source.stop_receipt['forced_close']:
            raise RuntimeError('Source child did not close naturally')
        if source.thread.is_alive() or archive.thread.is_alive() or not archive.closed or archive.error:
            raise RuntimeError('Source/archive worker closure')
        if archive.written_samples!=count or archive.source_samples!=count or archive.pending_bytes or archive.queue.qsize():
            raise RuntimeError('Archive does not cover all accepted samples')
        if source.timing.snapshot()['model_samples_accepted']!=count:raise RuntimeError('Source clock coverage')
        raw=archive.path/'model_input.f32le';pcm=archive.path/'model_input.wav'
        if raw.stat().st_size!=4*count:raise RuntimeError('Float archive size')
        with wave.open(str(pcm),'rb') as wav:
            if (wav.getnframes(),wav.getnchannels(),wav.getframerate(),wav.getsampwidth())!=(count,1,16000,2):
                raise RuntimeError('PCM reopen coverage')
        receipts.json('GUI_STOP.json',dict(source_samples=count,terminal=terminal,stop_receipt=source.stop_receipt,
            integrity=source.integrity,timeline=source.timing.snapshot(),archive=archive.snapshot(),
            source_thread_joined=True,archive_thread_joined=True,capture_closed=capture_closed()))
        controller.session_action('save',identifier=conversation);complete_command()
        controller.session_action('open',identifier=conversation);complete_command()
        meta=controller.session_store.metadata(conversation)
        if not meta['pinned'] or controller.opened_conversation!=conversation or not capture_closed():
            raise RuntimeError('Save/Open did not retain the stopped conversation')
        receipts.json('SAVE_REOPEN.json',dict(conversation=conversation,pinned=meta['pinned'],opened=controller.opened_conversation,
            source_samples=count,float_bytes=raw.stat().st_size,float_sha256=sha(raw),
            pcm_bytes=pcm.stat().st_size,pcm_sha256=sha(pcm),rows=len(controller.snapshot()['rows']),
            playback=False,private_audio=True))
        result.update(status='PASS_VISIBLE_LIVE_SOURCE_D1_STOP_SAVE_OPEN_ONLY',source_samples=count,
            conversation=conversation,epoch=archive.path.name,native_session=engine.session_dir.name,
            visible_start_stop=True,save_open=True,model_source_joined=True)
    except BaseException as exc:
        result.update(error=type(exc).__name__+': '+str(exc)[:1024],traceback=traceback.format_exc()[-16000:])
        if context:
            context['outputs'].fail('entry',exc,context['outputs'].request_stop,encoded(result))
    finally:
        # Close remains authorized after any failure; do not restart capture or publication.
        if controller is not None:
            try:
                controller.close()
                end=time.monotonic()+45
                while controller.commands.unfinished_tasks and time.monotonic()<end:
                    if tkroot is not None:
                        try:tkroot.update()
                        except Exception:pass
                    time.sleep(.02)
                controller.worker.join(max(0,end-time.monotonic()))
                if controller.worker.is_alive() or controller.commands.unfinished_tasks or not controller.closed:
                    raise RuntimeError('Controller command owner remains')
            except BaseException as exc:cleanup_errors.append(type(exc).__name__+': '+str(exc)[:512])
        if tkroot is not None:
            try:tkroot.destroy()
            except Exception as exc:cleanup_errors.append(repr(exc)[:512])
        alarm.close()
    result['cleanup_errors']=cleanup_errors
    if cleanup_errors:result['status']='FAILED_PRESERVED'
    if context:
        state=context['d1_binding']
        if result['status']!='FAILED_PRESERVED' and not(state['closed'] and state['finish_observed'] and state['samples']==result['source_samples']):
            result.update(status='FAILED_PRESERVED',postclose_error='D1 closure/EOF/source coverage')
        receipts.json('MODEL_CLOSURE.json',state)
        census=context['physical_files'].census()
        if census['failures'] or census['open_writable_descriptors'] or not capture_closed():
            result.update(status='FAILED_PRESERVED',postclose_error='Physical file or microphone closure')
        receipts.json('APPLICATION_CLOSURE.json',dict(controller_closed=bool(controller and controller.closed),
            worker_joined=bool(controller and not controller.worker.is_alive()),
            pending_commands=None if controller is None else controller.commands.unfinished_tasks,
            capture_closed=capture_closed(),physical=census,native=context['native_owner'].snapshot(),
            configuration_attempts=context['configuration'].attempts,configuration_failures=context['configuration'].failures))
    result.update(seconds=time.monotonic()-began,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    receipts.json('RESULT.json',result)
    if context:
        context['outputs'].finish('worker',dict(logical_success=result['status']!='FAILED_PRESERVED',
            work_complete=True,owner=owner,result_sha256=sha(root/'receipts/RESULT.json'),
            physical=context['physical_files'].census()))
    print(json.dumps(dict(status=result['status'],error=result.get('error'))))
    return int(result['status']=='FAILED_PRESERVED')


def available_ram():
    return next(int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))


def capture_closed():
    return Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(worker(args.root))
