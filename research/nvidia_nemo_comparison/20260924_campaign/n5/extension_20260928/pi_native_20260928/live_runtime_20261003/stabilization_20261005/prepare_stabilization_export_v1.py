"""Bind the unchanged selected export to an actual kept/finalized build25 session. See README_STABILIZATION_EXPORT_V1.md."""
import argparse,ast,ctypes,hashlib,json,os,re,shutil,stat,sys,time,uuid
from pathlib import Path,PurePosixPath

HERE=Path(__file__).parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PIN='6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
BOOT='0561d730-3cad-48e0-940a-fe3930c89665'
ACTION_SHA='931cdf6f24058485307ac40e84b9865f38fcec22c08ccd64d85050742c348d84'
VERIFY_SHA='2d99968be2f5421c81424b95e312437a4a38e9f8993d98e088c456600e82f7e9'
PACKAGE='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-25'
LIMIT=2*1024**2

def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON member')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
def read(path,maximum):
    before=path.lstat()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>maximum:raise ValueError('Finite real input required')
    raw=path.read_bytes();after=path.stat()
    fields=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns)
    if fields(before)!=fields(after) or len(raw)!=before.st_size:raise ValueError('Input changed')
    return raw

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--job',type=Path,required=True);ap.add_argument('--closed-monitor',type=Path,required=True)
    ap.add_argument('--finalize-result',type=Path,required=True);ap.add_argument('--finalized-monitor',type=Path,required=True);ap.add_argument('--label',required=True)
    args=ap.parse_args()
    if re.fullmatch(r'recording-export-[0-9]{2}',args.label) is None:raise ValueError('Explicit unused recording-export-NN required')
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p
    h=k.GetCurrentProcess();k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(h,16384):raise ctypes.WinError(ctypes.get_last_error())
    t=[ctypes.c_ulonglong() for _ in range(4)];k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not k.GetProcessTimes(h,*(ctypes.byref(v) for v in t)):raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('stabilization-export-'+args.label+'-'+uuid.uuid4().hex);root.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,creation_filetime=t[0].value,create_time=(t[0].value-116444736000000000)/10000000)
    (root/'REGISTERED_OWNER.json').write_bytes(encoded(owner));started=time.monotonic();used=0
    def write(name,raw):
        nonlocal used
        if used+len(raw)>LIMIT or time.monotonic()-started>600:raise ValueError('Finite2MiB/600s preparation')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Host storage floor')
        with (root/name).open('xb') as output:
            if output.write(raw)!=len(raw):raise OSError('Short prepared write')
            output.flush();os.fsync(output.fileno())
        used+=len(raw)
        if (root/name).read_bytes()!=raw:raise ValueError('Independent prepared readback differs')
    def triple(name,raw):
        for suffix in ('','.backup','.restore'):write(name+suffix,raw)
    write('HOST_SCOPE.json',encoded(dict(maximum_bytes=LIMIT,maximum_seconds=600,native_action=False)))
    sys.dont_write_bytecode=True
    triple('PREPARER.py',read(Path(__file__),65536));triple('README.md',read(HERE/'README_STABILIZATION_EXPORT_V1.md',65536))
    action_path=HERE.parent/'full_application_20261004/launch_full_recording_export_action_v2.py'
    action=read(action_path,131072)
    if hashlib.sha256(action).hexdigest()!=ACTION_SHA:raise ValueError('Unchanged exact selected export action required')
    triple('ACTION.py',action);compile(action,'<unchanged-selected-export-action>','exec')
    verifier=read(HERE/'prepare_stabilization_finalize_v5.py',65536)
    if hashlib.sha256(verifier).hexdigest()!=VERIFY_SHA:raise ValueError('Exact full closed-mirror verifier required')
    triple('CLOSURE_VERIFIER.py',verifier)
    space=dict(__name__='exact_export_input_verifier',__file__=str(HERE/'prepare_stabilization_finalize_v5.py'))
    exec(compile(verifier,'<unchanged-host-closure-verifier>','exec'),space)
    job,review=space['verify'](args.job,args.closed_monitor)
    # Only the host observation folder suffix changes. All original inventory,
    # process identity, natural exit, cgroup and worker checks remain exact.
    tree=ast.parse(verifier)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify')
    changes=0
    for value in ast.walk(node):
        if isinstance(value,ast.Constant) and value.value=='-monitor-01':
            value.value='-finalized-monitor-01';changes+=1
    if changes!=1:raise ValueError('Exactly one finalized observation folder suffix boundary required')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<same-full-verifier-finalized-observation-folder>','exec'),space)
    finalized_job,finalized_review=space['verify'](args.job,args.finalized_monitor)
    if finalized_job!=job:raise ValueError('Finalized mirror changed actual source job')
    if not args.finalize_result.is_relative_to(PRIVATE):raise ValueError('Actual private finalize result required')
    raw=read(args.finalize_result,262144);triple('FINALIZE_DISPATCH_RESULT.json',raw)
    value=strict(raw);actual=value.get('action_result');proof=actual.get('proof') if type(actual) is dict else None
    expected_path=job['output_root']+'/NATIVE_CHECK_V2.json'
    complete=strict(read(args.closed_monitor/'closed-output/COMPLETE.json',65536))
    if (type(proof) is not dict or actual.get('native_check_path')!=expected_path or proof.get('status')!='PASS' or
        proof.get('boot_id')!=BOOT or proof.get('package_manifest_sha256')!=PIN or proof.get('session_id')!=complete.get('session_id') or
        proof.get('owner')!=job.get('owner') or proof.get('unit')!=job.get('unit') or proof.get('invocation_id')!=job.get('invocation_id') or proof.get('control_group')!=job.get('control_group') or
        any(proof.get(key) is not True for key in ('processed_save_passed','workers_closed','main_exact_owner_gone','unit_recursively_empty','independent_native_finalize','worker_source_closure_before_save')) or
        proof.get('worker_closure')!=complete.get('worker_closure')):raise ValueError('Actual native finalized kept-session PASS required')
    for key in complete:
        if key!='status' and proof.get(key)!=complete[key]:raise ValueError('Native finalizer changed original complete workflow: '+key)
    proof_raw=read(args.finalized_monitor/'closed-output/NATIVE_CHECK_V2.json',65536)
    if strict(proof_raw)!=proof:raise ValueError('Actual independently copied native proof differs from native response')
    # These bytes copy the real native response; they do not generate new proof.
    triple('ACTUAL_NATIVE_CHECK_RESPONSE.json',proof_raw);triple('SOURCE_JOB.json',encoded(job))
    if any(PRIVATE.glob(args.label+'-monitor-*')):raise ValueError('Export label already has native evidence')
    payload=dict(operation='dispatch',package=PACKAGE,package_manifest_sha256=PIN,boot_id=BOOT,
        label=args.label,expires_unix=time.time()+590,session_id=proof['session_id'],source_job=job,
        recordings_root='/home/peachyprototype/JustPeachy/data/runtime-v29/recordings',maximum_output_bytes=256*1024**2)
    triple('PAYLOAD.json',encoded(payload))
    write('INPUT_REVIEW.json',encoded(dict(review,finalized_mirror_review=finalized_review,finalized_observation_folder_suffix_only=True,
        actual_native_proof_copied=True,native_check_sha256=hashlib.sha256(proof_raw).hexdigest(),native_check_path=expected_path,session_id=proof['session_id'],source_job_closed=True,
        unchanged_export_action_sha256=ACTION_SHA,independent_native_reserve_bytes=256*1024**2,independent_pc_reserve_bytes=256*1024**2,native_action=False)))
    write('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),independent_restores=True,payload_sha256=hashlib.sha256(encoded(payload)).hexdigest(),prepared_bytes=used,native_action=False)))
    print(encoded(dict(output=str(root),action=str(root/'ACTION.py'),original_action=str(action_path),payload=str(root/'PAYLOAD.json'),expires_unix=payload['expires_unix'],session_id=proof['session_id'],native_action=False)).decode())

if __name__=='__main__':main()
