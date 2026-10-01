"""Native closed-broker local backup; README_FIELD_LOCAL_CAPSULE_V3.md."""
from datetime import datetime, timezone
import fcntl
import hashlib
import math
import os
from pathlib import Path, PurePosixPath
import re
import resource
import shutil
import subprocess
import time

from field_local_release_plan_v2 import validate_research_operation, encoded
from field_operator_session_plan_v3 import validate_policy
from field_operator_session_ledger_v4 import read, file_pin, identity, ticks
from field_operator_health_v1 import _inspect
from field_operator_broker_streamed_mirror_v1 import (
    plan, inventory, ancestors, real, identity as file_identity,
    _readback, CHUNK, MAX_MANIFEST)
from field_local_release_files_v6 import sync


def unit_closed(unit):
    if type(unit) is not str or not re.fullmatch(r'jp-[a-z0-9-]{1,100}\.service', unit):
        raise ValueError('Explicit owned research service')
    proc = subprocess.run(['systemctl','--user','show',unit,'-p','LoadState',
        '-p','ActiveState','-p','SubState','-p','MainPID'],capture_output=True,timeout=5)
    if len(proc.stdout)>4096 or len(proc.stderr)>4096:
        raise ValueError('Bounded unit observation')
    values=dict(line.split('=',1) for line in proc.stdout.decode().splitlines())
    if values.get('MainPID')!='0' or values.get('ActiveState') not in ('inactive','failed') or values.get('SubState') not in ('dead','failed'):
        raise RuntimeError('Source service still active or unknown')
    if proc.returncode not in (0,1) or values.get('LoadState') not in ('loaded','not-found'):
        raise RuntimeError('Source service observation failed')
    return values


