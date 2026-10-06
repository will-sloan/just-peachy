"""Prepare the exact changed-source five-second raw admission. See README.md."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

HERE=Path(__file__).resolve().parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PACKAGE=PRIVATE/'audit-preparation/stabilization-package-fd5ba47fbfce4b598ca0c5f42390ceb2/package'
TARGET='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-23'
PIN='16bfa6fcddfac639c83e0c785b4292d98eac478873d5a4c3a2efb3ceb7740492'
BOOT='0561d730-3cad-48e0-940a-fe3930c89665'

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('stabilization-raw09-'+uuid.uuid4().hex)
    root.mkdir()
    (root/'REGISTERED_OWNER.json').write_bytes(encoded(dict(schema='just-peachy.host-registered-owner.v1',
        pid=os.getpid(),creation_filetime=stamps[0].value,cpu=14,affinity_mask=16384)))
    def pin(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    if pin(PACKAGE/'PACKAGE_MANIFEST.json')!=PIN:raise ValueError('Exact staged candidate source required')
    expires=time.time()+590
    template=dict(schema='just-peachy.raw-qualification-template.v1',reviewed=True,duration_seconds=5,
        target=TARGET,binding_sha256=pin(PACKAGE/'BINDING.json'),package_manifest_sha256=PIN,
        boot_id=BOOT,expires_unix=expires,installed_source_sha256=pin(PACKAGE/'installed_source.py'),
        raw_capture_sha256=pin(PACKAGE/'raw_capture.py'),source_batch_sha256=pin(PACKAGE/'source_batch.py'))
    payload=dict(package=TARGET,package_manifest_sha256=PIN,boot_id=BOOT,label='raw-qualification-09',
        expires_unix=expires,maximum_output_bytes=16*1024**2,raw_admission_template=template,
        raw_admission_template_sha256=hashlib.sha256(encoded(template)).hexdigest())
    action=PACKAGE/'launch_raw_qualification_action.py'
    for name,raw in (('PAYLOAD.json',encoded(payload)),('ACTION.py',action.read_bytes()),
                     ('PREPARER.py',Path(__file__).read_bytes()),('README.md',(HERE/'README.md').read_bytes())):
        for suffix in ('','backup','restore'):
            path=root/(name if not suffix else name+'.'+suffix)
            with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            if path.read_bytes()!=raw:raise OSError('Independent preparation readback differs')
    size=sum(path.stat().st_size for path in root.iterdir())
    if size>1024**2:raise ValueError('Raw admission preparation 1MiB ceiling')
    (root/'SOURCE_CLOSED.json').write_bytes(encoded(dict(closed_unix=time.time(),maximum_seconds=600,
        maximum_bytes=1024**2,bytes=size,independent_readback=True,native_action=False,
        action_sha256=pin(action),payload_sha256=pin(root/'PAYLOAD.json'))))
    print(encoded(dict(output=str(root),payload=str(root/'PAYLOAD.json'),action=str(root/'ACTION.py'),
        native_reservation_bytes=16*1024**2,independent_pc_reservation_bytes=16*1024**2)).decode())

if __name__=='__main__':main()
