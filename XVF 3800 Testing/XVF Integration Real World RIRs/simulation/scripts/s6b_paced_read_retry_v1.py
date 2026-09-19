"""Coordinator-only paced status-read repair; see README_S6B_PACED_READ_RETRY_V1.md."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback
from unittest.mock import patch

import psutil

DRIVER_SHA256 = 'e755867e703bc6f4dc457db8ad6e98b078af8cf3abcf15fce8adf58efd10fcd9'


def utc():
    return datetime.now(timezone.utc).isoformat()


def binding(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


class PermissionReadRetry:
    """Retry only a denied read, preserving all other original reader behavior."""

    def __init__(self, reader, emit=lambda event: None, *, sleep=time.sleep, clock=time.monotonic):
        self.reader, self.emit, self.sleep, self.clock = reader, emit, sleep, clock
        self.calls = self.retry_reads = self.denials = self.exhausted = 0
        self.scheduled_sleep_sec = self.measured_sleep_sec = 0.0

    def __call__(self, path):
        self.calls += 1
        started = self.clock()
        denied = 0
        last_denial = None
        while True:
            if denied and self.clock() - started >= 1.0:
                self.exhausted += 1
                self.emit({'event': 'permission_read_deadline_expired', 'path': str(path),
                           'denials': denied, 'elapsed_sec': self.clock() - started, 'utc': utc()})
                raise last_denial
            try:
                result = self.reader(path)
            except PermissionError as exc:
                last_denial = exc
                denied += 1
                self.denials += 1
                if denied == 1:
                    self.retry_reads += 1
                elapsed = self.clock() - started
                exhausted = denied >= 20 or elapsed >= 1.0
                self.emit({'event': 'permission_read_denied', 'path': str(path),
                           'denial_number': denied, 'elapsed_sec': elapsed,
                           'exhausted': exhausted, 'error': str(exc), 'utc': utc()})
                if exhausted:
                    self.exhausted += 1
                    raise
                remaining = 1.0 - (self.clock() - started)
                if remaining <= 0:
                    continue
                delay = min(0.05, remaining)
                before_sleep = self.clock()
                self.sleep(delay)
                measured = self.clock() - before_sleep
                self.scheduled_sleep_sec += delay
                self.measured_sleep_sec += measured
                self.emit({'event': 'permission_read_backoff', 'path': str(path),
                           'scheduled_sec': delay, 'measured_sec': measured, 'utc': utc()})
            else:
                if denied:
                    self.emit({'event': 'permission_read_recovered', 'path': str(path),
                               'denials': denied, 'elapsed_sec': self.clock() - started, 'utc': utc()})
                return result

    def snapshot(self):
        return {'read_calls': self.calls, 'reads_with_permission_retry': self.retry_reads,
                'permission_denials': self.denials, 'exhausted_reads': self.exhausted,
                'scheduled_sleep_sec': self.scheduled_sleep_sec,
                'measured_sleep_sec': self.measured_sleep_sec,
                'maximum_attempts': 20, 'maximum_scheduled_backoff_sec': 0.95,
                'retry_deadline_sec': 1.0,
                'bound_limit': 'Deadline is checked between reads; OS read duration itself cannot be preempted.'}


def load_driver(path):
    bound = binding(path)
    if bound['sha256'] != DRIVER_SHA256:
        raise ValueError('Original frozen paced driver bytes differ')
    spec = importlib.util.spec_from_file_location('s6b_paced_original_read_retry_host', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, bound


def validate_forwarded(forwarded):
    allowed = {'--mode', '--sim', '--report', '--epoch', '--profiles', '--repetitions',
               '--cases', '--streams', '--output', '--timeout'}
    if any(value.startswith('-') and value not in allowed for value in forwarded):
        raise ValueError('Use exact separate original run-option names; no abbreviations or worker flags')
    if forwarded.count('--mode') != 1:
        raise ValueError('Exactly one --mode run is required')
    position = forwarded.index('--mode')
    if position + 1 >= len(forwarded) or forwarded[position + 1] != 'run':
        raise ValueError('Only the original --mode run entry point is supported')


def check(driver, root, original_driver_path):
    root.mkdir(parents=True, exist_ok=False)
    source = root / 'status.json'
    source.write_text('{"status":"RUNNING","source_sec":17.2}', encoding='utf-8')
    initial = binding(source)
    expected = driver.read(source)
    events = []
    retry = PermissionReadRetry(driver.read, events.append, sleep=lambda _: None)
    assert retry(source) == expected and retry.denials == 0
    original = Path.read_text
    attempts = []

    def transient(path, *args, **kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError(13, 'injected sharing denial')
        return original(path, *args, **kwargs)

    with patch.object(Path, 'read_text', transient):
        assert retry(source) == expected
    assert len(attempts) == 3 and retry.denials == 2
    assert events[-1]['event'] == 'permission_read_recovered'
    attempts.clear()

    def persistent(*args, **kwargs):
        attempts.append(1)
        raise PermissionError('persistent injected denial')

    with patch.object(Path, 'read_text', persistent):
        try:
            retry(source)
        except PermissionError:
            pass
        else:
            raise AssertionError('Persistent denial was swallowed')
    assert len(attempts) == 20 and retry.exhausted == 1
    fake_time = [0.0]
    deadline_calls = []

    def slow_denial(path):
        deadline_calls.append(1)
        fake_time[0] += 0.6
        raise PermissionError(13, 'slow denied OS read')

    deadline = PermissionReadRetry(slow_denial, sleep=lambda delay: None, clock=lambda: fake_time[0])
    try:
        deadline(source)
    except PermissionError:
        pass
    else:
        raise AssertionError('Retry deadline was ignored')
    assert len(deadline_calls) == 2 and deadline.exhausted == 1
    fake_time[0] = 0.0
    oversleep_calls = []

    def succeeds_if_wrongly_retried(path):
        oversleep_calls.append(1)
        if len(oversleep_calls) == 1:
            raise PermissionError(13, 'must not retry after oversleep')
        return expected

    def oversleep(delay):
        fake_time[0] += 1.1

    overslept = PermissionReadRetry(succeeds_if_wrongly_retried, sleep=oversleep, clock=lambda: fake_time[0])
    try:
        overslept(source)
    except PermissionError:
        pass
    else:
        raise AssertionError('A new read started after the deadline')
    assert len(oversleep_calls) == 1 and overslept.exhausted == 1
    for error in (FileNotFoundError('missing'), json.JSONDecodeError('bad', '', 0), ValueError('semantic')):
        calls = []

        def different_error(path):
            calls.append(1)
            raise error

        try:
            PermissionReadRetry(different_error, sleep=lambda _: None)(source)
        except type(error):
            pass
        else:
            raise AssertionError('Non-permission error was swallowed')
        assert len(calls) == 1
    assert binding(source) == initial
    assert Path(driver.__file__).resolve() == Path(original_driver_path).resolve()
    validate_forwarded(['--mode', 'run', '--profiles', 'B00,B36,B10,B17', '--streams', 'O0,O1'])
    for invalid in (['--mode', 'run', '--mode', 'worker'], ['--mode', 'run', '--mode=worker'],
                    ['--mode', 'run', '--mo', 'worker'], ['--mode', 'worker']):
        try:
            validate_forwarded(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Alternate worker-mode route accepted')
    receipt = {'status': 'PASS', 'tests': 10, 'created_utc': utc(),
               'checks': ['unchanged actual original JSON read', 'two transient denials then identical read',
                          'twenty persistent denials fail closed', 'missing file is not retried',
                          'invalid JSON is not retried', 'semantic error is not retried',
                          'between-read deadline exhausts before attempt cap',
                          'oversleep cannot start an otherwise-successful retry after deadline',
                          'duplicate/equal-form/abbreviated worker mode cannot bypass run-only boundary',
                          'source unchanged and native child entry point stays original'],
               'source': initial, 'wrapper': binding(__file__), 'driver': binding(driver.__file__),
               'models_started': 0, 'retry_stats': retry.snapshot()}
    write_new(root / 'CHECK_RECEIPT.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, default=Path(__file__).with_name('s6b_paced.py'))
    parser.add_argument('--events-root', type=Path)
    parser.add_argument('--check-root', type=Path)
    parser.add_argument('driver_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    driver, bound = load_driver(args.driver)
    if args.check_root:
        print(json.dumps(check(driver, args.check_root, args.driver), indent=2))
        return 0
    if args.events_root is None:
        parser.error('--events-root is required for run')
    forwarded = args.driver_args[1:] if args.driver_args[:1] == ['--'] else args.driver_args
    try:
        validate_forwarded(forwarded)
    except ValueError as exc:
        parser.error(str(exc))
    args.events_root.mkdir(parents=True, exist_ok=False)
    me = psutil.Process()
    launch = {'schema': 's6b-paced-read-retry-overlay.v1', 'status': 'STARTED', 'created_utc': utc(),
              'pid': me.pid, 'creation_time': me.create_time(), 'wrapper': binding(__file__),
              'driver': bound, 'forwarded_args': forwarded,
              'scope': 'Coordinator JSON reads only. Original driver remains the native child entry point.'}
    write_new(args.events_root / 'LAUNCH.json', launch)
    with (args.events_root / 'READ_RETRY_EVENTS.jsonl').open('x', encoding='utf-8') as events:
        def emit(event):
            events.write(json.dumps(event, allow_nan=False) + '\n')
            events.flush()

        retry = PermissionReadRetry(driver.read, emit)
        driver.read = retry
        original_argv = sys.argv
        sys.argv = [str(args.driver)] + forwarded
        status, error = 'COMPLETE', None
        try:
            result = driver.main()
        except BaseException:
            status, error = 'FAILED', traceback.format_exc()
            raise
        finally:
            sys.argv = original_argv
            events.flush()
            os.fsync(events.fileno())
            write_new(args.events_root / 'COMPLETION.json', {'status': status, 'created_utc': utc(),
                      'launch': binding(args.events_root / 'LAUNCH.json'), 'stats': retry.snapshot(),
                      'error': error, 'events': binding(args.events_root / 'READ_RETRY_EVENTS.jsonl')})
    return result


if __name__ == '__main__':
    raise SystemExit(main())
