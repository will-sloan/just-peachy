"""Registered CPU14 S7 copy-equivalence checks; README_S7_PROJECTION_COPY.md."""
import ctypes
import os

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
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
parser.add_argument('--output',type=Path,required=True,help='Fresh private s7-projection-copy-host-UUID output')
args = parser.parse_args()
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PREFIX = 's7-projection-copy-host-'
if (args.output.parent != LOCAL/'audit-preparation' or not args.output.name.startswith(PREFIX)
        or len(args.output.name) != len(PREFIX)+32
        or any(char not in '0123456789abcdef' for char in args.output.name[len(PREFIX):])):
    raise ValueError('Exact fresh private host output label required')
args.output.mkdir()
started = time.monotonic()
MAXIMUM_SECONDS, MAXIMUM_PREPARED_BYTES, written = 300,16*1024**2,0


def put(name,value):
    global written
    raw = value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,allow_nan=False).encode()
    if len(raw)>2*1024**2 or written+len(raw)>MAXIMUM_PREPARED_BYTES or time.monotonic()-started>MAXIMUM_SECONDS:
        raise ValueError('Finite host evidence allowance exceeded')
    with (args.output/name).open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short host receipt write')
        stream.flush()
        os.fsync(stream.fileno())
    with (args.output/name).open('rb') as stream:
        if stream.read(len(raw)+1) != raw:
            raise OSError('Independent host receipt readback differs')
    written += len(raw)


owner = dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,
    creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
put('REGISTERED_OWNER.json',owner)
put('HOST_SCOPE.json',dict(issued_unix=time.time(),maximum_seconds=MAXIMUM_SECONDS,
    maximum_prepared_bytes=MAXIMUM_PREPARED_BYTES,native_action=False,models=False,
    fixture_only=True,owner_registered_before_project_import=True))
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'

import ast
import hashlib
import io
import shutil
import stat
import sys
import tempfile
import traceback
import unittest

HERE = Path(__file__).resolve().parent
INSTALLED = LOCAL.parent/'field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12'
PACKAGE = LOCAL/'audit-preparation/event-package33-efdac72ba11f4e8e93b519e80dc3898a/package'
INSTALLED_PIN = '274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'
PACKAGE_PIN = '2889a2bddc9b6cb65c150510e87db978eb5fb24e4ffa22809b1623d45234b61e'
MERGED_ENGINE = HERE.parent/'disk_capacity_policy_20261006/installed_engine.py'
ENGINE_PIN = 'f6c5ebd4dfa725baa738aa70d36d86bf7937d7030080ce61f25dee5f83fba25a'
PURE_PINS = {
    'vendor/edge_speech_pipeline/research_s7_presentation.py': 'a6229a1cc1f967012de2b79780ab92029e63dc3a64e52bf56b563d7e44f18f10',
    'vendor/edge_speech_pipeline/research_s6d.py': 'ad680e2d3cb30980c07bcd12de2a5a7c20b7ae529889a105fa57ae986fb355a1',
    'vendor/edge_speech_pipeline/research_n1_spans.py': 'a81478569480bb927943a460c17aad0549377e3b7365c4417e3b9f17ecd0d238',
}
sys.dont_write_bytecode = True
sys.path.insert(0,str(HERE))
fixture_root = args.output/'fixtures'
fixture_root.mkdir()
tempfile.tempdir = str(fixture_root)
pins,result,failure,source_verified,observations = [],None,None,False,{}


class BoundedLog(io.StringIO):
    def write(self,value):
        if self.tell()+len(value)>65536:
            raise ValueError('Host fixture log exceeds 64 KiB')
        return super().write(value)


log = BoundedLog()


def read_source(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or path.is_symlink()
            or getattr(info,'st_file_attributes',0)&0x400
            or any(parent.is_symlink() or getattr(parent.lstat(),'st_file_attributes',0)&0x400
                   for parent in path.parents)):
        raise ValueError('Ordinary single-link source input required')
    if info.st_size>2*1024**2:
        raise ValueError('Source input exceeds finite 2 MiB allowance')
    with path.open('rb') as stream:
        raw = stream.read(2*1024**2+1)
    if len(raw)>2*1024**2:
        raise ValueError('Source grew beyond finite 2 MiB allowance')
    return raw


