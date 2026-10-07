"""Prepare an unapproved build31 source plan only; README_CORE_PUBLICATION_V3.md."""
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
PIN='4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
SOURCE_REVIEW=Q/'audit-preparation/caption-package31-f6383c985d4d41e6b065ff9487dd19ad/SOURCE_DIFF_REVIEW.json'
SOURCE_REVIEW_SHA='6894adf19266061a15a71dc103d7317303652d68d58a4e27b74016430caaf4ca'
MIDDLE_SOURCE_REVIEW=Q/'audit-preparation/sidecar-package30-98954655204a43a99b28375e33d3faf6/SOURCE_DIFF_REVIEW.json'
MIDDLE_SOURCE_REVIEW_SHA='337cfff9ac688ee947b66e2920306dbca5c11a72fd230486ad35eec54bfd34c7'
PARENT_SOURCE_REVIEW=Q/'audit-preparation/core-package-v1-98d8679173344e6cb1f97599f489a1b7/SOURCE_DIFF_REVIEW.json'
PARENT_SOURCE_REVIEW_SHA='2f2b7b92fe54c87c5f1713c3cffc2f97420b1fc5d3f7f86566c043348d01549c'
PARENT_PIN='b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569'
PACKAGE=Q/'audit-preparation/caption-package31-f6383c985d4d41e6b065ff9487dd19ad/package'
PACKAGE_CONTENT_SHA='f65029c4d476fd557e073890dacaec218c0c2a6ce877c93a466c50a04e272b8d'
REPLACEMENT_ROOT=HERE/'caption_snapshot_20261006'
MIDDLE_REPLACEMENT_ROOT=HERE/'sqlite_sidecar_race_20261006'
PARENT_PROPOSER_SHA='46f580f1521eba1bab0117ba0f4766a51b0e6c319d64f8c8391a406a6d8f0b5d'
PARENT_REVIEWER_SHA='2ea65d63bd269f51f3ee7a65332e6e647258aade77b5cd03fcc3bd3bd5d49037'
PARENT_README_SHA='ed2220c82a92cb893ae0362c70d3675aa99f2f7a76bbe73408a77f4adc33166e'
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
SELECTED += '''activate_core_desktop_action30.py prepare_core_activation30.py prepare_core_native_validation_v3.py prepare_core_endurance30.py launch_core_full_app_hour30.py stage_c24_endurance_input30.py review_core_full_app_hour.py review_core_full_app_hour30.py README_CORE_BUILD30_HELPERS.md README_CORE_HOUR_REVIEW.md host_core_operations_v6.py README_CORE_OPERATIONS_V6.md inspect_sqlite_guard_failure.py README_SQLITE_GUARD_INSPECTION.md prepare_core_publication_v2.py review_core_publication_v2.py README_CORE_PUBLICATION_V2.md'''.split()
SELECTED += ['host_core_operations_v7.py','README_CORE_OPERATIONS_V7.md']
SELECTED += ['host_core_operations_v8.py','README_CORE_OPERATIONS_V8.md','README_CORE_HOUR_DISPATCH.md']
SELECTED += ['review_hour01_lanes.py','README_HOUR01_LANES.md',
    'host_core_operations_v9.py','README_CORE_OPERATIONS_V9.md',
    'extract_core_job31.py','README_EXTRACT_CORE_JOB31.md',
    'prepare_core_publication_v3.py','review_core_publication_v3.py','README_CORE_PUBLICATION_V3.md']
SUBTREE_SOURCES=tuple('sqlite_sidecar_race_20261006/'+name for name in (
    'storage_support.py','test_sqlite_sidecar_race.py','run_host_sidecar_checks.py',
    'build_sidecar_package30.py','prepare_sidecar_stage30.py',
    'README_SQLITE_SIDECAR_RACE.md','README_SIDECAR_PACKAGE30.md','README_SIDECAR_STAGE30.md',
    'prepare_sidecar_stage30_v2.py','README_SIDECAR_STAGE30_V2.md'))
SUBTREE_SOURCES += tuple('caption_snapshot_20261006/'+name for name in (
    'installed_engine.py','d1_spatial_policy.py','d1_caption_snapshot.py',
    'check_d1_caption_snapshot.py','run_host_snapshot_checks.py',
    'README_D1_CAPTION_SNAPSHOT.md','build_caption_package31.py',
    'README_CAPTION_PACKAGE31.md','ops31/prepare_caption31.py',
    'ops31/README_CAPTION31_OPS.md'))
