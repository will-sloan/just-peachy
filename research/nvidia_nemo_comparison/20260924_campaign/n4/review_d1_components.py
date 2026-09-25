"""Review terminal D1 smoke, not integrated acceptance. README_REVIEW_D1.md."""
import argparse
from collections import Counter, deque
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

from common import bind, verify, load, freeze, fingerprint
from d1_bank_components import verify_admission, component_key, event_digest, supervisor


def close(a, b):
    if not math.isfinite(a) or not math.isfinite(b) or abs(a-b) > 1e-6:
        raise ValueError('Numeric clock/source value differs')


def scan_events(rows, wave, summary, namespace, timeline_type):
    import numpy as np
    timeline = timeline_type()
    counts = Counter()
    expected_queries = deque()
    expected_runs = deque()
    last_query, admitted = {}, set()
    reported_end = -1.
    actual_vectors, geometry, frames = [], [], []
    source_samples = pushes = finishes = 0
    serial = 0
    modeled = 0.
    dispatch = None
    pending_call = None
    awaiting_decision = False
    short_count = 0
    short_sec = 0.
    known_kinds = {'n2_diarization_binding', 'component_d1_dispatch', 'n2_diarization_frames',
        'component_d1_embedding_call', 'research_embedding', 'speaker_decision', 'n2_exclusive_run_coverage'}
    for row in rows:
        kind, p = row['event_type'], row['payload']
        if (kind not in known_kinds or row.get('component_clock') !=
                'modeled_serial_source_plus_actual_compute_not_observed_S7'):
            raise ValueError('Unknown event or falsely observed clock')
        counts[kind] += 1
        if kind == 'n2_diarization_binding':
            if counts[kind] != 1 or counts['component_d1_dispatch']:
                raise ValueError('Native binding must precede the one stream')
        elif kind == 'component_d1_dispatch':
            if (expected_queries or expected_runs or pending_call or awaiting_decision
                    or dispatch is not None and dispatch['frame_end'] != timeline.next_frame):
                raise ValueError('Previous native update/query evidence is incomplete')
            if counts['n2_diarization_binding'] != 1 or finishes:
                raise ValueError('Dispatch after final or before binding')
            if p['operation'] == 'push':
                source_samples += min(1600, len(wave)-source_samples)
                pushes += 1
                if source_samples <= 0 or pushes > math.ceil(len(wave)/1600):
                    raise ValueError('Invalid native push census')
            elif p['operation'] == 'finish':
                finishes += 1
                if source_samples != len(wave):
                    raise ValueError('Native finish before all real samples')
            else:
                raise ValueError('Unknown native operation')
            if p['input_samples'] != source_samples or p['frame_start'] != timeline.next_frame:
                raise ValueError('Native source/frame discontinuity')
            close(row['source_time_sec'], source_samples/16000)
            elapsed = p['actual_finished_elapsed_sec']-p['actual_started_elapsed_sec']
            if elapsed < 0 or p['frame_end'] < p['frame_start'] or p['observed_live_latency_qualified'] is not False:
                raise ValueError('Invalid native dispatch timing/frames')
            modeled = max(modeled, source_samples/16000)+elapsed
            close(p['modeled_available_at_sec'], modeled)
            dispatch = p
        elif kind == 'n2_diarization_frames':
            if dispatch is None or p['frame_start'] != timeline.next_frame:
                raise ValueError('Native frame event without matching dispatch')
            probs = np.asarray(p['probabilities'], dtype=np.float64)
            if probs.size == 0: probs = np.empty((0, 8))
            if (probs.ndim != 2 or probs.shape[1] != 8 or not np.isfinite(probs).all()
                    or (probs < 0).any() or (probs > 1).any() or p['activity_threshold'] != .5
                    or p['activity_is_identity_confidence'] is not False
                    or p['frame_start']+len(probs) != dispatch['frame_end']
                    or p['is_final'] != (dispatch['operation'] == 'finish')
                    or len(p['track_ids']) != 8 or len(set(p['track_ids'])) != 8):
                raise ValueError('Invalid native probabilities/frame census')
            close(p['frame_step_sec'], .01)
            close(p['audio_received_sec'], source_samples/16000)
            close(row['source_time_sec'], p['audio_received_sec'])
            close(p['native_frame_end_sec'], dispatch['frame_end']*.01)
            close(p['endpoint_overhang_sec'], max(0., dispatch['frame_end']*.01-source_samples/16000))
            if (p['compute_sec'] < 0 or not math.isfinite(p['compute_sec'])
                    or not math.isfinite(p['available_at_monotonic'])
                    or not math.isfinite(p['received_at_monotonic'])
                    or p['available_at_monotonic'] < p['received_at_monotonic']):
                raise ValueError('Invalid raw native monotonic times')
            if len(probs):
                timeline.append(SimpleNamespace(frame_start=p['frame_start'], frame_end=dispatch['frame_end'],
                    probabilities=probs, seconds_per_frame=.01, audio_received_sec=source_samples/16000,
                    available_at_monotonic=p['available_at_monotonic']))
            for slot, start, end, run_start in timeline.exclusive_windows(last_query):
                expected_queries.append((slot, round(start*16000), round(end*16000), run_start, p['track_ids'][slot]))
                last_query[slot] = end
                admitted.add((slot, run_start))
            for slot, start, end, closed in timeline.exclusive_runs(final=p['is_final']):
                if closed and end > reported_end+1e-7:
                    reported_end = end
                    expected_runs.append((slot, start, end, (slot, start) in admitted))
            frames.append({k:p[k] for k in ('frame_start', 'probabilities', 'frame_step_sec',
                'audio_received_sec', 'native_frame_end_sec', 'is_final', 'track_ids')})
        elif kind == 'component_d1_embedding_call':
            if not expected_queries or pending_call is not None or awaiting_decision:
                raise ValueError('Unexpected embedding call')
            slot, first, last, _, track = expected_queries[0]
            actual = wave[first:last]
            if (not 0 <= first < last <= source_samples or p['samples'] != last-first
                    or p['waveform_sha256'] != hashlib.sha256(actual.astype('<f4').tobytes()).hexdigest()):
                raise ValueError('Embedding call waveform support differs')
            close(row['source_time_sec'], last/16000)
            elapsed = p['actual_finished_elapsed_sec']-p['actual_started_elapsed_sec']
            if elapsed < 0: raise ValueError('Negative embedding duration')
            modeled = max(modeled, source_samples/16000)+elapsed
            pending_call = p
        elif kind == 'research_embedding':
            if pending_call is None or not expected_queries:
                raise ValueError('Embedding event has no actual call/query')
            slot, first, last, _, track = expected_queries.popleft()
            serial += 1
            eid = f'n2-embedding:{serial:08d}'
            vector = np.asarray(p['normalized_embedding'])
            if (p['event_id'] != eid or p['evidence_event_id'] != eid or p['model_slot'] != slot
                    or p['tracker_id'] != track or p['model_namespace'] != namespace
                    or p['clean_intervals'] != [[first/16000, last/16000]]
                    or p['actual_selected_window'] is not True or p['speech'] is not True
                    or p['overlap'] is not False or p['left_padding_sec'] != 0
                    or vector.shape != (192,) or not np.isfinite(vector).all()
                    or abs(float(np.linalg.norm(vector))-1) > .001):
                raise ValueError('Embedding semantics or namespace differ')
            for key, expected in [('source_start_sec', first/16000), ('source_end_sec', last/16000),
                    ('receptive_start_sec', first/16000), ('receptive_end_sec', last/16000),
                    ('available_source_cursor_sec', source_samples/16000), ('available_at_sec', modeled)]:
                close(p[key], expected)
            actual_vectors.append(dict(start_sample=first, end_sample=last,
                waveform_sha256=pending_call['waveform_sha256'], model_slot=slot,
                tracker_id=track, normalized_embedding=p['normalized_embedding']))
            geometry.append([slot, first, last, pending_call['waveform_sha256'], track])
            pending_call = None
            awaiting_decision = True
        elif kind == 'speaker_decision':
            if not awaiting_decision or p['event_id'] != f'n2-embedding:{serial:08d}' or p.get('known_profile_id') is not None:
                raise ValueError('Missing anonymous decision or unexpected known identity')
            awaiting_decision = False
        elif kind == 'n2_exclusive_run_coverage':
            if expected_queries or pending_call or awaiting_decision or not expected_runs:
                raise ValueError('Missing/misordered exclusive-run evidence')
            slot, start, end, selected = expected_runs.popleft()
            short = end-start < .5-1e-6
            if (p['model_slot'] != slot or p['embedding_selected'] != selected
                    or p['unavailable_reason'] != ('BELOW_EMBEDDING_MINIMUM' if short else None)):
                raise ValueError('Short-turn coverage differs')
            close(p['source_start_sec'], start)
            close(p['source_end_sec'], end)
            close(p['duration_sec'], end-start)
            if short:
                short_count += 1
                short_sec += end-start
    if (finishes != 1 or source_samples != len(wave) or expected_queries or expected_runs
            or pending_call or awaiting_decision or not frames or not frames[-1]['is_final']):
        raise ValueError('Incomplete final native/query/coverage evidence')
    if (summary['input_samples'] != len(wave) or summary['source_reads'] != pushes
            or summary['event_counts'] != dict(counts) or summary['embeddings'] != serial
            or summary['native_frames'] != timeline.next_frame or summary['vectors'] != actual_vectors
            or summary['observed_live_latency_qualified'] is not False or summary['integrated_N4_cells'] != 0
            or summary['telemetry']['identity_audio_samples'] != len(wave)
            or summary['telemetry']['n2_exclusive_runs_below_embedding_minimum'] != short_count):
        raise ValueError('Summary does not match full evidence')
    close(summary['telemetry']['n2_exclusive_seconds_below_embedding_minimum'], short_sec)
    close(summary['modeled_completion_sec'], modeled)
    return dict(native_frames=timeline.next_frame, embeddings=serial, short_runs=short_count,
        semantic_frames_sha256=fingerprint(frames), query_geometry_sha256=fingerprint(geometry))


