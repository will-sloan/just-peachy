"""Closed paced evidence accounting; see README_S6B_PACED_CLOSURE.md."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import copy

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
    if [(r['fresh_complete'], r['interrupted'], r['copied_receipt_references']) for r in rows] != [(2, 1, 0), (22, 1, 2), (40, 0, 24)]:
        raise ValueError('Namespace physical/reuse split differs from reviewed admission')


def run(args):
    summary = read(args.final / 'SUMMARY.json')
    manifest = read(args.final / 'MANIFEST.json')
    validate_grid(summary, manifest, binding(args.final / 'MANIFEST.json'))
    if summary['status'] != 'COMPLETE' or summary['completed_jobs'] != 64 or summary['expected_jobs'] != 64:
        raise RuntimeError('Final 64-cell paced summary is not complete')
    if not all(row['no_pcm_loss'] and row['asr_cursor_complete'] and row['all_owned_processes_closed'] for row in summary['rows']):
        raise ValueError('A final delivery or closure check failed')
    if len(summary['rows']) != 64 or len(summary['repetition_comparisons']) != 32:
        raise ValueError('Final row/repetition grid is incomplete')
    verify(summary['manifest'])
    paths = [Path(p).resolve() for p in args.namespaces]
    if len(set(paths)) != 3 or paths[-1] != args.final.resolve():
        raise ValueError('Expected three ordered distinct namespaces ending at final')
    attempts, artifacts, process_rows, namespace_counts = {}, {}, [], []
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
            if launch['job_key'] != job['job_key']:
                raise ValueError('Launch native identity differs')
            argv = launch['argv']
            if Path(argv[1]).resolve() != Path(manifest['driver']['path']).resolve() or argv[argv.index('--mode') + 1] != 'worker' or argv[argv.index('--job-id') + 1] != job['job_id']:
                raise ValueError('Native worker launch was not the original driver entry point')
            success = path.with_name('COMPLETE.json').exists()
            failure = path.with_name('FAILURE.json').exists()
            if success == failure:
                raise ValueError('Physical attempt requires exactly one complete/failure result')
            fresh_complete += int(success)
            attempts[key] = {'job_id': job['job_id'], 'job_key': job['job_key'], 'namespace': str(root),
                             'pid': key[0], 'creation_time': key[1], 'status': 'COMPLETE' if success else 'INTERRUPTED',
                             'launch': binding(path), 'result': binding(path.with_name('COMPLETE.json' if success else 'FAILURE.json'))}
        namespace_counts.append({'namespace': str(root), 'physical_attempts': len(launches),
                                 'fresh_complete': fresh_complete, 'interrupted': len(faults),
                                 'logical_complete_receipts': len(complete_files),
                                 'copied_receipt_references': len(complete_files) - fresh_complete})
    validate_namespace_counts(namespace_counts)
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
    if Counter(x['status'] for x in attempts.values()) != {'COMPLETE': 64, 'INTERRUPTED': 2}:
        raise ValueError('Expected 64 successful physical sessions and two preserved interruptions')

    # Observer counters remain separate; they never count copied completions as inference.
    observers = []
    for root in args.observer_roots:
        launch, completion = read(root / 'LAUNCH.json'), read(root / 'COMPLETION.json')
        if not closed(launch['pid'], launch['creation_time']):
            raise RuntimeError('Observer coordinator still alive')
        verify(completion['launch'])
        verify(completion['events'])
        verify(launch['driver'])
        verify(launch['wrapper'])
        observers.append({'root': str(root), 'launch': binding(root / 'LAUNCH.json'),
                          'completion': binding(root / 'COMPLETION.json'), 'stats': completion['stats'],
                          'status': completion['status'], 'pid': launch['pid'], 'creation_time': launch['creation_time'], 'closed_now': True})
    if observers[-1]['status'] != 'COMPLETE':
        raise RuntimeError('Final observer did not close successfully')
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
                            'asr_backlog_max_sec': ranges([r['asr_backlog']['max_sec'] for r in rows]),
                            'speaker_backlog_max_sec': ranges([r['speaker_backlog']['max_sec'] for r in rows]),
                            'memory_trends': [{k: r.get(k) for k in ('job_id', 'private_resident_uss_trend', 'rss_sum_upper_bound_trend', 'windows_private_commit_trend')} for r in rows],
                            'model_threads': rows[0]['model_threads']})
    sample_gaps = []
    for job in manifest['jobs']:
        path = args.final / 'jobs' / job['job_id'] / 'PROCESS_SAMPLES.jsonl'
        samples = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
        gaps = [b['elapsed_sec'] - a['elapsed_sec'] for a, b in zip(samples, samples[1:])]
        if any(g <= 0 for g in gaps):
            raise ValueError('Non-increasing process observer trajectory')
        sample_gaps.append({'job_id': job['job_id'], 'samples': len(samples), 'gaps_sec': ranges(gaps),
                            'gaps_over_0_75_sec': sum(g > .75 for g in gaps), 'samples_interpolated': 0})
    pids = {(x['pid'], x['creation_time']): x for x in process_rows}
    memory = psutil.virtual_memory()
    storage = {drive: {'total_bytes': psutil.disk_usage(drive).total, 'used_bytes': psutil.disk_usage(drive).used,
                       'free_bytes': psutil.disk_usage(drive).free} for drive in ('C:\\', 'G:\\')}
    pairs = summary['repetition_comparisons']
    parity = {'pairs': len(pairs), **{key: sum(bool(p[key]) for p in pairs) for key in
              ('raw_final_words_exact', 'final_labels_exact', 'complete_native_display_sequence_exact', 'journals_exact')},
              'embedding_comparable_pairs': sum(p['embedding_parity'] is not None for p in pairs),
              'embedding_within_1e_minus_6_pairs': sum(bool((p['embedding_parity'] or {}).get('within_1e_minus_6')) for p in pairs)}
    result = {'schema': 's6b-paced-closure.v1', 'status': 'COMPLETE_VERIFIED', 'created_utc': utc(),
              'logical_completed_cells': 64, 'source_audio_sec_completed': manifest['total_audio_sec'],
              'physical_native_attempts': len(attempts), 'physical_complete': 64, 'physical_interrupted': 2,
              'namespace_counts': namespace_counts, 'attempts': list(attempts.values()), 'observers': observers,
              'manifest': binding(args.final / 'MANIFEST.json'), 'summary': binding(args.final / 'SUMMARY.json'),
              'source': binding(__file__), 'readme': binding(Path(__file__).with_name('README_S6B_PACED_CLOSURE.md')),
              'artifact_bindings': list(artifacts.values()), 'all_owned_processes_closed': True,
              'owned_processes': list(pids.values()), 'profile_stream_resource_ranges': comparisons,
              'sampling_gaps': sample_gaps, 'repetition_parity': parity,
              'all_exact_pcm': all(r['no_pcm_loss'] for r in summary['rows']),
              'all_complete_asr_cursor': all(r['asr_cursor_complete'] for r in summary['rows']),
              'host_closure': {'available_ram_bytes': memory.available, 'total_ram_bytes': memory.total, 'volumes': storage},
              'scope': 'Paced study only. Immutable pre-paced 3936 native/replay checkpoint and eight component smoke sessions are separate.',
              'limitations': ['Three observer versions, two interruption gaps and varying unrelated host activity; resource conditions are not identical.',
                  'Each cell is a fresh process with one resident bundle for its scene; no continuous multi-scene leak claim.',
                  'USS is private resident; RSS sums duplicate shared pages; private commit is virtual commitment; PSS null means unavailable.',
                  'Configured model threads do not equal total OS thread count. No CM5 throughput, 2 GB fit or thermal qualification.',
                  'B00 has no internal per-dispatch trace. Exact full PCM, journal/cursor and durable completion checks are its delivery evidence.',
                  'Modeled scheduler availability, native event emission and GUI/phonetic latency remain distinct.',
                  'All repetitions retained; changed words, labels or vectors are observations, never accuracy retry criteria.',
                  'Observer double reads and retries may delay sampling; gaps are measured without interpolation.']}
    args.output.mkdir(parents=True, exist_ok=False)
    write_new(args.output / 'PACED_CLOSURE.json', result)
    lines = ['# S6B paced closure', '', f"64 logical cells completed in {len(attempts)} physical native attempts: 64 complete, two preserved interruptions.",
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
    lines += ['', 'JSON retains per-cell trends, source-bound summary/artifacts, attempts, retry counters and measured sampling gaps.', '']
    lines += ['- ' + text for text in result['limitations']]
    (args.output / 'PACED_CLOSURE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'logical_cells': 64, 'physical_attempts': len(attempts),
                      'parity': parity, 'output': str(args.output)}, indent=2))


def check(root):
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
    counts = [dict(fresh_complete=a, interrupted=b, copied_receipt_references=c) for a, b, c in [(2, 1, 0), (22, 1, 2), (40, 0, 24)]]
    validate_namespace_counts(counts)
    counts[2]['copied_receipt_references'] = 25
    rejected(lambda: validate_namespace_counts(counts), 'incorrect physical/reuse namespace split rejected')
    assert ranges([None, 1, 3, 2]) == {'count': 3, 'min': 1, 'median': 2, 'max': 3}
    checks.append('resource null handling and range projection exact')
    receipt = {'status': 'PASS', 'tests': len(checks), 'checks': checks, 'source': binding(__file__),
               'readme': binding(Path(__file__).with_name('README_S6B_PACED_CLOSURE.md')), 'models_started': 0,
               'scope': 'Isolated fixture grid/worker/trajectory/accounting checks; no final aggregation or native input mutation.', 'created_utc': utc()}
    write_new(root / 'CHECK_RECEIPT.json', receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final', type=Path)
    parser.add_argument('--namespaces', nargs=3)
    parser.add_argument('--observer-roots', nargs=2, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-root', type=Path)
    arguments = parser.parse_args()
    if arguments.check_root:
        check(arguments.check_root)
    else:
        if any(v is None for v in (arguments.final, arguments.namespaces, arguments.observer_roots, arguments.output)):
            parser.error('--final, --namespaces, --observer-roots and --output are required for closure')
        run(arguments)
