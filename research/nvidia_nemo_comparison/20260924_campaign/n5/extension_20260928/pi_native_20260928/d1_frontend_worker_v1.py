"""Pinned frontend reference, not model inference. README_D1_NUMPY_FRONTEND_V1.md."""
import argparse, contextlib, hashlib, json, os, sys, time, traceback, wave
from pathlib import Path

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(p, x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);r=ap.parse_args().root
    a=json.loads((r/'ADMISSION.json').read_text(encoding='utf-8'))
    for b in a['bindings']:assert sha(b['path'])==b['sha256']
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='disabled')
    import psutil
    proc=psutil.Process();proc.cpu_affinity([4,14]);proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    save(r/'MODEL_OWNER.json',dict(pid=proc.pid,create_time=proc.create_time(),affinity=proc.cpu_affinity()))
    start=time.monotonic();result=dict(status='FAILED_PRESERVED',model_inference=False)
    with (r/'frontend.log').open('x',encoding='utf-8',buffering=1) as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            import numpy as np,torch
            torch.set_num_threads(1);torch.set_num_interop_threads(1)
            from nemo.collections.asr.parts.preprocessing.features import FilterbankFeatures
            from d1_numpy_frontend_v1 import Frontend
            coeff=Path(a['coefficients']);cfg=json.loads(Path(a['frontend_config']).read_text())
            assert cfg['parameters']==dict(n_fft=512,hop_length=160,win_length=400,normalize='NA',pad_to=16,frame_splicing=1,log=True,log_zero_guard_type='add',log_zero_guard_value=2**-24,preemph=.97,mag_power=2.0,exact_pad=False)
            reference=FilterbankFeatures(sample_rate=16000,n_window_size=400,n_window_stride=160,n_fft=512,nfilt=128,normalize='NA',dither=0,pad_to=16).eval()
            with np.load(coeff,allow_pickle=False) as c:
                reference.window.copy_(torch.from_numpy(c['window']))
                reference.fb.copy_(torch.from_numpy(c['filterbank']))
            with wave.open(a['source_wav'],'rb') as f:
                assert f.getframerate()==16000 and f.getnchannels()==1 and f.getsampwidth()==2 and f.getnframes()==715127
                source=np.frombuffer(f.readframes(f.getnframes()),'<i2').astype(np.float32)/32768
            impulse=np.zeros(1600,np.float32);impulse[[0,255,256,800,1599]]=[1,-.5,.25,-.75,.125]
            cases=[('empty',source[:0]),('one',source[:1]),('hop_minus',source[:159]),('hop_exact',source[:160]),('hop_plus',source[:161]),('tail',source[:1281]),('full',source),('zero',np.zeros(3201,np.float32)),('impulse',impulse)]
            rows=[];frontend=Frontend(coeff)
            for name,x in cases:
                original=x.tobytes();beg=time.monotonic()
                inp=torch.from_numpy(x.copy()).reshape(1,-1) if x.size else torch.zeros(1,1)
                with torch.inference_mode():ref,length=reference(inp,torch.tensor([len(x)]))
                ref=ref.numpy();length=length.numpy();torch_seconds=time.monotonic()-beg
                arrays=dict(audio=x,reference=ref,length=length);errors=[];timings=[];peaks=[]
                for mode,sizes in [('fixed',(3200,)),('irregular',(1,7,159,160,161,4093)),('repeat',(3200,))]:
                    beg=time.monotonic();valid=frontend.process(x,sizes);got=frontend.padded(valid,len(x));timings.append(time.monotonic()-beg);peaks.append(frontend.maximum_buffer_samples)
                    assert frontend.closed and frontend.total==len(x) and frontend.next_frame==len(x)//160 and frontend.buffer.size==0
                    assert got.shape==ref.shape and np.isfinite(got).all() and int(length[0])==len(x)//160
                    error=float(np.max(np.abs(got.astype(np.float64)-ref.astype(np.float64)))) if got.size else 0
                    errors.append(error);arrays[mode]=got
                    for method in (lambda:frontend.push(np.zeros(1,np.float32)),frontend.finish):
                        try:method()
                        except RuntimeError:pass
                        else:raise AssertionError('Post-finish call accepted')
                assert x.tobytes()==original
                row=dict(case=name,samples=len(x),valid_frames=int(length[0]),shape=list(ref.shape),max_abs=errors,torch_seconds=torch_seconds,candidate_seconds=timings,maximum_buffer_samples=peaks)
                np.savez(r/(name+'.npz'),**arrays);save(r/(name+'.json'),row);rows.append(row)
                assert max(errors)<=a['absolute_tolerance'],'Frontend log-feature gate'
                assert np.array_equal(arrays['fixed'],arrays['repeat'])
            bad_cases=0
            for bad in (np.zeros((1,2),np.float32),np.zeros(1,np.float64),np.array([np.nan],np.float32),np.zeros(32769,np.float32)):
                frontend.reset()
                try:frontend.push(bad)
                except ValueError:bad_cases+=1
                else:raise AssertionError('Invalid input accepted')
            result.update(status='FRONTEND_REFERENCE_CASES_REVIEW_REQUIRED',cases=rows,invalid_cases_rejected=bad_cases,absolute_tolerance=a['absolute_tolerance'],full_diarizer_qualified=False,native_pi_qualified=False)
        except Exception as exc:result.update(error=repr(exc),traceback=traceback.format_exc())
    result['seconds']=time.monotonic()-start;save(r/'RESULT.json',result)
    return int(result['status']!='FRONTEND_REFERENCE_CASES_REVIEW_REQUIRED')

if __name__=='__main__':raise SystemExit(main())
