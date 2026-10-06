"""Independently restore the exact closed database+failed19 backup. See README_SPEECH19_BACKUP_RESTORE_V2.md."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
import uuid

PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BACKUP=PRIVATE/'production-backup-09-reconcile-01'
MANIFEST_SHA='967cdf170037b4454a317843fd7e53d65b51a0ad7396f30aed9dab8dbdc6401a'
COMPLETE_SHA='9495c9bfe78ffb971f2ea5ab9d07c102252096297423b550c54d76e2bd85ecd4'
BOOT='0561d730-3cad-48e0-940a-fe3930c89665'
PIN24='1cb7b8c3ac07d7975b2a31585f94b6402d419a12a128b05758ed7af644319f4c'
LIMIT=128*1024**2


def safe(path):
    for item in (path,*path.parents):
        info=item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('Link/reparse path refused')
        if stat.S_ISREG(info.st_mode) and info.st_nlink!=1:
            raise ValueError('Hardlinked regular file refused')
    return path


def read(path,maximum):
    safe(path);info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>maximum:
        raise ValueError('Bounded regular metadata required')
    raw=path.read_bytes()
    if tuple(getattr(path.stat(),key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))!=tuple(getattr(info,key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')) or len(raw)!=info.st_size:raise ValueError('Metadata changed during read')
    return raw


def strict(raw):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('Duplicate JSON member')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(65536),b''):result.update(chunk)
    return result.hexdigest()


def relative(value):
    p=PurePosixPath(value)
    if type(value) is not str or p.is_absolute() or str(p)!=value or any(v in ('','.','..') for v in p.parts) or '\\' in value or ':' in value:
        raise ValueError('Canonical relative member required')
    return p


def inventory(root):
    safe(root);files={};dirs=set()
    for parent,children,names in os.walk(root,followlinks=False):
        for name in children:
            path=safe(Path(parent)/name);dirs.add(path.relative_to(root).as_posix())
        for name in names:
            path=safe(Path(parent)/name);info=path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size>32*1024**2:raise ValueError('Regular member/32MiB bound')
            files[path.relative_to(root).as_posix()]=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        if len(files)>512 or len(dirs)>64:raise ValueError('Finite restoration membership bound')
    return files,dirs


def bootstrap():
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p
    h=k.GetCurrentProcess();k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(h,16384):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not k.GetProcessTimes(h,*(ctypes.byref(v) for v in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('speech19-independent-restore-'+uuid.uuid4().hex);root.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
    (root/'REGISTERED_OWNER.json').write_text(json.dumps(owner,sort_keys=True))
    return root


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.parse_args()
    root=bootstrap()  # Before backup, source or project reads.
    started=time.monotonic()
    (root/'HOST_SCOPE.json').write_text(json.dumps(dict(maximum_bytes=LIMIT,maximum_seconds=600,issued_unix=time.time(),native_action=False)))
    records={}
    for path in (Path(__file__),Path(__file__).with_name('README_SPEECH19_BACKUP_RESTORE_V2.md')):
        raw=read(path,65536);records[path.name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        for folder in ('source-backup','source-restore'):
            target=root/folder/path.name;target.parent.mkdir(exist_ok=True)
            with target.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            if read(target,65536)!=raw:raise ValueError('Source independent restore differs')
    (root/'SOURCE_CLOSED.json').write_text(json.dumps(dict(files=records,independent_restores=True,closed_unix=time.time()),sort_keys=True))
    if shutil.disk_usage('C:/').free<50*1024**3 or shutil.disk_usage('G:/').free<75*1024**3+LIMIT:
        raise OSError('Existing C50GiB/G75GiB floors plus full restoration reserve required')
    manifest_raw=read(BACKUP/'MANIFEST.json',262144);complete_raw=read(BACKUP/'COMPLETE.json',65536)
    if hashlib.sha256(manifest_raw).hexdigest()!=MANIFEST_SHA or hashlib.sha256(complete_raw).hexdigest()!=COMPLETE_SHA:
        raise ValueError('Exact closed backup metadata pins differ')
    manifest,complete=strict(manifest_raw),strict(complete_raw)
    full=strict(read(BACKUP/'FULL_BACKUP.json',65536));job=strict(read(BACKUP/'JOB.json',65536))
    closure=complete['closure'];exit_record=closure['job_exit']
    if (complete.get('kind')!='COMPLETE' or complete.get('files')!=46 or complete.get('bytes')!=47256339 or
        complete.get('manifest_sha256')!=MANIFEST_SHA or complete.get('independent_readback') is not True or
        complete.get('source_before_after_verified') is not True or complete.get('source_deleted') is not False or
        closure.get('closed') is not True or closure.get('cgroup_empty') is not True or closure.get('exact_owner_gone') is not True or
        exit_record.get('natural_returncode')!=0 or exit_record.get('leases_released') is not True or exit_record.get('error') is not None or
        exit_record.get('output_budget_failure') is not None or job.get('boot_id')!=BOOT or job.get('package_manifest_sha256')!=PIN24 or
        closure.get('owner')!=job.get('owner') or exit_record.get('owner')!=job.get('owner') or
        closure.get('unit')!=job.get('unit') or exit_record.get('unit')!=job.get('unit') or
        closure.get('invocation_id')!=job.get('invocation_id') or exit_record.get('invocation_id')!=job.get('invocation_id') or
        full.get('root')!=str(BACKUP/'payload') or full.get('manifest_sha256')!=MANIFEST_SHA or full.get('completion_sha256')!=COMPLETE_SHA):
        raise ValueError('Actual independently closed backup required')
    files={};case=set()
    source_base='/home/peachyprototype/JustPeachy/data/runtime-v29/recordings/'
    session_base=source_base+'sessions/8c5d357f0acc4640bfcda4697d7e325b/'
    for row in manifest:
        name=str(relative(row['path']))
        if name in files or name.casefold() in case:raise ValueError('Duplicate/case-alias member')
        expected_source=source_base+'history.sqlite3' if name=='history.sqlite3' else session_base+name.removeprefix('session19/')
        if (name!='history.sqlite3' and not name.startswith('session19/')) or row.get('source')!=expected_source:
            raise ValueError('Only actual DB and failed19 scope may be restored')
        if type(row['identity']['bytes']) is not int or not 0<=row['identity']['bytes']<=32*1024**2:raise ValueError('Finite member bound')
        files[name]=row;case.add(name.casefold())
    dirs={str(relative(row['path'])) for row in complete['restoration_directories']}
    for name in dirs:
        if name!='session19' and not name.startswith('session19/'):raise ValueError('Only failed19 directories')
    if len(files)!=46 or sum(row['identity']['bytes'] for row in files.values())!=47256339 or len(dirs)!=8:
        raise ValueError('Exact complete scope counts differ')
    payload=BACKUP/'payload';before=inventory(payload)
    if set(before[0])!=set(files) or before[1]!=dirs:raise ValueError('Backup membership differs')
    restored=root/'restored';restored.mkdir()
    for name in sorted(dirs,key=lambda value:(value.count('/'),value)): (restored/name).mkdir()
    for name,row in files.items():
        if time.monotonic()-started>600:raise TimeoutError('Independent restoration600s boundary')
        source=payload/name;destination=restored/name
        before_identity=source.stat();sha=hashlib.sha256();count=0
        with source.open('rb') as src,destination.open('xb') as dst:
            for chunk in iter(lambda:src.read(65536),b''):
                if dst.write(chunk)!=len(chunk):raise OSError('Short independent restoration write')
                sha.update(chunk);count+=len(chunk)
            dst.flush();os.fsync(dst.fileno())
        if tuple(getattr(source.stat(),key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))!=tuple(getattr(before_identity,key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')) or count!=row['identity']['bytes'] or sha.hexdigest()!=row['sha256'] or digest(destination)!=row['sha256']:
            raise ValueError('Complete independent member hash/readback differs')
    if inventory(payload)!=before:raise ValueError('Backup changed during restoration')
    after=inventory(restored)
    if set(after[0])!=set(files) or after[1]!=dirs:raise ValueError('Independent restored membership differs')
    used=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())+len(dirs)*65536
    if used>LIMIT or time.monotonic()-started>600:raise ValueError('Restoration full128MiB/600s scope exceeded')
    result=dict(status='PASSED_INDEPENDENT_DB_FAILED19_RESTORE',files=46,bytes=47256339,directories=8,
        manifest_sha256=MANIFEST_SHA,completion_sha256=COMPLETE_SHA,history_sha256=files['history.sqlite3']['sha256'],
        full_member_readback=True,source_membership_unchanged=True,restored_membership_exact=True,
        native_backup_closure_verified=True,native_action=False,database_opened=False,
        scope='history database plus failed19 only; not a fresh backup of all user data',root=str(root),restored=str(restored),charged_bytes=used)
    (root/'RESULT.json').write_text(json.dumps(result,sort_keys=True));print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
