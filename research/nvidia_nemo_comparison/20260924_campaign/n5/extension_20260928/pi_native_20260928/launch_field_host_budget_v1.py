"""Bounded host-only fixture using retained job interface. See accompanying README."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import ctypes
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import sys
import time
import field_host_budget_v1 as h

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
BASE = LOCAL/'n5/research-extension-20260928/pi-native-20260928'
ROOT = BASE/'field-host-budget-v1-evidence'
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[2]/'supervision'))
from window_guard_v5 import budget, window
from common import bind, verify
from private_application_two_cpu_v1 import PrivateApplicationProcess, EXTENDED_LIMIT, checked
import supervisor


def main(census, closure_version):
    now = datetime.now(timezone.utc)
    w = window()
    closure_path = BASE/f'NATIVE_CLOSURE_V{closure_version}.json'
    resources_path = BASE/f'NATIVE_RESOURCES_V{closure_version}.json'
    c = json.loads(census.read_bytes()); r = json.loads(resources_path.read_bytes())
    closure = json.loads(closure_path.read_bytes())
    assert time.time()-census.stat().st_mtime < 900
    assert (now-datetime.fromisoformat(closure['checked_utc'])).total_seconds() < 900
    assert not c['active_allocations'] and closure['capture'] == 'closed'
    assert closure['hardware_lease_free'] and closure['research_lease_free']
    assert not ROOT.exists()
    requested = 8*h.MIB
    calc = budget(c['calculation']['existing_bytes'] + r['host_window_bytes']-c['calculation']['window_used_bytes']+r['target_bytes'],
                  r['combined_bytes'], requested, {d: shutil.disk_usage(d+'/').free for d in ('C:', 'G:')}, 52)
    assert psutil.virtual_memory().available >= 8*1024**3
    expiry = now+timedelta(seconds=300)
    assert expiry < datetime.fromisoformat(w['checkpoint_utc'])
    inputs = [BASE/'field-metadata-budget-v1-evidence/target/control'/n for n in ('OWNER.json','LIVE_ENVELOPE.json')]
    files = [HERE/n for n in ('field_host_budget_v1.py','field_host_budget_protocol_v1.py',
                             'launch_field_host_budget_v1.py','review_field_host_budget_v1.py','README_FIELD_HOST_BUDGET_V1.md')]
    files += [HERE.parent/'window_guard_v5.py', HERE.parent/'WINDOW_V5.json',
              HERE.parents[1]/'private_application_two_cpu_v1.py', Path(supervisor.__file__), Path(sys.executable)]
    admission = dict(schema='HOST_METADATA_FIXTURE_V1', admitted_utc=now.isoformat(), expires_utc=expiry.isoformat(),
                     scope='Bounded host metadata and small exact backup only; no Pi/model/capture',
                     output_max_bytes=requested, hard_job_commit_bytes=512*h.MIB, wall_seconds=120,
                     affinity=[14], job_affinity=[4,14], threads=1, gpu=False, budget=calc,
                     metadata_limits=h.LIMITS, metadata_directory_reserve_bytes=512*1024,
                     bindings=[bind(p) for p in files], backup_inputs=[bind(p) for p in inputs],
                     census=bind(census), closure=bind(closure_path), resources=bind(resources_path))
    initial = {'ADMISSION.json':h.encoded(admission), 'CENSUS.json':census.read_bytes(),
               'PREFLIGHT.json':h.encoded({'closure':bind(closure_path), 'resources':r})}
    # Validate all inputs before creating the outer fixture root.
    trial = h.HostStore(ROOT/'host')
    for name, raw in initial.items(): trial.preflight(name, raw)
    assert sum(map(len,initial.values())) < h.LIMITS['metadata'][0]
    ROOT.mkdir()
    s = trial.create(initial)
    job = None; outcome = {'logical_success':False}; started = time.monotonic(); samples = []
    with supervisor.lock(BASE/'HOST_EXPORT.lock'):
        try:
            for b in admission['bindings']+admission['backup_inputs']: verify(b)
            job = PrivateApplicationProcess(ROOT/'lifetime', executable_binding=bind(sys.executable),
                script_binding=bind(HERE/'field_host_budget_protocol_v1.py'), arguments=['--root',str(ROOT)])
            owner = job.spawn_suspended()
            limits = EXTENDED_LIMIT()
            limits.BasicLimitInformation.LimitFlags = 0x2000|0x10|0x8|0x200
            limits.BasicLimitInformation.Affinity = (1<<4)|(1<<14)
            limits.BasicLimitInformation.ActiveProcessLimit = 1
            limits.JobMemoryLimit = 512*h.MIB
            checked(job.kernel.SetInformationJobObject(job.job,9,ctypes.byref(limits),ctypes.sizeof(limits)))
            observed = EXTENDED_LIMIT()
            checked(job.kernel.QueryInformationJobObject(job.job,9,ctypes.byref(observed),ctypes.sizeof(observed),None))
            assert observed.JobMemoryLimit == 512*h.MIB and observed.BasicLimitInformation.ActiveProcessLimit == 1
            s.json('JOB_ENVELOPE.json', {'job_commit_bytes':int(observed.JobMemoryLimit), 'active_process_limit':1,
                    'job_affinity_mask':int(observed.BasicLimitInformation.Affinity), 'kill_on_close':True})
            job.resume(lambda identity,**kw: s.json('REGISTERED_OWNER.json',dict(owner=identity,**kw)))
            while not job.root_exited():
                assert time.monotonic()-started < 120
                size = sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
                assert size < requested
                assert psutil.virtual_memory().available >= 8*1024**3
                h.floors(requested)
                proc = psutil.Process(owner['pid'])
                assert abs(proc.create_time()-owner['create_time']) < .001
                samples.append({'seconds':time.monotonic()-started,'rss_bytes':proc.memory_info().rss,'bytes':size})
                time.sleep(.1)
            outcome['worker_exited'] = True
        except Exception as exc:
            outcome['failure'] = s.failure('coordinator',repr(exc).encode('utf-8'),exc)
        finally:
            if job is not None:
                outcome['lifetime'] = job.close(grace_seconds=0)
            outcome['seconds'] = time.monotonic()-started
            outcome['samples'] = samples
            outcome['logical_success'] = bool(outcome.get('worker_exited') and outcome.get('lifetime',{}).get('root_exit_code') == 0)
            s.json('LAUNCH.json', outcome)
            s.json('coordinator-closure.json', {'logical_success':outcome['logical_success'],
                   'owned_job_empty':outcome.get('lifetime',{}).get('job_empty_verified',False)})
    print(json.dumps({'root':str(ROOT),'logical_success':outcome['logical_success']}))
    return int(not outcome['logical_success'])


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--census',type=Path,required=True)
    p.add_argument('--closure-version',type=int,required=True); a=p.parse_args()
    raise SystemExit(main(a.census,a.closure_version))
