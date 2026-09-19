"""Chained exact paced completion admission; README_S6B_PACED_RESUME_V3.md."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HELPER_SHA = '21ecaa04ee8ae905ec705ba694ef135225a23eeb3ddd21d35ca6e099035db887'


def load_helper():
    path = Path(__file__).with_name('s6b_paced_resume_v2.py')
    if hashlib.sha256(path.read_bytes()).hexdigest() != HELPER_SHA:
        raise ValueError('Historical admission helper changed')
    spec = importlib.util.spec_from_file_location('s6b_resume_historical_helpers', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load_helper()
binding, read, verify, write_new, utc = prior.binding, prior.read, prior.verify, prior.write_new, prior.utc


def run(args):
    source, destination = args.source.resolve(), args.destination.resolve()
    prior.safe_path(args.source); prior.safe_path(args.destination)
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Source and destination must be separate sibling namespaces')
    if source in args.receipt.resolve().parents or args.receipt.exists():
        raise ValueError('New receipt must be outside preserved source and must not exist')
    if (destination / 'jobs').exists():
        raise FileExistsError('Fresh destination jobs directory required')
    inventory = read(args.inventory)
    if Path(inventory['source_root']).resolve() != source:
        raise ValueError('Inventory source differs')
    ledgers = [read(p) for p in args.prior_ledgers]
    if not ledgers or Path(ledgers[-1]['destination_namespace']).resolve() != source:
        raise ValueError('Latest previous ledger does not end at current source')
    for earlier, later in zip(ledgers, ledgers[1:]):
        if Path(earlier['destination_namespace']).resolve() != Path(later['source_namespace']).resolve():
            raise ValueError('Prior ledger chain is discontinuous')
    inventories = [inventory]
    for ledger in ledgers:
        verify(ledger['source_inventory'])
        inventories.append(read(ledger['source_inventory']['path']))
        verify(ledger['source_manifest']); verify(ledger['destination_manifest'])
        for row in ledger['copied_files']:
            verify(row['source']); verify(row['copied_binding'])
    checked_roots, checked_files, processes = set(), {}, []
    for index in inventories:
        root = Path(index['source_root']).resolve()
        if root in checked_roots:
            continue
        checked_roots.add(root)
        paths = {str(p.resolve()) for p in root.rglob('*') if p.is_file()}
        if paths != {row['path'] for row in index['files']}:
            raise ValueError('Preserved source inventory changed: ' + str(root))
        for row in index['files']:
            verify(row); checked_files[row['path']] = row
        processes += prior.process_closure(root)
    old, new = read(source / 'MANIFEST.json'), read(destination / 'MANIFEST.json')
    if old['jobs'] != new['jobs']:
        raise ValueError('Full native job objects/keys differ')
    copies, complete, artifacts = [], [], []
    for job in old['jobs']:
        directory = source / 'jobs' / job['job_id']
        path = directory / 'COMPLETE.json'
        if not path.exists():
            continue
        result = read(path); worker = result['worker']
        samples = round(job['duration_sec'] * job['source_sample_rate'])
        if result['status'] != 'COMPLETE' or result['job_key'] != job['job_key'] or not result['all_owned_processes_closed']:
            raise ValueError('Completed source identity/status differs')
        if worker['status'] != 'COMPLETE' or worker['job_key'] != job['job_key'] or not worker['native_pcm_exact'] or not worker['asr_cursor_complete']:
            raise ValueError('Native completion validation failed')
        if worker['complete_pcm_samples'] != samples or worker['source_duration_sec'] != job['duration_sec'] or worker['journal']['sha256'] != job['input_pcm_sha256'] or worker['journal']['bytes'] != samples * 2:
            raise ValueError('Native full source/journal identity differs')
        allowed, hop = {directory.resolve()}, source
        for ledger in reversed(ledgers):
            if Path(ledger['destination_namespace']).resolve() != hop or job['job_id'] not in ledger['reused_complete_jobs']:
                break
            hop = Path(ledger['source_namespace']).resolve()
            allowed.add((hop / 'jobs' / job['job_id']).resolve())
        trajectories = []
        for row in result['artifacts']:
            artifact = Path(row['path']).resolve()
            if not any(artifact == base or base in artifact.parents for base in allowed):
                raise ValueError('Artifact path is outside this job explicit reuse chain')
            artifacts.append(verify(row))
            if artifact.name == 'PROCESS_SAMPLES.jsonl':
                trajectories.append(row)
        current_trajectory = binding(directory / 'PROCESS_SAMPLES.jsonl')
        if len(trajectories) != 1 or any(trajectories[0][k] != current_trajectory[k] for k in ('sha256', 'bytes')):
            raise ValueError('Current trajectory copy differs from original complete binding')
        complete.append(job['job_id'])
        for name in ('COMPLETE.json', 'PROCESS_SAMPLES.jsonl'):
            copies.append({'job_id': job['job_id'], 'source': binding(directory / name),
                           'destination': str(destination / 'jobs' / job['job_id'] / name)})
    if len(complete) != 35 or sorted(complete) != inventory['complete_job_ids']:
        raise ValueError('Expected exact preserved 35-cell completion set')
    for row in copies:
        raw = Path(row['source']['path']).read_bytes()
        if len(raw) != row['source']['bytes'] or hashlib.sha256(raw).hexdigest() != row['source']['sha256']:
            raise ValueError('Source changed after preflight')
        target = Path(row['destination']); target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        row['copied_binding'] = binding(target)
        if any(row['copied_binding'][k] != row['source'][k] for k in ('sha256', 'bytes')):
            raise ValueError('Copied bytes differ')
    for row in checked_files.values():
        verify(row)
    result = {'schema': 's6b-paced-optional-live-resume.v3', 'status': 'PREPARED_FOR_INDEPENDENT_REVIEW_NO_MODELS_STARTED',
              'created_utc': utc(), 'source_namespace': str(source), 'destination_namespace': str(destination),
              'source_inventory': binding(args.inventory), 'prior_resume_ledgers': [binding(p) for p in args.prior_ledgers],
              'source_manifest': binding(source / 'MANIFEST.json'), 'destination_manifest': binding(destination / 'MANIFEST.json'),
              'all_job_objects_and_keys_exact': True, 'job_count': len(new['jobs']), 'reused_complete_jobs': complete,
              'copied_files': copies, 'verified_native_artifacts': artifacts, 'remaining_native_jobs': len(new['jobs']) - len(complete),
              'preserved_source_files_verified': len(checked_files), 'processes': processes,
              'copied_complete_receipts_mutated': False, 'old_worker_artifact_paths_preserved': True,
              'partial_failure_copied_as_success': False, 'models_started': 0,
              'source': binding(__file__), 'historical_helper': binding(prior.__file__),
              'readme': binding(Path(__file__).with_name('README_S6B_PACED_RESUME_V3.md')),
              'measurement_limit': 'Four observer versions and three interruption gaps; optional missing LIVE samples explicit, native source order unchanged. No interpolation or accuracy retry.'}
    write_new(args.receipt, result)
    print(json.dumps({'status': result['status'], 'reused': len(complete), 'remaining': result['remaining_native_jobs'],
                      'copied_files': len(copies), 'preserved_files': len(checked_files), 'receipt': binding(args.receipt)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--prior-ledgers', nargs='+', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    run(parser.parse_args())
