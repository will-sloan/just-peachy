"""Preserve a closed paced namespace and copy exact completions; README_S6B_PACED_RESUME_V2.md."""
import argparse
import json
import os
from pathlib import Path

import psutil
from s6b_paced_live_reader_v2 import binding, safe_path, utc, write_new


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verify(row):
    actual = binding(row['path'])
    if actual != row:
        raise ValueError('Bound file differs: ' + row['path'])
    return actual


def closed(pid, creation):
    try:
        return abs(psutil.Process(pid).create_time() - creation) > .001
    except psutil.NoSuchProcess:
        return True


def process_closure(source):
    found = {}
    paths = list(source.glob('COORDINATOR*.json'))
    paths += list((source / 'jobs').glob('*/LAUNCH.json'))
    paths += list((source / 'jobs').glob('*/COMPLETE.json'))
    paths += list((source / 'jobs').glob('*/FAILURE.json'))
    for path in paths:
        value = read(path)
        items = value.get('owned_processes', [])
        if 'pid' in value and 'creation_time' in value:
            items = items + [value]
        for item in items:
            key = item['pid'], item['creation_time']
            if not closed(*key):
                raise RuntimeError('Owned process still alive: ' + str(key))
            found[key] = {'pid': key[0], 'creation_time': key[1], 'closed_now': True}
    return list(found.values())


