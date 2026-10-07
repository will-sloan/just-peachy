"""Prepare actual finalized check34/build29 activation; README_CORE_ACTIVATION29.md."""
import ctypes
_k=ctypes.WinDLL('kernel32',use_last_error=True);_k.GetCurrentProcess.restype=ctypes.c_void_p
_h=_k.GetCurrentProcess();_k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
if not _k.SetProcessAffinityMask(_h,16384):raise ctypes.WinError(ctypes.get_last_error())
import argparse,base64,hashlib,json,os,re,shutil,time,uuid
from pathlib import Path, PurePosixPath
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
S=Path(__file__).parent
REFERENCE=S.parent/'stabilization_20261005'
TARGET29='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-29'
PIN29='331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b'
CURRENT_BOOT='e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
PARENT_PREPARER_SHA='796c7fed98400577eeb19a3460ff78484bf1044308254b6b0fea0e76380b369f'
PARENT_ACTION_SHA='e336034c83c77e524c6f2762ac6726961c1344a35f36e1a7da448db4ee244f65'
PRIOR_RECEIPT_SHA='638ebe5c58d038bcfa09a3f649de3775888e702ac73154ce682e9ca6e0d259c7'
PIN=None
BOOT=None


def verify_full_mirror(check_file,proof,read,strict,sha,expected_complete_sha):
    """Rehash every file of the real, independently closed check34 mirror.

    Stream payload files with64KiB buffers; retain only bounded metadata. No
    native probe, SSH, SQLite connection, model or recording-store access.
    """
    mirror=check_file.parent.parent
    raw={name:read(mirror/name,2*1024**2) for name in
        ('MIRROR_COMPLETE.json','MIRROR_MANIFEST.json','RESULT.json','EFFECTIVE_JOB.json')}
    if sha(raw['MIRROR_COMPLETE.json'])!=expected_complete_sha:
        raise ValueError('Actual root-reviewed check34 mirror completion pin differs')
    complete,rows,result,job=(strict(raw[name]) for name in raw)
    closure=complete.get('closure',{});exit_receipt=closure.get('job_exit',{})
    native_root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/classic-ui-check-34'
    if (complete.get('kind')!='COMPLETE' or complete.get('mirror_scope')!='all_regular_output_files'
        or complete.get('manifest_sha256')!=sha(raw['MIRROR_MANIFEST.json'])
        or any(closure.get(k) is not True for k in ('closed','exact_owner_gone','cgroup_empty'))
        or closure.get('owner')!=job.get('owner') or proof.get('owner')!=job.get('owner')
        or closure.get('invocation_id')!=job.get('invocation_id')
        or proof.get('invocation_id')!=job.get('invocation_id')
        or closure.get('unit')!='jp-v29-classic-ui-check-34.service'
        or proof.get('unit')!=closure.get('unit') or job.get('unit')!=closure.get('unit')
        or job.get('boot_id')!=CURRENT_BOOT or job.get('package_manifest_sha256')!=PIN29
        or job.get('output_root')!=native_root or job.get('owner',{}).get('boot_id')!=CURRENT_BOOT
        or exit_receipt.get('owner')!=job.get('owner')
        or exit_receipt.get('invocation_id')!=job.get('invocation_id')
        or exit_receipt.get('unit')!=job.get('unit') or exit_receipt.get('natural_returncode')!=0
        or exit_receipt.get('error') or exit_receipt.get('output_budget_failure')
        or exit_receipt.get('leases_released') is not True
        or result.get('status')!='FULL_CLOSED_OUTPUT_MIRRORED'
        or result.get('copied_root')!=str(check_file.parent) or result.get('job')!=job
        or result.get('mirror_scope')!='all_regular_output_files'
        or result.get('functional_success') is not True or result.get('native_actions') is not False
        or type(rows) is not list or type(job.get('maximum_output_bytes')) is not int
        or job['maximum_output_bytes']<=0):
        raise ValueError('Actual check34 natural owner/unit closure and full independent mirror required')
    expected=set();total=0
    for row in rows:
        name=row['path'];relative=PurePosixPath(name);size=row.get('identity',{}).get('bytes')
        if (not name or relative.is_absolute() or '..' in relative.parts or '\\' in name
            or relative.as_posix()!=name or name in expected or type(size) is not int or size<0
            or re.fullmatch('[0-9a-f]{64}',row.get('sha256','')) is None):
            raise ValueError('Exact unique bounded mirror inventory required')
        path=check_file.parent.joinpath(*relative.parts);before=path.stat()
        if (path.is_symlink() or path.resolve(strict=True)!=path or not path.is_file()
            or before.st_nlink!=1 or before.st_size!=size):
            raise ValueError('Real single-link mirrored member required')
        total+=size
        if total>job['maximum_output_bytes']:
            raise ValueError('Full mirror exceeds admitted native output extent')
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            while True:
                block=stream.read(65536)
                if not block:break
                digest.update(block)
        after=path.stat()
        if ((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
            !=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
            or digest.hexdigest()!=row['sha256']):
            raise ValueError('Full mirror independent hash readback differs: '+name)
        expected.add(name)
    actual=set()
    for directory,dirs,files in os.walk(check_file.parent,followlinks=False):
        parent=Path(directory)
        if parent.resolve(strict=True)!=parent or any((parent/name).is_symlink() for name in dirs):
            raise ValueError('Canonical real mirror directories required')
        actual.update((parent/name).relative_to(check_file.parent).as_posix() for name in files)
    if (actual!=expected or 'NATIVE_CHECK_V2.json' not in expected
        or complete.get('files')!=len(rows) or complete.get('bytes')!=total):
        raise ValueError('Full closed-output mirror membership/extent differs')
    native_proof_row=next(row for row in rows if row['path']=='NATIVE_CHECK_V2.json')
    if native_proof_row['sha256']!=sha(read(check_file,65536)):
        raise ValueError('Finalized proof is not the inventoried independent mirror file')
    return dict(check_number=34,mirror=str(mirror),native_root=native_root,
        files=len(rows),bytes=total,independent_full_hash_readback=True,
        complete_sha256=expected_complete_sha,manifest_sha256=sha(raw['MIRROR_MANIFEST.json']),
        owner=job['owner'],invocation_id=job['invocation_id'],unit=job['unit'],
        natural_returncode=0,exact_owner_gone=True,cgroup_empty=True),raw


def main():
    global BOOT,PIN
    stamps=[ctypes.c_ulonglong() for _ in range(4)];_k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not _k.GetProcessTimes(_h,*(ctypes.byref(v) for v in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    out=Q/'audit-preparation'/('activation29-payload-'+uuid.uuid4().hex);out.mkdir()
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
        if path.is_symlink() or path.resolve(strict=True)!=path or any(p.is_symlink() for p in path.parents) or not path.is_file() or before.st_nlink!=1 or before.st_size>limit:raise ValueError('Bounded ordinary input required')
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
    triple('PREPARER.py',read(Path(__file__),65536));triple('README.md',read(S/'README_CORE_ACTIVATION29.md',65536))
    parent_preparer=read(REFERENCE/'prepare_stabilization_activation28_v2.py',65536)
    parent_action=read(REFERENCE/'activate_full_desktop_action_v5.py',65536)
    if sha(parent_preparer)!=PARENT_PREPARER_SHA or sha(parent_action)!=PARENT_ACTION_SHA:
        raise ValueError('Exact immutable activation28 reference pins required')
    triple('PARENT_PREPARER.py',parent_preparer);triple('PARENT_ACTION.py',parent_action)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-check-file',type=Path,required=True)
    parser.add_argument('--finalizer-result',type=Path,required=True)
    parser.add_argument('--boot-id',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--mirror-complete-sha256',required=True)
    parser.add_argument('--finalizer-result-sha256',required=True)
    args=parser.parse_args()
    if (args.boot_id!=CURRENT_BOOT or args.manifest_sha256!=PIN29
        or str(uuid.UUID(args.boot_id))!=args.boot_id
        or any(re.fullmatch('[0-9a-f]{64}',value) is None for value in
            (args.mirror_complete_sha256,args.finalizer_result_sha256))):
        raise ValueError('Exact current boot/build29 manifest and reviewed future proof pins required')
    BOOT,PIN=args.boot_id,args.manifest_sha256
    action=read(S/'activate_core_desktop_action29.py',65536)
    if sha(action)!='e1a4e02b360e4d947b6c5e60952b3518d52abcbe8e004f3bae5cc786f99db271':raise ValueError('Frozen narrow build29 activation transaction required')
    triple('ACTION.py',action);compile(action,'<backed-activation29-action>','exec')
    check_file=args.native_check_file
    if (check_file.name!='NATIVE_CHECK_V2.json' or check_file.parent.name!='closed-output'
        or check_file.parent.parent.parent!=Q
        or re.fullmatch('classic-ui-check-34-finalized-monitor-[0-9]{2}',check_file.parent.parent.name) is None
        or check_file.resolve(strict=True)!=check_file):
        raise ValueError('Canonical actual finalized full-mirror check receipt required')
    proof_raw=read(check_file,65536);proof=strict(proof_raw)
    if (proof.get('status')!='PASS' or proof.get('boot_id')!=BOOT or proof.get('package_manifest_sha256')!=PIN
        or any(proof.get(k) is not True for k in ('actual_portrait_ui','capture_function_passed','workers_closed','main_exact_owner_gone','unit_recursively_empty','independent_native_finalize'))):raise ValueError('Actual closed build29/check34 current-boot proof required')
    triple('ACTUAL_NATIVE_CHECK_V2.json',proof_raw)
    mirror_review,mirror_raw=verify_full_mirror(check_file,proof,read,strict,sha,args.mirror_complete_sha256)
    triple('FULL_MIRROR_REVIEW.json',enc(mirror_review))
    for name,raw in mirror_raw.items():triple('ACTUAL_'+name,raw)
    finalizer_raw=read(args.finalizer_result);finalizer=strict(finalizer_raw)
    if sha(finalizer_raw)!=args.finalizer_result_sha256:
        raise ValueError('Actual root-reviewed check34 finalizer pin differs')
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
    prior_raw=read(Q/'operation-stabilization-desktop28-01/dispatch/RESULT.json');prior=strict(prior_raw);desktop=prior['action_result']
    if sha(prior_raw)!=PRIOR_RECEIPT_SHA:
        raise ValueError('Exact actual prior28 activation receipt pin differs')
    raw_desktop=base64.b64decode(desktop['desktop_base64'],validate=True)
    if (desktop.get('status')!='CLASSIC_SHORTCUT_ACTIVATED'
        or desktop.get('package_manifest_sha256')!='e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b'
        or desktop.get('desktop')!='/home/peachyprototype/Desktop/Just Peachy.desktop'
        or sha(raw_desktop)!=desktop.get('desktop_sha256')
        or desktop['desktop_sha256']!='8c917153c58c57d73d8ce0d0e5662b42b3f7d698de0cee4189b844f8cfc70ac0'
        or desktop.get('login_autostart_disabled') is not True
        or desktop.get('autostart_sha256')!='8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206'):raise ValueError('Actual prior28 shortcut/disabled-autostart receipt required')
    triple('PRIOR_DESKTOP_ACTIVATION.json',prior_raw);triple('EXPECTED_PRIOR_DESKTOP.desktop',raw_desktop)
    payload=dict(expected_boot_id=BOOT,package=TARGET29,package_manifest_sha256=PIN,
        data_root='/home/peachyprototype/JustPeachy/data/runtime-v29',
        native_check_path=native_check,
        native_check_sha256=sha(proof_raw),autostart_sha256=desktop['autostart_sha256'],
        previous_desktop=[dict(path=desktop['desktop'],sha256=desktop['desktop_sha256'])],
        evidence_root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-classic-activation-'+uuid.uuid4().hex)
    triple('PAYLOAD.json',enc(payload))
    put('INPUT_REVIEW.json',enc(dict(native_proof_actual_pc_sha256=sha(proof_raw),session_id=proof['session_id'],
        actual_finalizer_output_sha256=sha(finalizer_raw),native_check_path=native_check,
        independent_full_mirror=mirror_review,
        historical_desktop_receipt_boot=prior.get('boot_id'),current_boot=BOOT,
        prior_desktop_receipt_sha256=sha(prior_raw),expected_desktop_cas=desktop['desktop_sha256'],
        fresh_desktop_observation_claimed=False,transaction_rechecks_before_backup_and_mutation=True,
        independent_target_and_pc_metadata_reservation_bytes=16*1024**2,native_action=False)))
    if (read(check_file,65536)!=proof_raw or read(args.finalizer_result)!=finalizer_raw
        or any(read(check_file.parent.parent/name,2*1024**2)!=raw for name,raw in mirror_raw.items())):
        raise ValueError('Actual finalized proof/mirror inputs changed during preparation')
    put('SOURCE_CLOSED.json',enc(dict(independent_restores=True,closed_unix=time.time(),prepared_bytes=used,
        payload_sha256=sha(enc(payload)),action_sha256=sha(action),native_action=False,
        actual_check_number=34,independent_full_mirror=mirror_review)))
    print(json.dumps(dict(output=str(out),action=str(out/'ACTION.py'),original_action=str(S/'activate_core_desktop_action29.py'),payload=str(out/'PAYLOAD.json'),native_action=False)))

if __name__=='__main__':main()
