"""Selected installed acquire boundary; README_D1_MODEL_BINDING_V1.md."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import threading
import d1_modes_v1 as modes

N2_SHA256 = 'd00c24ad71d6f2c0cf193425e01b489aecceeb85d47006a52f63770fca9cba05'
REASON = 'Application worker binding is not connected. No model starts from this control.'


def validate_request(request):
    if type(request) is not dict or type(request.get('selection')) is not dict:
        raise ValueError('Explicit application selection required')
    mode = modes.select(request['selection'].get('id'))
    expected = dict(schema='d1-application-selection.v1',
                    selection=dict(id=mode['id'], catalog_sha256=modes.CATALOG_SHA256,
                                   geometry=mode['geometry'], retained_run=mode['retained_run']),
                    requires_fresh_process=True, requires_independent_session=True,
                    launchable=False, reason=REASON)
    # Canonical JSON distinguishes bool/int as well as extra/missing fields.
    encode = lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if encode(request) != encode(expected):
        raise ValueError('Exact nonlaunchable selection contract required')
    return copy.deepcopy(mode)


def selected_methods(source):
    raw = Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != N2_SHA256:
        raise ValueError('Installed N2 source identity changed')
    tree = ast.parse(raw.decode('utf-8'))
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'N2ResidentModels')
    acquire, close = [next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == n)
                      for n in ('acquire_diarizer', 'close')]
    branch = acquire.body[1]
    assert isinstance(branch, ast.If) and len(branch.body) == 2
    assert isinstance(branch.body[0], ast.ImportFrom)
    assert branch.body[0].module == 'edge_speech_pipeline.nemotron_diarization'
    assignment = branch.body[1]
    assert isinstance(assignment, ast.Assign) and isinstance(assignment.value, ast.Call)
    assert assignment.value.func.id == 'NemotronDiarizer'
    # Only the import/constructor region changes. D1 check, assignment,
    # resident-reset branch, return and close remain selected installed AST.
    branch.body = [assignment]
    assignment.value = ast.parse('self._d1_construct(session_id)', mode='eval').body
    module = ast.fix_missing_locations(ast.Module(body=[acquire, close], type_ignores=[]))
    namespace = {}
    exec(compile(module, str(source)+'#selected-d1-constructor-binding', 'exec'), namespace)
    return namespace['acquire_diarizer'], namespace['close']


def bind_request(request, campaign_root, installed_n2_source):
    """D1-only, one acquisition under caller admission/lease; no app Start grant.

    No original bundle constructor or ASR import. Reacquisition is blocked even
    after close; a fresh binding cannot load into an already mapped process.
    """
    mode = validate_request(request)
    acquire, close = selected_methods(installed_n2_source)
    root = Path(campaign_root).resolve()

    class BoundD1:
        def __init__(self):
            self.diarization = 'D1'
            self.diarizer = None
            self._lock = threading.RLock()
            self._claimed = False
            self._selected_mode = mode['id']
            self._session = None

        def _d1_construct(self, session_id):
            model = modes.guarded_factory(mode['id'], root)
            try:
                # Fresh empty native stream: bind the application session before
                # any push; this is not an ASR/VAD endpoint or midstream reset.
                model.reset(session_id=session_id)
                if model.session_id != session_id:
                    raise RuntimeError('Native independent session mismatch')
            except BaseException:
                model.close()
                raise
            self._session = session_id
            return model

        def acquire_diarizer(self, session_id):
            with self._lock:
                if type(session_id) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,64}', session_id) is None:
                    raise ValueError('Bounded explicit independent session required')
                if self.diarization != 'D1':
                    raise ValueError('D1 bundle required')
                if self._claimed or self.diarizer is not None:
                    raise RuntimeError('Diarizer already acquired; fresh process/session required')
                self._claimed = True  # Failure is latched; no in-process retry.
                return acquire(self, session_id)

        def close(self):
            with self._lock:
                return close(self)

    return BoundD1()
