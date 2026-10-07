"""Owned snapshot reads/finalize using reviewed monitor primitives. README_PRODUCTION_BACKUP.md."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


def emit(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(raw.encode())>65536: raise ValueError('Backup protocol line cap')
    print(raw,flush=True)


def load(path,expected):
    if path.resolve(strict=True)!=path or path.is_symlink() or path.stat().st_size>131072:
        raise ValueError('Exact bounded probe dependency required')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('Probe dependency hash changed')
    spec=importlib.util.spec_from_file_location('verified_backup_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    spec.loader.exec_module(module);return module


def locked_snapshot(probe,common,job):
    root,status=probe.inspect(job)
    if (status['closed'] or status['observed_owner']!=job['owner'] or
        status['state'].get('ActiveState')!='active' or status['state'].get('MainPID')!=str(job['owner']['pid'])):
        raise ValueError('The exact admitted snapshot guard must remain active')
    locks=probe.read_json(root/'SNAPSHOT_LOCKS.json')
    ready=probe.read_json(root/'SNAPSHOT_READY.json')
    if (locks['owner']!=job['owner'] or ready['owner']!=job['owner'] or
        ready['invocation_id']!=job['invocation_id'] or not locks['hardware_exclusive'] or
        not locks['research_exclusive'] or locks['capture'] is not False):
        raise ValueError('Actual snapshot exclusion proof differs')
    with Path('/proc/locks').open('rb') as stream:raw=stream.read(2*1024**2+1)
    if len(raw)>2*1024**2:raise ValueError('Kernel lease census bound')
    lines=[line.split() for line in raw.decode().splitlines()]
    for row in locks['locks']:
        path=common.canonical(row['path']);info=path.stat()
        if info.st_dev!=row['device'] or info.st_ino!=row['inode']:
            raise ValueError('Snapshot lease file identity changed')
        matched=False
        for fields in lines:
            if len(fields)!=8 or fields[1:4]!=['FLOCK','ADVISORY','WRITE'] or fields[4]!=str(job['owner']['pid']):continue
            major,minor,inode=fields[5].split(':')
            if (int(major,16),int(minor,16),int(inode))==(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino):matched=True
        if not matched:raise ValueError('Exact snapshot guard no longer owns both kernel flock leases')
    with (root/'CENSUS.json').open('rb') as stream:raw=stream.read(common.MAX_CENSUS+1)
    if len(raw)>common.MAX_CENSUS or hashlib.sha256(raw).hexdigest()!=ready['census_sha256']:
        raise ValueError('Immutable snapshot census pin changed')
    census=common.strict(raw)
    common.validate_native_census(census)
    status.update(snapshot_locked=True,census_sha256=ready['census_sha256'],scope_sha256=ready['scope_sha256'])
    return root,status,census


def main():
    import resource,signal
    os.sched_setaffinity(0,{3})
    # Finalize can create exactly one small marker; all other paths are read-only.
    for kind,cap in ((resource.RLIMIT_AS,128*1024**2),(resource.RLIMIT_STACK,1024**2),
                     (resource.RLIMIT_FSIZE,16384),(resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(cap,cap))
    signal.alarm(15)
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    emit(dict(kind='OWNER',owner=owner,cpu=3,address_space_bytes=128*1024**2,stack_bytes=1024**2,
        file_size_limit=16384,alarm_seconds=15))
    raw=sys.stdin.buffer.read(65537)
    if len(raw)>65536:raise ValueError('Backup request bound')
    # Strict parsing is available only after pinned module loading; this provisional
    # parse selects those exact paths, then the request is parsed strictly below.
    request=json.loads(raw);package=Path(request['package'])
    probe=load(package/'native_job_probe.py',request['native_job_probe_sha256'])
    common=load(package/'backup_reconciliation.py',request['backup_reconciliation_sha256'])
    request=common.strict(raw);job=request['job']
    if request['mode']=='ready':
        root,status=probe.inspect(job)
        if status['closed'] or status['observed_owner']!=job['owner']:
            raise ValueError('Exact live snapshot guard required while awaiting census')
        status['snapshot_ready']=(root/'SNAPSHOT_READY.json').is_file()
        emit(status);return
    root,status,census=locked_snapshot(probe,common,job)
    admission=probe.read_json(root/'ADMISSION.json',262144)
    if (admission['payload']['package']!=str(package) or
        admission['payload']['package_manifest_sha256']!=job['package_manifest_sha256'] or
        admission['payload']['backup_scope_sha256']!=status['scope_sha256']):
        raise ValueError('Probe package and scope must match actual snapshot admission')
    emit(status)
    if request['mode']=='catalog':
        emit(dict(kind='CENSUS_BEGIN',schema=census['schema'],scope=census['scope'],bytes=census['bytes']))
        for row in census['files']:emit(dict(kind='CENSUS_FILE',value=row))
        for row in census['directories']:emit(dict(kind='CENSUS_DIRECTORY',value=row))
        for row in census['external_assets']:emit(dict(kind='CENSUS_ASSET',value=row))
        _,after,_=locked_snapshot(probe,common,job)
        emit(dict(kind='CENSUS_END',census_sha256=status['census_sha256'],snapshot=after));return
    if request['census_sha256']!=status['census_sha256']:
        raise ValueError('Requested live census pin differs')
    if request['mode']=='finalize':
        value=dict(owner=job['owner'],invocation_id=job['invocation_id'],census_sha256=status['census_sha256'])
        common.write(root/'FINALIZE.json',common.encoded(value))
        emit(dict(kind='FINALIZE_ACCEPTED',**value));return
    if request['mode']!='segment':raise ValueError('Explicit snapshot operation required')
    row=request['entry']
    if row not in census['files']:raise ValueError('Source must belong to exact admitted census')
    path=common.canonical(row['source'])
    if common.identity(path)!=row['identity']:raise ValueError('Snapshot member changed before transfer')
    offset=request['offset'];count=request['count'];size=row['identity']['bytes']
    if (type(offset) is not int or type(count) is not int or not 0<=count<=1024**2
        or not 0<=offset<=size or offset+count>size or count==0 and size!=0):
        raise ValueError('Bounded source segment required')
    emit(dict(kind='SEGMENT',entry=row,offset=offset,count=count))
    sha=hashlib.sha256();cursor=offset
    with path.open('rb') as stream:
        stream.seek(offset)
        while cursor<offset+count:
            block=stream.read(min(16384,offset+count-cursor))
            if not block:raise ValueError('Snapshot member truncated')
            emit(dict(kind='CHUNK',path=row['path'],offset=cursor,data=base64.b64encode(block).decode()))
            sha.update(block);cursor+=len(block)
    if common.identity(path)!=row['identity']:raise ValueError('Snapshot member changed during transfer')
    _,after,_=locked_snapshot(probe,common,job)
    emit(dict(kind='SEGMENT_END',path=row['path'],offset=offset,bytes=count,sha256=sha.hexdigest(),snapshot=after))


if __name__=='__main__':main()
