"""Registered CPU14 combined pure capacity checks; README_GALLERY_CAPACITY_STORE.md.

One host process, synthetic fixtures only. No models/native/SSH/publication.
"""
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

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True, help='Fresh nonexistent private host output directory')
args = parser.parse_args()
args.output.mkdir()
started = time.monotonic()
MAXIMUM_SECONDS = 600
MAXIMUM_PREPARED_BYTES = 128*1024**2
written = 0


def put(name, value):
    global written
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, allow_nan=False).encode()
    if len(raw) > 2*1024**2 or written+len(raw) > MAXIMUM_PREPARED_BYTES or time.monotonic()-started > MAXIMUM_SECONDS:
        raise ValueError('Finite host evidence allocation exceeded')
    with (args.output/name).open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short host receipt write')
        stream.flush()
        os.fsync(stream.fileno())
    if (args.output/name).read_bytes() != raw:
        raise OSError('Independent host receipt readback differs')
    written += len(raw)


owner = dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
    affinity_mask=16384, creation_filetime=stamps[0].value,
    create_time=(stamps[0].value-116444736000000000)/10000000)
put('REGISTERED_OWNER.json', owner)
put('HOST_SCOPE.json', dict(issued_unix=time.time(), maximum_seconds=MAXIMUM_SECONDS,
    maximum_prepared_bytes=MAXIMUM_PREPARED_BYTES, native_action=False, models=False,
    fixture_only=True, synthetic_zip_fixtures=True, owner_registered_before_project_import=True))
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
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
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PACKAGE = LOCAL/'audit-preparation/caption-package31-f6383c985d4d41e6b065ff9487dd19ad/package'
PACKAGE_PIN = '4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
INSTALLED = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12')
INSTALLED_PIN = '274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'
sys.dont_write_bytecode = True
fixture_root = args.output/'fixtures'
fixture_root.mkdir()
tempfile.tempdir = str(fixture_root)
os.environ['JP_BENCH_TEST_ROOT'] = str(fixture_root)
os.environ['JP_CAPACITY_INSTALLED'] = str(INSTALLED)
pins, result, failure = [], None, None
source_verified = False


class BoundedLog(io.StringIO):
    def write(self, value):
        if self.tell()+len(value) > 65536:
            raise ValueError('Host fixture log exceeds 64 KiB')
        return super().write(value)


