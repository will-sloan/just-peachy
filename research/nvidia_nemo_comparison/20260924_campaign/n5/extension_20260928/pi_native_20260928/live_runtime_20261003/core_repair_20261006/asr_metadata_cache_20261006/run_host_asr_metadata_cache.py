"""Registered CPU14 synthetic ASR metadata checks; README_ASR_METADATA_CACHE.md."""
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
parser.add_argument('--output',type=Path,required=True,help='Fresh private asr-metadata-cache-host-UUID output')
args=parser.parse_args()
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PREFIX='asr-metadata-cache-host-'
if (args.output.parent!=LOCAL/'audit-preparation' or not args.output.name.startswith(PREFIX)
        or len(args.output.name)!=len(PREFIX)+32
        or any(char not in '0123456789abcdef' for char in args.output.name[len(PREFIX):])):
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
    with (args.output/name).open('rb') as stream:
        restored=stream.read(len(raw)+1)
    if restored!=raw:raise OSError('Independent host receipt readback differs')
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
import io
import shutil
import stat
import sys
import tempfile
import traceback
import unittest

HERE=Path(__file__).resolve().parent
PACKAGE=LOCAL/'audit-preparation/event-package33-efdac72ba11f4e8e93b519e80dc3898a/package'
PACKAGE_PIN='2889a2bddc9b6cb65c150510e87db978eb5fb24e4ffa22809b1623d45234b61e'
REFERENCE_SHA='c5d474e86b6a38754dac4f86bcec6e244950822a2781e202a7362e05ac57219c'
REFERENCE_NAMES=('asr_segment_runtime.py','asr_segment_contract.py','runtime_support.py',
                 'storage.py','storage_support.py','profiles.py')
sys.dont_write_bytecode=True
fixture_root=args.output/'fixtures';fixture_root.mkdir();tempfile.tempdir=str(fixture_root)
os.environ['JP_ASR_LEDGER_REFERENCE']=str(PACKAGE/'asr_segment_runtime.py')
pins=[];result=None;failure=None;source_verified=False;profitability={}


class BoundedLog(io.StringIO):
    def write(self,value):
        if self.tell()+len(value)>65536:raise ValueError('Host fixture log exceeds 64 KiB')
        return super().write(value)


log=BoundedLog()


def read_source(path):
    """Admit and read at most the retained 2 MiB source-file allowance."""
    info=path.lstat()
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink() or getattr(info,'st_file_attributes',0)&0x400
            or info.st_nlink!=1 or any(parent.is_symlink() or getattr(parent.lstat(),'st_file_attributes',0)&0x400 for parent in path.parents)):
        raise ValueError('Single-link ordinary source input required')
    if info.st_size>2*1024**2:raise ValueError('Source input exceeds finite 2 MiB allowance')
    with path.open('rb') as stream:
        raw=stream.read(2*1024**2+1)
    if len(raw)>2*1024**2:raise ValueError('Source grew beyond finite 2 MiB allowance')
    return raw


