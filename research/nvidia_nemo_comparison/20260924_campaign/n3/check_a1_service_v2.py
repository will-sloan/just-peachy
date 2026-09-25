"""Strict fresh-reference tests for the portable A1 service; README_A1_PORTABLE.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
import wave

for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('model','source','bundle','audio-manifest','output'):p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise ValueError('Use fresh parity evidence')
    args.output.mkdir(parents=True)
    report=dict(status='RUNNING',cases=[],dynamic_cases=[],host_service_qualified=False,ARM64_qualified=False)
    try:
        import psutil
        proc=psutil.Process();proc.cpu_affinity([4])
        if os.name=='nt':proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        if sha(args.model)!='6603a22a53b7c1a4bac4736cb24628fb568a7102ba931a28c799e2e72f109893':raise ValueError('Wrong checkpoint')
        sys.path.insert(0,str(args.source.resolve(strict=True)))
        import numpy as np
        import torch
        import nemo
        from a1_service import NemoStreamingASRService
        from a1_onnx_v2 import OnnxService
        from a1_export_contract import configure_service_export
        from diagnose_a1_parity import fresh_feed,compare_arrays
        if not Path(nemo.__file__).resolve().is_relative_to(args.source.resolve()):raise ValueError('Wrong source')
        torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(20260924)
        service=NemoStreamingASRService(model=str(args.model),device='cpu',att_context_size=[70,1],use_amp=False,chunk_size_in_secs=.08)
        report['original_feature_processor_training']=service._audio_buffer.preprocessor.training
        service._audio_buffer.preprocessor.eval()
        configure_service_export(service)
        portable=OnnxService(args.bundle,audit=True)
        encoder=service.asr_model.encoder
        for batch in (1,2):
            example=encoder.input_example(max_batch=batch);caches=[x.clone() for x in example[2:]]
            for step,width in enumerate((25,33,25)):
                inputs=[torch.randn(batch,128,width),torch.full((batch,),width,dtype=torch.int64),*caches]
                feed=fresh_feed([v.name for v in portable.encoder.get_inputs()],inputs)
                with torch.no_grad():gold=encoder.forward_for_export(*[x.clone() for x in inputs])
                actual=portable.encoder.run(None,feed);comparison=compare_arrays(actual,gold)
                report['dynamic_cases'].append(dict(batch=batch,step=step,outputs=comparison))
                if not all(x['within_tolerance'] for x in comparison):raise ValueError('Service encoder dynamic parity failed')
                caches=[x.detach().clone() for x in gold[2:]]
        observed={}
        original_encoder=encoder.cache_aware_stream_step
        def capture_encoder(*a,**kw):
            observed['features']=kw['processed_signal'].detach().cpu().numpy()[0].copy()
            outputs=original_encoder(*a,**kw)
            observed['encoder']=[x.detach().cpu().numpy().copy() for x in outputs]
            observed['encoder'][2]=observed['encoder'][2].transpose(1,0,2,3)
            observed['encoder'][3]=observed['encoder'][3].transpose(1,0,2,3)
            return outputs
        encoder.cache_aware_stream_step=capture_encoder
        original_best=service._get_best_hypothesis
        def capture_decoder(*a,**kw):
            best=original_best(*a,**kw);state=best[0].dec_state
            observed['decoder']=[x.detach().cpu().numpy().reshape(1,1,640).copy() for x in state] if state is not None else [np.zeros((1,1,640),np.float32)]*2
            return best
        service._get_best_hypothesis=capture_decoder
        manifest=json.loads(args.audio_manifest.read_text(encoding='utf-8'))
        jobs=manifest['jobs']
        allowed={'job_id','audio_path','audio_sha256','frames','sample_rate_hz','gain','reset_between_scenes','tap'}
        if not jobs or any(set(j)!=allowed for j in jobs):raise ValueError('Strict audio-only manifest required')
        # Four predeclared panel cells plus one exact replay; no score-based selection.
        if len(jobs)!=4:raise ValueError('Use the predeclared four-cell panel')
        for index,job in enumerate(jobs+[jobs[0]]):
            if job['gain']!=1 or job['reset_between_scenes'] is not True or sha(job['audio_path'])!=job['audio_sha256']:
                raise ValueError('Prepared audio/gain/reset binding differs')
            with wave.open(job['audio_path'],'rb') as wav:
                if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())!=(1,2,16000,job['frames']):raise ValueError('Audio format differs')
                pcm=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').copy()
            service.reset_state();portable.reset_state()
            maximum=np.zeros(8);steps=0;controls=0;token_digest=hashlib.sha256()
            row=dict(job_id=job['job_id'],repeat=index==4,input_samples=len(pcm),steps=0,status='RUNNING')
            report['cases'].append(row)
            blocks=[np.pad(pcm[i:i+1280],(0,max(0,1280-len(pcm[i:i+1280])))) for i in range(0,len(pcm),1280)]
            blocks.extend([np.zeros(1280,dtype='<i2') for _ in range(16)])
            for block in blocks:
                raw=block.astype('<i2',copy=False).tobytes()
                gold=service.transcribe(raw);actual=portable.transcribe(raw)
                left=[portable.last_step['features'],*portable.last_step['encoder'],*portable.last_step['decoder']]
                right=[observed['features'],*observed['encoder'],*observed['decoder']]
                comparison=compare_arrays(left,right)
                maximum=np.maximum(maximum,[x['maximum_absolute_error'] or 0 for x in comparison])
                if not all(x['within_tolerance'] for x in comparison):
                    row.update(failed_step=steps,comparison=comparison)
                    raise ValueError('Frontend/encoder/recurrent decoder state parity failed')
                if (actual.text,actual.is_final)!=(gold.text,gold.is_final):
                    row.update(failed_step=steps,reference_delta=gold.text,portable_delta=actual.text)
                    raise ValueError('Token/EOU sequence differs')
                for name in ('eou_prob','eob_prob'):
                    a,b=getattr(actual,name),getattr(gold,name)
                    if (a is None)!=(b is None) or a is not None and not np.isclose(a,b,rtol=2e-4,atol=2e-4):raise ValueError('Control probability differs')
                controls+=int(actual.is_final);token_digest.update(actual.text.encode());steps+=1
            row.update(status='PASS',steps=steps,controls=controls,text_digest=token_digest.hexdigest(),maximum_absolute_errors=maximum.tolist())
            print(json.dumps(dict(job=job['job_id'],repeat=index==4,status='PASS',steps=steps)),flush=True)
        if report['cases'][0]['text_digest']!=report['cases'][-1]['text_digest']:raise ValueError('Repeated stream differs')
        report.update(status='PASS_SERVICE_PARITY',host_service_qualified=True,
            bundle_sha256=sha(args.bundle/'BUNDLE.json'),manifest_sha256=sha(args.audio_manifest),
            scope='CPU reference/portable component parity; not performance, Controller, ARM64 or CM5 qualification',
            remaining=['Empty/tail API fixtures and independent application-runtime smoke',
                'Deterministic A1 screen/regression/paced and actual Controller integration'])
    except Exception as exc:
        report.update(status='PARITY_FAILED',error=repr(exc))
        (args.output/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        (args.output/'RESULT.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('status','error','host_service_qualified')}))


if __name__=='__main__':main()
