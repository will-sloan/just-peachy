"""Injected native raw SQLite recovery. See README_DATABASE_RECOVERY_V2.md.

Root supplies PAYLOAD/BASELINE after early owner and exact action admission.
No stdin, SSH, immutable-package writes, deletion or SessionStore import.
"""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import stat
import time
import types

SCHEMA = 'just-peachy.core-database-recovery.v2'
DATA = Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
CAMPAIGN = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
LOCKS = (CAMPAIGN/'B05_PREVIEW_DISPATCH.lock', DATA.parent/'xvf-hardware.lock',
         DATA/'launcher.lock', DATA/'recordings'/'active.lock')
HASH = re.compile(r'[0-9a-f]{64}')


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def project_handles():
    """Current database/data/sound descriptors; no contents or cmdlines emitted."""
    found = []
    for directory in Path('/proc').iterdir():
        if not directory.name.isdecimal() or int(directory.name)==os.getpid():
            continue
        try:
            command = (directory/'cmdline').read_bytes()
            if b'JustPeachy' not in command:
                continue
            for descriptor in (directory/'fd').iterdir():
                try:
                    target = os.readlink(descriptor)
                except FileNotFoundError:
                    continue
                if target.startswith(str(DATA)+'/') or target.startswith('/dev/snd/'):
                    found.append(dict(pid=int(directory.name),fd=descriptor.name))
                    if len(found)>16:
                        return found
        except (FileNotFoundError,ProcessLookupError):
            continue
    return found


def recover(payload,baseline):
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if (payload.get('schema')!=SCHEMA or payload.get('original_db_recovery') is not True or
        baseline.get('boot_id')!=boot or payload.get('boot_id')!=boot or
        type(payload.get('expires_unix')) not in (int,float) or
        not time.time()<payload['expires_unix']<=time.time()+300):
        raise ValueError('Fresh exact-boot original recovery admission required')
    if any(baseline.get(key) for key in ('current_project_processes','active_recorded_owners','live_manager_owners')):
        raise ValueError('Prior project owners must be closed')
    if set(map(str,LOCKS[:2]))-set(baseline.get('free_leases',[])):
        raise ValueError('Inspected shared research and hardware leases must be free')
    package = Path(payload['package'])
    if (package.parent!=CAMPAIGN or not re.fullmatch(r'field-runtime-v29-build-\d{2}',package.name) or
        package.resolve(strict=True)!=package or any(p.is_symlink() for p in (package,*package.parents))):
        raise ValueError('Exact existing immutable package required')
    manifest = package/'PACKAGE_MANIFEST.json'
    if manifest.is_symlink() or manifest.stat().st_size>262144 or hashlib.sha256(manifest.read_bytes()).hexdigest()!=payload['package_manifest_sha256']:
        raise ValueError('Existing immutable package manifest differs')
    source = base64.b64decode(payload['library_source_b64'],validate=True)
    if not 0<len(source)<=65536 or hashlib.sha256(source).hexdigest()!=payload['library_source_sha256']:
        raise ValueError('Exact admitted bounded recovery library required')
    core = types.ModuleType('admitted_core_database_recovery')
    exec(compile(source,'<admitted-core-database-recovery>','exec'),core.__dict__)
    certificate = payload['accepted_full_backup']
    if (hashlib.sha256(encoded(certificate)).hexdigest()!=payload['accepted_full_backup_sha256'] or
        certificate.get('schema')!='just-peachy.full-backup-host-certificate.v1' or
        any(certificate.get(key) is not True for key in ('whole_backup_complete','independent_payload_readback',
            'source_before_after_verified','native_backup_owner_closed')) or
        any(not HASH.fullmatch(certificate.get(key,'')) for key in
            ('census_sha256','manifest_sha256','complete_sha256','scope_sha256')) or
        type(certificate.get('files')) is not int or certificate['files']<2 or
        type(certificate.get('bytes')) is not int or certificate['bytes']<=0 or
        certificate.get('scope_roots')!=['package','runtime-data','desktop.desktop','autostart.desktop','display-config'] or
        certificate.get('database_source')!=payload['database_source']):
        raise ValueError('Actual full PC backup host certificate and exact database pair required')
    rows = payload['database_source']
    if (type(rows) is not list or len(rows)!=2 or
        [r.get('path') for r in rows]!=['runtime-data/recordings/history.sqlite3','runtime-data/recordings/history.sqlite3-journal'] or
        [r.get('source') for r in rows]!=[str(DATA/'recordings'/'history.sqlite3'),str(DATA/'recordings'/'history.sqlite3-journal')]):
        raise ValueError('Exact original runtime database and hot journal required')
    root = DATA/'recordings'
    physical = os.statvfs(root)
    maximum = payload['maximum_file_bytes']
    if (type(maximum) is not int or maximum!=physical.f_blocks*physical.f_frsize-5*1024**3 or
        maximum<=sum(r['identity']['bytes'] for r in rows)+65536 or
        physical.f_bavail*physical.f_frsize<5*1024**3+1024**2 or
        resource.getrlimit(resource.RLIMIT_FSIZE)[1]<maximum):
        raise ValueError('Admitted actual-capacity hard FSIZE and free reserve required')
    handles = []
    signal.alarm(30)
    try:
        for path in LOCKS:
            for parent in (path,*path.parents):
                if parent.is_symlink():
                    raise ValueError('Real existing shared lease path required')
            descriptor = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            stream = os.fdopen(descriptor,'rb')
            handles.append(stream)
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1:
                raise ValueError('Regular existing single-link shared lease required')
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            current = path.stat()
            if (before.st_dev,before.st_ino)!=(current.st_dev,current.st_ino):
                raise ValueError('Shared lease identity changed')
        if project_handles():
            raise ValueError('Active project/data/sound handles prevent recovery')
        before = core.verify_pair(root,rows,native_identity=True)
        resource.setrlimit(resource.RLIMIT_FSIZE,(maximum,maximum))
        result = core.recover_copy_or_original(root,metadata_root=root,census=dict(files=rows))
        return dict(schema=SCHEMA,status='PASS',boot_id=boot,
            package_manifest_sha256=payload['package_manifest_sha256'],
            accepted_full_backup_sha256=payload['accepted_full_backup_sha256'],
            accepted_full_backup=certificate,source_before=before,recovery=result,
            sidecars_after_close=core.sidecars(root),lease_paths=[str(p) for p in LOCKS],
            leases_held_during_sqlite=True,maximum_file_bytes=maximum,recording_deletion=False,
            metadata_intent_scope='Only the database pair was supplied; no stored deletion intent is certified')
    finally:
        for stream in reversed(handles):
            stream.close()
        signal.alarm(0)


if 'PAYLOAD' in globals():
    RESULT = recover(PAYLOAD,BASELINE)
