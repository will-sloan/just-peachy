"""CPU14 host certificate/payload preparation only. README_DATABASE_RECOVERY_V2.md."""
import ctypes
import os

kernel = ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p,ctypes.c_size_t]
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
handle = kernel.GetCurrentProcess()
if not kernel.SetProcessAffinityMask(handle,16384):
    raise ctypes.WinError(ctypes.get_last_error())
stamps = [ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())

import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--backup-root',type=Path,required=True)
for name in ('census','manifest','complete','scope','package-manifest','copy-result'):
    parser.add_argument('--'+name+'-sha256',required=True)
parser.add_argument('--package',type=Path,required=True)
parser.add_argument('--copy-result',type=Path,required=True)
parser.add_argument('--boot-id',required=True)
parser.add_argument('--maximum-file-bytes',type=int,required=True)
parser.add_argument('--output',type=Path,required=True)
args = parser.parse_args()
args.output.mkdir()
owner = dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
    affinity_mask=16384,creation_filetime=stamps[0].value,
    create_time=(stamps[0].value-116444736000000000)/1e7)
with (args.output/'REGISTERED_OWNER.json').open('xb') as stream:
    raw = json.dumps(owner,sort_keys=True).encode()
    stream.write(raw);stream.flush();os.fsync(stream.fileno())

