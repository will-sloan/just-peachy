"""Read-only current storage inspection dispatch; README_CORE_INSPECTION.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'stabilization_20261005/host_stabilization_operations_v5.py'
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
root=PRIVATE/'audit-preparation'/('core-inspection-source-'+uuid.uuid4().hex)
root.mkdir()
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
stamps=[ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(kernel.GetCurrentProcess(),*(ctypes.byref(v) for v in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())
owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
    affinity_mask=16384,creation_filetime=stamps[0].value,
    create_time=(stamps[0].value-116444736000000000)/10000000)
began=time.monotonic();written=0
def put(name,raw):
    global written
    if written+len(raw)>16*1024**2 or time.monotonic()-began>600:
        raise OSError('Finite inspection source scope')
    with (root/name).open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short preparation write')
        stream.flush();os.fsync(stream.fileno())
    if (root/name).read_bytes()!=raw:raise OSError('Independent preparation readback')
    written+=len(raw)
def encode(value):return json.dumps(value,sort_keys=True,allow_nan=False).encode()
put('REGISTERED_OWNER.json',encode(owner))
put('HOST_SCOPE.json',encode(dict(maximum_bytes=16*1024**2,maximum_seconds=600,
    issued_unix=time.time(),native_writes=False,purpose='Actual Discard failure diagnosis')))
raw=SOURCE.read_bytes()
marker="if sys.argv[1:]==['--host-review']:"
if raw.decode().count(marker)!=1:raise ValueError('Exact V5 dispatch entry boundary')
for label,path in (('HOST_WRAPPER.py',Path(__file__)),('README.md',HERE/'README_CORE_INSPECTION.md'),
                   ('PARENT.py',SOURCE),('ACTION.py',HERE/'inspect_core_storage.py')):
    content=path.read_bytes()
    for suffix in ('.backup','.restore'):put(label+suffix,content)
put('SOURCE_CLOSED.json',encode(dict(closed_unix=time.time(),independent_restores=True,
    wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    action_sha256=hashlib.sha256((HERE/'inspect_core_storage.py').read_bytes()).hexdigest())))
space=dict(__name__='core_inspection_dispatch',__file__=str(SOURCE))
exec(compile(raw.decode().split(marker)[0],str(SOURCE),'exec'),space)
driver=space['driver']
main=space['_main_source']
before="assert not value['current_project_processes'], 'Preserve other running applications'\nassert not value['active_recorded_owners'] and not value['live_manager_owners']"
if '--writes' in sys.argv or '--action' not in sys.argv:
    raise ValueError('Read-only exact storage action required')
action_path=Path(sys.argv[sys.argv.index('--action')+1]).resolve(strict=True)
if action_path!=(HERE/'inspect_core_storage.py').resolve(strict=True):
    raise ValueError('Only the reviewed nonmutating storage inspector is allowed')
action_sha=hashlib.sha256(action_path.read_bytes()).hexdigest()
after=("assert not OPERATION_WRITES, 'Storage inspection is read-only'\n"
       "assert ACTION_PAYLOAD.get('schema')=='just-peachy.core-storage-inspection.v1'\n"
       "assert hashlib.sha256(ACTION_SOURCE.encode()).hexdigest()=="+repr(action_sha))
if main.count(before)!=1:raise ValueError('Exact read-only action guard boundary')
main=main.replace(before,after)
# All original owner reads, native census, current resource guards and closure
# remain. Only this nonmutating action may observe a user's existing application.
exec(compile(main,'<current-storage-inspection-main>','exec'),driver.__dict__)
driver.main()
