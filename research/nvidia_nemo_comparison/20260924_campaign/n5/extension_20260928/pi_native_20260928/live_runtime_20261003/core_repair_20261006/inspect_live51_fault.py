"""Read exact closed Live51 source metadata; README_LIVE51_FAULT.md."""
import hashlib
import json
from pathlib import Path
import stat

ROOT=Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
BOOT='e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
if BASELINE['boot_id'] != BOOT or BASELINE['current_project_processes'] or BASELINE['active_recorded_owners'] or BASELINE['live_manager_owners']:
    raise ValueError('Current boot and all closed source/worker ownership required')
paths={
 'source':ROOT/'recordings/sessions/1b222a64540948439e81ea7189493cf3/work/source/SOURCE_CLOSE.json',
 'host':ROOT/'launches/97767498d8af43c6a2b8519f3f7ff4db/HOST_CLOSURE.json',
 'session':ROOT/'launches/97767498d8af43c6a2b8519f3f7ff4db/worker/SESSION.json'}
rows={}
for name,path in paths.items():
    before=path.lstat()
    if path.is_symlink() or path.resolve(strict=True)!=path or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>262144:
        raise ValueError('Exact bounded immutable failure metadata required')
    raw=path.read_bytes();after=path.stat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('Failure metadata changed')
    value=json.loads(raw)
    if name=='session' and value.get('session_id')!='1b222a64540948439e81ea7189493cf3':raise ValueError('Actual failed session differs')
    rows[name]=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),document=value)
RESULT=dict(schema='just-peachy.live51-source-fault-inspection.v1',native_writes=False,rows=rows)
