"""Changed Windows host publication fixtures; README_FIELD_HOST_BUDGET_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import json
import os
from pathlib import Path
import time
from unittest.mock import patch
import field_host_budget_v1 as h


def main(root):
    started = time.monotonic()
    main_store = h.HostStore(root/'host')
    admission = json.loads((root/'host/metadata/ADMISSION.json').read_bytes())
    for row in admission['bindings']:
        assert h.digest(Path(row['path']).read_bytes()) == row['sha256']
    cases = []
    fixtures = root/'fixtures'; fixtures.mkdir()

    def store(name, limits=None):
        return h.HostStore(fixtures/name, limits).create({})

    def rejects(name, fn, cls):
        try:
            fn()
        except cls as exc:
            cases.append({'case': name, 'rejected': type(exc).__name__})
        else:
            raise AssertionError('Expected rejection: '+name)

    raw = h.encoded({'caption': 'Peach \u00e9 \u6843\nquoted " value', 'samples': 0})
    s = store('unicode')
    s.write('RESULT.json', raw)
    assert (s.root/'metadata/RESULT.json').read_bytes() == raw
    rejects('immutable-repeat', lambda: s.write('RESULT.json', raw), FileExistsError)
    cases.append({'case': 'unicode-exact', 'bytes': len(raw), 'sha256': h.digest(raw)})

    for name, batch in [('unmapped', {'x.json': b'{}'}), ('nonfinite', {'RESULT.json': b'{"x":NaN}'})]:
        dst = fixtures/name
        rejects('batch-'+name, lambda: h.HostStore(dst).create(batch), ValueError)
        assert not dst.exists()

    limits = dict(h.LIMITS, metadata=(16, 16, 1))
    s = store('first-cap', limits)
    rejects('first-write-cap', lambda: s.write('RESULT.json', raw), h.HostBudgetError)
    assert not list((s.root/'metadata').iterdir())
    s.write('RESULT.json', b'{}')
    rejects('file-count-cap', lambda: s.write('REVIEW.json', b'{}'), h.HostBudgetError)
    assert (s.root/'metadata/RESULT.json').read_bytes() == b'{}'

    s = store('partial')
    original_write = os.write
    def partial(fd, data):
        original_write(fd, data[:3])
        raise OSError('injected host partial after three bytes')
    with patch.object(h.os, 'write', partial):
        rejects('partial-write', lambda: s.write('RESULT.json', raw), OSError)
    assert (s.root/'metadata/RESULT.json.pending').read_bytes() == raw[:3]
    rejects('pending-blocks-new-name', lambda: s.write('REVIEW.json', b'{}'), h.HostBudgetError)
    failure = s.failure('worker', raw, OSError('partial'))
    assert failure['raw_retained'] and failure['receipt_retained']
    assert (s.root/'failure/worker.raw').read_bytes() == raw
    s.json('worker-closure.json', {'logical_success': False, 'partial_preserved': True})
    cases.append({'case': 'partial-reserved-failure-closure', 'failure': failure})

    s = store('failure-cap', dict(h.LIMITS, failure=(1024, 512, 8)))
    failure = s.failure('worker', b'x'*513, RuntimeError('synthetic failure'))
    assert not failure['raw_retained'] and failure['receipt_retained'] and failure['bytes'] == 513
    s.json('worker-closure.json', failure)
    cases.append({'case': 'diagnostic-cap-explicit', 'failure': failure})

    s = store('contention')
    with s.locked():
        rejects('second-descriptor-lock-contention', lambda: s.write('RESULT.json', b'{}'), OSError)
    assert not list((s.root/'metadata').iterdir())

    s = store('directory-drift')
    (s.root/'unexpected').mkdir()
    rejects('directory-drift', lambda: s.write('RESULT.json', b'{}'), h.HostBudgetError)
    assert not list((s.root/'metadata').iterdir()) and (s.root/'unexpected').is_dir()

    for name, batch in [('traversal', {'../escape': b'no'}),
                        ('case-alias', {'A/a': b'a', 'a/b': b'b'}),
                        ('device-name', {'NUL.txt': b'no'}),
                        ('file-dir-collision', {'a': b'a', 'a/b': b'b'})]:
        rejects('backup-'+name, lambda: h.backup_plan(batch), ValueError)
    s = store('backup-metadata-cap', dict(h.LIMITS, metadata=(16, 16, 1)))
    dst = fixtures/'unpublished-backup'
    rejects('backup-manifest-before-payload', lambda: h.publish_backup(s, dst, {'a.txt': b'a'}), h.HostBudgetError)
    assert not dst.exists()

    # Only two retained control receipts are reused, not a release/catalogue copy.
    batch = {Path(row['path']).name: Path(row['path']).read_bytes() for row in admission['backup_inputs']}
    batch['nested/utf8.txt'] = raw
    s = store('exact-backup')
    dest = fixtures/'exact-copy'
    plan = h.publish_backup(s, dest, batch)
    assert all(dest.joinpath(*Path(name).parts).read_bytes() == value for name, value in batch.items())
    assert json.loads((s.root/'metadata/BACKUP.json').read_bytes())['files'] == plan['files']
    rejects('backup-existing-metadata', lambda: h.publish_backup(s, dest, batch), h.HostBudgetError)
    cases.append({'case': 'exact-retained-receipt-backup', 'plan': plan})

    result = {'status': 'PASS_HOST_METADATA_AND_SMALL_BACKUP_ONLY', 'cases': cases,
              'case_count': len(cases), 'seconds': time.monotonic()-started,
              'rss_bytes': psutil.Process().memory_info().rss, 'affinity': psutil.Process().cpu_affinity(),
              'native_pi_compute': False, 'models': False, 'capture': False}
    main_store.json('RESULT.json', result)
    main_store.json('worker-closure.json', {'logical_success': True, 'protocol_returned': True})
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, required=True)
    a = p.parse_args()
    try:
        raise SystemExit(main(a.root))
    except Exception as exc:
        s = h.HostStore(a.root/'host')
        failure = s.failure('worker', repr(exc).encode('utf-8'), exc)
        s.json('worker-closure.json', failure)
        raise
