"""Strict full-bank D0 component review; see README_REVIEW_D0_BANK.md."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'

from common import audio_only, bind, fingerprint, freeze, load, verify
from d0_bank_components import cell_key, verify_contract
from review_d0_collection import validate_pair

TIMING_FIELDS = {'modeled_available_at_sec', 'compute_ms', 'model_api_elapsed_ms',
                 'postprocess_compute_ms', 'compute_finished_elapsed_sec'}
ARRAY_FIELDS = ('speech_frames', 'overlap_frames', 'speech_probability_frames',
                'overlap_probability_frames')


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Nonfinite or nonnumeric event value')
    return value


def terminal(final, admission_binding, expected=480):
    if (final['status'] != 'COLLECTED_REQUIRES_REVIEW' or final['completed'] != 2*expected
            or final['total'] != 2*expected or final['admission'] != admission_binding
            or final.get('child') is not None or final.get('integrated_N4_cells') != 0):
        raise ValueError('Terminal full-bank component census required')
    import psutil
    owner = final['owner']
    try:
        if psutil.Process(owner['pid']).create_time() == owner['create_time']:
            raise ValueError('Collection coordinator is still alive')
    except psutil.NoSuchProcess:
        pass


def exact_path(binding, expected):
    if Path(binding['path']).resolve() != Path(expected).resolve():
        raise ValueError('Evidence outside its expected cell path')
    verify(binding)


def check_index(index, progress, jobs, admission_sha):
    required = {job['job_id'] for job in jobs}
    if len(required) != len(jobs) or set(index['cells']) != required:
        raise ValueError('Missing, duplicate or extra full-bank cells')
    if (index['status'] != 'COMPLETE' or index['completed'] != len(jobs)
            or index['total'] != len(jobs) or index['cpu_affinity'] != [4]
            or index['one_native_model_thread'] is not True):
        raise ValueError('Incomplete encoder index or changed execution policy')
    if (progress['cells'] != index['cells'] or progress['admission_sha256'] != admission_sha
            or progress['total'] != len(jobs) or progress['completed'] != len(jobs)
            or progress['failed'] != 0):
        raise ValueError('Progress/terminal index disagreement')


def scan_events(cell, wave):
    """Verify complete gzip bytes, actual vector observations and causal census.

    Hash segmentation/admission semantics without compute times. Encoder timing
    and vector values may differ; masks, gates and exact admitted windows may not.
    This checks the frozen fixed-cadence v1 collector, not arbitrary lane schemas.
    """
    import numpy as np
    verify(cell['events'])
    expanded = hashlib.sha256(); semantic = hashlib.sha256(); size = 0
    counts = Counter(); rejections = Counter(); prior_source = prior_available = -1.
    pending = None; vector_index = 0; admissions = set(); segment_ends = []
    duration = cell['job']['frames']/16000
    with gzip.open(cell['events']['path'], 'rb') as stream:
        for raw in stream:
            expanded.update(raw); size += len(raw)
            event = json.loads(raw)
            kind = event['event_type']; p = event['payload']; counts[kind] += 1
            if kind not in ('research_segmentation', 'research_embedding_admission', 'research_embedding'):
                raise ValueError('Unexpected component event kind')
            source = finite(event['source_time_sec']); available = finite(p['modeled_available_at_sec'])
            if (source != p['source_end_sec'] or not prior_source <= source <= duration
                    or source <= 0 or available < source or available < prior_available):
                raise ValueError('Noncausal source/availability sequence')
            prior_source, prior_available = source, available
            if pending is not None and kind != 'research_embedding':
                raise ValueError('Admitted embedding observation is missing')
            if kind == 'research_segmentation':
                segment_ends.append(source)
                if (p['frame_step_sec'] != .016875 or p['frame_duration_sec'] != .0619375
                        or p['receptive_start_sec'] != max(0., source-10.)
                        or p['receptive_end_sec'] != source
                        or p['left_padding_sec'] != max(0., 10.-source)):
                    raise ValueError('Changed segmentation receptive geometry')
                arrays = [np.asarray(p[key], dtype=np.float64) for key in ARRAY_FIELDS]
                if (not len(arrays[0]) or any(a.ndim != 1 or a.shape != arrays[0].shape
                        or not np.isfinite(a).all() or np.any((a < 0) | (a > 1)) for a in arrays)
                        or any(not np.isin(a, [0, 1]).all() for a in arrays[:2])):
                    raise ValueError('Malformed full segmentation frames')
            elif kind == 'research_embedding_admission':
                role = p['evidence_kind']; key = (source, role)
                if role not in ('short', 'mature') or key in admissions:
                    raise ValueError('Invalid or duplicate embedding admission')
                admissions.add(key)
                if (p['cadence_policy'] != 'fixed' or p['naming_used_for_schedule'] is not False
                        or p['tracking_context_used'] is not False or p['cue_event'] is not False):
                    raise ValueError('Tracker/name/spatial-dependent window selection')
                if type(p['admitted']) is not bool or p['admitted'] != (p['reason'] == 'admitted'):
                    raise ValueError('Admission decision disagrees with reason')
                if p['admitted']:
                    pending = p
                else:
                    rejections[p['reason']] += 1
            else:
                if pending is None or vector_index >= len(cell['vectors']):
                    raise ValueError('Unbound embedding observation')
                diagnostic = p['admission']
                if any(pending.get(k) != v for k, v in diagnostic.items()):
                    raise ValueError('Embedding differs from preceding admission')
                first = round(finite(p['source_start_sec'])*16000); last = round(source*16000)
                expected = dict(start_sample=first, end_sample=last,
                    waveform_sha256=hashlib.sha256(wave[first:last].astype('<f4').tobytes()).hexdigest(),
                    evidence_kind=p['evidence_kind'], clean_intervals=p['clean_intervals'],
                    normalized_embedding=p['normalized_embedding'])
                if (not 0 <= first < last <= len(wave) or last-first != diagnostic['samples']
                        or expected != cell['vectors'][vector_index]
                        or p['available_at_sec'] != available
                        or p['evidence_event_id'] != f'embedding:{vector_index+1:08d}'):
                    raise ValueError('Vector observation/waveform differs from result')
                pending = None; vector_index += 1
            if kind != 'research_embedding':
                semantic.update(fingerprint(dict(event_type=kind, source_time_sec=source,
                    payload={k:v for k,v in p.items() if k not in TIMING_FIELDS})).encode('ascii'))
    if cell['events_expanded'] != dict(uncompressed_sha256=expanded.hexdigest(), uncompressed_bytes=size):
        raise ValueError('Expanded event bytes differ')
    required_admissions = {(i/4, role) for i in range(1, cell['job']['frames']//4000+1)
                           for role in ('short', 'mature')}
    if (pending is not None or vector_index != len(cell['vectors']) or admissions != required_admissions
            or segment_ends != [i/2 for i in range(1, cell['job']['frames']//8000+1)]
            or len(segment_ends) != cell['segmentation_calls']):
        raise ValueError('Incomplete dispatch, segmentation or vector census')
    return dict(events=dict(counts), rejection_reasons=dict(rejections),
                paired_lane_semantics_sha256=semantic.hexdigest(), expanded_bytes=size)


def check_cell(cell, job, encoder, index, admission_sha):
    audio_only(job)
    profile = index['profiles'][job['tap']]
    if (cell['schema'] != 'n4-d0-component-cell-v1' or cell['job'] != job
            or cell['encoder'] != encoder or cell['admission_sha256'] != admission_sha
            or cell['profile_sha256'] != fingerprint(profile) or cell['namespace'] != index['namespace']
            or cell['cache_key'] != cell_key(admission_sha, job, encoder, profile)
            or cell['observed_compute_is_live_latency'] is not False
            or cell['tracker_name_or_ASR_outputs_present'] is not False):
        raise ValueError('Cell does not bind the exact component contract')
    telemetry = cell['telemetry']
    if (telemetry['paired_audio_samples'] != job['frames']
            or abs(telemetry['speaker_unanalyzed_short_tail_sec']-(job['frames'] % 4000)/16000) > 1e-9):
        raise ValueError('Source/tail telemetry differs')


def review(run, output):
    import soundfile as sf
    import numpy as np
    run = run.resolve(strict=True)
    if output.exists():
        raise ValueError('Preserve prior review; select a fresh output directory')
    final_binding = bind(run/'RESULT.json'); final = load(final_binding['path'])
    admission_binding = bind(run/'ADMISSION.json'); terminal(final, admission_binding)
    contract = verify_contract(run/'ADMISSION.json')
    if (contract['schema'] != 'n4-d0-bank-components-v1' or contract['expected_clips_per_encoder'] != 480
            or contract['total'] != 960 or Path(contract['output']).resolve() != run):
        raise ValueError('Wrong full-bank contract')
    jobs = load(contract['manifest']['path'])['jobs']
    if len(jobs) != 480 or len({j['job_id'] for j in jobs}) != 480:
        raise ValueError('Exactly 480 unique admitted jobs required')
    if len(final['encoders']) != 2:
        raise ValueError('Exactly E0 and E1 results required')
    indexes = []; index_bindings = []
    for encoder, binding in zip(('E0', 'E1'), final['encoders']):
        exact_path(binding, run/encoder/'RESULT.json'); index = load(binding['path'])
        progress_binding = bind(run/encoder/'RESULT_INDEX.json')
        check_index(index, load(progress_binding['path']), jobs, admission_binding['sha256'])
        indexes.append(index); index_bindings.extend([binding, progress_binding])
    if indexes[0]['profiles'] != indexes[1]['profiles'] or indexes[0]['namespace'] == indexes[1]['namespace']:
        raise ValueError('Paired profile or model namespace separation failed')
    details = []; windows = Counter(); rejections = Counter(); no_windows = 0; segments = 0; expanded = 0
    for job in jobs:
        audio_only(job)
        info = sf.info(job['audio_path'])
        if (bind(job['audio_path'])['sha256'] != job['audio_sha256'] or info.subtype != 'PCM_16'
                or info.frames != job['frames'] or info.samplerate != 16000 or info.channels != 1):
            raise ValueError('Source waveform binding or header differs')
        wave, rate = sf.read(job['audio_path'], dtype='float32')
        if rate != 16000 or wave.ndim != 1 or len(wave) != job['frames'] or not np.isfinite(wave).all():
            raise ValueError('Invalid actual waveform')
        cells = []; scans = []; bindings = []
        for encoder, index in zip(('E0', 'E1'), indexes):
            binding = index['cells'][job['job_id']]
            exact_path(binding, run/encoder/job['job_id']/'RESULT.json'); cell = load(binding['path'])
            check_cell(cell, job, encoder, index, admission_binding['sha256'])
            exact_path(cell['events'], run/encoder/job['job_id']/'LANE_EVENTS.jsonl.gz')
            scans.append(scan_events(cell, wave)); cells.append(cell); bindings.append(binding)
        geometry = validate_pair(*cells)
        if scans[0]['paired_lane_semantics_sha256'] != scans[1]['paired_lane_semantics_sha256']:
            raise ValueError('Paired segmentation/admission semantics differ')
        windows.update(row['evidence_kind'] for row in geometry); no_windows += not geometry
        segments += cells[0]['segmentation_calls']; rejections.update(scans[0]['rejection_reasons'])
        expanded += sum(scan['expanded_bytes'] for scan in scans)
        details.append(dict(job_id=job['job_id'], results=bindings, query_windows=len(geometry),
            geometry_sha256=fingerprint(geometry), scans=scans))
    # Detect index/final replacement while reviewing, without touching the producer.
    for binding in [final_binding, admission_binding, *index_bindings]:
        verify(binding)
    receipt = dict(schema='n4-d0-bank-review-v1', status='PASS_MATCHED_FULL_BANK_COMPONENTS_ONLY',
        reviewed_utc=datetime.now(timezone.utc).isoformat(), clips_per_encoder=480, encoder_clip_cells=960,
        matched_query_windows_per_encoder=sum(windows.values()), query_kinds_per_encoder=dict(windows),
        clips_without_admitted_windows_per_encoder=no_windows, segmentation_calls_per_encoder=segments,
        admission_rejections_per_encoder=dict(rejections), expanded_event_bytes_verified=expanded,
        source_seconds_per_encoder=sum(j['frames'] for j in jobs)/16000,
        inputs=[final_binding, admission_binding, contract['manifest'], *index_bindings],
        code=[bind(Path(__file__).with_name(name)) for name in ('review_d0_bank.py', 'review_d0_collection.py',
            'd0_bank_components.py', 'd0_calibration_windows.py', 'common.py', 'test_review_d0_bank.py',
            'README_REVIEW_D0_BANK.md')],
        integrated_N4_cells=0, live_latency_qualified=False, complete_stack_resources_qualified=False,
        calibrated_D0_E1_profile_accepted=False, cells=details)
    output.mkdir(parents=True, exist_ok=False)
    freeze(output/'REVIEW.json', receipt)
    public = {k:v for k,v in receipt.items() if k != 'cells'}
    public['private_review'] = bind(output/'REVIEW.json')
    freeze(output/'REDACTED_REVIEW.json', public)
    return public


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    process = psutil.Process(); process.cpu_affinity([14])
    if os.name == 'nt':
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    print(json.dumps(review(args.run, args.output), indent=2))