log = BoundedLog()
try:
    for drive, floor in (('C:/', 50*1024**3), ('G:/', 75*1024**3)):
        if shutil.disk_usage(drive).free-MAXIMUM_PREPARED_BYTES < floor:
            raise OSError('Actual host free-space floor required')
    package_raw = (PACKAGE/'PACKAGE_MANIFEST.json').read_bytes()
    installed_raw = (INSTALLED/'RELEASE_MANIFEST.json').read_bytes()
    if hashlib.sha256(package_raw).hexdigest() != PACKAGE_PIN or hashlib.sha256(installed_raw).hexdigest() != INSTALLED_PIN:
        raise ValueError('Exact frozen31/installed manifests required')
    package = {row['path']: row for row in json.loads(package_raw)['files']}
    installed = {row['path']: row for row in json.loads(installed_raw)['files']}
    candidates = [HERE/name for name in (
        'personal_gallery.py', 'application_contract.py', 'capacity_personal_store.py',
        'installed_engine.py', 'gallery_capacity_admission.py', 'gallery_worker.py',
        'README_GALLERY_CAPACITY_STORE.md', 'README_GALLERY_WORKER_CAPACITY.md',
        'test_capacity_personal_store.py', 'test_gallery_worker_capacity.py', 'run_host_gallery_capacity.py')]
    frozen = [PACKAGE/'PACKAGE_MANIFEST.json']+[PACKAGE/name for name in (
        'runtime_support.py', 'personal_gallery.py', 'application_contract.py', 'installed_engine.py')]
    # Back up the entire pure installed application/pipeline code inventory
    # before imports, including any lazy pure validator dependencies. No model,
    # personal metadata, audio or native library bytes are read or copied.
    installed_sources = [INSTALLED/'RELEASE_MANIFEST.json']+[INSTALLED/name for name in sorted(installed)
        if name.endswith('.py') and name.startswith(('app/', 'vendor/edge_speech_pipeline/', 'release_tools/'))]
    for index, path in enumerate(candidates+frozen+installed_sources):
        info = path.lstat()
        if (path.is_symlink() or getattr(info, 'st_file_attributes', 0)&0x400 or info.st_nlink != 1
                or any(parent.is_symlink() or getattr(parent.lstat(), 'st_file_attributes', 0)&0x400 for parent in path.parents)):
            raise ValueError('Single-link ordinary source input required')
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        table = package if path.is_relative_to(PACKAGE) else installed if path.is_relative_to(INSTALLED) else None
        root = PACKAGE if table is package else INSTALLED
        if table is not None and path.name not in ('PACKAGE_MANIFEST.json', 'RELEASE_MANIFEST.json'):
            row = table[path.relative_to(root).as_posix()]
            if actual != row['sha256'] or len(raw) != row['bytes']:
                raise ValueError('Pinned input source differs')
        put('SOURCE_%03d.backup'%index, raw)
        restored = (args.output/('SOURCE_%03d.backup'%index)).read_bytes()
        put('SOURCE_%03d.restore'%index, restored)
        if restored != raw or path.read_bytes() != raw:
            raise OSError('Independent source restore/readback differs')
        pins.append(dict(path=str(path), bytes=len(raw), sha256=actual))
    put('SOURCE_CLOSED.json', dict(pins=pins, closed_unix=time.time(),
        backup_and_independent_restore=True, before_check=True, package_manifest_sha256=PACKAGE_PIN,
        installed_manifest_sha256=INSTALLED_PIN))
    spec = importlib.util.spec_from_file_location('runtime_support', PACKAGE/'runtime_support.py')
    support = importlib.util.module_from_spec(spec)
    sys.modules['runtime_support'] = support
    spec.loader.exec_module(support)
    sys.path.insert(0, str(HERE))
    suite = unittest.defaultTestLoader.loadTestsFromNames(('test_capacity_personal_store', 'test_gallery_worker_capacity'))
    if suite.countTestCases() != 20:
        raise ValueError('Exactly the reviewed 20 focused cases required')
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    if any(fixture_root.iterdir()):
        raise OSError('Synthetic fixture closure incomplete')
    if time.monotonic()-started > MAXIMUM_SECONDS:
        raise OSError('Host fixture runtime exceeded finite scope')
    # Imported installed pure modules and isolated pinned AST regions must all
    # retain their inventoried origin/hash. Models must never be imported.
    for name, module in tuple(sys.modules.items()):
        if name in ('app.pipeline', 'edge_speech_pipeline.models', 'sherpa_onnx', 'onnxruntime', 'torch'):
            raise ValueError('Model graph import is outside pure fixture scope')
        source = getattr(module, '__file__', None)
        if source and Path(source).resolve().is_relative_to(INSTALLED):
            relative = Path(source).resolve().relative_to(INSTALLED).as_posix()
            if relative not in installed or support.digest(source) != installed[relative]['sha256']:
                raise ValueError('Imported installed pure source differs')
    for pin in pins:
        if support.digest(pin['path']) != pin['sha256']:
            raise OSError('Fixture source changed during check')
    source_verified = True
    put('SOURCE_UNCHANGED.json', dict(pins=pins, closed_unix=time.time(), source_unchanged=True,
        fixture_closed=True, scope_closed=True, native_action=False))
except BaseException as error:
    failure = dict(type=type(error).__name__, message=str(error)[:1024], traceback=traceback.format_exc()[-8192:])
finally:
    put('TEST_OUTPUT.txt', log.getvalue().encode())
    summary = dict(schema='just-peachy.gallery-capacity-host.v1',
        status='PASS' if failure is None and result is not None and result.wasSuccessful() and not result.skipped else 'FAILED',
        owner=owner, tests_run=result.testsRun if result else 0, skipped=len(result.skipped) if result else 0,
        failures=len(result.failures) if result else 0, errors=len(result.errors) if result else 0,
        failure=failure, elapsed_seconds=time.monotonic()-started,
        fixture_closed=not any(fixture_root.iterdir()), source_unchanged=source_verified,
        native_action=False, models=False, synthetic_vectors_only=True)
    put('RESULT.json', summary)
    put('HOST_EXIT.json', dict(owner=owner, finished_unix=time.time(), status=summary['status'],
        process_returns_after_receipt=True, fixture_closed=summary['fixture_closed']))
    print(json.dumps(summary, sort_keys=True), flush=True)
raise SystemExit(0 if summary['status'] == 'PASS' else 1)
