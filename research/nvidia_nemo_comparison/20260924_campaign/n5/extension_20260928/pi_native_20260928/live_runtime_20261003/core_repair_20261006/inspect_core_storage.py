"""Noncontent current runtime storage diagnostics. README_CORE_INSPECTION.md."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import time

PACKAGE=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-28')
DATA=Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
PIN='e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b'
BEGAN=time.monotonic()

def identity(path):
    item=path.lstat()
    if path.is_symlink() or not stat.S_ISREG(item.st_mode) or item.st_nlink!=1:
        raise ValueError('Independent regular inspection input required')
    return dict(device=item.st_dev,inode=item.st_ino,bytes=item.st_size,
        mtime_ns=item.st_mtime_ns,ctime_ns=item.st_ctime_ns,uid=item.st_uid,gid=item.st_gid,mode=oct(item.st_mode&0o777))

def digest(path,maximum):
    before=identity(path)
    if before['bytes']>maximum:raise ValueError('Finite diagnostic input')
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            if time.monotonic()-BEGAN>35:raise TimeoutError('Finite storage inspection')
            block=stream.read(16384)
            if not block:break
            value.update(block)
    if identity(path)!=before:raise RuntimeError('Diagnostic changed during hash')
    return dict(identity=before,sha256=value.hexdigest())

def command(args,maximum=16384):
    p=subprocess.run(args,capture_output=True,timeout=4)
    if len(p.stdout)+len(p.stderr)>maximum:
        return dict(returncode=p.returncode,overflow=True,stdout_tail=p.stdout[-maximum//2:].decode(errors='replace'),stderr_tail=p.stderr[-maximum//2:].decode(errors='replace'))
    return dict(returncode=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace'))

def inspect(payload,baseline):
    if (set(payload)!={'schema','package_manifest_sha256','expires_unix'}
        or payload['schema']!='just-peachy.core-storage-inspection.v1'
        or payload['package_manifest_sha256']!=PIN
        or type(payload['expires_unix']) not in (int,float)
        or not math.isfinite(payload['expires_unix'])
        or not time.time()<payload['expires_unix']<=time.time()+600):
        raise ValueError('Fresh exact build28 inspection required')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if baseline['boot_id']!=boot:raise ValueError('Current boot changed')
    manifest=PACKAGE/'PACKAGE_MANIFEST.json'
    if digest(manifest,262144)['sha256']!=PIN:raise ValueError('Activated package differs')
    storage=DATA/'recordings';database=storage/'history.sqlite3'
    files={}
    for suffix in ('','-wal','-shm','-journal'):
        p=Path(str(database)+suffix)
        files[suffix]=identity(p) if p.exists() else None
    v=os.statvfs(DATA)
    result=dict(status='CURRENT_CORE_STORAGE_READ_ONLY',boot_id=boot,package_manifest_sha256=PIN,
        sqlite_version=sqlite3.sqlite_version,available_bytes=v.f_bavail*v.f_frsize,
        free_inodes=v.f_favail,filesystem_block_size=v.f_frsize,
        database_files=files,processes=[],launches=[],sessions=[],native_payload_writes=False,
        capture_started=False,models_started=False)
    writers=[]
    for directory in Path('/proc').iterdir():
        if not directory.name.isdecimal():continue
        try:
            cmd=(directory/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if 'JustPeachy' not in cmd:continue
            row=dict(pid=int(directory.name),start_ticks=int((directory/'stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=boot)
            row['command']=cmd[:1024];row['limits']=(directory/'limits').read_text()
            handles=[]
            for fd in (directory/'fd').iterdir():
                try:target=os.readlink(fd)
                except (OSError,FileNotFoundError):continue
                if str(DATA) in target or '/dev/snd/' in target:
                    handles.append(dict(fd=fd.name,target=target))
                    if str(database) in target:writers.append(row['pid'])
                if len(handles)>64:raise ValueError('Finite data descriptor inventory')
            row['data_handles']=handles;result['processes'].append(row)
            if len(result['processes'])>16:raise ValueError('Finite current project process inventory')
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    result['mounts']=command(['findmnt','-T',str(DATA),'-o','TARGET,SOURCE,FSTYPE,OPTIONS','-n'])
    result['kernel_storage_errors']=command(['dmesg','--level=err,warn','--since','-30min'],8192)
    launches=DATA/'launches'
    if launches.exists():
        recent=sorted((p for p in launches.iterdir() if p.is_dir() and re.fullmatch('[0-9a-f]{32}',p.name)),key=lambda p:p.stat().st_mtime_ns,reverse=True)[:12]
        for folder in recent:
            row=dict(launch_id=folder.name,receipts={})
            for rel in ('SERVICE_EXIT.json','main/SERVICE_EXIT.json','worker/EXIT.json','CLOSED.json','STARTUP_ERROR.json'):
                path=folder/rel
                if not path.exists():continue
                before=identity(path)
                if before['bytes']>65536:raise ValueError('Finite closure diagnostic')
                value=json.loads(path.read_bytes())
                row['receipts'][rel]=dict(identity=before,owner=value.get('owner'),
                    error=value.get('error'),error_details=value.get('error_details'),
                    exit_code=value.get('exit_code'),sqlite_errorcode=value.get('sqlite_errorcode'),sqlite_errorname=value.get('sqlite_errorname'))
            result['launches'].append(row)
    sessions=storage/'sessions'
    if sessions.exists():
        recent=sorted((p for p in sessions.iterdir() if p.is_dir() and re.fullmatch('[0-9a-f]{32}',p.name)),key=lambda p:p.stat().st_mtime_ns,reverse=True)[:12]
        for folder in recent:
            row=dict(session_id=folder.name,owner_exists=(folder/'owner.json').exists(),files=[])
            for path in folder.rglob('*'):
                if path.is_file():
                    row['files'].append(dict(path=path.relative_to(folder).as_posix(),bytes=path.stat().st_size))
                if len(row['files'])>256:raise ValueError('Finite recent session inventory')
            result['sessions'].append(row)
    sidecar_busy=any(files[s] and files[s]['bytes'] for s in ('-wal','-journal'))
    result['database_query_skipped_reason']='active_database_handle' if writers else 'nonempty_wal_or_journal' if sidecar_busy else None
    if not writers and not sidecar_busy and files['']:
        before=identity(database);db=sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=1)
        start=time.monotonic();db.set_progress_handler(lambda: int(time.monotonic()-start>5),1000)
        try:
            db.row_factory=sqlite3.Row
            db.execute('PRAGMA query_only=ON');db.execute('PRAGMA trusted_schema=OFF')
            db.execute('PRAGMA cache_size=-2048');db.execute('PRAGMA temp_store=MEMORY')
            result['sqlite_quick_check']=[r[0] for r in db.execute('PRAGMA quick_check(1)')]
            result['sqlite_page_size']=db.execute('PRAGMA page_size').fetchone()[0]
            result['sqlite_pages']=db.execute('PRAGMA page_count').fetchone()[0]
            result['sqlite_free_pages']=db.execute('PRAGMA freelist_count').fetchone()[0]
            result['indexed_sessions']=[dict(r) for r in db.execute('SELECT id,status,processed_samples,raw_samples FROM sessions ORDER BY rowid DESC LIMIT 12')]
            result['caption_totals']=dict(db.execute('SELECT COUNT(*) AS rows,COUNT(DISTINCT session_id) AS sessions,SUM(LENGTH(text)) AS text_characters FROM captions').fetchone())
        except sqlite3.Error as exc:
            result['sqlite_error']=dict(type=type(exc).__name__,message=str(exc),sqlite_errorcode=getattr(exc,'sqlite_errorcode',None),sqlite_errorname=getattr(exc,'sqlite_errorname',None))
        finally:db.close()
        if identity(database)!=before:raise RuntimeError('Database changed during read-only query')
    result['database_handle_pids']=sorted(set(writers))
    result['recent_unit_errors']=command(['journalctl','--user','--no-pager','-n','100','-o','cat','--grep','disk I/O|OperationalError|SQLite|Traceback|SIGXFSZ'],16384)
    raw=json.dumps(result,sort_keys=True,allow_nan=False).encode()
    if len(raw)>65536:raise ValueError('Compact structural diagnostic limit')
    return result

if 'PAYLOAD' in globals():RESULT=inspect(PAYLOAD,BASELINE)
