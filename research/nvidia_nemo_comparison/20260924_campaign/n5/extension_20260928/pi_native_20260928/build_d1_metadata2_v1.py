"""Native recompile of scheduler capacity only; preserve all original inputs. README_D1_METADATA2_V1.md."""
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
        original=root.parent/'metadata-native-v1/session.cpp'
        parent_result=json.loads((root.parent/'metadata-native-v1/BUILD_RESULT.json').read_text())
        assert sha(original)==parent_result['patch']['after_sha256']
        text=original.read_text()
        assert text.count('= 8 * 1024 * 1024;')==3
        text=text.replace('= 8 * 1024 * 1024;', '= 2 * 1024 * 1024;')
        diagnostic = """static void d1_metadata_measurement(const char* tag, const TensorContainer::Measurement& m) {
    if (!memstats_enabled()) return;
    size_t peak = m.temp_ctx_bytes;
    for (const auto& item : m.per_buft_bytes) if (item.second > peak) peak = item.second;
    fprintf(stderr, "[d1-metadata] tag=%s temp_bytes=%zu max_arena_used_bytes=%zu cap_bytes=2097152\\n", tag, m.temp_ctx_bytes, peak);
}
"""
        marker='static constexpr size_t kSchedGraphSize = 2048;'
        assert text.count(marker)==1 and 'static constexpr double kSchedGraphErrorFrac = 0.95;' in text
        text=text.replace(marker,diagnostic+'\n'+marker)
        for old,new in [
            ('    root_module->define_tensors(this);', '    root_module->define_tensors(this);\n    d1_metadata_measurement("model", model_tensor_container->measure());\n    d1_metadata_measurement("state_template", state_tensor_container->measure());'),
            ('    tc->free_temp_ctx();', '    d1_metadata_measurement("session_state", tc->measure());\n    tc->free_temp_ctx();'),
            ('        const auto measurement = probe->measure();', '        const auto measurement = probe->measure();\n        d1_metadata_measurement("graph_probe", measurement);')]:
            assert text.count(old)==1
            text=text.replace(old,new)
        session=root/'session.cpp';session.write_text(text)
        result['metadata_change']=dict(default_arenas_mib=2,probe_arena_mib=2,old_mib=8,allocator_assertions_retained=True,measurement_logging=True)
        result['patch']=dict(before_sha256=sha(original),after_sha256=sha(session),scheduler_capacity=2048,existing_95_percent_guard_retained=True,D1_only=True,ASR_not_qualified=True)
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
        shutil.copyfile(root.parent/'metadata-native-v1/output/runtime.a',output/'runtime.a')
        run('replace-session',['ar','r','runtime.a','session.cpp.o'])
        run('index-runtime',['ranlib','runtime.a'])
        objects=sorted((dest/'objects').rglob('*.o'))
        if len(objects)!=28: raise RuntimeError('Expected 28 retained ASR objects')
        lru=root.parent/'d1-lru-build-v1'
        assert sha(lru/'output/libnemo_speech_asr.so')=='fa8ecbb66124b62fced485d45dd2ec6018634a35d39dbc143e221b9f7230b622'
        objects=[p for p in objects if str(p.relative_to(dest/'objects'))!='diar/sortformer_model.cpp.o']+[lru/'output/sortformer_model.cpp.o']
        assert len(objects)==28
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