def review(args):
    import soundfile as sf
    contract = verify_admission(args.run/'ADMISSION.json')
    result = load(args.run/'RESULT.json')
    if (Path(contract['output']).resolve() != args.run.resolve()
            or result['status'] != 'SMOKE_COLLECTED_REQUIRES_REVIEW' or result['completed'] != 4
            or result['total'] != 4 or result['child'] is not None or supervisor.same_process(result['owner'])
            or result['admission'] != bind(args.run/'ADMISSION.json')):
        raise ValueError('Require terminal four-cell D1 evidence and exited exact coordinator')
    source = Path(contract['source'])
    sys.path[:0] = [str(source), str(source/'vendor')]
    from app.n2_pipeline import ActivityTimeline
    from app.n2_models import redim_namespace
    from app.pipeline import effective_profile
    from app.paths import pipeline_config
    runtime = load(contract['component_contract']['runtime']['path'])
    rows, pairs = [], {}
    for encoder in contract['encoders']:
        terminal = load(args.run/encoder/'RESULT.json')
        index = load(args.run/encoder/'RESULT_INDEX.json')
        if (bind(args.run/encoder/'RESULT.json') not in result['encoders'] or terminal['status'] != 'COMPLETE'
                or terminal['completed'] != 2 or terminal['total'] != 2 or terminal['cpu_affinity'] != [4]
                or index['completed'] != 2 or index['total'] != 2 or index['cells'] != terminal['cells']
                or set(index['cells']) != {j['job_id'] for j in contract['jobs']}):
            raise ValueError('Per-encoder terminal census differs')
        for job in contract['jobs']:
            cell = args.run/encoder/job['job_id']
            binding = bind(cell/'RESULT.json')
            if binding != index['cells'][job['job_id']]: raise ValueError('Indexed cell binding differs')
            data = load(cell/'RESULT.json')
            profile = effective_profile('balanced', 'anonymous_conversation', job['tap'])
            config = profile.apply(pipeline_config(args.run/'unused-private-root', Path(contract['models_root'])))
            namespace = runtime['embedding_namespace'] if encoder == 'E1' else redim_namespace(config)
            if (data['status'] != 'COMPLETE' or data['job'] != job or data['encoder'] != encoder
                    or data['admission_sha256'] != bind(args.run/'ADMISSION.json')['sha256']
                    or data['profile_sha256'] != fingerprint(profile.to_dict())
                    or profile.to_dict() != contract['profiles'][job['tap']]
                    or data['cache_key'] != component_key(contract, job, encoder, profile.to_dict())
                    or data['namespace'] != namespace or data['cpu_affinity'] != [4]
                    or data['actual_neural_inference'] is not True or data['integrated_N4_cells'] != 0
                    or data['events'] != bind(cell/'D1_EVENTS.jsonl.gz')
                    or data['events_expanded'] != event_digest(cell/'D1_EVENTS.jsonl.gz')):
                raise ValueError('Cell cache/source/asset/evidence contract differs')
            if bind(job['audio_path'])['sha256'] != job['audio_sha256']: raise ValueError('Waveform hash differs')
            wave, rate = sf.read(job['audio_path'], dtype='float32')
            if rate != 16000 or wave.ndim != 1 or len(wave) != job['frames']: raise ValueError('Waveform format differs')
            with gzip.open(cell/'D1_EVENTS.jsonl.gz', 'rt', encoding='utf-8') as stream:
                events = [json.loads(line) for line in stream]
            native = next(e['payload'] for e in events if e['event_type'] == 'n2_diarization_binding')
            if (native['model_sha256'] != bind(runtime['nemotron_model'])['sha256']
                    or native['library_sha256'] != runtime['nemotron_library_sha256']
                    or native['gpu'] is not False or native['profile']['name'] != 'low_latency'):
                raise ValueError('Actual native model/runtime binding differs')
            scan = scan_events(events, wave, data['summary'], namespace, ActivityTimeline)
            paired = pairs.setdefault(job['job_id'], scan)
            if paired != scan: raise ValueError('E0/E1 native frame or query geometry differs')
            rows.append(dict(encoder=encoder, job_id=job['job_id'], result=binding, **scan))
    if args.output.exists(): raise ValueError('Preserve previous review; choose a new output')
    args.output.mkdir(parents=True)
    receipt = dict(status='PASS_D1_COMPONENT_SMOKE', reviewed_utc=supervisor.now(),
        admission=bind(args.run/'ADMISSION.json'), terminal=bind(args.run/'RESULT.json'),
        reviewer=bind(Path(__file__)), component_cells=4, paired_files=2, rows=rows,
        integrated_N4_cells=0, full_bank_admitted=False, Controller_widget_parity=False)
    freeze(args.output/'REVIEW.json', receipt)
    print(json.dumps(dict(status=receipt['status'], review=bind(args.output/'REVIEW.json'))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    import psutil
    psutil.Process().cpu_affinity([14])
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    review(parser.parse_args())
