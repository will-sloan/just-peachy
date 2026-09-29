"""Isolate exact reference features from waveform drift; README_D1_FEATURE_ISOLATION_V1.md."""
import argparse,os,json,hashlib,time,traceback
from pathlib import Path
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);r=parser.parse_args().root;a=json.loads((r/'ADMISSION.json').read_text(encoding='utf-8'))
    for binding in a['bindings']:assert sha(binding['path'])==binding['sha256']
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',ORT_DISABLE_TELEMETRY='1')
    import psutil
    proc=psutil.Process();proc.cpu_affinity([4,14]);save(r/'MODEL_OWNER.json',dict(pid=proc.pid,create_time=proc.create_time(),affinity=proc.cpu_affinity()))
    start=time.monotonic();out=dict(status='FAILED_PRESERVED',cases=[]);candidate=None
    try:
        import numpy as np
        from d1_waveform_runtime_v1 import WaveformD1
        parent=r.parent/'d1-onnx-waveform-v2';fixtures=r.parent/'d1-onnx-frontend-v1'
        candidate=WaveformD1(a['graph'],a['compression'],a['coefficients'],np.load(parent/'learned_silence.npy'))
        for name in ['tail','full']:
            with np.load(fixtures/(name+'.npz')) as z:
                audio=z['audio'];features=z['reference'][0,:,:len(audio)//160].T.copy()
            with np.load(parent/(name+'-reference.npz')) as z:
                assert np.array_equal(audio,z['audio']);ref=z['probabilities'].copy()
                last=len(json.loads((parent/(name+'-reference.json')).read_text())['chunks'])-1
                state_ref={field:z[str(last)+'_'+label][0].copy() for label,field in [('spkcache','cache'),('spkcache_preds','cache_probs'),('fifo','fifo'),('fifo_preds','fifo_probs')] if str(last)+'_'+label in z}
            runs=[]
            for repetition in range(2):
                candidate.reset();parts=[];begin=time.perf_counter()
                for offset in range(0,len(features),20):
                    candidate._append(features[offset:offset+20]);parts.append(candidate._pump(False))
                parts.append(candidate._pump(True));candidate.state.finish();candidate.closed=True
                got=np.concatenate(parts);assert got.shape==ref.shape
                difference=float(np.max(np.abs(got.astype('float64')-ref.astype('float64'))))
                state_diffs={key:float(np.max(np.abs(value.astype('float64')-getattr(candidate.state,key).astype('float64')))) if value.size else 0.0 for key,value in state_ref.items()}
                np.savez(r/(name+'-'+str(repetition)+'.npz'),probabilities=got,**{k:getattr(candidate.state,k) for k in state_ref})
                row=dict(case=name,repetition=repetition,max_abs=difference,state_max_abs=state_diffs,seconds=time.perf_counter()-begin,trace=list(candidate.trace),within_unchanged_gate=difference<=1e-5 and max(state_diffs.values(),default=0)<=1e-5)
                out['cases'].append(row);runs.append(got)
            assert np.array_equal(*runs)
        candidate.close();candidate=None
        out['status']='FEATURE_ISOLATION_OBSERVATIONS_REVIEW_REQUIRED'
    except Exception as exc:out.update(error=repr(exc),traceback=traceback.format_exc())
    finally:
        if candidate is not None:candidate.close()
    out['seconds']=time.monotonic()-start;save(r/'RESULT.json',out)
    return int(out['status']=='FAILED_PRESERVED')
if __name__=='__main__':raise SystemExit(main())
