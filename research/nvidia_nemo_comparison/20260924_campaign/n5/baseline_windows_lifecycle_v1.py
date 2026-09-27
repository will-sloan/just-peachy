"""Isolated baseline saved-file lifecycle. See README_BASELINE_WINDOWS_LIFECYCLE_V1.md."""
import argparse
import ctypes as C
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'n4'))
from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from private_application_process_v3 import PrivateApplicationProcess, api, checked


def require(value, message):
    if not value: raise ValueError(message)


def checked_inputs(path):
    a = load(path)
    require(a['scope'] == 'BASELINE_WINDOWS_SAVED_FILE_LIFECYCLE_ONLY', 'Wrong scope')
    for row in a['code']+a['release_files']+a['assets']+[a['audio'],a['manifest'],a['archive'],a['census']]: verify(row)
    return a


def desktop_name():
    kernel,user=api()
    kernel.GetCurrentThreadId.restype=C.c_ulong
    user.GetThreadDesktop.argtypes=[C.c_ulong]; user.GetThreadDesktop.restype=C.c_void_p
    handle=checked(user.GetThreadDesktop(kernel.GetCurrentThreadId()))
    buffer=C.create_unicode_buffer(256); needed=C.c_ulong()
    checked(user.GetUserObjectInformationW(handle,2,buffer,C.sizeof(buffer),C.byref(needed)))
    return buffer.value


def acceptance(result, lifetime):
    require(result.get('status') == 'PASS_BASELINE_PHASE', 'Phase incomplete')
    require(result.get('controller_closed') is True and result.get('worker_alive') is False
            and result.get('lock_released') is True and not result.get('errors'), 'Application did not close cleanly')
    require(result.get('rendered_rows',0)>0 and result.get('saved_audio_only') is True
            and result.get('sentinel_preserved') is True, 'Missing functional evidence')
    require(result.get('phase') in ('infer','reopen') and result.get('stored_rows',0)>0,'Missing persisted rows')
    require(result.get('pages')==[dict(requested=p,actual=p) for p in ('modes','backends','sessions','settings')], 'Navigation incomplete')
    require(result['phase']!='reopen' or result.get('test_session_deleted') is True,'Deletion unverified')
    require(lifetime.get('status')=='OWNED_PROCESS_LIFETIME_CLOSED' and lifetime.get('forced') is False
            and lifetime.get('job_empty_verified') is True and lifetime.get('root_exit_code')==0
            and lifetime.get('observed_members_exited') is True, 'Process closure failed')


