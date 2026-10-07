"""Finite native snapshot exclusion, no capture. README_PRODUCTION_BACKUP.md."""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import time


def run(output, scope_sha256):
    # The shared owned wrapper has already registered OWNER and verified the unit.
    from backup_reconciliation import (canonical, census, encoded, strict, validate_spec,
        validate_native_source, validate_native_census, write)
    from native_job_probe import identity, read_json
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,128*1024**2))
    output = canonical(output)
    owner = identity(os.getpid())
    if read_json(output/'OWNER.json') != owner:
        raise ValueError('Actual early wrapper owner required')
    unit = read_json(output/'UNIT_OWNERSHIP.json')
    if unit['owner'] != owner or unit['invocation_id'] != os.environ.get('INVOCATION_ID'):
        raise ValueError('Verified actual snapshot unit required')
    with (output/'BACKUP_SCOPE.json').open('rb') as stream: raw=stream.read(65537)
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != scope_sha256:
        raise ValueError('Exact bounded reviewed backup scope required')
    spec = validate_spec(strict(raw))
    base = Path('/home/peachyprototype/JustPeachy')
    for row in spec['roots']:
        path = canonical(row['source'])
        validate_native_source(str(path),is_file=path.is_file())
        if path == output or output in path.parents or path in output.parents:
            raise ValueError('Snapshot cannot include its own growing evidence')
    research = base/'research/nemotron-20260928/B05_PREVIEW_DISPATCH.lock'
    hardware = canonical(base/'data/xvf-hardware.lock')
    lease = hardware.open('rb')
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    error = None
    try:
        locks = []
        for path in (research, hardware):
            value = canonical(path).stat()
            locks.append(dict(path=str(path), device=value.st_dev, inode=value.st_ino))
        write(output/'SNAPSHOT_LOCKS.json', encoded(dict(owner=owner, locks=locks,
            research_exclusive=True, hardware_exclusive=True, capture=False)))
        before = census(spec); validate_native_census(before)
        raw = encoded(before); census_sha = hashlib.sha256(raw).hexdigest()
        write(output/'CENSUS.json', raw)
        write(output/'SNAPSHOT_READY.json', encoded(dict(owner=owner, census_sha256=census_sha,
            scope_sha256=scope_sha256, invocation_id=unit['invocation_id'], files=len(before['files']),
            bytes=before['bytes'], locks_held=True, capture=False)))
        deadline = min(time.monotonic() + spec['runtime_seconds'] - 30, unit['deadline_monotonic'] - 20)
        while not (output/'FINALIZE.json').exists():
            if time.monotonic() >= deadline: raise TimeoutError('Snapshot transfer did not finalize within admitted lifetime')
            time.sleep(.2)
        request = read_json(output/'FINALIZE.json')
        if request != dict(owner=owner, invocation_id=unit['invocation_id'], census_sha256=census_sha):
            raise ValueError('Finalization must bind exact live snapshot and census')
        after = census(spec)
        if after != before: raise ValueError('Full native scope membership, identities or content changed')
        write(output/'SOURCE_VERIFIED.json', encoded(dict(owner=owner, invocation_id=unit['invocation_id'],
            census_sha256=census_sha, scope_sha256=scope_sha256, membership_before_after_equal=True,
            hashes_before_after_equal=True, external_asset_pins_equal=True, files=len(before['files']),
            bytes=before['bytes'], locks_held_during_verification=True, capture=False)))
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc)[:2048])
        raise
    finally:
        fcntl.flock(lease, fcntl.LOCK_UN); lease.close()
        write(output/'SNAPSHOT_RELEASED.json', encoded(dict(owner=owner, hardware_lease_released=True,
            error=error, source_verified=error is None, actual_process_exit_not_yet_claimed=True)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--scope-sha256', required=True)
    args = ap.parse_args(); run(args.output, args.scope_sha256)


if __name__ == '__main__': main()
