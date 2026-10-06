"""Prepare an unapproved final source plan only; README_STABILIZATION_PUBLICATION_V1.md."""
import ctypes
_k=ctypes.WinDLL('kernel32',use_last_error=True)
_k.GetCurrentProcess.restype=ctypes.c_void_p
_h=_k.GetCurrentProcess()
_k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
if not _k.SetProcessAffinityMask(_h,16384):raise ctypes.WinError(ctypes.get_last_error())
import argparse,hashlib,json,os,re,shutil,stat,time,uuid
from pathlib import Path,PurePosixPath
ROOT=Path('G:/Just_Peachy_N1/20260924_campaign/worktree')
HERE=Path(__file__).parent
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE=Q/'audit-preparation/final-handoff-v29-build21-20261005/REVIEWED_PLAN.json'
BASE_SHA='804819723754a73be4a718a98ec0b237ff9906888e743ece0cdaf08283978556'
PIN='f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0'
C='research/nvidia_nemo_comparison/20260924_campaign/n5/completion_20261001/'
L='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/'
TRACKED=('DELIVERY_START_HERE.md',C+'ACCEPTANCE.json',C+'ACCEPTANCE_SCOPE.md',
    C+'BACKEND_COMBINATIONS.md',C+'CURRENT_RUNTIME_PROGRESS.md',C+'INSTALL_HEALTH_AND_RECOVERY.md',
    C+'MODE_GUIDE.md',C+'PATHS_AND_BACKUPS.md',C+'START_HERE_CURRENT.md',L+'MODE_GUIDE.md',
    L+'README_PIPELINES.md',L+'pipelines/chunk52_threads2.md',L+'pipelines/command_matrix.md',
    L+'pipelines/current_delayed.md',L+'pipelines/pyannote_redimnet.md',L+'pipelines/pyannote_titanet.md')
SELECTED='''launcher.py classic_frontend.py installed_engine.py installed_source.py
application_contract.py application_controller.py mature_frontend.py saved_replay.py
operator_profiles.py seat_backend.py saved_spatial.py storage.py worker.py
README.md README_OPERATOR_PROFILES.md README_SEAT_BACKENDS.md README_SAVED_SPATIAL.md
README_STARTUP_REPAIR.md README_SAVED_REPLAY.md README_STORAGE.md README_METADATA_CLEANUP.md
README_SOURCE_FAILURE_STATUS.md README_SAVED_SOURCE_CLOSURE.md
STABILIZATION_CHECKLIST.md STABILIZATION_MODE_GUIDE.md BACKEND_MATRIX.md
STABILIZATION_RESULTS.md SPEECH_STORAGE_REPAIR_FINDINGS.md
build_stabilization_package_v6.py README_STABILIZATION_PACKAGE_V6.md
stage_stabilization_action.py prepare_stabilization_stage26.py README_STAGE26_PREPARATION.md
host_stabilization_operations_v5.py README_HOST_STABILIZATION_OPERATIONS_V5.md native_scope.py
coordinator_filetime_v1.py check_coordinator_filetime_v1.py
prepare_stabilization_live_check_v3.py README_LIVE_CHECK_PAYLOAD_V3.md
native_stabilization_check_v5.py README_NATIVE_STABILIZATION_CHECK_V5.md
extract_stabilization_job_v6.py README_EXTRACT_STABILIZATION_JOB_V6.md
prepare_stabilization_finalize_v6.py README_FINALIZE_PAYLOAD_V6.md
activate_full_desktop_action_v4.py README_STABILIZATION_ACTIVATION_V4.md
prepare_stabilization_activation26.py README_PREPARE_ACTIVATION26.md
review_stabilization_activation26.py README_REVIEW_ACTIVATION26.md
freeze_build26_support.py README_BUILD26_SUPPORT_FREEZE.md
prepare_saved_stabilization_payload_v5.py README_PREPARE_SAVED_STABILIZATION_V5.md
native_saved_stabilization_check_v4.py README_NATIVE_SAVED_STABILIZATION_CHECK_V4.md
extract_saved_stabilization_job_v2.py README_EXTRACT_SAVED_STABILIZATION_JOB_V2.md
check_saved_payload_v5_source.py check_saved_source_closure.py
prepare_stabilization_export_v1.py README_STABILIZATION_EXPORT_V1.md
extract_stabilization_export_job_v1.py README_EXTRACT_STABILIZATION_EXPORT_JOB_V1.md
verify_stabilization_export_v3.py README_VERIFY_STABILIZATION_EXPORT_V3.md
inspect_kept_source21_v2.py prepare_kept_source21_inspection_v2.py README_KEPT_SOURCE21_INSPECTION_V2.md
inspect_speech_storage19.py README_SPEECH_STORAGE_INSPECTION.md
inspect_speech_work19.py README_SPEECH_WORK_INSPECTION.md
prepare_speech19_backup.py README_SPEECH19_BACKUP.md
verify_speech19_backup_restore_v2.py README_SPEECH19_BACKUP_RESTORE_V2.md
monitor_speech_ready.py native_speech_ready_probe.py README_SPEECH_READY.md
launch_current_xvf_repair_v2.py prepare_current_xvf_repair_v2.py README_CURRENT_XVF_REPAIR.md
check_stabilization_faults.py check_source_failure_status.py check_metadata_cleanup.py
check_seat_backend.py check_seat_integration.py check_saved_spatial.py check_speech_storage_repair_v2.py
prepare_saved27_failure_inspection.py
prepare_stabilization_publication_v1.py README_STABILIZATION_PUBLICATION_V1.md'''.split()

