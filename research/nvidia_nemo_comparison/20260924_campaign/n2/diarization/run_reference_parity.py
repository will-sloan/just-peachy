"""Replay causal NeMo V3 streaming steps and compare against saved native Q8 probabilities."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import shutil

for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['WANDB_MODE'] = 'disabled'
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / 'prototype/vendor'))
import numpy as np
import soundfile as sf
import psutil
import torch
from edge_speech_pipeline.nemotron_diarization import PROFILES


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reference_stream(model, audio, profile):
    """Features use only arrived prefixes; native model cache survives each step.

    Recomputing the arrived waveform prefix is an evaluator implementation,
    intentionally measured and not advertised as a deployable reference frontend.
    No full-file model forward or model.diarize call is used.
    """
    sm = model.sortformer_modules
    sm.chunk_len, sm.chunk_right_context, sm.chunk_left_context = profile.chunk_frames, profile.right_context_frames, 0
    sm.fifo_len = sm.spkcache_len = 264
    sm.spkcache_update_period = 222
    model.async_streaming = False
    model._check_streaming_parameters()
    model.preprocessor.featurizer.dither = 0.0
    state = sm.init_streaming_state(batch_size=1, async_streaming=False, device=torch.device('cpu'))
    total = torch.zeros((1, 0, 8))
    consumed = 0
    events = []
    hop, look = profile.chunk_frames*8, profile.right_context_frames*8
    start, cpu = time.perf_counter(), time.process_time()
    peak = psutil.Process().memory_info().rss

    def advance(received, final):
        nonlocal state, total, consumed, peak
        valid_complete = max(0, (received-256)//160+1) if not final else received//160
        if not final and consumed + hop + look > valid_complete:
            return
        signal = torch.from_numpy(audio[:received].copy())[None]
        mel, lengths = model.preprocessor(input_signal=signal, length=torch.tensor([received]))
        valid = min(valid_complete, int(lengths[0]))
        while consumed < valid and (final or consumed+hop+look <= valid):
            end = min(consumed+hop, valid)
            rc = min(look, valid-end)
            chunk = mel[:, :, consumed:end+rc].transpose(1,2)
            before = total.shape[1]
            state, total = model.forward_streaming_step(
                processed_signal=chunk, processed_signal_length=torch.tensor([chunk.shape[1]]),
                streaming_state=state, total_preds=total, left_offset=0, right_offset=rc)
            # The official feature loader and model forward truncate the final
            # upsampled group to its true feature support. Do the same per step.
            total = total[:, :before+end-consumed]
            events.append({'frame_start': before, 'frame_end': total.shape[1],
                           'audio_received_sec': received/16000,
                           'available_at_elapsed_sec': time.perf_counter()-start, 'is_final': final,
                           'speaker_cache_frames': state.spkcache.shape[1], 'fifo_frames': state.fifo.shape[1]})
            consumed = end
            peak = max(peak, psutil.Process().memory_info().rss)

    with torch.inference_mode():
        for received in range(1600, len(audio)+1600, 1600):
            advance(min(received,len(audio)), False)
        advance(len(audio), True)
    return total[0].cpu().numpy(), events, {'wall_sec': time.perf_counter()-start, 'process_cpu_sec': time.process_time()-cpu,
                                           'sampled_peak_rss_bytes': peak, 'cpu_threads': 1,
                                           'frontend': 'recomputed_arrived_prefix_only_no_future', 'pacing': 'accelerated_causal_delivery'}


def comparison(native, reference):
    count = min(len(native), len(reference))
    a, b = native[:count], reference[:count]
    active_a, active_b = a>=.5, b>=.5
    differences = np.abs(a-b)
    boundary_errors = []
    segment_counts = {'native': [], 'reference': []}
    for slot in range(8):
        for activity, key in ((active_a, 'native'), (active_b, 'reference')):
            segment_counts[key].append(int(np.sum(np.diff(np.r_[False,activity[:,slot],False].astype(int))==1)))
        for edge_value in (-1,1):
            da = np.flatnonzero(np.diff(np.r_[False,active_a[:,slot],False].astype(int))==edge_value)
            db = np.flatnonzero(np.diff(np.r_[False,active_b[:,slot],False].astype(int))==edge_value)
            if len(da) and len(db):
                boundary_errors.extend((np.min(np.abs(da[:,None]-db[None,:]),axis=1)*.01).tolist())
    speech_union = active_a.any(axis=1) | active_b.any(axis=1)
    return {'compared_frames': count, 'native_frames': len(native), 'reference_frames': len(reference),
            'native_unpaired_tail_frames': len(native)-count, 'reference_unpaired_tail_frames': len(reference)-count,
            'activity_threshold': .5, 'threshold_calibrated': False,
            'mean_absolute_probability_error': float(differences.mean()),
            'max_absolute_probability_error': float(differences.max()),
            'p99_absolute_probability_error': float(np.quantile(differences,.99)),
            'activity_bit_disagreement_fraction': float(np.mean(active_a != active_b)),
            'frame_active_set_disagreement_fraction': float(np.mean(np.any(active_a != active_b, axis=1))),
            'speech_presence_disagreement_sec': float(np.sum(active_a.any(axis=1)!=active_b.any(axis=1))*.01),
            'overlap_presence_disagreement_sec': float(np.sum((active_a.sum(axis=1)>1)!=(active_b.sum(axis=1)>1))*.01),
            'dominant_slot_agreement_on_union_speech': float(np.mean(a[speech_union].argmax(axis=1)==b[speech_union].argmax(axis=1))) if speech_union.any() else None,
            'speaker_active_seconds_native': (active_a.sum(axis=0)*.01).tolist(),
            'speaker_active_seconds_reference': (active_b.sum(axis=0)*.01).tolist(),
            'threshold_segment_counts': segment_counts,
            'native_to_nearest_same_slot_same_edge_boundary_error_sec': {
                'count': len(boundary_errors), 'median': float(np.median(boundary_errors)) if boundary_errors else None,
                'max': max(boundary_errors) if boundary_errors else None},
            'scope': 'route comparison, not DER/JER or gold-reference efficacy; no slot remapping, no time shift, no bit-equality requirement'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-panel', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--receipt-name', default='REFERENCE_PARITY_RECEIPT.json')
    args = ap.parse_args()
    if Path(args.receipt_name).name != args.receipt_name or not args.receipt_name.endswith('.json'):
        raise ValueError('receipt-name must be a JSON basename')
    if args.output.exists():
        raise RuntimeError('Use a new output directory to preserve previous evidence')
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output/'run_reference_parity.source.py')
    if os.name == 'nt':
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    native_receipt_path = args.native_panel/'RECEIPT.json'
    native = json.loads(native_receipt_path.read_text())
    artifact = json.loads((HERE/'REFERENCE_ARTIFACT_RECEIPT.json').read_text())
    if sha(artifact['path']) != artifact['sha256']:
        raise RuntimeError('Reference checkpoint hash mismatch')
    audio_path = native['audio_job']['audio_path']
    if sha(audio_path) != native['audio_job']['audio_sha256']:
        raise RuntimeError('Paired audio hash mismatch')
    audio, sr = sf.read(audio_path, dtype='float32')
    if sr != 16000 or audio.ndim != 1:
        raise RuntimeError('Wrong waveform geometry')
    import nemo
    from nemo.collections.asr.models import SortformerEncLabelModel
    model = SortformerEncLabelModel.restore_from(artifact['path'], map_location='cpu', strict=True).eval()
    if not model.high_resolution or model.output_subsampling_factor != 1 or model.sortformer_modules.n_spk != 8:
        raise RuntimeError('Reference model is not eight-channel high-resolution Nemotron 3')
    import inspect
    model_source = Path(inspect.getfile(SortformerEncLabelModel))
    result = {'status': 'RUNNING', 'source_revision': 'cf724ac337d1ebc7d0dda1e23fb80916f52927a5',
              'python': sys.version, 'torch': torch.__version__, 'nemo': nemo.__version__,
              'model_class_source_path': str(model_source), 'model_class_source_sha256': sha(model_source),
              'model_sha256': artifact['sha256'], 'native_panel_sha256': sha(native_receipt_path),
              'script_sha256': sha(__file__), 'profiles': {}, 'gpu': False, 'dither': 0,
              'precision': 'NeMo-FP32-from-official-checkpoint',
              'tail_note': 'Native emits one centered-STFT endpoint frame more than NeMo valid length for the bound exact-second input. Compare common support, retain and report both unmodified tails.'}
    for name, entry in native['profiles'].items():
        if sha(entry['probability_file']) != entry['probability_sha256']:
            raise RuntimeError('Native probability evidence hash mismatch')
        native_probs = np.load(entry['probability_file'])['probabilities']
        sample_count = int(np.load(entry['probability_file'])['audio_samples'])
        probs, events, resources = reference_stream(model, audio[:sample_count], PROFILES[name])
        file = args.output/(name+'.npz')
        np.savez_compressed(file, probabilities=probs)
        result['profiles'][name] = {'metrics': comparison(native_probs,probs), 'resources': resources,
                                   'probability_path': str(file), 'probability_sha256': sha(file), 'events': events}
        (args.output/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
        print(name, json.dumps(result['profiles'][name]['metrics']), flush=True)
    result['status'] = 'ACTUALLY_RUN'
    (args.output/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
    summary = dict(result)
    summary['profiles'] = {key:{k:v for k,v in value.items() if k!='events'} for key,value in result['profiles'].items()}
    summary.update(local_receipt=str(args.output/'RECEIPT.json'), local_receipt_sha256=sha(args.output/'RECEIPT.json'))
    (HERE/args.receipt_name).write_text(json.dumps(summary,indent=2)+'\n')

if __name__ == '__main__':
    main()
