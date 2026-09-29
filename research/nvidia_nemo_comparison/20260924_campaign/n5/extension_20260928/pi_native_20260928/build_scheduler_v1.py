"""Native recompile of scheduler capacity only; preserve all original inputs. README_SCHEDULER.md."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tarfile
import time
from datetime import datetime, timezone


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    root=Path(__file__).resolve().parent
    admission=json.loads((root/'BUILD_ADMISSION.json').read_text())
    if sorted(os.sched_getaffinity(0)) != [2,3] or os.getuid()==0:
        raise RuntimeError('Wrong CPU/user scope')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot != admission['boot_id'] or datetime.now(timezone.utc)>=datetime.fromisoformat(admission['expires_utc']):
        raise RuntimeError('Wrong boot or expired admission')
    for name,digest in admission['files'].items():
        if sha(root/name)!=digest: raise RuntimeError('Changed bound input: '+name)
    if shutil.disk_usage(root).free < 5*1024**3:
        raise RuntimeError('Target storage floor')
    available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    if available<850*1024**2: raise RuntimeError('Target RAM floor')
    resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=boot,admission_sha256=sha(root/'BUILD_ADMISSION.json'))
    with (root/'BUILD_OWNER.json').open('x') as f: json.dump(owner,f)
    result=dict(status='FAILED_PRESERVED',owner=owner,commands=[],stage_acceptance=False,native_recompile=True)
    began=time.monotonic()
    try:
        manifest=json.loads((root/'bundle.tar.json').read_text())
        if sha(root/'bundle.tar.gz')!=manifest['archive_sha256']: raise RuntimeError('Archive hash')
        rows={x['name']:x for x in manifest['files']}
        dest=root/'inputs';dest.mkdir()
        with tarfile.open(root/'bundle.tar.gz') as archive:
            members=archive.getmembers()
            if len(members)!=len(rows) or {m.name for m in members}!=set(rows): raise RuntimeError('Archive member inventory')
            if sum(m.size for m in members)>96*1024**2: raise RuntimeError('Archive expansion cap')
            for m in members:
                target=dest/m.name
                if not m.isfile() or not target.resolve().is_relative_to(dest.resolve()) or m.size!=rows[m.name]['bytes']:
                    raise RuntimeError('Unsafe or changed member')
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(m) as inp,target.open('xb') as out: shutil.copyfileobj(inp,out)
                if sha(target)!=rows[m.name]['sha256']: raise RuntimeError('Extracted member hash')
        source=dest/'source';session=source/'src/runtime/ggml/session.cpp'
        before=sha(session)
        if before!=manifest['source_session_sha256']: raise RuntimeError('Session before hash')
        old='static constexpr size_t kSchedGraphSize = 65536;'
        text=session.read_text()
        if text.count(old)!=1: raise RuntimeError('Patch context count')
        session.write_text(text.replace(old,'static constexpr size_t kSchedGraphSize = 8192;'))
        result['patch']=dict(before_sha256=before,after_sha256=sha(session),old_capacity=65536,new_capacity=8192,existing_95_percent_guard_retained=True)
        output=root/'output';output.mkdir()
        def run(name,args):
            t=time.monotonic()
            with (root/(name+'.log')).open('x') as log:
                proc=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=300,cwd=output)
            result['commands'].append(dict(name=name,argv=list(map(str,args)),returncode=proc.returncode,elapsed_seconds=time.monotonic()-t))
            if proc.returncode: raise RuntimeError(name+' failed')
        run('compiler-version',['g++','--version'])
        args=['g++','-DGGML_BACKEND_SHARED','-DGGML_SHARED','-DGGML_USE_CPU','-DNEMO_SPEECH_VERSION_STR="0.1.0"']
        args += ['-I'+str(source/p) for p in ['src/runtime/ggml','ggml/include','ggml/src','src/common']]
        args += ['-march=armv8-a','-O3','-DNDEBUG','-std=gnu++17','-fPIC','-fvisibility=hidden','-fvisibility-inlines-hidden','-Wall','-Wextra','-o','session.cpp.o','-c',str(session)]
        run('compile-session',args)
        shutil.copyfile(dest/'prebuilt/runtime.a',output/'runtime.a')
        run('replace-session',['ar','r','runtime.a','session.cpp.o'])
        run('index-runtime',['ranlib','runtime.a'])
        objects=sorted((dest/'objects').rglob('*.o'))
        if len(objects)!=28: raise RuntimeError('Expected 28 retained ASR objects')
        args=['g++','-fPIC','-march=armv8-a','-O3','-DNDEBUG','-Wl,--exclude-libs,libsentencepiece.a','-shared','-Wl,-soname,libnemo_speech_asr.so','-o','libnemo_speech_asr.so']
        args += list(map(str,objects))+['-Wl,-rpath,$ORIGIN:$ORIGIN/../lib',str(dest/'prebuilt/common.a'),'runtime.a',str(dest/'prebuilt/libsentencepiece.a')]
        args += [str(dest/'prebuilt'/x) for x in ['libggml.so.0.12.0','libggml-cpu.so.0.12.0','libggml-base.so.0.12.0']]
        run('link-asr',args)
        run('elf-dynamic',['readelf','-d','libnemo_speech_asr.so'])
        result['library']=dict(bytes=(output/'libnemo_speech_asr.so').stat().st_size,sha256=sha(output/'libnemo_speech_asr.so'))
        result['status']='NATIVE_SCHEDULER_BUILD_COLLECTED_NOT_INFERENCE'
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
    result['elapsed_seconds']=time.monotonic()-began
    result['ended_utc']=datetime.now(timezone.utc).isoformat()
    with (root/'BUILD_RESULT.json').open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)
    return int(result['status']=='FAILED_PRESERVED')


if __name__=='__main__':
    raise SystemExit(main())
