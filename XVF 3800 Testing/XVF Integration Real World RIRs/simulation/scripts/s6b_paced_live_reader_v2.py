"""Bounded coordinator LIVE snapshots; see README_S6B_PACED_LIVE_READER_V2.md."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

import psutil

V1_SHA = '15b6449c182c79b2b548e6e36ddff0a05bc84efd71f9a2b0c07c58cff278e4d2'
MAX_BYTES = 65536
MAX_ATTEMPTS = 20
MAX_CAPTURE_BYTES = 16 * 1024 * 1024


def load_v1():
    path = Path(__file__).with_name('s6b_paced_read_retry_v1.py')
    if hashlib.sha256(path.read_bytes()).hexdigest() != V1_SHA:
        raise ValueError('Pinned v1 observer dependency changed')
    spec = importlib.util.spec_from_file_location('s6b_paced_observer_v1_dependency', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v1 = load_v1()
binding, utc, write_new = v1.binding, v1.utc, v1.write_new


def lexical(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def safe_path(path):
    """Disallow an alias/reparse target even when it points to readable JSON."""
    if lexical(path) != lexical(Path(path).resolve()):
        raise ValueError('LIVE path or ancestor resolves through an alias/reparse target')


def admitted_paths(manifest, expected_sha, forwarded):
    v1.validate_forwarded(forwarded)
    if forwarded.count('--output') != 1:
        raise ValueError('Exactly one explicit --output is required')
    output = Path(forwarded[forwarded.index('--output') + 1]).absolute()
    safe_path(output)
    manifest = Path(manifest).absolute()
    safe_path(manifest)
    if lexical(manifest) != lexical(output / 'MANIFEST.json'):
        raise ValueError('Manifest must be the exact forwarded output/MANIFEST.json')
    raw = manifest.read_bytes()
    bound = {'path': str(manifest), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    if bound['sha256'] != expected_sha:
        raise ValueError('Admitted manifest bytes differ')
    plan = json.loads(raw.decode('utf-8-sig'))
    if lexical(plan['output_root']) != lexical(output):
        raise ValueError('Manifest output root differs')
    paths, ids = [], set()
    for job in plan['jobs']:
        name = job['job_id']
        if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name) or name in ids:
            raise ValueError('Unsafe or duplicate manifest job ID')
        ids.add(name)
        path = output / 'jobs' / name / 'LIVE.json'
        safe_path(path)
        paths.append(path)
    if not paths:
        raise ValueError('Empty admitted manifest')
    return paths, bound


def metadata(value):
    return {key: getattr(value, key, None) for key in ('st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_dev', 'st_ino')}


class StableLiveReader:
    """Two exact snapshots, one per-call budget; all other files remain strict."""
    def __init__(self, strict_reader, paths, capture_root, emit=lambda event: None,
                 *, clock=time.monotonic, sleep=time.sleep, snapshotter=None):
        self.strict = v1.PermissionReadRetry(strict_reader, emit, clock=clock, sleep=sleep)
        self.paths = {lexical(p) for p in paths}
        for p in paths:
            safe_path(p)
        self.capture_root = Path(capture_root)
        self.capture_root.mkdir(parents=True, exist_ok=False)
        self.emit, self.clock, self.sleep = emit, clock, sleep
        self.snapshotter = snapshotter
        self.calls = self.read_attempts = self.changed_pairs = self.denials = 0
        self.recovered_calls = self.failed_calls = self.captured_bytes = self.captured_snapshots = 0
        self.scheduled_sleep_sec = self.measured_sleep_sec = 0.0

    def _capture(self, records, reason):
        for record in records:
            if record.get('retained'):
                continue
            raw = record.get('raw')
            row = {k: v for k, v in record.items() if k not in ('raw', 'retained')}
            row.update(reason=reason, event='live_snapshot_retained', utc=utc())
            if raw is not None:
                if self.captured_bytes + len(raw) > MAX_CAPTURE_BYTES:
                    raise RuntimeError('LIVE anomaly capture capacity exhausted; fail closed')
                path = self.capture_root / f'{self.captured_snapshots:06d}.bin'
                with path.open('xb') as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                row['raw_binding'] = binding(path)
                self.captured_bytes += len(raw)
                self.captured_snapshots += 1
            self.emit(row)
            record['retained'] = True

    def __call__(self, path):
        if lexical(path) not in self.paths:
            return self.strict(path)
        safe_path(path)
        self.calls += 1
        if self.captured_bytes + MAX_ATTEMPTS * (MAX_BYTES + 1) > MAX_CAPTURE_BYTES:
            raise RuntimeError('Insufficient capacity to preserve a complete worst-case LIVE anomaly')
        started, attempts, records, last_error, retries = self.clock(), 0, [], None, 0

        def budget():
            if attempts >= MAX_ATTEMPTS or self.clock() - started >= 1.0:
                if isinstance(last_error, PermissionError):
                    raise last_error
                raise TimeoutError('LIVE snapshot shared deadline/attempt budget exhausted')

        def snapshot():
            nonlocal attempts
            budget()
            safe_path(path)
            attempts += 1
            self.read_attempts += 1
            row = {'call': self.calls, 'attempt': attempts, 'path': str(path), 'started_elapsed_sec': self.clock() - started}
            records.append(row)
            try:
                if self.snapshotter is not None:
                    row.update(self.snapshotter(path))
                else:
                    row['before'] = metadata(Path(path).stat())
                    budget_before_os_read = self.clock() - started < 1.0
                    if not budget_before_os_read:
                        raise TimeoutError('LIVE deadline expired before OS byte read')
                    with Path(path).open('rb') as handle:
                        if self.clock() - started >= 1.0:
                            raise TimeoutError('LIVE deadline expired while opening byte stream')
                        row['raw'] = handle.read(MAX_BYTES + 1)
                    row['after'] = metadata(Path(path).stat())
                    safe_path(path)
                raw = row['raw']
                row['sha256'] = hashlib.sha256(raw).hexdigest()
                row['bytes'] = len(raw)
                row['truncated'] = len(raw) > MAX_BYTES
                if row['truncated']:
                    raise ValueError('LIVE JSON exceeds 64 KiB; retained prefix is explicitly truncated')
                row['within_snapshot_metadata_stable'] = row['before'] == row['after']
                return row
            except BaseException as exc:
                row['error_type'], row['error'] = type(exc).__name__, str(exc)
                raise
            finally:
                row['finished_elapsed_sec'] = self.clock() - started

        try:
            while True:
                try:
                    first, second = snapshot(), snapshot()
                    equal = first['raw'] == second['raw']
                    if equal:
                        # Identical malformed bytes are never hidden by a metadata change.
                        result = json.loads(first['raw'].decode('utf-8-sig'))
                        stable = first['before'] == first['after'] == second['before'] == second['after']
                        if stable:
                            if retries:
                                self.recovered_calls += 1
                                self.emit({'event': 'live_snapshot_recovered', 'call': self.calls, 'path': str(path),
                                           'attempts': attempts, 'elapsed_sec': self.clock() - started, 'utc': utc()})
                            return result
                    self.changed_pairs += 1
                    retries += 1
                    self._capture(records, 'changed bytes or metadata; no merged snapshot accepted')
                    last_error = RuntimeError('LIVE snapshot changed')
                except PermissionError as exc:
                    last_error = exc
                    self.denials += 1
                    retries += 1
                    self._capture(records, 'permission denial within shared snapshot budget')
                    self.emit({'event': 'live_permission_denied', 'call': self.calls, 'path': str(path),
                               'attempts': attempts, 'elapsed_sec': self.clock() - started, 'error': str(exc), 'utc': utc()})
                budget()
                delay = min(.05, 1.0 - (self.clock() - started))
                if delay <= 0:
                    budget()
                before = self.clock()
                self.sleep(delay)
                measured = self.clock() - before
                self.scheduled_sleep_sec += delay
                self.measured_sleep_sec += measured
                self.emit({'event': 'live_snapshot_backoff', 'call': self.calls, 'path': str(path),
                           'scheduled_sec': delay, 'measured_sec': measured, 'utc': utc()})
                # The next snapshot rechecks after sleep and event-log overhead.
        except BaseException as exc:
            self.failed_calls += 1
            self._capture(records, 'terminal ' + type(exc).__name__)
            self.emit({'event': 'live_snapshot_failed', 'call': self.calls, 'path': str(path),
                       'attempts': attempts, 'elapsed_sec': self.clock() - started,
                       'error_type': type(exc).__name__, 'error': str(exc), 'utc': utc()})
            raise

    def snapshot(self):
        return {'live_calls': self.calls, 'individual_snapshot_attempts': self.read_attempts,
                'changed_pairs': self.changed_pairs, 'permission_denials': self.denials,
                'recovered_calls': self.recovered_calls, 'failed_calls': self.failed_calls,
                'captured_snapshots': self.captured_snapshots, 'captured_bytes': self.captured_bytes,
                'scheduled_sleep_sec': self.scheduled_sleep_sec, 'measured_sleep_sec': self.measured_sleep_sec,
                'strict_non_live_reader': self.strict.snapshot(), 'shared_deadline_sec': 1.0,
                'maximum_individual_attempts': MAX_ATTEMPTS, 'snapshot_byte_limit': MAX_BYTES,
                'anomaly_capture_capacity_bytes': MAX_CAPTURE_BYTES,
                'limits': 'Deadline checked before each OS byte read; an ongoing OS call/fsync cannot be preempted. Observer samples can be delayed; no interpolation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--driver', type=Path, default=Path(__file__).with_name('s6b_paced.py'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--events-root', type=Path, required=True)
    parser.add_argument('driver_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    forwarded = args.driver_args[1:] if args.driver_args[:1] == ['--'] else args.driver_args
    paths, manifest_binding = admitted_paths(args.manifest, args.manifest_sha256, forwarded)
    driver, driver_binding = v1.load_driver(args.driver)
    args.events_root.mkdir(parents=True, exist_ok=False)
    me = psutil.Process()
    write_new(args.events_root / 'LAUNCH.json', {'schema': 's6b-paced-live-observer.v2', 'status': 'STARTED',
              'created_utc': utc(), 'pid': me.pid, 'creation_time': me.create_time(),
              'wrapper': binding(__file__), 'v1_dependency': binding(v1.__file__), 'driver': driver_binding,
              'manifest': manifest_binding, 'allowed_live_paths': [str(p) for p in paths], 'forwarded_args': forwarded,
              'scope': 'Coordinator observation only; original native child entry point, models, profiles, pacing, dispatch remain unchanged.'})
    with (args.events_root / 'OBSERVER_EVENTS.jsonl').open('x', encoding='utf-8') as handle:
        def emit(event):
            handle.write(json.dumps(event, allow_nan=False) + '\n')
            handle.flush()
        observer = StableLiveReader(driver.read, paths, args.events_root / 'rejected_snapshots', emit)
        driver.read = observer
        argv = sys.argv
        sys.argv = [str(args.driver)] + forwarded
        status, error = 'COMPLETE', None
        try:
            result = driver.main()
        except BaseException:
            status, error = 'FAILED', traceback.format_exc()
            raise
        finally:
            sys.argv = argv
            handle.flush()
            os.fsync(handle.fileno())
            write_new(args.events_root / 'COMPLETION.json', {'status': status, 'created_utc': utc(),
                      'launch': binding(args.events_root / 'LAUNCH.json'), 'stats': observer.snapshot(),
                      'error': error, 'events': binding(args.events_root / 'OBSERVER_EVENTS.jsonl')})
    return result


if __name__ == '__main__':
    raise SystemExit(main())
