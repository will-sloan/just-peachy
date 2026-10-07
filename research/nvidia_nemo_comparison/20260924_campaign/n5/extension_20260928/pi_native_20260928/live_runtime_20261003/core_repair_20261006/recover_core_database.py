"""Sealed native raw SQLite recovery action. See README_DATABASE_RECOVERY.md.

No SSH, recording deletion, SessionStore upgrade or manual sidecar clearing.
Root must admit this exact action and its capacity-derived hard FSIZE first.
"""
import os
import resource

os.sched_setaffinity(0,{3})
for kind,maximum in ((resource.RLIMIT_AS,128*1024**2),(resource.RLIMIT_STACK,1024**2),
                     (resource.RLIMIT_CORE,0)):
    resource.setrlimit(kind,(maximum,maximum))

import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import sys
import time

SCHEMA = 'just-peachy.core-database-recovery.v1'


def strict(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result:
                raise ValueError('Duplicate native recovery request field')
            result[key] = value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite native recovery field')))


def emit(value):
    raw = json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(raw.encode())>65536:
        raise ValueError('Native recovery protocol record bound')
    print(raw,flush=True)


def owner(pid):
    try:
        ticks = int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:
        return None
    return dict(pid=pid,start_ticks=ticks,
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def library(payload):
    package = Path(payload['package'])
    if package.resolve(strict=True)!=package or any(p.is_symlink() for p in (package,*package.parents)):
        raise ValueError('Exact real admitted native package required')
    path = package/'PACKAGE_MANIFEST.json'
    raw = path.read_bytes()
    if len(raw)>2*1024**2 or hashlib.sha256(raw).hexdigest()!=payload['package_manifest_sha256']:
        raise ValueError('Admitted native package manifest differs')
    document = strict(raw)
    rows = document.get('files') if isinstance(document,dict) else document
    if type(rows) is not list:
        raise ValueError('Admitted package file membership required')
    for name in ('recover_core_database.py','core_database_recovery.py'):
        entries = [row for row in rows if row.get('path')==name]
        if len(entries)!=1:
            raise ValueError('Recovery action/library must be exact package members')
        source = package/name
        if source.is_symlink() or source.stat().st_size>262144 or source.stat().st_nlink!=1:
            raise ValueError('Bounded real native recovery source required')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=entries[0]['sha256']:
            raise ValueError('Native recovery source pin differs')
    if Path(__file__).resolve()!=package/'recover_core_database.py':
        raise ValueError('Executing recovery action is outside admitted package')
    spec = importlib.util.spec_from_file_location('pinned_raw_database_recovery',package/'core_database_recovery.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def accepted_backup(core,proof,rows):
    census = core.read_pinned_json(proof['census_path'],proof['census_sha256'])
    manifest = core.read_pinned_json(proof['manifest_path'],proof['manifest_sha256'])
    complete = core.read_pinned_json(proof['complete_path'],proof['complete_sha256'])
    scope = core.read_pinned_json(proof['scope_path'],proof['scope_sha256'])
    if (complete.get('kind')!='COMPLETE' or complete.get('independent_readback') is not True or
        complete.get('source_before_after_verified') is not True or
        complete.get('census_sha256')!=proof['census_sha256'] or
        complete.get('manifest_sha256')!=proof['manifest_sha256'] or census.get('scope')!=scope or
        {row.get('destination') for row in scope.get('roots',[])}!=
            {'package','runtime-data','desktop.desktop','autostart.desktop','display-config'} or
        scope.get('reviewed') is not True):
        raise ValueError('Actual accepted full-backup pins/scope/verification are required')
    manifest_rows = manifest.get('files') if isinstance(manifest,dict) else manifest
    if type(manifest_rows) is not list or len(manifest_rows)!=len(census['files']):
        raise ValueError('Accepted backup membership differs')
    expected = {row['path']:row for row in census['files']}
    if len(expected)!=len(census['files']) or any(expected.get(row.get('path'))!=row for row in manifest_rows):
        raise ValueError('Accepted full backup census/manifest records differ')
    if complete.get('files')!=len(manifest_rows) or complete.get('bytes')!=sum(r['identity']['bytes'] for r in manifest_rows):
        raise ValueError('Accepted full-backup extent differs')
    if core.census_pair(census)!=rows:
        raise ValueError('Recovery database sources differ from accepted full backup')
    return census


def main():
    signal.alarm(30)
    current = owner(os.getpid())
    emit(dict(kind='OWNER',schema=SCHEMA,owner=current,cpu=3,address_space_bytes=128*1024**2,
        stack_bytes=1024**2,maximum_vm_seconds=30))
    raw = sys.stdin.buffer.read(65537)
    if len(raw)>65536:
        raise ValueError('Bounded native recovery payload required')
    payload = strict(raw)
    if (payload.get('schema')!=SCHEMA or payload.get('original_db_recovery') is not True or
        payload.get('boot_id')!=current['boot_id'] or not time.time()<payload['expires_unix']<=time.time()+300):
        raise ValueError('Fresh exact-boot explicit original database recovery authority required')
    core = library(payload)
    rows = payload['database_source']
    census = accepted_backup(core,payload['accepted_full_backup'],rows)
    source_paths = [Path(row['source']) for row in rows]
    database_root = source_paths[0].parent
    if (source_paths[0].name!='history.sqlite3' or source_paths[1].name!='history.sqlite3-journal' or
            any(path.parent!=database_root for path in source_paths)):
        raise ValueError('Exact original database and journal pair required')
    maximum = payload['maximum_file_bytes']
    physical = os.statvfs(database_root)
    if (type(maximum) is not int or maximum!=physical.f_blocks*physical.f_frsize-5*1024**3 or
            maximum<=sum(row['identity']['bytes'] for row in rows)+65536 or
            physical.f_bavail*physical.f_frsize<5*1024**3+1024**2):
        raise ValueError('Exact filesystem-capacity FSIZE and free-space reserve required')
    if resource.getrlimit(resource.RLIMIT_FSIZE)[1]<maximum:
        raise ValueError('Parent action-specific hard FSIZE derivative was not admitted')
    resource.setrlimit(resource.RLIMIT_FSIZE,(maximum,maximum))
    # The sealed root driver owns and checks the actual PID baseline, process
    # handles and research/hardware lease exclusion. Do not acquire them again.
    guard = payload['driver_guard']
    if (guard.get('boot_id')!=current['boot_id'] or
        any(guard.get(k) is not True for k in ('pid_baseline_verified',
            'no_active_project_handles','research_and_hardware_exclusive')) or
        not core.HASH.fullmatch(guard.get('pid_baseline_sha256',''))):
        raise ValueError('Root driver baseline/handle/lease guard binding required')
    before = core.verify_pair(database_root,rows,native_identity=True)
    emit(dict(kind='RECOVERY_ADMITTED',schema=SCHEMA,owner=current,
        accepted_full_backup=payload['accepted_full_backup'],source_before=before,
        driver_guard=guard,maximum_file_bytes=maximum))
    result = core.recover_copy_or_original(database_root,metadata_root=database_root,census=census)
    emit(dict(kind='RESULT',schema=SCHEMA,status='PASS',owner=current,recovery=result,
        sidecars_after_close=core.sidecars(database_root),recording_deletion=False))
    signal.alarm(0)


if __name__=='__main__':
    try:
        main()
    except BaseException as error:
        emit(dict(kind='RESULT',schema=SCHEMA,status='FAILED',error_type=type(error).__name__,
            error=str(error)[:512],recording_deletion=False))
        raise SystemExit(1)
