"""Pinned state arithmetic comparison. See README_D1_NUMPY_STATE_V1.md."""
import argparse,contextlib,hashlib,json,os,time,traceback
from pathlib import Path

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(p,x):
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
    start=time.monotonic();result=dict(status='FAILED_PRESERVED',model_inference=False,cases=[])
    with (r/'state.log').open('x',encoding='utf-8',buffering=1) as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            import numpy as np,torch
            torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(20260929)
            from nemo.collections.asr.modules.sortformer_modules import SortformerModules
            from d1_numpy_state_v1 import State,AmbiguousSelection
            rng=np.random.default_rng(20260929);sil=np.linspace(-.1,.1,512,dtype=np.float32)
            fields=[('cache','spkcache'),('cache_probs','spkcache_preds'),('fifo','fifo'),('fifo_probs','fifo_preds')]
            scenarios=[('delayed',0,188,[(264,0,1),(264,1,1),(29,1,0),(0,0,0)]),('fifo',80,40,[(52,0,1),(52,0,1),(52,0,1),(200,0,1),(1,0,0)]),('quiet',0,188,[(264,0,1),(264,1,1),(11,1,0)]),('overlap',0,188,[(264,0,1),(264,1,1),(17,1,0)])]
            fixture_names=[]
            for name,capacity,refresh,steps in scenarios:
                model=SortformerModules(num_spks=8,fc_d_model=512,tf_d_model=192,spkcache_len=264,fifo_len=capacity,chunk_len=264,spkcache_update_period=refresh,spkcache_sil_frames_per_spk=1,use_learnable_sil_emb=True).eval()
                with torch.no_grad():model.learnable_sil_emb.copy_(torch.from_numpy(sil))
                reference=model.init_streaming_state(batch_size=1,async_streaming=False,device='cpu');candidate=State(sil,capacity,refresh)
                for step,(count,lc,rc) in enumerate(steps):
                    chunk=rng.normal(0,.1,(count+lc+rc,512)).astype(np.float32)
                    n=len(candidate.cache)+len(candidate.fifo)+len(chunk)
                    preds=rng.uniform(.01,.04,(n,8)).astype(np.float32)
                    if name=='quiet':preds[:]=0
                    elif name=='overlap':preds[:,:3]=rng.uniform(.55,.98,(n,3)).astype(np.float32)
                    else:
                        speakers=rng.integers(0,8,n);preds[np.arange(n),speakers]=rng.uniform(.55,.999,n).astype(np.float32)
                    original=(chunk.tobytes(),preds.tobytes());offset=candidate.offset
                    with torch.inference_mode():reference,ref_chunk=model.streaming_update(reference,torch.from_numpy(chunk.copy())[None],torch.from_numpy(preds.copy())[None],lc,rc)
                    got=candidate.update(chunk,preds,offset=offset,left=lc,right=rc)
                    arrays=dict(chunk=chunk,predictions=preds,silence=sil,parameters=np.array([capacity,refresh,offset,lc,rc],np.int64),reference_chunk=ref_chunk.numpy()[0],candidate_chunk=got)
                    diffs=[]
                    for field,ref_field in fields:
                        raw=getattr(reference,ref_field)
                        if raw is None:
                            assert ref_field=='spkcache_preds' and reference.spkcache.shape[1]==0
                            ref=np.empty((0,8),np.float32)
                        else:ref=raw.numpy()[0]
                        value=getattr(candidate,field)
                        arrays['reference_'+field]=ref;arrays['candidate_'+field]=value
                        assert ref.shape==value.shape
                        diffs.append(float(np.max(np.abs(ref.astype(np.float64)-value))) if ref.size else 0.)
                    assert bool(reference.spkcache_compressed)==candidate.compressed
                    assert (chunk.tobytes(),preds.tobytes())==original
                    filename=name+'-'+str(step)+'.npz';np.savez(r/filename,**arrays);fixture_names.append(filename)
                    row=dict(case=name,step=step,offset=offset,count=count,cache_frames=len(candidate.cache),fifo_frames=len(candidate.fifo),compressed=candidate.compressed,max_abs=diffs)
                    save(r/(name+'-'+str(step)+'.json'),row);result['cases'].append(row)
                    assert max(diffs)<=a['absolute_tolerance'] and np.array_equal(got,arrays['reference_chunk'])
                assert candidate.finish()==sum(x[0] for x in steps)
                try:candidate.finish()
                except RuntimeError:pass
                else:raise AssertionError('Duplicate finish accepted')
                candidate.reset()
                for step in range(len(steps)):
                    with np.load(r/(name+'-'+str(step)+'.npz'),allow_pickle=False) as z:
                        cap,refresh,offset,lc,rc=map(int,z['parameters']);got=candidate.update(z['chunk'],z['predictions'],offset=offset,left=lc,right=rc)
                        assert np.array_equal(got,z['candidate_chunk'])
                        for field,_ in fields:assert np.array_equal(getattr(candidate,field),z['candidate_'+field])
            # Ambiguous finite selections must reject atomically; do not claim tie parity.
            state=State(sil);chunk=np.ones((264,512),np.float32);preds=np.zeros((264,8),np.float32);preds[:,0]=.9
            state.update(chunk,preds,offset=0)
            before=[getattr(state,f).tobytes() for f,_ in fields]+[state.offset,state.compressed]
            try:state.update(chunk,np.concatenate((preds,preds)),offset=264)
            except AmbiguousSelection:pass
            else:raise AssertionError('Finite tie silently selected')
            assert before==[getattr(state,f).tobytes() for f,_ in fields]+[state.offset,state.compressed]
            rejected=0
            for bad_offset in [-1,265,0]:
                try:state.update(chunk,np.concatenate((preds,preds)),offset=bad_offset)
                except ValueError:rejected+=1
                else:raise AssertionError('Discontinuity accepted')
            result.update(status='STATE_REFERENCE_CASES_REVIEW_REQUIRED',fixture_names=fixture_names,absolute_tolerance=a['absolute_tolerance'],finite_ties_supported=False,finite_tie_rejected_atomically=True,discontinuities_rejected=rejected,complete_driver=False,native_pi_qualified=False)
        except Exception as exc:result.update(error=repr(exc),traceback=traceback.format_exc())
    result['seconds']=time.monotonic()-start;save(r/'RESULT.json',result)
    return int(result['status']!='STATE_REFERENCE_CASES_REVIEW_REQUIRED')

if __name__=='__main__':raise SystemExit(main())
