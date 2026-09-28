"""Isolated nemotron saved-file lifecycle. See README_ASR_FAILURE_V1.md."""
import argparse
import ctypes as C
from dataclasses import replace
import traceback
import hashlib
import wave
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import time

CODE = Path(__file__).resolve().parent
HERE = CODE.parent
sys.path.append(str(HERE/'prepi_20260928'))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent/'n4'))
from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from private_application_two_cpu_v1 import PrivateApplicationProcess, api, checked


def require(value, message):
    if not value: raise ValueError(message)


def checked_inputs(path):
    a=load(path)
    require(a['scope']=='EXTENDED_WINDOWS_ASR_FAILURE_V1','Wrong window scope')
    for row in a['code']+a['release_files']+a['assets']+[a['audio'],a['source_receipt'],a['acceptance'],a['census'],a['window']]+a['runtime_configs']:verify(row)
    from window_guard import window
    window()
    require(a['backend_key']=='nemotron_600m','Unadmitted backend')
    require(a['mode']=='anonymous_conversation' and a['arm']=='parent','Only E0 mode admitted')
    require(a['application_cpus']==[4,14] and a['numerical_threads_per_model']==1,'CPU contract differs')
    require(load(a['acceptance']['path'])['status']=='ACCEPTED_N3_OFFLINE_COMPONENT_SCOPE','N3 acceptance missing')
    d=load(a['source_receipt']['path'])
    require(d['schema']=='extended-ui-error-priority-v1' and d['changed_code']==['app/ui.py'],'Unexpected GUI derivative')
    verify(d['parent_source_receipt']);d=load(d['parent_source_receipt']['path'])
    require(d['schema']=='prepi-e0-runtime-derivative-v1' and d['parent_source_receipt']==a['parent_source_receipt'],'Shutdown ancestry differs')
    verify(a['parent_source_receipt']);verify(a['accepted_source_receipt'])
    shutdown=load(a['parent_source_receipt']['path'])
    require(shutdown['schema']=='prepi-shutdown-derivative-v1','Shutdown ancestry absent')
    stable=shutdown['parent_source_receipt'];verify(stable)
    require(load(stable['path'])['parent_source_receipt']==a['accepted_source_receipt'],'Accepted ancestry differs')
    runtime=next(row for row in a['runtime_configs'] if Path(row['path']).name=='n2_runtime.json')
    require(not {'titanet_manifest','titanet_manifest_sha256','embedding_namespace'} & set(load(runtime['path'])),'Retired E1 dependency remains in selected runtime')
    require(d['changed_code']==['app/controller.py','app/n2_models.py'],'Unexpected source mutation')
    verify(a['shadow_reference_review']);verify(a['shadow_reference_result'])
    reviewed=load(a['shadow_reference_review']['path'])
    require(reviewed['status']=='PASS_PREPI_ONE_FILE_WINDOWS_LIFECYCLE_ONLY' and reviewed['backend_key']==a['backend_key'],'Ungated reference not reviewed')
    require(reviewed['phases'][0]['result']==a['shadow_reference_result'],'Reference phase binding differs')
    return a


def desktop_name():
    kernel,user=api()
    kernel.GetCurrentThreadId.restype=C.c_ulong
    user.GetThreadDesktop.argtypes=[C.c_ulong]; user.GetThreadDesktop.restype=C.c_void_p
    handle=checked(user.GetThreadDesktop(kernel.GetCurrentThreadId()))
    buffer=C.create_unicode_buffer(256); needed=C.c_ulong()
    checked(user.GetUserObjectInformationW(handle,2,buffer,C.sizeof(buffer),C.byref(needed)))
    return buffer.value


from asr_failure_child_v1 import child


def acceptance(result, lifetime):
    require(result['status']=='PASS_CONTROLS_PHASE' and not result['errors'],'Controls phase failed')
    require(result['controller_closed'] and result['worker_alive'] is False and result['lock_released'],'Controller did not close')
    require(result['baseline_rollback'] and result['sentinel_preserved'] and result['saved_audio_only'],'Isolation/rollback failed')
    require(lifetime['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and not lifetime['forced']
        and lifetime['job_empty_verified'] and lifetime['root_exit_code']==0 and lifetime['observed_members_exited'],'Process closure failed')


def output_bytes(output):
    # The application legitimately deletes its own session during reopen.
    # A disappearing file contributes zero retained bytes; other errors fail closed.
    total=0
    for path in output.rglob('*'):
        try:
            if path.is_file(): total+=path.stat().st_size
        except FileNotFoundError:
            continue
    return total


def host(precheck, output):
    own=identity(pin()); local=HERE.parents[4]/'local'
    require(not output.exists() and output.resolve().is_relative_to(local/'n5'),'Fresh private output required')
    a=checked_inputs(precheck); now=datetime.now(timezone.utc)
    require(0 <= (now-datetime.fromisoformat(a['admitted_utc'])).total_seconds()<120,'Admission stale')
    require(now<datetime.fromisoformat(a['expires_utc'])<datetime.fromisoformat(load(a['window']['path'])['checkpoint_utc']),'Invalid cutoff')
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
        for phase in ('controls',):
            process=PrivateApplicationProcess(output/(phase+'-lifetime'),executable_binding=bind(sys.executable),
                script_binding=bind(__file__),cpu=(4,14))
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
                    require(output_bytes(output)<a['output_cap_bytes'],'Output cap exceeded')
                    time.sleep(1)
            result=load(output/phase/'RESULT.json'); acceptance(result,process.receipt)
            phases.append(dict(phase=phase,result=bind(output/phase/'RESULT.json'),lifetime=bind(process.output/'LIFETIME.json')))
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    for row in a['code']+a['release_files']+a['assets']+a['runtime_configs']:verify(row)
    freeze(output/'RESULT.json',dict(status='PASS_WINDOWS_CONTROLS_SMOKE' if error is None else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),owner=own,error=error,phases=phases,admission=bind(output/'ADMISSION.json'),
        scope='Actual Windows A2 ASR missing-model and runtime-hash startup failures, recovery prefix and explicit baseline rollback. Not complete mode or release acceptance.',
        microphone=False,playback=False,personal_store_used=False,CM5_tested=False,N4_accepted=False,N5_complete=False))
    return int(error is not None)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--precheck',type=Path)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--child',action='store_true')
    parser.add_argument('--admission',type=Path); parser.add_argument('--phase',choices=['controls']); parser.add_argument('--desktop')
    args=parser.parse_args()
    raise SystemExit(child(args.admission,args.output,args.phase,args.desktop) if args.child else host(args.precheck,args.output))
