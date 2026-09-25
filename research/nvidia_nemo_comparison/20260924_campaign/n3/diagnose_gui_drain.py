"""Compare preserved actual GUI drainage without loading models; README_GUI_DRAIN.md."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def bound(path):
    path = Path(path).resolve(strict=True)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), sha256=digest, bytes=path.stat().st_size)


def summarize(cell):
    cell = Path(cell).resolve(strict=True)
    result = load(cell / 'RESULT.json')
    admission_path = cell.parents[1] / 'ADMISSION.json'
    admission = load(admission_path)
    if len(admission['jobs']) != 1 or admission['jobs'][0]['cell_id'] != result['cell_id']:
        raise ValueError('Expected exact single-cell admission')
    sessions = list((cell / 'data/sessions').iterdir())
    if len(sessions) != 1: raise ValueError('Expected one private session')
    final_path = sessions[0] / 'session_finalization_v3.json'
    final = load(final_path)
    archive_path = cell / 'ARCHIVE_INTEGRITY.json'; archive = load(archive_path)
    epoch = Path(archive['epoch']['path'])
    if bound(epoch) != archive['epoch']: raise ValueError('Archive epoch changed')
    event_path = epoch.parent / 'events.jsonl'
    dispatch = []; drain = []; failures = []; origin = None
    for line in event_path.open(encoding='utf-8'):
        row = json.loads(line); kind = row.get('kind'); payload = row['payload']
        if kind == 'source_started':
            if origin is not None: raise ValueError('Multiple source origins')
            origin = payload['source_epoch_monotonic_sec']
        elif kind == 'research_asr_dispatch':
            dispatch.append({key: payload[key] for key in ('source_start_sec', 'source_end_sec',
                'samples', 'compute_ms', 'publication_monotonic_sec')})
        elif kind == 'research_asr_drain':
            drain.append({key: payload[key] for key in ('exact_input_samples', 'compute_ms', 'publication_monotonic_sec')})
        elif kind == 'failure':
            failures.append(dict(at=payload['publication_monotonic_sec'],
                expected_drain_timeout=payload.get('reason') == 'session finalization failed: session lane edge-asr did not finish within 60 seconds'))
    if origin is None or not dispatch: raise ValueError('Missing actual source/ASR timing evidence')
    audio = admission['jobs'][0]['audio']; expected_samples = audio['frames']
    if final['source_samples'] != expected_samples: raise ValueError('Source sample census differs')
    # Require contiguous journal coverage; no fitted alignment or transcript use.
    consumed = 0
    for row in dispatch:
        if abs(row['source_start_sec'] * 16000 - consumed) > 1e-5:
            raise ValueError('Noncontiguous ASR dispatch evidence')
        consumed += row['samples']
        if abs(row['source_end_sec'] * 16000 - consumed) > 1e-5:
            raise ValueError('Dispatch end/sample census mismatch')
    if consumed > expected_samples: raise ValueError('ASR consumed more than observed audio')
    samples = load(cell / 'PROCESS_SAMPLES.json')
    span_summary = load(cell / 'SPAN_PRESENTATION_SUMMARY.json')
    first_finals = sum(value.get('first_final') is not None for value in span_summary.values())
    files = [cell / name for name in ('RESULT.json', 'PROCESS_SAMPLES.json',
        'SPAN_PRESENTATION_SUMMARY.json', 'PRESENTATION_RECEIPTS.jsonl', 'FINAL_STATE_APPLIED.jsonl')]
    files += [admission_path, final_path, archive_path, epoch, event_path]
    runtime_scope = {key: admission[key] for key in ('source', 'source_bindings', 'inputs',
        'common_ui_sha256', 'common_layout_sha256', 'cpu', 'threads', 'jobs')}
    public = dict(cell_id=result['cell_id'], status=result['status'], final_state=final['state'],
        archive_integrity_passed=result.get('archive_integrity_passed'),
        input_samples=expected_samples, input_seconds=expected_samples / 16000,
        consumed_samples=consumed, unprocessed_audio_seconds=(expected_samples - consumed) / 16000,
        asr_dispatches=len(dispatch), asr_dispatch_compute_wall_seconds=sum(r['compute_ms'] for r in dispatch) / 1000,
        last_asr_dispatch_elapsed_from_source_seconds=dispatch[-1]['publication_monotonic_sec'] - origin,
        tail_drain_count=len(drain),
        tail_drain_elapsed_from_source_seconds=[r['publication_monotonic_sec'] - origin for r in drain],
        tail_drain_sample_counts=[r['exact_input_samples'] for r in drain],
        failures=[dict(source_elapsed_seconds=r['at'] - origin, expected_drain_timeout=r['expected_drain_timeout']) for r in failures],
        lane_drain_timeout_seconds=final['lane_drain_timeout_sec'],
        live_lanes_at_finalization=final['live_lanes_at_finalization'],
        sampled_process_cpu_seconds=max(r['cpu_seconds'] for r in samples),
        sampled_process_elapsed_seconds=max(r['elapsed_sec'] for r in samples),
        peak_sampled_rss_bytes=max(r['rss_bytes'] for r in samples),
        spans=len(span_summary), spans_with_final_widget_observation=first_finals,
        original_runner=admission['runner'], evidence=[bound(p) for p in files])
    return runtime_scope, public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('passed-cell', 'failed-cell', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('Preserve existing reports')
    passed_scope, passed = summarize(args.passed_cell)
    failed_scope, failed = summarize(args.failed_cell)
    if passed_scope != failed_scope: raise ValueError('Application/runtime/audio/CPU contracts differ')
    if passed['status'] != 'COMPLETE' or passed['tail_drain_sample_counts'] != [passed['input_samples']]:
        raise ValueError('Passing comparator did not consume and flush all audio')
    if failed['status'] != 'FAILED' or not failed['failures'] or not all(r['expected_drain_timeout'] for r in failed['failures']):
        raise ValueError('Unexpected failure; do not misclassify it as drain capacity')
    report = dict(schema='n3-actual-gui-drain-diagnostic-v1',
        created_utc=datetime.now(timezone.utc).isoformat(), status='DIAGNOSED_NOT_REPAIRED',
        equal_application_runtime_audio_and_cpu_contract=True, cpu_affinity=passed_scope['cpu'],
        common_ui_unchanged=True, passing=passed, failed=failed,
        interpretation=[
            'Both actual runs accumulate ASR backlog on the admitted single CPU affinity.',
            'The passing run completes only after source delivery ends; it is not real-time qualification.',
            'The failed run is still advancing when the fixed lane-finalization deadline stops it.',
            'No missing recognized words are invented or dropped from an accuracy denominator.',
            'Different GUI audit callbacks and ordinary host/queue activity prevent a causal attribution of the slowdown.',
            'A1 queue verification overlapped the failed panel; its resource contribution was not measured independently.',
            'Preserve the existing timeout and failure. A3 single-CPU full-GUI use is not accepted from this evidence.'
        ],
        inference_rerun=False, modified_application=False, changed_timeout=False,
        required_next='Evaluate the admitted resource profile and full integration in N4; only a separately bound, justified repair and actual retest can qualify the affected runtime.',
        diagnostic_source=bound(__file__))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(status=report['status'], report=bound(args.output),
        passed_tail_seconds=passed['tail_drain_elapsed_from_source_seconds'],
        failed_remaining_seconds=failed['unprocessed_audio_seconds'])))


if __name__ == '__main__': main()
