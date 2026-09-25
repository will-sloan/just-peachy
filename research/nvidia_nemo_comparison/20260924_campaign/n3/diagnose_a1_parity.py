"""Inspect the preserved A1 graph against fresh common inputs; README_A1_DIAGNOSTIC.md."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def fresh_feed(names, tensors):
    """Capture inputs before either implementation can mutate shared storage."""
    if len(names) != len(tensors) or len(set(names)) != len(names):
        raise ValueError('Every graph input needs one uniquely named tensor')
    return {name: value.detach().cpu().numpy().copy() for name, value in zip(names, tensors)}


def compare_arrays(actual, expected):
    import numpy as np
    rows = []
    if len(actual) != len(expected):
        raise ValueError('Output count differs')
    for index, (left, right) in enumerate(zip(actual, expected)):
        right = right.detach().cpu().numpy() if hasattr(right, 'detach') else right
        same_shape = left.shape == right.shape
        exact = bool(same_shape and np.array_equal(left, right))
        close = bool(same_shape and (exact if right.dtype.kind in 'iub' else np.allclose(left, right, rtol=2e-4, atol=2e-4)))
        finite = bool(np.all(np.isfinite(left)) and np.all(np.isfinite(right)))
        rows.append(dict(output=index, shape=list(left.shape), reference_shape=list(right.shape),
                         exact=exact, within_tolerance=close,
                         all_finite=finite,
                         maximum_absolute_error=float(np.max(np.abs(left-right))) if finite and same_shape and left.size else 0.0 if finite and same_shape else None))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent-plan', 'model', 'source', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve existing diagnostics; choose a fresh output')
    parent = load(args.parent_plan)
    result_path = Path(parent['output']) / 'RESULT.json'
    parent_result = load(result_path)
    if parent_result.get('status') != 'READY_FOR_REVIEW' or parent_result.get('plan_sha256') != sha(args.parent_plan):
        raise ValueError('Diagnostic requires the matching terminal parent queue')
    import psutil
    owner = parent_result['owner']
    try:
        if abs(psutil.Process(owner['pid']).create_time() - owner['create_time']) < .1:
            raise ValueError('Parent coordinator is still alive')
    except psutil.NoSuchProcess:
        pass
    process = psutil.Process()
    process.cpu_affinity([4])
    if os.name == 'nt':
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    args.output.mkdir(parents=True)
    result = dict(schema='n3-a1-parity-diagnostic-v1', status='RUNNING',
                  started_utc=datetime.now(timezone.utc).isoformat(), cases=[],
                  portable_streaming_qualified=False, parent_result_sha256=sha(result_path),
                  scope='Synthetic feature/cache protocol diagnostic, not new audio or ASR quality measurement')
    try:
        export_path = Path(parent['output']) / 'A1-export/EXPORT_RESULT.json'
        export = load(export_path)
        if sha(args.model) != export['source_model_sha256'] or export['source_model_sha256'] != '6603a22a53b7c1a4bac4736cb24628fb568a7102ba931a28c799e2e72f109893':
            raise ValueError('Pinned A1 model differs')
        graph = next(row for row in export['files'] if Path(row['path']).name == 'encoder-a1.onnx')
        if sha(graph['path']) != graph['sha256']:
            raise ValueError('Preserved encoder graph differs')
        result['graph'] = graph
        sys.path.insert(0, str(args.source.resolve(strict=True)))
        import numpy as np
        import torch
        import onnxruntime as ort
        from nemo.collections.asr.models import EncDecRNNTBPEModel
        import nemo
        if not Path(nemo.__file__).resolve().is_relative_to(args.source.resolve()):
            raise ValueError('Wrong NeMo source')
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.manual_seed(20260924)
        model = EncDecRNNTBPEModel.restore_from(str(args.model), map_location=torch.device('cpu')).eval()
        model.encoder.set_default_att_context_size([70, 1])
        model.set_export_config({'cache_support': True})
        encoder = model.encoder
        result['streaming_config'] = asdict(encoder.streaming_cfg)
        result['training_modules'] = [name for name, module in model.named_modules() if module.training]
        options = ort.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session = ort.InferenceSession(graph['path'], sess_options=options, providers=['CPUExecutionProvider'])
        names = [value.name for value in session.get_inputs()]
        expected_names = ['audio_signal', 'length', 'cache_last_channel', 'cache_last_time', 'cache_last_channel_len']
        if names != expected_names:
            raise ValueError('Unexpected encoder input contract')
        def check(label, inputs, **metadata):
            feed = fresh_feed(names, inputs)
            before = {name: hashlib.sha256(value.tobytes()).hexdigest() for name, value in feed.items()}
            # The independent reference gets disjoint storage, as does ORT.
            with torch.no_grad():
                reference = encoder.forward_for_export(*[x.clone() for x in inputs])
            with torch.inference_mode():
                inference_reference = encoder.forward_for_export(*[x.clone() for x in inputs])
            actual = session.run(None, feed)
            comparisons = compare_arrays(actual, reference)
            row = dict(case=label, **metadata, input_shapes={name:list(value.shape) for name,value in feed.items()},
                       input_sha256=before, outputs=comparisons,
                       reference_execution_modes=compare_arrays([x.detach().cpu().numpy() for x in inference_reference], reference),
                       pass_all_outputs=all(r['within_tolerance'] for r in comparisons),
                       input_storage_unchanged=before == {name:hashlib.sha256(value.tobytes()).hexdigest() for name,value in feed.items()})
            result['cases'].append(row)
            return [x.detach().clone() for x in reference[2:]]
        for batch in (1, 2):
            example = encoder.input_example(max_batch=batch)
            width = example[0].shape[-1]
            check('fresh_random_example', example, batch=batch, step=0)
            channel, time_cache, lengths = encoder.get_initial_cache_state(batch_size=batch)
            caches = [channel.transpose(0,1), time_cache.transpose(0,1), lengths]
            for step, frames in enumerate((width, width+8, width)):
                inputs = [torch.randn(batch,128,frames), torch.full((batch,),frames,dtype=torch.int64), *caches]
                caches = check('common_reference_cache_rollout', inputs, batch=batch, step=step,
                               cache_feedback='identical reference state supplied to both implementations')
        result.update(status='DIAGNOSTIC_COMPLETE',
                      all_cases_match=all(row['pass_all_outputs'] for row in result['cases']),
                      remaining=['Separate runtime defect versus test defect from these outputs',
                                 'No portable decoder/EOU/audio or ARM64 qualification is claimed'])
    except Exception as exc:
        result.update(status='DIAGNOSTIC_FAILED', error=f'{type(exc).__name__}: {exc}')
        (args.output/'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
    finally:
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (args.output/'RESULT.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({key:result.get(key) for key in ('status','all_cases_match','error')}))


if __name__ == '__main__':
    main()
