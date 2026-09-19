"""Model-free observer fault fixtures; README_S6B_PACED_LIVE_READER_V2.md."""
import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import s6b_paced_live_reader_v2 as module


def run(root):
    root.mkdir(parents=True, exist_ok=False)
    source = root / 'LIVE.json'
    source.write_bytes(b'\xef\xbb\xbf{"telemetry":{"source_duration_sec":17.2}}')
    original = module.binding(source)
    checks = []
    events = []
    serial = [0]

    def factory(sequence=None, clock=None, sleep=lambda _: None):
        serial[0] += 1
        values = list(sequence) if sequence is not None else None
        calls = []
        def fake(path):
            calls.append(1)
            value = values.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value() if callable(value) else value
        return module.StableLiveReader(lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig')),
                    [source], root / f'captures_{serial[0]}', events.append,
                    snapshotter=fake if values is not None else None,
                    sleep=sleep, **({'clock': clock} if clock else {})), calls

    def snap(raw=b'{"n":1}', tag=1, after=None):
        return {'raw': raw, 'before': {'v': tag}, 'after': {'v': tag if after is None else after}}

    def rejects(reader, error, path=source):
        try:
            reader(path)
        except error:
            return
        raise AssertionError(f'{error.__name__} was swallowed')

    reader, calls = factory()
    assert reader(source) == {'telemetry': {'source_duration_sec': 17.2}}
    assert reader.read_attempts == 2 and reader.captured_bytes == 0
    checks.append('actual binary utf-8-sig stable read, two snapshots, no source mutation')

    reader, calls = factory([snap(b'{"n":1}'), snap(b'{"n":2}'), snap(b'{"n":3}'), snap(b'{"n":3}')])
    assert reader(source) == {'n': 3} and len(calls) == 4
    assert reader.changed_pairs == 1 and reader.captured_snapshots == 2
    assert sorted(p.read_bytes() for p in reader.capture_root.glob('*.bin')) == [b'{"n":1}', b'{"n":2}']
    checks.append('changing valid snapshots are captured exactly, never spliced, then stable recovery')

    reader, calls = factory([snap(b'{bad'), snap(b'{"n":1}'), snap(), snap()])
    assert reader(source) == {'n': 1} and reader.recovered_calls == 1
    assert (reader.capture_root / '000000.bin').read_bytes() == b'{bad'
    checks.append('malformed-changing-stable valid recovery retains exact malformed bytes')

    reader, calls = factory([snap(b'{bad', 1, 2), snap(b'{bad', 3, 4), snap(), snap()])
    rejects(reader, json.JSONDecodeError)
    assert len(calls) == 2 and reader.captured_snapshots == 2 and reader.scheduled_sleep_sec == 0
    checks.append('identical malformed bytes fail immediately even when metadata changes')

    reader, calls = factory([snap(tag=1, after=2), snap(tag=2), snap(tag=3), snap(tag=3)])
    assert reader(source) == {'n': 1} and reader.changed_pairs == 1
    checks.append('identical valid bytes with unstable metadata are retried under same budget')

    reader, calls = factory([snap(), PermissionError(13, 'second read denial'), snap(), snap()])
    assert reader(source) == {'n': 1} and len(calls) == 4 and reader.denials == 1
    assert reader.captured_snapshots == 1
    checks.append('errno EACCES between snapshots retains first bytes and retries complete pair')

    timer = [0.]
    def slow_first():
        timer[0] += 1.1
        return snap()
    reader, calls = factory([slow_first, snap()], clock=lambda: timer[0])
    rejects(reader, TimeoutError)
    assert len(calls) == 1 and reader.captured_snapshots == 1
    checks.append('slow first snapshot cannot start second snapshot beyond shared deadline')

    timer[0] = 0.
    reader, calls = factory(clock=lambda: timer[0])
    opened_reads = []
    original_open = Path.open
    class SlowOpen:
        def __enter__(self):
            timer[0] += 1.1
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            opened_reads.append(size)
            return b'{"n":1}'
    def opening(path, *args, **kwargs):
        if module.lexical(path) == module.lexical(source) and args[:1] == ('rb',):
            return SlowOpen()
        return original_open(path, *args, **kwargs)
    with patch.object(Path, 'open', opening):
        rejects(reader, TimeoutError)
    assert opened_reads == []
    checks.append('slow file open cannot start its byte read after the deadline')

    timer[0] = 0.
    reader, calls = factory([snap(b'1'), snap(b'2'), snap(), snap()], clock=lambda: timer[0])
    def slow_log(event):
        events.append(event)
        timer[0] += .6
    reader.emit = slow_log
    rejects(reader, TimeoutError)
    assert len(calls) == 2
    checks.append('diagnostic logging overshoot cannot authorize another snapshot read')

    timer[0] = 0.
    def denied_second():
        timer[0] += .6
        raise PermissionError(13, 'shared deadline')
    def oversleep(delay):
        timer[0] += .5
    reader, calls = factory([snap(), denied_second, snap(), snap()], clock=lambda: timer[0], sleep=oversleep)
    rejects(reader, PermissionError)
    assert len(calls) == 2
    checks.append('permission between snapshots plus oversleep cannot restart a fresh deadline')

    reader, calls = factory([snap(str(i).encode()) for i in range(30)], clock=lambda: 0.)
    rejects(reader, TimeoutError)
    assert len(calls) == 20 and reader.captured_snapshots == 20
    checks.append('attempt cap counts individual snapshots, not twenty double-read pairs')

    reader, calls = factory([snap(), FileNotFoundError('vanished'), snap()])
    rejects(reader, FileNotFoundError)
    assert len(calls) == 2 and reader.captured_snapshots == 1
    checks.append('file vanishes between snapshots: fails without retry and preserves earlier bytes')

    outside = root / 'outside' / 'LIVE.json'
    outside.parent.mkdir()
    outside.write_bytes(b'{bad')
    reader, calls = factory()
    rejects(reader, json.JSONDecodeError, outside)
    assert reader.calls == 0 and reader.strict.calls == 1 and reader.strict.denials == 0
    checks.append('same-named unlisted LIVE remains original strict JSON reader')

    reader, calls = factory([snap(b'[]'), snap(b'[]')])
    value = reader(source)
    assert value == [] and len(calls) == 2
    try:
        value.get('telemetry')
    except AttributeError:
        pass
    else:
        raise AssertionError('Valid semantic error was hidden')
    checks.append('valid-but-semantic error propagates to original caller without retry')

    reader, calls = factory()
    resolve = Path.resolve
    def aliased(path, *args, **kwargs):
        return outside if module.lexical(path) == module.lexical(source) else resolve(path, *args, **kwargs)
    with patch.object(Path, 'resolve', aliased):
        rejects(reader, ValueError)
    assert reader.read_attempts == 0
    checks.append('retargeted path/reparse resolution rejected before byte read')

    reader, calls = factory([snap(b'x' * (module.MAX_BYTES + 1))])
    rejects(reader, ValueError)
    assert reader.captured_bytes == module.MAX_BYTES + 1
    assert any(e.get('truncated') is True for e in events)
    checks.append('oversized status fails closed with explicitly truncated retained prefix')

    output = root / 'admitted'
    output.mkdir()
    manifest = output / 'MANIFEST.json'
    manifest.write_text(json.dumps({'output_root': str(output), 'jobs': [{'job_id': 'fixture'}]}), encoding='utf-8')
    forwarded = ['--mode', 'run', '--output', str(output)]
    paths, bound = module.admitted_paths(manifest, module.binding(manifest)['sha256'], forwarded)
    assert paths == [output / 'jobs' / 'fixture' / 'LIVE.json']
    for invalid in (['--mode', 'run', '--mode', 'worker', '--output', str(output)],
                    ['--mode', 'run', '--mode=worker', '--output', str(output)],
                    ['--mode', 'run', '--mo', 'worker', '--output', str(output)],
                    forwarded + ['--output', str(root)]):
        try:
            module.admitted_paths(manifest, bound['sha256'], invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Override accepted')
    try:
        module.admitted_paths(manifest, '0' * 64, forwarded)
    except ValueError:
        pass
    else:
        raise AssertionError('Unbound manifest accepted')
    checks.append('manifest byte binding, output equality and duplicate/inline/abbreviated mode guards')

    driver, driver_binding = module.v1.load_driver(Path(module.__file__).with_name('s6b_paced.py'))
    assert Path(driver.__file__).resolve() == Path(module.__file__).with_name('s6b_paced.py').resolve()
    assert module.binding(source) == original
    for event in events:
        if 'raw_binding' in event:
            assert module.binding(event['raw_binding']['path']) == event['raw_binding']
    checks.append('all retained byte bindings verify and original child __file__ remains unchanged')

    module.write_new(root / 'FIXTURE_EVENTS.json', events)
    receipt = {'status': 'PASS', 'created_utc': module.utc(), 'tests': len(checks), 'checks': checks,
               'wrapper': module.binding(module.__file__), 'tests_source': module.binding(__file__),
               'v1_dependency': module.binding(module.v1.__file__), 'driver': driver_binding,
               'fixture_events': module.binding(root / 'FIXTURE_EVENTS.json'), 'models_started': 0,
               'active_measurement_inputs_mutated': False}
    module.write_new(root / 'CHECK_RECEIPT.json', receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root)
