"""Prepare an unapproved final source plan only; README_CORE_PUBLICATION.md."""
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
BASE=Q/'audit-preparation/final-build28-reviewed-plan-c30ef5c38a5d4752ae0eb6a0fcdd4d19/REVIEWED_PLAN.json'
BASE_SHA='0639e6249fb288120657e9e1fffee56d6b72f7e9c452f4faaf071c20df035d6f'
PIN='331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b'
SOURCE_REVIEW=Q/'audit-preparation/core-package-v1-98d8679173344e6cb1f97599f489a1b7/SOURCE_DIFF_REVIEW.json'
SOURCE_REVIEW_SHA='2f2b7b92fe54c87c5f1713c3cffc2f97420b1fc5d3f7f86566c043348d01549c'
PARENT_PROPOSER_SHA='5843e4c20871bd3149bc7508be6999c83e066a1be5375aa08b6f7c98f65abb58'
FINAL_BUILDER=HERE.parent.parent/'runtime_handoff_tools/build_handoff_v2.py'
FINAL_BUILDER_SHA='34bd6696f360dd0c50a0e1817fc328b1d5a7983aa968d391c264fb8263349c6f'
C='research/nvidia_nemo_comparison/20260924_campaign/n5/completion_20261001/'
L='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/'
TRACKED=('DELIVERY_START_HERE.md',C+'ACCEPTANCE.json',C+'ACCEPTANCE_SCOPE.md',
    C+'BACKEND_COMBINATIONS.md',C+'CURRENT_RUNTIME_PROGRESS.md',C+'INSTALL_HEALTH_AND_RECOVERY.md',
    C+'MODE_GUIDE.md',C+'PATHS_AND_BACKUPS.md',C+'START_HERE_CURRENT.md',
    C+'FINAL_OPERATOR_GUIDE.md',C+'CHATGPT_HANDOFF.md',L+'MODE_GUIDE.md',
    L+'README_PIPELINES.md',L+'CORE_REPAIR_PIPELINE_NOTES.md',L+'CORE_REPAIR_TECHNICAL_NOTES.md',
    L+'pipelines/chunk52_threads2.md',L+'pipelines/command_matrix.md',
    L+'pipelines/current_delayed.md',L+'pipelines/pyannote_redimnet.md',L+'pipelines/pyannote_titanet.md')
