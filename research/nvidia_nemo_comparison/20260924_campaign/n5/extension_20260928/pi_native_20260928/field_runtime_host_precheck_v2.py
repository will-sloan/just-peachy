"""Compact full host owner/lifetime preread; README_RUNTIME_TITANET_INSTALL_V1.md."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
from datetime import datetime,timezone
import psutil

PARTIAL={
'operator-broker-qualification-v1-preparation/partial-contract-v1/truncated-source/broker/STAGE_OWNER.json',
'operator-broker-qualification-v1-preparation/partial-contract-v1/truncated-mirror/broker/STAGE_OWNER.json'}


def inspect(local,private,*,current_owner,deadline,guard):
    """Read all matching evidence; exclude only the current actual coordinator from live-host rejection."""
    local=Path(local);private=Path(private)
    me=psutil.Process()
    if current_owner!={'pid':me.pid,'create_time':me.create_time(),'affinity':[14]} or me.cpu_affinity()!=[14]:
        raise ValueError('Actual CPU14 current host owner required')
    def strict(raw):
        def pairs(rows):
            out={}
            for k,v in rows:
                if k in out:raise ValueError('Duplicate JSON key')
                out[k]=v
            return out
        def bad(v):raise ValueError('Nonfinite JSON')
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    selected={local/'supervision/worker.json':('owner',)}
    for base,dirs,names in os.walk(private,followlinks=False):
        guard()
        if time.monotonic()>=deadline:raise TimeoutError('Full host preread deadline')
        folder=Path(base)
        if folder.is_symlink() or getattr(folder.lstat(),'st_file_attributes',0)&0x400:
            raise ValueError('Private evidence reparse directory')
        lifetime=any('lifetime' in s.lower() for s in folder.parts)
        for name in names:
            upper=name.upper();path=folder/name;kinds=[]
            if 'OWNER' in upper and upper.endswith('.JSON') or name=='worker.json' and folder.name=='supervision':kinds.append('owner')
            if lifetime or 'LIFETIME' in upper or 'EVENT' in upper or 'MEMBER' in upper:kinds.append('lifetime')
            if upper.endswith('.JSON') and any(k in upper for k in ('ADMISSION','RESULT','PREFLIGHT','ENVELOPE','CENSUS')):kinds.append('metadata')
            if kinds:selected[path]=tuple(kinds)
    h=hashlib.sha256();host={};owner_count=life_count=metadata_count=0;read_bytes=0
    def identities(value):
        if type(value) is dict:
            for pk,tk in (('pid','create_time'),('child_pid','child_create_time')):
                if pk in value and tk in value and value[pk] is not None:
                    pid,created=value[pk],value[tk]
                    if type(pid) is not int or pid<=0 or type(created) not in (int,float) or not math.isfinite(created) or created<=0:
                        raise ValueError('Malformed completed host identity')
                    host[(pid,float(created))]=None
            for item in value.values():identities(item)
        elif type(value) is list:
            for item in value:identities(item)
    for path,kinds in sorted(selected.items(),key=lambda p:str(p[0])):
        guard()
        if time.monotonic()>=deadline:raise TimeoutError('Full host preread deadline')
        before=path.lstat()
        if not stat.S_ISREG(before.st_mode) or getattr(before,'st_file_attributes',0)&0x400 or before.st_size>32*1024**2:
            raise ValueError('Bounded real evidence file')
        raw=path.read_bytes();after=path.lstat()
        if len(raw)!=before.st_size or (before.st_ino,before.st_mtime_ns,before.st_size)!=(after.st_ino,after.st_mtime_ns,after.st_size):
            raise RuntimeError('Evidence changed during preread')
        read_bytes+=len(raw);h.update(str(path).encode()+b'\0'+hashlib.sha256(raw).digest())
        owner_count+='owner' in kinds;life_count+='lifetime' in kinds;metadata_count+='metadata' in kinds
        if 'owner' in kinds:
            relative=path.relative_to(private).as_posix() if path.is_relative_to(private) else ''
            if relative in PARTIAL:
                if raw!=b'{"pid":':raise ValueError('Historical partial fixture changed')
                continue
            value=strict(raw)
            if path.name=='OWNERSHIP_CLOSURE.json':
                # Typed closure is read and hashed, not converted to a process identity.
                if type(value) is not dict:raise ValueError('Typed nonidentity receipt')
                continue
            if type(value) not in (dict,list):raise ValueError('Completed owner evidence type')
            identities(value)
        elif 'metadata' in kinds:
            # Failed metadata is retained raw. Only actual OWNER records define this host process inventory.
            pass
    alive=[]
    for pid,created in host:
        if pid==me.pid and created==me.create_time():continue
        try:observed=psutil.Process(pid).create_time()
        except psutil.NoSuchProcess:continue
        if abs(observed-created)<.001:alive.append(dict(pid=pid,create_time=created))
    result=dict(schema='just-peachy.runtime-host-precheck.v1',observed_utc=datetime.now(timezone.utc).isoformat(),
        owner_paths_read=owner_count,lifetime_paths_read=life_count,inventory_sha256=h.hexdigest(),alive_owners=alive)
    if not owner_count or not life_count:raise ValueError('Complete owner/lifetime evidence absent')
    return result,dict(metadata_paths_read=metadata_count,read_bytes=read_bytes,unique_host_identities=len(host),
        current_coordinator_excluded=current_owner,typed_closures_are_not_processes=True)

