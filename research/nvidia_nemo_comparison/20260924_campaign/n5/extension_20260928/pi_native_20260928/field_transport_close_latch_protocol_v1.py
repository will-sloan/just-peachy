"""Saved-failure close replay only; README_FIELD_TRANSPORT_CLOSE_LATCH_V1.md."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace


def run(root, admission):
    prior = Path(admission['retained_run'])
    sys.path.insert(0, str(prior))
    old = importlib.import_module('isolated_source_transport_budget_v1')
    assert Path(old.__file__).resolve() == prior/'isolated_source_transport_budget_v1.py'
    from field_transport_close_latch_v1 import source_class
    cls = source_class(old.IsolatedSource, old.SourceFault)
    rows = []

    class Wire:
        def __init__(self): self.closes = 0
        def close(self): self.closes += 1

    class Watcher:
        def __init__(self): self.joins = 0
        def join(self, timeout): self.joins += 1
        def is_alive(self): return False

    def caught(obj):
        try: obj.close()
        except old.SourceFault as exc:
            return {'code': exc.code, 'detail': exc.detail}
        raise AssertionError('Failure became a successful close')

    for name in ['owner-quota', 'ready-quota', 'result-quota', 'parent-blocked']:
        saved = json.loads((prior/(name+'-CASE.json')).read_bytes())
        obj = cls.__new__(cls)
        obj._initialize_close_outcome()
        obj.root = prior/'fixtures'/name
        obj.closed = False
        obj.terminal = saved['terminal']
        assert obj.terminal is not None  # Never read a socket or run a timer.
        obj.deadline = saved['deadline']
        obj.proc = SimpleNamespace(returncode=saved['returncode'])
        obj.wire = Wire()
        obj.watcher = Watcher()
        obj.watch_error = None
        obj.watch_result = saved['watch']
        first = caught(obj)
        expected = 'CHILD_CLOSURE_MISSING' if name == 'parent-blocked' else 'CHILD_OUTPUT_OR_FINALIZATION_FAILED'
        assert first['code'] == expected
        assert first['detail'] == ({} if saved['closure'] is None else saved['closure'])
        stable = json.loads(json.dumps(first))
        first['detail']['caller_mutation'] = True
        assert caught(obj) == stable == caught(obj)
        assert obj.closed and obj.wire.closes == obj.watcher.joins == 1
        rows.append(dict(case=name, outcome=stable, calls=3, physical_close_calls=obj.wire.closes,
                         watcher_join_calls=obj.watcher.joins, retained_case_sha256=hashlib.sha256((prior/(name+'-CASE.json')).read_bytes()).hexdigest()))

    # Exercise serialization branches and concurrent callers without a source,
    # socket, process, timer, controller, hardware, or transport constructor.
    entered = threading.Event()
    release = threading.Event()
    class FailingBase:
        closed = False
        attempts = 0
        def close(self, timeout=4):
            self.attempts += 1
            entered.set()
            assert release.wait(2)
            raise old.SourceFault('SYNTHETIC_FINALIZATION_FAILURE', {'nested': [1]})
    concurrent_cls = source_class(FailingBase, old.SourceFault)
    obj = concurrent_cls()
    outcomes = []
    thread = threading.Thread(target=lambda: outcomes.append(caught(obj)))
    thread.start()
    assert entered.wait(2)
    second = threading.Thread(target=lambda: outcomes.append(caught(obj)))
    second.start()
    release.set()
    thread.join(2); second.join(2)
    assert not thread.is_alive() and not second.is_alive()
    assert len(outcomes) == 2 and outcomes[0] == outcomes[1] and obj.attempts == 1
    rows.append(dict(case='concurrent-failed-close', outcome=outcomes[0], calls=2, attempts=1, threads_joined=True))

    for name, error, expected in [
        ('unexpected-exception', ValueError('synthetic invalid closure'), 'CLOSE_FINALIZATION_EXCEPTION'),
        ('nonfinite-detail', old.SourceFault('SYNTHETIC', {'value': float('nan')}), 'CLOSE_FAILURE_DETAIL_UNSERIALIZABLE'),
        ('interrupted-close', KeyboardInterrupt('synthetic interruption'), 'CLOSE_FINALIZATION_EXCEPTION')]:
        class RaisingBase:
            closed = False
            attempts = 0
            def close(self, timeout=4):
                self.attempts += 1
                raise error
        obj = source_class(RaisingBase, old.SourceFault)()
        if name == 'interrupted-close':
            try: obj.close()
            except KeyboardInterrupt: pass
            else: raise AssertionError('Interrupt swallowed')
            first = caught(obj)
        else: first = caught(obj)
        assert first['code'] == expected and caught(obj) == first and obj.attempts == 1
        rows.append(dict(case=name, outcome=first, attempts=1, interrupt_propagated=name=='interrupted-close'))

    obj = cls.__new__(cls); obj._initialize_close_outcome(); obj.closed = True
    first = caught(obj)
    assert first['code'] == 'CLOSE_OUTCOME_UNAVAILABLE' and caught(obj) == first
    rows.append(dict(case='closed-without-outcome', outcome=first, physical_attempts=0))
    raw = json.dumps(rows, indent=2, allow_nan=False).encode()
    assert len(raw) < 65536
    with (root/'CLOSE_LATCH_CASES.json').open('xb') as f: f.write(raw)
    return dict(status='PASS_REPEATED_CLOSE_FAILURE_PERSISTENCE_ONLY', cases=len(rows), saved_failure_cases=4,
                child_processes=0, transport_constructors=0, source_audio_samples=0,
                models=False, capture=False, GUI=False, controller=False, whole_run_integrated=False,
                policy_changed=False, retained_evidence_modified=False)
