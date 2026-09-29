"""Saved-input ReDimNet/ORT lifecycle check. See README_B01_E0_REFERENCE_V1.md."""
import os
os.environ['ORT_DISABLE_TELEMETRY'] = '1'
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import hashlib
import json
from pathlib import Path
import resource
import shutil
import time
from datetime import datetime, timezone


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root = Path(__file__).resolve().parent
    admission = json.loads((root/'ADMISSION.json').read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot == admission['boot_id'] and os.getuid() != 0
    assert sorted(os.sched_getaffinity(0)) == [2, 3]
    assert datetime.now(timezone.utc) < datetime.fromisoformat(admission['expires_utc'])
    assert shutil.disk_usage(root).free >= 5*1024**3
    available = next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    assert available >= 850*1024**2
    resource.setrlimit(resource.RLIMIT_AS, (768*1024**2, 768*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for row in admission['files']:
        assert sha(Path(row['path'])) == row['sha256'],row['path']
    cgroup = next(x.split(':', 2)[2] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    quota, period = (Path('/sys/fs/cgroup')/cgroup.lstrip('/')/'cpu.max').read_text().split()
    assert quota != 'max' and int(quota)/int(period) <= 2
    owner = dict(pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]), boot_id=boot)
    (root/'OWNER.json').write_text(json.dumps(owner))
    result = dict(status='FAILED_PRESERVED', owner=owner, cases=[], accuracy_scored=False, enrollment=False)
    try:
        import numpy as np
        import onnxruntime as ort
        import soundfile as sf
        result['ort_version'] = ort.__version__
        options = ort.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        started = time.perf_counter()
        session = ort.InferenceSession(admission['model'], sess_options=options, providers=['CPUExecutionProvider'])
        result['load_seconds'] = time.perf_counter()-started
        assert session.get_providers() == ['CPUExecutionProvider']
        plan=json.loads((root/'QUERY_PLAN.json').read_text())
        assert plan['tolerance_max_abs']==1e-5
        sources={}
        for name in plan['sources']:
            audio,sr=sf.read(name,dtype='float32');assert sr==16000 and audio.ndim==1
            sources[name]=audio
        for index,query in enumerate(plan['queries']):
            audio=sources[query['source']]
            wave=audio[query['first_sample']:query['last_sample']].copy()
            assert 8000<=len(wave)<=32000
            prior=wave.copy();expected=np.asarray(query['expected'],dtype=np.float32)
            assert expected.shape==(192,)
            vectors=[]
            for repeat in range(2):
                began=time.perf_counter();cpu=time.process_time()
                raw=session.run(None,{'waveform':wave[None,:]})[0]
                vector=np.asarray(raw[0],dtype=np.float32)
                assert vector.shape==(192,) and np.isfinite(vector).all()
                norm=float(np.linalg.norm(vector));assert norm>0 and np.isfinite(norm)
                vector=vector/norm
                assert np.array_equal(wave,prior) and abs(float(np.linalg.norm(vector))-1)<1e-5
                difference=float(np.max(np.abs(vector-expected)));assert difference<=1e-5
                vectors.append(vector)
                result['cases'].append(dict(query=index,run_id=query['run_id'],event_id=query['event_id'],repeat=repeat,samples=len(wave),source_first=query['first_sample'],source_last=query['last_sample'],elapsed_seconds=time.perf_counter()-began,cpu_seconds=time.process_time()-cpu,max_abs_to_application=difference,input_sha256=hashlib.sha256(wave.tobytes()).hexdigest()))
            assert float(np.max(np.abs(vectors[0]-vectors[1])))<=1e-5
            np.save(root/f'reference_{index:03d}.npy',np.stack(vectors),allow_pickle=False)
        result['query_count']=len(plan['queries'])
        result['query_plan_sha256']=sha(root/'QUERY_PLAN.json')
        del session
        import gc
        gc.collect()
        result['session_released'] = True
        result['status'] = 'B01_E0_REFERENCE_COLLECTED_REQUIRES_REVIEW'
    except Exception as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
    result['peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    result['finished_utc'] = datetime.now(timezone.utc).isoformat()
    with (root/'RESULT.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k != 'cases'}), flush=True)
    return int(result['status'] == 'FAILED_PRESERVED')


if __name__ == '__main__':
    raise SystemExit(main())
