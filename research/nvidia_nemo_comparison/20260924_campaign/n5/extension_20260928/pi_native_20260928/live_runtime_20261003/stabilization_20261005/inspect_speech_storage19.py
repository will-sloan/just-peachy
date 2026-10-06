"""Read-only failed-speech numeric census. README_SPEECH_STORAGE_INSPECTION.md."""
import ast
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import sys
import time

DATA = Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
PACKAGE = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-24')
PIN = '1cb7b8c3ac07d7975b2a31585f94b6402d419a12a128b05758ed7af644319f4c'
BOOT = '0561d730-3cad-48e0-940a-fe3930c89665'
SESSION = '8c5d357f0acc4640bfcda4697d7e325b'
LAUNCH = '75bd9635afc54076a4bc6b611d479a90'
JOB_ROOT = PACKAGE.parent/'live-runtime-tests-20261003/classic-ui-check-19'
FLAGS = {'closed','logical_cleanup_complete','physical_process_closed','exact_owner_gone',
    'direct_child_reaped','stdout_reader_joined','stream_closed','watcher_joined','model_closed',
    'source_closed','d1_closed','hardware_lease_closed','forced_close','physical_closed'}


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate inspection field')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))


def info(path,maximum):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Real diagnostic path required')
    item=path.lstat()
    if not stat.S_ISREG(item.st_mode) or item.st_nlink!=1 or item.st_size>maximum:
        raise ValueError('Bounded independent regular diagnostic required')
    return dict(device=item.st_dev,inode=item.st_ino,bytes=item.st_size,
        mtime_ns=item.st_mtime_ns,ctime_ns=item.st_ctime_ns)


def read(path,maximum=262144):
    before=info(path,maximum);raw=path.read_bytes()
    if len(raw)!=before['bytes'] or info(path,maximum)!=before:
        raise ValueError('Diagnostic changed during read')
    return raw


def digest(path,maximum):
    before=info(path,maximum);value=hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            raw=stream.read(16384)
            if not raw:break
            value.update(raw)
    if info(path,maximum)!=before:raise ValueError('Hashed diagnostic changed')
    return value.hexdigest()


