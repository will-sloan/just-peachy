"""Exact failed normal01 ownership wrapper; README_CORE_OPERATIONS_V15.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ctypes
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import uuid

PARENT_SHA = '46732d020c5727515a04e56a69d06df86feefd40f7e654e890d5bae7a3764573'
ADAPTER_SHA = '80182bbab77d4352c922c889ab61499387f02364fd041acf32200078dd1cd15d'
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
root = PRIVATE/'audit-preparation'/('core-operations-v15-source-'+uuid.uuid4().hex)
root.mkdir(exist_ok=False)
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
stamps = [ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(kernel.GetCurrentProcess(), *(ctypes.byref(v) for v in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())
owner = dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
    affinity_mask=16384, creation_filetime=stamps[0].value,
    create_time=(stamps[0].value-116444736000000000)/10000000)


def put(path, raw):
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw): raise OSError('Short V15 source preservation write')
        stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw: raise OSError('Independent V15 source readback differs')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


put(root/'REGISTERED_OWNER.json', encoded(owner))


def read(path):
    before = path.lstat()
    if (path.resolve(strict=True) != path or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1 or before.st_size > 131072
            or any(parent.is_symlink() for parent in path.parents)):
        raise ValueError('Canonical bounded single-link V15 source required')
    raw = path.read_bytes(); after = path.lstat()
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if len(raw) != before.st_size or identity(before) != identity(after):
        raise ValueError('V15 source changed during read')
    return raw


here = Path(__file__).resolve().parent
parent = here/'host_core_operations_v12.py'
adapter = here/'closed_normal01_02_owner.py'
sources = {}; pins = {}
for path in (Path(__file__).resolve(), here/'README_CORE_OPERATIONS_V15.md', adapter,
             parent, here/'README_CORE_OPERATIONS_V12.md'):
    raw = read(path); digest = hashlib.sha256(raw).hexdigest()
    if path == parent and digest != PARENT_SHA or path == adapter and digest != ADAPTER_SHA:
        raise ValueError('Exact reviewed V12 parent and normal01 adapter required')
    for suffix in ('.backup', '.restore'): put(root/(path.name+suffix), raw)
    if read(path) != raw: raise ValueError('V15 source changed during independent preservation')
    sources[path] = raw; pins[str(path)] = dict(bytes=len(raw), sha256=digest)

text = sources[parent].decode()
boundary = '\nbind_owner_family()\n'
addition = boundary+'install_exact_closed_normal01(globals())\n'
if text.count(boundary) != 1: raise ValueError('One exact V12 pre-main owner seam required')
derived = text.replace(boundary, addition)
if derived.replace(addition, boundary) != text: raise ValueError('Whole V12 source reverse differs')
module = dict(__name__='reviewed_exact_closed_normal01', __file__=str(adapter))
exec(compile(sources[adapter], str(adapter), 'exec'), module)
put(root/'SOURCE_CLOSED.json', encoded(dict(schema='just-peachy.core-v15-source-binding.v1',
    owner=owner, source_pins=pins, independent_backups_and_restores=True,
    source_unchanged=True, parent_reverse_source_exact=True,
    admitted_closed_runs=['production-normal-01', 'production-normal-02'], future_labels_admitted=False,
    native_action_claimed=False, prepared_unix=time.time())))
space = dict(__name__='reviewed_core_v15_v12_parent', __file__=str(parent),
             install_exact_closed_normal01=module['install'])
exec(compile(derived, str(parent), 'exec'), space)
for path, raw in sources.items():
    if read(path) != raw: raise ValueError('V15 source changed during original dispatch')
