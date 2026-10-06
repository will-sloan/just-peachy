"""Freeze only selected build26 helper sources; README_BUILD26_SUPPORT_FREEZE.md."""
import ctypes
_k=ctypes.WinDLL('kernel32',use_last_error=True)
_k.GetCurrentProcess.restype=ctypes.c_void_p
_h=_k.GetCurrentProcess()
_k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
if not _k.SetProcessAffinityMask(_h,16384):raise ctypes.WinError(ctypes.get_last_error())
import ast,hashlib,json,os,shutil,time,uuid
from pathlib import Path
HERE=Path(__file__).parent
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PIN='f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0'
OLD_PIN='6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
PAIRS=(('prepare_stabilization_live_check_v2.py','prepare_stabilization_live_check_v3.py','README_LIVE_CHECK_PAYLOAD_V3.md'),
    ('extract_stabilization_job_v5.py','extract_stabilization_job_v6.py','README_EXTRACT_STABILIZATION_JOB_V6.md'),
    ('prepare_stabilization_stage25.py','prepare_stabilization_stage26.py','README_STAGE26_PREPARATION.md'),
    ('activate_full_desktop_action_v3.py','activate_full_desktop_action_v4.py','README_STABILIZATION_ACTIVATION_V4.md'),
    ('prepare_stabilization_finalize_v5.py','prepare_stabilization_finalize_v6.py','README_FINALIZE_PAYLOAD_V6.md'))

def main():
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    _k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not _k.GetProcessTimes(_h,*(ctypes.byref(s) for s in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    out=Q/'audit-preparation'/('build26-support-freeze-'+uuid.uuid4().hex);out.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    with (out/'REGISTERED_OWNER.json').open('x',encoding='utf-8') as stream:
        json.dump(owner,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
    started=time.monotonic();written=(out/'REGISTERED_OWNER.json').stat().st_size
    def put(name,raw):
        nonlocal written
        if written+len(raw)>2*1024**2 or time.monotonic()-started>600:raise OSError('Finite2MiB/600s freeze')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+2*1024**2:raise OSError('Original host free floor')
        with (out/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short source-freeze write')
            stream.flush();os.fsync(stream.fileno())
        written+=len(raw)
        if (out/name).read_bytes()!=raw:raise OSError('Independent source readback differs')
    def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    def methods(raw):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(raw).body
            if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    inputs={name:HERE/name for row in PAIRS for name in row}
    inputs.update({Path(__file__).name:Path(__file__),
        'README_BUILD26_SUPPORT_FREEZE.md':HERE/'README_BUILD26_SUPPORT_FREEZE.md',
        'native_stabilization_check_v5.py':HERE/'native_stabilization_check_v5.py'})
    put('HOST_SCOPE.json',encoded(dict(maximum_bytes=2*1024**2,maximum_seconds=600,native_action=False)))
    hashes={};sources={}
    for name,path in inputs.items():
        before=path.stat();raw=path.read_bytes();after=path.stat()
        if path.is_symlink() or len(raw)>131072 or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Bounded stable source required')
        raw.decode('utf-8');sources[name]=raw;hashes[name]=hashlib.sha256(raw).hexdigest()
        for suffix in ('','.backup','.restore'):put(name+suffix,raw)
    if hashes['native_stabilization_check_v5.py']!='0690f255b0fc8fef4ee76b6c32aefc2297de9751d18508ac0a29a7e89a5e1dce':raise ValueError('Unchanged V5 helper required')
    reviews={}
    for old,new,guide in PAIRS:
        raw=sources[new];compile(raw,new,'exec')
        if new=='prepare_stabilization_live_check_v3.py':
            a=methods(sources[old]);b=methods(raw)
            if set(a)!=set(b) or any(a[k]!=b[k] for k in a if k!='main'):raise ValueError('Live pure guards/allocation methods changed')
            if PIN.encode() not in raw or b'field-runtime-v29-build-26' not in raw or b'(?:29|30|31)' not in raw:raise ValueError('Exact build26 remaining map required')
            reviews[new]=dict(original_non_main_ast_exact=True,main_changes='newmanifest,target,README,three remaininglabels')
        else:
            old_guide={'extract_stabilization_job_v6.py':'README_EXTRACT_STABILIZATION_JOB_V5.md',
                'prepare_stabilization_stage26.py':'README_STAGE25_PREPARATION.md',
                'activate_full_desktop_action_v4.py':'README_STABILIZATION_ACTIVATION_V3.md',
                'prepare_stabilization_finalize_v6.py':'README_FINALIZE_PAYLOAD_V5.md'}[new]
            expected=sources[old].decode().replace('field-runtime-v29-build-25','field-runtime-v29-build-26').replace(OLD_PIN,PIN).replace(old_guide,guide)
            if new=='prepare_stabilization_stage26.py':expected=expected.replace('stage25-preparation-','stage26-preparation-').replace('stabilization-stage25-01','stabilization-stage26-01').replace('build25','build26').replace('stage25','stage26')
            if new=='prepare_stabilization_finalize_v6.py':expected=expected.replace('stabilization-package-41186a7a33004f1f8656e7be91e54e12/package','stabilization-package-b3df11de85bf41d7a6e8afd5092e3268/package')
            if raw!=expected.encode():raise ValueError('Derivative differs outside exact identity substitutions: '+new)
            reviews[new]=dict(exact_whole_source_identity_substitutions_only=True)
    if any(path.read_bytes()!=sources[name] for name,path in inputs.items()):raise ValueError('Source changed after independent backup')
    result=dict(output=str(out),source_hashes=hashes,reviews=reviews,independent_restores=True,
        native_action=False,payload_created=False,closed_unix=time.time(),prepared_bytes=written)
    put('RESULT.json',encoded(result));put('SOURCE_CLOSED.json',encoded(result));print(json.dumps(result))

if __name__=='__main__':main()
