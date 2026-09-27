"""Bounded Linux/QEMU model checks only; README_NATIVE_STREAM_MODELS_V1.md."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PureWindowsPath
import resource
import shutil
import signal
import subprocess
import time

from build_native_stream_smoke_v1 import binding, freeze
from native_stream_review_v1 import review, require


def linux_path(value):
    if len(value) > 2 and value[1:3] in (':\\', ':/'):
        p = PureWindowsPath(value)
        return Path('/mnt')/p.drive[0].lower()/Path(*p.parts[1:])
    return Path(value)


def verify(row):
    actual = binding(linux_path(row['path']))
    require(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'], 'Binding changed')
    return Path(actual['path'])


def command(argv, folder, name, seconds, admission):
    stdout = folder/(name+'.stdout'); stderr = folder/(name+'.stderr')
    began = time.monotonic(); cancelled = None; owner = None
    with stdout.open('xb') as out, stderr.open('xb') as err:
        process = subprocess.Popen(argv, stdout=out, stderr=err, start_new_session=True)
        try:
            stat = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()
            owner = dict(pid=process.pid, start_ticks=int(stat[19]))
            while process.poll() is None:
                if time.monotonic()-began > seconds: cancelled = 'model_timeout'
                elif (admission.parent/'CANCEL').exists(): cancelled = 'host_cancelled'
                elif any(shutil.disk_usage('/mnt/'+drive).free < gib*1024**3 for drive, gib in [('c', 50), ('g', 75)]): cancelled = 'disk_reserve'
                elif sum(p.stat().st_size for p in folder.iterdir() if p.is_file()) > 128*1024**2: cancelled = 'allocation_cap'
                if cancelled: break
                time.sleep(1)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
    members = []
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            stat = path.read_text().rsplit(')', 1)[1].split()
            if int(stat[2]) == process.pid: members.append(int(path.parent.name))
        except FileNotFoundError: pass
    receipt = dict(argv=argv, owner=owner, returncode=process.returncode,
                   timed_out=cancelled == 'model_timeout', cancelled=cancelled,
                   elapsed_seconds=time.monotonic()-began, remaining_group_members=members,
                   stdout=binding(stdout), stderr=binding(stderr))
    freeze(folder/(name+'.json'), receipt)
    require(not members and cancelled is None, 'Command cancelled or process group not empty')
    return receipt


def run(admission, output):
    require(not output.exists(), 'Fresh output required')
    a = json.loads(admission.read_text(encoding='utf-8-sig'))
    require(a['scope'] == 'EMULATED_NATIVE_ASR_COMPONENT_ONLY', 'Wrong scope')
    require(datetime.now(timezone.utc) < datetime.fromisoformat(a['expires_utc']), 'Expired admission')
    require(a['per_model_seconds'] == 1800 and a['allocation_bytes'] == 128*1024**2, 'Limits differ')
    for row in a['code']: verify(row)
    os.nice(10); os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    resource.setrlimit(resource.RLIMIT_FSIZE, (16*1024**2, 16*1024**2))
    # A screening ceiling, never a claim of 2-GB target fit. QEMU host VA is distinct.
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    prior = json.loads(verify(a['build_result']).read_text())
    require(prior['status'] == 'PASS_ARM64_BUILD_AND_INVALID_WAV_ONLY', 'Unqualified harness')
    binary = verify(a['binary']); require(binding(binary)['sha256'] == prior['binary']['sha256'], 'Wrong binary')
    inputs = json.loads(verify(prior['inputs']).read_text())
    qemu = verify(inputs['qemu']); verify(inputs['runtime_manifest']); verify(inputs['original_build'])
    runtime = Path(inputs['runtime_manifest']['path']).parent
    manifest = json.loads((runtime/'NATIVE_MANIFEST.json').read_text())
    for row in manifest['files']:
        p = runtime/row['path']
        if 'sha256' in row: require(binding(p)['sha256'] == row['sha256'], 'Runtime changed')
        if 'symlink' in row: require(p.is_symlink() and str(p.readlink()) == row['symlink'], 'Runtime symlink changed')
    sysroot = Path('/home/amiri/jp-n5-native-v1/tools/arm-gnu-toolchain-12.3.rel1-x86_64-aarch64-none-linux-gnu/aarch64-none-linux-gnu/libc')
    audio = verify(a['audio']); models = [(row['variant'], verify(row['asset'])) for row in a['models']]
    require([name for name, _ in models] == ['A2', 'A3'], 'Wrong model order')
    output.mkdir(parents=True)
    freeze(output/'INPUTS.json', dict(admission=binding(admission), owner_pid=os.getpid(),
        owner_start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
        linux_cpu=list(os.sched_getaffinity(0)), binary=binding(binary), qemu=binding(qemu),
        audio=binding(audio), runtime_manifest=binding(runtime/'NATIVE_MANIFEST.json'),
        models=[dict(variant=name, asset=binding(path)) for name, path in models],
        per_model_seconds=1800, maximum_address_space_bytes=8*1024**3,
        execution='QEMU_AARCH64_EMULATED', GPU=False, CM5_tested=False))
    results = []
    for name, model in models:
        error = None; receipt = None; checked = None
        try:
            require(datetime.now(timezone.utc) < datetime.fromisoformat(a['expires_utc']), 'Expired before model')
            require(not (admission.parent/'CANCEL').exists(), 'Host cancelled allocation')
            receipt = command([str(qemu), '-L', str(sysroot), '-E', 'LD_LIBRARY_PATH='+str(runtime/'lib'),
                               str(binary), str(model), str(audio)], output, name, 1800, admission)
            require(receipt['returncode'] == 0, 'Native command failed')
            checked = review(Path(receipt['stdout']['path']), a['frames'])
        except Exception as exc:
            error = type(exc).__name__+': '+str(exc)
            if (output/(name+'.json')).exists(): receipt = json.loads((output/(name+'.json')).read_text())
        results.append(dict(variant=name, command=receipt, review=checked, error=error))
        freeze(output/(name+'_RESULT.json'), results[-1])
        # Timeouts and process closure failures end the allocation; ordinary model
        # errors preserve their row and allow the next independently reset model.
        if receipt is None or receipt['cancelled'] or receipt['remaining_group_members']: break
    passed = len(results) == 2 and all(row['error'] is None for row in results)
    freeze(output/'RESULT.json', dict(status='PASS_EMULATED_NATIVE_ASR_COMPONENTS_ONLY' if passed else 'FAILED_OR_PARTIAL_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(), inputs=binding(output/'INPUTS.json'), results=results,
        required_models=2, attempted_models=len(results), passed_models=sum(row['error'] is None for row in results),
        unattempted_models=2-len(results), GUI_validated=False, CM5_tested=False, N4_accepted=False, N5_complete=False))
    print(json.dumps(dict(passed=passed, attempted=len(results))))
    return 0 if passed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.admission, args.output))