SELECTED='''activate_core_desktop_action29.py application_controller.py asr_segment_contract.py asr_segment_runtime.py build_core_package_v1.py CAPTION_AUDIT.md caption_paragraphs.py check_asr_segments.py check_caption_repair.py classic_frontend.py core_database_recovery.py CORE_REPAIR_TECHNICAL_NOTES.md d1_spatial_policy.py gallery_snapshot_io.py host_core_operations_v2.py host_core_operations_v3.py host_core_operations_v4.py host_core_operations_v5.py host_core_operations.py host_inspect_core.py identity_modes.py inspect_core_storage.py installed_engine.py launch_core_full_app_hour.py launcher.py mature_frontend.py native_core_live_check_v2.py native_core_live_check.py native_core_saved_check_v2.py native_core_saved_check.py native_scope.py personal_gallery.py prepare_core_activation29.py prepare_core_database_recovery_v2.py prepare_core_endurance.py prepare_core_native_validation_v2.py prepare_core_native_validation.py prepare_core_publication_v1.py prepare_core_stage29_v2.py prepare_core_stage29.py README_ASR_SEGMENTS.md README_CAPTION_REPAIR.md README_CORE_ACTIVATION29.md README_CORE_BACKUP_V2.md README_CORE_BACKUP.md README_CORE_ENDURANCE.md README_CORE_INSPECTION.md README_CORE_NATIVE_VALIDATION_V2.md README_CORE_NATIVE_VALIDATION.md README_CORE_OPERATIONS_V3.md README_CORE_OPERATIONS_V4.md README_CORE_OPERATIONS_V5.md README_CORE_OPERATIONS.md README_CORE_PACKAGE_V1.md README_CORE_PUBLICATION.md README_CORE_REPAIR.md README_CORE_STAGE_V2.md README_CORE_STAGE.md README_DATABASE_RECOVERY_V2.md README_DATABASE_RECOVERY.md README_GALLERY_CAPACITY.md README_IDENTITY_MODES.md README_RUNTIME_CAPACITY.md README_STORAGE_RECOVERY.md reconcile_core_backup_v2.py reconcile_core_backup.py recover_core_database_copy.py recover_core_database_v2.py recover_core_database.py review_core_publication_v1.py run_host_caption_checks.py run_host_identity_checks.py run_host_storage_checks.py runtime_support.py stage_c24_endurance_input.py storage_support.py storage.py test_gallery_capacity.py test_identity_modes.py test_identity_pinned.py test_installed_caption_projection.py test_runtime_capacity.py test_storage_recovery.py worker.py'''.split()
CROSS_SOURCES=('ui_restore_20261004/xvf_readiness.py',
    'ui_restore_20261004/xvf_readiness_helper.py')

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
    parser.add_argument('--results-summary',type=Path,required=True,help='Final reviewed aggregate Markdown findings, without private content')
    parser.add_argument('--results-summary-sha256',required=True)
    parser.add_argument('--extra-source',action='append',default=[],help='Explicit D-relative additional code/Markdown only; no globs')
    args=parser.parse_args()
    if (re.fullmatch(r'[a-z][a-z0-9-]{0,63}',args.label) is None
        or re.fullmatch('[0-9a-f]{64}',args.results_summary_sha256) is None):raise ValueError('Fresh canonical plan label and explicit final-results pin required')
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
        for name in ('prepare_core_publication_v1.py','README_CORE_PUBLICATION.md'):
            raw=read(HERE/name)
            for suffix in ('','.backup','.restore'):put(name+suffix,raw)
        parent_raw=read(HERE.parent/'stabilization_20261005/prepare_stabilization_publication_v4.py')
        if sha(parent_raw)!=PARENT_PROPOSER_SHA or sha(read(FINAL_BUILDER))!=FINAL_BUILDER_SHA:
            raise ValueError('Immutable V4 proposer/current V2 archive-builder pins required')
        for suffix in ('','.backup','.restore'):put('PARENT_PROPOSER.py'+suffix,parent_raw)
        source_raw=read(SOURCE_REVIEW)
        if sha(source_raw)!=SOURCE_REVIEW_SHA:raise ValueError('Approved frozen build29 source inventory changed')
        approved_source=strict(source_raw)
        frozen=approved_source['replacement_pins']
        for name,pin in approved_source['source_pins'].items():
            raw=read(Path(pin['path']))
            if (len(raw),sha(raw))!=(pin['bytes'],pin['sha256']):raise ValueError('Frozen build input changed: '+name)
        for name,pin in frozen.items():
            raw=read(HERE/name)
            if (len(raw),sha(raw))!=(pin['bytes'],pin['sha256']):raise ValueError('Frozen package replacement changed: '+name)
        summary=args.results_summary
        if summary.suffix!='.md' or not summary.resolve(strict=True).is_relative_to(ROOT):
            raise ValueError('Final results must be ordinary repository Markdown')
        summary_raw=read(summary)
        if sha(summary_raw)!=args.results_summary_sha256:raise ValueError('Final aggregate results summary differs from supplied pin')
        summary_member=summary.resolve(strict=True).relative_to(ROOT).as_posix()
        base_raw=read(BASE,1024**2)
        if sha(base_raw)!=BASE_SHA:raise ValueError('Exact immutable approved build28 handoff plan required')
        base=strict(base_raw)
        if base.get('schema')!='just-peachy.reviewed-public-handoff.v1' or base.get('reviewed_publication') is not True:raise ValueError('Prior reviewed plan required')
        sources={row['member']:Path(row['source']) for row in base['files']};old={row['member']:row for row in base['files']}
        if len(old)!=697 or len(old)!=len(base['files']):raise ValueError('Exact 697 unique approved build28 sources required')
        sources[C+'START_HERE.md']=ROOT/(C+'START_HERE_CURRENT.md')
        sources[summary_member]=summary
        for name in args.extra_source:
            rel=PurePosixPath(name)
            if (rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name
                or rel.as_posix()!=name or rel.suffix not in {'.py','.md'}):
                raise ValueError('Explicit additional D code/Markdown member required')
            path=HERE.joinpath(*rel.parts)
            raw=read(path);raw.decode('utf-8')
            sources[path.relative_to(ROOT).as_posix()]=path
        queue=list(SELECTED);chosen=set();referenced_history=[];missing_links=[]
        while queue:
            name=queue.pop()
            canonical=(HERE/name).resolve(strict=True)
            if canonical.parent!=HERE.resolve(strict=True):raise ValueError('Same-parent stabilization dependency required')
            name=canonical.name
            if name in chosen:continue
            if re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*\.(?:py|md)',name) is None:raise ValueError('Explicit flat core source required')
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
        for name in CROSS_SOURCES:sources[L+name]=ROOT/(L+name)
        for name in TRACKED:sources[name]=ROOT/name
        rows=[];total=0;aliases=set();changed=[];snapshots={};backed_inputs={}
        for member,path in sorted(sources.items()):
            rel=PurePosixPath(member)
            if (rel.is_absolute() or '..' in rel.parts or '\\' in member or rel.as_posix()!=member
                or member.casefold() in aliases or path.suffix.lower() not in {'.md','.json','.py','.txt','.toml','.h','.cpp','.c','.sh'}):raise ValueError('Exact unique public source member required')
            aliases.add(member.casefold());relative=path.resolve(strict=True).relative_to(ROOT).as_posix()
            if relative!=member and (member,relative)!=(C+'START_HERE.md',C+'START_HERE_CURRENT.md'):raise ValueError('Only locked StartHere alias permitted: '+member+' -> '+relative)
            raw=read(path);raw.decode('utf-8');total+=len(raw)
            if total>20*1024**2 or len(rows)>=4096:raise ValueError('Original20MiB/4096source bounds')
            row=dict(member=member,source=str(path),bytes=len(raw),sha256=sha(raw));rows.append(row);snapshots[member]=row
            if member not in old or (row['bytes'],row['sha256'])!=(old[member]['bytes'],old[member]['sha256']):
                changed.append(member)
                if relative in backed_inputs:
                    if backed_inputs[relative]!=sha(raw):raise ValueError('Aliased real input changed between archive members')
                else:
                    for prefix in ('source','backup','restore'):put(prefix+'/'+relative,raw)
                    backed_inputs[relative]=sha(raw)
        plan=dict(schema=base['schema'],reviewed_publication=False,
            scope='Build29 core storage/caption/identity repair over immutable build28; final observed outcomes and limitations are in '+summary_member+'. All older evidence retains its original scope.',files=rows)
        plan_raw=encoded(plan)
        for suffix in ('','.backup','.restore'):put('PROPOSED_PLAN_REQUIRES_FINAL_REVIEW.json'+suffix,plan_raw)
        if not set(old)<=set(sources):raise ValueError('Every approved build28 handoff member must remain')
        git_names=sorted(set(TRACKED)|{(HERE/name).relative_to(ROOT).as_posix() for name in chosen}|
            {L+name for name in CROSS_SOURCES}|{summary_member}|
            {(HERE.joinpath(*PurePosixPath(name).parts)).relative_to(ROOT).as_posix() for name in args.extra_source})
        put('GIT_WHITELIST.txt',('\n'.join(git_names)+'\n').encode())
        if any(sha(read(path))!=snapshots[member]['sha256'] for member,path in sources.items()):raise ValueError('Publication source changed after backup')
        result=dict(output=str(out),base_plan_sha256=BASE_SHA,selected_runtime_manifest_sha256=PIN,
            frozen_build29_source_review_sha256=SOURCE_REVIEW_SHA,frozen_replacements=len(frozen),
            frozen_source_inputs=len(approved_source['source_pins']),
            final_archive_builder_sha256=FINAL_BUILDER_SHA,
            results_summary_member=summary_member,results_summary_sha256=args.results_summary_sha256,
            prior_members=len(old),members=len(rows),source_bytes=total,git_publication_members=len(git_names),
            selected_stabilization_files=sorted(chosen),referenced_historical_sources=sorted(set(referenced_history)),
            changed_existing_and_new_members=changed,unresolved_current_links=sorted(set(missing_links)),
            proposed_plan_sha256=sha(plan_raw),reviewed_publication=False,native_action=False,zip_built=False,
            independent_changed_source_restores=True,backed_real_inputs=len(backed_inputs),duplicate_archive_aliases_use_same_exact_restored_input=True,private_media_models_galleries_included=False,
            all_approved_build28_member_paths_preserved=True,
            unchanged_sources_reuse_prior_closed_backups=True,
            directory_reserved_bytes=len(directories)*65536,prepared_allocated_bytes=written)
        put('PLAN_REVIEW.json',encoded(result));put('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),prepared_allocated_bytes=written,source_backups_and_independent_restores=True,native_action=False)))
        print(json.dumps(dict(output=str(out),members=len(rows),source_bytes=total,git_publication_members=len(git_names),unresolved_current_links=result['unresolved_current_links'],reviewed_publication=False,zip_built=False)))
    except BaseException as error:
        put('FAILURE.json',encoded(dict(type=type(error).__name__,message=str(error)[:2048])));raise

if __name__=='__main__':main()
