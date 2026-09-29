"""Native ggml CPU candidate using actual CM5 ISA. See README_A76_V2.md."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import time
from datetime import datetime, timezone

SOURCES=['ggml-cpu.c','ggml-cpu.cpp','repack.cpp','hbm.cpp','quants.c','traits.cpp','amx/amx.cpp','amx/mmq.cpp','binary-ops.cpp','unary-ops.cpp','vec.cpp','ops.cpp','arch/arm/quants.c','arch/arm/repack.cpp']


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    root=Path(__file__).resolve().parent
    a=json.loads((root/'BUILD_ADMISSION.json').read_text())
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot!=a['boot_id'] or sorted(os.sched_getaffinity(0))!=[2,3] or os.getuid()==0:raise RuntimeError('Target/user/affinity changed')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(a['expires_utc']):raise RuntimeError('Expired admission')
    features=Path('/proc/cpuinfo').read_text()
    if not all(x in features for x in ['asimddp','asimdhp','fphp']):raise RuntimeError('Required observed target features absent')
    for n,h in a['files'].items():
        if sha(root/n)!=h:raise RuntimeError('Bound input changed')
    available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    if available<850*1024**2 or shutil.disk_usage(root).free<5*1024**3:raise RuntimeError('Resource floor')
    resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=boot,admission_sha256=sha(root/'BUILD_ADMISSION.json'))
    with (root/'BUILD_OWNER.json').open('x') as f:json.dump(owner,f)
    result=dict(status='FAILED_PRESERVED',owner=owner,commands=[],stage_accepted=False,actual_inference=False)
    started=time.monotonic()
    try:
        parent=root.parent/'scheduler-native-v1';source=parent/'inputs/source'
        if sha(parent/'bundle.tar.json')!=a['source_manifest_sha256']:raise RuntimeError('Source manifest binding')
        manifest=json.loads((parent/'bundle.tar.json').read_text())
        rows=[x for x in manifest['files'] if x['name'].startswith('source/ggml/')]
        for row in rows:
            if sha(parent/'inputs'/row['name'])!=row['sha256']:raise RuntimeError('ggml source changed')
        base=parent/'inputs/prebuilt/libggml-base.so.0.12.0'
        if sha(base)!='aab12d9b5aac8e4a23c54f9fc1c24cd95d20c62ad8f7db44e918170ea28bf48b':raise RuntimeError('Base runtime changed')
        output=root/'output';output.mkdir()
        def run(name,args):
            begin=time.monotonic()
            with (root/(name+'.log')).open('x') as log:
                done=subprocess.run(args,cwd=output,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            result['commands'].append(dict(name=name,argv=list(map(str,args)),returncode=done.returncode,elapsed_seconds=time.monotonic()-begin))
            if done.returncode:raise RuntimeError(name+' failed')
        run('compiler-version',['g++','--version'])
        common=['-DGGML_BACKEND_BUILD','-DGGML_BACKEND_SHARED','-DGGML_SCHED_MAX_COPIES=4','-DGGML_SHARED','-DGGML_USE_CPU_REPACK','-DNEMO_SPEECH_VERSION_STR="0.1.0"','-D_GNU_SOURCE','-D_XOPEN_SOURCE=600','-Dggml_cpu_EXPORTS']
        common+=['-I'+str(source/x) for x in ['ggml','ggml/src','ggml/src/ggml-cpu','ggml/include']]
        common+=['-mcpu=cortex-a76+nofp16','-O3','-DNDEBUG','-fPIC','-Wall','-Wextra','-Wno-unused-function']
        objects=[]
        for i,name in enumerate(SOURCES):
            obj=str(i)+'.o';objects.append(obj)
            run('compile-'+str(i),(['gcc','-std=gnu11'] if name.endswith('.c') else ['g++','-std=gnu++17'])+common+['-o',obj,'-c',str(source/'ggml/src/ggml-cpu'/name)])
        run('link',['g++','-fPIC','-mcpu=cortex-a76+nofp16','-O3','-DNDEBUG','-shared','-Wl,-soname,libggml-cpu.so.0','-o','libggml-cpu.so.0.12.0']+objects+['-Wl,-rpath,$ORIGIN:$ORIGIN/../lib',str(base)])
        run('dynamic',['readelf','-d','libggml-cpu.so.0.12.0'])
        # Count actual emitted instructions; compile flags alone are not evidence.
        dis=subprocess.run(['objdump','-d',str(output/'libggml-cpu.so.0.12.0')],capture_output=True,text=True,check=True,timeout=30).stdout
        counts={op:sum(('\t'+op+' ') in line or ('\t'+op+'\t') in line for line in dis.splitlines()) for op in ['sdot','udot']}
        result['emitted_instruction_counts']=counts
        if sum(counts.values())==0:raise RuntimeError('No dot-product instructions found')
        result.update(status='NATIVE_A76_CPU_BUILD_COLLECTED_NOT_INFERENCE',library_sha256=sha(output/'libggml-cpu.so.0.12.0'),library_bytes=(output/'libggml-cpu.so.0.12.0').stat().st_size,verified_source_files=len(rows))
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
    result['elapsed_seconds']=time.monotonic()-started;result['ended_utc']=datetime.now(timezone.utc).isoformat()
    with (root/'BUILD_RESULT.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='commands'}),flush=True)
    return int(result['status']=='FAILED_PRESERVED')


if __name__=='__main__':raise SystemExit(main())
