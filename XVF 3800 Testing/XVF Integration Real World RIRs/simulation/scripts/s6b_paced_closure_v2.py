"""Closed paced evidence accounting; see README_S6B_PACED_CLOSURE_V2.md."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import copy
import math
import csv
from itertools import product

import psutil
from s6b_paced_resume_v2 import binding, closed, process_closure, read, verify, utc, write_new


def ranges(values):
    values = [v for v in values if v is not None]
    return {'count': len(values), 'min': min(values) if values else None,
            'median': statistics.median(values) if values else None, 'max': max(values) if values else None}


def validate_grid(summary, manifest, final_binding):
    if summary['manifest'] != final_binding:
        raise ValueError('Summary does not bind the actual final manifest')
    jobs = {j['job_id']: j for j in manifest['jobs']}
    rows = {r['job_id']: r for r in summary['rows']}
    if len(jobs) != len(manifest['jobs']) or len(rows) != len(summary['rows']) or set(rows) != set(jobs):
        raise ValueError('Summary job-ID grid differs or contains duplicates')
    for name, job in jobs.items():
        if any(rows[name][k] != job[k] for k in ('profile_id', 'case_id', 'stream', 'repetition')):
            raise ValueError('Summary row source/profile/repetition identity differs')
    key = lambda x: (x['profile_id'], x['case_id'], x['stream'])
    expected = {key(j) for j in jobs.values()}
    pairs = {key(p): p for p in summary['repetition_comparisons']}
    if set(pairs) != expected or len(pairs) != len(summary['repetition_comparisons']):
        raise ValueError('Repetition pair grid differs or contains duplicates')
    if any(sorted(p['repetitions']) != [1, 2] for p in pairs.values()):
        raise ValueError('Each repetition pair must contain exactly repetitions 1 and 2')


def validate_worker(result, job):
    worker = result['worker']
    samples = round(job['duration_sec'] * job['source_sample_rate'])
    if worker['status'] != 'COMPLETE' or worker['job_key'] != job['job_key']:
        raise ValueError('Completed worker identity/status differs')
    if not worker['native_pcm_exact'] or not worker['asr_cursor_complete']:
        raise ValueError('Completed worker delivery validation failed')
    if worker['source_duration_sec'] != job['duration_sec'] or worker['complete_pcm_samples'] != samples:
        raise ValueError('Completed worker did not consume the exact whole source')
    if worker['journal']['sha256'] != job['input_pcm_sha256'] or worker['journal']['bytes'] != samples * 2:
        raise ValueError('Worker journal differs from expected admitted PCM body')


def validate_trajectory(result, path):
    rows = [r for r in result['artifacts'] if Path(r['path']).name == 'PROCESS_SAMPLES.jsonl']
    if len(rows) != 1:
        raise ValueError('Exactly one original trajectory binding is required')
    actual = binding(path)
    if any(actual[k] != rows[0][k] for k in ('sha256', 'bytes')):
        raise ValueError('Final trajectory copy differs from its original completed binding')
    return actual


def validate_namespace_counts(rows):
    if [(r['fresh_complete'], r['interrupted'], r['copied_receipt_references']) for r in rows] != [(2, 1, 0), (22, 1, 2), (11, 1, 24), (29, 0, 35)]:
        raise ValueError('Namespace physical/reuse split differs from reviewed admission')


NAMESPACE_NAMES = tuple('paced_finalists_epoch2_v' + str(i) for i in range(1, 5))
OBSERVER_NAMES = ('read_retry_overlay_v1_run1', 'live_reader_overlay_v2_run1', 'optional_live_overlay_v3_run1')
OBSERVER_WRAPPERS = ('s6b_paced_read_retry_v1.py', 's6b_paced_live_reader_v2.py', 's6b_paced_optional_live_v3.py')


def verify_historical_reporter():
    prior = binding(Path(__file__).with_name('s6b_paced_closure.py'))
    if prior['sha256'] != HISTORICAL_REPORTER_SHA256:
        raise ValueError('Preserved historical closure reporter changed')
    return prior


def finite_nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Expected finite nonnegative ' + name)
    return value


def validate_expected_plan(manifest):
    jobs = manifest['jobs']
    if len(jobs) != 64 or len({j['job_key'] for j in jobs}) != 64:
        raise ValueError('Expected 64 unique native job keys')
    cases = {j['case_id'] for j in jobs}
    expected = set(product(('B00', 'B36', 'B10', 'B17'), cases, ('O0', 'O1'), (1, 2)))
    actual = [(j['profile_id'], j['case_id'], j['stream'], j['repetition']) for j in jobs]
    if len(cases) != 4 or len(set(actual)) != 64 or set(actual) != expected:
        raise ValueError('Expected exact four-profile/four-case/two-tap/two-repeat factorial')
    if not math.isclose(sum(j['duration_sec'] for j in jobs), manifest['total_audio_sec'], abs_tol=1e-7):
        raise ValueError('Manifest total audio duration differs from all 64 cells')


def validate_launch(launch, job, namespace, driver_path):
    if launch['job_key'] != job['job_key']:
        raise ValueError('Launch native identity differs')
    argv = launch['argv']
    if len(argv) != 10 or Path(argv[1]).resolve() != Path(driver_path).resolve():
        raise ValueError('Native worker argv is not the exact original driver form')
    options = dict(zip(argv[2::2], argv[3::2]))
    if set(options) != {'--mode', '--manifest', '--job-id', '--timeout'} or len(options) != 4:
        raise ValueError('Unexpected or duplicate native worker options')
    if options['--mode'] != 'worker' or options['--job-id'] != job['job_id']:
        raise ValueError('Native worker mode or source identity differs')
    if Path(options['--manifest']).resolve() != (namespace / 'MANIFEST.json').resolve():
        raise ValueError('Native worker used another namespace manifest')
    if finite_nonnegative(float(options['--timeout']), 'worker timeout') == 0:
        raise ValueError('Worker timeout must be positive')


def validate_attempt_grid(attempts, jobs):
    successes = Counter(x['job_id'] for x in attempts if x['status'] == 'COMPLETE')
    if successes != Counter(j['job_id'] for j in jobs):
        raise ValueError('Every logical job needs exactly one fresh successful physical attempt')
    if Counter(x['status'] for x in attempts) != {'COMPLETE': 64, 'INTERRUPTED': 3}:
        raise ValueError('Expected 64 successful plus three interrupted physical attempts')


def trajectory_observations(samples, job):
    """Describe stored observations only; never backfill missing LIVE/tree data."""
    times = [finite_nonnegative(x['elapsed_sec'], 'sample elapsed time') for x in samples]
    gaps = [b-a for a,b in zip(times,times[1:])]
    if any(g <= 0 for g in gaps):
        raise ValueError('Non-increasing process observer trajectory')
    counts, phases = Counter(), Counter()
    backlogs = {'asr': [], 'speaker': []}
    backlog_times = {'asr': [], 'speaker': []}
    coordinator = []
    tree_metrics = {k: [] for k in ('private_resident_uss_sum_bytes', 'rss_sum_upper_bound_bytes',
        'windows_private_commit_sum_bytes', 'pss_sum_bytes', 'full_tree_threads')}
    for sample in samples:
        live = sample.get('live')
        if live is None:
            counts['live_missing_samples'] += 1
            phases['LIVE_NULL'] += 1
        elif not isinstance(live, dict):
            raise ValueError('Stored LIVE must be a JSON object or explicit null')
        else:
            counts['live_object_observed_samples'] += 1
            phases[str(live.get('phase', 'LIVE_OBJECT_PHASE_UNAVAILABLE'))] += 1
        telemetry = (live or {}).get('telemetry')
        if telemetry is not None and not isinstance(telemetry, dict):
            raise ValueError('Stored telemetry must be an object or absent/null')
        if telemetry:
            counts['telemetry_object_observed_samples'] += 1
        else:
            counts['telemetry_missing_samples'] += 1
            if live is not None:
                counts['live_object_without_telemetry_samples'] += 1
        for label, cursor in (('asr', 'asr_cursor_sec'), ('speaker', 'speaker_cursor_sec')):
            if telemetry and telemetry.get('source_duration_sec') is not None and telemetry.get(cursor) is not None:
                source = finite_nonnegative(telemetry['source_duration_sec'], 'source cursor')
                value = finite_nonnegative(telemetry[cursor], cursor)
                backlogs[label].append(max(0., source-value))
                backlog_times[label].append(sample['elapsed_sec'])
        tree = sample.get('tree')
        if tree is None:
            counts['process_tree_missing_samples'] += 1
        elif not isinstance(tree, dict):
            raise ValueError('Stored process tree must be an object or absent/null')
        elif tree.get('tree_complete') is True and not tree.get('unreadable_pids') and tree.get('processes'):
            counts['process_tree_complete_samples'] += 1
            for key in tree_metrics:
                value = tree.get(key)
                if value is not None:
                    tree_metrics[key].append(finite_nonnegative(value, key))
        else:
            counts['process_tree_partial_samples'] += 1
        rss = sample.get('coordinator_rss_bytes')
        if rss is not None:
            coordinator.append(finite_nonnegative(rss, 'separate coordinator RSS'))
    n = len(samples)
    def backlog(label):
        values, when = backlogs[label], backlog_times[label]
        return {'observed_samples': len(values), 'missing_samples': n-len(values),
            'observed_fraction_of_stored_samples': len(values)/n if n else None,
            'observed_sample_max_sec': max(values) if values else None,
            'observed_sample_last_sec': values[-1] if values else None,
            'observed_sample_first_elapsed_sec': when[0] if when else None,
            'observed_sample_last_elapsed_sec': when[-1] if when else None,
            'complete_stored_grid_max_sec': max(values) if values and len(values)==n else None,
            'whole_time_max_sec': None,
            'scope': 'Stored snapshots only. Missing samples are not zero or prior values. No continuous-time maximum is established, even with a complete stored grid.'}
    fields = ('live_missing_samples','live_object_observed_samples','telemetry_object_observed_samples',
        'telemetry_missing_samples','live_object_without_telemetry_samples','process_tree_missing_samples',
        'process_tree_complete_samples','process_tree_partial_samples')
    result = {k: job[k] for k in ('job_id','profile_id','case_id','stream','repetition')}
    result.update(stored_trajectory_samples=n, **{k: counts[k] for k in fields},
        live_phase_sample_counts=dict(phases),
        sample_first_elapsed_sec=times[0] if times else None, sample_last_elapsed_sec=times[-1] if times else None,
        sample_gaps_sec=ranges(gaps), gaps_over_0_75_sec=sum(g>.75 for g in gaps), samples_interpolated=0,
        asr_backlog=backlog('asr'), speaker_backlog=backlog('speaker'),
        complete_process_tree_observed_metrics={k:ranges(v) for k,v in tree_metrics.items()},
        coordinator_rss_bytes=ranges(coordinator),
        process_scope='Tree metric ranges use stored sampler-complete flags. Native sample_tree can fall back to root-only after descendant enumeration failure without clearing that flag, so exhaustive OS descendant coverage is not independently proven. Coordinator RSS is separate. Partial trees stay counted; sampled CPU is a lower bound.')
    return result


def validate_optional_observer(stats, events, jobs, namespace, verify_raw=verify):
    """Check missing-read counts and the preceding retained full-byte events."""
    calls = stats['live_calls_by_path']; missing = stats['missing_live_json_by_path']
    if not isinstance(calls,dict) or not isinstance(missing,dict):
        raise ValueError('Expected per-path observer dictionaries')
    for value in list(calls.values())+list(missing.values()):
        if isinstance(value,bool) or not isinstance(value,int) or value < 0:
            raise ValueError('Observer counters must be nonnegative integers')
    if sum(calls.values()) != stats['live_calls'] or sum(missing.values()) != stats['missing_live_json_calls']:
        raise ValueError('Observer totals and pathwise denominators differ')
    allowed = {str((namespace/'jobs'/j['job_id']/'LIVE.json').resolve()):j for j in jobs}
    if set(calls)-set(allowed) or set(missing)-set(calls):
        raise ValueError('Observer path falls outside final admitted LIVE paths')
    if any(missing.get(p,0)>count for p,count in calls.items()):
        raise ValueError('Missing reads exceed actual read calls')
    retained, failures, missing_events, unique_raw = defaultdict(list), {}, {}, {}
    failed_count = 0
    for event in events:
        kind = event.get('event')
        if kind == 'live_snapshot_retained' and event.get('raw_binding'):
            raw = event['raw_binding']
            if ('bytes' in event and raw['bytes'] != event['bytes']) or ('sha256' in event and raw['sha256'] != event['sha256']):
                raise ValueError('Retained full-byte metadata differs from snapshot identity')
            verify_raw(raw)
            if raw['path'] in unique_raw:
                raise ValueError('Duplicate retained snapshot file event')
            unique_raw[raw['path']] = raw
            retained[event['call']].append(event)
        elif kind == 'live_snapshot_failed':
            failed_count += 1
            if event['call'] in failures:
                raise ValueError('Duplicate failed LIVE call')
            failures[event['call']] = event
        elif kind == 'optional_live_json_missing':
            call = event['base_call_number']
            if call in missing_events or event.get('sample_value','absent') is not None:
                raise ValueError('Missing LIVE event repeats or is not explicit null')
            failure = failures.get(call)
            rows = retained.get(call,[])
            if not failure or failure['error_type'] != 'JSONDecodeError' or failure['path'] != event['path']:
                raise ValueError('Missing LIVE requires an earlier matching JSON failure')
            if len(rows)<2 or any(x.get('truncated') is not False or 'sha256' not in x or 'bytes' not in x for x in rows[-2:]):
                raise ValueError('Missing LIVE lacks complete retained raw snapshots')
            if any(x['path']!=event['path'] for x in rows) or rows[-1]['sha256']!=rows[-2]['sha256']:
                raise ValueError('Terminal stable malformed pair is not retained exactly')
            missing_events[call] = event
    observed = Counter(x['path'] for x in missing_events.values())
    if observed != Counter({k:v for k,v in missing.items() if v}):
        raise ValueError('Missing-event counts differ from observer summary')
    if failed_count != stats['failed_calls'] or stats['failed_calls'] != stats['missing_live_json_calls']:
        raise ValueError('Successful final observer has unexplained terminal LIVE failure')
    if len(unique_raw)!=stats['captured_snapshots'] or sum(x['bytes'] for x in unique_raw.values())!=stats['captured_bytes']:
        raise ValueError('Retained snapshot totals differ from observer stats')
    rows=[]
    for path,count in sorted(calls.items()):
        job=allowed[path]
        rows.append({k:job[k] for k in ('job_id','profile_id','case_id','stream','repetition')} | {
            'path':path,'live_read_calls':count,'missing_json_read_calls':missing.get(path,0),
            'nonmissing_read_calls':count-missing.get(path,0),
            'scope':'Final optional observer read calls; distinct from trajectory rows and native failures.'})
    return {'by_job':rows,'live_read_calls':sum(calls.values()),'missing_json_read_calls':sum(missing.values()),
        'retained_raw_snapshot_bindings':list(unique_raw.values()),'retained_json_failure_precedes_every_missing_event':True,
        'failed_calls_interpretation':'Retained JSON failures mapped to missing observations; never failed native sessions.'}


def attach_optional_counts(observations, optional_rows):
    by_id={x['job_id']:x for x in optional_rows}
    for row in observations:
        calls=by_id.get(row['job_id'])
        missing=calls['missing_json_read_calls'] if calls else None
        if missing is not None and missing>row['live_missing_samples']:
            raise ValueError('Explicit optional missing reads exceed null trajectory samples')
        row['optional_live_read_calls']=calls['live_read_calls'] if calls else None
        row['explicit_malformed_live_missing_read_calls']=missing
        row['other_null_live_samples']=row['live_missing_samples']-missing if missing is not None else None
        row['null_live_scope']='Null LIVE can include status not created yet. Explicit malformed read counts are separately instrumented only in observer V3. No per-row reason is invented.'


def group_observations(observations, optional_rows):
    groups=defaultdict(list);calls=defaultdict(list)
    for row in observations:groups[row['profile_id'],row['stream']].append(row)
    for row in optional_rows:calls[row['profile_id'],row['stream']].append(row)
    answer=[]
    counts=('stored_trajectory_samples','live_missing_samples','live_object_observed_samples',
        'telemetry_object_observed_samples','telemetry_missing_samples','live_object_without_telemetry_samples',
        'process_tree_missing_samples','process_tree_complete_samples','process_tree_partial_samples','gaps_over_0_75_sec')
    for key,rows in sorted(groups.items()):
        total={k:sum(x[k] for x in rows) for k in counts};n=total['stored_trajectory_samples'];phases=Counter()
        for row in rows:phases.update(row['live_phase_sample_counts'])
        total.update(profile_id=key[0],stream=key[1],completed_cells=len(rows),
            live_phase_sample_counts=dict(phases),
            live_observed_fraction=total['live_object_observed_samples']/n if n else None,
            complete_tree_fraction=total['process_tree_complete_samples']/n if n else None,
            optional_observer_cells_with_read_counters=len(calls[key]),
            optional_observer_live_read_calls=sum(x['live_read_calls'] for x in calls[key]),
            optional_observer_missing_json_read_calls=sum(x['missing_json_read_calls'] for x in calls[key]),
            legacy_observer_pathwise_missing_json_calls=None,
            legacy_missing_scope='Earlier pathwise malformed-read counters were uninstrumented, not zero.',
            asr_backlog_observed_sample_max_sec=ranges([x['asr_backlog']['observed_sample_max_sec'] for x in rows]),
            speaker_backlog_observed_sample_max_sec=ranges([x['speaker_backlog']['observed_sample_max_sec'] for x in rows]),
            whole_time_backlog_max_sec=None)
        for label in ('asr','speaker'):
            observed=sum(x[label+'_backlog']['observed_samples'] for x in rows)
            total[label+'_backlog_observed_samples']=observed
            total[label+'_backlog_missing_samples']=n-observed
        answer.append(total)
    return answer


def write_observation_csv(path, rows):
    fields=('job_id','profile_id','case_id','stream','repetition','stored_trajectory_samples',
        'live_object_observed_samples','live_missing_samples','live_object_without_telemetry_samples',
        'telemetry_object_observed_samples','telemetry_missing_samples','process_tree_complete_samples',
        'process_tree_partial_samples','process_tree_missing_samples','gaps_over_0_75_sec',
        'optional_live_read_calls','explicit_malformed_live_missing_read_calls','other_null_live_samples')
    flat=[]
    for row in rows:
        item={k:row[k] for k in fields}
        for label in ('asr','speaker'):
            for key in ('observed_samples','missing_samples','observed_sample_max_sec'):
                item[label+'_backlog_'+key]=row[label+'_backlog'][key]
        item['coordinator_rss_peak_bytes']=row['coordinator_rss_bytes']['max']
        item['whole_time_backlog_max_sec']=None
        item['live_phase_sample_counts_json']=json.dumps(row['live_phase_sample_counts'],sort_keys=True)
        flat.append(item)
    if not flat:
        raise ValueError('Refuse empty observation table')
    with path.open('x',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)


def observation_markdown(groups, optional):
    lines=['','## Observed and missing telemetry','',
        '| Profile/tap | Stored samples | LIVE observed/null | Observed LIVE without telemetry | ASR backlog observed/missing |',
        '|---|---:|---:|---:|---:|']
    for row in groups:
        lines.append(f"| {row['profile_id']}/{row['stream']} | {row['stored_trajectory_samples']} | {row['live_object_observed_samples']}/{row['live_missing_samples']} | {row['live_object_without_telemetry_samples']} | {row['asr_backlog_observed_samples']}/{row['asr_backlog_missing_samples']} |")
    lines += ['',f"Final optional observer: {optional['missing_json_read_calls']} explicit malformed JSON reads represented as missing, out of {optional['live_read_calls']} admitted LIVE read calls. These are not counts of null startup rows or native failures.",'',
        'JSON and PACED_OBSERVATION_COVERAGE.csv retain exact per-cell denominators and phases. Observed backlog peaks are sampled values, never proven continuous-time maxima. No interpolation. Complete native process-tree observations and coordinator RSS are separate. Interrupted partial trajectories do not enter successful-cell ranges.','']
    return lines


# The historical source pin below is immutable.
HISTORICAL_REPORTER_SHA256 = '1c65b2514c0dc6b79e9ba3960256340bc7bead0f836cb46ed6ebf627a59b9e85'

def run(args):
    historical_reporter = verify_historical_reporter()
    for observer_root in args.observer_roots:
        launch = read(observer_root / 'LAUNCH.json')
        if not closed(launch['pid'], launch['creation_time']):
            raise RuntimeError('Observer still running: final aggregation is forbidden')
    summary = read(args.final / 'SUMMARY.json')
    manifest = read(args.final / 'MANIFEST.json')
    validate_expected_plan(manifest)
    validate_grid(summary, manifest, binding(args.final / 'MANIFEST.json'))
    if summary['status'] != 'COMPLETE' or summary['completed_jobs'] != 64 or summary['expected_jobs'] != 64:
        raise RuntimeError('Final 64-cell paced summary is not complete')
    if not all(row['no_pcm_loss'] and row['asr_cursor_complete'] and row['all_owned_processes_closed'] for row in summary['rows']):
        raise ValueError('A final delivery or closure check failed')
    if len(summary['rows']) != 64 or len(summary['repetition_comparisons']) != 32:
        raise ValueError('Final row/repetition grid is incomplete')
    verify(summary['manifest'])
    paths = [Path(p).resolve() for p in args.namespaces]
    if len(set(paths)) != 4 or paths[-1] != args.final.resolve():
        raise ValueError('Expected four ordered distinct namespaces ending at final')
    if tuple(p.name for p in paths) != NAMESPACE_NAMES:
        raise ValueError('Namespaces must be reviewed ordered v1/v2/v3/v4')
    if tuple(p.name for p in args.observer_roots) != OBSERVER_NAMES:
        raise ValueError('Observer roots must be reviewed ordered v1/v2/v3')
    target = args.output.resolve()
    if any(target == p or p in target.parents for p in paths + [x.resolve() for x in args.observer_roots]):
        raise ValueError('New report must be outside preserved source namespaces')
    attempts, artifacts, process_rows, namespace_counts = {}, {}, [], []
    interrupted_observations = []
    for root in paths:
        if read(root / 'MANIFEST.json')['jobs'] != manifest['jobs']:
            raise ValueError('Historical native job plan differs')
        process_rows += process_closure(root)
        launches = list((root / 'jobs').glob('*/LAUNCH.json'))
        complete_files = list((root / 'jobs').glob('*/COMPLETE.json'))
        faults = list((root / 'jobs').glob('*/FAILURE.json'))
        fresh_complete = 0
        for path in launches:
            launch = read(path)
            key = (launch['pid'], launch['creation_time'])
            if key in attempts:
                raise ValueError('Duplicate physical launch identity')
            job = next(j for j in manifest['jobs'] if j['job_id'] == path.parent.name)
            validate_launch(launch, job, root, manifest['driver']['path'])
            success = path.with_name('COMPLETE.json').exists()
            failure = path.with_name('FAILURE.json').exists()
            if success == failure:
                raise ValueError('Physical attempt requires exactly one complete/failure result')
            fresh_complete += int(success)
            attempts[key] = {'job_id': job['job_id'], 'job_key': job['job_key'], 'namespace': str(root),
                             'pid': key[0], 'creation_time': key[1], 'status': 'COMPLETE' if success else 'INTERRUPTED',
                             'launch': binding(path), 'result': binding(path.with_name('COMPLETE.json' if success else 'FAILURE.json'))}
        launched_ids = {p.parent.name for p in launches}
        if any(p.parent.name not in launched_ids for p in faults):
            raise ValueError('Interrupted result without physical launch')
        for fault in faults:
            trace = fault.with_name('PROCESS_SAMPLES.jsonl')
            rows = [json.loads(x) for x in trace.read_text(encoding='utf-8').splitlines() if x.strip()]
            job = next(j for j in manifest['jobs'] if j['job_id'] == fault.parent.name)
            interrupted_observations.append(trajectory_observations(rows, job) | {'namespace':str(root), 'status':'INTERRUPTED_PARTIAL_ONLY', 'trajectory':binding(trace)})
        namespace_counts.append({'namespace': str(root), 'physical_attempts': len(launches),
                                 'fresh_complete': fresh_complete, 'interrupted': len(faults),
                                 'logical_complete_receipts': len(complete_files),
                                 'copied_receipt_references': len(complete_files) - fresh_complete})
    validate_namespace_counts(namespace_counts)
    validate_attempt_grid(list(attempts.values()), manifest['jobs'])
    for job in manifest['jobs']:
        out = args.final / 'jobs' / job['job_id']
        result = read(out / 'COMPLETE.json')
        if result['status'] != 'COMPLETE' or result['job_key'] != job['job_key']:
            raise ValueError('Final completion identity differs')
        validate_worker(result, job)
        for row in result['artifacts']:
            verify(row)
            artifacts[row['path']] = row
        artifacts[str(out / 'COMPLETE.json')] = binding(out / 'COMPLETE.json')
        artifacts[str(out / 'PROCESS_SAMPLES.jsonl')] = validate_trajectory(result, out / 'PROCESS_SAMPLES.jsonl')
    if Counter(x['status'] for x in attempts.values()) != {'COMPLETE': 64, 'INTERRUPTED': 3}:
        raise ValueError('Expected 64 successful physical sessions and three preserved interruptions')

    # Observer counters remain separate; they never count copied completions as inference.
    observers = []
    for observer_index, root in enumerate(args.observer_roots):
        launch, completion = read(root / 'LAUNCH.json'), read(root / 'COMPLETION.json')
        if not closed(launch['pid'], launch['creation_time']):
            raise RuntimeError('Observer coordinator still alive')
        verify(completion['launch'])
        verify(completion['events'])
        verify(launch['driver'])
        verify(launch['wrapper'])
        if Path(launch['wrapper']['path']).name != OBSERVER_WRAPPERS[observer_index]:
            raise ValueError('Observer wrapper version/order differs')
        if launch['driver'] != manifest['driver']:
            raise ValueError('Observer refers to different native driver')
        if completion['status'] != ('COMPLETE' if observer_index == 2 else 'FAILED'):
            raise ValueError('Observer status differs from reviewed chain')
        observers.append({'root': str(root), 'launch': binding(root / 'LAUNCH.json'),
                          'completion': binding(root / 'COMPLETION.json'), 'stats': completion['stats'],
                          'status': completion['status'], 'pid': launch['pid'], 'creation_time': launch['creation_time'], 'closed_now': True})
    if observers[-1]['status'] != 'COMPLETE':
        raise RuntimeError('Final observer did not close successfully')
    optional_events = [json.loads(x) for x in Path(read(args.observer_roots[-1] / 'COMPLETION.json')['events']['path']).read_text(encoding='utf-8').splitlines() if x.strip()]
    optional_coverage = validate_optional_observer(observers[-1]['stats'], optional_events, manifest['jobs'], paths[-1])
    groups = defaultdict(list)
    for row in summary['rows']:
        groups[(row['profile_id'], row['stream'])].append(row)
    metrics = ('full_worker_elapsed_sec', 'startup_bundle_sec', 'startup_engine_launch_sec', 'process_cpu_sec',
               'private_resident_uss_peak_bytes', 'rss_sum_upper_bound_peak_bytes', 'windows_private_commit_peak_bytes',
               'pss_peak_bytes', 'nonunique_shared_resident_estimate_peak_bytes', 'peak_full_tree_threads',
               'process_write_bytes', 'process_write_bytes_per_audio_second', 'application_artifact_bytes',
               'minimum_host_available_ram_bytes', 'full_tree_cpu_sampled_lower_bound_sec')
    comparisons = []
    for (profile, stream), rows in sorted(groups.items()):
        comparisons.append({'profile_id': profile, 'stream': stream, 'cells': len(rows),
                            'metrics': {k: ranges([r.get(k) for r in rows]) for k in metrics},
                            'asr_backlog_observed_sample_max_sec': ranges([r['asr_backlog']['max_sec'] for r in rows]),
                            'speaker_backlog_observed_sample_max_sec': ranges([r['speaker_backlog']['max_sec'] for r in rows]),
                            'whole_time_backlog_max_sec': None,
                            'memory_trends': [{k: r.get(k) for k in ('job_id', 'private_resident_uss_trend', 'rss_sum_upper_bound_trend', 'windows_private_commit_trend')} for r in rows],
                            'model_threads': rows[0]['model_threads']})
    sample_gaps = []
    observation_rows = []
    for job in manifest['jobs']:
        path = args.final / 'jobs' / job['job_id'] / 'PROCESS_SAMPLES.jsonl'
        samples = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
        observation = trajectory_observations(samples, job)
        row = next(x for x in summary['rows'] if x['job_id'] == job['job_id'])
        if len(samples) != row['sample_count']:
            raise ValueError('Summary sample denominator differs')
        for label in ('asr', 'speaker'):
            reported, measured = row[label+'_backlog'], observation[label+'_backlog']
            if reported['trajectory_samples'] != measured['observed_samples'] or reported['max_sec'] != measured['observed_sample_max_sec'] or reported['last_sec'] != measured['observed_sample_last_sec']:
                raise ValueError('Summary backlog differs from stored observations')
        observation_rows.append(observation)
        gaps = [b['elapsed_sec'] - a['elapsed_sec'] for a, b in zip(samples, samples[1:])]
        if any(g <= 0 for g in gaps):
            raise ValueError('Non-increasing process observer trajectory')
        sample_gaps.append({'job_id': job['job_id'], 'samples': len(samples), 'gaps_sec': ranges(gaps),
                            'gaps_over_0_75_sec': sum(g > .75 for g in gaps), 'samples_interpolated': 0})
    attach_optional_counts(observation_rows, optional_coverage['by_job'])
    observed_groups = group_observations(observation_rows, optional_coverage['by_job'])
    pids = {(x['pid'], x['creation_time']): x for x in process_rows}
    memory = psutil.virtual_memory()
    storage = {drive: {'total_bytes': psutil.disk_usage(drive).total, 'used_bytes': psutil.disk_usage(drive).used,
                       'free_bytes': psutil.disk_usage(drive).free} for drive in ('C:\\', 'G:\\')}
    pairs = summary['repetition_comparisons']
    parity = {'pairs': len(pairs), **{key: sum(bool(p[key]) for p in pairs) for key in
              ('raw_final_words_exact', 'final_labels_exact', 'complete_native_display_sequence_exact', 'journals_exact')},
              'embedding_comparable_pairs': sum(p['embedding_parity'] is not None for p in pairs),
              'embedding_within_1e_minus_6_pairs': sum(bool((p['embedding_parity'] or {}).get('within_1e_minus_6')) for p in pairs)}
    result = {'schema': 's6b-paced-closure.v2', 'status': 'COMPLETE_VERIFIED', 'created_utc': utc(),
              'logical_completed_cells': 64, 'source_audio_sec_completed': manifest['total_audio_sec'],
              'physical_native_attempts': len(attempts), 'physical_complete': 64, 'physical_interrupted': 3,
              'namespace_counts': namespace_counts, 'attempts': list(attempts.values()), 'observers': observers,
              'manifest': binding(args.final / 'MANIFEST.json'), 'summary': binding(args.final / 'SUMMARY.json'),
              'source': binding(__file__), 'readme': binding(Path(__file__).with_name('README_S6B_PACED_CLOSURE_V2.md')),
              'artifact_bindings': list(artifacts.values()), 'all_owned_processes_closed': True,
              'owned_processes': list(pids.values()), 'profile_stream_resource_ranges': comparisons,
              'sampling_gaps': sample_gaps, 'repetition_parity': parity,
              'observation_coverage_by_job': observation_rows, 'observation_coverage_by_profile_stream': observed_groups,
              'interrupted_partial_observations': interrupted_observations, 'optional_observer_read_accounting': optional_coverage,
              'historical_reporter_source': historical_reporter, 'observer_versions': 4, 'interruptions': 3,
              'all_exact_pcm': all(r['no_pcm_loss'] for r in summary['rows']),
              'all_complete_asr_cursor': all(r['asr_cursor_complete'] for r in summary['rows']),
              'host_closure': {'available_ram_bytes': memory.available, 'total_ram_bytes': memory.total, 'volumes': storage},
              'scope': 'Paced study only. Immutable pre-paced 3936 native/replay checkpoint and eight component smoke sessions are separate.',
              'limitations': ['Four observer versions, three interruption gaps and varying unrelated host activity; resource conditions are not identical.',
                  'Each cell is a fresh process with one resident bundle for its scene; no continuous multi-scene leak claim.',
                  'USS is private resident; RSS sums duplicate shared pages; private commit is virtual commitment; PSS null means unavailable.',
                  'Configured model threads do not equal total OS thread count. No CM5 throughput, 2 GB fit or thermal qualification.',
                  'B00 has no internal per-dispatch trace. Exact full PCM, journal/cursor and durable completion checks are its delivery evidence.',
                  'Modeled scheduler availability, native event emission and GUI/phonetic latency remain distinct.',
                  'All repetitions retained; changed words, labels or vectors are observations, never accuracy retry criteria.',
                  'Observer double reads and retries may delay sampling; gaps are measured without interpolation.',
                  'Null LIVE, observed LIVE without telemetry, and explicit malformed JSON read events are separate denominators.',
                  'Observed backlog peaks are retained; missing telemetry has no imputed value and whole-time maxima remain unavailable.',
                  'Tree metrics use sampler-complete flags. Root-only fallback after OS descendant enumeration failure is not flagged by the frozen sampler, so exhaustive descendant coverage is not independently proven.',
                  'Separate coordinator RSS and interrupted partial trajectories are explicit.']}
    args.output.mkdir(parents=True, exist_ok=False)
    write_observation_csv(args.output / 'PACED_OBSERVATION_COVERAGE.csv', observation_rows)
    result['observation_table'] = binding(args.output / 'PACED_OBSERVATION_COVERAGE.csv')
    write_new(args.output / 'PACED_CLOSURE.json', result)
    lines = ['# S6B paced closure', '', f"64 logical cells completed in {len(attempts)} physical native attempts: 64 complete, three preserved interruptions.",
             'The source plan covers four fixed whole scenes, both O0/O1 taps and two balanced repetitions for B00/B36/B10/B17.', '',
             '| Namespace | Fresh complete | Interrupted | Copied references |', '|---|---:|---:|---:|']
    lines += [f"| {Path(x['namespace']).name} | {x['fresh_complete']} | {x['interrupted']} | {x['copied_receipt_references']} |" for x in namespace_counts]
    lines += ['', 'All final PCM/journal and ASR cursor checks passed; all owned process identities are closed.', '',
              f"Repetition pairs: {len(pairs)}. Exact final words {parity['raw_final_words_exact']}; exact final labels {parity['final_labels_exact']}; exact full display sequence {parity['complete_native_display_sequence_exact']}; exact journals {parity['journals_exact']}.", '',
              '| Profile/tap | USS peak MiB range | RSS peak MiB range | Private commit MiB range | OS thread peak range |', '|---|---:|---:|---:|---:|']
    def span(row, key, factor=1):
        m = row['metrics'][key]
        return 'unavailable' if not m['count'] else f"{m['min']/factor:.2f}–{m['max']/factor:.2f}"
    for row in comparisons:
        lines.append(f"| {row['profile_id']}/{row['stream']} | {span(row,'private_resident_uss_peak_bytes',1048576)} | {span(row,'rss_sum_upper_bound_peak_bytes',1048576)} | {span(row,'windows_private_commit_peak_bytes',1048576)} | {span(row,'peak_full_tree_threads')} |")
    lines += observation_markdown(observed_groups, optional_coverage)
    lines += ['- ' + text for text in result['limitations']]
    (args.output / 'PACED_CLOSURE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'logical_cells': 64, 'physical_attempts': len(attempts),
                      'parity': parity, 'output': str(args.output)}, indent=2))


def extra_checks(root, checks, rejected):
    job={'job_id':'fixture','profile_id':'B17','case_id':'case','stream':'O0','repetition':1}
    def sample(t,live,complete=True):
        return {'elapsed_sec':t,'live':live,'tree':{'tree_complete':complete,
            'unreadable_pids':[] if complete else [2],'processes':[{'pid':1}],
            'private_resident_uss_sum_bytes':100 if complete else None,
            'rss_sum_upper_bound_bytes':150 if complete else None,
            'windows_private_commit_sum_bytes':200 if complete else None,
            'pss_sum_bytes':None,'full_tree_threads':3},'coordinator_rss_bytes':50}
    live={'phase':'paced_source','telemetry':{'source_duration_sec':2.,'asr_cursor_sec':1.,'speaker_cursor_sec':.5}}
    loading={'phase':'model_loading','telemetry':None}
    obs=trajectory_observations([sample(0,None),sample(.5,loading),sample(1,live),sample(2,None,False)],job)
    assert obs['live_missing_samples']==2 and obs['asr_backlog']['observed_sample_max_sec']==1.
    assert obs['asr_backlog']['missing_samples']==3 and obs['asr_backlog']['complete_stored_grid_max_sec'] is None
    assert obs['asr_backlog']['whole_time_max_sec'] is None and obs['gaps_over_0_75_sec']==1
    assert obs['live_object_without_telemetry_samples']==1 and obs['live_phase_sample_counts']['model_loading']==1
    checks.append('null LIVE, observed loading object and valid backlog have separate denominators and phases')
    assert obs['process_tree_complete_samples']==3 and obs['process_tree_partial_samples']==1
    assert obs['complete_process_tree_observed_metrics']['pss_sum_bytes']['count']==0
    assert obs['coordinator_rss_bytes']['max']==50 and obs['complete_process_tree_observed_metrics']['rss_sum_upper_bound_bytes']['max']==150
    checks.append('complete native tree and coordinator RSS stay separate; unavailable PSS remains null')
    empty=trajectory_observations([],job)
    assert empty['asr_backlog']['observed_sample_max_sec'] is None and empty['sample_gaps_sec']['count']==0
    checks.append('empty interrupted trajectory has unavailable observations rather than zero backlog')
    all_observed=trajectory_observations([sample(0,live),sample(.5,live)],job)
    assert all_observed['asr_backlog']['complete_stored_grid_max_sec']==1. and all_observed['asr_backlog']['whole_time_max_sec'] is None
    checks.append('complete stored grid still does not claim continuous-time maximum')
    rejected(lambda:trajectory_observations([sample(1,live),sample(1,live)],job),'nonincreasing actual sample clock rejected')
    rejected(lambda:trajectory_observations([sample(float('nan'),live)],job),'nonfinite trajectory clock rejected')
    rejected(lambda:trajectory_observations([sample(0,[])],job),'nonobject LIVE observation rejected')
    bad_live={'telemetry':{'source_duration_sec':2.,'asr_cursor_sec':float('nan'),'speaker_cursor_sec':1.}}
    rejected(lambda:trajectory_observations([sample(0,bad_live)],job),'nonfinite telemetry rejected instead of hidden')
    ns=root/'paced_finalists_epoch2_v4';path=str((ns/'jobs'/'fixture'/'LIVE.json').resolve())
    raw1=root/'bad0.bin';raw2=root/'bad1.bin';raw1.write_bytes(b'{bad}\x00');raw2.write_bytes(raw1.read_bytes())
    rawbindings=[binding(raw1),binding(raw2)]
    events=[{'event':'live_snapshot_retained','call':1,'path':path,'bytes':b['bytes'],'sha256':b['sha256'],
             'truncated':False,'raw_binding':b} for b in rawbindings]
    events += [{'event':'live_snapshot_failed','call':1,'path':path,'error_type':'JSONDecodeError'},
               {'event':'optional_live_json_missing','base_call_number':1,'path':path,'sample_value':None}]
    stats={'live_calls':2,'live_calls_by_path':{path:2},'missing_live_json_by_path':{path:1},
           'missing_live_json_calls':1,'failed_calls':1,'captured_snapshots':2,
           'captured_bytes':sum(b['bytes'] for b in rawbindings)}
    validated=validate_optional_observer(stats,events,[job],ns)
    assert validated['missing_json_read_calls']==1 and validated['live_read_calls']==2
    checks.append('missing JSON requires earlier matching failure and fully retained stable malformed pair')
    metadata_error_file=root/'retained_after_stat_error.bin';metadata_error_file.write_bytes(b'{"valid":1}')
    recovered_events=copy.deepcopy(events)
    for event in recovered_events:
        if 'call' in event:event['call']+=1
        if 'base_call_number' in event:event['base_call_number']+=1
    recovered_events=[{'event':'live_snapshot_retained','call':1,'path':path,'error_type':'PermissionError',
        'raw_binding':binding(metadata_error_file)}, {'event':'live_snapshot_recovered','call':1,'path':path}] + recovered_events
    recovered_stats=copy.deepcopy(stats);recovered_stats['live_calls']=3;recovered_stats['live_calls_by_path'][path]=3
    recovered_stats['captured_snapshots']=3;recovered_stats['captured_bytes']+=metadata_error_file.stat().st_size
    validate_optional_observer(recovered_stats,recovered_events,[job],ns)
    checks.append('retained bytes after metadata-stat error need no absent convenience hash fields; terminal JSON pair remains fully identified')
    bad=copy.deepcopy(events);bad[1].pop('sha256')
    rejected(lambda:validate_optional_observer(stats,bad,[job],ns),'terminal malformed pair missing identity metadata rejected')
    bad=copy.deepcopy(stats);bad['missing_live_json_calls']=2
    rejected(lambda:validate_optional_observer(bad,events,[job],ns),'missing read total mismatch rejected')
    bad=copy.deepcopy(stats);bad['live_calls_by_path']={path:3}
    rejected(lambda:validate_optional_observer(bad,events,[job],ns),'read-call denominator mismatch rejected')
    bad=copy.deepcopy(stats);bad['missing_live_json_by_path']={str(ns/'outside'/'LIVE.json'):1}
    rejected(lambda:validate_optional_observer(bad,events,[job],ns),'unadmitted missing LIVE path rejected')
    rejected(lambda:validate_optional_observer(stats,events[2:],[job],ns),'missing without retained raw evidence rejected')
    bad=copy.deepcopy(events);bad[2]['error_type']='PermissionError'
    rejected(lambda:validate_optional_observer(stats,bad,[job],ns),'non-JSON terminal failure cannot become missing')
    bad=copy.deepcopy(events);bad[-1]['sample_value']={}
    rejected(lambda:validate_optional_observer(stats,bad,[job],ns),'invented replacement observation rejected')
    bad=copy.deepcopy(events);bad[0]['truncated']=True
    rejected(lambda:validate_optional_observer(stats,bad,[job],ns),'truncated capture cannot prove full malformed retention')
    rejected(lambda:validate_optional_observer(stats,events+[events[-1]],[job],ns),'duplicate missing event rejected')
    raw1.write_bytes(b'changed')
    rejected(lambda:validate_optional_observer(stats,events,[job],ns),'changed retained raw bytes rejected')
    raw1.write_bytes(raw2.read_bytes())
    attach_optional_counts([obs],validated['by_job'])
    assert obs['explicit_malformed_live_missing_read_calls']==1 and obs['other_null_live_samples']==1
    attach_optional_counts([all_observed],[])
    assert all_observed['explicit_malformed_live_missing_read_calls'] is None
    checks.append('explicit malformed count separated from other nulls; uninstrumented earlier versions stay null')
    grouped=group_observations([obs],validated['by_job'])
    assert grouped[0]['stored_trajectory_samples']==4 and grouped[0]['optional_observer_live_read_calls']==2
    assert grouped[0]['legacy_observer_pathwise_missing_json_calls'] is None
    checks.append('grouped trajectory and read-call denominators remain distinct')
    write_observation_csv(root/'OBSERVATION_FIXTURE.csv',[obs])
    with (root/'OBSERVATION_FIXTURE.csv').open(encoding='utf-8',newline='') as handle:
        csvrow=next(csv.DictReader(handle))
    assert csvrow['whole_time_backlog_max_sec']=='' and csvrow['explicit_malformed_live_missing_read_calls']=='1'
    checks.append('compact CSV preserves missing maxima and explicit malformed count')
    nativejob=dict(job,job_key='key')
    launch={'job_key':'key','argv':['python.exe',str(root/'driver.py'),'--mode','worker',
        '--manifest',str(ns/'MANIFEST.json'),'--job-id','fixture','--timeout','300']}
    validate_launch(launch,nativejob,ns,root/'driver.py');checks.append('exact original native child argv accepted')
    bad=copy.deepcopy(launch);bad['argv'][3]='run'
    rejected(lambda:validate_launch(bad,nativejob,ns,root/'driver.py'),'coordinator mode cannot count as native worker')
    bad=copy.deepcopy(launch);bad['argv'][5]=str(root/'foreign.json')
    rejected(lambda:validate_launch(bad,nativejob,ns,root/'driver.py'),'foreign native manifest argv rejected')
    bad=copy.deepcopy(launch);bad['argv']+=['--mode','worker']
    rejected(lambda:validate_launch(bad,nativejob,ns,root/'driver.py'),'duplicate native CLI option rejected')
    all_jobs=[{'job_id':str(i),'job_key':str(i),'profile_id':p,'case_id':c,'stream':t,'repetition':n,'duration_sec':1.}
        for i,(p,c,t,n) in enumerate(product(('B00','B36','B10','B17'),('a','b','c','d'),('O0','O1'),(1,2)))]
    validate_expected_plan({'jobs':all_jobs,'total_audio_sec':64.});checks.append('complete scientific factorial accepted')
    bad=copy.deepcopy(all_jobs);bad[0]['job_key']=bad[1]['job_key']
    rejected(lambda:validate_expected_plan({'jobs':bad,'total_audio_sec':64.}),'duplicate native job key rejected')
    attempts=[{'job_id':j['job_id'],'status':'COMPLETE'} for j in all_jobs]+[{'job_id':'0','status':'INTERRUPTED'} for _ in range(3)]
    validate_attempt_grid(attempts,all_jobs);checks.append('64 successful plus three interrupted attempts accepted')
    bad=copy.deepcopy(attempts);bad[1]['job_id']=bad[0]['job_id']
    rejected(lambda:validate_attempt_grid(bad,all_jobs),'duplicate successful job cannot substitute another logical completion')


def check(root):
    verify_historical_reporter()
    root.mkdir(parents=True, exist_ok=False)
    bound = {'path': 'fixture-manifest', 'sha256': 'a' * 64, 'bytes': 1}
    jobs = [{'job_id': f'{p}_{n}', 'profile_id': p, 'case_id': 'case', 'stream': 'O0', 'repetition': n} for p in ('A', 'B') for n in (1, 2)]
    manifest = {'jobs': jobs}
    summary = {'manifest': bound, 'rows': copy.deepcopy(jobs),
               'repetition_comparisons': [{'profile_id': p, 'case_id': 'case', 'stream': 'O0', 'repetitions': [1, 2]} for p in ('A', 'B')]}
    checks = []
    def rejected(fn, name):
        try:
            fn()
        except ValueError:
            checks.append(name)
            return
        raise AssertionError(name)
    validate_grid(summary, manifest, bound)
    checks.append('valid unique summary and repetition grid accepted')
    bad = copy.deepcopy(summary); bad['rows'][1] = bad['rows'][0]
    rejected(lambda: validate_grid(bad, manifest, bound), 'duplicate summary row rejected despite same length')
    bad = copy.deepcopy(summary); bad['rows'][0]['stream'] = 'O1'
    rejected(lambda: validate_grid(bad, manifest, bound), 'misassigned summary source identity rejected')
    bad = copy.deepcopy(summary); bad['repetition_comparisons'][1] = bad['repetition_comparisons'][0]
    rejected(lambda: validate_grid(bad, manifest, bound), 'duplicate repetition pair rejected despite same length')
    bad = copy.deepcopy(summary); bad['repetition_comparisons'][0]['repetitions'] = [1, 1]
    rejected(lambda: validate_grid(bad, manifest, bound), 'wrong repetition membership rejected')
    rejected(lambda: validate_grid(summary, manifest, dict(bound, path='other-manifest')), 'wrong final manifest path rejected')
    job = {'job_key': 'k', 'duration_sec': 1., 'source_sample_rate': 16000, 'input_pcm_sha256': 'b' * 64}
    worker = {'status': 'COMPLETE', 'job_key': 'k', 'native_pcm_exact': True, 'asr_cursor_complete': True,
              'source_duration_sec': 1., 'complete_pcm_samples': 16000, 'journal': {'sha256': 'b' * 64, 'bytes': 32000}}
    validate_worker({'worker': worker}, job)
    checks.append('whole-source successful worker accepted')
    for key, value in [('status', 'FAILED'), ('job_key', 'other'), ('native_pcm_exact', False),
                       ('asr_cursor_complete', False), ('source_duration_sec', .5), ('complete_pcm_samples', 1),
                       ('journal', {'sha256': 'c' * 64, 'bytes': 32000})]:
        rejected(lambda k=key, v=value: validate_worker({'worker': dict(worker, **{k: v})}, job), 'worker ' + key + ' mismatch rejected')
    trajectory = root / 'PROCESS_SAMPLES.jsonl'; trajectory.write_bytes(b'{"elapsed_sec":1}\n')
    result = {'artifacts': [binding(trajectory)]}
    validate_trajectory(result, trajectory)
    checks.append('exact copied trajectory accepted')
    trajectory.write_bytes(b'{"elapsed_sec":2}\n')
    rejected(lambda: validate_trajectory(result, trajectory), 'same-length changed trajectory copy rejected')
    counts = [dict(fresh_complete=a, interrupted=b, copied_receipt_references=c) for a, b, c in [(2, 1, 0), (22, 1, 2), (11, 1, 24), (29, 0, 35)]]
    validate_namespace_counts(counts)
    counts[2]['copied_receipt_references'] = 25
    rejected(lambda: validate_namespace_counts(counts), 'incorrect physical/reuse namespace split rejected')
    assert ranges([None, 1, 3, 2]) == {'count': 3, 'min': 1, 'median': 2, 'max': 3}
    checks.append('resource null handling and range projection exact')
    extra_checks(root, checks, rejected)
    receipt = {'status': 'PASS', 'tests': len(checks), 'checks': checks, 'source': binding(__file__),
               'readme': binding(Path(__file__).with_name('README_S6B_PACED_CLOSURE_V2.md')), 'models_started': 0,
               'scope': 'Isolated fixture grid/worker/trajectory/accounting checks; no final aggregation or native input mutation.', 'created_utc': utc()}
    write_new(root / 'CHECK_RECEIPT.json', receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--final', type=Path)
    parser.add_argument('--namespaces', nargs=4)
    parser.add_argument('--observer-roots', nargs=3, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-root', type=Path)
    arguments = parser.parse_args()
    if arguments.check_root:
        check(arguments.check_root)
    else:
        if any(v is None for v in (arguments.final, arguments.namespaces, arguments.observer_roots, arguments.output)):
            parser.error('--final, --namespaces, --observer-roots and --output are required for closure')
        run(arguments)
