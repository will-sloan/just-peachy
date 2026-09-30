"""Single-file candidate publication. See README_FIELD_OVERLAY_LAUNCHER_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
import field_dependencies_v2 as pins
import field_overlay_deployment_v1 as adapter


def encoded(value):
    raw = json.dumps(value, indent=2, allow_nan=False).encode('utf-8')
    if len(raw) > 128*1024:
        raise ValueError('Candidate transaction document bound')
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_new(path, raw):
    with Path(path).open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def inspect(root):
    """Read the sole commit point and its immutable record; never repair/retry writes."""
    root = Path(root).resolve()
    state_path = root/'state.json'
    if not state_path.exists():
        return None, None
    raw = state_path.read_bytes()
    if len(raw) > 128*1024:
        raise ValueError('Candidate state bound')
    state = json.loads(raw)
    if state.get('schema') != 'just-peachy.candidate-state.v1':
        raise ValueError('Candidate state schema')
    name = state['transaction']
    if len(name) != 37 or not name.endswith('.json') or any(x not in '0123456789abcdef' for x in name[:-5]):
        raise ValueError('Candidate transaction name')
    record_path = root/'transactions'/name
    if record_path.is_symlink() or not record_path.is_file():
        raise ValueError('Candidate transaction file')
    record_raw = record_path.read_bytes()
    if len(record_raw) > 128*1024 or digest(record_raw) != state['transaction_sha256']:
        raise ValueError('Candidate transaction digest')
    record = json.loads(record_raw)
    if record.get('schema') != 'just-peachy.candidate-transaction.v1':
        raise ValueError('Candidate transaction schema')
    if record['current'] != state['current'] or record['previous'] != state['previous']:
        raise ValueError('Candidate transaction projection')
    return state, digest(raw)


def _publish(root, data, descriptor_path, descriptor_sha, expected_state_sha, release_tools,
             maximum_additional_bytes=None, fault_hook=None, *, locked=False):
    # Caller holds the existing private-data update lock across read/validation/publication.
    assert locked
    root = Path(root).resolve()
    data = Path(data).resolve()
    if not root.is_dir() or not (root/'transactions').is_dir() or not (root/'staged').is_dir():
        raise ValueError('Fresh candidate directories must already exist')
    if any((root/n).exists() for n in ('current.json', 'previous.json')):
        raise ValueError('Legacy multi-file pointers cannot be mixed with transaction state')
    old, actual_sha = inspect(root)
    if actual_sha != expected_state_sha:
        raise ValueError('Candidate state changed')
    d, manifest, checked = adapter.check_descriptor(descriptor_path, descriptor_sha, release_tools)
    if d['candidate_root'] != str(root) or d['data_root'] != str(data):
        raise ValueError('Candidate root/data binding')
    release_tools.check_data_schema(data, manifest, initialize=False)
    current = dict(version=d['version'], descriptor=str(Path(descriptor_path).resolve()),
                   descriptor_sha256=descriptor_sha, release=d['release'],
                   manifest_sha256=d['manifest_sha256'], inference_started=False)
    previous = old['current'] if old else None
    name = uuid.uuid4().hex+'.json'
    record = dict(schema='just-peachy.candidate-transaction.v1', expected_prior_sha256=actual_sha,
                  prior_transaction=old['transaction'] if old else None,
                  current=current, previous=previous, dependency_check=checked)
    record_raw = encoded(record)
    state = dict(schema='just-peachy.candidate-state.v1', current=current, previous=previous,
                 transaction=name, transaction_sha256=digest(record_raw))
    state_raw = encoded(state)
    if pins.OUTPUT_LIMIT is None:
        raise RuntimeError('Output policy not configured')
    output_root, bound = pins.OUTPUT_LIMIT
    if output_root not in root.parents:
        raise ValueError('Candidate outside bound output root')
    used = sum(p.stat().st_size for p in output_root.rglob('*') if p.is_file())
    required = len(record_raw)+len(state_raw)
    if maximum_additional_bytes is not None:
        if type(maximum_additional_bytes) is not int or maximum_additional_bytes < 0:
            raise ValueError('Invalid lower transaction budget')
        bound = min(bound, used+maximum_additional_bytes)
    if used+required > bound:
        raise ValueError('Transaction quota rejected before publication')
    if shutil.disk_usage(root).free < 5*1024**3+32*1024**2+required:
        raise ValueError('Fixed-device transaction reserve')
    # No candidate file has changed above this line. Reserve counts both complete new
    # documents while the old state still exists; the final rename reduces that usage.
    record_path = root/'transactions'/name
    staged_path = root/'staged'/name
    write_new(record_path, record_raw)
    write_new(staged_path, state_raw)
    sync_directory(root/'transactions')
    sync_directory(root/'staged')
    if fault_hook:
        fault_hook('before_commit', name)
    # This is the only authoritative commit point. An exception after it must be
    # resolved by inspect(), never an automatic retry. Prepared orphan files remain.
    os.replace(staged_path, root/'state.json')
    if fault_hook:
        fault_hook('after_commit', name)
    sync_directory(root)
    return state, digest(state_raw)


def activate(root, data, descriptor_path, descriptor_sha, expected_state_sha, release_tools,
             *, maximum_additional_bytes=None, fault_hook=None):
    with release_tools.update_boundary(data):
        return _publish(root, data, descriptor_path, descriptor_sha, expected_state_sha,
                        release_tools, maximum_additional_bytes, fault_hook, locked=True)


def rollback(root, data, expected_state_sha, release_tools, *, maximum_additional_bytes=None, fault_hook=None):
    with release_tools.update_boundary(data):
        state, actual = inspect(root)
        if actual != expected_state_sha:
            raise ValueError('Candidate state changed')
        if state is None or state['previous'] is None:
            raise ValueError('No previous candidate')
        previous = state['previous']
        return _publish(root, data, previous['descriptor'], previous['descriptor_sha256'],
                        expected_state_sha, release_tools, maximum_additional_bytes, fault_hook, locked=True)
