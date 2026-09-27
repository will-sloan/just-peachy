"""Cross-compile and exercise malformed-WAV rejection only; README_NATIVE_STREAM_BUILD_V1.md."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import struct
import subprocess
import time


def binding(path):
    path = Path(path).resolve(strict=True)
    with path.open('rb') as stream: digest = hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(path=str(path),sha256=digest,bytes=path.stat().st_size)


def freeze(path, value):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def command(argv, folder, index, seconds):
    """Fresh process group, finite logs, timeout and retained exact start ticks."""
    stdout=folder/f'{index}.stdout';stderr=folder/f'{index}.stderr'
    start=time.monotonic();process=None;expired=False;owner=None
    with stdout.open('xb') as out, stderr.open('xb') as err:
        process=subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True)
        try:
            raw=Path(f'/proc/{process.pid}/stat').read_text()
            owner=dict(pid=process.pid,start_ticks=int(raw.rsplit(')',1)[1].split()[19]))
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            expired=True
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
    # These fixed compiler and QEMU commands must leave no child in their group.
    members=[]
    for stat in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields=stat.read_text().rsplit(')',1)[1].split()
            if int(fields[2]) == process.pid:members.append(int(stat.parent.name))
        except FileNotFoundError:pass
    receipt=dict(argv=argv,owner=owner,returncode=process.returncode,timed_out=expired,
        elapsed_seconds=time.monotonic()-start,remaining_group_members=members,
        stdout=binding(stdout),stderr=binding(stderr))
    freeze(folder/f'{index}.json',receipt)
    if members or expired:raise RuntimeError('Command failed lifetime closure/timeout; preserve attempt')
    return receipt


def wav(format_code=1,bits=16,channels=1,rate=16000,frames=1281,value=0):
    width=bits//8
    sample=struct.pack('<h',value) if bits==16 else struct.pack('<f',value)
    data=sample*frames*channels
    fmt=struct.pack('<HHIIHH',format_code,channels,rate,rate*channels*width,channels*width,bits)
    body=b'WAVEfmt '+struct.pack('<I',16)+fmt+b'data'+struct.pack('<I',len(data))+data
    return b'RIFF'+struct.pack('<I',len(body))+body


def run(a):
    if a.output.exists():raise ValueError('Fresh private output required')
    if not a.output.is_absolute():raise ValueError('Absolute output required')
    admitted=json.loads(a.admission.read_text())
    if admitted['scope']!='COMPILE_AND_MALFORMED_WAV_ONLY' or admitted['models_loaded'] is not False:
        raise ValueError('Wrong host admission')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(admitted['expires_utc']):raise ValueError('Expired host admission')
    os.nice(10);os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    resource.setrlimit(resource.RLIMIT_FSIZE,(1024**2,1024**2))
    here=Path(__file__).resolve().parent;source=here/'native_stream_smoke_v1.cpp'
    if binding(source)['sha256']!=admitted['source_sha256'] or binding(__file__)['sha256']!=admitted['builder_sha256']:
        raise ValueError('Admitted code differs')
    assets=here.parents[4]/'local/assets/source/NeMo-Speech.cpp-97a15afa5caa9bce5baaa86c1184103877af4101'
    header=assets/'include/nemo_speech/asr.h'
    if binding(header)['sha256']!=admitted['header_sha256']:raise ValueError('Header changed')
    arm=Path('/home/amiri/jp-n5-native-v1/tools/arm-gnu-toolchain-12.3.rel1-x86_64-aarch64-none-linux-gnu')
    sysroot=arm/'aarch64-none-linux-gnu/libc';runtime=Path('/home/amiri/jp-n5-runtime-v1')
    qemu=Path('/home/amiri/jp-n5-loader-v2/qemu/usr/bin/qemu-aarch64')
    manifest=json.loads((runtime/'NATIVE_MANIFEST.json').read_text())
    original_build=json.loads((here/'NATIVE_BUILD_RECEIPT.json').read_text())
    for row in original_build['binaries']:
        name=Path(row['path']).name
        p=runtime/('bin' if name=='nemo-speech' else 'lib')/name
        if binding(p)['sha256']!=row['sha256']:raise ValueError('Runtime differs from published build receipt')
    for row in manifest['files']:
        p=runtime/row['path']
        if 'sha256' in row and binding(p)['sha256']!=row['sha256']:raise ValueError('Runtime package member changed')
        if 'symlink' in row and (not p.is_symlink() or str(p.readlink())!=row['symlink']):raise ValueError('Runtime symlink differs')
    a.output.mkdir(parents=True)
    commands=[];error=None
    try:
        freeze(a.output/'INPUTS.json',dict(admission=binding(a.admission),source=binding(source),builder=binding(__file__),
            header=binding(header),compiler=binding(arm/'bin/aarch64-none-linux-gnu-g++'),qemu=binding(qemu),
            runtime_manifest=binding(runtime/'NATIVE_MANIFEST.json'),original_build=binding(here/'NATIVE_BUILD_RECEIPT.json'),linux_cpu=list(os.sched_getaffinity(0)),
            payload_limit_bytes=32*1024**2,models_loaded=False,CM5_tested=False))
        binary=a.output/'native_stream_smoke_v1'
        argv=[str(arm/'bin/aarch64-none-linux-gnu-g++'),'--sysroot='+str(sysroot),'-std=c++17','-O2','-march=armv8-a',
            '-Wall','-Wextra','-Werror','-I',str(assets/'include'),str(source),'-L',str(runtime/'lib'),
            '-Wl,-rpath-link,'+str(runtime/'lib'),'-lnemo_speech_asr_c','-o',str(binary)]
        commands.append(command(argv,a.output,'compile',120))
        if commands[-1]['returncode']!=0:raise RuntimeError('Cross-compilation failed')
        elf=binary.read_bytes()[:64]
        if elf[:6]!=b'\x7fELF\x02\x01' or int.from_bytes(elf[18:20],'little')!=183:raise ValueError('Expected ELF64 little-endian AArch64')
        invalid=dict(empty=b'',not_riff=b'not a RIFF WAV file',truncated=wav()[:-1],
            stereo=wav(channels=2),wrong_rate=wav(rate=8000),short=wav(frames=1),
            nonfinite=wav(format_code=3,bits=32,value=float('nan')),
            too_loud=wav(format_code=3,bits=32,value=1.5))
        for name,data in invalid.items():
            path=a.output/(name+'.wav');path.write_bytes(data)
            commands.append(command([str(qemu),'-L',str(sysroot),'-E','LD_LIBRARY_PATH='+str(runtime/'lib'),
                str(binary),str(a.output/'INTENTIONALLY_ABSENT_MODEL.gguf'),str(path)],a.output,name,15))
            r=commands[-1];lines=Path(r['stdout']['path']).read_text().splitlines()
            if r['returncode']!=1 or len(lines)!=1:raise ValueError('Malformed input was not a clean bounded rejection')
            event=json.loads(lines[0])
            if event.get('kind')!='failure' or event.get('status')!='FAILED_PRESERVED':
                raise ValueError('Unexpected malformed-input terminal')
            if 'WAV' not in event.get('error','') and 'sample' not in event.get('error','') and 'source' not in event.get('error',''):
                raise ValueError('Input was not rejected before model creation')
        if sum(p.stat().st_size for p in a.output.iterdir() if p.is_file())>32*1024**2:raise ValueError('Total build output cap exceeded')
    except BaseException as exc:error=type(exc).__name__+': '+str(exc)
    receipt=dict(status='PASS_ARM64_BUILD_AND_INVALID_WAV_ONLY' if error is None else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),inputs=binding(a.output/'INPUTS.json'),commands=commands,error=error,
        binary=binding(a.output/'native_stream_smoke_v1') if (a.output/'native_stream_smoke_v1').exists() else None,
        malformed_cases_passed=len(commands)-1 if error is None else None,
        model_inference=False,ARM64_FUNCTIONAL_SMOKE=False,CM5_tested=False,N5_complete=False)
    freeze(a.output/'RESULT.json',receipt);print(json.dumps(dict(status=receipt['status'],error=error)))
    if error:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--admission',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())
