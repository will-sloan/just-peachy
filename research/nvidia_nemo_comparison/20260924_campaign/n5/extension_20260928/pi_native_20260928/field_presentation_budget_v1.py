"""Selected presentation/Stop adapter; README_FIELD_PRESENTATION_BUDGET_V1.md."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import queue
import threading
from field_sidecar_budget_v1 import GroupWriter, encoded, validate

MAP = {'telemetry': 'gui_presentation.jsonl', 'failure': ['presentation.bin', 'presentation.json'],
       'closure_reserve': 'PRESENTATION_CLOSURE.json'}


class PresentationFailure(RuntimeError): pass


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_descriptor(path, expected, admission):
    path = Path(path)
    if sha(path) != expected: raise ValueError('Presentation descriptor hash')
    v = json.loads(path.read_bytes())
    if set(v) != {'schema', 'scope', 'files', 'groups', 'mapped_names', 'plan_sha256'}:
        raise ValueError('Presentation descriptor fields')
    if v['schema'] != 'presentation-budget.v1' or v['scope'] != 'detached-method-qualification':
        raise ValueError('Presentation qualification scope')
    if v['mapped_names'] != MAP or set(v['groups']) != set(MAP): raise ValueError('Presentation map')
    if v['files'] != admission['presentation_files']: raise ValueError('Presentation source pins')
    for row in v['files'].values():
        if sha(row['path']) != row['sha256']: raise ValueError('Presentation source changed')
    if v['plan_sha256'] != sha(admission['plan_path']): raise ValueError('Presentation plan')
    plan = json.loads(Path(admission['plan_path']).read_bytes())
    for name, limits in v['groups'].items():
        validate(limits)
        if any(limits[k] > plan['sidecar_groups'][name][k] for k in limits):
            raise ValueError('Presentation budget exceeds plan')
    return v, plan


class PresentationBudget:
    def __init__(self, root, descriptor, expected, admission, epoch, source_error):
        v, self.plan = validate_descriptor(descriptor, expected, admission)
        if type(epoch) is not int or epoch < 0: raise ValueError('Presentation epoch')
        self.root = Path(root)
        if self.root.exists(): raise ValueError('Fresh presentation layout required')
        self.root.mkdir()
        for name in v['groups']: (self.root/name).mkdir()
        self.groups = {k: GroupWriter(self.root/k, limits) for k, limits in v['groups'].items()}
        self.epoch = epoch
        self.source_error = source_error
        self.failure = None
        self.error_text = None
        self.finished = False
        self.finish_failure = None
        self.layout()

    def layout(self):
        dirs = [self.root] + list(self.root.iterdir())
        if len(dirs) != 4 or any(not d.is_dir() or d.is_symlink() for d in dirs):
            raise ValueError('Presentation layout changed')
        observed = sum(d.stat().st_size for d in dirs)
        if len(dirs) > self.plan['maximum_directories'] or observed+65536 > self.plan['filesystem_metadata_reserve_bytes']:
            raise ValueError('Presentation directory reserve')
        return {'directories': len(dirs), 'observed_bytes': observed, 'growth_reserved_bytes': 65536}

    def reassert(self, controller):
        if self.error_text:
            # The first failure is never cleared by the command worker's reset.
            if controller.error and controller.error != self.error_text:
                controller.metrics['presentation_cleanup_error'] = str(controller.error)[:512]
            controller.error = self.error_text
            controller.state = 'ERROR'
            controller.status = self.error_text

    def write(self, controller, value):
        if self.failure is not None:
            self.reassert(controller)
            return False
        raw = None
        try:
            if controller.epoch != self.epoch or value['caption_epoch'] != self.epoch:
                raise ValueError('Presentation epoch changed')
            self.layout()
            raw = encoded(value)+b'\n'
            self.groups['telemetry'].write(MAP['telemetry'], raw, append=True)
            controller.metrics['gui_presentation_log'] = str(self.root/'telemetry'/MAP['telemetry'])
            return True
        except Exception as exc:
            self.error_text = 'GUI_PRESENTATION_WRITE_FAILED'
            self.failure = dict(epoch=self.epoch, error_type=type(exc).__name__, error=str(exc)[:256],
                                bytes=None if raw is None else len(raw),
                                sha256=None if raw is None else hashlib.sha256(raw).hexdigest(),
                                raw_retained=False, receipt_retained=False, source_stop_requested=False,
                                stop_enqueued=False)
            # Request source termination before any further filesystem or queue operation.
            source = getattr(getattr(controller, 'engine', None), '_source', None)
            event = getattr(source, 'stop_event', None)
            if isinstance(event, threading.Event):
                event.set()
                self.failure['source_stop_requested'] = True
                try: self.source_error(source, RuntimeError(self.error_text))
                except Exception as stop_exc: self.failure['source_error_callback_error'] = str(stop_exc)[:256]
            else: self.failure['source_stop_error'] = 'Bound isolated source Event unavailable'
            try:
                controller.stop()
                self.failure['stop_enqueued'] = True
            except Exception as queue_exc: self.failure['stop_queue_error'] = str(queue_exc)[:256]
            try:
                if raw is not None:
                    self.groups['failure'].write('presentation.bin', raw)
                    self.failure['raw_retained'] = True
                published = dict(self.failure, receipt_retained=True)
                self.groups['failure'].json('presentation.json', published)
                self.failure['receipt_retained'] = True
            except Exception as detail_exc:
                self.failure['diagnostic_error'] = type(detail_exc).__name__+': '+str(detail_exc)[:256]
            controller.metrics['gui_presentation_failure'] = deepcopy(self.failure)
            self.reassert(controller)
            return False

    def finish(self, controller, cleanup_returned, cleanup_error):
        if not self.finished:
            self.finished = True
            value = dict(epoch=self.epoch, cleanup_returned=cleanup_returned,
                         cleanup_error=cleanup_error, presentation_failure=self.failure,
                         logical_success=cleanup_returned and self.failure is None,
                         scope='selected-method cleanup return; no physical closure inferred')
            controller.metrics['presentation_cleanup_outcome'] = dict(cleanup_returned=cleanup_returned, cleanup_error=cleanup_error)
            try:
                self.layout()
                self.groups['closure_reserve'].json(MAP['closure_reserve'], value)
            except Exception as exc:
                self.finish_failure = type(exc).__name__+': '+str(exc)[:256]
                self.error_text = self.error_text or 'GUI_PRESENTATION_CLOSURE_FAILED'
                controller.metrics['presentation_closure_error'] = self.finish_failure
        self.reassert(controller)
        if self.failure is not None or self.finish_failure:
            raise PresentationFailure(self.error_text)


def selected_controller(controller_path, expected):
    """Compile exact selected installed methods; replace only documented sites."""
    if sha(controller_path) != expected: raise ValueError('Installed controller changed')
    tree = ast.parse(Path(controller_path).read_bytes())
    original = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Controller')
    names = {'record_presentation', '_enqueue', '_commands', 'stop', '_do_stop'}
    methods = [deepcopy(n) for n in original.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in methods} == names
    record = next(n for n in methods if n.name == 'record_presentation')
    with_body = record.body[-1].body
    conditional = with_body[-1]
    assert isinstance(conditional, ast.If) and ast.unparse(conditional.test) == 'session'
    assert len(conditional.body) == 1 and isinstance(conditional.body[0], ast.Try)
    conditional.body = ast.parse('self._presentation.write(self, value)').body
    commands = next(n for n in methods if n.name == '_commands')
    attempt = commands.body[0].body[1]
    assert isinstance(attempt, ast.Try)
    resets = [n for n in attempt.body if isinstance(n, ast.Assign) and ast.unparse(n) == 'self.error = None']
    assert len(resets) == 1
    resets[0].value = ast.parse('self._presentation.error_text', mode='eval').body
    attempt.finalbody.insert(0, ast.parse('self._presentation.reassert(self)').body[0])
    cls = ast.ClassDef(name='SelectedController', bases=[], keywords=[], body=methods, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    namespace = dict(deepcopy=deepcopy, Path=Path, json=json, queue=queue, SEAT_MODES=set())
    exec(compile(module, str(controller_path)+':selected-presentation', 'exec'), namespace)
    base = namespace['SelectedController']

    class BudgetedController(base):
        def __init__(self): raise RuntimeError('Detached method qualification only; no controller constructor')
        def _do_stop(self):
            returned = False
            error = None
            try:
                super()._do_stop()
                returned = True
            except Exception as exc:
                error = type(exc).__name__+': '+str(exc)[:256]
                raise
            finally:
                self._presentation.finish(self, returned, error)
    return BudgetedController
