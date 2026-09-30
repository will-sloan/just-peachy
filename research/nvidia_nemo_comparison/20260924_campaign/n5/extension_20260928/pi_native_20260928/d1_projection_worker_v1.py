"""Isolate natural-feature projection arithmetic; README_D1_PROJECTION_V1.md."""
import argparse,contextlib,hashlib,io,json,os,tarfile,time,traceback
from pathlib import Path


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);r=ap.parse_args().root;a=json.loads((r/'ADMISSION.json').read_text())
    for b in a['bindings']:assert sha(b['path'])==b['sha256']
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='disabled',ORT_DISABLE_TELEMETRY='1')
    import psutil
    proc=psutil.Process();proc.cpu_affinity([4,14]);proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    save(r/'MODEL_OWNER.json',dict(pid=proc.pid,create_time=proc.create_time(),affinity=proc.cpu_affinity()))
    began=time.monotonic();out=dict(status='FAILED_PRESERVED',cases=[],absolute_tolerance=1e-5,waveform_accepted=False,native_pi_qualified=False)
    with (r/'diagnostic.log').open('x',encoding='utf-8',buffering=1) as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            import numpy as np,onnx,onnxruntime as ort,torch
            from onnx.utils import Extractor
            torch.set_num_threads(1);torch.set_num_interop_threads(1)
            from nemo.collections.asr.parts.submodules.subsampling import FeatureStacking
            # Read only the pinned tensor archive into RAM; never extract files.
            with tarfile.open(a['checkpoint'],'r:*') as tar:
                members=[m for m in tar.getmembers() if m.isfile() and m.name.endswith('model_weights.ckpt')]
                assert len(members)==1 and members[0].size==198666820
                data=tar.extractfile(members[0]).read();assert len(data)==members[0].size
            tensors=torch.load(io.BytesIO(data),map_location='cpu',weights_only=True);del data
            if 'state_dict' in tensors:tensors=tensors['state_dict']
            key='encoder.pre_encode.proj.weight';weight=tensors[key].float().clone();del tensors
            assert tuple(weight.shape)==(512,1024)
            original=FeatureStacking(subsampling_factor=8,feat_in=128,feat_out=512).eval()
            original.load_state_dict({'proj.weight':weight},strict=True)
            graph=onnx.load(a['graph'],load_external_data=False)
            producers={out:node for node in graph.graph.node for out in node.output}
            endpoint=producers['chunk_pre_encode_embs'];assert endpoint.op_type=='MatMul'
            stack_name,weight_name=endpoint.input
            initializer=next(v for v in graph.graph.initializer if v.name==weight_name)
            graph_weight=onnx.numpy_helper.to_array(initializer).copy()
            assert np.array_equal(graph_weight,weight.numpy().T)
            graph.graph.value_info.append(onnx.helper.make_tensor_value_info(stack_name,onnx.TensorProto.FLOAT,[1,'encoded_frames',1024]))
            sub=Extractor(graph).extract_model(['chunk','chunk_lengths'],['chunk_pre_encode_embs','chunk_pre_encode_lengths',stack_name])
            assert sum(n.op_type=='MatMul' for n in sub.graph.node)==1
            onnx.checker.check_model(sub);onnx.save(sub,r/'preencoder.onnx');del graph,sub
            assert (r/'preencoder.onnx').stat().st_size<4*1024**2
            np.save(r/'projection_weight.npy',weight.numpy())
            save(r/'GRAPH.json',dict(graph_sha256=sha(r/'preencoder.onnx'),bytes=(r/'preencoder.onnx').stat().st_size,
                 original_graph_sha256=sha(a['graph']),checkpoint_tensor_key=key,checkpoint_weight_equals_graph=True,
                 stack_output=stack_name,projection_output='chunk_pre_encode_embs',checkpoint_files_extracted=False))
            sessions={}
            for name,level in [('basic',ort.GraphOptimizationLevel.ORT_ENABLE_BASIC),('disabled',ort.GraphOptimizationLevel.ORT_DISABLE_ALL)]:
                so=ort.SessionOptions();so.intra_op_num_threads=1;so.inter_op_num_threads=1;so.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;so.graph_optimization_level=level
                sessions[name]=ort.InferenceSession(str(r/'preencoder.onnx'),so,providers=['CPUExecutionProvider'])
            parent=r.parent/'d1-onnx-waveform-v2';fixtures=r.parent/'d1-onnx-frontend-v1'
            full=np.load(fixtures/'full.npz');tail=np.load(fixtures/'tail.npz')
            specs=[('tail',tail['reference'][0,:,:8].T.copy(),0,0),('full_first',full['reference'][0,:,:2120].T.copy(),0,1),
                   ('full_middle',full['reference'][0,:,2104:4232].T.copy(),1,1),('full_tail',full['reference'][0,:,4216:4469].T.copy(),1,0)]
            full.close();tail.close()
            for name,chunk,left,right in specs:
                before=chunk.tobytes();length=np.array([len(chunk)],np.int64);stack=np.pad(chunk,((0,(-len(chunk))%8),(0,0))).reshape(1,-1,1024)
                with torch.inference_mode():
                    ref,lens=original(torch.from_numpy(chunk[None]).transpose(1,2),torch.from_numpy(length))
                    manual=torch.nn.functional.linear(torch.from_numpy(stack),weight)
                ref=ref.numpy();lens=lens.numpy();assert np.array_equal(ref,manual.numpy())
                arrays=dict(chunk=chunk,stack=stack,pytorch=ref,lengths=lens)
                # Float64 is a diagnostic accumulation reference, not a replacement runtime.
                fp64=stack.astype(np.float64)@weight.numpy().astype(np.float64).T;arrays['float64_accumulation']=fp64
                row=dict(case=name,feature_frames=len(chunk),encoded_frames=len(stack[0]),left_coarse=left,right_coarse=right,shape=list(ref.shape),
                         maximum_embedding_magnitude=float(np.abs(ref).max()),pytorch_vs_float64_maxabs=float(np.abs(ref.astype(np.float64)-fp64).max()),paths={})
                for label,session in sessions.items():
                    feed={'chunk':chunk[None],'chunk_lengths':length};got,got_lengths,got_stack=session.run(None,feed);repeat=session.run(None,feed)
                    assert np.array_equal(stack,got_stack) and np.array_equal(lens,got_lengths) and all(np.array_equal(x,y) for x,y in zip((got,got_lengths,got_stack),repeat))
                    arrays[label]=got
                    delta=float(np.abs(got.astype(np.float64)-ref.astype(np.float64)).max())
                    row['paths'][label]=dict(max_abs=delta,within_unchanged_gate=delta<=a['absolute_tolerance'],stack_exact=True,lengths_exact=True,repeat_exact=True,
                                             versus_float64_maxabs=float(np.abs(got.astype(np.float64)-fp64).max()))
                if name in ['tail','full_first']:
                    source='tail' if name=='tail' else 'full'
                    with np.load(parent/(source+'-reference.npz')) as z:retained=z['0_spkcache'].copy()
                    central=ref[:,left:ref.shape[1]-right if right else None]
                    assert retained.shape==central.shape
                    arrays['retained_first_cache']=retained
                    row['pytorch_vs_retained_first_cache_maxabs']=float(np.abs(central.astype(np.float64)-retained.astype(np.float64)).max())
                    row['basic_vs_retained_first_cache_maxabs']=float(np.abs(arrays['basic'][:,left:ref.shape[1]-right if right else None].astype(np.float64)-retained.astype(np.float64)).max())
                assert chunk.tobytes()==before
                np.savez(r/(name+'.npz'),**arrays);out['cases'].append(row)
            sessions.clear();del original
            out.update(status='PROJECTION_ISOLATION_OBSERVATIONS_REVIEW_REQUIRED',checkpoint_weight_equals_graph=True,
                       checkpoint_files_extracted=False,subgraph_bytes=(r/'preencoder.onnx').stat().st_size,
                       stack_and_lengths_exact=True,precision_gate_changed=False,speedup_qualified=False)
        except Exception as exc:out.update(error=repr(exc),traceback=traceback.format_exc())
    out['seconds']=time.monotonic()-began;save(r/'RESULT.json',out)
    return int(out['status']=='FAILED_PRESERVED')


if __name__=='__main__':raise SystemExit(main())
