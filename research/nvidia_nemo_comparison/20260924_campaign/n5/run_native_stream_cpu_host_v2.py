"""Supervised Windows owner for bounded ARM64 checks; README_NATIVE_STREAM_CPU_V2.md."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'n4'))
from common import bind, freeze, load, verify
from metric_process import pin, identity, exact_process
from native_stream_review_v1 import require


def linux_path(path):
    p = Path(path).resolve()
    return '/mnt/'+p.drive[0].lower()+'/'+p.as_posix()[3:]


def run(precheck, output):
    own = identity(pin()); local = HERE.parents[4]/'local'
    require(not output.exists() and output.resolve().is_relative_to(local/'n5'), 'Fresh N5 output required')
    a = load(precheck)
    require(a['scope'] == 'EMULATED_NATIVE_ASR_CORTEX_A76_V2', 'Wrong admission')
    now = datetime.now(timezone.utc)
    require(0 <= (now-datetime.fromisoformat(a['admitted_utc'])).total_seconds() < 120, 'Admission stale')
    require(now < datetime.fromisoformat(a['expires_utc']) and (datetime.fromisoformat(a['expires_utc'])-now).total_seconds()<=3900, 'Admission duration differs')
    require(a['qemu_cpu']=='cortex-a76' and a['per_model_seconds']==1800 and a['allocation_bytes']==128*1024**2, 'Resource/CPU scope differs')
    require(datetime.fromisoformat(a['expires_utc']) < datetime(2026, 9, 28, 2, 48, 19, tzinfo=timezone.utc), 'Packaging cutoff exceeded')
    for row in a['code']+[a['audio'], a['binary'], a['build_result'], a['census'], a['prior_admission'], a['baseline_cpu_audit']]: verify(row)
    for row in a['models']: verify(row['asset'])
    for owner in a['closed_prior_owners']: require(exact_process(owner) is None, 'Prior owner is active')
    worker = None
    for _ in range(50):
        worker = load(local/'supervision/worker.json')
        if worker.get('child_pid') == own['pid'] and worker.get('child_create_time') == own['create_time']: break
        time.sleep(.1)
    require(worker.get('child_pid') == own['pid'] and worker.get('child_create_time') == own['create_time'], 'Supervisor identity differs')
    require(exact_process({k:worker[k] for k in ('pid','create_time')}) is not None, 'Supervisor absent')
    require(load(local/'supervision/worker_spec.json')['argv'] == __import__('psutil').Process().cmdline(), 'Worker argv differs')
    output.mkdir(parents=True)
    a.update(owner=own, precheck=bind(precheck), supervisor=worker)
    freeze(output/'ADMISSION.json', a)
    actual = output/'linux'; argv = ['wsl.exe', '-d', 'Ubuntu', '--', 'timeout', '--signal=TERM', '--kill-after=10s', '3750s',
        'python3', '-B', linux_path(HERE/'run_native_stream_cpu_v2.py'), '--admission', linux_path(output/'ADMISSION.json'), '--output', linux_path(actual)]
    error = None; child_owner = None; process = None
    with (output/'stdout.log').open('xb') as out, (output/'stderr.log').open('xb') as err:
        try:
            process = subprocess.Popen(argv, stdout=out, stderr=err, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            child_owner = identity(__import__('psutil').Process(process.pid))
            freeze(output/'STARTED.json', dict(owner=child_owner, argv=argv, admission=bind(output/'ADMISSION.json')))
            began = time.monotonic()
            while process.poll() is None:
                if any(shutil.disk_usage(d+':/').free < gib*1024**3 for d, gib in [('C',50),('G',75)]): error='Disk reserve breached'
                if datetime.now(timezone.utc) >= datetime.fromisoformat(a['expires_utc']): error='Allocation expired'
                if error and not (output/'CANCEL').exists(): (output/'CANCEL').write_text(error,encoding='utf-8')
                require(time.monotonic()-began < 3800, 'Outer WSL timeout did not close')
                time.sleep(2)
            require(process.returncode == 0, 'ARM64 checks failed; preserve Linux receipts')
            result = load(actual/'RESULT.json')
            require(result['status']=='PASS_EMULATED_NATIVE_ASR_COMPONENTS_ONLY', 'ARM64 terminal differs')
        except Exception as exc: error = error or type(exc).__name__+': '+str(exc)
        finally:
            if process is not None and process.poll() is None:
                if not (output/'CANCEL').exists(): (output/'CANCEL').write_text('Host cleanup',encoding='utf-8')
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    # Terminate only the exact Windows launch handle; do not claim
                    # Linux closure when its own finite timeout did not return.
                    process.terminate(); process.wait(timeout=5)
                    error = str(error)+'; Linux lifetime closure unverified'
    freeze(output/'RESULT.json', dict(status='CLOSED_ARM64_COMPONENT_INVOCATION' if error is None else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(), owner=own, child_owner=child_owner, error=error,
        returncode=process.returncode if process is not None else None,
        admission=bind(output/'ADMISSION.json'), stdout=bind(output/'stdout.log'), stderr=bind(output/'stderr.log'),
        linux_result=bind(actual/'RESULT.json') if (actual/'RESULT.json').exists() else None,
        GUI_validated=False, N4_accepted=False, N5_complete=False, CM5_tested=False))
    return 0 if error is None else 1


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--precheck',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); raise SystemExit(run(args.precheck,args.output))
