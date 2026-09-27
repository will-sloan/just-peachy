"""Internal owned C-API diagnostic; README_BASELINE_ASR_DIAGNOSTIC_V3.md."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise ValueError(message)


def binding(path):
    p=Path(path);return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def path(value):
    if os.name!='nt' and len(value)>2 and value[1]==':':return Path('/mnt')/value[0].lower()/value[3:].replace('\\','/')
    return Path(value)


def verify(row):
    p=path(row['path']);actual=binding(p)
    require(all(actual[k]==row[k] for k in ('bytes','sha256')),'Binding changed: '+str(p));return p


def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def freeze(p,value):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def read_events(p,frames):
    data=Path(p).read_bytes();require(0<len(data)<1024**2 and data.endswith(b'\n'),'Incomplete or oversized diagnostic')
    rows=[json.loads(s) for s in data.decode().splitlines()]
    require(len(rows)==4 and [r['kind'] for r in rows]==['diagnostic_input','case_start','case_closed','diagnostic_complete'],'Unexpected diagnostic records')
    info,begin,end,done=rows
    require(info['frames']==frames and 0<info['nonzero']<=frames and 0<info['peak']<=1 and math.isfinite(info['sum_squares']) and info['sum_squares']>0,'Missing input energy')
    require(isinstance(info['f32_le_fnv1a64'],str) and 1<=len(info['f32_le_fnv1a64'])<=16 and all(c in '0123456789abcdef' for c in info['f32_le_fnv1a64']),'Invalid sample fingerprint')
    require(begin==dict(kind='case_start',case='fresh_full_source',frames=frames),'Different case')
    require(end['case']=='fresh_full_source' and end['frames']==end['sent_frames']==frames and end['stream_closed'] is True and end['padding_frames']==10560,'Incomplete stream')
    require(done==dict(kind='diagnostic_complete',recognizer_closed=True,nonempty=bool(end['finals']),acceptance=False,CM5_tested=False),'Incomplete diagnostic closure')
    return dict(info=info,case=end,complete=done)


def verified_build(proof):
    """Verify the retained completed build; a failed admission is not acceptance."""
    for b in proof['source']+[proof[k] for k in ('binary','compiler_configuration','actual_compiler','configure_command','compile_command')]:verify(b)
    configured=re.findall(r'set\(CMAKE_CXX_COMPILER "([^"\n]+)"\)',verify(proof['compiler_configuration']).read_text())
    require(len(configured)==1 and os.path.normcase(str(Path(configured[0]).resolve()))==os.path.normcase(str(verify(proof['actual_compiler']))),'Actual compiler differs')
    configure=load(verify(proof['configure_command']));compile_record=load(verify(proof['compile_command']))
    for record in (configure,compile_record):
        require(record['returncode']==0 and record['cancelled'] is None,'Retained build did not finish normally')
        verify(record['stdout']);verify(record['stderr'])
    require(len(proof['source'])==3 and {Path(b['path']).name for b in proof['source']}=={'diagnostic.cpp','CMakeLists.txt','baseline_arm64_asr_v1.cpp'},'Build source set differs')
    argv=configure['argv'];require(argv.count('-S')==1 and argv.count('-B')==1,'Configure paths ambiguous')
    source_root=Path(argv[argv.index('-S')+1]).resolve();build_root=Path(argv[argv.index('-B')+1]).resolve()
    require(verify(proof['source'][0]).parent==source_root,'Configured source differs')
    require(compile_record['argv']==[argv[0],'--build',str(build_root),'--config','Release','--parallel','1'],'Compile command differs')
    binary=verify(proof['binary']);require(binary==build_root/'Release/baseline_asr_diagnostic_v2.exe','Build output differs')
    raw=binary.read_bytes();offset=int.from_bytes(raw[60:64],'little')
    require(raw[:2]==b'MZ' and raw[offset:offset+6]==b'PE\x00\x00\x64\x86','Not Windows x64 PE')
    return binary


def run(admission,output):
    a=load(admission);require(not output.exists(),'Fresh output required')
    require(a['scope']=='BASELINE_C_API_DIAGNOSTIC_ONLY_V3','Wrong scope')
    require(datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']),'Expired admission')
    for b in a['code']+[a['audio'],a['prior_linux_inputs']]+[r['asset'] for r in a['models']]:verify(b)
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    output.mkdir();commands=[];error=None;checked=None
    if os.name=='nt':
        import psutil
        own=dict(pid=os.getpid(),create_time=psutil.Process().create_time())
        require(psutil.Process().ppid()==a['owner']['pid'] and psutil.Process().cpu_affinity()==[4],'Not owned Windows diagnostic child')
        require(load(output.parent/'REFERENCE_OWNER.json')['owner']==own,'Unregistered Windows diagnostic')
        def command(argv,name,seconds):
            began=time.monotonic();cancelled=None
            with (output/(name+'.stdout')).open('xb') as out,(output/(name+'.stderr')).open('xb') as err:
                p=subprocess.Popen(argv,stdout=out,stderr=err,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
                owner=dict(pid=p.pid,create_time=psutil.Process(p.pid).create_time())
                freeze(output/(name+'_OWNER.json'),dict(owner=owner,argv=argv))
                try:
                    while p.poll() is None:
                        if time.monotonic()-began>seconds:cancelled='timeout'
                        if datetime.now(timezone.utc)>=datetime.fromisoformat(a['expires_utc']):cancelled='allocation_expired'
                        if sum(f.stat().st_size for f in output.rglob('*') if f.is_file())>a['allocation_bytes']:cancelled='output_cap'
                        if any(shutil.disk_usage(d+':/').free<g*1024**3 for d,g in [('C',50),('G',75)]):cancelled='disk_reserve'
                        if cancelled:raise ValueError(cancelled)
                        time.sleep(.25)
                finally:
                    if p.poll() is None:p.terminate();p.wait(timeout=5)
            value=dict(argv=argv,owner=owner,returncode=p.returncode,cancelled=cancelled,elapsed_seconds=time.monotonic()-began,
                stdout=binding(output/(name+'.stdout')),stderr=binding(output/(name+'.stderr')))
            freeze(output/(name+'.json'),value);require(p.returncode==0,'Windows command failed: '+name);return value
    else:
        import resource
        from run_native_stream_models_v1 import command as linux_command
        os.nice(10);os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
        resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2));resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
        own=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))
        def command(argv,name,seconds):return linux_command(argv,output,name,seconds,admission)
    freeze(output/'OWNER.json',own)
    try:
        source=HERE/'baseline_asr_diagnostic_v2/diagnostic.cpp'
        if os.name=='nt':
            for b in a['windows_runtime']:verify(b)
            proof=load(verify(a['prior_windows_build_audit']))['build']
            original=verified_build(proof)
            sherpa=Path(a['windows_sherpa_root']);destination=output/'windows-bin';destination.mkdir()
            binary=destination/original.name;shutil.copyfile(original,binary)
            require(binding(binary)['sha256']==proof['binary']['sha256'],'Copied binary differs')
            for name in ('sherpa-onnx-c-api.dll','onnxruntime.dll'):
                source_dll=sherpa/'lib'/name;destination_dll=destination/name
                shutil.copyfile(source_dll,destination_dll)
                require(binding(source_dll)['sha256']==binding(destination_dll)['sha256'],'Copied DLL differs')
            freeze(output/'WINDOWS_BUILD_INPUTS.json',dict(reused_build=proof,audit=a['prior_windows_build_audit'],runtime=a['windows_runtime']))
            prefix=[str(binary)]
        else:
            prior=load(verify(a['prior_linux_inputs']));compiler=verify(prior['compiler']);qemu=verify(prior['qemu'])
            for b in prior['members']:verify(b)
            lib=path(prior['members'][0]['path']).parent;inc=lib.parent/'include';sysroot=Path(prior['sysroot']);binary=output/'diagnostic'
            commands.append(command([str(compiler),'--sysroot='+str(sysroot),'-std=c++17','-O2','-march=armv8-a','-Wall','-Wextra','-Werror','-I',str(inc),str(source),'-L',str(lib),'-Wl,-rpath-link,'+str(lib),'-lsherpa-onnx-c-api','-o',str(binary)],'compile',120))
            raw=binary.read_bytes();require(raw[:6]==b'\x7fELF\x02\x01' and int.from_bytes(raw[18:20],'little')==183,'Not AArch64')
            prefix=[str(qemu),'-L',str(sysroot),'-E','LD_LIBRARY_PATH='+str(lib),str(binary)]
        freeze(output/'BINARY.json',binding(binary))
        argv=prefix+[str(verify(r['asset'])) for r in a['models']]+[str(verify(a['audio']))]
        commands.append(command(argv,'model',600 if os.name!='nt' else 90))
        require(commands[-1]['returncode']==0,'Diagnostic process failed')
        checked=read_events(output/'model.stdout',a['frames']);freeze(output/'REVIEW.json',checked)
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    freeze(output/'RESULT.json',dict(status='DIAGNOSTIC_COMPLETED_NO_ACCEPTANCE' if error is None else 'DIAGNOSTIC_FAILED_PRESERVED',
        error=error,owner=own,commands=commands,nonempty=None if checked is None else checked['complete']['nonempty'],CM5_tested=False,acceptance=False))
    return int(error is not None)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--admission',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(run(a.admission,a.output))
