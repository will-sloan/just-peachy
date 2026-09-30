"""Bind actual native writers; see README_FIELD_NATIVE_BINDING_V1.md."""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil
import threading

from field_native_text_v2 import NativeTextOwner, NativeTextFailure, bind as bind_text
from field_archive_budget_v4 import encode_control, publish
from field_live_layout_v2 import finite_json, specification

CONTROL_NAMES = tuple(specification()['artifacts']['native_controls']['paths'])
METHODS = ('_write_revised_transcript', '_watch_session',
           'record_s6d_consumer_closure', '_write_summary')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class NativeOwner(NativeTextOwner):
    """One session, fixed native filenames, one attempt per terminal control.

    Old/pending control slots use the retained V4 publication implementation.
    Failed writes remain on disk. A failed control is never retried, including
    after replacement succeeded but directory fsync failed. This process-local
    latch does not claim crash recovery or a cross-process failure latch.
    """
    def __init__(self, session_parent, outputs, request_stop):
        super().__init__(session_parent, outputs, request_stop)
        self.lock = threading.RLock()
        self.controls = {}
        self.session_attempted = False

    def claim_session(self):
        with self.lock:
            if self.session_attempted:
                raise NativeTextFailure('One native session per fresh process')
            # Reserve before any constructor/model/source side effect.
            self.session_attempted = True
            if self.parent.is_symlink() or not self.parent.is_dir() or any(self.parent.iterdir()):
                raise NativeTextFailure('Empty real native session parent required')

    def _directory(self, path):
        path = Path(path)
        if path.parent.parent.resolve() != self.parent or path.parent.is_symlink() or not path.parent.is_dir():
            raise ValueError('Native control outside the selected session')
        directory = path.parent.resolve()
        if self.directory not in (None, directory):
            raise NativeTextFailure('Second native session is not reserved')
        self.directory = directory
        return path

    def publish(self, path, value):
        raw = None
        with self.lock:
            path = Path(path)
            if path.name not in CONTROL_NAMES:
                raise ValueError('Unmapped native control')
            if path.name in self.controls:
                raise NativeTextFailure('Native control already attempted; inspect retained outcome')
            self.controls[path.name] = dict(attempted=True, published=False)
            try:
                self._directory(path)
                if path.exists() or path.is_symlink():
                    raise NativeTextFailure('Fresh native control required')
                raw = encode_control(value, 65536)
                finite_json(raw)
                if shutil.disk_usage(path.parent).free < 5*1024**3 + len(raw):
                    raise NativeTextFailure('Pi free floor')
                publish(path, value, 65536)
                self.controls[path.name].update(published=True, bytes=len(raw),
                                               sha256=hashlib.sha256(raw).hexdigest())
            except BaseException as exc:
                self.controls[path.name].update(error=repr(exc)[:512],
                    replaced=getattr(exc, 'replaced', False))
                self.fail(exc, raw)
                raise

    def snapshot(self):
        with self.lock:
            return dict(text=super().snapshot(), controls=deepcopy(self.controls),
                        session_attempted=self.session_attempted)


def _code(node):
    return ast.dump(node, include_attributes=False)


