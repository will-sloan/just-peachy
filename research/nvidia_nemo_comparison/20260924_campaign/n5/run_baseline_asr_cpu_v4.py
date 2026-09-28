"""Single-variable QEMU CPU diagnostic; README_BASELINE_ASR_CPU_V4.md."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
from run_baseline_asr_diagnostic_v3 import require, load, freeze, binding, verify, path, read_events


def cpu_argv(original, cpu):
    require(cpu == 'cortex-a76', 'Only the admitted CPU contrast is allowed')
    require(len(original) == 11 and original[1] == '-L' and original[3] == '-E'
            and original[4].startswith('LD_LIBRARY_PATH=') and '-cpu' not in original,
            'Unexpected original model command')
    return [original[0], '-cpu', cpu, *original[1:]]


def run_linux(admission, output):
    import resource
    from run_native_stream_models_v1 import command
    a = load(admission)
    require(a['scope'] == 'BASELINE_C_API_CPU_CONTRAST_V4' and not output.exists(), 'Scope or output differs')
    require(datetime.now(timezone.utc) < datetime.fromisoformat(a['expires_utc']), 'Expired admission')
    for b in a['code']+[a[k] for k in ('prior_admission', 'prior_linux_inputs', 'prior_model_command', 'prior_binary_record', 'prior_windows_events', 'audio')]+[r['asset'] for r in a['models']]:
        verify(b)
    prior = load(verify(a['prior_linux_inputs']))
    qemu = verify(prior['qemu'])
    for b in prior['members']:
        verify(b)
    binary = verify(load(verify(a['prior_binary_record'])))
    old = load(verify(a['prior_model_command']))
    require(old['returncode'] == 0 and old['cancelled'] is None and not old['remaining_group_members'], 'Prior run not normally closed')
    expected = [str(qemu), '-L', prior['sysroot'], '-E', 'LD_LIBRARY_PATH='+str(path(prior['members'][0]['path']).parent), str(binary)]
    expected += [str(verify(r['asset'])) for r in a['models']]+[str(verify(a['audio']))]
    require(old['argv'] == expected, 'Prior invocation/source binding differs')
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.nice(10)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_FSIZE, (16*1024**2, 16*1024**2))
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    output.mkdir()
    owner = dict(pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))
    freeze(output/'OWNER.json', owner)
    receipts = []; checked = None; error = None
    try:
        receipts.append(command([str(qemu), '-cpu', 'help'], output, 'cpu_help', 10, admission))
        require(receipts[-1]['returncode'] == 0 and 'cortex-a76' in (output/'cpu_help.stdout').read_text(encoding='utf-8'), 'CPU not advertised by pinned QEMU')
        argv = cpu_argv(old['argv'], a['qemu_cpu'])
        freeze(output/'INPUTS.json', dict(admission=binding(admission), reused_binary=binding(binary), qemu=prior['qemu'],
            original_argv=old['argv'], contrast_argv=argv, cpu=list(os.sched_getaffinity(0)), owner=owner,
            model_seconds=600, changed_variable='Explicit QEMU -cpu cortex-a76 only', CM5_tested=False))
        receipts.append(command(argv, output, 'model', 600, admission))
        require(receipts[-1]['returncode'] == 0, 'Model failed')
        checked = read_events(output/'model.stdout', a['frames'])
        reference = read_events(verify(a['prior_windows_events']), a['frames'])
        freeze(output/'REVIEW.json', dict(measurement=checked, reference=reference,
            decoded_input_identical=checked['info']['f32_le_fnv1a64'] == reference['info']['f32_le_fnv1a64'],
            nonempty=checked['complete']['nonempty'], acceptance=False, CM5_tested=False))
    except Exception as exc:
        error = type(exc).__name__+': '+str(exc)
    freeze(output/'RESULT.json', dict(status='DIAGNOSTIC_COMPLETED_NO_ACCEPTANCE' if error is None else 'FAILED_PRESERVED',
        error=error, commands=receipts, owner=owner, nonempty=None if checked is None else checked['complete']['nonempty'],
        acceptance=False, CM5_tested=False, N5_complete=False))
    return int(error is not None)


def run_host(precheck, output):
    sys.path.insert(0, str(HERE.parent/'n4'))
    from metric_process import pin, identity, exact_process
    own = identity(pin()); a = load(precheck); now = datetime.now(timezone.utc)
    local = HERE.parents[4]/'local'
    require(a['scope'] == 'BASELINE_C_API_CPU_CONTRAST_V4' and a['qemu_cpu'] == 'cortex-a76', 'Wrong scope')
    require(not output.exists() and output.resolve().is_relative_to(local/'n5'), 'Fresh N5 output required')
    require(0 <= (now-datetime.fromisoformat(a['admitted_utc'])).total_seconds() < 120, 'Stale admission')
    require(now < datetime.fromisoformat(a['expires_utc']) < datetime(2026,9,28,2,48,19,tzinfo=timezone.utc), 'Cutoff differs')
    require((datetime.fromisoformat(a['expires_utc'])-now).total_seconds() <= 900 and a['allocation_bytes'] == 128*1024**2, 'Budget differs')
    for b in a['code']+[a[k] for k in ('census','prior_admission','prior_linux_inputs','prior_model_command','prior_binary_record','prior_windows_events','audio')]+[r['asset'] for r in a['models']]:
        verify(b)
    require(all(exact_process(o) is None for o in a['closed_prior_owners']), 'Prior owner active')
    for _ in range(50):
        worker = load(local/'supervision/worker.json')
        if worker.get('child_pid') == own['pid'] and worker.get('child_create_time') == own['create_time']:
            break
        time.sleep(.1)
    require(worker.get('child_pid') == own['pid'] and worker.get('child_create_time') == own['create_time'], 'Not exact supervised child')
    require(exact_process({k: worker[k] for k in ('pid','create_time')}) is not None, 'Supervisor absent')
    require(load(local/'supervision/worker_spec.json')['argv'] == __import__('psutil').Process().cmdline(), 'Worker argv differs')
    output.mkdir(); a.update(owner=own, supervisor=worker, precheck=binding(precheck)); freeze(output/'ADMISSION.json', a)
    def linux(p):
        p = Path(p).resolve(); return '/mnt/'+p.drive[0].lower()+'/'+p.as_posix()[3:]
    argv = ['wsl.exe','-d','Ubuntu','--','timeout','--signal=TERM','--kill-after=10s','650s',
        'python3','-B',linux(__file__),'--admission',linux(output/'ADMISSION.json'),'--output',linux(output/'linux')]
    error = None; process = None; wsl_owner = None
    try:
        with (output/'wsl.stdout').open('xb') as out, (output/'wsl.stderr').open('xb') as err:
            process = subprocess.Popen(argv, stdout=out, stderr=err, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            wsl_owner = identity(__import__('psutil').Process(process.pid)); freeze(output/'WSL_OWNER.json', dict(owner=wsl_owner, argv=argv))
            began = time.monotonic()
            while process.poll() is None:
                require(time.monotonic()-began < 680 and datetime.now(timezone.utc) < datetime.fromisoformat(a['expires_utc']), 'Time allocation exceeded')
                require(not (output/'CANCEL').exists(), 'Cancelled')
                require(all(shutil.disk_usage(d+':/').free > g*1024**3 for d,g in [('C',50),('G',75)]), 'Drive reserve breached')
                require(sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) < a['allocation_bytes'], 'Output cap exceeded')
                time.sleep(2)
        require(process.returncode == 0 and load(output/'linux/RESULT.json')['status'] == 'DIAGNOSTIC_COMPLETED_NO_ACCEPTANCE', 'Linux diagnostic failed; preserve evidence')
    except Exception as exc:
        error = type(exc).__name__+': '+str(exc)
    finally:
        if process is not None and process.poll() is None:
            if not (output/'CANCEL').exists():
                (output/'CANCEL').write_text(str(error), encoding='utf-8')
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.terminate(); process.wait(timeout=5); error=str(error)+'; Linux group closure unverified'
    freeze(output/'RESULT.json', dict(status='DIAGNOSTIC_COMPLETED_NO_ACCEPTANCE' if error is None else 'FAILED_PRESERVED',
        error=error, owner=own, wsl_owner=wsl_owner, admission=binding(output/'ADMISSION.json'),
        linux_result=binding(output/'linux/RESULT.json') if (output/'linux/RESULT.json').exists() else None,
        acceptance=False, CM5_tested=False, N5_complete=False))
    return int(error is not None)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--precheck', type=Path)
    g.add_argument('--admission', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    require((os.name == 'nt') == bool(args.precheck), 'Wrong platform/role')
    raise SystemExit(run_host(args.precheck,args.output) if args.precheck else run_linux(args.admission,args.output))
