"""Isolate observed cache tie; README_D1_STATE_TIE_V2.md."""
import argparse,contextlib,hashlib,json,os,time,traceback
from pathlib import Path

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);r=ap.parse_args().root
    a=json.loads((r/'ADMISSION.json').read_text(encoding='utf-8'));old=r.parent/'d1-onnx-state-v1'
    for b in a['bindings']:assert sha(b['path'])==b['sha256']
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='disabled')
    import psutil
    proc=psutil.Process();proc.cpu_affinity([4,14]);proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    save(r/'MODEL_OWNER.json',dict(pid=proc.pid,create_time=proc.create_time(),affinity=proc.cpu_affinity()))
    start=time.monotonic();result=dict(status='FAILED_PRESERVED',model_inference=False)
    with (r/'tie.log').open('x',encoding='utf-8',buffering=1) as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            import numpy as np,torch,onnx,onnxruntime as ort
            torch.set_num_threads(1);torch.set_num_interop_threads(1)
            from nemo.collections.asr.modules.sortformer_modules import SortformerModules
            from d1_numpy_state_v1 import State,AmbiguousSelection
            rng=np.random.default_rng(20260929);prior=json.loads((old/'RESULT.json').read_text());verified=[]
            def generate(name,n,frames):
                chunk=rng.normal(0,.1,(frames,512)).astype(np.float32)
                preds=rng.uniform(.01,.04,(n,8)).astype(np.float32)
                if name=='quiet':preds[:]=0
                elif name=='overlap':preds[:,:3]=rng.uniform(.55,.98,(n,3)).astype(np.float32)
                else:
                    speakers=rng.integers(0,8,n);preds[np.arange(n),speakers]=rng.uniform(.55,.999,n).astype(np.float32)
                return chunk,preds
            for entry in prior['cases']:
                filename=entry['case']+'-'+str(entry['step'])+'.npz'
                with np.load(old/filename,allow_pickle=False) as z:
                    chunk,preds=generate(entry['case'],len(z['predictions']),len(z['chunk']))
                    assert chunk.tobytes()==z['chunk'].tobytes() and preds.tobytes()==z['predictions'].tobytes()
                verified.append(filename)
            assert len(verified)==14
            with np.load(old/'overlap-1.npz',allow_pickle=False) as z:
                cache=z['reference_cache'];cache_probs=z['reference_cache_probs'];sil=z['silence']
            chunk,preds=generate('overlap',264+18,18)
            joined=np.concatenate((cache,chunk[1:]));joined_probs=np.concatenate((cache_probs,preds[265:]))
            np.savez(r/'reconstructed_input.npz',chunk=chunk,predictions=preds,cache=cache,cache_probs=cache_probs,silence=sil,joined=joined,joined_probs=joined_probs)
            state=State(sil);state.cache=cache.copy();state.cache_probs=cache_probs.copy();state.compressed=True;state.offset=528
            before=(state.cache.tobytes(),state.cache_probs.tobytes(),state.offset,state.compressed)
            try:state.update(chunk,preds,offset=528,left=1,right=0)
            except AmbiguousSelection:pass
            else:raise AssertionError('Observed tie not reproduced')
            assert before==(state.cache.tobytes(),state.cache_probs.tobytes(),state.offset,state.compressed)
            result.update(reconstructed_prefix_byte_exact=verified,finite_tie_reproduced=True,rejection_atomicity_verified=True)
            model=SortformerModules(num_spks=8,fc_d_model=512,tf_d_model=192,spkcache_len=264,fifo_len=0,chunk_len=264,spkcache_update_period=188,spkcache_sil_frames_per_spk=1,use_learnable_sil_emb=True).eval()
            with torch.no_grad():model.learnable_sil_emb.copy_(torch.from_numpy(sil))
            inputs=(torch.from_numpy(joined)[None],torch.from_numpy(joined_probs)[None],torch.from_numpy(sil)[None])
            with torch.inference_mode():reference=[x.numpy() for x in model._compress_spkcache(*inputs)[:2]]
            model.use_learnable_sil_emb=False
            with torch.inference_mode():explicit=[x.numpy() for x in model._compress_spkcache(*inputs)[:2]]
            assert all(np.array_equal(x,y) for x,y in zip(reference,explicit))
            np.savez(r/'pytorch_reference.npz',cache=reference[0],cache_probs=reference[1])
            class Graph(torch.nn.Module):
                def __init__(self,m):super().__init__();self.m=m
                def forward(self,embeddings,probabilities,silence):return self.m._compress_spkcache(embeddings,probabilities,silence)[:2]
            graph=r/'cache_compression.onnx'
            with torch.inference_mode():torch.onnx.export(Graph(model),inputs,str(graph),opset_version=17,dynamo=False,input_names=['embeddings','probabilities','silence'],output_names=['cache','cache_probs'],dynamic_axes={'embeddings':{1:'frames'},'probabilities':{1:'frames'}})
            g=onnx.load(str(graph));producers={out:node for node in g.graph.node for out in node.output};repairs=[]
            for node in g.graph.node:
                if node.op_type=='Add' and len(node.input)==2 and all(value in producers and producers[value].op_type in ('Equal','GreaterOrEqual','Greater','LessOrEqual','Less') for value in node.input):
                    repairs.append(dict(name=node.name,inputs=list(node.input),old_type='Add',new_type='Or'));node.op_type='Or'
            assert len(repairs)==1,'Unexpected bool-union export structure'
            onnx.save(g,str(graph));save(r/'BOOLEAN_UNION_REPAIR.json',dict(repairs=repairs,original_source_unchanged=True,semantics='Torch boolean in-place addition is logical union, not numeric Add'))
            onnx.checker.check_model(str(graph),full_check=True);options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
            session=ort.InferenceSession(str(graph),options,providers=['CPUExecutionProvider'])
            output=session.run(None,{name:x.numpy() for name,x in zip(['embeddings','probabilities','silence'],inputs)})
            repeat=session.run(None,{name:x.numpy() for name,x in zip(['embeddings','probabilities','silence'],inputs)})
            errors=[float(np.max(np.abs(x.astype(np.float64)-y))) for x,y in zip(reference,output)]
            np.savez(r/'comparison.npz',reference_cache=reference[0],reference_probs=reference[1],ort_cache=output[0],ort_probs=output[1],repeat_cache=repeat[0],repeat_probs=repeat[1])
            result.update(graph_sha256=sha(graph),graph_bytes=graph.stat().st_size,max_abs=errors,repeat_exact=all(np.array_equal(x,y) for x,y in zip(output,repeat)),status='CACHE_TIE_GRAPH_PASS_REVIEW_REQUIRED' if max(errors)<=a['absolute_tolerance'] else 'CACHE_TIE_GRAPH_MISMATCH_PRESERVED',native_pi_qualified=False,complete_driver=False)
            session=None
        except Exception as exc:result.update(error=repr(exc),traceback=traceback.format_exc())
    result['seconds']=time.monotonic()-start;save(r/'RESULT.json',result)
    return int(result['status']!='CACHE_TIE_GRAPH_PASS_REVIEW_REQUIRED')

if __name__=='__main__':raise SystemExit(main())
