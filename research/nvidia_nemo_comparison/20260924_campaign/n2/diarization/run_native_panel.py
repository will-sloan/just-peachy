"""Run hash-bound native streaming probability and arrival-time evidence on saved audio."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import shutil
import subprocess

os.environ['OMP_NUM_THREADS'] = os.environ['OPENBLAS_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '1'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'prototype/vendor'))
import numpy as np
import soundfile as sf
import psutil
from edge_speech_pipeline.nemotron_diarization import NemotronDiarizer, PROFILES


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run_audio(model, audio, block_samples=1600, paced=False):
    events, probabilities = [], []
    started, cpu_start = time.perf_counter(), time.process_time()
    process = psutil.Process()
    peak = 0
    for offset in range(0, len(audio), block_samples):
        end = min(len(audio), offset+block_samples)
        if paced:
            delay = started + end/16000 - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
        update = model.push(audio[offset:end])
        peak = max(peak, process.memory_info().rss)
        if update.probabilities.size:
            probabilities.append(update.probabilities)
            events.append({'frame_start': update.frame_start, 'frame_end': update.frame_end,
                           'audio_received_sec': update.audio_received_sec,
                           'received_at_elapsed_sec': update.received_at_monotonic-started,
                           'available_at_elapsed_sec': update.available_at_monotonic-started,
                           'compute_sec': update.compute_sec, 'is_final': False})
    final = model.finish()
    probabilities.append(final.probabilities)
    events.append({'frame_start': final.frame_start, 'frame_end': final.frame_end,
                   'audio_received_sec': final.audio_received_sec,
                   'received_at_elapsed_sec': final.received_at_monotonic-started,
                   'available_at_elapsed_sec': final.available_at_monotonic-started,
                   'compute_sec': final.compute_sec, 'is_final': True})
    values = np.concatenate(probabilities, axis=0) if probabilities else np.empty((0,8), np.float32)
    return values, events, {'wall_sec': time.perf_counter()-started, 'process_cpu_sec': time.process_time()-cpu_start,
                           'sampled_peak_rss_bytes': max(peak, process.memory_info().rss),
                           'windows_peak_working_set_bytes': getattr(process.memory_info(), 'peak_wset', None),
                           'pacing': 'source_speed' if paced else 'accelerated_causal_file_delivery',
                           'block_samples': block_samples, 'audio_sec': len(audio)/16000}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--seconds', type=float, default=12)
    ap.add_argument('--job-index', type=int, default=0)
    ap.add_argument('--profiles', nargs='+', default=list(PROFILES), choices=list(PROFILES))
    ap.add_argument('--paced', action='store_true')
    ap.add_argument('--functional', action='store_true')
    ap.add_argument('--receipt-name', help='distinct redacted receipt basename, ending in .json')
    ap.add_argument('--build-receipt', type=Path, default=HERE/'NATIVE_BUILD_RECEIPT.json')
    ap.add_argument('--device', choices=('cpu','cuda'), default='cpu')
    ap.add_argument('--gpu-index', type=int, default=0, help='Explicit CUDA index; ignored for CPU')
    ap.add_argument('--cpu-reference', type=Path, help='Previously completed matching CPU panel directory')
    args = ap.parse_args()
    if args.gpu_index < 0:
        ap.error('GPU index must be nonnegative')
    args.gpu = args.gpu_index if args.device=='cuda' else -1
    if args.receipt_name and (Path(args.receipt_name).name != args.receipt_name or not args.receipt_name.endswith('.json')):
        raise ValueError('receipt-name must be a JSON basename')
    if args.output.exists():
        raise RuntimeError('Use a fresh output directory to preserve evidence')
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output/'run_native_panel.source.py')
    shutil.copyfile(ROOT/'prototype/vendor/edge_speech_pipeline/nemotron_diarization.py', args.output/'nemotron_diarization.source.py')
    process = psutil.Process()
    if os.name == 'nt':
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    campaign = HERE.parents[1]
    build = json.loads(args.build_receipt.read_text())
    if args.gpu < -1 or (args.gpu >= 0 and not build['gpu']):
        raise ValueError('An explicit GPU device requires an admitted CUDA build')
    for item in build['runtime_files']:
        if sha(item['path']) != item['sha256']:
            raise ValueError('Native runtime dependency hash mismatch')
    artifact = next(x for x in json.loads((campaign/'assets/model_manifest.json').read_text())['models'] if x['id']=='D1')['download']
    manifest_path = Path('G:/Just_Peachy_N1/20260924_campaign/local/data/BASELINE_SCREEN_AUDIO_ONLY.json')
    audio_manifest = json.loads(manifest_path.read_text())
    job = audio_manifest['jobs'][args.job_index]
    if job['gain'] != 1 or sha(job['audio_path']) != job['audio_sha256']:
        raise RuntimeError('Saved audio admission mismatch')
    audio, sr = sf.read(job['audio_path'], dtype='float32')
    if audio.ndim != 1 or sr != 16000 or len(audio) != job['frames']:
        raise RuntimeError('Saved audio header mismatch')
    if args.seconds > 0:
        audio = audio[:round(args.seconds * sr)]
    cpu_reference = json.loads((args.cpu_reference/'RECEIPT.json').read_text()) if args.cpu_reference else None
    if cpu_reference and cpu_reference['audio_job'] != job:
        raise ValueError('CPU reference audio job mismatch')
    def gpu_snapshot():
        if args.gpu < 0:
            return None
        executable = shutil.which('nvidia-smi')
        if not executable:
            return {'status':'UNAVAILABLE','scope':'global device, not process VRAM'}
        query = subprocess.run([executable,'-i',str(args.gpu),
            '--query-gpu=index,name,uuid,driver_version,memory.total,memory.used,utilization.gpu',
            '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
        return {'status':'ACTUALLY_QUERIED','returncode':query.returncode,'csv':query.stdout.strip(),
                'scope':'global device snapshot; desktop allocations included, not process-isolated peak VRAM'}
    result = {'status': 'RUNNING', 'audio_job': job, 'audio_manifest_sha256': sha(manifest_path),
              'source_sha256': sha(ROOT/'prototype/vendor/edge_speech_pipeline/nemotron_diarization.py'),
              'runner_sha256': sha(__file__), 'profiles': {}, 'functional': {},
              'cpu_threads': 1, 'priority': 'BELOW_NORMAL', 'gpu': args.gpu>=0,'gpu_device':args.gpu,
              'native_device':{'kind':args.device,'gpu_index':args.gpu},
              'build_receipt':str(args.build_receipt),'build_receipt_sha256':sha(args.build_receipt),
              'native_runtime_files':build['runtime_files'],
              'cpu_reference_receipt_sha256':sha(args.cpu_reference/'RECEIPT.json') if args.cpu_reference else None,
              'probabilities_are_activity_not_identity': True, 'new_acoustic_bank_generated': False}
    for profile in args.profiles:
        with NemotronDiarizer(artifact['path'], build['library_path'], profile=profile,
                             expected_library_sha256=build['library_sha256'], session_id='panel-'+profile,gpu=args.gpu) as model:
            device_before = gpu_snapshot()
            probs, events, resource = run_audio(model, audio, paced=args.paced)
            if probs.shape != (len(audio)//160+1,8) or not np.isfinite(probs).all():
                raise RuntimeError('Native panel shape/finiteness contract failed')
            device_after = gpu_snapshot()
            file = args.output / (profile+'.npz')
            np.savez_compressed(file, probabilities=probs, sample_rate=np.array(sr), audio_samples=np.array(len(audio)))
            record = {'manifest': model.manifest(), 'events': events, 'resources': resource,
                      'probability_file': str(file), 'probability_sha256': sha(file),
                      'shape': list(probs.shape), 'finite': bool(np.all(np.isfinite(probs))),
                      'gpu_snapshot_before':device_before,'gpu_snapshot_after':device_after,
                      'frames_with_overlap_at_0_5': int(np.sum((probs>=.5).sum(axis=1)>1)),
                      'slots_with_activity_at_0_5': np.flatnonzero(np.any(probs>=.5, axis=0)).tolist()}
            result['profiles'][profile] = record
            if cpu_reference:
                cpu_entry = cpu_reference['profiles'][profile]
                if sha(cpu_entry['probability_file']) != cpu_entry['probability_sha256']:
                    raise ValueError('CPU reference probability hash mismatch')
                data = np.load(cpu_entry['probability_file'])
                reference = data['probabilities']
                if int(data['audio_samples']) != len(audio) or reference.shape != probs.shape:
                    raise ValueError('CPU/CUDA input support or probability shape differs')
                delta = np.abs(reference-probs)
                a,b = reference>=.5,probs>=.5
                boundary_errors=[]
                for slot in range(8):
                    for sign in (-1,1):
                        ae=np.flatnonzero(np.diff(np.r_[False,a[:,slot],False].astype(int))==sign)
                        be=np.flatnonzero(np.diff(np.r_[False,b[:,slot],False].astype(int))==sign)
                        if len(ae) and len(be):
                            boundary_errors.extend((np.min(np.abs(be[:,None]-ae[None,:]),axis=1)*.01).tolist())
                record['cpu_comparison']={'reference_probability_sha256':cpu_entry['probability_sha256'],
                    'same_shape':True,'compared_frames':len(probs),'mean_absolute_probability_error':float(delta.mean()),
                    'max_absolute_probability_error':float(delta.max()),'activity_threshold':.5,
                    'frame_active_set_disagreements':int(np.sum(np.any(a!=b,axis=1))),
                    'overlap_disagreement_sec':float(np.sum((a.sum(axis=1)>1)!=(b.sum(axis=1)>1))*.01),
                    'nearest_same_slot_boundary_max_sec':max(boundary_errors) if boundary_errors else None,
                    'scope':'CPU versus explicit CUDA route; no time shifts, no slot mapping, no gold quality score'}
            (args.output/'RECEIPT.json').write_text(json.dumps(result, indent=2)+'\n')
            print(profile, 'frames', len(probs), 'wall', round(resource['wall_sec'],3), flush=True)
            if args.functional:
                checks = {}
                model.reset(session_id='empty')
                checks['empty_push_frames'] = len(model.push(np.array([],np.float32)).probabilities)
                checks['empty_finish_frames'] = len(model.finish().probabilities)
                checks['repeat_finish_frames'] = len(model.finish().probabilities)
                try:
                    model.push(np.zeros(1,np.float32))
                    checks['post_finish_rejected'] = False
                except RuntimeError:
                    checks['post_finish_rejected'] = True
                model.reset(session_id='constant')
                const, _, _ = run_audio(model, np.full(25600,.01,np.float32))
                checks['constant_finite'] = bool(np.isfinite(const).all())
                checks['constant_shape'] = list(const.shape)
                np.savez_compressed(args.output/(profile+'_constant.npz'), probabilities=const)
                comparison = []
                for block in (1600, 997):
                    model.reset(session_id='chunk-invariance')
                    candidate, _, _ = run_audio(model, audio[:48000], block_samples=block)
                    comparison.append(candidate)
                checks['partition_shape_equal'] = comparison[0].shape == comparison[1].shape
                checks['partition_max_abs_error'] = float(np.max(np.abs(comparison[0]-comparison[1])))
                checks['reset_repeats_same_slots'] = model.track_ids == tuple(f'chunk-invariance:nemotron-slot-{i}' for i in range(8))
                checks['pass'] = (checks['empty_push_frames']==checks['empty_finish_frames']==checks['repeat_finish_frames']==0
                                  and checks['post_finish_rejected'] and checks['constant_finite']
                                  and checks['partition_shape_equal'] and checks['partition_max_abs_error'] <= 1e-5)
                result['functional'][profile] = checks
    if args.gpu>=0 and cpu_reference:
        cpu_manifest=cpu_reference['profiles'][args.profiles[0]]['manifest']
        try:
            forbidden=NemotronDiarizer(artifact['path'],cpu_manifest['library_path'],
                expected_library_sha256=cpu_manifest['library_sha256'])
        except RuntimeError as exc:
            if not str(exc).startswith('This process already selected native runtime directory'):
                raise
            result['functional']['runtime_directory_guard']={'different_runtime_after_close_rejected':True,
                'same_directory_three_profile_loads_completed':len(result['profiles'])==3,'pass':True}
        else:
            forbidden.close()
            raise AssertionError('Runtime directory switch was not rejected')
    result['status'] = 'ACTUALLY_RUN' if all(c['pass'] for c in result['functional'].values()) else 'FAILED_FUNCTIONAL'
    (args.output/'RECEIPT.json').write_text(json.dumps(result, indent=2)+'\n')
    summary = {'status': result['status'], 'local_receipt': str(args.output/'RECEIPT.json'),
               'local_receipt_sha256': sha(args.output/'RECEIPT.json'), 'functional': result['functional'],
               'source_sha256': result['source_sha256'],
               'gpu':result['gpu'],'gpu_device':args.gpu,'build_receipt_sha256':result['build_receipt_sha256'],
               'native_runtime_files':build['runtime_files'],
               'profiles': {key: {k:v for k,v in value.items() if k!='events'} for key,value in result['profiles'].items()}}
    (HERE/(args.receipt_name or ('NATIVE_PACED_RECEIPT.json' if args.paced else 'NATIVE_PANEL_RECEIPT.json'))).write_text(json.dumps(summary, indent=2)+'\n')

if __name__ == '__main__':
    main()
