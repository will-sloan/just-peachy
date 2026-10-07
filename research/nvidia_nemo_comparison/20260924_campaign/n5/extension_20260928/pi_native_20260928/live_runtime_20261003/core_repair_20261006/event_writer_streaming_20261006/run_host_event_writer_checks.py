"""Registered CPU14 synthetic writer checks; README_EVENT_WRITER_STREAMING.md."""
import ctypes
import os

kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
handle=kernel.GetCurrentProcess()
if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
stamps=[ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())

import argparse
import json
from pathlib import Path
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True,help='Fresh private event-writer-host-UUID output')
args=parser.parse_args()
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
if (args.output.parent!=LOCAL/'audit-preparation' or not args.output.name.startswith('event-writer-host-')
        or len(args.output.name)!=len('event-writer-host-')+32
        or any(char not in '0123456789abcdef' for char in args.output.name[len('event-writer-host-'):])):
    raise ValueError('Exact fresh private host output label required')
args.output.mkdir()
started=time.monotonic();MAXIMUM_SECONDS=600;MAXIMUM_PREPARED_BYTES=16*1024**2;written=0


def put(name,value):
    global written
    raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,allow_nan=False).encode()
    if len(raw)>2*1024**2 or written+len(raw)>MAXIMUM_PREPARED_BYTES or time.monotonic()-started>MAXIMUM_SECONDS:
        raise ValueError('Finite host evidence allocation exceeded')
    with (args.output/name).open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short host receipt write')
        stream.flush();os.fsync(stream.fileno())
    if (args.output/name).read_bytes()!=raw:raise OSError('Independent host receipt readback differs')
    written+=len(raw)


owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,
    creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
put('REGISTERED_OWNER.json',owner)
put('HOST_SCOPE.json',dict(issued_unix=time.time(),maximum_seconds=MAXIMUM_SECONDS,
    maximum_prepared_bytes=MAXIMUM_PREPARED_BYTES,native_action=False,models=False,
    fixture_only=True,owner_registered_before_project_import=True))
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'

import hashlib
import importlib.util
import io
import shutil
import stat
import sys
import tempfile
import traceback
import unittest

HERE=Path(__file__).resolve().parent
PACKAGE=LOCAL/'audit-preparation/caption-package31-f6383c985d4d41e6b065ff9487dd19ad/package'
PACKAGE_PIN='4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
EXPECTED={'event_compaction.py':'4ad7255459b7aadbbee1c1bd498a6f1402e3ba60e83db0386a6a9bf10f28e206',
          'runtime_support.py':'b31cc219a1dded71bc2393190c79a9e93a8bfcaff206c5c69d3c7ee056a24999'}
sys.dont_write_bytecode=True
fixture_root=args.output/'fixtures';fixture_root.mkdir();tempfile.tempdir=str(fixture_root)
os.environ['JP_EVENT_REFERENCE']=str(PACKAGE/'event_compaction.py')
pins=[];result=None;failure=None;source_verified=False;allocation={}


class BoundedLog(io.StringIO):
    def write(self,value):
        if self.tell()+len(value)>65536:raise ValueError('Host fixture log exceeds 64 KiB')
        return super().write(value)


