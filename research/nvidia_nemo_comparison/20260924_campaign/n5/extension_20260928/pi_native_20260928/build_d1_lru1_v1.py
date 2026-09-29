"""Native D1 executable-graph LRU bound. See README_D1_LRU1_V1.md."""
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
        parent=root.parent/'scheduler-native-v1'
        manifest=json.loads((parent/'bundle.tar.json').read_text())
        dest=parent/'inputs';source=dest/'source'
        prior=json.loads((parent/'BUILD_RESULT.json').read_text())
        for row in manifest['files']:
            item=dest/row['name']
            expected=(prior['patch']['after_sha256'] if row['name']=='source/src/runtime/ggml/session.cpp' else row['sha256'])
            if sha(item)!=expected: raise RuntimeError('Changed retained build input: '+row['name'])
        original=root.parent/'d1-lru-build-v1/sortformer_model.cpp'
        assert sha(original)==json.loads((root.parent/'d1-lru-build-v1/BUILD_RESULT.json').read_text())['patch']['after_sha256']
        text=original.read_text();old='session_->set_run_cache_capacity(8);'
        assert text.count(old)==1
        patched=root/'sortformer_model.cpp'
        patched.write_text(text.replace(old,'session_->set_run_cache_capacity(1);'))
        result['patch']=dict(before_sha256=sha(original),after_sha256=sha(patched),old_graph_cache_capacity=8,new_graph_cache_capacity=1,speaker_history_unchanged=True,weights_unchanged=True,geometry_unchanged=True,D1_only=True,ASR_not_qualified=True)
        metadata=root.parent/'d1-metadata2-build-v2/output'
        assert sha(metadata/'libnemo_speech_asr.so')=='1639518a4de05caa1cf40feb3c9e4e2672cfe82fde87f79f707b115421cdb020'
        output=root/'output';output.mkdir()
        def run(name,args):
            t=time.monotonic()
            with (root/(name+'.log')).open('x') as log:
                proc=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=300,cwd=output)
            result['commands'].append(dict(name=name,argv=list(map(str,args)),returncode=proc.returncode,elapsed_seconds=time.monotonic()-t))
            if proc.returncode: raise RuntimeError(name+' failed')
        run('compiler-version',['g++','--version'])
        args=['g++','-DGGML_BACKEND_SHARED','-DGGML_SHARED','-DGGML_USE_CPU','-DNEMO_SPEECH_VERSION_STR="0.1.0"']
        includes=['src/asr','src/asr/features','src/asr/encoder','src/asr/decoders','src/asr/vad','src/asr/diar','src/asr/postproc','src/asr/pnc','src/runtime/ggml','ggml/include','ggml/src','src/common']
        args += ['-I'+str(source/p) for p in includes]
        args += ['-march=armv8-a','-O3','-DNDEBUG','-std=gnu++17','-fPIC','-Wall','-Wextra','-o','sortformer_model.cpp.o','-c',str(patched)]
        run('compile-sortformer',args)
        objects=sorted((dest/'objects').rglob('*.o'))
        assert len(objects)==28
        replaced=[p for p in objects if str(p.relative_to(dest/'objects'))=='diar/sortformer_model.cpp.o']
        assert len(replaced)==1
        objects=[p for p in objects if p!=replaced[0]]+[output/'sortformer_model.cpp.o']
        args=['g++','-fPIC','-march=armv8-a','-O3','-DNDEBUG','-Wl,--exclude-libs,libsentencepiece.a','-shared','-Wl,-soname,libnemo_speech_asr.so','-o','libnemo_speech_asr.so']
        args += list(map(str,objects))+['-Wl,-rpath,$ORIGIN:$ORIGIN/../lib',str(dest/'prebuilt/common.a'),str(metadata/'runtime.a'),str(dest/'prebuilt/libsentencepiece.a')]
        args += [str(dest/'prebuilt'/x) for x in ['libggml.so.0.12.0','libggml-cpu.so.0.12.0','libggml-base.so.0.12.0']]
        run('link-asr',args)
        run('elf-dynamic',['readelf','-d','libnemo_speech_asr.so'])
        result['library']=dict(bytes=(output/'libnemo_speech_asr.so').stat().st_size,sha256=sha(output/'libnemo_speech_asr.so'))
        result['status']='NATIVE_D1_LRU_BUILD_COLLECTED_NOT_INFERENCE'
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
    result['elapsed_seconds']=time.monotonic()-began
    result['ended_utc']=datetime.now(timezone.utc).isoformat()
    with (root/'BUILD_RESULT.json').open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)
    return int(result['status']=='FAILED_PRESERVED')


if __name__=='__main__':
    raise SystemExit(main())