def run(args):
    source = args.source.resolve()
    safe_path(args.source)
    if source in args.receipt.resolve().parents:
        raise ValueError('Preservation/admission receipt must be outside the immutable source')
    if args.receipt.exists():
        raise FileExistsError('Receipt already exists')
    if args.mode == 'snapshot':
        rows = [binding(p) for p in sorted(source.rglob('*')) if p.is_file()]
        processes = process_closure(source)
        completions = sorted(p.parent.name for p in (source / 'jobs').glob('*/COMPLETE.json'))
        failures = [binding(p) for p in sorted((source / 'jobs').glob('*/FAILURE.json'))]
        result = {'schema': 's6b-paced-interruption-source-index.v2', 'status': 'PRESERVED_CLOSED_INTERRUPTED_ATTEMPT',
                  'created_utc': utc(), 'source_root': str(source), 'complete_job_ids': completions,
                  'failures': failures, 'processes': processes, 'owned_processes_closed': True,
                  'files': rows, 'file_count': len(rows), 'total_bytes': sum(x['bytes'] for x in rows),
                  'source': binding(__file__), 'models_started': 0}
        write_new(args.receipt, result)
        print(json.dumps({k: result[k] for k in ('status', 'file_count', 'total_bytes')}, indent=2))
        return

    destination = args.destination.resolve()
    safe_path(args.destination)
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Source and destination must be separate sibling namespaces')
    inventory = read(args.inventory)
    if Path(inventory['source_root']).resolve() != source:
        raise ValueError('Source inventory root differs')
    for row in inventory['files']:
        verify(row)
    current_paths = {str(p.resolve()) for p in source.rglob('*') if p.is_file()}
    if current_paths != {x['path'] for x in inventory['files']}:
        raise ValueError('Source file inventory changed')
    prior = read(args.prior_ledger)
    # Verify the previous immutable closure, including original v1 native bindings.
    verify(prior['source_inventory'])
    for row in read(prior['source_inventory']['path'])['files']:
        verify(row)
    for row in prior['copied_files']:
        verify(row['source'])
        verify(row['copied_binding'])
    prior_source = Path(prior['source_namespace']).resolve()
    if Path(prior['destination_namespace']).resolve() != source:
        raise ValueError('Earlier resume destination differs from current source')
    old, new = read(source / 'MANIFEST.json'), read(destination / 'MANIFEST.json')
    if old['jobs'] != new['jobs']:
        raise ValueError('Full native job objects/keys differ')
    if (destination / 'jobs').exists():
        raise FileExistsError('Destination jobs directory already exists; no overwrites supported')
    copies, complete, native_artifacts = [], [], []
    for job in old['jobs']:
        directory = source / 'jobs' / job['job_id']
        path = directory / 'COMPLETE.json'
        if not path.exists():
            continue
        result = read(path)
        if result['status'] != 'COMPLETE' or result['job_key'] != job['job_key'] or not result['all_owned_processes_closed']:
            raise ValueError('Completed source identity/status differs')
        if result['worker']['status'] != 'COMPLETE' or not result['worker']['native_pcm_exact'] or not result['worker']['asr_cursor_complete']:
            raise ValueError('Completed native source validation missing')
        allowed = {directory.resolve()}
        if job['job_id'] in prior['reused_complete_jobs']:
            allowed.add((prior_source / 'jobs' / job['job_id']).resolve())
        for row in result['artifacts']:
            path_artifact = Path(row['path']).resolve()
            if not any(path_artifact == base or base in path_artifact.parents for base in allowed):
                raise ValueError('Native artifact outside current or previously admitted job closure')
            native_artifacts.append(verify(row))
        complete.append(job['job_id'])
        for name in ('COMPLETE.json', 'PROCESS_SAMPLES.jsonl'):
            copies.append({'job_id': job['job_id'], 'source': binding(directory / name),
                           'destination': str(destination / 'jobs' / job['job_id'] / name)})
    if complete != inventory['complete_job_ids'] and sorted(complete) != inventory['complete_job_ids']:
        raise ValueError('Completion inventory differs')
    processes = process_closure(source) + process_closure(prior_source)
    # All admission checks precede the first copy. Copy exact buffers via exclusive creation.
    for row in copies:
        path = Path(row['destination'])
        raw = Path(row['source']['path']).read_bytes()
        import hashlib
        if len(raw) != row['source']['bytes'] or hashlib.sha256(raw).hexdigest() != row['source']['sha256']:
            raise ValueError('Source changed after preflight')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        row['copied_binding'] = binding(path)
        if row['copied_binding']['sha256'] != row['source']['sha256']:
            raise RuntimeError('Copied bytes differ')
    for row in inventory['files']:
        verify(row)
    result = {'schema': 's6b-paced-live-reader-resume.v2', 'status': 'PREPARED_FOR_INDEPENDENT_REVIEW_NO_MODELS_STARTED',
              'created_utc': utc(), 'source_namespace': str(source), 'destination_namespace': str(destination),
              'source_inventory': binding(args.inventory), 'earlier_resume_ledger': binding(args.prior_ledger),
              'source_manifest': binding(source / 'MANIFEST.json'), 'destination_manifest': binding(destination / 'MANIFEST.json'),
              'all_job_objects_and_keys_exact': True, 'job_count': len(new['jobs']),
              'reused_complete_jobs': complete, 'copied_files': copies, 'verified_native_artifacts': native_artifacts,
              'remaining_native_jobs': len(new['jobs']) - len(complete), 'processes': processes,
              'copied_complete_receipts_mutated': False, 'old_worker_artifact_paths_preserved': True,
              'partial_failure_copied_as_success': False, 'source_files_verified_unchanged': len(inventory['files']),
              'source': binding(__file__), 'models_started': 0,
              'measurement_limit': 'Three observer versions and two interruption gaps. Native code unchanged; observation sampling/overhead may differ. No interpolation or accuracy retry.'}
    write_new(args.receipt, result)
    print(json.dumps({'status': result['status'], 'reused': len(complete), 'remaining': result['remaining_native_jobs'],
                      'copied_files': len(copies), 'receipt': str(args.receipt)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['snapshot', 'admit'], required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--prior-ledger', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.mode == 'admit' and any(x is None for x in (arguments.destination, arguments.inventory, arguments.prior_ledger)):
        parser.error('admit requires --destination, --inventory and --prior-ledger')
    run(arguments)