def copy_closed(source, destination, policy_sha256, source_unit, pinned_files, *,
                operation, deadline, maximum_bytes):
    """Copy once after actual closure checks, returning an unpublished receipt.

    Fresh enclosing admission must reserve the full source-policy allocation for
    this independent destination and a complete host backup. This API grants no
    source writes, activation, capture, policy increase or next-slot permission.
    """
    validate_research_operation(operation)
    if type(deadline) not in (int,float) or not math.isfinite(deadline):
        raise ValueError('Finite monotonic deadline')
    remaining=(datetime.fromisoformat(operation['expires_utc'])-datetime.now(timezone.utc)).total_seconds()
    if not time.monotonic()<deadline<=time.monotonic()+min(remaining,600):
        raise ValueError('Deadline inside fresh operation')
    if os.uname().machine!='aarch64' or os.sched_getaffinity(0)!={3}:
        raise ValueError('Native CPU3 backup worker')
    for kind,value in ((resource.RLIMIT_AS,134217728),(resource.RLIMIT_STACK,1048576),
                       (resource.RLIMIT_FSIZE,33554432)):
        if resource.getrlimit(kind)!=(value,value):raise ValueError('Exact native backup envelope')
    source=Path(source).absolute();destination=Path(destination).absolute()
    campaign=Path.home()/'JustPeachy/research/nemotron-20260928'
    if source.parent!=campaign or source.resolve()!=source:
        raise ValueError('Canonical existing broker source')
    ancestors(destination.parent)
    if not destination.is_relative_to(campaign) or destination==source or source in destination.parents or destination in source.parents:
        raise ValueError('Disjoint campaign-local destination')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Consumed destination; preserve partial copies')
    policy=read(source/'RELEASE.json')
    if policy['root']!=str(source) or file_pin(source/'RELEASE.json')['sha256']!=policy_sha256:
        raise ValueError('Exact immutable source policy')
    validate_policy(policy,now=datetime.fromisoformat(policy['issued_utc']))
    if type(maximum_bytes) is not int or maximum_bytes!=policy['allocation']['target_maximum_bytes']:
        raise ValueError('Full independent original broker reservation required')
    lock=os.open(source/'broker',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    leases=[]
    try:
        fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
        # Reuse receipt/owner/capsule checks, under this writer's separately
        # enforced envelope. The FSIZE0 public read-only entry is unchanged.
        health=_inspect(source,policy,policy_sha256)
        if health['status']!='CLOSED_HISTORY_AVAILABLE' or not health['minimum_free_floor_met']:
            raise RuntimeError('Actual closed source required; failed/unclosed source remains fenced')
        before_unit=unit_closed(source_unit)
        gate=read(source/'broker/GATE_RESULT.json')
        if not (gate['logical_success'] and gate['capture_closed'] and gate['worker_exact_dead'] and gate['pipe_closed']) or gate['returncode']!=0:
            raise ValueError('Actual successful gate closure required')
        for path in (campaign/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock'):
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BaseException:os.close(fd);raise
            leases.append(fd)
        def check():
            validate_research_operation(operation)
            if time.monotonic()>=deadline:raise TimeoutError('Local mirror deadline')
            if shutil.disk_usage(destination.parent).free<5*1024**3:raise RuntimeError('Pi free floor')
            available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
            if available<192*1024**2:raise RuntimeError('Available RAM stop floor')
            if Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()!='closed':
                raise RuntimeError('Capture must remain off')
            now=identity()
            for row in health['owners']:
                owner=row['owner']
                if now['boot_id']==owner['boot_id'] and ticks(owner['pid'])==owner['start_ticks']:
                    raise RuntimeError('Source owner alive')
        check()
        value=plan(source,pinned_files,deadline,maximum_bytes)
        public={k:v for k,v in value.items() if k!='source_identities'}
        # Include empty directories and both independent file inventories.
        if len(encoded(public))>MAX_MANIFEST:raise ValueError('Backup manifest ceiling')
        if shutil.disk_usage(destination.parent).free<5*1024**3+maximum_bytes:
            raise RuntimeError('Full local mirror plus physical free floor')
        destination.mkdir();sync(destination.parent)
        for name in sorted(value['directories'],key=lambda n:(n.count('/'),n)):
            check()
            if name:
                path=destination.joinpath(*PurePosixPath(name).parts)
                path.mkdir();sync(path.parent)
        chunks=0;copied={}
        for name,expected in sorted(value['files'].items()):
            check()
            src=source.joinpath(*PurePosixPath(name).parts)
            dst=destination.joinpath(*PurePosixPath(name).parts)
            ancestors(src.parent);ancestors(dst.parent)
            if file_identity(real(src))!=value['source_identities'][name]:
                raise RuntimeError('Source changed before copy')
            h=hashlib.sha256();count=0
            with src.open('rb',buffering=0) as reader,dst.open('xb',buffering=0) as writer:
                while True:
                    check();block=reader.read(CHUNK)
                    if not block:break
                    if count+len(block)>expected['bytes']:raise ValueError('Source grew')
                    pending=memoryview(block)
                    while pending:
                        n=writer.write(pending)
                        if not n:raise OSError('Incomplete local mirror write')
                        pending=pending[n:];count+=n
                    h.update(block);chunks+=1
                os.fsync(writer.fileno())
            sync(dst.parent)
            if count!=expected['bytes'] or h.hexdigest()!=expected['sha256'] or file_identity(real(src))!=value['source_identities'][name]:
                raise ValueError('Exact source bytes and identity required')
            _readback(dst,expected,deadline)
            copied[name]=file_identity(real(dst))
        # Independent full readback pass after every file has been copied.
        for name,expected in sorted(value['files'].items()):
            check();_readback(destination.joinpath(*PurePosixPath(name).parts),expected,deadline)
        after,dirs=inventory(source,deadline);mirror,mirror_dirs=inventory(destination,deadline)
        if after!=value['source_identities'] or mirror!=copied or dirs!=set(value['directories']) or mirror_dirs!=dirs:
            raise ValueError('Exact full source/destination membership and identity')
        for name in sorted(value['directories'],key=lambda n:(n.count('/'),n),reverse=True):
            sync(destination.joinpath(*PurePosixPath(name).parts) if name else destination)
        sync(destination.parent);check();after_unit=unit_closed(source_unit)
        result=dict(schema='just-peachy.local-broker-backup.v1',
            status='COMPLETE_LOCAL_COPY_READBACK',source=str(source),destination=str(destination),
            policy_sha256=policy_sha256,source_unit=source_unit,
            unit_before=before_unit,unit_after=after_unit,owners=health['owners'],
            chunk_bytes=CHUNK,data_chunks=chunks,independent_full_readback=True,
            full_reserved_bytes=maximum_bytes,**public)
        if len(encoded(result))>MAX_MANIFEST:raise ValueError('Complete receipt ceiling')
        return result
    finally:
        for fd in leases:os.close(fd)
        os.close(lock)