try:
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free-MAXIMUM_PREPARED_BYTES<floor:
            raise OSError('Actual host free-space floor required')
    raw=read_source(PACKAGE/'PACKAGE_MANIFEST.json')
    if hashlib.sha256(raw).hexdigest()!=PACKAGE_PIN:raise ValueError('Exact frozen33 manifest required')
    members={row['path']:row for row in json.loads(raw)['files']}
    sources=[HERE/name for name in ('asr_segment_runtime.py','asr_metadata_cache.py','test_asr_metadata_cache.py',
        'run_host_asr_metadata_cache.py','README_ASR_METADATA_CACHE.md')]
    sources+=[PACKAGE/'PACKAGE_MANIFEST.json']+[PACKAGE/name for name in REFERENCE_NAMES]
    sources+=[HERE/'preserved'/name for name in ('asr_segment_runtime.build33.py',
                                               'asr_segment_runtime.build33.py.restore')]
    for index,path in enumerate(sources):
        raw=read_source(path);sha=hashlib.sha256(raw).hexdigest()
        if path.is_relative_to(PACKAGE) and path.name!='PACKAGE_MANIFEST.json':
            member=members[path.name]
            if sha!=member['sha256'] or len(raw)!=member['bytes']:
                raise ValueError('Frozen reference bytes differ')
            if path.name=='asr_segment_runtime.py' and sha!=REFERENCE_SHA:
                raise ValueError('Exact unchanged build33 ledger required')
        elif path.parent==HERE/'preserved' and sha!=REFERENCE_SHA:
            raise ValueError('Independent preserved ledger restore differs')
        put('SOURCE_%03d.backup'%index,raw)
        restored=read_source(args.output/('SOURCE_%03d.backup'%index))
        put('SOURCE_%03d.restore'%index,restored)
        if restored!=raw or read_source(path)!=raw:raise OSError('Independent source restore/readback differs')
        pins.append(dict(path=str(path),bytes=len(raw),sha256=sha))
    put('SOURCE_CLOSED.json',dict(pins=pins,closed_unix=time.time(),backup_and_independent_restore=True,
        before_check=True,package_manifest_sha256=PACKAGE_PIN))
    sys.path.insert(0,str(PACKAGE));sys.path.insert(0,str(HERE))
    suite=unittest.defaultTestLoader.loadTestsFromName('test_asr_metadata_cache')
    if suite.countTestCases()!=17:raise ValueError('Exactly the reviewed 17 focused cases required')
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    profitability=sys.modules['test_asr_metadata_cache'].PROFITABILITY
    if any(fixture_root.iterdir()):raise OSError('Synthetic fixture closure incomplete')
    if time.monotonic()-started>MAXIMUM_SECONDS:raise OSError('Host fixture runtime exceeded finite scope')
    for name in ('asr_segment_runtime','asr_metadata_cache','test_asr_metadata_cache'):
        if Path(sys.modules[name].__file__).resolve()!=HERE/(name+'.py'):
            raise ValueError('Candidate pure import origin differs')
    for name in ('asr_segment_contract','storage','storage_support','profiles','runtime_support'):
        if name in sys.modules and Path(sys.modules[name].__file__).resolve()!=PACKAGE/(name+'.py'):
            raise ValueError('Frozen pure dependency origin differs')
    if any(name in sys.modules for name in ('torch','onnxruntime','sherpa_onnx')):
        raise ValueError('Model import outside pure fixture scope')
    for pin in pins:
        current=read_source(Path(pin['path']))
        if len(current)!=pin['bytes'] or hashlib.sha256(current).hexdigest()!=pin['sha256']:
            raise OSError('Fixture source changed during check')
    source_verified=True
    put('SOURCE_UNCHANGED.json',dict(pins=pins,closed_unix=time.time(),source_unchanged=True,
        fixture_closed=True,scope_closed=True,native_action=False))
except BaseException as error:
    failure=dict(type=type(error).__name__,message=str(error)[:1024],traceback=traceback.format_exc()[-8192:])
finally:
    put('TEST_OUTPUT.txt',log.getvalue().encode())
    summary=dict(schema='just-peachy.asr-metadata-cache-host.v1',
        status='PASS' if failure is None and result is not None and result.wasSuccessful() and not result.skipped else 'FAILED',
        owner=owner,tests_run=result.testsRun if result else 0,skipped=len(result.skipped) if result else 0,
        failures=len(result.failures) if result else 0,errors=len(result.errors) if result else 0,
        failure=failure,elapsed_seconds=time.monotonic()-started,fixture_closed=not any(fixture_root.iterdir()),
        source_unchanged=source_verified,native_action=False,models=False,synthetic_sqlite_only=True,
        cache_query_elimination=profitability)
    put('RESULT.json',summary)
    put('HOST_EXIT.json',dict(owner=owner,finished_unix=time.time(),status=summary['status'],
        process_returns_after_receipt=True,fixture_closed=summary['fixture_closed']))
    print(json.dumps(summary,sort_keys=True),flush=True)
raise SystemExit(0 if summary['status']=='PASS' else 1)
