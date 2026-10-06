"""Prepare the existing bounded backup helper for speech19. README_SPEECH19_BACKUP.md."""
import argparse
import ast
import base64
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
NATIVE='/home/peachyprototype/JustPeachy/research/nemotron-20260928'
DATA='/home/peachyprototype/JustPeachy/data/runtime-v29'
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BOOT='0561d730-3cad-48e0-940a-fe3930c89665'
PIN='1cb7b8c3ac07d7975b2a31585f94b6402d419a12a128b05758ed7af644319f4c'
SESSION='8c5d357f0acc4640bfcda4697d7e325b'
LABEL='production-backup-09'
COMMON_SHA='aba044705f9e4938261cd82d46264b5c4868206abcac290a31580f971a1d50ef'
MAXIMUM=1024**2

def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate backup preparation field')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
def read(path,maximum=262144):
    path=Path(path);before=path.lstat()
    if path.is_symlink() or before.st_nlink!=1 or not path.is_file() or before.st_size>maximum:raise ValueError('Bounded independent preparation input')
    raw=path.read_bytes();after=path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns) or len(raw)!=before.st_size:raise ValueError('Preparation input changed')
    return raw

def bootstrap(output):
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p
    h=k.GetCurrentProcess();k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(h,16384):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not k.GetProcessTimes(h,*(ctypes.byref(v) for v in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    if output is None:output=PRIVATE/'audit-preparation'/('speech19-backup-job-'+uuid.uuid4().hex)
    if output.parent!=PRIVATE/'audit-preparation' or output.is_symlink():raise ValueError('Exact private unique preparation parent')
    output.mkdir(exist_ok=True)
    if any(output.iterdir()):raise ValueError('Fresh empty host output required')
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity=[14],affinity_mask=16384,creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
    def write(name,raw):
        if sum(p.stat().st_size for p in output.iterdir() if p.is_file())+len(raw)>MAXIMUM:raise ValueError('OneMiB preparation bound')
        with (output/name).open('xb') as f:
            if f.write(raw)!=len(raw):raise OSError('Short preparation write')
            f.flush();os.fsync(f.fileno())
        if (output/name).read_bytes()!=raw:raise OSError('Preparation readback')
    write('REGISTERED_OWNER.json',encoded(owner))
    write('HOST_SCOPE.json',encoded(dict(issued_unix=time.time(),maximum_seconds=600,maximum_output_bytes=MAXIMUM,cpu=14,native_action=False)))
    return output,write,owner

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--job-result',type=Path,help='Actual successful backup-dispatch RESULT, not monitor finalization')
    ap.add_argument('--preparation',type=Path,help='Closed payload preparation; required with --job-result')
    args=ap.parse_args();out,write,owner=bootstrap(args.output);began=time.time();sys.dont_write_bytecode=True
    rows=[]
    def copies(name,raw):
        for suffix in ('','.backup','.restore'):write(name+suffix,raw)
        rows.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    copies('prepare_speech19_backup.py',read(Path(__file__),65536))
    copies('README.md',read(HERE/'README_SPEECH19_BACKUP.md',32768))
    if args.job_result:
        if args.preparation is None or args.preparation.parent!=PRIVATE/'audit-preparation':raise ValueError('Exact closed payload preparation required')
        prepared=strict(read(args.preparation/'PAYLOAD.json',65536))
        if prepared['label']!=LABEL or prepared['boot_id']!=BOOT or prepared['package_manifest_sha256']!=PIN:raise ValueError('Exact speech19 backup package contract')
        closed=strict(read(args.preparation/'HOST_CHECK_CLOSED.json',65536))
        if closed.get('status')!='EXACT_HOST_OWNER_ABSENT':raise ValueError('Actual prior host preparation must be closed')
        raw=read(args.job_result,262144);copies('DISPATCH_RESULT.json',raw);value=strict(raw)
        job=value.get('action_result')
        if (type(job) is not dict or job.get('schema')!='just-peachy.native-component-job.v1' or job.get('boot_id')!=BOOT
            or job.get('package_manifest_sha256')!=PIN or job.get('unit')!='jp-v29-'+LABEL+'.service'
            or job.get('output_root')!=NATIVE+'/live-runtime-tests-20261003/'+LABEL
            or job.get('external_backup_common_sha256')!=COMMON_SHA
            or job.get('external_backup_schema')!='just-peachy.external-backup-common.v2'
            or job.get('control_group')!='/user.slice/user-1000.slice/user@1000.service/app.slice/jp-v29-'+LABEL+'.service'
            or type(job.get('owner')) is not dict or job['owner'].get('boot_id')!=BOOT
            or any(type(job['owner'].get(k)) is not int or job['owner'][k]<=0 for k in ('pid','start_ticks'))):
            raise ValueError('Actual exact running backup JOB required')
        copies('JOB.json',encoded(job));copies('SEEDS.json',read(args.preparation/'SEEDS.json',65536))
        write('SOURCE_CLOSED.json',encoded(dict(status='ACTUAL_JOB_EXTRACTED_NO_NATIVE_ACTION',owner=owner,members=rows,closed_unix=time.time(),native_action=False,backup_complete=False)))
        print(str(out));return
    n=HERE.parent
    common_raw=read(n/'backup_external_common_v2.py',32768)
    if len(common_raw)!=20433 or hashlib.sha256(common_raw).hexdigest()!=COMMON_SHA:raise ValueError('Exact unchanged external common helper')
    action=read(n/'launch_backup_external_action_v2.py',32768)
    copies('ACTION.py',action);copies('EXTERNAL_COMMON.py',common_raw)
    inspect_path=PRIVATE/'operation-speech-storage-inspect19-01/dispatch/RESULT.json'
    inspected_raw=read(inspect_path,262144);copies('NUMERIC_INSPECTION.json',inspected_raw);inspected=strict(inspected_raw)['action_result']
    if inspected.get('status')!='FAILED19_NUMERIC_STORAGE_READ_ONLY' or inspected.get('session_id')!=SESSION or inspected.get('boot_id')!=BOOT or inspected.get('package_manifest_sha256')!=PIN:raise ValueError('Exact actual failed19 inspection required')
    if len(inspected['old_owners'])!=3 or any(row.get('exact_absent') is not True for row in inspected['old_owners']):raise ValueError('Old main/worker/source exact absence evidence')
    db=DATA+'/recordings/history.sqlite3'
    roots=[dict(source=db,destination='history.sqlite3'),dict(source=DATA+'/recordings/sessions/'+SESSION,destination='session19')]
    for suffix,identity in inspected['sqlite_sidecars'].items():
        if suffix not in ('-wal','-shm','-journal'):raise ValueError('Exact sidecar kind')
        if identity is not None:roots.append(dict(source=db+suffix,destination='history.sqlite3'+suffix))
    scope=dict(schema='just-peachy.production-backup-scope.v1',reviewed=True,roots=roots,external_assets=[],
        maximum_payload_bytes=128*1024**2,maximum_external_asset_bytes=0,runtime_seconds=480,
        scope_classification='pre-speech-storage-schema-DB-and-failed19-only',
        existing_database_sha256=inspected['database_sha256'],existing_database_identity=inspected['database_identity'],
        source_inspection_sha256=hashlib.sha256(inspected_raw).hexdigest(),boot_id=BOOT,session_id=SESSION,
        unrelated_recording_directories_in_scope=False,unchanged_selection_settings_in_scope=False)
    # Exact native POSIX validation uses the original validator with only its two Path names translated for Windows.
    namespace=dict(__name__='speech19_unchanged_common',__file__=str(n/'backup_external_common_v2.py'))
    exec(compile(common_raw,'<backed-unchanged-common>','exec'),namespace)
    tree=ast.parse(common_raw);node=next(v for v in tree.body if isinstance(v,ast.FunctionDef) and v.name=='validate_spec');changed=0
    for v in ast.walk(node):
        if isinstance(v,ast.Name) and v.id=='Path':v.id='PurePosixPath';changed+=1
    if changed!=2:raise ValueError('Exact original POSIX validator boundary')
    namespace['PurePosixPath']=PurePosixPath
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<unchanged-POSIX-spec>','exec'),namespace)
    namespace['validate_spec'](scope)
    for row in roots:namespace['validate_native_source'](row['source'],is_file=row['destination']!='session19')
    scope_raw=encoded(scope);copies('SCOPE.json',scope_raw)
    external=dict(schema='just-peachy.external-backup-common.v2',sha256=COMMON_SHA,bytes=20433,base64=base64.b64encode(common_raw).decode())
    payload=dict(package=NATIVE+'/field-runtime-v29-build-24',package_manifest_sha256=PIN,boot_id=BOOT,expires_unix=time.time()+590,label=LABEL,
        maximum_output_bytes=16*1024**2,full_backup_reservation_bytes=scope['maximum_payload_bytes'],
        backup_scope=scope,backup_scope_sha256=hashlib.sha256(scope_raw).hexdigest(),external_backup_common=external)
    copies('PAYLOAD.json',encoded(payload))
    seed=PRIVATE/'production-backup-08-reconcile-01/payload/root-03/runtime-v29/recordings/history.sqlite3'
    seeds=[dict(destination='history.sqlite3',local=str(seed))] if seed.is_file() else []
    copies('SEEDS.json',encoded(seeds))
    compile(action,'<backed-existing-native-backup-action>','exec')
    write('SOURCE_CLOSED.json',encoded(dict(status='EXISTING_HELPER_PAYLOAD_PREPARED_NO_NATIVE_ACTION',owner=owner,members=rows,closed_unix=time.time(),payload_expires_unix=payload['expires_unix'],
        native_action=False,backup_complete=False,full_copy_reservation_bytes=134217728,native_metadata_bytes=16777216,pc_metadata_bytes=16777216,
        guard_seconds=480,total_deadline_seconds=600,selected_settings_mutated=False,existing_sources_changed=False,
        actual_capture_evidence=dict(processed_samples=inspected['processed_samples'],inspection_capture_started_scalar=inspected['capture_started'],meaning='Scalar belongs to this readonly inspection; historic speech capture is evidenced by samples/events, not by a null engine result'))))
    if time.time()-began>600:raise TimeoutError('Finite preparation')
    print(str(out))

if __name__=='__main__':main()

