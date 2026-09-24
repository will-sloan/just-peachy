"""Bind unchanged N3 reference evidence into a fresh recovery; see README_REUSE.md."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bound(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)


REUSABLE = {'smoke-A0', 'smoke-A1', 'probe-A1', 'reference-A2', 'reference-A3',
            'screen-A0', 'regression-A0', 'paced-A0', 'screen-A1', 'regression-A1', 'paced-A1'}
PROTOTYPE_CHANGES = {'vendor/edge_speech_pipeline/n3_asr_native.py',
                     'vendor/edge_speech_pipeline/README_N3_ASR.md', 'tests/test_n3_components.py'}


def check_prototype_changes(previous, current):
    changes = {name for name in previous.keys() | current.keys() if previous.get(name) != current.get(name)}
    if not changes <= PROTOTYPE_CHANGES:
        raise ValueError('Unreviewed prototype change affects reuse: ' + ', '.join(sorted(changes - PROTOTYPE_CHANGES)))
    return sorted(changes)


def evidence_files(folder):
    """Bind original metadata and every referenced cell/event without copying audio."""
    result = load(folder / 'RESULT.json')
    if result.get('status') != 'COMPLETE' or result.get('errors'):
        raise ValueError('Only complete error-free results can be reused')
    copies = [bound(p) for p in sorted(folder.iterdir()) if p.is_file() and p.suffix in ('.json', '.jsonl')]
    if any(row['bytes'] > 10 * 2**20 for row in copies):
        raise ValueError('Reuse metadata unexpectedly large')
    references = []
    for row in result.get('cells', []):
        path = Path(row['path'])
        if sha(path) != row['sha256']:
            raise ValueError('Changed completed cell')
        cell = load(path)
        if cell.get('status') != 'COMPLETE':
            raise ValueError('Incomplete reused cell')
        event = path.parent / 'events.jsonl'
        if sha(event) != cell['events_sha256']:
            raise ValueError('Changed completed events')
        references.extend([bound(path), bound(event)])
    for case in result.get('cases', []):
        event = folder / (case['case'] + '.jsonl')
        if case.get('status') != 'PASS' or sha(event) != case['events_sha256']:
            raise ValueError('Changed conformance evidence')
    if result.get('schema') == 'just-peachy.n3.asr-result.v1':
        lock = load(folder / 'RUN_LOCK.json')
        digest = hashlib.sha256(json.dumps(lock, sort_keys=True, separators=(',', ':'),
                                          default=str, allow_nan=False).encode()).hexdigest()
        if digest != result['contract_sha256'] or result['completed'] != result['total'] or len(result['cells']) != result['total']:
            raise ValueError('Source contract or cell census differs')
    return copies, references


def prepare(previous_plan, jobs, prototype, manifest_path, python):
    """Narrow recovery: only native adapter/export metadata may have changed."""
    if manifest_path.exists():
        raise ValueError('Preserve existing reuse admission')
    previous_plan = Path(previous_plan).resolve(strict=True)
    prior = load(previous_plan)
    receipt_path = Path(prior['output']) / 'RESULT.json'
    receipt = load(receipt_path)
    if receipt.get('status') != 'READY_FOR_REVIEW' or receipt.get('plan_sha256') != sha(previous_plan):
        raise ValueError('Prior plan is not a matching terminal reviewed attempt')
    import psutil
    owner = receipt.get('owner', {})
    try:
        if abs(psutil.Process(owner['pid']).create_time() - owner['create_time']) < .1:
            raise ValueError('Prior coordinator still owns its process')
    except psutil.NoSuchProcess:
        pass
    here = Path(__file__).resolve().parent
    permitted_helpers = {here / name for name in ('prepare.py', 'export_a1.py', 'test_queue.py')}
    # Every previous model, reference implementation, manifest and frozen file
    # must remain byte-identical. Only these non-inference helpers are exempt.
    unchanged = []
    for row in prior['bindings']:
        if Path(row['path']).resolve() not in permitted_helpers:
            if sha(row['path']) != row['sha256']:
                raise ValueError('Prior inference dependency changed: ' + row['path'])
            unchanged.append(row)
    prior_suite = next(j for j in prior['jobs'] if j['id'] == 'prototype-suite')
    old_prototype = Path(prior_suite['argv'][prior_suite['argv'].index('--source') + 1])
    changes = check_prototype_changes(load(old_prototype.parent / 'SOURCE_RECEIPT.json')['files'],
                                      load(prototype.parent / 'SOURCE_RECEIPT.json')['files'])
    previous_jobs = {j['id']: j for j in prior['jobs']}
    entries = {}
    bindings = [bound(previous_plan), bound(receipt_path), *unchanged]
    for job in jobs:
        name = job['id']
        if name not in REUSABLE:
            continue
        old = previous_jobs[name]
        row = receipt['jobs'][name]
        if row.get('status') != 'COMPLETE' or sha(old['result']) != row['result']['sha256']:
            raise ValueError('Reusable job did not finish with unchanged evidence: ' + name)
        # The fresh plan can change output/frozen root only; panel bytes must
        # match and all other inference parameters must be exactly the same.
        def normalized(argv):
            values = list(argv)
            for flag in ('--prototype', '--output'):
                values[values.index(flag) + 1] = flag
            if '--audio-manifest' in values:
                index = values.index('--audio-manifest') + 1
                values[index] = sha(values[index])
            return values
        if normalized(old['argv']) != normalized(job['argv']):
            raise ValueError('Reusable inference command changed: ' + name)
        copies, references = evidence_files(Path(old['result']).parent)
        entries[name] = dict(copies=copies, references=references, destination=str(Path(job['result']).parent),
                             original_job=old, original_result=row['result'])
        bindings.extend(copies + references)
        job['argv'] = [str(python), '-B', str(here / 'reuse_results.py'), '--manifest', str(manifest_path), '--job', name]
        job['gpu'] = False
        job['execution'] = 'REUSE_VERIFIED_PRIOR_EVIDENCE_NO_INFERENCE'
        job['timeout_seconds'] = 600
    manifest = dict(schema='just-peachy.n3.evidence-reuse.v1', previous_plan=bound(previous_plan),
                    previous_result=bound(receipt_path), changed_prototype_files=changes, jobs=entries,
                    scope='Reuse original A0/reference inference; rerun native, export, suite and aggregate comparisons')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    bindings.append(bound(manifest_path))
    return bindings


def reuse(manifest, name):
    row = manifest['jobs'][name]
    destination = Path(row['destination'])
    if destination.exists():
        raise ValueError('Preserve existing recovery evidence')
    for item in row['copies'] + row['references']:
        if sha(item['path']) != item['sha256']:
            raise ValueError('Reuse evidence changed: ' + item['path'])
    destination.mkdir(parents=True)
    for item in row['copies']:
        target = destination / Path(item['path']).name
        shutil.copyfile(item['path'], target)
        if sha(target) != item['sha256']:
            raise ValueError('Copied receipt differs')
    (destination / 'REUSE_RECEIPT.json').write_text(json.dumps(dict(
        status='REUSED_VERIFIED_PRIOR_EVIDENCE', new_inference=False,
        original_result=row['original_result'], original_job=row['original_job'],
        copied_files=row['copies'], referenced_files=row['references']), indent=2) + '\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--job', required=True)
    args = p.parse_args()
    reuse(load(args.manifest), args.job)
    print('REUSED_VERIFIED_PRIOR_EVIDENCE_NO_INFERENCE', args.job)


if __name__ == '__main__':
    main()
