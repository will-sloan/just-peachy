"""Export the actual A1 service geometry and inference frontend; README_A1_PORTABLE.md."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''


def binding(path):
    path=Path(path)
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(name=path.name,sha256=digest,bytes=path.stat().st_size)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('model','source','output'):p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise ValueError('Use a fresh output; preserve previous exports')
    args.output.mkdir(parents=True)
    result=dict(status='RUNNING',portable_streaming_qualified=False)
    try:
        import psutil
        process=psutil.Process();process.cpu_affinity([4])
        if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        model_hash=binding(args.model)['sha256']
        if model_hash!='6603a22a53b7c1a4bac4736cb24628fb568a7102ba931a28c799e2e72f109893':
            raise ValueError('Unadmitted checkpoint')
        sys.path.insert(0,str(args.source.resolve(strict=True)))
        import numpy as np
        import torch
        import onnx
        import nemo
        from a1_service import NemoStreamingASRService
        from export_a1 import configure_encoder_export
        if not Path(nemo.__file__).resolve().is_relative_to(args.source.resolve()):raise ValueError('Wrong NeMo source')
        torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(20260924)
        service=NemoStreamingASRService(model=str(args.model),device='cpu',att_context_size=[70,1],use_amp=False,chunk_size_in_secs=.08)
        processor=service._audio_buffer.preprocessor
        result['original_feature_processor_training']=processor.training
        processor.eval()
        f=processor.featurizer
        config=dict(model_sha256=model_hash,context=[70,1],chunk_samples=1280,
            streaming=asdict(service.asr_model.encoder.streaming_cfg),
            vocabulary=service.tokenizer.ids_to_tokens(list(range(service.blank_id))),
            original_service_feature_processor_training=result['original_feature_processor_training'],
            frontend_inference_policy='eval; no random training-mode dither or augmentation',
            frontend=dict(sample_rate=16000,features=128,n_fft=f.n_fft,hop_length=f.hop_length,
                win_length=f.win_length,normalize=f.normalize,pad_to=f.pad_to,frame_splicing=f.frame_splicing,
                log=f.log,log_zero_guard_type=f.log_zero_guard_type,log_zero_guard_value=f.log_zero_guard_value,
                preemph=f.preemph,mag_power=f.mag_power,exact_pad=f.exact_pad,use_grads=f.use_grads))
        if (config['streaming']['cache_drop_size'],config['streaming']['valid_out_len'])!=(1,1):
            raise ValueError('Actual service geometry differs')
        model=service.asr_model;model.set_export_config({'cache_support':True})
        result['metadata_repair']=configure_encoder_export(model.encoder)
        result['streaming_before_export']=asdict(model.encoder.streaming_cfg)
        result['training_before_export']=[n for n,m in model.named_modules() if m.training]
        # The blank embedding must implement NeMo predict(None)'s zero input.
        blank_embedding=model.decoder.prediction['embed'].weight[service.blank_id]
        if torch.count_nonzero(blank_embedding).item()!=0:raise ValueError('Blank embedding is not exact zero')
        model.export(str(args.output/'service.onnx'),onnx_opset_version=17,check_trace=True)
        result['streaming_after_export']=asdict(model.encoder.streaming_cfg)
        result['training_after_export']=[n for n,m in model.named_modules() if m.training]
        graphs=sorted(args.output.glob('*.onnx'))
        if {p.name for p in graphs}!={'encoder-service.onnx','decoder_joint-service.onnx'}:
            raise ValueError('Unexpected exported graphs')
        for graph in graphs:onnx.checker.check_model(onnx.load(str(graph)))
        np.savez(args.output/'frontend_buffers.npz',window=f.window.detach().cpu().numpy(),filterbank=f.fb.detach().cpu().numpy())
        (args.output/'service_config.json').write_text(json.dumps(config,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        manifest=dict(schema='n3-a1-onnx-service-bundle-v1',status='EXPORTED_NOT_QUALIFIED',
            files=[binding(p) for p in [*graphs,args.output/'frontend_buffers.npz',args.output/'service_config.json']],
            dependencies=['NumPy','SciPy','ONNX Runtime CPU'],no_nemo_or_torch_runtime_dependency=True,
            provenance='Exact pinned NeMo model export; Apache-2.0 service scheduling; model NVIDIA Open Model License',
            inference_policy=config['frontend_inference_policy'])
        (args.output/'BUNDLE.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        result.update(status='EXPORTED_SERVICE_BUNDLE_NOT_QUALIFIED',bundle=binding(args.output/'BUNDLE.json'),
            remaining=['Fresh reference frontend/encoder/decoder/cache/EOU and saved-audio parity',
                'Deterministic A1 screen/regression/paced comparisons and integrated Controller',
                'ARM64 and target hardware qualification'])
    except Exception as exc:
        result.update(status='EXPORT_FAILED',error=repr(exc))
        (args.output/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        (args.output/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('status','error','original_feature_processor_training')}))


if __name__=='__main__':main()
