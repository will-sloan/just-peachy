"""Bounded D1 FP32 graph export candidate; README_D1_ONNX_EXPORT_V3.md."""
import argparse, contextlib, hashlib, json, os, sys, time, traceback
from pathlib import Path


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);args=ap.parse_args()
    r=args.root; a=json.loads((r/'ADMISSION.json').read_text(encoding='utf-8'))
    for b in a['bindings']:assert sha(b['path'])==b['sha256'],b['path']
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='disabled',ORT_DISABLE_TELEMETRY='1')
    temp=r/'temp';temp.mkdir();os.environ['TMP']=os.environ['TEMP']=str(temp)
    import tempfile
    tempfile.tempdir=str(temp)
    import psutil
    p=psutil.Process();p.cpu_affinity([4,14]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    save(r/'MODEL_OWNER.json',dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()))
    started=time.monotonic();result=dict(status='FAILED_PRESERVED',gpu=False,threads=1,stage_acceptance=False)
    with (r/'export.log').open('x',encoding='utf-8',buffering=1) as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            import numpy as np
            import torch,onnx,onnxruntime as ort
            torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(20260929)
            from nemo.collections.asr.models import SortformerEncLabelModel
            import inspect
            assert sha(inspect.getfile(SortformerEncLabelModel))==a['model_source_sha256']
            model=SortformerEncLabelModel.restore_from(a['checkpoint'],map_location='cpu',strict=True).eval()
            assert model.high_resolution and model.output_subsampling_factor==1 and model.sortformer_modules.n_spk==8
            sm=model.sortformer_modules
            sm.chunk_len=264;sm.chunk_left_context=1;sm.chunk_right_context=1;sm.fifo_len=0;sm.spkcache_len=264;sm.spkcache_update_period=188
            model.async_streaming=False;model._check_streaming_parameters();model.preprocessor.featurizer.dither=0.0
            model.preprocessor.eval()
            save(r/'MODEL_LOADED.json',dict(seconds=time.monotonic()-started,parameters=sum(v.numel() for v in model.parameters()),
                torch=torch.__version__,onnx=onnx.__version__,ort=ort.__version__,precision='FP32',geometry=[264,1,1,0,264,188]))
            class Graph(torch.nn.Module):
                def __init__(self,m):super().__init__();self.m=m;self.pad_for_export=False
                def forward(self,chunk,chunk_lengths,spkcache,spkcache_lengths,fifo,fifo_lengths):
                    if self.pad_for_export:chunk=torch.nn.functional.pad(chunk,(0,0,0,(-chunk.shape[1])%8))
                    return self.m.forward_for_export(chunk,chunk_lengths,spkcache,spkcache_lengths,fifo,fifo_lengths)
            graph=Graph(model).eval();feat=model.encoder._feat_in;emb=sm.fc_d_model
            def inputs(frames,cache,fifo):
                return (torch.randn(1,frames,feat),torch.tensor([frames]),torch.randn(1,cache,emb),torch.tensor([cache]),torch.randn(1,fifo,emb),torch.tensor([fifo]))
            example=inputs(2128,264,0)
            names=['chunk','chunk_lengths','spkcache','spkcache_lengths','fifo','fifo_lengths']
            outputs=['spkcache_fifo_chunk_preds','chunk_pre_encode_embs','chunk_pre_encode_lengths']
            dynamic={'chunk':{1:'chunk_frames'},'spkcache':{1:'cache_frames'},'fifo':{1:'fifo_frames'},
                     outputs[0]:{1:'output_frames'},outputs[1]:{1:'encoded_frames'}}
            cases=[('delayed_warm',example),('cold_short',inputs(32,0,0)),('dynamic_tail',inputs(17,8,3))]
            with torch.inference_mode():reference=[[v.detach().numpy() for v in graph(*inp)] for _,inp in cases]
            from d1_export_attention_v1 import dense_export_attention
            attention_context=dense_export_attention(model);attention_context.__enter__();graph.pad_for_export=True
            adapter_checks=[]
            for (name,inp),ref in zip(cases,reference):
                with torch.inference_mode():adapted=[v.detach().numpy() for v in graph(*inp)]
                diffs=[float(np.max(np.abs(x.astype(np.float64)-y.astype(np.float64)))) if x.size else 0.0 for x,y in zip(ref,adapted)]
                row=dict(case=name,max_absolute_differences=diffs,absolute_tolerance=a['absolute_tolerance']);adapter_checks.append(row)
                np.savez(r/('attention_'+name+'.npz'),**{**{'reference_'+str(i):v for i,v in enumerate(ref)},**{'adapted_'+str(i):v for i,v in enumerate(adapted)}})
                save(r/('attention_'+name+'.json'),row)
                assert diffs[0]<=a['absolute_tolerance'] and diffs[1]<=a['absolute_tolerance'] and diffs[2]==0,'Attention replacement parity gate failed'
            save(r/'ATTENTION_PARITY.json',dict(status='THREE_CASES_COLLECTED_REVIEW_REQUIRED',cases=adapter_checks))
            graph_path=r/'sortformer_fp32.onnx';beg=time.monotonic()
            with torch.inference_mode():
                torch.onnx.export(graph,example,str(graph_path),input_names=names,output_names=outputs,
                    opset_version=17,dynamo=False,dynamic_axes=dynamic,do_constant_folding=True)
            result['export_seconds']=time.monotonic()-beg
            onnx.checker.check_model(str(graph_path));g=onnx.load(str(graph_path),load_external_data=False)
            ops={}
            for n in g.graph.node:
                key=(n.domain or 'ai.onnx')+':'+n.op_type;ops[key]=ops.get(key,0)+1
            assert all(n.domain in ('','ai.onnx') for n in g.graph.node),'Unexpected custom operators'
            save(r/'GRAPH.json',dict(sha256=sha(graph_path),bytes=graph_path.stat().st_size,opset=[dict(domain=x.domain,version=x.version) for x in g.opset_import],
                operators=ops,inputs=[x.name for x in g.graph.input],outputs=[x.name for x in g.graph.output],waveform_frontend_included=False,
                streaming_update_included=False,probabilities='coarse grid; high-resolution postprocessing is outside this export'))
            del g
            so=ort.SessionOptions();so.intra_op_num_threads=1;so.inter_op_num_threads=1
            so.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
            session=ort.InferenceSession(str(graph_path),so,providers=['CPUExecutionProvider'])
            assert [x.name for x in session.get_inputs()]==names
            checks=[]
            for (name,inp),expected in zip(cases,reference):
                feed={n:v.numpy() for n,v in zip(names,inp)};actual=session.run(outputs,feed)
                diffs=[]
                for i,(ref,got) in enumerate(zip(expected,actual)):
                    assert ref.shape==got.shape and np.isfinite(ref).all() and np.isfinite(got).all()
                    delta=float(np.max(np.abs(ref.astype(np.float64)-got.astype(np.float64)))) if ref.size else 0.0
                    diffs.append(delta)
                np.savez(r/(name+'.npz'),**{**{'input_'+k:v for k,v in feed.items()},**{'reference_'+str(i):v for i,v in enumerate(expected)},**{'ort_'+str(i):v for i,v in enumerate(actual)}})
                row=dict(case=name,max_absolute_differences=diffs,shapes=[list(v.shape) for v in actual],absolute_tolerance=a['absolute_tolerance'])
                save(r/(name+'.json'),row);checks.append(row)
                assert diffs[0]<=a['absolute_tolerance'] and diffs[1]<=a['absolute_tolerance'] and diffs[2]==0,'Predeclared FP32 parity gate failed'
            f=model.preprocessor.featurizer
            np.savez(r/'frontend_buffers.npz',window=f.window.detach().cpu().numpy(),filterbank=f.fb.detach().cpu().numpy())
            frontend={k:getattr(f,k) for k in ['n_fft','hop_length','win_length','normalize','pad_to','frame_splicing','log','log_zero_guard_type','log_zero_guard_value','preemph','mag_power','exact_pad']}
            save(r/'FRONTEND.json',dict(parameters=frontend,sample_rate=16000,dither=0,features=feat,implemented_portable_frontend=False))
            result.update(status='EXPORTED_GRAPH_THREE_CASES_REVIEW_REQUIRED',checks=checks,graph_sha256=sha(graph_path),
                complete_streaming_driver=False,native_pi_execution=False,frontend_ported=False,speedup_qualified=False)
            attention_context.__exit__(None,None,None)
            del session,graph,model
        except Exception as e:
            result['error']=repr(e)
            with (r/'exception.txt').open('x',encoding='utf-8') as f:f.write(traceback.format_exc())
        finally:
            result.update(seconds=time.monotonic()-started,rss_bytes=p.memory_info().rss)
            save(r/'RESULT.json',result)
    return 0 if result['status']=='EXPORTED_GRAPH_THREE_CASES_REVIEW_REQUIRED' else 1


if __name__=='__main__':raise SystemExit(main())
