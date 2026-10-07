"""Nested broker qualification; README_FIELD_OPERATOR_MANUAL_V1.md."""
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

from field_operator_layout_v2 import specification, encoded, finite_json
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
    if a['scope']!='OPERATOR_LIVE_DATA_COMPOSITION' or a['capture'] is not (a['runtime_profile']['definition']['selection']['input_kind']=='microphone'):
        raise RuntimeError('Genuine live capture admission required')
    if resource.getrlimit(resource.RLIMIT_AS)!=(768*1024**2,)*2 or resource.getrlimit(resource.RLIMIT_STACK)!=(1024**2,)*2:
        raise RuntimeError('AS/stack envelope')
    if os.sched_getaffinity(0)!={2,3}:raise RuntimeError('CPU envelope')
    for row in a['files']:
        path=Path(row['path'])
        if path.is_symlink() or path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
            raise RuntimeError('Changed admitted input: '+str(path))
    threading.stack_size(1024**2)
    control=sink(root,'parent_control');receipts=sink(root,'receipts')
    cgroup=next(s.split(':',2)[2] for s in Path('/proc/self/cgroup').read_text().splitlines() if s.startswith('0::'))
    quota,period=(Path('/sys/fs/cgroup')/cgroup.lstrip('/')/'cpu.max').read_text().split()
    if quota=='max' or int(quota)/int(period)>2:raise RuntimeError('Shared CPU quota absent')
    control.json('LIVE_ENVELOPE.json',dict(owner=owner,as_limit=list(resource.getrlimit(resource.RLIMIT_AS)),
        stack_limit=list(resource.getrlimit(resource.RLIMIT_STACK)),affinity=sorted(os.sched_getaffinity(0)),
        cgroup=cgroup,cpu_max=[quota,period],initial_available_ram_bytes=available_ram()))
    # Ready identity is last: parent ACK cannot race startup envelope publication.
    control.json('OWNER.json',owner)
    deadline=validate(cfg['deadline'],a)
    alarm=ChildAlarm(deadline,a).arm()
    controller=context=tkroot=ui=engine=archive=source=None
    result=dict(status='FAILED_PRESERVED',owner=owner,quiet_functional_only=True,accuracy_tested=False,
                physical_touch_tested=False,offline_network_tested=False)
    cleanup_errors=[];began=time.monotonic()
    try:
        packet=small(root/'parent_control/REQUEST.json')
        parent=packet['parent']
        if set(packet)!={'parent','mode','admission_sha256','profile_binding_sha256'} or packet['mode']!=a['runtime_profile']['definition']['selection']['engine_mode']:
            raise RuntimeError('Exact parent request')
        if parent['boot_id']!=a['boot_id'] or ticks(parent['pid'])!=parent['start_ticks']:
            raise RuntimeError('Parent no longer owns child')
        if packet['admission_sha256']!=sha(root/'control/ADMISSION.json') or packet['profile_binding_sha256']!=hashlib.sha256(json.dumps(a['runtime_profile'],sort_keys=True,separators=(',',':')).encode()).hexdigest():
            raise RuntimeError('Parent input binding drift')
        while not (root/'parent_control/ACK.json').exists():
            if ticks(parent['pid'])!=parent['start_ticks']:raise RuntimeError('Parent disappeared before ACK')
            validate(deadline,a)
            if remaining(deadline)<60:raise TimeoutError('Owner ACK not received in useful lifetime')
            time.sleep(.01)
        ack=small(root/'parent_control/ACK.json')
        if ack!=dict(owner=owner,request_sha256=sha(root/'parent_control/REQUEST.json')):
            raise RuntimeError('Exact owner ACK mismatch')
        result['owner_ack_before_constructor']=True
        result['offline_socket_proof']=offline_socket_check()
        result['offline_network_tested']=True
        from field_operator_controller_v6 import create
        controller,context=create(root/'config/CONFIG.json')
        from app.ui import PrototypeUI
        from d1_visible_controls_v2 import visible,window_state,check_box
        import tkinter as tk

        from field_operator_ui_v1 import ui_class
        from native import field_entry_v5 as entry
        returning=[]
        def request_return(reason):
            if not returning:returning.append(reason)
        LiveUI=ui_class(entry,PrototypeUI,context,request_return)
        tkroot=tk.Tk(screenName=':0');tkroot.withdraw()
        callback_errors=[]
        tkroot.report_callback_exception=lambda k,v,t:callback_errors.append(k.__name__+': '+str(v)[:512])
        ui=LiveUI(tkroot,controller,allow_auto_start=False)
        visible(tkroot)
        states=[];stable=0;end=time.monotonic()+3
        while time.monotonic()<end:
            tkroot.update();state=window_state(tkroot)
            if not states or states[-1]!=state:
                if len(states)>=16:raise RuntimeError('Geometry state bound')
                states.append(state)
            stable=stable+1 if state['viewable'] and state['geometry']=='480x800+0+0' and state['x']==state['y']==0 else 0
            if stable>=10:break
            time.sleep(.02)
        if stable<10:raise RuntimeError('Interactive window geometry')
        result['visible_geometry']=dict(states=states,stable_observations=stable,
            return_button=check_box(tkroot,ui.actions['operator_return']))
        stop_requested=False;observed_start=False
        # All recording/data actions require the actual operator controls.
        while not returning:
            tkroot.update();validate(deadline,a)
            if ticks(parent['pid'])!=parent['start_ticks']:raise RuntimeError('Parent disappeared')
            if callback_errors:raise RuntimeError('UI callback: '+str(callback_errors))
            if available_ram()<192*1024**2:raise RuntimeError('Available RAM sampled stop')
            if controller.error or context['outputs'].stop_event.is_set():
                raise RuntimeError(controller.error or 'Required output failed')
            if controller.engine is not None:
                if engine is not None and engine is not controller.engine:
                    raise RuntimeError('Second engine appeared in one recording process')
                engine=controller.engine
                if archive is None:archive=controller.archive
                if source is None:source=getattr(engine,'_source',None)
                if archive is not None and source is not None:observed_start=True
            if observed_start and source.sent>=1920000 and controller.state=='RUNNING' and not stop_requested:
                stop_requested=True;controller.stop()
            if remaining(deadline)<65:
                request_return('ADMISSION_END')
            time.sleep(.02)
        result.update(status='INTERACTIVE_RETURN_REQUESTED',return_reason=returning[0],
            source_samples=0 if source is None else source.sent,
            actual_source_started=observed_start,actual_capture_started=observed_start and a['capture'],source_kind='live' if a['capture'] else 'file',actions=context['actions'].completed,
            auto_started=False,automatic_explicit_button_driver=False,accepted_field_runtime=False)
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
        if state is None:
            profile=context['runtime_profile']['selection']
            if profile['diarization']!='D0':raise RuntimeError('Missing actual D1 closure state')
            state=dict(schema='just-peachy.process-owned-d0-models.v1',owner=owner,
                profile=profile['profile'],embedding=profile['embedding'],
                asr_loads=controller.models.asr_loads,speaker_loads=controller.models.speaker_loads,
                release_requires_exact_process_exit=True,
                physical_process_death_claimed=False,samples=0 if source is None else source.sent)
        if source is not None:result['source_samples']=source.sent
        if result['status']!='FAILED_PRESERVED' and result.get('actual_source_started') and state['schema']=='just-peachy.live-d1-binding.v1' and not(state['closed'] and state['finish_observed'] and state['samples']==result['source_samples']):
            result.update(status='FAILED_PRESERVED',postclose_error='D1 closure/EOF/source coverage')
        if source is not None:
            # Retain raw child wait/forced-close fields rather than infer them.
            receipts.json('GUI_STOP.json',dict(stop_receipt=source.stop_receipt,
                source_samples=source.sent,integrity=source.integrity,
                source_thread_created=source.thread is not None,source_thread_joined=source.thread is not None and not source.thread.is_alive(),
                archive=None if archive is None else archive.snapshot(),
                archive_thread_joined=archive is not None and not archive.thread.is_alive(),
                capture_closed=capture_closed()))
        receipts.json('SAVE_REOPEN.json',dict(status='INTERACTIVE_ACTIONS',
            actions=context['actions'].completed,counts=context['actions'].counts,
            export_binding=context['actions'].binding))
        if context['runtime_profile']['selection']['embedding']=='E1':
            speaker=getattr(controller.models,'speakers',None)
            encoder=getattr(speaker,'encoder',None)
            result['embedding_runtime']=None if encoder is None else dict(encoder.runtime_memory_policy)
        receipts.json('MODEL_CLOSURE.json',state)
        census=context['physical_files'].census()
        if census['failures'] or census['open_writable_descriptors'] or context['configuration'].failures or not capture_closed():
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