from core_database_recovery import (census_pair,digest,identity,read_pinned_json,
    real_file,write_receipt)


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def main():
    started = time.monotonic()
    pins = []
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free<floor+4*1024**2:
            raise OSError('Host source/certificate reserve unavailable')
    for index,name in enumerate(('prepare_core_database_recovery_v2.py','recover_core_database_v2.py',
                                 'core_database_recovery.py','README_DATABASE_RECOVERY_V2.md')):
        source = Path(__file__).with_name(name)
        real_file(source,262144)
        body = source.read_bytes()
        for suffix in ('backup','restore'):
            with (args.output/('SOURCE_%02d.%s'%(index,suffix))).open('xb') as stream:
                stream.write(body);stream.flush();os.fsync(stream.fileno())
        if ((args.output/('SOURCE_%02d.backup'%index)).read_bytes()!=body or
            (args.output/('SOURCE_%02d.restore'%index)).read_bytes()!=body or source.read_bytes()!=body):
            raise OSError('Source backup/independent restore differs')
        pins.append(dict(path=str(source),bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
    root = args.backup_root
    census = read_pinned_json(root/'CENSUS.json',args.census_sha256)
    rows = read_pinned_json(root/'MANIFEST.json',args.manifest_sha256)
    complete = read_pinned_json(root/'COMPLETE.json',args.complete_sha256)
    copy_result = read_pinned_json(args.copy_result,args.copy_result_sha256)
    scope = census['scope']
    closure = complete.get('closure',{})
    if (type(rows) is not list or rows!=census['files'] or
        hashlib.sha256(encoded(scope)).hexdigest()!=args.scope_sha256 or
        scope.get('reviewed') is not True or
        [r.get('destination') for r in scope.get('roots',[])]!=
            ['package','runtime-data','desktop.desktop','autostart.desktop','display-config'] or
        complete.get('kind')!='COMPLETE' or
        any(complete.get(k) is not True for k in ('independent_readback','source_before_after_verified')) or
        complete.get('census_sha256')!=args.census_sha256 or
        complete.get('manifest_sha256')!=args.manifest_sha256 or
        any(closure.get(k) is not True for k in ('closed','exact_owner_gone','cgroup_empty')) or
        closure.get('job_exit',{}).get('natural_returncode')!=0 or closure.get('job_exit',{}).get('error') or
        complete.get('files')!=len(rows) or complete.get('bytes')!=sum(r['identity']['bytes'] for r in rows)):
        raise ValueError('Actual completed full backup, pins, extent and natural owner closure required')
    pair = census_pair(census)
    if (copy_result.get('schema')!='just-peachy.core-database-copy-recovery.v1' or
        copy_result.get('status')!='PASS' or copy_result.get('source_copied_files_unchanged') is not True or
        copy_result.get('recovery',{}).get('quick_check')!='ok' or
        [(r['bytes'],r['sha256']) for r in copy_result['recovery']['before_sidecars'][:2]]!=
            [(r['identity']['bytes'],r['sha256']) for r in pair]):
        raise ValueError('Successful exact copied database/journal recovery must precede admission')
    payload_root = root/'payload'
    expected = set()
    for row in rows:
        name = row['path'];rel = PurePosixPath(name)
        if (rel.is_absolute() or '..' in rel.parts or '\\' in name or rel.as_posix()!=name or name in expected):
            raise ValueError('Exact unique canonical full-backup membership required')
        expected.add(name)
        source = payload_root.joinpath(*rel.parts)
        before = identity(source)
        if (before['bytes']!=row['identity']['bytes'] or digest(source)!=row['sha256'] or
            identity(source)!=before or time.monotonic()-started>600):
            raise ValueError('Independent full-backup member readback differs or timed out')
    found = set()
    for directory,children,files in os.walk(payload_root,followlinks=False):
        for name in children:
            if (Path(directory)/name).is_symlink():
                raise ValueError('Real full-backup directory membership required')
        for name in files:
            source = Path(directory)/name;real_file(source)
            found.add(source.relative_to(payload_root).as_posix())
    if found!=expected:
        raise ValueError('Full backup has missing or unlisted regular files')
    manifest = read_pinned_json(args.package/'PACKAGE_MANIFEST.json',args.package_manifest_sha256,262144)
    if not re.fullmatch(r'/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-\d{2}',manifest.get('target','')):
        raise ValueError('Actual immutable native package target required')
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',args.boot_id):
        raise ValueError('Actual observed current boot UUID required')
    if args.maximum_file_bytes<=sum(r['identity']['bytes'] for r in pair)+65536:
        raise ValueError('Actual observed filesystem-derived FSIZE must cover the existing pair')
    certificate = dict(schema='just-peachy.full-backup-host-certificate.v1',
        census_sha256=args.census_sha256,manifest_sha256=args.manifest_sha256,
        complete_sha256=args.complete_sha256,scope_sha256=args.scope_sha256,
        files=len(rows),bytes=complete['bytes'],
        scope_roots=[r['destination'] for r in scope['roots']],database_source=pair,
        whole_backup_complete=True,independent_payload_readback=True,
        source_before_after_verified=True,native_backup_owner_closed=True)
    library = Path(__file__).with_name('core_database_recovery.py').read_bytes()
    action = Path(__file__).with_name('recover_core_database_v2.py').read_bytes()
    compile(library,'<prepared-recovery-library>','exec')
    compile(action,'<prepared-recovery-action>','exec')
    payload = dict(schema='just-peachy.core-database-recovery.v2',package=manifest['target'],
        package_manifest_sha256=args.package_manifest_sha256,boot_id=args.boot_id,
        expires_unix=time.time()+290,original_db_recovery=True,database_source=pair,
        maximum_file_bytes=args.maximum_file_bytes,accepted_full_backup=certificate,
        accepted_full_backup_sha256=hashlib.sha256(encoded(certificate)).hexdigest(),
        library_source_b64=base64.b64encode(library).decode(),
        library_source_sha256=hashlib.sha256(library).hexdigest())
    write_receipt(args.output/'HOST_CERTIFICATE.json',certificate)
    write_receipt(args.output/'PAYLOAD.json',payload)
    for pin in pins:
        if digest(pin['path'])!=pin['sha256']:
            raise ValueError('Recovery source changed during preparation')
    for name,pin in (('CENSUS.json',args.census_sha256),('MANIFEST.json',args.manifest_sha256),('COMPLETE.json',args.complete_sha256)):
        if digest(root/name)!=pin:
            raise ValueError('Accepted full backup proof changed during preparation')
    write_receipt(args.output/'RESULT.json',dict(status='PREPARED',owner=owner,native_action=False,
        native_dispatched=False,action_name='recover_core_database_v2.py',action_sha256=hashlib.sha256(action).hexdigest(),
        payload_sha256=digest(args.output/'PAYLOAD.json'),certificate_sha256=payload['accepted_full_backup_sha256'],
        source_pins=pins,source_unchanged=True,full_payload_members_verified=len(rows),
        full_payload_bytes_verified=complete['bytes'],elapsed_seconds=time.monotonic()-started))
    print(encoded(dict(status='PREPARED',output=str(args.output),native_dispatched=False)).decode())


status = 'FAILED'
try:
    main();status='PREPARED'
finally:
    write_receipt(args.output/'HOST_EXIT.json',dict(owner=owner,status=status,native_dispatched=False,
        physical_closure_claimed=False))
