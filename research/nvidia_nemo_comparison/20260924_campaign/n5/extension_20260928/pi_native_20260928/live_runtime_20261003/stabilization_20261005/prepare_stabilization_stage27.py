"""Host-only exact build27 stage payload; see README_STAGE27_PREPARATION.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import base64
import ctypes
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
OLD=PRIVATE/'audit-preparation/stabilization-stage24-preparation-1791236770589'
INSTALLER_SHA='b4cbc107259556f901da1e47462b9ba238b766e56b7910c3c5982ea3fee68ad6'
ACTION_SHA='4f5876f32a634db420baf78583a7a0ebac7d27b17bab52aace867d78df0d1c74'
TARGET='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-27'
BOOT_HISTORY='0561d730-3cad-48e0-940a-fe3930c89665'

def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()

def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(item) for item in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('stabilization-stage27-preparation-'+uuid.uuid4().hex)
    root.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    with (root/'REGISTERED_OWNER.json').open('xb') as output:
        output.write(encoded(owner));output.flush();os.fsync(output.fileno())
    began=time.monotonic();written=(root/'REGISTERED_OWNER.json').stat().st_size
    def write(name,raw):
        nonlocal written
        if written+len(raw)>8*1024**2 or time.monotonic()-began>600:
            raise RuntimeError('Original finite 8 MiB/600s staging preparation scope')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Original host floor')
        with (root/name).open('xb') as output:
            if output.write(raw)!=len(raw):raise OSError('Short staging preparation write')
            output.flush();os.fsync(output.fileno())
        written+=len(raw)
        if (root/name).read_bytes()!=raw:raise OSError('Independent staging readback differs')
    def triple(name,raw):
        for suffix in ('','.backup','.restore'):write(name+suffix,raw)
    write('HOST_SCOPE.json',encoded(dict(maximum_bytes=8*1024**2,maximum_seconds=600,
        native_action=False,label='stabilization-stage27-01')))
    triple('PREPARER.py',Path(__file__).read_bytes())
    triple('README.md',(HERE/'README_STAGE27_PREPARATION.md').read_bytes())
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--archive-sha256',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--boot-id',required=True)
    args=parser.parse_args()
    try:
        prior_raw=(OLD/'PAYLOAD.json').read_bytes()
        if prior_raw!=(OLD/'PAYLOAD.json.backup').read_bytes() or prior_raw!=(OLD/'PAYLOAD.json.restore').read_bytes():
            raise ValueError('Closed stage24 payload independent restore differs')
        installer_raw=(OLD/'INSTALLER.py').read_bytes()
        action=(HERE/'stage_stabilization_action.py').read_bytes()
        if sha(installer_raw)!=INSTALLER_SHA or sha(action)!=ACTION_SHA:
            raise ValueError('Exact unchanged stage24 installer/action required')
        triple('INSTALLER.py',installer_raw);triple('ACTION.py',action)
        namespace=dict(__name__='verified_host_stage27_inspection')
        exec(compile(installer_raw,'<exact-stage24-installer>','exec'),namespace)
        prior=namespace['strict'](prior_raw)
        if (type(args.boot_id) is not str or re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',args.boot_id) is None or
            base64.b64decode(prior['installer_source_base64'],validate=True)!=installer_raw):
            raise ValueError('Exact current boot/installer payload binding required')
        if args.archive.is_symlink() or args.archive.stat().st_size>2*1024**2:
            raise ValueError('Original bounded regular package archive required')
        archive=args.archive.read_bytes()
        manifest,files=namespace['validate_payload'](archive,args.archive_sha256,args.manifest_sha256)
        if manifest['target']!=TARGET:raise ValueError('Exact fresh build27 target required')
        package=args.package.resolve(strict=True)
        actual=set();directories=set()
        for path in package.rglob('*'):
            if path.is_symlink():raise ValueError('Real package files required')
            name=path.relative_to(package).as_posix()
            if path.is_dir():directories.add(name)
            elif path.is_file():
                actual.add(name)
                if (name not in files or path.stat().st_size!=len(files[name]) or
                    path.read_bytes()!=files[name]):
                    raise ValueError('Full archive/expanded-package readback differs')
            else:raise ValueError('Unsupported package member')
        if actual!=set(files):raise ValueError('Complete package/archive membership differs')
        expanded=sum(map(len,files.values()))
        reservation=expanded+len(archive)+(len(directories)+1)*65536+65536
        payload=dict(prior,archive_base64=base64.b64encode(archive).decode(),
            archive_sha256=sha(archive),manifest_sha256=args.manifest_sha256,
            target_reservation_bytes=reservation,expected_boot_id=args.boot_id)
        payload_raw=encoded(payload);triple('PAYLOAD.json',payload_raw)
        for suffix in ('','.backup','.restore'):
            restored=namespace['strict']((root/('PAYLOAD.json'+suffix)).read_bytes())
            if (base64.b64decode(restored['archive_base64'],validate=True)!=archive or
                base64.b64decode(restored['installer_source_base64'],validate=True)!=installer_raw):
                raise ValueError('Independent decoded payload restore differs')
        if args.archive.read_bytes()!=archive or (package/'PACKAGE_MANIFEST.json').read_bytes()!=files['PACKAGE_MANIFEST.json']:
            raise ValueError('Bound package source changed during preparation')
        receipt=dict(output=str(root),action=str(root/'ACTION.py'),payload=str(root/'PAYLOAD.json'),
            owner=owner,label='stabilization-stage27-01',target=TARGET,boot_id=args.boot_id,
            manifest_sha256=args.manifest_sha256,archive_sha256=sha(archive),archive_bytes=len(archive),
            expanded_bytes=expanded,archive_members=len(files),directories=len(directories),
            target_reservation_bytes=reservation,
            allocation_formula='expanded+archive+(directories+1)*65536+65536',
            installer_source_sha256=INSTALLER_SHA,action_sha256=ACTION_SHA,
            source_backup_independent_restores=True,
            source_files={name:dict(bytes=(root/name).stat().st_size,
                sha256=sha((root/name).read_bytes())) for name in
                ('PREPARER.py','README.md','INSTALLER.py','ACTION.py','PAYLOAD.json')},
            prepared_bytes=written,native_action=False)
        write('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),elapsed=time.monotonic()-began,**receipt)))
        print(encoded(receipt).decode())
    except BaseException as error:
        write('FAILURE.json',encoded(dict(type=type(error).__name__,message=str(error))))
        raise

if __name__=='__main__':main()
