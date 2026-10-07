"""Read only structural check37 diagnostics. README_SQLITE_GUARD_INSPECTION.md."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time

DATA=Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
PACKAGE=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-29')
PIN='331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b'
LAUNCH=DATA/'launches/fc1472d113bb459fa78b67506b6d23cb'

def metadata(path):
    try:
        s=path.lstat()
    except FileNotFoundError:
        return None
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,nlink=s.st_nlink,
                mode=oct(s.st_mode),mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)

def read_json(path):
    before=metadata(path)
    if before is None:return None
    if (not stat.S_ISREG(int(before['mode'],8)) or before['nlink']!=1
        or before['bytes']>262144 or any(p.is_symlink() for p in path.parents)):
        raise ValueError('Independent bounded diagnostic file required: '+str(path))
    raw=path.read_bytes()
    if metadata(path)!=before:raise RuntimeError('Diagnostic changed during read')
    return dict(sha256=hashlib.sha256(raw).hexdigest(),identity=before,value=json.loads(raw))

def inspect(payload,baseline):
    if (set(payload)!={'schema','package_manifest_sha256','expires_unix'}
        or payload['schema']!='just-peachy.sqlite-guard-inspection.v1'
        or payload['package_manifest_sha256']!=PIN
        or type(payload['expires_unix']) not in (int,float)
        or not math.isfinite(payload['expires_unix'])
        or not time.time()<payload['expires_unix']<=time.time()+600):
        raise ValueError('Fresh exact inspection required')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if baseline['boot_id']!=boot:raise ValueError('Current boot changed')
    if hashlib.sha256((PACKAGE/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest()!=PIN:
        raise ValueError('Package differs')
    result=dict(status='CHECK37_GUARD_FAILURE_READ_ONLY',boot_id=boot,
                package_manifest_sha256=PIN,database_files={},launch_files=[],receipts={},
                capture_started=False,models_started=False,native_payload_writes=False)
    db=DATA/'recordings/history.sqlite3'
    for suffix in ('','-journal','-wal','-shm'):
        result['database_files'][suffix]=metadata(Path(str(db)+suffix))
    for p in LAUNCH.rglob('*'):
        if p.is_symlink():raise ValueError('Unexpected launch symlink')
        if not p.is_file():continue
        name=p.relative_to(LAUNCH).as_posix()
        result['launch_files'].append(dict(path=name,identity=metadata(p)))
        if len(result['launch_files'])>128:raise ValueError('Finite launch diagnostics')
        if p.name not in ('RESULT.json','EXIT.json','SESSION.json','REGISTERED_OWNER.json','CLOSED.json','SERVICE_EXIT.json'):continue
        item=read_json(p);value=item.pop('value')
        fields=('session_id','failure','failure_diagnostics','cleanup_error','logical_cleanup_complete',
                'post_stop_choice_pending','physical_process_closed','owner','worker','exit_code','error')
        item['facts']={key:value[key] for key in fields if key in value}
        result['receipts'][name]=item
    return result

if 'PAYLOAD' in globals():RESULT=inspect(PAYLOAD,BASELINE)