try:
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free-MAXIMUM_PREPARED_BYTES<floor:
            raise OSError('Actual host free-space floor required')
    raw = read_source(INSTALLED/'RELEASE_MANIFEST.json')
    if hashlib.sha256(raw).hexdigest() != INSTALLED_PIN:
        raise ValueError('Exact unchanged installed manifest required')
    installed_members = {row['path']:row for row in json.loads(raw)['files']}
    raw = read_source(PACKAGE/'PACKAGE_MANIFEST.json')
    if hashlib.sha256(raw).hexdigest() != PACKAGE_PIN:
        raise ValueError('Exact frozen33 manifest required')
    package_members = {row['path']:row for row in json.loads(raw)['files']}
    sources = [HERE/name for name in ('s7_projection_copy.py','classic_frontend.py','test_s7_projection_copy.py',
        'run_host_s7_projection_copy.py','README_S7_PROJECTION_COPY.md')]
    sources += [MERGED_ENGINE]
    sources += [INSTALLED/'RELEASE_MANIFEST.json']+[INSTALLED/name for name in PURE_PINS]
    sources += [HERE/'preserved'/name for name in ('research_s7_presentation.installed.py',
        'research_s7_presentation.installed.py.restore','classic_frontend.build33.py',
        'classic_frontend.build33.py.restore')]
    sources += [PACKAGE/'PACKAGE_MANIFEST.json']+[PACKAGE/name for name in (
        'installed_engine.py','classic_frontend.py','runtime_support.py','d1_caption_snapshot.py')]
    for index,path in enumerate(sources):
        raw = read_source(path)
        sha = hashlib.sha256(raw).hexdigest()
        if path == MERGED_ENGINE and sha != ENGINE_PIN:
            raise ValueError('Settled merged Engine integration pin differs')
        if path.is_relative_to(INSTALLED) and path.name != 'RELEASE_MANIFEST.json':
            name = path.relative_to(INSTALLED).as_posix()
            member = installed_members[name]
            if sha != PURE_PINS[name] or sha != member['sha256'] or len(raw) != member['bytes']:
                raise ValueError('Pinned original pure S7 source differs')
        elif path.is_relative_to(PACKAGE) and path.name != 'PACKAGE_MANIFEST.json':
            member = package_members[path.name]
            if sha != member['sha256'] or len(raw) != member['bytes']:
                raise ValueError('Frozen33 integration reference differs')
        elif path.parent == HERE/'preserved':
            expected = (package_members['classic_frontend.py']['sha256'] if path.name.startswith('classic_frontend')
                else PURE_PINS['vendor/edge_speech_pipeline/research_s7_presentation.py'])
            if sha != expected:
                raise ValueError('Preserved independent source restore differs')
        if path.suffix == '.py':
            ast.parse(raw.decode('utf-8'),filename=str(path))
        put('SOURCE_%03d.backup'%index,raw)
        restored = read_source(args.output/('SOURCE_%03d.backup'%index))
        put('SOURCE_%03d.restore'%index,restored)
        if restored != raw or read_source(path) != raw:
            raise OSError('Independent source restore/readback differs')
        pins.append(dict(path=str(path),bytes=len(raw),sha256=sha))
    put('SOURCE_CLOSED.json',dict(pins=pins,closed_unix=time.time(),backup_and_independent_restore=True,
        before_check=True,installed_manifest_sha256=INSTALLED_PIN,package_manifest_sha256=PACKAGE_PIN))
    suite = unittest.defaultTestLoader.loadTestsFromName('test_s7_projection_copy')
    if suite.countTestCases() != 19:
        raise ValueError('Exactly the reviewed 19 focused cases required')
    result = unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    observations = sys.modules['test_s7_projection_copy'].OBSERVATIONS
    if any(fixture_root.iterdir()):
        raise OSError('Synthetic fixture closure incomplete')
    if time.monotonic()-started>MAXIMUM_SECONDS:
        raise OSError('Host fixture runtime exceeded finite scope')
    for name in ('s7_projection_copy','test_s7_projection_copy'):
        if Path(sys.modules[name].__file__).resolve() != HERE/(name+'.py'):
            raise ValueError('Candidate pure import origin differs')
    for name in ('research_s7_presentation','research_s6d'):
        module = sys.modules['_s7_projection_copy_pure_pinned.'+name]
        if Path(module.__file__).resolve() != INSTALLED/'vendor/edge_speech_pipeline'/(name+'.py'):
            raise ValueError('Actual pinned pure S7 class origin differs')
    if any(name in sys.modules for name in ('torch','onnxruntime','sherpa_onnx')):
        raise ValueError('Model import outside pure fixture scope')
    for pin in pins:
        raw = read_source(Path(pin['path']))
        if len(raw) != pin['bytes'] or hashlib.sha256(raw).hexdigest() != pin['sha256']:
            raise OSError('Source changed during check')
    source_verified = True
    put('SOURCE_UNCHANGED.json',dict(pins=pins,closed_unix=time.time(),source_unchanged=True,
        fixture_closed=True,scope_closed=True,native_action=False))
except BaseException as error:
    failure = dict(type=type(error).__name__,message=str(error)[:1024],traceback=traceback.format_exc()[-8192:])
finally:
    put('TEST_OUTPUT.txt',log.getvalue().encode())
    summary = dict(schema='just-peachy.s7-projection-copy-host.v1',
        status='PASS' if failure is None and result is not None and result.wasSuccessful() and not result.skipped else 'FAILED',
        owner=owner,tests_run=result.testsRun if result else 0,skipped=len(result.skipped) if result else 0,
        failures=len(result.failures) if result else 0,errors=len(result.errors) if result else 0,
        failure=failure,elapsed_seconds=time.monotonic()-started,fixture_closed=not any(fixture_root.iterdir()),
        source_unchanged=source_verified,native_action=False,models=False,actual_pinned_pure_classes=True,
        equivalence_observations=observations)
    put('RESULT.json',summary)
    put('HOST_EXIT.json',dict(owner=owner,finished_unix=time.time(),status=summary['status'],
        process_returns_after_receipt=True,fixture_closed=summary['fixture_closed']))
    print(json.dumps(summary,sort_keys=True),flush=True)
raise SystemExit(0 if summary['status']=='PASS' else 1)
