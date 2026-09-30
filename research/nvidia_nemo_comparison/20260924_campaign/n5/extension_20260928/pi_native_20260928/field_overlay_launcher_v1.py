"""Exact candidate-state overlay launch; README_FIELD_OVERLAY_LAUNCHER_V1.md."""
import argparse
import json
import os
from pathlib import Path
import resource
import sys
import threading
import time
import traceback
import field_dependencies_v2 as pins
import field_overlay_deployment_v1 as adapter
import field_overlay_transaction_v1 as transactions

def execute(spec_path):
    sys.dont_write_bytecode=True;threading.stack_size(1024**2)
    root=Path(spec_path).resolve().parent;spec=pins.read(spec_path);case=spec['case']
    if not case or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in case):raise ValueError('Case identifier')
    a=pins.read(root/'ADMISSION.json');pins.configure_output(root,a['target_output_max_bytes'])
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    pins.exclusive(root/(case+'-OWNER.json'),owner)
    result=dict(status='FAILED_PRESERVED',case=case,entered=False,borrowers=0,borrowers_closed=0,models=0,capture=False,GUI=False)
    controller=None;paths=None;old_lock=None;lease=None;began=time.monotonic()
    try:
        if set(spec)!={'case','command','run_admission_sha256','expires_unix','candidate_root','data_root','state_sha256','config_sha256','test_barriers'}:raise ValueError('Launcher spec fields')
        if spec['run_admission_sha256']!=pins.sha(root/'ADMISSION.json') or owner['boot_id']!=a['boot_id']:raise ValueError('Admission binding')
        if not time.time()<spec['expires_unix']<=time.time()+120:raise ValueError('Launcher deadline')
        if a['capture'] or spec['command']!='overlay-controller':raise ValueError('Only no-capture overlay controller command admitted')
        assert sorted(os.sched_getaffinity(0))==[2,3] and resource.getrlimit(resource.RLIMIT_AS)==(768*1024**2,)*2
        assert resource.getrlimit(resource.RLIMIT_STACK)==(1024**2,)*2
        for row in a['files']:assert pins.sha(row['path'])==row['sha256']
        for path,h in a['retained_adapter_files'].items():assert pins.sha(path)==h
        bootstrap=Path(a['installed_release']);sys.path[:0]=[str(bootstrap),str(bootstrap/'vendor'),str(bootstrap/'native')]
        for rel,h in a['installed_files'].items():assert pins.sha(bootstrap/rel)==h
        from release_tools import release as rt
        from release_tools.runtime_lock import RuntimeLock
        import release_tools as namespace
        assert namespace.__spec__.origin is None and {Path(x).resolve() for x in namespace.__path__}=={bootstrap/'release_tools'}
        assert Path(rt.__file__).resolve()==bootstrap/'release_tools/release.py'
        assert Path(sys.modules['release_tools.runtime_lock'].__file__).resolve()==bootstrap/'release_tools/runtime_lock.py'
        data=Path(spec['data_root']);candidate=Path(spec['candidate_root'])
        if data!=root/'data' or candidate!=root/'deployment':raise ValueError('Launcher root binding')
        lease=RuntimeLock(data,'guarded_retained_overlay');raw=(data/'runtime.lock').read_bytes()
        state,state_sha=transactions.inspect(candidate)
        if state_sha!=spec['state_sha256']:raise ValueError('Launcher candidate state changed')
        pointer=state['current'];d=pins.read(pointer['descriptor'])
        if spec['config_sha256']!=d['config_sha256']:raise ValueError('Launcher requested configuration differs from candidate')
        d,manifest,checked=adapter.check_descriptor(pointer['descriptor'],pointer['descriptor_sha256'],rt)
        if d['candidate_root']!=str(candidate) or d['data_root']!=str(data):raise ValueError('Candidate root/data conflict')
        projection=dict(version=d['version'],descriptor=str(Path(pointer['descriptor']).resolve()),descriptor_sha256=pointer['descriptor_sha256'],release=d['release'],manifest_sha256=d['manifest_sha256'],inference_started=False)
        if pointer!=projection:raise ValueError('Candidate pointer projection')
        if d['overlay'] is None:raise ValueError('Selected candidate has no archive overlay; no fallback')
        for name,h in d['config_sha256'].items():assert pins.sha(data/name)==h
        result.update(state_sha256=state_sha,descriptor_sha256=pointer['descriptor_sha256'],overlay=d['overlay'],dependency_check=checked,
                      config_sha256=d['config_sha256'],lease_token=lease.token,lease_owner_pid=os.getpid())
        def barrier(phase):
            assert (data/'runtime.lock').read_bytes()==raw
            if spec['test_barriers']:
                pins.exclusive(root/(case+'-'+phase+'.json'),dict(owner=owner,phase=phase,lease_token=lease.token,state_sha256=state_sha))
                deadline=time.monotonic()+8;gate=root/(case+'-'+phase+'-continue.json')
                while not gate.exists():
                    if time.monotonic()>deadline:raise TimeoutError('Bounded overlay barrier')
                    time.sleep(.01)
                assert pins.read(gate)==dict(continue_phase=phase,owner_pid=os.getpid())
        barrier('before-entry')
        module=adapter.loaded_overlay(d['overlay'])
        from app import paths
        old_lock=paths.RuntimeLock
        class Borrow:
            def __init__(self,requested,purpose):
                if Path(requested).resolve()!=data or purpose!='application' or result['borrowers']:raise RuntimeError('Unexpected overlay borrower')
                assert (data/'runtime.lock').read_bytes()==raw
                self.token=lease.token;self.closed=False;result['borrowers']+=1
            def close(self):
                if not self.closed:self.closed=True;result['borrowers_closed']+=1
        paths.RuntimeLock=Borrow;before_threads={t.ident for t in threading.enumerate()}
        result['entered']=True
        controller=module.create_controller(d['overlay']['descriptor'],d['overlay']['descriptor_sha256'],data)
        assert controller.state=='IDLE' and controller.engine is None and controller.models.asr_loads==controller.models.speaker_loads==0
        assert controller.saved_audio_only and controller.session_store.archive_budget['schema']=='just-peachy.archive-budget.v2'
        barrier('controller-active')
        controller.close();controller.commands.join();controller.worker.join(10)
        assert controller.closed and not controller.worker.is_alive() and controller.commands.unfinished_tasks==0
        assert result['borrowers']==result['borrowers_closed']==1
        assert not [t for t in threading.enumerate() if t.ident not in before_threads]
        assert transactions.inspect(candidate)[1]==state_sha and (data/'runtime.lock').read_bytes()==raw
        barrier('after-entry')
        result.update(controller_closed=True,worker_joined=True,pending_commands=0,lease_continuous=True,threads_closed=True)
        result['status']='PASS_GUARDED_RETAINED_OVERLAY_ONLY'
    except Exception as exc:result.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc()[-16000:])
    finally:
        if controller is not None:
            if not controller.closed:controller.close()
            controller.commands.join();controller.worker.join(10)
            if controller.worker.is_alive():raise RuntimeError('Do not release data ownership with live controller worker')
        if paths is not None and old_lock is not None:paths.RuntimeLock=old_lock
        if lease is not None:lease.close();result['lease_released']=True
    result.update(elapsed_seconds=time.monotonic()-began,address_space=list(resource.getrlimit(resource.RLIMIT_AS)),stack=list(resource.getrlimit(resource.RLIMIT_STACK)),affinity=sorted(os.sched_getaffinity(0)))
    pins.exclusive(root/(case+'-RESULT.json'),result)
    print(json.dumps({k:result.get(k) for k in ['status','case','entered','error']}))
    return int(result['status']!='PASS_GUARDED_RETAINED_OVERLAY_ONLY')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--launch',type=Path,required=True)
    raise SystemExit(execute(p.parse_args().launch))