def child(admission, output, phase, expected_desktop):
    require(not output.exists(), 'Fresh phase output required'); output.mkdir()
    errors=[]; result=dict(phase=phase,errors=errors); controller=ui=root=None
    # Child diagnostics are private; no transcript is emitted to the caller.
    with (output/'stdout.log').open('x',encoding='utf-8') as out, (output/'stderr.log').open('x',encoding='utf-8') as err:
        sys.stdout=out; sys.stderr=err
        try:
            require(desktop_name()==expected_desktop and expected_desktop.startswith('codex-n1-n4-'), 'Private desktop mismatch')
            a=checked_inputs(admission); release=Path(a['release']); data=Path(a['data'])
            import psutil
            process=psutil.Process()
            require(process.ppid()==a['owner']['pid'] and exact_process(a['owner']) is not None
                    and process.cpu_affinity()==[4],'Admitted parent or child CPU differs')
            registration=load(output.parent/(phase+'-OWNER.json'))
            require(registration['owner']==identity(process),'Child identity differs from registered owner')
            require(datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']),'Child admission expired')
            sys.path[:0]=[str(release),str(release/'vendor')]
            import app.controller
            from app.controller import Controller
            from app.ui import PrototypeUI,prepare_dpi_awareness
            import tkinter as tk
            require(Path(app.controller.__file__).resolve()==release/'app/controller.py','Wrong application import')
            if phase=='infer':
                require(not data.exists(),'Fresh isolated data required'); data.mkdir()
                (data/'people').mkdir(); (data/'people/SYNTHETIC_SENTINEL.txt').write_bytes(b'N5 isolated preservation fixture\n')
            sentinel=bind(data/'people/SYNTHETIC_SENTINEL.txt')
            require(sentinel['sha256']==a['sentinel_sha256'],'Sentinel changed before phase')
            prepare_dpi_awareness(); controller=Controller(data,Path(a['models']),saved_audio_only=True)
            root=tk.Tk(); ui=PrototypeUI(root,controller,allow_auto_start=False)
            deadline=time.monotonic()+240
            def pump(until):
                while not until():
                    require(time.monotonic()<deadline,'Phase deadline reached')
                    require(not (output.parent/'CANCEL').exists()
                            and not (output.parent/(phase+'-lifetime')/'CANCEL').exists(),'Parent cancelled')
                    require(not controller.error,'Controller reported error: '+str(controller.error))
                    root.update(); time.sleep(.02)
            def command(action,**values):
                controller.session_action(action,**values)
                pump(lambda:controller.commands.unfinished_tasks==0)
            root.update(); result['client']=ui.measure_client()
            require((result['client']['physical_width'],result['client']['physical_height'])==(480,800),'Client dimensions differ')
            if phase=='infer':
                controller.switch(mode='caption_only',recipe='fast',tap='O0'); controller.start_file(a['audio']['path'])
                pump(lambda:controller.metrics.get('completed_sessions',0)>=1 and controller.state=='STOPPED'
                     and controller.commands.unfinished_tasks==0)
                require(controller.snapshot()['rows'],'No actual captions')
                identifier=controller.conversation_id
                command('save',identifier=identifier)
                require(controller.session_store.metadata(identifier)['pinned'] is True,'Save did not pin')
                stored=controller.session_store.rows(identifier)
                require(stored,'Empty saved transcript')
                freeze(output/'SAVED.json',dict(identifier=identifier,rows_fingerprint=fingerprint(stored),rows=len(stored),sentinel=sentinel))
            else:
                prior=load(output.parent/'infer/SAVED.json'); identifier=prior['identifier']
                stored=controller.session_store.rows(identifier)
                require(fingerprint(stored)==prior['rows_fingerprint'],'Saved rows changed across process restart')
                require(controller.session_store.metadata(identifier)['pinned'] is True,'Saved pin lost on restart')
                command('open',identifier=identifier)
                require(controller.opened_conversation==identifier,'Open did not select saved session')
            rows=controller.snapshot()['rows']; require(rows,'Opened view is empty')
            # Observe the real GUI poll/render path. This is Tk text evidence, not scanout/touch timing.
            pump(lambda:ui._render_order==[r['id'] for r in rows] and
                 all(ui._display_row(r)[1] in ui.caption_text.get('1.0','end-1c') for r in rows))
            result['rendered_rows']=len(rows); result['stored_rows']=len(stored)
            result['pages']=[]
            for page,show in [('modes',ui.show_modes),('backends',ui.show_backends),('sessions',ui.show_sessions),('settings',ui.show_settings)]:
                show(); root.update(); result['pages'].append(dict(requested=page,actual=ui.page))
                require(ui.page==page,'Navigation failed: '+page)
            if phase=='reopen':
                command('delete',identifier=identifier,confirmed=True)
                require(not controller.session_store.folder(identifier).exists(),'Test session not deleted')
                result['test_session_deleted']=True
            require(bind(data/'people/SYNTHETIC_SENTINEL.txt')==sentinel,'Session operation altered people fixture')
            result.update(sentinel_preserved=True,saved_audio_only=controller.saved_audio_only,
                output_observations=controller.output_defaults,model_cache=controller.snapshot()['metrics'].get('model_cache'))
            require(all(r.get('status')=='DISABLED_SAVED_AUDIO_ONLY' for r in controller.output_defaults),'Audio enumeration was not disabled')
            ui.close(); pump(lambda:controller.closed and not controller.worker.is_alive())
        except Exception as exc:
            errors.append(type(exc).__name__+': '+str(exc))
        finally:
            if controller is not None:
                if not controller.closed and not (ui and ui._closing): controller.close()
                until=time.monotonic()+15
                while controller.worker.is_alive() and time.monotonic()<until: time.sleep(.05)
                result.update(controller_closed=controller.closed,worker_alive=controller.worker.is_alive(),
                              lock_released=not (controller.data_root/'runtime.lock').exists())
            result.update(status='PASS_BASELINE_PHASE' if not errors else 'FAILED_BASELINE_PHASE',
                utc=datetime.now(timezone.utc).isoformat(),owner=identity(__import__('psutil').Process()),
                desktop=expected_desktop,CM5_tested=False,N4_accepted=False,N5_complete=False)
            freeze(output/'RESULT.json',result)
    return 0 if not errors else 1


def host(precheck, output):
    own=identity(pin()); local=HERE.parents[4]/'local'
    require(not output.exists() and output.resolve().is_relative_to(local/'n5'),'Fresh private output required')
    a=checked_inputs(precheck); now=datetime.now(timezone.utc)
    require(0 <= (now-datetime.fromisoformat(a['admitted_utc'])).total_seconds()<120,'Admission stale')
    require(now<datetime.fromisoformat(a['expires_utc'])<datetime(2026,9,28,2,48,19,tzinfo=timezone.utc),'Invalid cutoff')
    require(0 < (datetime.fromisoformat(a['expires_utc'])-datetime.fromisoformat(a['admitted_utc'])).total_seconds()<=600
            and a['output_cap_bytes']==128*1024**2,'Execution bound differs')
    require(all(exact_process(o) is None for o in a['closed_prior_owners']),'Prior owner active')
    for _ in range(50):
        worker=load(local/'supervision/worker.json')
        if worker.get('child_pid')==own['pid'] and worker.get('child_create_time')==own['create_time']:break
        time.sleep(.1)
    require(worker.get('child_pid')==own['pid'] and worker.get('child_create_time')==own['create_time'],'Not supervised owner')
    require(exact_process({k:worker[k] for k in ('pid','create_time')}) is not None,'Supervisor absent')
    require(load(local/'supervision/worker_spec.json')['argv']==__import__('psutil').Process().cmdline(),'Worker argv differs')
    require(Path(a['data']).resolve()==output/'data','Isolated data root differs')
    output.mkdir(); a.update(owner=own,precheck=bind(precheck),supervisor=worker); freeze(output/'ADMISSION.json',a)
    phases=[]; error=None
    try:
        for phase in ('infer','reopen'):
            process=PrivateApplicationProcess(output/(phase+'-lifetime'),executable_binding=bind(sys.executable),
                script_binding=bind(__file__),cpu=4)
            # Desktop is known only after construction; the actual suspended argv is then frozen.
            arguments=['--child','--admission',str(output/'ADMISSION.json'),'--output',str(output/phase),
                       '--phase',phase,'--desktop',process.desktop_name]
            process.argv=[sys.executable,'-B',str(Path(__file__).resolve()),*arguments]
            with process:
                process.spawn_suspended()
                process.resume(lambda who,**values:freeze(output/(phase+'-OWNER.json'),dict(owner=who,**values)))
                began=time.monotonic()
                while not process.root_exited():
                    require(time.monotonic()-began<285,'Process deadline reached')
                    require(datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']),'Allocation expired')
                    require(not (output/'CANCEL').exists(),'Stage cancelled')
                    require(all(shutil.disk_usage(d+':/').free>gib*1024**3 for d,gib in [('C',50),('G',75)]),'Drive reserve breached')
                    require(sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<a['output_cap_bytes'],'Output cap exceeded')
                    time.sleep(1)
            result=load(output/phase/'RESULT.json'); acceptance(result,process.receipt)
            phases.append(dict(phase=phase,result=bind(output/phase/'RESULT.json'),lifetime=bind(process.output/'LIFETIME.json')))
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    for row in a['code']+a['release_files']:verify(row)
    freeze(output/'RESULT.json',dict(status='PASS_BASELINE_WINDOWS_LIFECYCLE_SMOKE' if error is None else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),owner=own,error=error,phases=phases,admission=bind(output/'ADMISSION.json'),
        scope='One saved source, caption-only baseline, two real Windows processes; Tk render/save/reopen/delete smoke only.',
        microphone=False,playback=False,personal_store_used=False,CM5_tested=False,N4_accepted=False,N5_complete=False))
    return int(error is not None)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--precheck',type=Path)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--child',action='store_true')
    parser.add_argument('--admission',type=Path); parser.add_argument('--phase',choices=['infer','reopen']); parser.add_argument('--desktop')
    args=parser.parse_args()
    raise SystemExit(child(args.admission,args.output,args.phase,args.desktop) if args.child else host(args.precheck,args.output))
