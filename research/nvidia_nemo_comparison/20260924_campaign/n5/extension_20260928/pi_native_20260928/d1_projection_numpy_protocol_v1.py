"""One FP32 CPU projection kernel alternative; README_D1_PROJECTION_NUMPY_V1.md."""
import contextlib
import io
import json
import time
from pathlib import Path


def run(root, admission):
    import numpy as np
    weights=np.load(root/'projection_weight.npy',allow_pickle=False)
    assert weights.dtype==np.float32 and weights.shape==(512,1024) and weights.flags.c_contiguous
    original_weights=weights.tobytes()
    config=io.StringIO()
    with contextlib.redirect_stdout(config):np.show_config()
    with (root/'NUMPY_CONFIG.txt').open('x') as f:f.write(config.getvalue())
    cases=[];began=time.monotonic()
    for name in ['tail','full_first','full_middle','full_tail']:
        with np.load(Path(admission['reference_directory'])/(name+'.npz'),allow_pickle=False) as z:
            stack=z['stack'].copy();lengths=z['lengths'].copy()
            assert stack.dtype==np.float32 and stack.ndim==3 and stack.shape[0]==1 and stack.shape[-1]==1024
            before=stack.tobytes();first=None
            for repeat in range(2):
                t=time.monotonic()
                # Exactly one alternative: FP32 NumPy CPU matmul, original weights/order.
                embedding=(stack.reshape(-1,1024) @ weights.T).reshape(1,stack.shape[1],512)
                seconds=time.monotonic()-t
                assert embedding.dtype==np.float32 and np.isfinite(embedding).all()
                assert stack.tobytes()==before and weights.tobytes()==original_weights
                assert embedding.shape==z['pytorch'].shape
                if first is None:first=embedding.copy()
                else:assert np.array_equal(first,embedding)
                delta=float(np.max(np.abs(embedding.astype(np.float64)-z['pytorch'])))
                old_delta=float(np.max(np.abs(embedding.astype(np.float64)-z['basic'])))
                exact_delta=float(np.max(np.abs(embedding.astype(np.float64)-z['float64_accumulation'])))
                np.savez(root/(name+'-native-'+str(repeat)+'.npz'),embedding=embedding,lengths=lengths,stack=stack)
                cases.append(dict(case=name,repeat=repeat,seconds=seconds,reference_maxabs=delta,
                                  host_ort_maxabs=old_delta,float64_diagnostic_maxabs=exact_delta,
                                  within_unchanged_gate=delta<=admission['absolute_tolerance'],
                                  inputs_unchanged=True,repeat_exact=True,stack_exact=True,lengths_exact=True))
    return dict(status='NATIVE_NUMPY_PROJECTION_OBSERVATIONS_REVIEW_REQUIRED',cases=cases,
                absolute_tolerance=admission['absolute_tolerance'],numpy_version=np.__version__,
                all_reference_cases_within_gate=all(c['within_unchanged_gate'] for c in cases),
                kernel='numpy_float32_matmul_original_weight_transpose',kernel_protocol_seconds=time.monotonic()-began,
                gate_relaxed=False,full_waveform_qualified=False,speedup_qualified=False)
