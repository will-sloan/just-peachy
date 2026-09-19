"""Offline native evidence guards; see README_S6D_NATIVE_EVIDENCE_V1.md."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import wave

RATE = 16000
MAX_JSON = 64 * 2**20
MAX_STREAM = 2**30
MAX_LINE = 8 * 2**20
MAX_ROWS = 1000000


def need(value, message):
    if not value:
        raise ValueError(message)


def frame(value):
    need(type(value) in (int, float) and math.isfinite(value) and value >= 0,
         'Finite nonnegative source time required')
    result = round(value * RATE)
    need(abs(value * RATE - result) <= 1e-5, 'Source time is not an integer 16k frame')
    return result


def binding(path):
    path = Path(path).resolve()
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for raw in iter(lambda: handle.read(2**20), b''):
            h.update(raw)
    after = path.stat()
    need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'File changed while hashing')
    return dict(path=str(path), bytes=after.st_size, sha256=h.hexdigest())


def read_json(path):
    path = Path(path)
    need(path.stat().st_size <= MAX_JSON, 'Metadata size bound exceeded')
    raw = path.read_bytes()
    need(len(raw) <= MAX_JSON, 'Metadata grew beyond bound')
    value = json.loads(raw.decode('utf-8-sig'), parse_constant=lambda x: need(False, 'Nonfinite JSON'))
    return value, dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def stream(path):
    """Bounded read-only iterator; caller binds before and after consuming."""
    size = rows = 0
    with Path(path).open('rb') as handle:
        while True:
            raw = handle.readline(MAX_LINE + 1)
            if not raw:
                break
            size += len(raw)
            need(len(raw) <= MAX_LINE and size <= MAX_STREAM, 'Event stream byte bound exceeded')
            if raw.strip():
                rows += 1
                need(rows <= MAX_ROWS, 'Event row bound exceeded')
                row = json.loads(raw.decode('utf-8-sig'), parse_constant=lambda x: need(False, 'Nonfinite JSON'))
                need(isinstance(row, dict), 'Object event required')
                yield row


def pcm_proof(path, expected_binding=None):
    """One read-only WAV body hash; no conversion, gain, inference or playback."""
    before = binding(path)
    if expected_binding is not None:
        need(before == expected_binding, 'Source WAV binding differs')
    h = hashlib.sha256()
    count = 0
    with wave.open(str(path), 'rb') as handle:
        need((handle.getnchannels(), handle.getsampwidth(), handle.getframerate(), handle.getcomptype()) ==
             (1, 2, RATE, 'NONE'), 'Exact mono PCM16/16k source required')
        frames = handle.getnframes()
        for raw in iter(lambda: handle.readframes(65536), b''):
            count += len(raw)
            h.update(raw)
    need(count == 2 * frames and binding(path) == before, 'Source body truncated or changed')
    return dict(source=before, frames=frames, bytes=count, sha256=h.hexdigest())


def validate_completion(result, job, finalization, journal_proofs, consumer_closure):
    """Return explicit semantic errors. Caller must separately admit exact owner/source chain."""
    errors = []
    def check(value, message):
        if not value:
            errors.append(message)
    expected = job.get('expected_frames')
    if type(expected) is not int or expected <= 0:
        return ['Expected positive integer frame count must be predeclared']
    try:
        check(frame(job['audio_duration_sec']) == expected, 'Declared duration/frame mismatch')
    except (KeyError, ValueError):
        errors.append('Declared duration/frame mismatch')
    source = journal_proofs.get('source', {})
    check(source.get('frames') == expected and source.get('sha256') == job.get('audio_pcm_sha256')
          and isinstance(job.get('audio_pcm_sha256'), str) and len(job['audio_pcm_sha256']) == 64,
          'Expected source PCM proof mismatch')
    for name in ('asr', 'identity'):
        proof = journal_proofs.get(name, {})
        check(proof.get('bytes') == expected * 2 and proof.get('sha256') == source.get('sha256'),
              'Actual journal differs from full source PCM: ' + name)
    check(result.get('job') == job, 'Literal native job mismatch')
    check(result.get('status') == 'COMPLETE' and result.get('failure') is None
          and result.get('native_tested') is True, 'Native semantic failure')
    for key in ('resource_observer_closed', 'event_consumer_drained'):
        check(result.get(key) is True, 'Not closed: ' + key)
    for key in ('observer_errors', 'completion_errors'):
        check(result.get(key) == [], 'Missing or adverse ' + key)
    telemetry = result.get('telemetry') or {}
    check(telemetry.get('state') == 'COMPLETED', 'Engine not completed')
    for key in ('source_duration_sec', 'asr_cursor_sec', 'speaker_cursor_sec'):
        try:
            check(frame(telemetry[key]) == expected, 'Incomplete cursor: ' + key)
        except (KeyError, ValueError):
            errors.append('Unavailable cursor: ' + key)
    for key in ('paired_audio_samples', 'identity_audio_samples'):
        check(type(telemetry.get(key)) is int and telemetry[key] == expected, 'Incomplete source count: ' + key)
    for key in ('audio_frames_dropped', 'portaudio_input_overflows', 'raw_capture_reserve_failures'):
        check(type(telemetry.get(key)) is int and telemetry[key] == 0, 'Missing/nonzero loss counter: ' + key)
    check(telemetry.get('live_lanes_at_finalization') == [] and telemetry.get('bundle_retained_due_live_lanes') is False,
          'Live lane/bundle retention')
    scheduler = telemetry.get('scheduler') or {}
    check(scheduler.get('closed') is True and scheduler.get('pending_events') == 0
          and scheduler.get('watermarks') == {'asr': 'closed', 'speaker': 'closed'}, 'Scheduler not fully drained')
    check(finalization.get('state') == 'COMPLETED' and finalization.get('finalization_error') is None
          and 'finalization_error' in finalization and finalization.get('live_lanes_at_finalization') == []
          and finalization.get('resident_bundle_lease_retained') is False
          and finalization.get('event_and_transcript_handles_closed') is True, 'Finalizer not closed successfully')
    check(finalization.get('source_samples') == finalization.get('identity_samples') == expected,
          'Finalizer accepted only a prefix')
    if job.get('settings') is not None:
        queues = telemetry.get('s6d') or {}
        check((queues.get('event_consumer') or {}).get('depth') == 0, 'Consumer queue not drained')
        for name in ('journal', 'punctuation', 'policy'):
            row = queues.get(name) or {}
            check(row.get('depth') == 0 and row.get('thread_alive') is False and row.get('closed') is True
                  and row.get('error') is None and 'error' in row
                  and type(row.get('accepted')) is int and row.get('accepted') == row.get('completed'),
                  'Worker queue not drained: ' + name)
        check(isinstance(consumer_closure, dict) and consumer_closure.get('state') == 'COMPLETED'
              and consumer_closure.get('full_event_consumer_drained') is True
              and consumer_closure.get('queues') == queues, 'Consumer closure missing or inconsistent')
    return errors


def validate_dispatch(events, expected_frames):
    need(type(expected_frames) is int and expected_frames > 0, 'Positive expected frames required')
    end = total = starts = complete = drains = tails = blocks = 0
    closed = set()
    for event in events:
        kind, p = event.get('event_type'), event.get('payload', {})
        need(kind != 'failure', 'Failure event recorded')
        if kind == 'source_started':
            starts += 1
            need(starts == 1 and not complete and p.get('expected_samples') == expected_frames
                 and p.get('pipeline_sample_rate') == RATE, 'Missing/duplicate/wrong source origin')
        if kind == 'session_completed':
            complete += 1
            need(starts == 1 and complete == 1, 'Invalid completion event')
        if kind in ('research_asr_dispatch', 'research_asr_tail_dispatch'):
            need(starts == 1 and complete == 0 and drains == 0, 'Dispatch outside source/drain order')
            a, b = frame(p['source_start_sec']), frame(p['source_end_sec'])
            need(a == end and a < b <= expected_frames, 'ASR dispatch gap/duplicate/overrun')
            if kind == 'research_asr_tail_dispatch':
                tails += 1
                need(tails == 1 and type(p.get('samples')) is int and p['samples'] == b - a, 'Tail span/count mismatch')
            total += b - a
            end = b
            blocks += 1
        if kind == 'research_asr_drain':
            drains += 1
            need(drains == 1 and end == expected_frames and frame(p['source_end_sec']) == expected_frames
                 and p.get('padding_is_observed_audio') is False and p.get('synthetic_right_padding_sec') == .66,
                 'Final synthetic padding is not full observed source')
        if kind == 'research_scheduler_watermark' and p.get('lane_closed') is True:
            lane = p.get('lane')
            need(lane in {'asr', 'speaker'} and lane not in closed, 'Duplicate/unknown lane closure')
            closed.add(lane)
    need(starts == complete == drains == 1 and total == end == expected_frames
         and closed == {'asr', 'speaker'}, 'Incomplete full-source dispatch/drain evidence')
    return dict(frames=total, blocks=blocks, tail_blocks=tails, synthetic_padding_excluded_sec=.66)


def shift_reference_pieces(pieces, expected_frames):
    """Shift already mapped, evaluator-only turns; never remap canonical samples directly."""
    result = []
    cursor = 0
    ids = set()
    for index, piece in enumerate(pieces):
        start, length, gap = piece['start_sample'], piece['samples'], piece['gap_before_samples']
        need(all(type(x) is int for x in (start, length, gap)) and length > 0 and gap >= 0,
             'Integer positive whole piece/gap required')
        need(start == cursor + gap and (index != 0 or gap == 0), 'Composition gap/overlap mismatch')
        for turn in piece['mapped_turns']:
            key = (index, piece['case_id'], turn['segment_index'])
            need(key not in ids, 'Duplicate reference occurrence')
            ids.add(key)
            out = dict(turn, occurrence_id=f'{index}:{piece["case_id"]}:{turn["segment_index"]}',
                       piece_index=index, case_id=piece['case_id'], all_reference_complete=piece['all_reference_complete'])
            for field in ('file_support', 'active_ranges', 'sole'):
                ranges = turn.get(field)
                if ranges is None:
                    out[field] = None
                    continue
                shifted = []
                for a, b in ranges:
                    need(type(a) is int and type(b) is int and 0 <= a < b <= length, 'Mapped support outside piece')
                    shifted.append([a + start, b + start])
                out[field] = shifted
            result.append(out)
        cursor = start + length
    need(cursor == expected_frames, 'Composition does not cover expected whole source')
    return result


def opportunity_census(opportunities):
    """No missing/unqualified opportunity becomes a successful zero latency."""
    counts = dict(total=len(opportunities), observed=0, right_censored=0, unavailable=0)
    ids = set()
    for row in opportunities:
        key = row['occurrence_id']
        need(key not in ids, 'Duplicate opportunity denominator')
        ids.add(key)
        status, wait = row['status'], row.get('wait_sec')
        if status == 'OBSERVED':
            need(type(wait) in (int, float) and math.isfinite(wait), 'Observed latency missing/nonfinite')
            counts['observed'] += 1
        elif status == 'RIGHT_CENSORED':
            need(wait is None and type(row.get('censor_sec')) in (int, float)
                 and math.isfinite(row['censor_sec']) and row['censor_sec'] >= 0, 'Invalid censor horizon')
            counts['right_censored'] += 1
        else:
            need(status in {'INCOMPLETE_REFERENCE', 'UNAVAILABLE_ALIGNMENT', 'NO_SOLE_SUPPORT',
                            'NO_GALLERY_CONTROL', 'INTENDED_BUT_UNAVAILABLE', 'WITHHELD_OR_UNSELECTED'}
                 and wait is None, 'Unknown/misrepresented opportunity status')
            counts['unavailable'] += 1
    return counts


def audit(manifest_path, sha, job_id):
    """Inspect closed artifacts only; does not grant process/source-authority admission."""
    manifest, mb = read_json(manifest_path)
    need(mb['sha256'] == sha, 'Manifest hash mismatch')
    jobs = [r for r in manifest['jobs'] if r['job_id'] == job_id]
    need(len(jobs) == 1, 'One exact manifest job required')
    job = jobs[0]
    output = Path(job['output']).resolve()
    result, rb = read_json(output / 'RESULT.json')
    need(result['manifest'] == mb and result['helper'] == manifest['helper'] and result['job'] == job,
         'Native receipt source chain differs')
    session = Path(result['session_dir']).resolve()
    need(output / 'sessions' in session.parents, 'Session outside bound job')
    final, fb = read_json(session / 'session_finalization_v3.json')
    closure, cb = read_json(session / 's6d_consumer_closure.json') if job.get('settings') else (None, None)
    source = pcm_proof(job['audio']['path'], job['audio'])
    # Historical pilot lacks these two declarations: derive from bound WAV for inspection only.
    enriched = dict(job, expected_frames=job.get('expected_frames', source['frames']),
                    audio_pcm_sha256=job.get('audio_pcm_sha256', source['sha256']))
    proofs = dict(source=source, asr=binding(session / 'audio_spool.pcm16'),
                  identity=binding(session / 'identity_audio_spool.pcm16'))
    checked = dict(result, job=enriched)
    errors = validate_completion(checked, enriched, final, proofs, closure)
    ep = output / 'consumer_events.jsonl'
    eb = binding(ep)
    try:
        dispatch = validate_dispatch(stream(ep), source['frames'])
    except (KeyError, ValueError) as exc:
        errors.append('Dispatch: ' + str(exc))
        dispatch = None
    need(binding(ep) == eb and read_json(output / 'RESULT.json')[1] == rb
         and read_json(session / 'session_finalization_v3.json')[1] == fb, 'Native evidence changed during audit')
    return dict(schema='s6d-native-evidence-audit.v1', status='PASS_OFFLINE_EVIDENCE' if not errors else 'REJECTED',
                job_id=job_id, manifest=mb, result=rb, finalization=fb, consumer_closure=cb,
                journals=proofs, consumer_events=eb, dispatch=dispatch, errors=errors,
                expected_frames_predeclared='expected_frames' in job,
                limitation='Offline evidence inspection; owner exit, supervisor/source graph admission and correctness are separate. Headless consumer is not GUI render or display scanout.',
                source=binding(__file__), models_started=0, hardware_calls=0, gui_started=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--job-id', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    value = audit(a.manifest, a.sha256, a.job_id)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(status=value['status'], receipt=binding(a.output))))