def inspect(payload,baseline):
    expected={'package_manifest_sha256','boot_id','session_id','launch_id','job','request_sha256','expires_unix'}
    if (set(payload)!=expected or payload['package_manifest_sha256']!=PIN or payload['boot_id']!=BOOT
        or payload['session_id']!=SESSION or payload['launch_id']!=LAUNCH
        or type(payload['expires_unix']) not in (int,float) or not time.time()<payload['expires_unix']<=time.time()+600
        or baseline.get('boot_id')!=BOOT):
        raise ValueError('Exact fresh current-boot/build24/failed19 diagnostic required')
    for key in ('current_project_processes','active_recorded_owners','live_manager_owners'):
        if key not in baseline or baseline[key]:raise ValueError('Complete clear current-owner census required')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=BOOT:
        raise ValueError('Actual current boot changed')
    manifest_raw=read(PACKAGE/'PACKAGE_MANIFEST.json')
    if hashlib.sha256(manifest_raw).hexdigest()!=PIN:raise ValueError('Actual package pin changed')
    manifest=strict(manifest_raw);names=set();total=0
    for row in manifest['files']:
        rel=PurePosixPath(row['path'])
        if rel.is_absolute() or '..' in rel.parts or rel.as_posix()!=row['path'] or row['path'].casefold() in names:
            raise ValueError('Exact bounded package inventory required')
        names.add(row['path'].casefold());total+=row['bytes']
        path=PACKAGE.joinpath(*rel.parts)
        if info(path,2*1024**2)['bytes']!=row['bytes'] or digest(path,2*1024**2)!=row['sha256']:
            raise ValueError('Actual package source changed')
    if len(names)>512 or total>16*1024**2:raise ValueError('Original package limits exceeded')
    sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('_speech19_read_scope',PACKAGE/'native_scope.py')
    scope=importlib.util.module_from_spec(spec);spec.loader.exec_module(scope)
    if scope.verified_inventory(PACKAGE,PIN)!=manifest:
        raise ValueError('Complete package membership changed')
    job=strict(read(JOB_ROOT/'JOB.json',65536))
    if (job!=payload['job'] or job['boot_id']!=BOOT or job['package_manifest_sha256']!=PIN
        or job['unit']!='jp-v29-classic-ui-check-19.service' or scope.alive(job['owner'])
        or not scope.cgroup_empty(job['control_group'])):
        raise ValueError('Exact failed19 owner/unit must be physically closed before query')
    properties=scope.properties(job['unit'])
    if properties.get('ActiveState') in ('active','activating','deactivating') or properties.get('InvocationID') not in ('',job['invocation_id']):
        raise ValueError('Failed19 exact invocation still active or replaced')
    launch=DATA/'launches'/LAUNCH;session=DATA/'recordings/sessions'/SESSION
    request=read(launch/'REQUEST.json',65536)
    if hashlib.sha256(request).hexdigest()!=payload['request_sha256']:
        raise ValueError('Actual failed-worker request changed')
    request_values=strict(request)
    if strict(read(launch/'worker/SESSION.json',65536)).get('session_id')!=SESSION:
        raise ValueError('Exact failed worker/session binding required')
    owners=[dict(role='main',owner=job['owner'],exact_absent=True)]
    for role,path in (('worker',launch/'worker/REGISTERED_OWNER.json'),
                      ('source',session/'work/source/REGISTERED_OWNER.json')):
        value=strict(read(path,65536));owner=value.get('owner',value)
        if (type(owner) is not dict or set(owner)!={'boot_id','pid','start_ticks'} or owner['boot_id']!=BOOT
            or any(type(owner[key]) is not int or owner[key]<=0 for key in ('pid','start_ticks')) or scope.alive(owner)):
            raise ValueError('Exact recorded old worker/source identity must be absent')
        owners.append(dict(role=role,owner=owner,exact_absent=True))
    receipts=[]
    for name,path in (('SOURCE_CLOSE',session/'work/source/SOURCE_CLOSE.json'),
                      ('WORKER_EXIT',launch/'worker/EXIT.json'),('CONTROLLER_CLOSED',launch/'CLOSED.json'),
                      ('MODEL_RESULT',session/'work/RESULT.json')):
        if not path.exists():
            receipts.append(dict(role=name,present=False));continue
        raw=read(path,4*1024**2);value=strict(raw);flags=[];pending=[('',value)];visited=0
        while pending:
            prefix,item=pending.pop();visited+=1
            if visited>8192:raise ValueError('Bounded closure flag extraction')
            if isinstance(item,dict):
                for key,entry in item.items():
                    if key in FLAGS and type(entry) is bool:flags.append(dict(path=prefix+key,value=entry))
                    if isinstance(entry,(dict,list)):pending.append((prefix+key+'.',entry))
            elif isinstance(item,list):
                for index,entry in enumerate(item):
                    if isinstance(entry,(dict,list)):pending.append((prefix+str(index)+'.',entry))
        receipts.append(dict(role=name,present=True,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),flags=flags))
    lock=DATA/'recordings/locks'/(SESSION+'.lock');lease=None
    if lock.exists():
        info(lock,65536);lease=lock.open('rb');fcntl.flock(lease,fcntl.LOCK_SH|fcntl.LOCK_NB)
    try:
        database=DATA/'recordings/history.sqlite3';before=info(database,128*1024**2);sidecars={}
        for suffix,maximum in (('-wal',16*1024**2),('-shm',1024**2),('-journal',16*1024**2)):
            path=Path(str(database)+suffix)
            sidecars[suffix]=info(path,maximum) if path.exists() else None
            if suffix in ('-wal','-journal') and sidecars[suffix] and sidecars[suffix]['bytes']:
                raise ValueError('Nonempty WAL/journal requires separately verified read-only snapshot; never ignore or mutate it')
        db=sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=1)
        db.row_factory=sqlite3.Row;began=time.monotonic();calls=[0]
        def progress():
            calls[0]+=1
            return 1 if calls[0]>20000 or time.monotonic()-began>8 else 0
        db.set_progress_handler(progress,1000)
        try:
            db.execute('PRAGMA query_only=ON');db.execute('PRAGMA trusted_schema=OFF')
            db.execute('PRAGMA temp_store=MEMORY');db.execute('PRAGMA cache_size=-2048')
            row=db.execute('SELECT status,processed_samples,raw_samples,include_raw,spec FROM sessions WHERE id=?',(SESSION,)).fetchone()
            if row is None:raise ValueError('Exact failed session is absent')
            spec_values=strict(row['spec'].encode())
            events=[dict(item) for item in db.execute('SELECT event_type,COUNT(*) AS count,SUM(payload_bytes) AS original_payload_bytes,SUM(LENGTH(CAST(payload AS BLOB))) AS stored_payload_bytes,SUM(CASE WHEN payload_encoding="zlib-json-v1" THEN LENGTH(CAST(payload AS BLOB)) ELSE 0 END) AS compressed_stored_bytes,SUM(2*LENGTH(CAST(payload AS BLOB))+1024) AS estimated_charge FROM events WHERE session_id=? GROUP BY event_type LIMIT 33',(SESSION,))]
            if len(events)>32 or any(re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}',item['event_type']) is None for item in events):
                raise ValueError('Bounded event type labels required')
            usage=db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',(SESSION,)).fetchone()
            captions=dict(db.execute('SELECT COUNT(*) AS count,COALESCE(SUM(CASE WHEN LENGTH(TRIM(text))>0 THEN 1 ELSE 0 END),0) AS nonempty_count,COALESCE(SUM(LENGTH(CAST(text AS BLOB))),0) AS total_text_bytes,COALESCE(SUM(LENGTH(CAST(provenance AS BLOB))),0) AS total_provenance_bytes,COALESCE(SUM(2*(LENGTH(CAST(text AS BLOB))+LENGTH(CAST(provenance AS BLOB)))+1024),0) AS estimated_charge FROM captions WHERE session_id=?',(SESSION,)).fetchone())
            artifacts=dict(db.execute('SELECT COUNT(*) AS count,COALESCE(SUM(2*(LENGTH(CAST(path AS BLOB))+LENGTH(CAST(role AS BLOB)))+1024),0) AS estimated_charge FROM artifacts WHERE session_id=?',(SESSION,)).fetchone())
            segments=[dict(item) for item in db.execute('SELECT kind,COUNT(*) AS count,SUM(samples) AS samples,MIN(start_sample) AS first_sample,MAX(start_sample+samples) AS end_sample FROM segments WHERE session_id=? GROUP BY kind LIMIT 3',(SESSION,))]
        finally:db.close()
        if info(database,128*1024**2)!=before:raise ValueError('History database changed during read-only inspection')
        for suffix,prior in sidecars.items():
            path=Path(str(database)+suffix);after=info(path,16*1024**2) if path.exists() else None
            if prior!=after:raise ValueError('SQLite sidecar changed during read-only inspection')
        allowance=request_values.get('storage_policy',{}).get('metadata_allowance_bytes',1024**2)
        reserve=spec_values.get('metadata_reserve_bytes',0);split=spec_values.get('metadata_split')
        denominator=4 if split=='text3_sqlite1_v1' else 6 if split is None else None
        if denominator is None or type(reserve) is not int or type(allowance) is not int:raise ValueError('Exact typed metadata split required')
        result=dict(status='FAILED19_NUMERIC_STORAGE_READ_ONLY',boot_id=BOOT,package_manifest_sha256=PIN,
            session_id=SESSION,session_status=row['status'],processed_samples=row['processed_samples'],raw_samples=row['raw_samples'],
            include_raw=row['include_raw'],spec_numeric=dict(sample_rate=spec_values.get('sample_rate'),duration_seconds=spec_values.get('duration_seconds'),
                metadata_reserve_bytes=reserve,metadata_split=split,text_reserve_bytes=reserve-reserve//denominator,
                sqlite_reserve_bytes=reserve//denominator+allowance,closing_allowance_bytes=min(allowance//4,256*1024)),
            metadata_usage=dict(usage) if usage else None,events=events,captions=captions,artifacts=artifacts,segments=segments,
            old_owners=owners,old_unit_properties=properties,closure_receipts=receipts,
            database_identity=before,database_sha256=digest(database,128*1024**2),sqlite_sidecars=sidecars,
            shared_existing_session_lease=lease is not None,query_progress_calls=calls[0],
            native_payload_writes=False,capture_started=False,models_started=False,text_vectors_media_returned=False)
        if len(encoded(result))>65536:raise ValueError('Numeric diagnostic response bound')
        return result
    finally:
        if lease is not None:lease.close()


if 'PAYLOAD' in globals():RESULT=inspect(PAYLOAD,BASELINE)
