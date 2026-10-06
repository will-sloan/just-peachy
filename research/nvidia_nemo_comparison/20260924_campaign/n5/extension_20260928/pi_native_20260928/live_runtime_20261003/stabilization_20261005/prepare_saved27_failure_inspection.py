"""Freeze one Saved27 read-only diagnostic payload. README_INSPECT_SAVED27_FAILURE.md."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid

HERE=Path(__file__).resolve().parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PIN='6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
BOOT='0561d730-3cad-48e0-940a-fe3930c89665'
LAUNCH='8d61371110d0470c93f4ff58cc73027d'
JOB_PIN='72957f93d74bd0ec510485c8fa7fdc293bb0ed3bb6fc11c9c7714482f1e0a648'


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p;handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    output=PRIVATE/'audit-preparation'/('saved27-failure-inspection-'+uuid.uuid4().hex);output.mkdir()
    started=time.monotonic();used=0
    def put(name,raw):
        nonlocal used
        if used+len(raw)>2*1024**2 or time.monotonic()-started>30:raise ValueError('Finite2MiB30s preparation')
        for drive,gib in (('C:/',50),('G:/',75)):
            if shutil.disk_usage(drive).free<gib*1024**3+len(raw):raise OSError('Host storage floor')
        with (output/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short preparation write')
            stream.flush();os.fsync(stream.fileno())
        used+=len(raw)
        if (output/name).read_bytes()!=raw:raise OSError('Preparation readback differs')
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    put('REGISTERED_OWNER.json',encoded(owner))
    put('HOST_SCOPE.json',encoded(dict(maximum_output_bytes=2*1024**2,maximum_seconds=30,native_action=False)))
    sources={}
    for name,path in (('PREPARER.py',Path(__file__)),('ACTION.py',HERE/'inspect_saved27_failure.py'),
            ('README.md',HERE/'README_INSPECT_SAVED27_FAILURE.md'),
            ('JOB27.json',PRIVATE/'classic-ui-check-27-JOB.json')):
        before=path.lstat();raw=path.read_bytes();after=path.stat()
        if (path.is_symlink() or before.st_nlink!=1 or before.st_size>65536 or len(raw)!=before.st_size or
                (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns)):
            raise ValueError('Stable bounded preparation input required')
        sources[name]=raw
        for suffix in ('','.backup','.restore'):put(name+suffix,raw)
    put('SOURCE_CLOSED.json',encoded(dict(exact_backup=True,independent_restore=True,
        before_execution=True,closed_unix=time.time(),pins={name:hashlib.sha256(raw).hexdigest() for name,raw in sources.items()})))
    compile(sources['ACTION.py'],'<backed-readonly-saved27-action>','exec')
    compile(sources['PREPARER.py'],'<backed-readonly-saved27-preparer>','exec')
    job=json.loads(sources['JOB27.json'])
    if hashlib.sha256(encoded(job)).hexdigest()!=JOB_PIN or job.get('boot_id')!=BOOT or job.get('package_manifest_sha256')!=PIN:
        raise ValueError('Actual Saved27 JOB binding differs')
    payload=dict(package_manifest_sha256=PIN,boot_id=BOOT,launch_id=LAUNCH,expires_unix=time.time()+590)
    put('PAYLOAD.json',encoded(payload))
    put('RESULT.json',encoded(dict(status='PREPARED_CLOSED_SAVED27_DIAGNOSTIC',output=str(output),
        action_sha256=hashlib.sha256(sources['ACTION.py']).hexdigest(),expires_unix=payload['expires_unix'],native_action=False)))
    put('EXIT_INTENT.json',encoded(dict(owner=owner,physical_closure_claimed=False)))
    print(str(output))


if __name__=='__main__':main()
