"""Reconstruct bounded application resource evidence. README_RESOURCE_REVIEW.md."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

from application_resources import FIELDS, PHASES, ResourceLedger, identity as resource_identity
from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock

MAX_LOG = 64*1024**2
MAX_LINE = 1024**2
MAX_RECORDS = 40000


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def sums(tree, owner):
    """Independently recompute each aggregate; unavailable fields remain None."""
    rows = tree['processes']; keys = [resource_identity(row) for row in rows]
    require(len(rows) <= 256 and len(keys) == len(set(keys)), 'Resource process census duplicated or unbounded')
    incomplete = tree.get('incomplete_processes', [])
    require(type(incomplete) is list and len(incomplete) <= 256, 'Incomplete census is unbounded')
    require(type(tree['complete']) is bool and tree['complete'] == (not incomplete and resource_identity(owner) in keys),
        'Complete-tree flag differs from raw process observations')
    for row in rows:
        require(type(row['memory_info_bytes']) is dict, 'Missing per-process memory fields')
        for value in list(row['memory_info_bytes'].values())+[row.get('unique_set_size_bytes'), row.get('proportional_set_size_bytes'), row.get('threads')]:
            require(value is None or type(value) is int and value >= 0, 'Invalid memory/thread counter')
        for field in ('user', 'system'):
            value = row['cpu_seconds'][field]; require(finite(value) and value >= 0, 'Invalid raw CPU counter')
    getters = {
        FIELDS[0]: lambda row: row['memory_info_bytes'].get('rss'),
        FIELDS[1]: lambda row: row.get('unique_set_size_bytes'),
        FIELDS[2]: lambda row: row['memory_info_bytes'].get('private'),
        FIELDS[3]: lambda row: row.get('proportional_set_size_bytes'),
        'thread_count_sum': lambda row: row.get('threads'),
    }
    result = {}
    for field, getter in getters.items():
        values = [getter(row) for row in rows]
        calculated = sum(values) if values and all(type(v) is int and v >= 0 for v in values) else None
        require(tree.get(field) == calculated and (calculated is None or type(tree.get(field)) is int),
            'Per-process '+field+' does not match the stored sum')
        result[field] = calculated
    return result


def review(result_binding, *, expected_owner=None, require_all_phases=False):
    verify(result_binding); require(result_binding['bytes'] <= 8*1024**2, 'Resource summary exceeds bound')
    result = load(result_binding['path']); owner = result['owner']; resource_identity(owner)
    if expected_owner is not None: require(owner == expected_owner, 'Resource root belongs to a different application')
    require(exact_process(owner) is None, 'Resource root must have exited before review')
    require(result['status'] == 'OBSERVED_HOST_RESOURCES' and result['error'] is None and result['observer_thread_exited'] is True,
        'Resource observation failed or remains open')
    require(result['controlled_whole_stack_qualified'] is False and result['target_qualified'] is False
        and result['integrated_N4_cells'] == 0, 'Collector improperly asserted acceptance')
    evidence = result['evidence']; verify(evidence)
    require(Path(evidence['path']).resolve() == Path(result_binding['path']).resolve().parent/'SAMPLES.jsonl', 'Foreign resource sample log')
    require(0 < evidence['bytes'] <= MAX_LOG and result['observer_bytes'] == evidence['bytes'], 'Resource byte census differs')
    require(finite(result['interval_sec']) and .1 <= result['interval_sec'] <= 10, 'Sampling interval outside collector contract')
    require(finite(result['elapsed_sec']) and result['elapsed_sec'] >= 0, 'Invalid resource elapsed time')
    ledger = ResourceLedger(owner); marks = []; records = total = 0; last_mark = None; maximum_end = None
    global_peaks = {field: None for field in (*FIELDS, 'thread_count_sum')}
    with Path(evidence['path']).open('rb') as stream:
        while True:
            line = stream.readline(MAX_LINE+1)
            if not line: break
            records += 1; total += len(line)
            require(records <= MAX_RECORDS and total <= MAX_LOG and len(line) <= MAX_LINE and line.endswith(b'\n'),
                'Resource log truncated or exceeds record/byte bounds')
            row = json.loads(line)
            if row.get('kind') == 'phase':
                require(set(row) == {'kind','phase','monotonic_sec'} and len(marks) < len(PHASES)
                    and row['phase'] == PHASES[len(marks)] and finite(row['monotonic_sec'])
                    and (last_mark is None or row['monotonic_sec'] >= last_mark), 'Phase mark order/clock differs')
                marks.append(row); last_mark = row['monotonic_sec']
            elif row.get('kind') == 'sample':
                require(marks and row['phase_at_end'] == marks[-1]['phase']
                    and row['phase_at_start'] in PHASES[:len(marks)], 'Sample phase is not the published lifecycle prefix')
                start_mark = next(m for m in marks if m['phase'] == row['phase_at_start'])
                require(finite(row['began_monotonic_sec']) and row['began_monotonic_sec'] >= start_mark['monotonic_sec'],
                    'Sample precedes its phase start')
                values = sums(row['tree'], owner); ledger.accept(row)
                maximum_end = max(maximum_end or row['ended_monotonic_sec'], row['ended_monotonic_sec'])
                if row['tree']['complete']:
                    for field, value in values.items():
                        if value is not None: global_peaks[field] = max(global_peaks[field] or 0, value)
            else: raise ValueError('Unknown resource log record')
    rebuilt = ledger.summary()
    require(total == evidence['bytes'] and rebuilt['samples'] > 0 and marks == result['phase_marks'], 'Resource record/mark census differs')
    for field, value in rebuilt.items(): require(result[field] == value, 'Reconstructed resource summary differs: '+field)
    complete = [m['phase'] for m in marks] == list(PHASES)
    require(result['all_lifecycle_marks_present'] is complete, 'Complete-lifecycle flag differs')
    if require_all_phases: require(complete, 'Full application lifecycle marks are missing')
    require(result['elapsed_sec'] >= max(maximum_end, marks[-1]['monotonic_sec'])-marks[0]['monotonic_sec'], 'Elapsed time excludes recorded observations')
    durations = {a['phase']: b['monotonic_sec']-a['monotonic_sec'] for a,b in zip(marks, marks[1:])}
    running = rebuilt['phases'].get('running'); growth = None
    if running and running['complete_samples'] >= 2:
        first, last = running['first'], running['last']
        growth = dict(sample_window_seconds=last['monotonic_sec']-first['monotonic_sec'],
            delta_bytes={field: last[field]-first[field] if last[field] is not None and first[field] is not None else None for field in FIELDS},
            interpretation='Difference between complete first/last running samples; not a memory-leak diagnosis')
    verify(result_binding); verify(evidence)
    return dict(status='PASS_RECONSTRUCTED_RESOURCE_OBSERVATIONS_ONLY', input=result_binding, evidence=evidence,
        owner=owner, raw_records=records, all_lifecycle_marks_present=complete, reconstructed=rebuilt,
        sampled_global_peaks=global_peaks, marked_phase_intervals_seconds=durations, running_growth=growth,
        gpu_visibility_environment=result.get('gpu_visibility_environment'),
        controlled_whole_stack_qualified=False, target_qualified=False, deployment_tier='UNKNOWN', integrated_N4_cells=0,
        limitations=['Resource sums and phase summaries were reconstructed, not remeasured.',
            'Point samples can miss peaks/short-lived children; CPU deltas are lower bounds.',
            'RSS sum can double-count shared pages; USS omits shared pages; private commit and PSS remain separate.',
            'Phase labels do not prove actual source/model/GUI operation, cold cache or exclusive resource ownership.',
            'No GPU allocator/device measurement, WSL/cgroup accounting, CM5 performance or 2-GB physical-fit inference.'])


def run(result_path, output):
    process = pin(); started = time.monotonic(); local = Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'), 'Fresh private review output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output, local, started, 720); inventory = shared_allowance(local)
        qualifier = load(Path(__file__).with_name('RESOURCE_REVIEW_CHECK_V1.json'))
        require(qualifier['status'] == 'PASS_RESOURCE_REVIEW_DEVELOPMENT_ONLY', 'Review implementation qualification required')
        for b in qualifier['code']: verify(b)
        result_binding = bind(result_path)
        freeze(output/'ADMISSION.json', dict(owner=identity(process), result=result_binding, inventory=inventory,
            qualification=bind(Path(__file__).with_name('RESOURCE_REVIEW_CHECK_V1.json')), code=qualifier['code']))
        reviewed = review(result_binding)
        guard(output, local, started, 720)
        freeze(output/'REVIEW.json', dict(reviewed, admission=bind(output/'ADMISSION.json'), utc=datetime.now(timezone.utc).isoformat()))
        print('Reviewed saved resource evidence; no application or target acceptance', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args(); run(args.result,args.output)