def derive(source):
    """Transform only four reviewed actual-runtime writer regions.

    Return original/changed ASTs for independent review. No module import,
    object fixture, source, model or native function is executed here.
    """
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PipelineEngine')
    original = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in METHODS}
    if set(original) != set(METHODS):
        raise ValueError('Native runtime methods changed')
    changed = deepcopy(original)

    latest = changed['_write_revised_transcript']
    block = next(n for n in latest.body if isinstance(n, ast.With))
    if ast.unparse(block.items[0].context_expr) != "path.open('x', encoding='utf-8')":
        raise ValueError('Revised transcript open site changed')
    if ast.unparse(block.body[-1]) != 'os.fsync(handle.fileno())':
        raise ValueError('Revised transcript fsync site changed')
    block.items[0].context_expr = ast.parse('_field_native_owner.open(path)', mode='eval').body
    block.body.pop()  # FixedText.flush already fsyncs and latches failures.

    watcher = changed['_watch_session']
    final = watcher.body[0].finalbody[-1]
    if not isinstance(final, ast.If) or ast.unparse(final.test) != 'self._research_v3 and self._session_dir is not None':
        raise ValueError('Native finalization boundary changed')
    if len(final.body) != 3 or not isinstance(final.body[2], ast.Try):
        raise ValueError('Native finalization publication structure changed')
    if not ast.unparse(final.body[1]).startswith('temporary = destination.with_name('):
        raise ValueError('Native finalization temporary changed')
    attempt = final.body[2]
    if not isinstance(attempt.body[-2], ast.With) or ast.unparse(attempt.body[-1]) != 'os.replace(temporary, destination)':
        raise ValueError('Native finalization commit changed')
    attempt.body[-2:] = ast.parse('_field_native_owner.publish(destination, receipt)').body
    final.body.pop(1)

    consumer = changed['record_s6d_consumer_closure']
    condition = consumer.body[-1]
    if not isinstance(condition, ast.If) or ast.unparse(condition.test) != 'not path.exists()':
        raise ValueError('Native consumer idempotence gate changed')
    call = condition.body[0].value
    if not isinstance(call, ast.Call) or ast.unparse(call.func) != 'path.write_text':
        raise ValueError('Native consumer writer changed')
    expression = call.args[0]
    if not isinstance(expression, ast.BinOp) or not isinstance(expression.left, ast.Call) or ast.unparse(expression.left.func) != 'json.dumps':
        raise ValueError('Native consumer payload changed')
    payload = expression.left.args[0]
    condition.body = [ast.Expr(value=ast.Call(func=ast.Attribute(value=ast.Name(id='_field_native_owner', ctx=ast.Load()),
        attr='publish', ctx=ast.Load()), args=[ast.Name(id='path', ctx=ast.Load()), payload], keywords=[]))]

    summary = changed['_write_summary']
    indices = [i for i,n in enumerate(summary.body) if isinstance(n, ast.Assign) and
               any(isinstance(t, ast.Name) and t.id == 'destination' for t in n.targets)]
    if len(indices) != 1 or not isinstance(summary.body[-1], ast.For):
        raise ValueError('Native summary publication structure changed')
    i = indices[0]
    if len(summary.body[i+1:]) != 3 or 'os.replace(temporary, destination)' not in ast.unparse(summary.body[-1]):
        raise ValueError('Native summary commit/retry site changed')
    summary.body[i+1:] = ast.parse('_field_native_owner.publish(destination, summary)').body

    for method in changed.values():
        ast.fix_missing_locations(method)
    return original, changed


def bind(pipeline, runtime, trace_module, owner, pins):
    """Install into an otherwise unused process, after checking actual origins.

    Event journals retain the existing separately bounded sink. This binds the
    native text/clock/revised/control paths and one native-session entry only.
    Full source/archive/controller integration still requires its own admission.
    """
    if set(pins) != {'pipeline', 'runtime', 'trace'}:
        raise ValueError('Exact three native module pins required')
    for name, module in (('pipeline', pipeline), ('runtime', runtime), ('trace', trace_module)):
        if digest(module.__file__) != pins[name]:
            raise ValueError('Native module changed: '+name)
    Base = runtime.PipelineEngine
    if pipeline.PipelineEngine is not Base or not issubclass(pipeline.PrototypeEngine, Base):
        raise ValueError('Unexpected actual native class chain')
    if getattr(Base, '_field_native_binding_v1', False):
        raise ValueError('Native runtime already bound')
    original, changed = derive(Path(runtime.__file__).read_bytes())
    namespace = dict(runtime.__dict__, _field_native_owner=owner)
    compiled = {}
    for name, method in changed.items():
        module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
        exec(compile(module, str(runtime.__file__)+':bounded-native', 'exec'), namespace)
        compiled[name] = namespace[name]
    old_begin = Base._begin_session
    def begin(self, mode):
        owner.claim_session()
        return old_begin(self, mode)
    # All validation/compilation precedes the first binding mutation.
    text_binding = bind_text(pipeline, trace_module, owner,
                            {name:pins[name] for name in ('pipeline', 'trace')})
    for name, method in compiled.items():
        setattr(Base, name, method)
    Base._begin_session = begin
    Base._field_native_binding_v1 = True
    return dict(pins=dict(pins), original_methods={name:_code(n) for name,n in original.items()},
                changed_methods={name:_code(n) for name,n in changed.items()},
                native_text_bound=True, native_controls_bound=True,
                latest_transcript_bound=True, one_native_session=True,
                text_binding=text_binding, runtime_tested=False)
