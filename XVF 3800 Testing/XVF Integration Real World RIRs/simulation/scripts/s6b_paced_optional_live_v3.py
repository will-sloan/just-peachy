"""Explicit missing optional LIVE samples; README_S6B_PACED_OPTIONAL_LIVE_V3.md."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

import psutil

V2_SHA = 'bef16948513e1104ee554dbe7ef1f4f8056599c5f539ee8e1b43bf87d303182b'


def load_v2():
    path = Path(__file__).with_name('s6b_paced_live_reader_v2.py')
    if hashlib.sha256(path.read_bytes()).hexdigest() != V2_SHA:
        raise ValueError('Pinned snapshot reader dependency changed')
    spec = importlib.util.spec_from_file_location('s6b_paced_snapshot_dependency_v2', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v2 = load_v2()
binding, utc, write_new = v2.binding, v2.utc, v2.write_new


class OptionalLiveReader(v2.StableLiveReader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.live_calls_by_path = {}
        self.missing_live_json_by_path = {}

    def __call__(self, path):
        admitted = v2.lexical(path) in self.paths
        name = str(Path(path).absolute())
        if admitted:
            self.live_calls_by_path[name] = self.live_calls_by_path.get(name, 0) + 1
        try:
            return super().__call__(path)
        except json.JSONDecodeError as exc:
            if not admitted:
                raise
            # The pinned reader has already durably retained raw snapshots and
            # emitted its terminal parse error. Other failures never reach here.
            self.missing_live_json_by_path[name] = self.missing_live_json_by_path.get(name, 0) + 1
            self.emit({'event': 'optional_live_json_missing', 'utc': utc(), 'path': name,
                       'base_call_number': self.calls, 'error': str(exc), 'sample_value': None,
                       'retained_snapshot_count_total': self.captured_snapshots,
                       'policy': 'Explicit missing optional telemetry; no prefix parsing, prior-value reuse or interpolation.'})
            return None

    def snapshot(self):
        return super().snapshot() | {
            'missing_live_json_calls': sum(self.missing_live_json_by_path.values()),
            'live_calls_by_path': self.live_calls_by_path,
            'missing_live_json_by_path': self.missing_live_json_by_path,
            'interpretation': 'Inherited failed_calls counts retained reader failures, including JSON failures represented as missing telemetry. Native outcomes remain separate strict results.'}


def check(root):
    root.mkdir(parents=True, exist_ok=False)
    live = root / 'LIVE.json'
    malformed = b'{"telemetry":{"source_duration_sec":2}}\r\n' + b'\x00' * 128
    live.write_bytes(malformed)
    events = []
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))
    observer = OptionalLiveReader(read, [live], root / 'retained', events.append)
    assert observer(live) is None
    snapshots = sorted((root / 'retained').glob('*.bin'))
    assert len(snapshots) == 2 and all(p.read_bytes() == malformed for p in snapshots)
    assert events[-1]['event'] == 'optional_live_json_missing'
    assert observer.snapshot()['missing_live_json_calls'] == 1
    checks = ['identical NUL-padded malformed LIVE becomes explicit None only after exact retained bytes']
    live.write_bytes(b'{"telemetry":{"source_duration_sec":3}}')
    assert observer(live) == {'telemetry': {'source_duration_sec': 3}}
    assert observer.snapshot()['live_calls_by_path'][str(live.absolute())] == 2
    checks.append('later valid observation used directly; missing count and call denominator remain explicit')
    live.write_bytes(malformed)
    assert observer(live) is None
    assert observer.snapshot()['missing_live_json_calls'] == 2
    checks.append('repeated malformed observation remains separately missing without prefix or last-value reuse')
    def reject(fn, error, label):
        try:
            fn()
        except error:
            checks.append(label)
            return
        raise AssertionError(label)
    authoritative = root / 'WORKER_RESULT.json'; authoritative.write_bytes(malformed)
    reject(lambda: observer(authoritative), json.JSONDecodeError, 'authoritative non-LIVE malformed JSON remains fatal')
    outside = root / 'other' / 'LIVE.json'; outside.parent.mkdir(); outside.write_bytes(malformed)
    reject(lambda: observer(outside), json.JSONDecodeError, 'same-named unlisted LIVE remains strict')
    live.write_bytes(b'[]')
    value = observer(live)
    reject(lambda: value.get('telemetry'), AttributeError, 'valid-but-semantic caller error remains fatal')
    live.write_bytes(b'x' * (v2.MAX_BYTES + 1))
    reject(lambda: observer(live), ValueError, 'oversized snapshot remains fatal')
    live.write_bytes(malformed)
    broken = OptionalLiveReader(read, [live], root / 'capture_failure', lambda event: (_ for _ in ()).throw(OSError('injected retention/event error')))
    reject(lambda: broken(live), OSError, 'snapshot retention/event failure cannot become a missing sample')
    timed = OptionalLiveReader(read, [live], root / 'deadline_failure')
    timer = [0.]
    def slow(path):
        timer[0] = 2.
        return {'raw': b'{}', 'before': {}, 'after': {}}
    timed.clock = lambda: timer[0]
    timed.snapshotter = slow
    reject(lambda: timed(live), TimeoutError, 'shared deadline failure remains fatal')
    capped = OptionalLiveReader(read, [live], root / 'capacity_failure')
    capped.captured_bytes = v2.MAX_CAPTURE_BYTES
    reject(lambda: capped(live), RuntimeError, 'capture capacity failure remains fatal')
    driver, driver_binding = v2.v1.load_driver(Path(__file__).with_name('s6b_paced.py'))
    assert Path(driver.__file__).resolve() == Path(__file__).with_name('s6b_paced.py').resolve()
    checks.append('unchanged original native child entry point preserved')
    write_new(root / 'FIXTURE_EVENTS.json', events)
    receipt = {'status': 'PASS', 'tests': len(checks), 'checks': checks, 'created_utc': utc(),
               'source': binding(__file__), 'v2_dependency': binding(v2.__file__), 'driver': driver_binding,
               'readme': binding(Path(__file__).with_name('README_S6B_PACED_OPTIONAL_LIVE_V3.md')),
               'events': binding(root / 'FIXTURE_EVENTS.json'), 'models_started': 0, 'stats': observer.snapshot()}
    write_new(root / 'CHECK_RECEIPT.json', receipt)
    print(json.dumps(receipt, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--driver', type=Path, default=Path(__file__).with_name('s6b_paced.py'))
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--events-root', type=Path)
    parser.add_argument('--check-root', type=Path)
    parser.add_argument('driver_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.check_root:
        check(args.check_root)
        return 0
    if any(x is None for x in (args.manifest, args.manifest_sha256, args.events_root)):
        parser.error('--manifest, --manifest-sha256 and --events-root are required for run')
    forwarded = args.driver_args[1:] if args.driver_args[:1] == ['--'] else args.driver_args
    paths, manifest_binding = v2.admitted_paths(args.manifest, args.manifest_sha256, forwarded)
    driver, driver_binding = v2.v1.load_driver(args.driver)
    args.events_root.mkdir(parents=True, exist_ok=False)
    me = psutil.Process()
    write_new(args.events_root / 'LAUNCH.json', {'schema': 's6b-paced-optional-live-observer.v3', 'status': 'STARTED',
              'created_utc': utc(), 'pid': me.pid, 'creation_time': me.create_time(),
              'wrapper': binding(__file__), 'v2_dependency': binding(v2.__file__), 'v1_dependency': binding(v2.v1.__file__),
              'driver': driver_binding, 'manifest': manifest_binding, 'allowed_live_paths': [str(p) for p in paths],
              'forwarded_args': forwarded, 'scope': 'Only admitted optional LIVE JSON parse failures become explicit missing samples after retention; original native children and authoritative validation unchanged.'})
    with (args.events_root / 'OBSERVER_EVENTS.jsonl').open('x', encoding='utf-8') as handle:
        def emit(event):
            handle.write(json.dumps(event, allow_nan=False) + '\n')
            handle.flush()
            if event.get('event') == 'optional_live_json_missing':
                os.fsync(handle.fileno())
        observer = OptionalLiveReader(driver.read, paths, args.events_root / 'rejected_snapshots', emit)
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
