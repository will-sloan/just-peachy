"""Attempt official stateful A1 ONNX export and test dynamic recurrent inputs."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
import inspect

for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='1'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def configure_encoder_export(encoder):
    """Remove an optional port absent from the pinned export forward signature."""
    expected = ['audio_signal', 'length', 'cache_last_channel', 'cache_last_time', 'cache_last_channel_len']
    if list(inspect.signature(encoder.forward_for_export).parameters) != expected:
        raise ValueError('Unexpected encoder export signature; review the pinned source')
    if set(encoder.input_names) != set(expected + ['bypass_pre_encode']):
        raise ValueError('Unexpected encoder export ports; do not silently filter inputs')
    class EncoderExportPorts(type(encoder)):
        @property
        def disabled_deployment_input_names(self):
            return set(super().disabled_deployment_input_names) | {'bypass_pre_encode'}
    encoder.__class__ = EncoderExportPorts
    if encoder.input_names != expected:
        raise ValueError('Encoder input order differs from export forward')
    return dict(excluded_port='bypass_pre_encode', reason='absent from forward_for_export and input_example',
                scope='export instance metadata only; pinned NeMo source and model math unchanged')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cpu',type=int,default=4,choices=[4,14])
    args=p.parse_args()
    if args.output.exists():raise ValueError('Preserve prior export evidence; use a fresh directory')
    args.output.mkdir(parents=True)
    result=dict(schema='just-peachy.n3.a1-export.v1',status='RUNNING',
        source_model_sha256=sha(args.model),portable_streaming_qualified=False,
        started_utc=datetime.now(timezone.utc).isoformat(),checks=[],files=[])
    try:
        if result['source_model_sha256']!='6603a22a53b7c1a4bac4736cb24628fb568a7102ba931a28c799e2e72f109893':
            raise ValueError('Unadmitted A1 checkpoint')
        sys.path.insert(0,str(args.source.resolve(strict=True)))
        import psutil
        process=psutil.Process();process.cpu_affinity([args.cpu])
        if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        import numpy as np
        import torch
        import onnx
        import onnxruntime as ort
        from omegaconf import OmegaConf
        from nemo.collections.asr.models import EncDecRNNTBPEModel
        import nemo
        if not Path(nemo.__file__).resolve().is_relative_to(args.source.resolve()):raise ValueError('Wrong NeMo source imported')
        torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(20260924)
        model=EncDecRNNTBPEModel.restore_from(str(args.model),map_location=torch.device('cpu')).eval()
        model.encoder.set_default_att_context_size([70,1])
        model.set_export_config({'cache_support':True})
        result['export_metadata_repair'] = configure_encoder_export(model.encoder)
        model.export(str(args.output/'a1.onnx'),onnx_opset_version=17,check_trace=True)
        graphs=list(args.output.glob('*.onnx'))
        if len(graphs)!=2:raise RuntimeError('Expected separate streaming encoder and decoder/joint graphs')
        for path in graphs:
            graph=onnx.load(str(path));onnx.checker.check_model(graph)
            result['files'].append(dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size,
                inputs=[dict(name=x.name,shape=[d.dim_param or d.dim_value for d in x.type.tensor_type.shape.dim]) for x in graph.graph.input],
                outputs=[x.name for x in graph.graph.output]))
        encoder_path=next(p for p in graphs if p.name.startswith('encoder'))
        options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        session=ort.InferenceSession(str(encoder_path),sess_options=options,providers=['CPUExecutionProvider'])
        names=[x.name for x in session.get_inputs()]
        expected=['audio_signal','length','cache_last_channel','cache_last_time','cache_last_channel_len']
        if names!=expected:raise RuntimeError('Stateful encoder cache input contract was not exported')
        output_names=[x.name for x in session.get_outputs()]
        if len(output_names)!=5:raise RuntimeError('Encoder did not expose all next-cache outputs')
        for batch in (1,2):
            example=model.encoder.input_example(max_batch=batch)
            base_width=example[0].shape[-1]
            caches=[x.clone() for x in example[2:]]
            for step,width in enumerate((base_width,base_width+8,base_width)):
                signal=torch.randn(batch,128,width)
                length=torch.full((batch,),width,dtype=torch.int64)
                inputs=(signal,length,*caches)
                with torch.no_grad():reference=model.encoder.forward_for_export(*inputs)
                actual=session.run(None,{name:value.numpy() for name,value in zip(names,inputs)})
                errors=[]
                for output,ref in zip(actual,reference):
                    gold=ref.detach().numpy()
                    if gold.dtype.kind in 'iu':np.testing.assert_array_equal(output,gold)
                    else:np.testing.assert_allclose(output,gold,rtol=2e-4,atol=2e-4)
                    errors.append(float(np.max(np.abs(output-gold))) if output.size else 0.)
                caches=[torch.from_numpy(x.copy()) for x in actual[2:]]
                result['checks'].append(dict(batch=batch,step=step,feature_frames=width,
                    nonzero_recurrent_state=step>0,maximum_absolute_errors=errors,status='PASS'))
        processor=model.preprocessor.featurizer
        np.savez(args.output/'frontend_buffers.npz',window=processor.window.detach().cpu().numpy(),
            filterbank=processor.fb.detach().cpu().numpy())
        (args.output/'model_config.json').write_text(json.dumps(OmegaConf.to_container(model.cfg,resolve=True),indent=2,default=str)+'\n',encoding='utf-8')
        result.update(status='EXPORTED_ENCODER_DYNAMIC_STATE_PARITY_PASSED',
            decoder_joint_status='EXPORTED_AND_ONNX_CHECKED_NOT_YET_STREAM_PARITY_QUALIFIED',
            remaining=['portable feature-cache/decoder rollout parity including EOU and real saved audio',
                       'ARM64 execution and target RAM/latency not tested'])
    except Exception as exc:
        result.update(status='EXPORT_OR_STATE_PARITY_FAILED',error=f'{type(exc).__name__}: {exc}',
            remaining=['A1 reference path remains independently testable; no offline Parakeet substitution'])
        (args.output/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        result['updated_utc']=datetime.now(timezone.utc).isoformat()
        (args.output/'EXPORT_RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(result['status'],flush=True)


if __name__=='__main__':main()
