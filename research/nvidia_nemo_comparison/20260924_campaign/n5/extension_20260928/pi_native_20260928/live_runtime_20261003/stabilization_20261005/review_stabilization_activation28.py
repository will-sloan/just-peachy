"""Verify actual activation28 desktop bytes; README_REVIEW_ACTIVATION28.md."""
import ctypes
_k=ctypes.WinDLL('kernel32',use_last_error=True)
_k.GetCurrentProcess.restype=ctypes.c_void_p
_h=_k.GetCurrentProcess()
_k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
if not _k.SetProcessAffinityMask(_h,16384):raise ctypes.WinError(ctypes.get_last_error())
import argparse,base64,hashlib,json,os,re,shutil,stat,time,uuid
from pathlib import Path
HERE=Path(__file__).parent
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PIN='e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b'
BOOT='31ead85c-17cf-49c3-909a-8f2e1108a151'
ACTION_SHA='e336034c83c77e524c6f2762ac6726961c1344a35f36e1a7da448db4ee244f65'
PREVIOUS_SHA='d014baa64a8330bc802a59616c8d3a0874a97402d6ff9cef77d29c6dd8d24fe4'
AUTOSTART_SHA='8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206'
PACKAGE='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-28'

def encode(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path,maximum=262144):
    before=path.lstat()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>maximum:raise ValueError('Bounded ordinary input required')
    raw=path.read_bytes();after=path.stat()
    identity=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns)
    if identity(before)!=identity(after) or len(raw)!=before.st_size:raise ValueError('Input changed during read')
    return raw
def strict(raw):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('Duplicate JSON key')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--result',type=Path,required=True);parser.add_argument('--label',required=True);args=parser.parse_args()
    if re.fullmatch(r'[a-z][a-z0-9-]{0,63}',args.label) is None:raise ValueError('Fresh canonical label required')
    times=[ctypes.c_ulonglong() for _ in range(4)]
    _k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not _k.GetProcessTimes(_h,*(ctypes.byref(v) for v in times)):raise ctypes.WinError(ctypes.get_last_error())
    out=Q/'audit-preparation'/(args.label+'-'+uuid.uuid4().hex);out.mkdir();started=time.monotonic();used=65536
    def put(name,raw):
        nonlocal used
        if used+len(raw)>2*1024**2 or time.monotonic()-started>600:raise OSError('Finite2MiB/600s reconstruction')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+2*1024**2:raise OSError('Original host storage floor')
        with (out/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short reconstruction write')
            stream.flush();os.fsync(stream.fileno())
        used+=len(raw)
        if read(out/name,2*1024**2)!=raw:raise OSError('Independent readback differs')
    def triple(name,raw):
        for suffix in ('','.backup','.restore'):put(name+suffix,raw)
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,creation_filetime=times[0].value,create_time=(times[0].value-116444736000000000)/10000000)
    put('REGISTERED_OWNER.json',encode(owner));put('HOST_SCOPE.json',encode(dict(maximum_bytes=2*1024**2,maximum_seconds=600,directory_reserved_bytes=65536,native_action=False)))
    try:
        for name in ('review_stabilization_activation28.py','README_REVIEW_ACTIVATION28.md'):triple(name,read(HERE/name))
        action=read(HERE/'activate_full_desktop_action_v5.py')
        if sha(action)!=ACTION_SHA:raise ValueError('Frozen native action differs')
        triple('BACKED_ACTION.py',action)
        raw=read(args.result);triple('ACTUAL_ACTIVATION_DISPATCH.json',raw);result=strict(raw);a=result['action_result']
        if (result.get('boot_id')!=BOOT or result.get('utility_pid_absent_after_ssh') is not True
            or a.get('status')!='CLASSIC_SHORTCUT_ACTIVATED' or a.get('package_manifest_sha256')!=PIN
            or a.get('boot_id')!=BOOT or a.get('package')!=PACKAGE or a.get('application_started') is not False
            or a.get('autostart_sha256')!=AUTOSTART_SHA
            or any(a.get(key) is not True for key in ('capture_off','login_autostart_disabled','rollback_package_preserved','recordings_and_galleries_unchanged','independent_before_restore_readbacks'))):raise ValueError('Actual closed current-boot desktop-only activation required')
        utility=result.get('utility_owner')
        if (type(utility) is not dict or set(utility)!={'pid','start_ticks','boot_id'}
            or utility.get('boot_id')!=BOOT or any(type(utility.get(k)) is not int or utility[k]<=0 for k in ('pid','start_ticks'))):raise ValueError('Exact independently closed activation utility identity required')
        rows=a['backups']
        if type(rows) is not list or len(rows)!=1 or rows[0]['path']!='/home/peachyprototype/Desktop/Just Peachy.desktop':raise ValueError('Exactly affected owned desktop entry required')
        old=base64.b64decode(rows[0]['base64'],validate=True);new=base64.b64decode(a['desktop_base64'],validate=True)
        if (len(old)>16384 or len(new)>16384 or sha(old)!=PREVIOUS_SHA or sha(old)!=rows[0]['sha256']
            or sha(new)!=a['desktop_sha256'] or b'field-runtime-v29-build-28/native_scope.py' not in new
            or PIN.encode() not in new):raise ValueError('Actual desktop before/new bytes or launch pins differ')
        for name,data in (('DESKTOP_BEFORE.desktop',old),('DESKTOP_INDEPENDENT_RESTORE.desktop',old),('DESKTOP_ACTIVE_BUILD28.desktop',new)):triple(name,data)
        if read(HERE/'activate_full_desktop_action_v5.py')!=action:raise ValueError('Action changed during review')
        summary=dict(status='ACTUAL_DESKTOP_ACTIVATION_PC_BYTE_READBACK_PASSED',output=str(out),native_dispatch=str(args.result),before_sha256=sha(old),active_sha256=sha(new),package_manifest_sha256=PIN,independent_pc_before_restore_readbacks=True,full_native_tree_mirror_claimed=False,documentation_updated=False,documentation_update_owner='final publication review',action_source_unchanged=True,native_action=False)
        put('RESULT.json',encode(summary));put('SOURCE_CLOSED.json',encode(dict(closed_unix=time.time(),prepared_allocated_bytes=used,source_backups_and_independent_restores=True,native_action=False)));print(json.dumps(summary))
    except BaseException as error:
        put('FAILURE.json',encode(dict(type=type(error).__name__,message=str(error)[:2048])));raise

if __name__=='__main__':main()
