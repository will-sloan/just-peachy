"""Read-only original CHECK21 metadata/clock pins. README_KEPT_SOURCE21_INSPECTION.md."""
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

MIB = 1024**2
PACKAGE = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-25')
DATA = Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
PIN = '6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
BOOT = '0561d730-3cad-48e0-940a-fe3930c89665'
SESSION = 'c24b685b2bd34d6bb04172965d712c0f'
PROOF = '0c4844160ab39d53f140a8cd7a3e192ad6fe1f47308a10a4bc59213b91893423'
JOB_ROOT = PACKAGE.parent/'live-runtime-tests-20261003/classic-ui-check-21'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate source inspection field')
            result[key] = value
        return result
    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Nonfinite source inspection number')
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_float=number,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def info(path, maximum):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Canonical existing source required')
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or value.st_size > maximum:
        raise ValueError('Bounded independent source file required')
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns]


def read(path, maximum):
    before = info(path, maximum)
    raw = path.read_bytes()
    if len(raw) != before[2] or info(path, maximum) != before:
        raise ValueError('Source changed during readback')
    return raw


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class SourceSnapshot:
    def source_snapshot(self):
        """Pin only the explicitly selected kept source; never the whole history."""
        folder = self.manager.store._session_dir(self.settings['saved_session_id'])
        files, total, visited = [], 0, 0
        pending = [folder]
        paths = []
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 768 or entry.is_symlink():
                        raise ValueError('Bounded regular saved source membership required')
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    else:
                        paths.append(Path(entry.path))
        for path in sorted(paths):
            if path.is_symlink():
                raise ValueError('Saved source must not contain symlinks')
            if path.is_dir():
                continue
            if not path.is_file() or len(files) >= 512:
                raise ValueError('Bounded regular saved source tree required')
            before = path.stat()
            if before.st_size > 32*MIB:
                raise ValueError('Saved source individual file cap32MiB')
            digest = sha(path)
            after = path.stat()
            identity = [before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns]
            if identity != [after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns]:
                raise ValueError('Saved source changed during readback')
            total += before.st_size
            if total > 256*MIB:
                raise ValueError('Selected short saved source exceeds finite readback bound')
            files.append(dict(path=path.relative_to(folder).as_posix(),bytes=before.st_size,
                sha256=digest,identity=identity))
        if not files:
            raise ValueError('Complete kept source required')
        return dict(files=files,bytes=total,sha256=hashlib.sha256(encoded(files)).hexdigest())


