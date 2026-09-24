"""Bounded Windows atomic JSON replacement retries. See README_IO.md."""
from __future__ import annotations
import json
import os
from pathlib import Path
import time
import uuid

IO_VERSION='n2-windows-atomic-replace-retry-v1'


def atomic(path,value,*,timeout_sec=2.0):
    """Durably stage JSON, retry only transient Windows replacement denials.

    The two-second deadline covers replacement retries. Write/fsync failures
    propagate immediately. Failed replacement preserves its unique temporary
    file for diagnosis; it never changes permissions or deletes the target.
    """
    if not 0<timeout_sec<=2.0:
        raise ValueError('Atomic replacement retry bound must be in (0,2] seconds')
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temporary.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    deadline=time.monotonic()+timeout_sec
    delay=.01
    while True:
        try:
            os.replace(temporary,path)
            return
        except PermissionError as exc:
            remaining=deadline-time.monotonic()
            if getattr(exc,'winerror',None) not in (5,32,33) or remaining<=0:
                raise
            time.sleep(min(delay,remaining))
            delay=min(.2,delay*1.7)
