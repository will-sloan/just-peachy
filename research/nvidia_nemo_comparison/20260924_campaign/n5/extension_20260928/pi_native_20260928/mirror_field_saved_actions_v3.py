"""CPU14, one admitted closed Pi tree export; README_FIELD_SAVED_ACTIONS_V3.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import threading
import time

from dispatch_b01_stack_v2 import SSH, REMOTE
from field_host_budget_v1 import HostStore, encoded
from field_ssh_mirror_v1 import receive, receive_json, send_json, write_all

MODULES = ('field_host_budget_v1', 'field_streamed_mirror_v1', 'field_ssh_mirror_v1', 'field_saved_export_v3')
BOOTSTRAP = '''import os,resource,signal,sys,json,types
os.sched_setaffinity(0,{2,3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
signal.alarm(80)
n=int(sys.stdin.buffer.readline(16));assert 0<n<=262144
raw=sys.stdin.buffer.read(n);assert len(raw)==n
r=json.loads(raw);modules=r.pop('modules')
for name,source in modules.items():
 m=types.ModuleType(name);m.__file__='<admitted:'+name+'>';sys.modules[name]=m
 exec(compile(source,m.__file__,'exec'),m.__dict__)
sys.modules['field_saved_export_v3'].run(r,modules)
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    early=dict(pid=psutil.Process().pid,create_time=psutil.Process().create_time(),affinity=[14])
    early_raw=encoded(early);assert len(early_raw)<=512
    with (args.output.parent/'MIRROR_EARLY_OWNER.json').open('xb') as f:f.write(early_raw)
    raw = args.admission.read_bytes()
    assert len(raw) <= 131072
    a = json.loads(raw)
    now = datetime.now(timezone.utc)
    assert now < datetime.fromisoformat(a['expires_utc']) <= datetime.fromisoformat('2026-10-01T17:42:44+00:00')
    assert 150 <= (datetime.fromisoformat(a['expires_utc'])-now).total_seconds() <= 600
    assert a['pi_readonly_export'] is True and a['capture'] is False
    assert a['host_affinity'] == [14] and a['maximum_host_output_bytes'] == 84300332
    assert a['mirror_maximum_bytes'] == 80106028 and a['target_payload_writes'] is False
    assert args.output.resolve() == Path(a['output']).resolve()
    for row in a['input_pins']:
        p = Path(row['path'])
        assert p.stat().st_size == row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256']
    manifest = json.loads(Path(a['manifest']).read_text())['files']
    files = {k:manifest[k] for k in sorted(manifest)}
    modules = {name:(Path(__file__).parent/(name+'.py')).read_text(encoding='utf-8') for name in MODULES}
    assert {k:hashlib.sha256(v.encode()).hexdigest() for k,v in modules.items()} == a['module_sha256']
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == a['coordinator_sha256']
    owner = dict(pid=psutil.Process().pid, create_time=psutil.Process().create_time(), affinity=[14])
    limits = dict(metadata=(512*1024,256*1024,12),failure=(128*1024,65536,4),closure=(32768,16384,4))
    store = HostStore(args.output, limits).create({'ADMISSION.json':encoded(a), 'REGISTERED_OWNER.json':encoded(owner)})
    command = ['systemd-run','--user','--unit=jp-field-live-export-v3','--description=JustPeachy-closed-live-export-v1','--wait','--pipe','--quiet']
    for prop in ('CPUQuota=200%','TasksMax=64','LimitAS=134217728','LimitSTACK=1048576',
                 'RuntimeMaxSec=90','TimeoutStopSec=10','LimitCORE=0','LimitFSIZE=0','Nice=10'):
        command += ['-p', prop]
    command += ['--setenv=OPENBLAS_NUM_THREADS=1','--setenv=OMP_NUM_THREADS=1',
                '--setenv=CUDA_VISIBLE_DEVICES=', 'taskset','-c','2,3','python3','-u','-B','-c',BOOTSTRAP]
    began = time.monotonic()
    proc = subprocess.Popen(SSH + ['exec '+shlex.join(command)], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    stderr = bytearray()
    overflow = threading.Event()
    def drain_stderr():
        while True:
            block = proc.stderr.read(4096)
            if not block: break
            room = 65536-len(stderr)
            stderr.extend(block[:room])
            if len(block) > room:
                overflow.set()
                proc.kill()
                break
    reader = threading.Thread(target=drain_stderr, name='ssh-stderr', daemon=True)
    reader.start()
    expired = threading.Event()
    def expire():
        if proc.poll() is None:
            expired.set(); proc.kill()
    timer = threading.Timer(110, expire); timer.daemon = True; timer.start()
    remote_owner = None
    result = dict(status='FAILED_PRESERVED')
    try:
        request = encoded(dict(admission=a, files=files, modules=modules))
        assert len(request) <= 262144
        write_all(proc.stdin, str(len(request)).encode()+b'\n'+request); proc.stdin.flush()
        ready = receive_json(proc.stdout, began+105)
        remote_owner = ready['owner']
        assert set(remote_owner) == {'pid','start_ticks','boot_id'} and remote_owner['boot_id'] == a['boot_id']
        assert ready['source'] == REMOTE+'/field-saved-actions-v3'
        store.write('PREFLIGHT.json', encoded(ready))
        send_json(proc.stdin, dict(ack=remote_owner))
        proc.stdin.close()
        def closed():
            assert proc.stdout.read(1) == b'', 'Unexpected trailing stream bytes'
            assert proc.wait(timeout=max(.1, began+105-time.monotonic())) == 0
            reader.join(2)
            assert not reader.is_alive() and not overflow.is_set() and not expired.is_set()
            # Exact process check after natural systemd-run/SSH reaping.
            from dispatch_geometry_v2 import remote
            observation = remote('O='+repr(remote_owner)+'\n'+'''import os,json
from pathlib import Path
os.sched_setaffinity(0,{3})
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
try:t=int(Path('/proc',str(O['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])
except FileNotFoundError:t=None
assert not(boot==O['boot_id'] and t==O['start_ticks'])
me=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=boot)\nprint(json.dumps(dict(owner=O,observed_start_ticks=t,exact_alive=False,utility_owner=me)))''')
            check=subprocess.run(SSH+['test ! -e /proc/'+str(observation['utility_owner']['pid'])],capture_output=True,timeout=10)
            assert check.returncode==0
            observation['utility_pid_absent_after_ssh']=True
            result['remote_closure'] = observation
        data = receive(store, args.output.with_name(args.output.name+'-mirror'), proc.stdout,
            files, deadline=began+105, maximum_bytes=a['mirror_maximum_bytes'],
            verify_process_closed=closed, source_label=ready['source'])
        result.update(data, status='PASS_SSH_CLOSED_TREE_MIRROR_ONLY')
    except Exception as exc:
        import traceback
        result.update(error=str(exc), traceback=traceback.format_exc())
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        timer.cancel(); timer.join(2); reader.join(2)
        for pipe in (proc.stdin,proc.stdout,proc.stderr):
            if not pipe.closed: pipe.close()
        store.write('worker.raw', bytes(stderr))
        result.update(elapsed_seconds=time.monotonic()-began, ssh_returncode=proc.returncode,
                      stderr_overflow=overflow.is_set(), watchdog_expired=expired.is_set(),
                      threads_joined=not reader.is_alive() and not timer.is_alive(), remote_owner=remote_owner)
        store.write('RESULT.json', encoded(result))
        store.write('coordinator-closure.json', encoded(dict(owner=owner, work_complete=True,
            ssh_reaped=True,pipes_closed=True,threads_joined=result['threads_joined'],
            logical_success=result['status']=='PASS_SSH_CLOSED_TREE_MIRROR_ONLY')))
    print(json.dumps({k:result.get(k) for k in ('status','error','files','bytes','data_chunks','elapsed_seconds','ssh_returncode')}))
    return int(result['status'] != 'PASS_SSH_CLOSED_TREE_MIRROR_ONLY')


if __name__ == '__main__':
    raise SystemExit(main())