GUIDE_TARGETS=(C+'MODE_GUIDE.md',C+'BACKEND_COMBINATIONS.md',
    C+'INSTALL_HEALTH_AND_RECOVERY.md',C+'CHATGPT_HANDOFF.md',C+'FINAL_OPERATOR_GUIDE.md',
    L+'README_PIPELINES.md',L+'CORE_REPAIR_PIPELINE_NOTES.md',L+'CORE_REPAIR_TECHNICAL_NOTES.md',
    L+'RAM_RESOURCE_GUIDE.md',L+'pipelines/pyannote_redimnet.md',L+'pipelines/pyannote_titanet.md',
    L+'pipelines/current_delayed.md',L+'pipelines/chunk52_threads2.md')
ENTRY_TARGETS=('DELIVERY_START_HERE.md',C+'START_HERE_CURRENT.md',L+'START_HERE.md')
TRACKED=tuple(dict.fromkeys((*TRACKED,*GUIDE_TARGETS,*ENTRY_TARGETS)))
PRIVATE_PARTS=frozenset(('preserved','drafts','source','backup','restore','runtime-data',
    'models','galleries','recordings','__pycache__','source-backups'))
PRIVATE_PREFIXES=('completion_docs_','entry_review_','audit-','operation-',
    'production-backup-','classic-ui-check-','full-app-hour-','publication-')

def extra_source_path(name):
    rel=PurePosixPath(name)
    if (not name or rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name
            or rel.as_posix()!=name or rel.suffix not in {'.py','.md'}
            or any(part.casefold() in PRIVATE_PARTS or
                   part.casefold().startswith(PRIVATE_PREFIXES) for part in rel.parts)):
        raise ValueError('Explicit public D code/Markdown path required; private/draft trees excluded')
    return HERE.joinpath(*rel.parts)

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

