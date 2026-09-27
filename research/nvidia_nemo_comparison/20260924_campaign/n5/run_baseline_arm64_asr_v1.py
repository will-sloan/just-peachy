"""Pinned wheel C ABI cross-build and emulated baseline ASR; README_BASELINE_ARM64_ASR_V1.md."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import resource
import zipfile

from build_native_stream_smoke_v1 import binding,freeze,wav
from run_native_stream_models_v1 import verify,command
from baseline_arm64_asr_review_v1 import require,review,compare


def run(admission,output):
    require(not output.exists(),'Fresh Linux output required');a=json.loads(admission.read_text(encoding='utf-8-sig'))
    require(a['scope']=='BASELINE_ASR_WINDOWS_ARM64_COMPONENT_PARITY_ONLY','Wrong scope')
    require(datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']),'Expired admission')
    for b in a['code']+[a['audio'],a['wheel'],a['prior_tool_inputs'],a['reference_events']]:verify(b)
    os.nice(10);os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2));resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    prior=json.loads(verify(a['prior_tool_inputs']).read_text());compiler=verify(prior['compiler']);qemu=verify(prior['qemu'])
    arm=compiler.parent.parent;sysroot=arm/'aarch64-none-linux-gnu/libc';output.mkdir()
    source=Path(__file__).with_name('baseline_arm64_asr_v1.cpp');binary=output/'baseline_arm64_asr_v1'
    members=['sherpa_onnx/lib/libsherpa-onnx-c-api.so','sherpa_onnx/lib/libonnxruntime.so','sherpa_onnx/include/sherpa-onnx/c-api/c-api.h']
    expected={r['name']:r for r in a['wheel_members']};extracted=[];commands=[];error=None;parity=None
    try:
        with zipfile.ZipFile(verify(a['wheel'])) as z:
            require(set(expected)==set(members),'Wheel member set differs')
            for name in members:
                data=z.read(name);import hashlib
                require(hashlib.sha256(data).hexdigest()==expected[name]['sha256'] and len(data)==expected[name]['bytes'],'Wheel member changed')
                path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);extracted.append(binding(path))
                if name.endswith('.so'):require(data[:6]==b'\x7fELF\x02\x01' and int.from_bytes(data[18:20],'little')==183,'Expected AArch64 library')
        freeze(output/'INPUTS.json',dict(admission=binding(admission),compiler=binding(compiler),qemu=binding(qemu),
            sysroot=str(sysroot),wheel=binding(verify(a['wheel'])),members=extracted,source=binding(source),
            linux_owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])),
            cpu=list(os.sched_getaffinity(0)),execution='QEMU_AARCH64_EMULATED',CM5_tested=False))
        lib=output/'sherpa_onnx/lib'
        argv=[str(compiler),'--sysroot='+str(sysroot),'-std=c++17','-O2','-march=armv8-a','-Wall','-Wextra','-Werror',
            '-I',str(output/'sherpa_onnx/include'),str(source),'-L',str(lib),'-Wl,-rpath-link,'+str(lib),'-lsherpa-onnx-c-api','-o',str(binary)]
        commands.append(command(argv,output,'compile',120,admission));require(commands[-1]['returncode']==0,'Cross-build failed')
        raw=binary.read_bytes();require(raw[:6]==b'\x7fELF\x02\x01' and int.from_bytes(raw[18:20],'little')==183,'Expected AArch64 executable')
        prefix=[str(qemu),'-L',str(sysroot),'-E','LD_LIBRARY_PATH='+str(lib),str(binary)]
        invalid=dict(empty=b'',not_riff=b'not RIFF',truncated=wav()[:-1],stereo=wav(channels=2),wrong_rate=wav(rate=8000),
            short=wav(frames=1),nonfinite=wav(format_code=3,bits=32,value=float('nan')),too_loud=wav(format_code=3,bits=32,value=1.5))
        for name,data in invalid.items():
            path=output/(name+'.wav');path.write_bytes(data)
            c=command(prefix+['INTENTIONALLY_ABSENT']*4+[str(path)],output,name,15,admission);commands.append(c)
            rows=Path(c['stdout']['path']).read_text().splitlines();require(c['returncode']==1 and len(rows)==1,'Malformed WAV rejection failed')
            r=json.loads(rows[0]);require(r.get('kind')=='failure' and any(k in r['error'] for k in ('WAV','sample','source')),'Did not reject WAV before model')
        model_paths=[str(verify(r['asset'])) for r in a['models']];require([r['component_id'] for r in a['models']]==['encoder','decoder','joiner','tokens'],'Model order differs')
        require(datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']),'Expired before model')
        c=command(prefix+model_paths+[str(verify(a['audio']))],output,'model',1200,admission);commands.append(c)
        require(c['returncode']==0,'Native model invocation failed')
        native=review(Path(c['stdout']['path']),a['frames']);reference=review(verify(a['reference_events']),a['frames'])
        parity=compare(reference,native)
        freeze(output/'COMPONENT_REVIEW.json',dict(native=native,reference=reference,parity=parity))
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    freeze(output/'RESULT.json',dict(status='PASS_EMULATED_BASELINE_ASR_COMPONENT_PARITY_ONLY' if error is None else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),error=error,commands=commands,
        inputs=binding(output/'INPUTS.json') if (output/'INPUTS.json').exists() else None,
        binary=binding(binary) if binary.exists() else None,parity=parity,GUI_validated=False,CM5_tested=False,N5_complete=False))
    return int(error is not None)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--admission',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(run(a.admission,a.output))