log=BoundedLog()
try:
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free-MAXIMUM_PREPARED_BYTES<floor:
            raise OSError('Actual host free-space floor required')
    raw=(PACKAGE/'PACKAGE_MANIFEST.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PACKAGE_PIN:raise ValueError('Exact frozen31 manifest required')
    members={row['path']:row for row in json.loads(raw)['files']}
    sources=[HERE/name for name in ('event_compaction.py','runtime_support.py','test_event_writer_streaming.py',
        'run_host_event_writer_checks.py','README_EVENT_WRITER_STREAMING.md')]
    sources+=[PACKAGE/'PACKAGE_MANIFEST.json']+[PACKAGE/name for name in EXPECTED]
    for index,path in enumerate(sources):
        info=path.lstat()
        if (not stat.S_ISREG(info.st_mode) or path.is_symlink() or getattr(info,'st_file_attributes',0)&0x400
                or info.st_nlink!=1 or any(parent.is_symlink() or getattr(parent.lstat(),'st_file_attributes',0)&0x400 for parent in path.parents)):
            raise ValueError('Single-link ordinary source input required')
        raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        if path.is_relative_to(PACKAGE) and path.name!='PACKAGE_MANIFEST.json':
            member=members[path.name]
            if sha!=EXPECTED[path.name] or sha!=member['sha256'] or len(raw)!=member['bytes']:
                raise ValueError('Frozen reference bytes differ')
        put('SOURCE_%03d.backup'%index,raw)
        restored=(args.output/('SOURCE_%03d.backup'%index)).read_bytes()
        put('SOURCE_%03d.restore'%index,restored)
        if restored!=raw or path.read_bytes()!=raw:raise OSError('Independent source restore/readback differs')
        pins.append(dict(path=str(path),bytes=len(raw),sha256=sha))
    put('SOURCE_CLOSED.json',dict(pins=pins,closed_unix=time.time(),backup_and_independent_restore=True,
        before_check=True,package_manifest_sha256=PACKAGE_PIN))
    sys.path.insert(0,str(HERE))
    suite=unittest.defaultTestLoader.loadTestsFromName('test_event_writer_streaming')
    if suite.countTestCases()!=14:raise ValueError('Exactly the reviewed 14 focused cases required')
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    allocation=sys.modules['test_event_writer_streaming'].ALLOCATION_RESULT
    if any(fixture_root.iterdir()):raise OSError('Synthetic fixture closure incomplete')
    if time.monotonic()-started>MAXIMUM_SECONDS:raise OSError('Host fixture runtime exceeded finite scope')
    for name in ('event_compaction','runtime_support','test_event_writer_streaming'):
        if Path(sys.modules[name].__file__).resolve()!=HERE/(name+'.py'):
            raise ValueError('Candidate pure import origin differs')
    if any(name in sys.modules for name in ('torch','onnxruntime','sherpa_onnx')):
        raise ValueError('Model import outside pure fixture scope')
    for pin in pins:
        current=Path(pin['path']).read_bytes()
        if len(current)!=pin['bytes'] or hashlib.sha256(current).hexdigest()!=pin['sha256']:
            raise OSError('Fixture source changed during check')
    source_verified=True
    put('SOURCE_UNCHANGED.json',dict(pins=pins,closed_unix=time.time(),source_unchanged=True,
        fixture_closed=True,scope_closed=True,native_action=False))
except BaseException as error:
    failure=dict(type=type(error).__name__,message=str(error)[:1024],traceback=traceback.format_exc()[-8192:])
finally:
    put('TEST_OUTPUT.txt',log.getvalue().encode())
    summary=dict(schema='just-peachy.event-writer-streaming-host.v1',
        status='PASS' if failure is None and result is not None and result.wasSuccessful() and not result.skipped else 'FAILED',
        owner=owner,tests_run=result.testsRun if result else 0,skipped=len(result.skipped) if result else 0,
        failures=len(result.failures) if result else 0,errors=len(result.errors) if result else 0,
        failure=failure,elapsed_seconds=time.monotonic()-started,fixture_closed=not any(fixture_root.iterdir()),
        source_unchanged=source_verified,native_action=False,models=False,synthetic_events_only=True,
        traced_prepare_allocation=allocation)
    put('RESULT.json',summary)
    put('HOST_EXIT.json',dict(owner=owner,finished_unix=time.time(),status=summary['status'],
        process_returns_after_receipt=True,fixture_closed=summary['fixture_closed']))
    print(json.dumps(summary,sort_keys=True),flush=True)
raise SystemExit(0 if summary['status']=='PASS' else 1)
