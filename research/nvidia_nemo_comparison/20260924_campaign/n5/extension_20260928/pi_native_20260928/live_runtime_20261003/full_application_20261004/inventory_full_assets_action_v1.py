"""Read-only selected native assets; injected by host_operations. README_RUNTIME_ASSETS.md."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time


def digest(path):
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > 1024**3:
        raise ValueError('Bounded regular asset required')
    state = hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            if time.monotonic() > DEADLINE:
                raise TimeoutError('Asset inventory deadline')
            raw = stream.read(65536)
            if not raw:
                break
            state.update(raw)
    after = path.stat()
    fields = lambda item: (item.st_dev,item.st_ino,item.st_size,item.st_mtime_ns,item.st_ctime_ns)
    if fields(before) != fields(after):
        raise ValueError('Asset identity changed during read')
    return state.hexdigest(), before.st_size


def load_verified(package, manifest, name):
    row = next(item for item in manifest['files'] if item['path'] == name+'.py')
    path = package/row['path']; raw = path.read_bytes()
    if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Pinned pure module changed')
    module_spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[name] = module
    module_spec.loader.exec_module(module)
    return module


def inspect(payload, baseline):
    global DEADLINE
    DEADLINE = time.monotonic()+60
    if (payload['boot_id'] != baseline['boot_id'] or
            not time.time() < payload['expires_unix'] <= time.time()+600):
        raise ValueError('Fresh current boot inventory admission required')
    package = Path(payload['package'])
    expected = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-21'
    if str(package) != expected or package.resolve(strict=True) != package:
        raise ValueError('Exact staged qualification package required')
    raw = (package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(raw) > 262144 or hashlib.sha256(raw).hexdigest() != payload['package_manifest_sha256']:
        raise ValueError('Package inventory pin changed')
    manifest = json.loads(raw)
    sys.dont_write_bytecode = True
    shared = load_verified(package, manifest, 'launch_raw_qualification_action')
    shared.inventory(package, payload['package_manifest_sha256'])
    sys.path.insert(0, str(package))
    profiles = load_verified(package, manifest, 'profiles')
    authorization = load_verified(package, manifest, 'release_authorization')
    binding = json.loads((package/'BINDING.json').read_bytes())
    requirements = {}; extras = set(); selections = []
    for diarizer, embedding, geometry in (
            ('pyannote','redimnet',None), ('pyannote','titanet',None),
            ('nemotron','redimnet','current_delayed'), ('nemotron','titanet','current_delayed'),
            ('nemotron','redimnet','streaming'), ('nemotron','titanet','streaming'),
            ('nemotron','redimnet','chunk52_threads2')):
        selection = profiles.RuntimeSelection(diarizer=diarizer, embedding=embedding,
            input_source='live', nemotron_profile=geometry, allow_experimental=True)
        selection.validate(); selections.append(selection.validate())
        paths, extra = authorization.required_assets(binding, selection)
        extras.update(extra)
        for path, expected_hash in paths.items():
            if path in requirements and requirements[path] not in (None,expected_hash) and expected_hash is not None:
                raise ValueError('Selected asset pins conflict')
            requirements[path] = expected_hash or requirements.get(path)
    for row in baseline['titanet_assets']:
        if row['sha256'] in extras:
            if not row['path'].startswith('/home/peachyprototype/JustPeachy/research/nemotron-20260928/runtime-titanet-v3/'):
                raise ValueError('Unexpected TitaNet source')
            requirements[row['path']] = row['sha256']
    if not extras.issubset({value for value in requirements.values() if value is not None}) or len(requirements)>128:
        raise ValueError('Selected embedding inventory incomplete or oversized')
    rows = []; total = 0
    for name, expected_hash in sorted(requirements.items()):
        path = Path(name); resolved = path.resolve(strict=True)
        value, size = digest(resolved); total += size
        if expected_hash is not None and value != expected_hash:
            raise ValueError('Actual selected asset digest differs: '+name)
        if total > 4*1024**3:
            raise ValueError('Total selected asset inventory bound')
        rows.append(dict(path=name,resolved=str(resolved),bytes=size,sha256=value))
    memory = dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line)
    return dict(schema='just-peachy.selected-native-assets.v1',package=str(package),
        package_manifest_sha256=payload['package_manifest_sha256'],boot_id=baseline['boot_id'],
        assets=rows,bytes=total,selections=selections,actual_hashes_verified=True,
        capture=False,models_loaded=False,files_written=False,physical_ram_bytes=int(memory['MemTotal'].split()[0])*1024,
        limitations='Asset presence and identity only; no model-fit, speed or accuracy claim')


if 'PAYLOAD' in globals():
    RESULT = inspect(PAYLOAD, BASELINE)
