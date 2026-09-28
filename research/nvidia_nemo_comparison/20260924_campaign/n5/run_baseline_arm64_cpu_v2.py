"""Full baseline protocol with explicit emulated CPU; README_BASELINE_ARM64_CPU_V2.md."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
from run_baseline_asr_diagnostic_v3 import require, load, freeze, binding, verify, path
from run_baseline_asr_cpu_v5 import cpu_argv, check_cpu_help


def run_linux(admission, output):
    import resource
    from run_native_stream_models_v1 import command
    from baseline_arm64_asr_review_v1 import review, compare
    a = load(admission)
    require(a['scope'] == 'BASELINE_ARM64_CORTEX_A76_FULL_PROTOCOL_V2' and not output.exists(), 'Scope or output differs')
    require(datetime.now(timezone.utc) < datetime.fromisoformat(a['expires_utc']), 'Expired admission')
    for b in a['code']+[a[k] for k in ('prior_admission','prior_linux_inputs','prior_model_command','prior_binary_record','prior_windows_events','audio')]+[r['asset'] for r in a['models']]:
        verify(b)
    prior = load(verify(a['prior_linux_inputs']));qemu=verify(prior['qemu'])
    for b in prior['members']:
        verify(b)
    prior_result = load(verify(a['prior_binary_record']))
    binary = verify(prior_result['binary'])
    require(prior_result['status']=='FAILED_PRESERVED', 'Expected retained original failed protocol')
    original = load(verify(a['prior_model_command']))
    require(original['cancelled'] is None and not original['remaining_group_members'], 'Original process not closed')
    expected=[str(qemu),'-L',prior['sysroot'],'-E','LD_LIBRARY_PATH='+str(path(prior['members'][0]['path']).parent),str(binary)]
    expected += [str(verify(r['asset'])) for r in a['models']]+[str(verify(a['audio']))]
    require(original['argv']==expected, 'Original invocation/source differs')
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[k]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    os.nice(10);os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2));resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    output.mkdir();owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))
    freeze(output/'OWNER.json',owner)
    commands=[];error=None;parity=None
    try:
        c=command([str(qemu),'-cpu','help'],output,'cpu_help',10,admission);commands.append(c)
        check_cpu_help(c,(output/'cpu_help.stdout').read_text(encoding='utf-8'),(output/'cpu_help.stderr').read_text(encoding='utf-8'))
        argv=cpu_argv(original['argv'],a['qemu_cpu']);prefix=argv[:-5]
        freeze(output/'INPUTS.json',dict(admission=binding(admission),reused_binary=binding(binary),qemu=prior['qemu'],
            original_argv=original['argv'],contrast_argv=argv,cpu=list(os.sched_getaffinity(0)),owner=owner,
            model_seconds=1200,CM5_tested=False))
        for name in ('empty','not_riff','truncated','stereo','wrong_rate','short','nonfinite','too_loud'):
            previous=next(x for x in prior_result['commands'] if Path(x['stdout']['path']).name==name+'.stdout')
            bad=verify(next(x['asset'] for x in a['malformed_inputs'] if x['name']==name))
            require(bad==path(previous['argv'][-1]),'Retained invalid-input fixture path differs')
            c=command(prefix+['INTENTIONALLY_ABSENT']*4+[str(bad)],output,name,15,admission);commands.append(c)
            rows=(output/(name+'.stdout')).read_text(encoding='utf-8').splitlines()
            require(c['returncode']==1 and len(rows)==1,'Invalid-input rejection differs')
            row=__import__('json').loads(rows[0]);require(row.get('kind')=='failure' and any(x in row['error'] for x in ('WAV','sample','source')),'Did not reject before model loading')
        c=command(argv,output,'model',1200,admission);commands.append(c);require(c['returncode']==0,'Full model protocol failed')
        native=review(output/'model.stdout',a['frames']);reference=review(verify(a['prior_windows_events']),a['frames'])
        parity=compare(reference,native)
        freeze(output/'COMPONENT_REVIEW.json',dict(native=native,reference=reference,parity=parity))
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc)
    freeze(output/'RESULT.json',dict(status='PASS_EMULATED_BASELINE_ASR_COMPONENT_PARITY_ONLY' if error is None else 'FAILED_PRESERVED',
        error=error,commands=commands,owner=owner,parity=parity,GUI_validated=False,CM5_tested=False,N5_complete=False))
    return int(error is not None)

def run_host(precheck, output):
    sys.path.insert(0, str(HERE.parent/'n4'))
    from metric_process import pin, identity, exact_process
    own = identity(pin()); a = load(precheck); now = datetime.now(timezone.utc)
    local = HERE.parents[4]/'local'
    require(a['scope'] == 'BASELINE_ARM64_CORTEX_A76_FULL_PROTOCOL_V2' and a['qemu_cpu'] == 'cortex-a76', 'Wrong scope')
    require(not output.exists() and output.resolve().is_relative_to(local/'n5'), 'Fresh N5 output required')
    require(0 <= (now-datetime.fromisoformat(a['admitted_utc'])).total_seconds() < 120, 'Stale admission')
    require(now < datetime.fromisoformat(a['expires_utc']) < datetime(2026,9,28,2,48,19,tzinfo=timezone.utc), 'Cutoff differs')
    require((datetime.fromisoformat(a['expires_utc'])-now).total_seconds() <= 1800 and a['allocation_bytes'] == 128*1024**2, 'Budget differs')
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
    argv = ['wsl.exe','-d','Ubuntu','--','timeout','--signal=TERM','--kill-after=10s','1450s',
        'python3','-B',linux(__file__),'--admission',linux(output/'ADMISSION.json'),'--output',linux(output/'linux')]
    error = None; process = None; wsl_owner = None
    try:
        with (output/'wsl.stdout').open('xb') as out, (output/'wsl.stderr').open('xb') as err:
            process = subprocess.Popen(argv, stdout=out, stderr=err, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            wsl_owner = identity(__import__('psutil').Process(process.pid)); freeze(output/'WSL_OWNER.json', dict(owner=wsl_owner, argv=argv))
            began = time.monotonic()
            while process.poll() is None:
                require(time.monotonic()-began < 1470 and datetime.now(timezone.utc) < datetime.fromisoformat(a['expires_utc']), 'Time allocation exceeded')
                require(not (output/'CANCEL').exists(), 'Cancelled')
                require(all(shutil.disk_usage(d+':/').free > g*1024**3 for d,g in [('C',50),('G',75)]), 'Drive reserve breached')
                require(sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) < a['allocation_bytes'], 'Output cap exceeded')
                time.sleep(2)
        require(process.returncode == 0 and load(output/'linux/RESULT.json')['status'] == 'PASS_EMULATED_BASELINE_ASR_COMPONENT_PARITY_ONLY', 'Linux diagnostic failed; preserve evidence')
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
    freeze(output/'RESULT.json', dict(status='PASS_EMULATED_BASELINE_ASR_COMPONENT_PARITY_ONLY' if error is None else 'FAILED_PRESERVED',
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
