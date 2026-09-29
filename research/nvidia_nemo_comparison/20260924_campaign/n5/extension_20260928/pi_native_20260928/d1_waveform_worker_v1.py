"""Original-model full waveform reference and candidate. README_D1_WAVEFORM_V1.md."""
import argparse,contextlib,hashlib,json,os,time,traceback,wave
from pathlib import Path

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);r=parser.parse_args().root
    a=json.loads((r/'ADMISSION.json').read_text(encoding='utf-8'))
    for b in a['bindings']:assert sha(b['path'])==b['sha256']
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='disabled',ORT_DISABLE_TELEMETRY='1')
    temp=r/'temp';temp.mkdir();os.environ['TMP']=os.environ['TEMP']=str(temp)
    import tempfile
    tempfile.tempdir=str(temp)
    import psutil
    proc=psutil.Process();proc.cpu_affinity([4,14]);proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    save(r/'MODEL_OWNER.json',dict(pid=proc.pid,create_time=proc.create_time(),affinity=proc.cpu_affinity()))
    started=time.monotonic();result=dict(status='FAILED_PRESERVED',cases=[],complete_native_runtime=False)
    candidate=None
    with (r/'waveform.log').open('x',encoding='utf-8',buffering=1) as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            import numpy as np,torch
            torch.set_num_threads(1);torch.set_num_interop_threads(1)
            from nemo.collections.asr.models import SortformerEncLabelModel
            from d1_waveform_runtime_v1 import WaveformD1
            model=SortformerEncLabelModel.restore_from(a['checkpoint'],map_location='cpu',strict=True).eval()
            model.streaming_mode=True;model.async_streaming=False
            sm=model.sortformer_modules;sm.chunk_len=264;sm.chunk_left_context=1;sm.chunk_right_context=1
            sm.fifo_len=0;sm.spkcache_len=264;sm.spkcache_update_period=188
            model._check_streaming_parameters();model.preprocessor.featurizer.dither=0.0
            assert model.high_resolution and model.output_subsampling_factor==1 and sm.use_learnable_sil_emb
            silence=sm.learnable_sil_emb.detach().cpu().numpy().copy();np.save(r/'learned_silence.npy',silence)
            f=model.preprocessor.featurizer
            with np.load(a['coefficients']) as z:
                assert np.array_equal(z['window'],f.window.detach().numpy()) and np.array_equal(z['filterbank'],f.fb.detach().numpy())
            with wave.open(a['source_wav'],'rb') as wav:
                assert (wav.getframerate(),wav.getnchannels(),wav.getsampwidth(),wav.getnframes())==(16000,1,2,715127)
                audio=np.frombuffer(wav.readframes(715127),'<i2').astype(np.float32)/32768
            np.save(r/'source_float32.npy',audio)
            original_step=model.forward_streaming_step;events=[];state_arrays={}
            def observe_step(**kw):
                old_rows=kw['total_preds'].shape[1]
                before_cache=kw['streaming_state'].spkcache.shape[1];before_fifo=kw['streaming_state'].fifo.shape[1]
                state,total=original_step(**kw);index=len(events)
                events.append(dict(graph_feature_rows=kw['processed_signal'].shape[1],valid_feature_rows=int(kw['processed_signal_length'][0]),
                    left_features=kw['left_offset'],right_features=kw['right_offset'],before_cache=before_cache,before_fifo=before_fifo,
                    raw_output_start=old_rows,raw_output_end=total.shape[1],cache_rows=state.spkcache.shape[1],fifo_rows=state.fifo.shape[1]))
                for name in ['spkcache','spkcache_preds','fifo','fifo_preds']:
                    value=getattr(state,name,None)
                    if value is not None:state_arrays[str(index)+'_'+name]=value.detach().numpy().copy()
                return state,total
            model.forward_streaming_step=observe_step
            references={};reference_meta={}
            for name,x in [('tail',audio[:1281]),('full',audio)]:
                events.clear();state_arrays.clear();beg=time.perf_counter()
                with torch.inference_mode():ref=model.forward(torch.from_numpy(x.copy())[None],torch.tensor([len(x)]))[0].numpy()
                seconds=time.perf_counter()-beg
                assert ref.shape==(len(x)//160,8) and np.isfinite(ref).all()
                references[name]=ref.copy();reference_meta[name]=list(events)
                np.savez(r/(name+'-reference.npz'),audio=x,probabilities=ref,**state_arrays)
                save(r/(name+'-reference.json'),dict(samples=len(x),frames=len(ref),seconds=seconds,chunks=list(events)))
            events.clear();state_arrays.clear()
            with torch.inference_mode():repeat=model.forward(torch.from_numpy(audio.copy())[None],torch.tensor([len(audio)]))[0].numpy()
            np.save(r/'full-pytorch-repeat.npy',repeat);assert np.array_equal(repeat,references['full'])
            model.forward_streaming_step=original_step
            # Explicit coefficients from this actual checkpoint, never synthetic silence values.
            candidate=WaveformD1(a['graph'],a['compression'],a['coefficients'],silence)
            for name,x,sizes,refname in [('tail',audio[:1281],(3200,),'tail'),('full',audio,(3200,),'full'),('irregular',audio,(1,7,159,160,161,4093),'full'),('repeat',audio,(3200,),'full')]:
                before=x.tobytes();beg=time.perf_counter();got=candidate.process(x,sizes);seconds=time.perf_counter()-beg
                ref=references[refname];assert x.tobytes()==before and got.shape==ref.shape and np.isfinite(got).all()
                delta=float(np.max(np.abs(ref.astype(np.float64)-got.astype(np.float64)))) if got.size else 0.0
                np.savez(r/(name+'-candidate.npz'),probabilities=got,cache=candidate.state.cache,cache_probs=candidate.state.cache_probs,fifo=candidate.state.fifo,fifo_probs=candidate.state.fifo_probs)
                row=dict(case=name,samples=len(x),frames=len(got),max_abs=delta,seconds=seconds,source_bytes_unchanged=True,
                    trace=list(candidate.trace),peak_feature_rows=candidate.peak_feature_rows,frontend_seconds=candidate.frontend_seconds,
                    model_seconds=candidate.model_seconds,state_seconds=candidate.state_seconds,subhop_remainder_samples=len(x)%160,
                    source_samples_accepted=candidate.samples,frontend_samples=candidate.frontend.total,final_features_empty=candidate.features.size==0)
                state_deltas={}
                last=len(reference_meta[refname])-1
                with np.load(r/(refname+'-reference.npz')) as refstates:
                    for label,field in [('spkcache','cache'),('spkcache_preds','cache_probs'),('fifo','fifo'),('fifo_preds','fifo_probs')]:
                        key=str(last)+'_'+label
                        if key not in refstates:continue
                        truth=refstates[key][0];actual=getattr(candidate.state,field)
                        assert truth.shape==actual.shape
                        state_deltas[field]=float(np.max(np.abs(truth.astype(np.float64)-actual.astype(np.float64)))) if actual.size else 0.0
                row['final_state_max_abs']=state_deltas
                result['cases'].append(row);save(r/(name+'-candidate.json'),row)
                assert delta<=a['absolute_tolerance'],'Predeclared full-waveform1e-5 gate failed'
                assert max(state_deltas.values(),default=0)<=a['absolute_tolerance'],'Predeclared final-state1e-5 gate failed'
                expected=reference_meta[refname];assert len(expected)==len(candidate.trace)
                for truth,observed in zip(expected,candidate.trace):
                    for key in ['graph_feature_rows','left_features','right_features','cache_rows','fifo_rows']:assert truth[key]==observed[key]
                    assert observed['highres_offset']==(truth['before_cache']+truth['before_fifo']+truth['left_features']//8)*8
                if name=='full':first=got.copy()
                if name in ['irregular','repeat']:assert np.array_equal(first,got),'Push segmentation changed probabilities'
            empty_cases=[]
            for n in [0,1,159]:
                out=candidate.process(audio[:n]);assert out.shape==(0,8) and candidate.samples==n and not candidate.trace
                empty_cases.append(n)
            invalid=0
            for call in [lambda:candidate.push(np.zeros(1,np.float32),source_start=159),candidate.finish]:
                try:call()
                except RuntimeError:invalid+=1
                else:raise AssertionError('Post-finish call accepted')
            for bad in [np.zeros((1,2),np.float32),np.zeros(1,np.float64),np.array([np.nan],np.float32),np.zeros(32769,np.float32)]:
                candidate.reset()
                try:candidate.push(bad,source_start=0)
                except ValueError:invalid+=1
                else:raise AssertionError('Malformed input accepted')
                assert candidate.samples==0 and candidate.state.offset==0 and candidate.available==0
            candidate.reset()
            try:candidate.push(audio[:160],source_start=1)
            except ValueError:invalid+=1
            else:raise AssertionError('Noncontiguous source accepted')
            assert candidate.samples==0
            candidate.close();candidate=None
            result.update(status='HOST_WAVEFORM_FULL_REFERENCE_REVIEW_REQUIRED',pytorch_repeat_exact=True,candidate_repeat_exact=True,
                irregular_exact=True,empty_contract_samples=empty_cases,invalid_calls_rejected=invalid,learned_silence_sha256=sha(r/'learned_silence.npy'),
                absolute_tolerance=a['absolute_tolerance'],runtime_released=True,no_accuracy_score=True)
            del model
        except Exception as exc:result.update(error=repr(exc),traceback=traceback.format_exc())
        finally:
            if candidate is not None:
                try:candidate.close();result['runtime_released']=True
                except Exception as exc:result['cleanup_error']=repr(exc)
    result['seconds']=time.monotonic()-started;save(r/'RESULT.json',result)
    return int(result['status']!='HOST_WAVEFORM_FULL_REFERENCE_REVIEW_REQUIRED')
if __name__=='__main__':raise SystemExit(main())
