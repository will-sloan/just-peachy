"""Changed selected-method fixtures; README_FIELD_PRESENTATION_BUDGET_V1.md."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import queue
import threading
from types import SimpleNamespace
from field_presentation_budget_v1 import MAP, PresentationBudget, PresentationFailure, selected_controller, sha
from field_sidecar_budget_v1 import encoded


def run(root, admission):
    plan = json.loads(Path(admission['plan_path']).read_bytes())
    files = admission['presentation_files']
    cls = selected_controller(files['controller']['path'], files['controller']['sha256'])
    tree = ast.parse(Path(files['source']['path']).read_bytes())
    source_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'IsolatedPipelineSource')
    error_method = next(n for n in source_cls.body if isinstance(n, ast.FunctionDef) and n.name == '_error')
    ns = {'LiveTimingError': type('ExcludedTimingError', (Exception,), {})}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[error_method], type_ignores=[])), files['source']['path']+':_error', 'exec'), ns)
    # Exact selected _error body; RuntimeError only, no timing-error branch claim.
    source_error = ns['_error']
    base = dict(schema='presentation-budget.v1', scope='detached-method-qualification', files=files,
                groups={k:deepcopy(plan['sidecar_groups'][k]) for k in MAP}, mapped_names=MAP,
                plan_sha256=sha(admission['plan_path']))
    fixtures = root/'fixtures'; fixtures.mkdir()
    rows = []

    def descriptor(name, value):
        path = root/(name+'-DESCRIPTOR.json')
        with path.open('xb') as f: f.write(encoded(value))
        return path

    for name in ['schema', 'scope', 'group', 'map', 'source-pin', 'over-budget']:
        value = deepcopy(base)
        if name == 'schema': value['extra'] = True
        elif name == 'scope': value['scope'] = 'live'
        elif name == 'group': del value['groups']['failure']
        elif name == 'map': value['mapped_names']['telemetry'] = 'unmapped.jsonl'
        elif name == 'source-pin': value['files']['controller']['sha256'] = '0'*64
        else: value['groups']['telemetry']['maximum_bytes'] += 1
        path = descriptor('reject-'+name, value)
        destination = fixtures/('reject-'+name)
        try: PresentationBudget(destination, path, sha(path), admission, 1, source_error)
        except ValueError as exc: error = str(exc)
        else: raise AssertionError('Bad presentation descriptor accepted')
        assert not destination.exists()
        rows.append(dict(case='reject-'+name, rejected=True, error=error, directory_created=False))

    receipt = {'text_fixture': 'peach \"line\"\n\u00e9', 'applied': True}
    projected = dict(receipt, caption_epoch=1, scope='Tk text applied; viewport visibility and physical scanout not measured')
    first_raw = encoded(projected)+b'\n'
    for name in ['mapped-write', 'first-quota', 'append-quota', 'queue-full', 'cleanup-failure', 'diagnostic-quota', 'closure-quota']:
        value = deepcopy(base)
        if name not in ['mapped-write', 'append-quota']:
            value['groups']['telemetry']['maximum_write_bytes'] = 8
        if name == 'append-quota':
            value['groups']['telemetry']['maximum_file_bytes'] = len(first_raw)+10
            value['groups']['telemetry']['maximum_write_bytes'] = len(first_raw)+10
        if name == 'diagnostic-quota': value['groups']['failure']['maximum_write_bytes'] = 8
        if name == 'closure-quota': value['groups']['closure_reserve']['maximum_write_bytes'] = 8
        path = descriptor(name, value)
        guard = PresentationBudget(fixtures/name, path, sha(path), admission, 1, source_error)
        obj = cls.__new__(cls)
        source = SimpleNamespace(stop_event=threading.Event(), journal=None, error=None, secondary_errors=[])
        obj._presentation = guard
        obj.epoch = 1; obj.lock = threading.RLock(); obj.metrics = {}; obj.error = None
        obj.engine = SimpleNamespace(session_dir='fixture-session', _source=source)
        obj.commands = queue.Queue(maxsize=1); obj.closed = False
        obj.mode = 'fixture'; obj.state = 'RUNNING'; obj.status = 'fixture'; obj.source_kind = 'fixture'
        obj.enrollment = {'state':'IDLE'}
        actions = []
        obj._stop_playback = lambda: actions.append('playback-stop-stub')
        def cleanup():
            actions.append('session-cleanup-stub')
            if name == 'cleanup-failure': raise RuntimeError('synthetic cleanup failure')
            obj.engine = None
        obj._stop_session = cleanup
        obj._do_noop = lambda: actions.append('noop')
        if name == 'queue-full': obj.commands.put_nowait(('noop', (), {}))
        obj.record_presentation(receipt)
        if name == 'append-quota': obj.record_presentation(receipt)
        failed = name != 'mapped-write'
        assert source.stop_event.is_set() == failed
        assert (source.error is not None) == failed
        if failed:
            assert obj.error == 'GUI_PRESENTATION_WRITE_FAILED' and guard.failure
            if name == 'queue-full': assert not guard.failure['stop_enqueued'] and guard.failure['source_stop_requested']
            else: assert guard.failure['stop_enqueued']
        else: obj.stop()
        # Actual selected command loop, including its reset, dispatch and finally.
        worker = threading.Thread(target=obj._commands)
        worker.start()
        obj.commands.put(None, timeout=2)
        worker.join(2)
        assert not worker.is_alive() and obj.commands.unfinished_tasks == 0
        if name == 'queue-full':
            assert obj.error == 'GUI_PRESENTATION_WRITE_FAILED' and actions == ['noop']
            try: obj._do_stop()
            except PresentationFailure: pass
            else: raise AssertionError('Failed presentation stop became success')
        assert actions.count('session-cleanup-stub') == 1
        assert (obj.state == 'ERROR') == failed
        assert bool(obj.error) == failed
        if failed: assert obj.error == 'GUI_PRESENTATION_WRITE_FAILED'
        telemetry = guard.root/'telemetry/gui_presentation.jsonl'
        assert telemetry.exists() == (name in ['mapped-write','append-quota'])
        if telemetry.exists(): assert telemetry.read_bytes() == first_raw
        closure_path = guard.root/'closure_reserve/PRESENTATION_CLOSURE.json'
        if name == 'closure-quota':
            assert not closure_path.exists() and guard.finish_failure
            closure = None
        else:
            closure = json.loads(closure_path.read_bytes())
            assert closure['logical_success'] == (not failed)
            assert closure['cleanup_returned'] == (name != 'cleanup-failure')
        if name == 'diagnostic-quota': assert not guard.failure['raw_retained'] and not guard.failure['receipt_retained']
        elif failed:
            assert (guard.root/'failure/presentation.bin').read_bytes() == first_raw
            assert json.loads((guard.root/'failure/presentation.json').read_bytes())['receipt_retained']
        rows.append(dict(case=name, failure=deepcopy(guard.failure), closure=closure, finish_failure=guard.finish_failure,
                         actions=actions, error=obj.error, state=obj.state, source_error=source.error,
                         source_stop_requested=source.stop_event.is_set(), worker_joined=True, pending_commands=0,
                         telemetry_bytes=telemetry.stat().st_size if telemetry.exists() else 0,
                         telemetry_sha256=sha(telemetry) if telemetry.exists() else None,
                         cleanup_outcome=obj.metrics['presentation_cleanup_outcome']))
    with (root/'PRESENTATION_CASES.json').open('xb') as f: f.write(encoded(rows))
    return dict(status='PASS_SELECTED_PRESENTATION_FAILURE_AND_STOP_METHODS_ONLY', cases=len(rows),
                descriptor_rejections=6, selected_method_cases=7, worker_loops=7,
                controller_constructors=0, models=False, capture=False, GUI=False, source_audio_samples=0,
                physical_cleanup=False, whole_run_integrated=False, policy_changed=False)
