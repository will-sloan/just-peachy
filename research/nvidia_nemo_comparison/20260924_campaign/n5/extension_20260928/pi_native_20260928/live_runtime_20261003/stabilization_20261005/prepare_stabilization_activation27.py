"""Prepare actual build27 activation only; README_PREPARE_ACTIVATION27.md."""
import ctypes
_k=ctypes.WinDLL('kernel32',use_last_error=True);_k.GetCurrentProcess.restype=ctypes.c_void_p
_h=_k.GetCurrentProcess();_k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
if not _k.SetProcessAffinityMask(_h,16384):raise ctypes.WinError(ctypes.get_last_error())
import argparse,base64,hashlib,json,os,re,shutil,time,uuid
from pathlib import Path
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
S=Path(__file__).parent
PIN=None
BOOT=None

def main():
    global BOOT,PIN
    stamps=[ctypes.c_ulonglong() for _ in range(4)];_k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not _k.GetProcessTimes(_h,*(ctypes.byref(v) for v in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    out=Q/'audit-preparation'/('activation27-payload-'+uuid.uuid4().hex);out.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,
        creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
    def enc(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    def sha(raw):return hashlib.sha256(raw).hexdigest()
    with (out/'REGISTERED_OWNER.json').open('xb') as stream:stream.write(enc(owner));stream.flush();os.fsync(stream.fileno())
    started=time.monotonic();used=(out/'REGISTERED_OWNER.json').stat().st_size
    def put(name,raw):
        nonlocal used
        if used+len(raw)>2*1024**2 or time.monotonic()-started>600:raise OSError('Finite2MiB/600s activation preparation')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+2*1024**2:raise OSError('Original host floor')
        with (out/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short preparation write')
            stream.flush();os.fsync(stream.fileno())
        used+=len(raw)
        if (out/name).read_bytes()!=raw:raise OSError('Independent readback differs')
    def triple(name,raw):
        for suffix in ('','.backup','.restore'):put(name+suffix,raw)
    def read(path,limit=262144):
        before=path.stat()
        if path.is_symlink() or any(p.is_symlink() for p in path.parents) or before.st_nlink!=1 or before.st_size>limit:raise ValueError('Bounded ordinary input required')
        raw=path.read_bytes();after=path.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Input changed')
        return raw
    def strict(raw):
        def pairs(rows):
            out={}
            for k,v in rows:
                if k in out:raise ValueError('Duplicate JSON key')
                out[k]=v
            return out
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
    put('HOST_SCOPE.json',enc(dict(maximum_bytes=2*1024**2,maximum_seconds=600,native_action=False)))
    triple('PREPARER.py',read(Path(__file__),65536));triple('README.md',read(S/'README_PREPARE_ACTIVATION27.md',65536))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-check-file',type=Path,required=True)
    parser.add_argument('--finalizer-result',type=Path,required=True)
    parser.add_argument('--boot-id',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args()
    if str(uuid.UUID(args.boot_id))!=args.boot_id or re.fullmatch('[0-9a-f]{64}',args.manifest_sha256) is None:
        raise ValueError('Exact current boot/manifest inputs required')
    BOOT,PIN=args.boot_id,args.manifest_sha256
    action=read(S/'activate_full_desktop_action_v4.py',65536)
    if sha(action)!='fa8156e7076125e8d85fbae40f53fee79e908ec6a8eaea16757cd534832357b1':raise ValueError('Frozen unchanged activation transaction required')
    triple('ACTION.py',action);compile(action,'<backed-activation27-action>','exec')
    check_file=args.native_check_file
    if (check_file.name!='NATIVE_CHECK_V2.json' or check_file.parent.name!='closed-output'
        or check_file.parent.parent.parent!=Q
        or re.fullmatch('classic-ui-check-[0-9]{2}-finalized-monitor-[0-9]{2}',check_file.parent.parent.name) is None
        or check_file.resolve(strict=True)!=check_file):
        raise ValueError('Canonical actual finalized full-mirror check receipt required')
    proof_raw=read(check_file,65536);proof=strict(proof_raw)
    if (proof.get('status')!='PASS' or proof.get('boot_id')!=BOOT or proof.get('package_manifest_sha256')!=PIN
        or any(proof.get(k) is not True for k in ('actual_portrait_ui','capture_function_passed','workers_closed','main_exact_owner_gone','unit_recursively_empty','independent_native_finalize'))):raise ValueError('Actual closed Live29 current-boot proof required')
    triple('ACTUAL_NATIVE_CHECK_V2.json',proof_raw)
    finalizer_raw=read(args.finalizer_result);finalizer=strict(finalizer_raw)
    finalized=finalizer.get('action_result')
    number=check_file.parent.parent.name.split('-')[3]
    native_check='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/classic-ui-check-'+number+'/NATIVE_CHECK_V2.json'
    utility=finalizer.get('utility_owner')
    if (type(finalized) is not dict or finalized.get('proof')!=proof
        or finalized.get('native_check_path')!=native_check or finalizer.get('boot_id')!=BOOT
        or finalizer.get('utility_pid_absent_after_ssh') is not True
        or type(utility) is not dict or set(utility)!={'pid','start_ticks','boot_id'}
        or utility.get('boot_id')!=BOOT
        or any(type(utility.get(k)) is not int or utility[k]<=0 for k in ('pid','start_ticks'))):
        raise ValueError('Matching actual finalizer output and exact utility closure required')
    triple('ACTUAL_FINALIZER_RESULT.json',finalizer_raw)
    prior_raw=read(Q/'operation-stabilization-desktop26-01/dispatch/RESULT.json');prior=strict(prior_raw);desktop=prior['action_result']
    raw_desktop=base64.b64decode(desktop['desktop_base64'],validate=True)
    if (desktop.get('status')!='CLASSIC_SHORTCUT_ACTIVATED'
        or desktop.get('package_manifest_sha256')!='f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0'
        or desktop.get('desktop')!='/home/peachyprototype/Desktop/Just Peachy.desktop'
        or sha(raw_desktop)!=desktop.get('desktop_sha256')
        or desktop['desktop_sha256']!='d014baa64a8330bc802a59616c8d3a0874a97402d6ff9cef77d29c6dd8d24fe4'
        or desktop.get('login_autostart_disabled') is not True
        or desktop.get('autostart_sha256')!='8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206'):raise ValueError('Actual prior26 shortcut/disabled-autostart receipt required')
    triple('PRIOR_DESKTOP_ACTIVATION.json',prior_raw);triple('EXPECTED_PRIOR_DESKTOP.desktop',raw_desktop)
    payload=dict(expected_boot_id=BOOT,package='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-27',package_manifest_sha256=PIN,
        data_root='/home/peachyprototype/JustPeachy/data/runtime-v29',
        native_check_path=native_check,
        native_check_sha256=sha(proof_raw),autostart_sha256=desktop['autostart_sha256'],
        previous_desktop=[dict(path=desktop['desktop'],sha256=desktop['desktop_sha256'])],
        evidence_root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-classic-activation-'+uuid.uuid4().hex)
    triple('PAYLOAD.json',enc(payload))
    put('INPUT_REVIEW.json',enc(dict(native_proof_actual_pc_sha256=sha(proof_raw),session_id=proof['session_id'],
        actual_finalizer_output_sha256=sha(finalizer_raw),native_check_path=native_check,
        historical_desktop_receipt_boot=prior.get('boot_id'),current_boot=BOOT,
        prior_desktop_receipt_sha256=sha(prior_raw),expected_desktop_cas=desktop['desktop_sha256'],
        fresh_desktop_observation_claimed=False,transaction_rechecks_before_backup_and_mutation=True,
        independent_target_and_pc_metadata_reservation_bytes=16*1024**2,native_action=False)))
    put('SOURCE_CLOSED.json',enc(dict(independent_restores=True,closed_unix=time.time(),prepared_bytes=used,
        payload_sha256=sha(enc(payload)),action_sha256=sha(action),native_action=False)))
    print(json.dumps(dict(output=str(out),action=str(out/'ACTION.py'),original_action=str(S/'activate_full_desktop_action_v4.py'),payload=str(out/'PAYLOAD.json'),native_action=False)))

if __name__=='__main__':main()
