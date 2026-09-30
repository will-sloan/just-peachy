"""Absolute expiry and forced closure only; README_FIELD_CHILD_DEADLINE_V1.md."""
import copy
import json
import os
from pathlib import Path
import signal
import sys
import time
import field_child_deadline_v1 as deadlines
import field_dependencies_v2 as pins

def run(root,a):
    pins.configure_output(root,a['target_output_max_bytes'])
    sys.path.insert(0,a['installed_release'])
    from release_tools.runtime_lock import RuntimeLock
    rejected=[]
    base=deadlines.create(a)
    for name in ['missing-field','wrong-boot','future-issued','overlong','grace-overmax','noninteger','expired-before-spawn']:
        d=copy.deepcopy(base);now=time.monotonic_ns()
        if name=='missing-field':d.pop('grace_ns')
        elif name=='wrong-boot':d['boot_id']='wrong-boot'
        elif name=='future-issued':
            d.update(issued_ns=now+1_000_000_000,soft_ns=now+3_000_000_000,hard_ns=now+4_000_000_000,grace_ns=1_000_000_000)
        elif name=='overlong':d['hard_ns']+=1_000_000_000;d['soft_ns']+=1_000_000_000
        elif name=='grace-overmax':d['soft_ns']=d['hard_ns']-3_000_000_000;d['grace_ns']=3_000_000_000
        elif name=='noninteger':d['issued_ns']=True
        else:d.update(issued_ns=now-3_000_000_000,soft_ns=now-2_000_000_000,hard_ns=now-1_000_000_000,grace_ns=1_000_000_000)
        pins.exclusive(root/(name+'-INPUT.json'),d)
        try:deadlines.spawn([sys.executable,'-c','raise SystemExit(99)'],d,a)
        except (ValueError,deadlines.DeadlineExpired) as exc:
            row=dict(case=name,rejected=True,error=str(exc));pins.exclusive(root/(name+'-REJECTION.json'),row);rejected.append(row)
        else:raise AssertionError('Rejected deadline launched process')
    # Actual new launcher rejects an expired spec before dependency/controller work.
    spec=dict(case='expired-launcher',command='overlay-controller',run_admission_sha256=pins.sha(root/'ADMISSION.json'),deadline=d,
              candidate_root=str(root/'deployment'),data_root=str(root/'data'),state_sha256='0'*64,config_sha256={},test_barriers=False)
    path=root/'expired-launcher-SPEC.json';pins.exclusive(path,spec)
    outer=deadlines.create(a,lifetime=2,grace=.3)
    with (root/'expired-launcher.log').open('xb') as log:
        proc=deadlines.spawn([sys.executable,'-B',str(root/'field_overlay_launcher_v2.py'),'--launch',str(path)],outer,a,stdout=log,stderr=log)
        outcome=deadlines.supervise(proc,outer,a)
    result=pins.read(root/'expired-launcher-RESULT.json')
    assert proc.returncode==1 and not result['entered'] and 'expired before work' in result['error']
    assert result['borrowers']==0 and not outcome['terminate_sent'] and not (root/'data/runtime.lock').exists()
    pins.exclusive(root/'expired-launcher-COLLECTED.json',dict(supervision_deadline=outer,outcome=outcome,result_sha256=pins.sha(root/'expired-launcher-RESULT.json')))
    cases=[]
    for mode in ['normal','cooperative','stubborn']:
        budget=deadlines.create(a,lifetime=1.2,grace=.25)
        spec=dict(mode=mode,deadline=budget);path=root/(mode+'-SPEC.json');pins.exclusive(path,spec)
        with (root/(mode+'.log')).open('xb') as log:
            proc=deadlines.spawn([sys.executable,'-B',str(root/'field_deadline_fixture_v1.py'),'--spec',str(path)],budget,a,stdout=log,stderr=log)
            try:outcome=deadlines.supervise(proc,budget,a)
            finally:
                if proc.poll() is None:deadlines.supervise(proc,budget,a,abort=True)
        ready=pins.read(root/(mode+'-READY.json'));owner=pins.read(root/(mode+'-OWNER.json'))
        assert ready['owner']==owner and owner['pid']==proc.pid and ready['deadline']==budget
        assert not Path('/proc',str(proc.pid)).exists()
        assert outcome['reaped_ns']<=budget['hard_ns']+500_000_000
        data=root/(mode+'-data');recovery=None
        if mode=='normal':
            assert proc.returncode==0 and not outcome['terminate_sent'] and not outcome['kill_sent']
            assert pins.read(root/(mode+'-RESULT.json'))['lease_closed']
        elif mode=='cooperative':
            result=pins.read(root/(mode+'-RESULT.json'))
            assert proc.returncode==124 and result['expired'] and result['lease_closed'] and not outcome['kill_sent']
        else:
            assert proc.returncode==-signal.SIGKILL and outcome['terminate_sent'] and outcome['kill_sent']
            assert budget['hard_ns']<=outcome['kill_ns']<=budget['hard_ns']+500_000_000
            assert not (root/(mode+'-RESULT.json')).exists()
            stale=(data/'runtime.lock').read_bytes();old=json.loads(stale)
            assert old['pid']==proc.pid and old['token']==ready['lease_token']
            # Existing RuntimeLock reclaims an independently confirmed dead owner.
            # Preserve its exact stale bytes first; never manually delete the lock.
            with (root/'STUBBORN_STALE_LOCK.json').open('xb') as f:f.write(stale)
            lease=RuntimeLock(data,'deadline_fixture_recovery')
            recovery=dict(previous_pid=proc.pid,previous_token=old['token'],new_pid=os.getpid(),new_token=lease.token)
            lease.close()
            assert recovery['new_token']!=recovery['previous_token']
        assert not (data/'runtime.lock').exists()
        row=dict(mode=mode,deadline=budget,outcome=outcome,owner=owner,lease_closed=True,recovery=recovery)
        pins.exclusive(root/(mode+'-COLLECTED.json'),row);cases.append(row)
    pins.exclusive(root/'DEADLINE_CASES.json',dict(rejections=rejected,cases=cases,launcher_expired_rejection=True))
    assert not list(root.rglob('*.wav')) and not list(root.rglob('epoch.json'))
    return dict(status='PASS_ABSOLUTE_CHILD_DEADLINE_FIXTURES_ONLY',rejections=7,expired_launcher=True,fixture_children=3,
                normal_exit=True,cooperative_expiry=True,forced_sigkill=True,stale_lock_recovered_through_interface=True,
                main_deadline_seconds=a['child_deadline_seconds'],grace_seconds=a['child_stop_grace_seconds'],
                models=False,capture=False,GUI=False,controller=False,epoch=False,full_launcher_protocol_v2_executed=False,ownership_closed=True)
