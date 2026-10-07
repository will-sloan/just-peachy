"""CPU14 recovery of verified PC backup copies only. See README_DATABASE_RECOVERY.md."""
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
import json
from pathlib import Path
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--census',type=Path,required=True)
parser.add_argument('--census-sha256',required=True)
parser.add_argument('--payload-root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True,help='Fresh nonexistent private output directory')
args = parser.parse_args()
args.output.mkdir()
owner = dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
    affinity_mask=16384,creation_filetime=stamps[0].value,
    create_time=(stamps[0].value-116444736000000000)/1e7)
raw = json.dumps(owner,sort_keys=True).encode()
with (args.output/'REGISTERED_OWNER.json').open('xb') as stream:
    stream.write(raw)
    stream.flush()
    os.fsync(stream.fileno())

import hashlib
import shutil
import sys
import traceback
from core_database_recovery import (read_pinned_json,census_pair,verify_pair,copy_pair,
    write_receipt,recover_copy_or_original,digest,sidecars)

started = time.monotonic()
failure, report, initial = None,None,None
try:
    census = read_pinned_json(args.census,args.census_sha256)
    rows = census_pair(census)
    source_root = args.payload_root/'runtime-data'/'recordings'
    maximum = 2*sum(row['identity']['bytes'] for row in rows)+4*1024**2
    write_receipt(args.output/'HOST_SCOPE.json',dict(issued_unix=time.time(),owner=owner,
        maximum_bytes=maximum,maximum_seconds=120,native_action=False,models=False,
        copied_files_only=True,whole_backup_certified=False))
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free-maximum<floor:
            raise OSError('Actual host filesystem reserve unavailable')
    code_pins = []
    for index,name in enumerate(('core_database_recovery.py','recover_core_database_copy.py',
                                'recover_core_database.py','README_DATABASE_RECOVERY.md')):
        path = Path(__file__).with_name(name)
        body = path.read_bytes()
        if len(body)>262144:
            raise ValueError('Bounded recovery source input required')
        with (args.output/('SOURCE_%02d.backup'%index)).open('xb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        with (args.output/('SOURCE_%02d.restore'%index)).open('xb') as stream:
            restored = (args.output/('SOURCE_%02d.backup'%index)).read_bytes()
            stream.write(restored)
            stream.flush()
            os.fsync(stream.fileno())
        if restored!=body or (args.output/('SOURCE_%02d.restore'%index)).read_bytes()!=body or path.read_bytes()!=body:
            raise OSError('Recovery source independent restore differs')
        code_pins.append(dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
    write_receipt(args.output/'SOURCE_CLOSED.json',dict(pins=code_pins,backup_and_independent_restore=True))
    # Verify BOTH original copied files before opening any SQLite connection.
    initial = verify_pair(source_root,rows)
    write_receipt(args.output/'COPIED_SOURCE_VERIFIED.json',dict(census_sha256=args.census_sha256,
        files=initial,scope='database and journal copied extents only',whole_backup_certified=False))
    copy_pair(source_root,args.output/'unrecovered-copy',rows)
    copy_pair(args.output/'unrecovered-copy',args.output/'independent-restore',rows)
    write_receipt(args.output/'COPY_READBACK.json',dict(files=verify_pair(args.output/'independent-restore',rows),
        unchanged_original_copied_files=True,independent_restore=True,before_sqlite_open=True))
    report = recover_copy_or_original(args.output/'independent-restore',
        metadata_root=source_root,census=census)
    if verify_pair(source_root,rows)!=initial or digest(args.census)!=args.census_sha256:
        raise ValueError('Original PC copied database/journal/census changed')
    for pin in code_pins:
        if digest(pin['path'])!=pin['sha256']:
            raise ValueError('Recovery source changed during copied-files action')
    if time.monotonic()-started>120:
        raise TimeoutError('Copied-files recovery host scope expired')
except BaseException as error:
    failure = dict(type=type(error).__name__,message=str(error)[:512])
finally:
    unchanged = initial is not None and verify_pair(source_root,rows)==initial
    summary = dict(schema='just-peachy.core-database-copy-recovery.v1',owner=owner,
        status='PASS' if failure is None and report is not None else 'FAILED',
        failure=failure,recovery=report,source_copied_files_unchanged=unchanged,
        whole_backup_certified=False,native_action=False,recording_deletion=False,
        elapsed_seconds=time.monotonic()-started)
    if (args.output/'independent-restore').exists():
        summary['restore_sidecars_after_close'] = sidecars(args.output/'independent-restore')
    write_receipt(args.output/'RESULT.json',summary)
    write_receipt(args.output/'HOST_EXIT.json',dict(owner=owner,status=summary['status'],
        process_returns_after_receipt=True,finished_unix=time.time()))
    print(json.dumps(dict(status=summary['status'],owner=owner,failure=failure,
        quick_check=report.get('quick_check') if report else None,
        source_copied_files_unchanged=unchanged,whole_backup_certified=False,
        output=str(args.output)),sort_keys=True),flush=True)
raise SystemExit(0 if summary['status']=='PASS' else 1)