def offline_socket_check():
    """Verify this process has no inherited Internet socket and cannot create one."""
    import errno
    import socket
    from pathlib import Path
    import os
    status = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            status[k] = v.strip()
    if status.get('NoNewPrivs') != '1' or status.get('Seccomp') != '2':
        raise RuntimeError('Actual kernel socket restriction missing')
    local = set()
    for name, column in (('unix', 6), ('netlink', 9)):
        raw = Path('/proc/net', name).read_bytes()
        if len(raw) > 262144:
            raise ValueError('Bounded inherited-socket census')
        for line in raw.decode().splitlines()[1:]:
            parts = line.split()
            if len(parts) > column:
                local.add(parts[column])
    inherited = 0
    for fd in Path('/proc/self/fd').iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        if target.startswith('socket:['):
            if target[8:-1] not in local:
                raise RuntimeError('Inherited nonlocal socket rejected')
            inherited += 1
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.close()
    denied = {}
    for family, kind in ((socket.AF_INET, socket.SOCK_STREAM), (socket.AF_INET6, socket.SOCK_DGRAM)):
        try:
            probe = socket.socket(family, kind)
        except OSError as exc:
            if exc.errno not in (errno.EAFNOSUPPORT, errno.EPERM, errno.EACCES):
                raise
            denied[str(int(family))] = exc.errno
        else:
            probe.close()
            raise RuntimeError('Internet socket creation was not denied')
    return dict(schema='just-peachy.offline-sockets.v1',pid=os.getpid(),
        seccomp=2,no_new_privileges=True,ipv4_ipv6_socket_denied=denied,
        inherited_local_sockets=inherited,physical_disconnect_tested=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(worker(args.root))