def load_pinned(path, name, manifest):
    row = next(value for value in manifest['files'] if value['path'] == path.name)
    if info(path, 2*MIB)[2] != row['bytes'] or sha(path) != row['sha256']:
        raise ValueError('Pinned read-only package helper required')
    if name in sys.modules:
        raise ValueError('Read-only module name collision')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def inspect(payload, baseline):
    expected = {'package_manifest_sha256','boot_id','session_id','check21_proof_sha256','expires_unix'}
    if (type(payload) is not dict or set(payload) != expected or
            payload['package_manifest_sha256'] != PIN or payload['boot_id'] != BOOT or
            payload['session_id'] != SESSION or payload['check21_proof_sha256'] != PROOF or
            type(payload['expires_unix']) not in (int,float) or not math.isfinite(payload['expires_unix']) or
            not time.time() < payload['expires_unix'] <= time.time()+600 or baseline.get('boot_id') != BOOT):
        raise ValueError('Fresh exact CHECK21 read-only source admission required')
    for key in ('current_project_processes','active_recorded_owners','live_manager_owners'):
        if key not in baseline or baseline[key]:
            raise ValueError('Full prior-owner inspection must be clear')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != BOOT:
        raise ValueError('Actual current boot changed')
    manifest_raw = read(PACKAGE/'PACKAGE_MANIFEST.json', 262144)
    if hashlib.sha256(manifest_raw).hexdigest() != PIN:
        raise ValueError('Actual package manifest changed')
    manifest = strict(manifest_raw)
    if manifest.get('target') != str(PACKAGE):
        raise ValueError('Actual selected package target differs')
    sys.dont_write_bytecode = True
    scope = load_pinned(PACKAGE/'native_scope.py', '_source21_read_scope', manifest)
    if scope.verified_inventory(PACKAGE, PIN) != manifest:
        raise ValueError('Complete read-only package inventory differs')
    proof_raw = read(JOB_ROOT/'NATIVE_CHECK_V2.json', 262144)
    proof = strict(proof_raw)
    job = strict(read(JOB_ROOT/'JOB.json', 65536))
    if (hashlib.sha256(proof_raw).hexdigest() != PROOF or proof.get('status') != 'PASS' or
            proof.get('session_id') != SESSION or proof.get('boot_id') != BOOT or
            proof.get('processed_save_passed') is not True or proof.get('main_exact_owner_gone') is not True or
            proof.get('unit_recursively_empty') is not True or job.get('boot_id') != BOOT or
            job.get('package_manifest_sha256') != PIN or job.get('unit') != 'jp-v29-classic-ui-check-21.service' or
            scope.alive(job['owner']) or not scope.cgroup_empty(job['control_group'])):
        raise ValueError('Exact closed CHECK21/kept recording proof required')
    storage = load_pinned(PACKAGE/'storage.py', '_source21_read_storage', manifest)
    spatial = load_pinned(PACKAGE/'saved_spatial.py', '_source21_read_spatial', manifest)
    store = storage.SessionStore(DATA/'recordings', read_only=True)
    lock_path = store.root/'locks'/(SESSION+'.lock')
    lock_identity = info(lock_path, 65536)
    lease = lock_path.open('rb')
    result = None
    try:
        fcntl.flock(lease, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if info(lock_path, 65536) != lock_identity:
            raise ValueError('Existing shared source lease identity changed')
        source_path = store._session_dir(SESSION)/'session.json'
        raw = read(source_path, 65536)
        metadata = strict(raw)
        current = store.read(SESSION)
        if (metadata != current or metadata.get('session_id') != SESSION or metadata.get('status') != 'kept' or
                metadata.get('spec',{}).get('sample_rate') != 16000 or
                type(metadata.get('processed_samples')) is not int or metadata['processed_samples'] != 966400):
            raise ValueError('Actual complete kept 60.4second source differs')
        view = SourceSnapshot()
        view.manager = SimpleNamespace(store=store)
        view.settings = {'saved_session_id':SESSION}
        before = view.source_snapshot()
        artifacts = {}
        for row in store._artifacts(SESSION):
            if row['path'] in artifacts or len(artifacts) >= 4096:
                raise ValueError('Bounded unique kept artifact catalogue required')
            artifacts[row['path']] = row
        maximum = metadata['spec']['metadata_reserve_bytes']
        if type(maximum) is not int or not 0 < maximum <= 2**31:
            raise ValueError('Finite original metadata allocation required')
        poses = spatial._Timeline(store, SESSION, 'work/motion/orientation.jsonl', artifacts, maximum)
        beams = spatial._Timeline(store, SESSION, 'work/spatial/beam_angles.jsonl', artifacts, maximum)
        if (poses.end != 966400 or poses.last_audio_end != 966400 or poses.origin is None or
                beams.origin != poses.origin or not poses.counts.get('bmi270_pose') or
                not beams.counts.get('xvf_observation') or poses.bytes+beams.bytes > maximum):
            raise ValueError('Original complete recorded spatial/audio clocks required')
        if (view.source_snapshot() != before or read(source_path,65536) != raw or
                store.read(SESSION) != metadata or info(lock_path,65536) != lock_identity):
            raise ValueError('Kept source metadata/membership/clock input changed')
        result = dict(status='SOURCE21_METADATA_CLOCKS_READ_ONLY',session_id=SESSION,boot_id=BOOT,
            package_manifest_sha256=PIN,check21_proof_sha256=PROOF,kept=True,processed_samples=966400,
            original_session_json_sha256=hashlib.sha256(raw).hexdigest(),original_session_json_bytes=len(raw),
            original_session_json_identity=info(source_path,65536),canonical_metadata_sha256=hashlib.sha256(encoded(metadata)).hexdigest(),
            source_files=len(before['files']),source_bytes=before['bytes'],source_identity_sha256=before['sha256'],
            recorded_pose_clock_counts=poses.counts,recorded_beam_clock_counts=beams.counts,
            recorded_audio_end_sample=poses.end,recorded_source_epoch_monotonic_sec=poses.origin,
            native_payload_writes=False,current_sensors_used=False,models_started=False,
            captions_or_person_data_returned=False,physical_closure_claimed=False)
        if len(encoded(result)) > 8192:
            raise ValueError('Source metadata scalar response bound')
    finally:
        lease.close()
    result['shared_existing_source_lease_closed'] = lease.closed
    return result


if 'PAYLOAD' in globals():
    RESULT = inspect(PAYLOAD, BASELINE)
