"""Freeze one read-only recovery inspection. README_CLOSED_RECOVERY_INSPECTION.md."""
import ctypes,hashlib,json,os,shutil,time,uuid
from pathlib import Path


def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    clocks=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in clocks)):
        raise ctypes.WinError(ctypes.get_last_error())
    out=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation')/('closed-recovery-inspect-'+uuid.uuid4().hex)
    out.mkdir();begun=time.monotonic();used=0
    def put(name,raw):
        nonlocal used
        if used+len(raw)>2097152 or time.monotonic()-begun>30:raise ValueError('Finite2MiB/30s freeze')
        with (out/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short freeze write')
            stream.flush();os.fsync(stream.fileno())
        used+=len(raw)
        if (out/name).read_bytes()!=raw:raise OSError('Independent freeze readback differs')
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=clocks[0].value,
        create_time=(clocks[0].value-116444736000000000)/10000000)
    put('REGISTERED_OWNER.json',json.dumps(owner,sort_keys=True).encode())
    for drive,gib in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<gib*1024**3+2097152:raise OSError('Host storage floor')
    put('HOST_SCOPE.json',json.dumps(dict(maximum_output_bytes=2097152,maximum_seconds=30,native_action=False,issued_unix=time.time())).encode())
    here=Path(__file__).resolve().parent;pins={}
    for name in ('prepare_closed_recovery_inspection.py','inspect_closed_recovery.py',
                 'README_CLOSED_RECOVERY_INSPECTION.md','host_closed_recovery_diagnostics.py'):
        source=here/name;before=source.stat();raw=source.read_bytes();after=source.stat()
        if len(raw)>65536 or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('Stable finite preparation source required')
        for suffix in ('','.backup','.restore'):put(name+suffix,raw)
        pins[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    put('SOURCE_CLOSED.json',json.dumps(dict(pins=pins,independent_restores=True,closed_unix=time.time())).encode())
    # Compilation occurs only after all source bytes and independent restores close.
    for name in pins:
        if name.endswith('.py'):compile((out/name).read_bytes(),name,'exec')
    payload=dict(schema='just-peachy.closed-recovery-inspection.v1',
        fault_sha256='01beda380170956338c66b1489689e7c725cb0f74a6014b6793a96eb389f133a',
        maximum_tree_bytes=524288,maximum_file_bytes=262144)
    put('PAYLOAD.json',json.dumps(payload,sort_keys=True).encode())
    print(str(out))


if __name__=='__main__':main()
