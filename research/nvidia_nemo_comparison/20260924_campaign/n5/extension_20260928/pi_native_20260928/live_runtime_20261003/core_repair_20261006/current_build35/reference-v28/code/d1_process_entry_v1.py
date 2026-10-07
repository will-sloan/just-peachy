"""Receipt-bound process entry selection; README_D1_PROCESS_LAUNCH_V1.md."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import threading

import d1_modes_v1 as modes
from d1_method_controls_v1 import canonical

ROOT = '/home/peachyprototype/JustPeachy/research/nemotron-20260928'
STATUS = 'PASS_INSTALLED_D1_SAVED_SELECTION_START_STOP_ONLY'
_process_lock = threading.Lock()
_process_claimed = False


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Registry:
    """A verified projection of three separate receipts, not new runtime acceptance."""
    def __init__(self, raw, expected_sha256, reader=None):
        if type(raw) is not bytes or sha(raw) != expected_sha256:
            raise ValueError('Changed mode entry manifest')
        self.digest = expected_sha256
        self._reader = reader or (lambda path:Path(path).read_bytes())
        value = json.loads(raw)
        if set(value) != {'schema', 'catalog_sha256', 'method_binding', 'modes'}:
            raise ValueError('Mode entry manifest fields')
        if value['schema'] != 'd1-mode-entry.v1' or value['catalog_sha256'] != modes.CATALOG_SHA256:
            raise ValueError('Mode entry catalogue binding')
        if set(value['modes']) != {'delayed', 'streaming', 'chunk52'}:
            raise ValueError('Exact supported mode set required')
        self._manifest = deepcopy(value)
        self._inputs = {}
        for mode, item in value['modes'].items():
            if set(item) != {'label', 'geometry', 'assets_sha256', 'app_source', 'input', 'review', 'endpoint_module', 'endpoint_contract'}:
                raise ValueError('Mode entry fields')
            native = modes.select(mode)
            if canonical(item['geometry']) != canonical(native['geometry']) or item['assets_sha256'] != sha(canonical(native['assets']).encode()):
                raise ValueError('Mode geometry or all-assets binding differs')
            self.read(item['app_source'])
            spec = json.loads(self.read(item['input']))
            review = json.loads(self.read(item['review']))
            endpoint = json.loads(self.read(item['endpoint_contract']))
            self.read(item['endpoint_module'])
            result = review['result']
            if review['status'] != STATUS or result['mode'] != mode or spec['mode'] != mode:
                raise ValueError('Application receipt belongs to another mode')
            if spec['retained_run'] != native['retained_run']:
                raise ValueError('Retained assets belong to another mode')
            if result['endpoint_contract']['contract_sha256'] != item['endpoint_contract']['sha256']:
                raise ValueError('Receipt endpoint differs')
            if endpoint['retained_run'] != native['retained_run']:
                raise ValueError('Endpoint lineage belongs to another mode')
            if not all(result[k] for k in ('controller_closed', 'command_worker_joined', 'application_lease_released', 'model_worker_joined')):
                raise ValueError('Prior application ownership did not close')
            self._inputs[mode] = spec
        for pin in value['method_binding'].values():
            self.read(pin)

    def read(self, pin):
        if type(pin) is not dict or set(pin) != {'path', 'bytes', 'sha256'}:
            raise ValueError('Exact file pin required')
        path = PurePosixPath(pin['path'])
        if not path.is_absolute() or '..' in path.parts or not path.is_relative_to(ROOT):
            raise ValueError('File outside retained campaign')
        if type(pin['bytes']) is not int or not 0 < pin['bytes'] <= 256*1024:
            raise ValueError('Bounded metadata file required')
        raw = self._reader(str(path))
        if type(raw) is not bytes or len(raw) != pin['bytes'] or sha(raw) != pin['sha256']:
            raise ValueError('Changed retained entry dependency: '+str(path))
        return raw

    def request(self, mode, session_id):
        if type(mode) is not str or mode not in self._inputs:
            raise ValueError('Explicit supported diarizer mode required')
        if type(session_id) is not str or not re.fullmatch(r'[a-z][a-z0-9-]{7,95}', session_id):
            raise ValueError('Explicit independent session required')
        if session_id in {x['session_id'] for x in self._inputs.values()}:
            raise ValueError('Retained session cannot be reused')
        item = self._manifest['modes'][mode]
        return dict(schema='d1-process-entry-request.v1', mode=mode, session_id=session_id,
            registry_sha256=self.digest, geometry=deepcopy(item['geometry']), assets_sha256=item['assets_sha256'],
            prior_application_sha256=item['review']['sha256'], endpoint_sha256=item['endpoint_contract']['sha256'],
            requires_fresh_process=True, source_scope='saved-input-only', live_start_available=False,
            entry_native_qualification='PENDING_NEW_PROCESS_LAUNCH_TEST')

    def validate(self, request):
        if type(request) is not dict:
            raise ValueError('Explicit entry request required')
        expected = self.request(request.get('mode'), request.get('session_id'))
        if canonical(request) != canonical(expected):
            raise ValueError('Changed entry request')
        return deepcopy(expected)

    def specification(self, request):
        request = self.validate(request)
        spec = deepcopy(self._inputs[request['mode']])
        spec['session_id'] = request['session_id']
        spec['mode_label'] = self._manifest['modes'][request['mode']]['label']
        spec['saved_application_evidence'] = {mode:deepcopy(item['review']) for mode,item in self._manifest['modes'].items()}
        spec['method_binding'] = deepcopy(self._manifest['method_binding'])
        return spec

    def endpoint(self, request):
        request = self.validate(request)
        pin = self._manifest['modes'][request['mode']]['endpoint_module']
        self.read(pin)
        # Native entry only: load the exact origin, not a same-named sys.path module.
        path = Path(pin['path'])
        if sha(path.read_bytes()) != pin['sha256']:
            raise ValueError('Endpoint origin changed')
        spec = importlib.util.spec_from_file_location('_d1_entry_endpoint_'+request['mode'], path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if Path(module.__file__) != path or module.CONTRACT_SHA256 != request['endpoint_sha256']:
            raise ValueError('Wrong endpoint module loaded')
        return module


def claim_process(request, registry):
    """Latch one prepared binding per process; a child supervisor is still required."""
    global _process_claimed
    request = registry.validate(request)
    with _process_lock:
        if _process_claimed:
            raise RuntimeError('Start a fresh process for another diarizer run')
        maps = Path('/proc/self/maps').read_text()
        if 'libnemo_speech_' in maps or 'libggml' in maps:
            raise RuntimeError('Native model libraries are already mapped')
        _process_claimed = True  # A later binding failure also requires a fresh process.
    return dict(pid=os.getpid(), session_id=request['session_id'], mode=request['mode'])


def controller_class(Base, root, request, registry, writer, closer, failure, catalog):
    """Prepared native composition. Caller must supply fresh guarded process admission."""
    request = registry.validate(request)
    claim_process(request, registry)
    endpoint = registry.endpoint(request)
    profile = catalog.request(request['mode'])
    if profile['assets_sha256'] != request['assets_sha256'] or canonical(profile['geometry']) != canonical(request['geometry']):
        raise ValueError('Method profile differs from selected entry')
    from d1_recovery_process_v1 import controller_class as compose
    return compose(Base, root, registry.specification(request), writer, closer, failure, catalog, endpoint=endpoint)
