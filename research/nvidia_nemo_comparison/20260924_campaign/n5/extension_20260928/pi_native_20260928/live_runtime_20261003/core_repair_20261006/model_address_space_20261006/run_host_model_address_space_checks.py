"""Registered CPU14 standard-library AS/source checks; README_MODEL_ADDRESS_SPACE.md."""
import ctypes
import os

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
handle = kernel.GetCurrentProcess()
if not kernel.SetProcessAffinityMask(handle, 16384):
    raise ctypes.WinError(ctypes.get_last_error())
stamps = [ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())

import argparse
import json
from pathlib import Path
import time

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True, help='Fresh private audit-preparation/model-as-host-UUID directory')
args = parser.parse_args()
if args.output.exists() or args.output.parent.resolve(strict=True) != PRIVATE/'audit-preparation' or not args.output.name.startswith('model-as-host-'):
    raise ValueError('One fresh private registered host output required')
args.output.mkdir()
started = time.monotonic()
MAXIMUM_SECONDS = 600
MAXIMUM_PREPARED_BYTES = 128*1024**2
written = 0


def put(name, value):
    global written
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, allow_nan=False).encode()
    if len(raw) > 2*1024**2 or written+len(raw) > MAXIMUM_PREPARED_BYTES or time.monotonic()-started > MAXIMUM_SECONDS:
        raise ValueError('Finite host source evidence allocation exceeded')
    path = args.output/name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short host source write')
        stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise OSError('Independent host source readback differs')
    written += len(raw)


owner = dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
             affinity_mask=16384, creation_filetime=stamps[0].value,
             create_time=(stamps[0].value-116444736000000000)/10000000)
put('REGISTERED_OWNER.json', owner)
put('HOST_SCOPE.json', dict(owner=owner, maximum_seconds=MAXIMUM_SECONDS,
    maximum_prepared_bytes=MAXIMUM_PREPARED_BYTES, models=False, native_action=False,
    source_ast_only=True, registered_before_project_reads=True))

import hashlib
import importlib.util
import io
import shutil
import stat
import sys
import traceback
import unittest

HERE = Path(__file__).resolve().parent
PACKAGE = PRIVATE/'audit-preparation/gallery-package32-d1140c29f0d843c881bd719309bb5d6d/package'
PIN = '55f449d563b3011a0793cef174921a215cd9aeb0dbbaa597b228ae4ba889fbbf'
sys.dont_write_bytecode = True
os.environ['JP_AS_TEST_BASE'] = str(PACKAGE)
os.environ['JP_AS_REGISTERED_OWNER'] = str(args.output/'REGISTERED_OWNER.json')
pins, result, failure = [], None, None
source_verified = False


class BoundedLog(io.StringIO):
    def write(self, value):
        if self.tell()+len(value) > 65536:
            raise ValueError('Finite source fixture diagnostic bound')
        return super().write(value)


log = BoundedLog()
try:
    for drive, floor in (('C:/', 50*1024**3), ('G:/', 75*1024**3)):
        if shutil.disk_usage(drive).free-MAXIMUM_PREPARED_BYTES < floor:
            raise OSError('Actual host physical free-space floor required')
    manifest_raw = (PACKAGE/'PACKAGE_MANIFEST.json').read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != PIN:
        raise ValueError('Exact immutable package32 required')
    manifest = json.loads(manifest_raw)
    members = {row['path']: row for row in manifest['files']}
    if len(members) != len(manifest['files']) or len(members) != 432:
        raise ValueError('Exact sealed package32 member count required')
    sources = [(PACKAGE/'PACKAGE_MANIFEST.json', 'package/PACKAGE_MANIFEST.json', PIN)]
    for name, row in sorted(members.items()):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or not 0 <= row['bytes'] <= 2*1024**2:
            raise ValueError('Unsafe sealed source member')
        sources.append((PACKAGE/relative, 'package/'+name, row['sha256']))
    for name in ('worker.py', 'native_scope.py', 'launch_raw_qualification_action.py',
                 'README_MODEL_ADDRESS_SPACE.md', 'test_model_address_space.py', 'run_host_model_address_space_checks.py'):
        sources.append((HERE/name, 'draft/'+name, None))
    for name in ('worker.py', 'native_scope.py', 'launch_raw_qualification_action.py'):
        for suffix in ('backup', 'restore'):
            sources.append((HERE/'preserved32'/(name+'.'+suffix), 'preserved32/'+name+'.'+suffix, members[name]['sha256']))
    for source, token, expected in sources:
        info = source.lstat()
        if source.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 2*1024**2:
            raise ValueError('Ordinary bounded host source required')
        raw = source.read_bytes(); observed = hashlib.sha256(raw).hexdigest()
        if expected is not None and observed != expected:
            raise ValueError('Admitted source pin differs: '+token)
        put('source-backup/'+token, raw)
        put('source-restore/'+token, raw)
        pins.append(dict(path=str(source), bytes=len(raw), sha256=observed, backup='source-backup/'+token,
                         restore='source-restore/'+token, independent_restore_equal=True))
    put('SOURCE_CLOSED.json', dict(owner=owner, before_tests=True, package_manifest_sha256=PIN,
        source_pins=pins, source_count=len(pins), independent_backups_and_restores=True,
        prepared_bytes=written, native_action=False, models=False))
    for name in ('worker.py', 'native_scope.py', 'launch_raw_qualification_action.py'):
        compile((HERE/name).read_bytes(), str(HERE/name), 'exec')
    spec = importlib.util.spec_from_file_location('_registered_as_source_cases', HERE/'test_model_address_space.py')
    checks = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = checks
    spec.loader.exec_module(checks)
    suite = unittest.defaultTestLoader.loadTestsFromModule(checks)
    if suite.countTestCases() != 10:
        raise ValueError('Exactly ten admitted AS source cases required')
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    for row in pins:
        source = Path(row['path'])
        if source.stat().st_size != row['bytes'] or hashlib.sha256(source.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Source changed during source/AST checks')
        for kind in ('backup', 'restore'):
            saved = args.output/row[kind]
            if saved.stat().st_size != row['bytes'] or hashlib.sha256(saved.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('Independent source preservation changed')
    source_verified = True
    put('SOURCE_UNCHANGED.json', dict(owner=owner, after_tests=True, source_count=len(pins),
        source_pins=pins, source_unchanged=True, independent_backup_restore_readback_exact=True))
except BaseException as error:
    failure = dict(type=type(error).__name__, message=str(error)[:1024], traceback=traceback.format_exc()[-8192:])
finally:
    put('TEST_OUTPUT.txt', log.getvalue().encode())
    summary = dict(schema='just-peachy.model-address-space-host.v1', owner=owner,
        status='PASS' if failure is None and result is not None and result.wasSuccessful() and not result.skipped else 'FAILED',
        tests_run=result.testsRun if result else 0, skipped=len(result.skipped) if result else 0,
        failures=len(result.failures) if result else 0, errors=len(result.errors) if result else 0,
        failure=failure, elapsed_seconds=time.monotonic()-started, source_unchanged=source_verified,
        fixture_closed=True, source_ast_only=True, models=False, native_action=False,
        package_manifest_sha256=PIN, source_count=len(pins))
    put('RESULT.json', summary)
    put('HOST_EXIT.json', dict(owner=owner, finished_unix=time.time(), status=summary['status'],
        process_returns_after_receipt=True, fixture_closed=True))
    print(json.dumps(summary, sort_keys=True), flush=True)
raise SystemExit(0 if summary['status'] == 'PASS' else 1)
