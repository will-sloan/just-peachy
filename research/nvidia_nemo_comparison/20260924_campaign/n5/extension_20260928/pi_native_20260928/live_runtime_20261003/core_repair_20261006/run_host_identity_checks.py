"""Registered CPU14 focused identity/capacity checks. See README_IDENTITY_MODES.md.

One process; no SSH, models, GUI, production recordings, or native ownership.
"""
import ctypes
import os

kernel = ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p,ctypes.c_size_t]
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
handle = kernel.GetCurrentProcess()
if not kernel.SetProcessAffinityMask(handle,1<<14):
    raise ctypes.WinError(ctypes.get_last_error())
stamps = [ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())

import argparse
import json
from pathlib import Path
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True,help='Fresh nonexistent private host output directory')
parser.add_argument('--suite',choices=('contracts','pinned','caption'),required=True)
args = parser.parse_args()
args.output.mkdir()
started = time.monotonic()
issued_unix = time.time()
written = 0
MAXIMUM = 128*1024**2
MAXIMUM_SECONDS = 120

def put(name,value):
    global written
    raw = value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,allow_nan=False).encode()
    if len(raw)>262144 or written+len(raw)>MAXIMUM or time.monotonic()-started>MAXIMUM_SECONDS:
        raise ValueError('Bounded storage contract receipt allowance exceeded')
    with (args.output/name).open('xb') as stream:
        if stream.write(raw)!=len(raw):
            raise OSError('Short contract receipt write')
        stream.flush()
        os.fsync(stream.fileno())
    written += len(raw)
    if (args.output/name).read_bytes()!=raw:
        raise OSError('Independent contract receipt readback differs')

owner = dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),
             create_time=(stamps[0].value-116444736000000000)/10000000,
             creation_filetime=stamps[0].value,cpu=14,affinity_mask=16384)
put('REGISTERED_OWNER.json',owner)
put('HOST_SCOPE.json',dict(issued_unix=issued_unix,maximum_seconds=MAXIMUM_SECONDS,
                         maximum_bytes=MAXIMUM,native_action=False,models=False,
                         fixture_only=True,suite=args.suite,owner_registered_before_project_import=True))
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'

import hashlib
import importlib.util
import io
import shutil
import sys
import tempfile
import traceback
import unittest

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0,str(HERE))
sys.path.insert(1,str(HERE.parent))
pins = []
result = None
failure = None
fixture_root = args.output/'fixtures'
fixture_root.mkdir()
tempfile.tempdir = str(fixture_root)

class BoundedLog(io.StringIO):
    def write(self,value):
        if self.tell()+len(value)>65536:
            raise ValueError('Contract log exceeded 64 KiB')
        return super().write(value)

log = BoundedLog()
try:
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free-MAXIMUM<floor:
            raise OSError('Actual host free-space floor required')
    paths = [HERE/name for name in (
        'installed_engine.py','application_controller.py','personal_gallery.py',
        'runtime_support.py','identity_modes.py','d1_spatial_policy.py','gallery_snapshot_io.py',
        'test_identity_modes.py','test_identity_pinned.py','test_installed_caption_projection.py',
        'test_runtime_capacity.py','test_gallery_capacity.py','run_host_identity_checks.py',
        'README_IDENTITY_MODES.md','README_RUNTIME_CAPACITY.md','README_GALLERY_CAPACITY.md')]
    for index,path in enumerate(paths):
        info = path.lstat()
        if path.is_symlink() or getattr(info,'st_file_attributes',0)&0x400 or info.st_nlink!=1:
            raise ValueError('Regular single-link source input required')
        raw = path.read_bytes()
        if len(raw)>262144:
            raise ValueError('Bounded source input required')
        put('SOURCE_%02d.backup'%index,raw)
        restored = (args.output/('SOURCE_%02d.backup'%index)).read_bytes()
        put('SOURCE_%02d.restore'%index,restored)
        if restored!=raw or path.read_bytes()!=raw:
            raise OSError('Independent source restore differs')
        pins.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    put('SOURCE_CLOSED.json',dict(pins=pins,closed_unix=time.time(),
                               backup_and_independent_restore=True,before_check=True))
    modules = ('test_identity_pinned',) if args.suite=='pinned' else ('test_installed_caption_projection',) if args.suite=='caption' else (
        'test_identity_modes','test_installed_caption_projection','test_runtime_capacity','test_gallery_capacity')
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    if any(fixture_root.iterdir()):
        raise OSError('Synthetic fixture closure incomplete')
    if time.monotonic()-started>MAXIMUM_SECONDS:
        raise OSError('Contract time allowance exceeded')
    for pin in pins:
        if hashlib.sha256(Path(pin['path']).read_bytes()).hexdigest()!=pin['sha256']:
            raise OSError('Source changed during isolated check: '+pin['path'])
except BaseException as error:
    failure = dict(type=type(error).__name__,message=str(error)[:1024],traceback=traceback.format_exc()[-8192:])
finally:
    put('TEST_OUTPUT.txt',log.getvalue().encode())
    summary = dict(schema='just-peachy.identity-host-contract.v1',
        status='PASS' if failure is None and result is not None and result.wasSuccessful() else 'FAILED',
        owner=owner,suite=args.suite,skipped=len(result.skipped) if result else 0,tests_run=result.testsRun if result else 0,
        failures=len(result.failures) if result else 0,errors=len(result.errors) if result else 0,
        elapsed_seconds=time.monotonic()-started,fixture_closed=not any(fixture_root.iterdir()),
        source_unchanged=failure is None,failure=failure,native_action=False)
    put('RESULT.json',summary)
    put('HOST_EXIT.json',dict(owner=owner,finished_unix=time.time(),status=summary['status'],
                            process_returns_after_receipt=True,fixture_closed=summary['fixture_closed']))
    print(json.dumps(summary,sort_keys=True),flush=True)
raise SystemExit(0 if summary['status']=='PASS' else 1)