def verify_frozen_sources():
    """Preserve all three immutable source generations and bind actual build31 bytes."""
    reviews=[]
    for path,pin,root,expected_inputs,expected_replacements in (
            (PARENT_SOURCE_REVIEW,PARENT_SOURCE_REVIEW_SHA,HERE,27,24),
            (MIDDLE_SOURCE_REVIEW,MIDDLE_SOURCE_REVIEW_SHA,MIDDLE_REPLACEMENT_ROOT,10,2),
            (SOURCE_REVIEW,SOURCE_REVIEW_SHA,REPLACEMENT_ROOT,13,4)):
        raw=read(path)
        if sha(raw)!=pin:raise ValueError('Root-approved immutable source review changed')
        document=strict(raw)
        if (len(document['source_pins'])!=expected_inputs or
                len(document['replacement_pins'])!=expected_replacements):
            raise ValueError('Exact parent/current source inventory required')
        for name,value in document['source_pins'].items():
            source=read(Path(value['path']))
            if (len(source),sha(source))!=(value['bytes'],value['sha256']):
                raise ValueError('Frozen build source/evidence changed: '+name)
        for name,value in document['replacement_pins'].items():
            source=read(root/name)
            if (len(source),sha(source))!=(value['bytes'],value['sha256']):
                raise ValueError('Frozen runtime replacement changed: '+name)
        reviews.append(document)
    manifest_raw=read(PACKAGE/'PACKAGE_MANIFEST.json')
    if sha(manifest_raw)!=PIN:raise ValueError('Exact immutable build31 manifest required')
    manifest=strict(manifest_raw)
    binding=strict(read(PACKAGE/'BINDING.json'))
    provenance=strict(read(PACKAGE/'REPAIR_PROVENANCE.json'))
    if (manifest.get('target')!=binding.get('target') or
            manifest.get('target')!='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-31' or
            manifest.get('candidate_content_sha256')!=PACKAGE_CONTENT_SHA or
            binding.get('candidate_content_sha256')!=PACKAGE_CONTENT_SHA or
            provenance.get('parent_manifest_sha256')!=PARENT_PIN or
            provenance.get('source_review_sha256')!=SOURCE_REVIEW_SHA):
        raise ValueError('Actual build31 target/content/parent/source binding differs')
    for name,value in reviews[2]['replacement_pins'].items():
        source=read(PACKAGE/name)
        if (len(source),sha(source))!=(value['bytes'],value['sha256']):
            raise ValueError('Actual package replacement differs from frozen current source')
    return reviews

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
        for name in ('prepare_core_publication_v3.py','review_core_publication_v3.py','README_CORE_PUBLICATION_V3.md'):
            raw=read(HERE/name)
            for suffix in ('','.backup','.restore'):put(name+suffix,raw)
        parent_raw=read(HERE/'prepare_core_publication_v2.py')
        if sha(parent_raw)!=PARENT_PROPOSER_SHA or sha(read(FINAL_BUILDER))!=FINAL_BUILDER_SHA:
            raise ValueError('Immutable publicationV2/exact final archive-builder pins required')
        for suffix in ('','.backup','.restore'):put('PARENT_PROPOSER.py'+suffix,parent_raw)
        for name,pin in (('review_core_publication_v2.py',PARENT_REVIEWER_SHA),
                         ('README_CORE_PUBLICATION_V2.md',PARENT_README_SHA)):
            body=read(HERE/name)
            if sha(body)!=pin:raise ValueError('Immutable publicationV2 parent differs: '+name)
            for suffix in ('','.backup','.restore'):put('PARENT_'+name+suffix,body)
        parent_source,middle_source,approved_source=verify_frozen_sources()
        frozen=approved_source['replacement_pins']
        summary=args.results_summary
        if summary.resolve(strict=True)!=(HERE/'CORE_REPAIR_RESULTS.md').resolve(strict=True):
            raise ValueError('Final results must be exact canonical CORE_REPAIR_RESULTS.md')
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
        for name in SUBTREE_SOURCES:
            path=HERE.joinpath(*PurePosixPath(name).parts)
            raw=read(path);raw.decode('utf-8')
            sources[path.relative_to(ROOT).as_posix()]=path
        for name in args.extra_source:
            path=extra_source_path(name)
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
            scope='Build31 minimal canonical identity snapshots and current-revision cache cleanup over immutable build30, preserving all approved697 baseline paths and historical storage/caption/identity sources. Final observed outcomes and limits are in '+summary_member+'. Failed hour01 and older evidence retain their original scope; host checks do not qualify native behavior.',files=rows)
        plan_raw=encoded(plan)
        for suffix in ('','.backup','.restore'):put('PROPOSED_PLAN_REQUIRES_FINAL_REVIEW.json'+suffix,plan_raw)
        if not set(old)<=set(sources):raise ValueError('Every approved build28 handoff member must remain')
        git_names=sorted(set(TRACKED)|{(HERE/name).relative_to(ROOT).as_posix() for name in chosen}|
            {L+name for name in CROSS_SOURCES}|{summary_member}|
            {(HERE.joinpath(*PurePosixPath(name).parts)).relative_to(ROOT).as_posix() for name in SUBTREE_SOURCES}|
            {extra_source_path(name).relative_to(ROOT).as_posix() for name in args.extra_source})
        put('GIT_WHITELIST.txt',('\n'.join(git_names)+'\n').encode())
        if any(sha(read(path))!=snapshots[member]['sha256'] for member,path in sources.items()):raise ValueError('Publication source changed after backup')
        result=dict(output=str(out),base_plan_sha256=BASE_SHA,selected_runtime_manifest_sha256=PIN,
            frozen_build31_source_review_sha256=SOURCE_REVIEW_SHA,frozen_replacements=len(frozen),
            frozen_source_inputs=len(approved_source['source_pins']),
            frozen_middle_build30_source_review_sha256=MIDDLE_SOURCE_REVIEW_SHA,
            frozen_middle_build30_source_inputs=len(middle_source['source_pins']),
            frozen_middle_build30_replacements=len(middle_source['replacement_pins']),
            frozen_parent_build29_source_review_sha256=PARENT_SOURCE_REVIEW_SHA,
            frozen_parent_build29_source_inputs=len(parent_source['source_pins']),
            frozen_parent_build29_replacements=len(parent_source['replacement_pins']),
            immutable_build31_candidate_content_sha256=PACKAGE_CONTENT_SHA,
            selected_explicit_subtree_sources=list(SUBTREE_SOURCES),
            selected_canonical_guides=list(GUIDE_TARGETS),selected_existing_entries=list(ENTRY_TARGETS),
            selected_extra_sources=list(args.extra_source),
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
