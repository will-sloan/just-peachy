"""Raw SQLite recovery primitives, no SessionStore. See README_DATABASE_RECOVERY.md."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

DATABASE = 'history.sqlite3'
SOURCE_PREFIX = 'runtime-data/recordings/'
SID = re.compile(r'[0-9a-f]{32}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')


def strict(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result:
                raise ValueError('Duplicate recovery metadata field')
            result[key] = value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite recovery metadata')))


def real_file(path, maximum=None):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or path.is_symlink() or
            getattr(info,'st_file_attributes',0)&0x400 or any(p.is_symlink() for p in path.parents) or
            maximum is not None and info.st_size > maximum):
        raise ValueError('Real single-link bounded recovery input required')
    return info


def digest(path):
    real_file(path)
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def identity(path):
    info = real_file(path)
    return dict(bytes=info.st_size,device=info.st_dev,inode=info.st_ino,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns)


def read_pinned_json(path, expected, maximum=2*1024**2):
    if not HASH.fullmatch(expected):
        raise ValueError('Exact SHA256 pin required')
    real_file(path,maximum)
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Recovery metadata pin differs')
    return strict(raw)


def write_receipt(path, value):
    raw = json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()+b'\n'
    if len(raw)>262144:
        raise ValueError('Recovery receipt exceeds bounded metadata record')
    with Path(path).open('xb') as stream:
        if stream.write(raw)!=len(raw):
            raise OSError('Short recovery receipt write')
        stream.flush()
        os.fsync(stream.fileno())
    if Path(path).read_bytes()!=raw:
        raise OSError('Recovery receipt independent readback differs')


def census_pair(census):
    rows = census.get('files')
    if type(rows) is not list:
        raise ValueError('Captured file census required')
    result = []
    for name in (DATABASE,DATABASE+'-journal'):
        found = [row for row in rows if row.get('path')==SOURCE_PREFIX+name]
        if len(found)!=1:
            raise ValueError('Exactly one captured database and journal required')
        row = found[0]
        if not HASH.fullmatch(row.get('sha256','')) or type(row.get('identity',{}).get('bytes')) is not int:
            raise ValueError('Captured database extent/hash contract differs')
        result.append(row)
    return result


def verify_pair(root, rows, *, native_identity=False):
    root = Path(root)
    result = []
    for row in rows:
        path = root/Path(row['path']).name
        actual = identity(path)
        if actual['bytes']!=row['identity']['bytes'] or digest(path)!=row['sha256']:
            raise ValueError('Database/journal copied extent or SHA256 differs')
        if native_identity and actual!=row['identity']:
            raise ValueError('Original database/journal source identity differs')
        result.append(dict(name=path.name,bytes=actual['bytes'],sha256=row['sha256'],identity=actual))
    for name in (DATABASE+'-wal',DATABASE+'-shm'):
        if (root/name).exists() or (root/name).is_symlink():
            raise ValueError('Uncaptured WAL/SHM cannot be ignored during recovery')
    return result


def copy_pair(source_root, target_root, rows):
    source_root, target_root = Path(source_root),Path(target_root)
    target_root.mkdir()
    if target_root.resolve().is_relative_to(source_root.resolve()):
        raise ValueError('Fresh recovery copy must be separate from source')
    before = verify_pair(source_root,rows)
    for row in rows:
        source,target = source_root/Path(row['path']).name,target_root/Path(row['path']).name
        with source.open('rb') as original,target.open('xb') as copied:
            while True:
                raw = original.read(16384)
                if not raw:
                    break
                if copied.write(raw)!=len(raw):
                    raise OSError('Short copied database write')
            copied.flush()
            os.fsync(copied.fileno())
    copied = verify_pair(target_root,rows)
    if verify_pair(source_root,rows)!=before:
        raise ValueError('Copied database source changed during copy')
    return copied


def sidecars(root):
    result = []
    for suffix in ('','-journal','-wal','-shm'):
        path = Path(root)/(DATABASE+suffix)
        if path.exists() or path.is_symlink():
            result.append(dict(name=path.name,bytes=real_file(path).st_size,sha256=digest(path)))
        else:
            result.append(dict(name=path.name,present=False))
    return result


def _known_json(root, relative, census):
    found = [row for row in census['files'] if row.get('path')==SOURCE_PREFIX+relative]
    if len(found)!=1:
        return None
    path = Path(root)/relative
    if not path.exists():
        return None
    row = found[0]
    if identity(path)['bytes']!=row['identity']['bytes']:
        raise ValueError('Stored-intent metadata extent differs')
    return read_pinned_json(path,row['sha256'],maximum=128*1024)


def deletion_metadata(root, session_id, census):
    marker = _known_json(root,'store.json',census)
    value = _known_json(root,'deletions/'+session_id+'.json',census)
    if value is None:
        return dict(explicit_stored_intent=False,partial_discard_candidate=False,
            basis='No census-verified explicit stored deletion intent; historical status is insufficient')
    required = {'schema','store_id','session_id','request_kind','requested_unix','origin_status','directories'}
    valid = (type(marker) is dict and marker.get('schema')==1 and type(value) is dict and
        set(value)==required and value['schema']=='just-peachy.session-deletion.v1' and
        value['store_id']==marker.get('store_id') and value['session_id']==session_id and
        value['request_kind'] in ('discard','delete') and
        value['origin_status'] in ('stopped','failed','cancelled','discarded','kept') and
        type(value['requested_unix']) in (int,float) and math.isfinite(value['requested_unix']) and
        type(value['directories']) is list and len(value['directories'])<=128)
    if not valid or value['request_kind']=='discard' and value['origin_status']=='kept':
        raise ValueError('Stored deletion intent ownership/contract differs')
    for item in value['directories']:
        if (type(item) is not str or not item or item.startswith('/') or '\\' in item or
                any(part in ('','..','.') for part in item.split('/'))):
            raise ValueError('Stored deletion intent path differs')
    if len(set(value['directories']))!=len(value['directories']):
        raise ValueError('Duplicate stored deletion intent path')
    return dict(explicit_stored_intent=True,partial_discard_candidate=value['request_kind']=='discard',
        request_kind=value['request_kind'],origin_status=value['origin_status'],
        requested_unix=value['requested_unix'],inspection_only=True,deletion_authorized_by_this_tool=False)


def recover_copy_or_original(root, *, metadata_root, census, recent=16, maximum_seconds=30):
    """Normal engine recovery only; no immutable URI, journal unlink or SessionStore."""
    if type(recent) is not int or not 1<=recent<=64 or not 0<maximum_seconds<=30:
        raise ValueError('Bounded metadata/VM inspection scope required')
    root = Path(root)
    before = sidecars(root)
    deadline = time.monotonic()+maximum_seconds
    db = sqlite3.connect(str(root/DATABASE),timeout=2,isolation_level=None)
    db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
    try:
        db.execute('PRAGMA cache_size=-2048')
        db.execute('PRAGMA temp_store=MEMORY')
        db.execute('PRAGMA busy_timeout=2000')
        if hasattr(db,'setlimit'):
            db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,262144)
            db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH,8192)
        db.execute('BEGIN IMMEDIATE')
        db.execute('ROLLBACK')
        check = db.execute('PRAGMA quick_check(1)').fetchall()
        if check != [('ok',)]:
            raise ValueError('Normal SQLite recovery quick_check did not return ok')
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'sessions','segments','captions'}<=tables:
            raise ValueError('Expected raw session-history schema unavailable')
        metadata = []
        for sid,status,spec in db.execute('SELECT id,status,spec FROM sessions ORDER BY seq DESC LIMIT ?',(recent,)):
            if not isinstance(sid,str) or not SID.fullmatch(sid):
                raise ValueError('Session metadata UUID differs')
            if status not in ('active','stopped','kept','discarded','failed','cancelled','deleting'):
                raise ValueError('Session metadata status differs')
            row = dict(session_id=sid,status=status)
            for table,key in (('captions','caption_count'),('segments','segment_count'),
                              ('events','event_count'),('artifacts','artifact_count')):
                row[key] = db.execute('SELECT count(*) FROM '+table+' WHERE session_id=?',(sid,)).fetchone()[0] if table in tables else None
            parsed = strict(spec) if isinstance(spec,str) and len(spec.encode())<=128*1024 else {}
            flag = parsed.get('audio_discarded') if type(parsed) is dict else None
            row.update(audio_discarded=flag if type(flag) is bool else None,
                audio_discarded_flag_present=type(flag) is bool,
                audio_discarded_scope='stored sessions.spec flag only; absence is not inferred from status')
            row['deletion'] = deletion_metadata(metadata_root,sid,census)
            metadata.append(row)
        return dict(quick_check='ok',sqlite_version=sqlite3.sqlite_version,cache_kib=2048,
            maximum_vm_seconds=maximum_seconds,recent_metadata=metadata,
            before_sidecars=before,after_sidecars=sidecars(root),
            normal_sqlite_recovery=True,immutable_uri=False,manual_journal_clear=False,
            recording_deletion=False,session_store_imported=False)
    finally:
        db.close()