def encoded(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def strict(raw):
    def pairs(rows):
        out={}
        for key,value in rows:
            if key in out:raise ValueError('Duplicate plan key')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
def read(path,maximum=2*1024**2):
    before=path.lstat();resolved=path.resolve(strict=True)
    if (path.is_symlink() or any(p.is_symlink() for p in path.parents) or not stat.S_ISREG(before.st_mode)
        or before.st_nlink!=1 or before.st_size>maximum or os.path.normcase(str(path.absolute()))!=os.path.normcase(str(resolved))):raise ValueError('Canonical bounded ordinary source required: '+str(path))
    raw=path.read_bytes();after=path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns) or len(raw)!=before.st_size:raise ValueError('Source changed during plan snapshot')
    return raw

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--label',required=True)
    args=parser.parse_args()
    if re.fullmatch(r'[a-z][a-z0-9-]{0,63}',args.label) is None:raise ValueError('Fresh canonical plan label required')
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    _k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not _k.GetProcessTimes(_h,*(ctypes.byref(s) for s in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    out=Q/'audit-preparation'/(args.label+'-'+uuid.uuid4().hex);out.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
    with (out/'REGISTERED_OWNER.json').open('xb') as stream:
        raw=encoded(owner);stream.write(raw);stream.flush();os.fsync(stream.fileno())
    started=time.monotonic();written=len(raw)+65536;directories={out}
    def put(name,raw):
        nonlocal written
        path=out.joinpath(*PurePosixPath(name).parts)
        if path.is_relative_to(out) is not True:raise ValueError('Owned output only')
        pending=[p for p in path.parents if p!=out and p.is_relative_to(out) and p not in directories]
        if written+len(raw)+len(pending)*65536>16*1024**2 or time.monotonic()-started>600:raise OSError('Finite16MiB includingdirectories/600s plan scope')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+16*1024**2:raise OSError('Original host floor')
        path.parent.mkdir(parents=True,exist_ok=True);directories.update(pending);written+=len(pending)*65536
        with path.open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short publication-plan write')
            stream.flush();os.fsync(stream.fileno())
        written+=len(raw)
        if read(path,16*1024**2)!=raw:raise OSError('Independent publication-plan readback differs')
    put('HOST_SCOPE.json',encoded(dict(maximum_bytes=16*1024**2,maximum_seconds=600,includes_directory_reservations=True,native_action=False,zip_built=False)))
    try:
        for name in ('prepare_stabilization_publication_v1.py','README_STABILIZATION_PUBLICATION_V1.md'):
            raw=read(HERE/name)
            for suffix in ('','.backup','.restore'):put(name+suffix,raw)
        base_raw=read(BASE,1024**2)
        if sha(base_raw)!=BASE_SHA:raise ValueError('Exact immutable build21 handoff plan required')
        base=strict(base_raw)
        if base.get('schema')!='just-peachy.reviewed-public-handoff.v1' or base.get('reviewed_publication') is not True:raise ValueError('Prior reviewed plan required')
        sources={row['member']:Path(row['source']) for row in base['files']};old={row['member']:row for row in base['files']}
        sources[C+'START_HERE.md']=ROOT/(C+'START_HERE_CURRENT.md')
        queue=list(SELECTED);chosen=set();referenced_history=[];missing_links=[]
        while queue:
            name=queue.pop()
            if name in chosen:continue
            if re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*\.(?:py|md)',name) is None:raise ValueError('Explicit flat stabilization source required')
            raw=read(HERE/name);text=raw.decode('utf-8');chosen.add(name)
            for dependency in re.findall(r'\b([A-Za-z][A-Za-z0-9_.-]*\.(?:py|md))\b',text):
                if dependency not in chosen and (HERE/dependency).is_file():
                    queue.append(dependency)
                    if dependency not in SELECTED:referenced_history.append(dependency)
            if name.endswith('.md'):
                for target in re.findall(r'\]\(([^)]+)\)',text):
                    target=target.split('#',1)[0].strip('<>')
                    if not target or ':' in target or target.startswith('/'):continue
                    candidate=(HERE/target).resolve()
                    if candidate.is_relative_to(ROOT) and candidate.is_file():
                        member=candidate.relative_to(ROOT).as_posix()
                        if member not in sources and candidate.parent!=HERE:missing_links.append(member)
                    elif not candidate.is_file():missing_links.append(name+' -> '+target)
        for name in chosen:sources[(HERE/name).relative_to(ROOT).as_posix()]=HERE/name
        for name in TRACKED:sources[name]=ROOT/name
        rows=[];total=0;aliases=set();changed=[];snapshots={}
        for member,path in sorted(sources.items()):
            rel=PurePosixPath(member)
            if (rel.is_absolute() or '..' in rel.parts or '\\' in member or rel.as_posix()!=member
                or member.casefold() in aliases or path.suffix.lower() not in {'.md','.json','.py','.txt','.toml','.h','.cpp','.c','.sh'}):raise ValueError('Exact unique public source member required')
            aliases.add(member.casefold());relative=path.resolve(strict=True).relative_to(ROOT).as_posix()
            if relative!=member and (member,relative)!=(C+'START_HERE.md',C+'START_HERE_CURRENT.md'):raise ValueError('Only locked StartHere alias permitted')
            raw=read(path);raw.decode('utf-8');total+=len(raw)
            if total>20*1024**2 or len(rows)>=4096:raise ValueError('Original20MiB/4096source bounds')
            row=dict(member=member,source=str(path),bytes=len(raw),sha256=sha(raw));rows.append(row);snapshots[member]=row
            if member not in old or (row['bytes'],row['sha256'])!=(old[member]['bytes'],old[member]['sha256']):
                changed.append(member)
                for prefix in ('source','backup','restore'):put(prefix+'/'+relative,raw)
        plan=dict(schema=base['schema'],reviewed_publication=False,
            scope='Build26 six-choice portrait runtime, Saved-source closure repair, actual scoped results and retained research provenance; all final outcomes require separate review.',files=rows)
        plan_raw=encoded(plan)
        for suffix in ('','.backup','.restore'):put('PROPOSED_PLAN_REQUIRES_FINAL_REVIEW.json'+suffix,plan_raw)
        git_names=sorted(set(TRACKED)|{(HERE/name).relative_to(ROOT).as_posix() for name in chosen})
        put('GIT_WHITELIST.txt',('\n'.join(git_names)+'\n').encode())
        if any(sha(read(path))!=snapshots[member]['sha256'] for member,path in sources.items()):raise ValueError('Publication source changed after backup')
        result=dict(output=str(out),base_plan_sha256=BASE_SHA,selected_runtime_manifest_sha256=PIN,
            prior_members=len(old),members=len(rows),source_bytes=total,git_publication_members=len(git_names),
            selected_stabilization_files=sorted(chosen),referenced_historical_sources=sorted(set(referenced_history)),
            changed_existing_and_new_members=changed,unresolved_current_links=sorted(set(missing_links)),
            proposed_plan_sha256=sha(plan_raw),reviewed_publication=False,native_action=False,zip_built=False,
            independent_changed_source_restores=True,private_media_models_galleries_included=False,
            directory_reserved_bytes=len(directories)*65536,prepared_allocated_bytes=written)
        put('PLAN_REVIEW.json',encoded(result));put('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),prepared_allocated_bytes=written,source_backups_and_independent_restores=True,native_action=False)))
        print(json.dumps(dict(output=str(out),members=len(rows),source_bytes=total,git_publication_members=len(git_names),unresolved_current_links=result['unresolved_current_links'],reviewed_publication=False,zip_built=False)))
    except BaseException as error:
        put('FAILURE.json',encoded(dict(type=type(error).__name__,message=str(error)[:2048])));raise

if __name__=='__main__':main()
