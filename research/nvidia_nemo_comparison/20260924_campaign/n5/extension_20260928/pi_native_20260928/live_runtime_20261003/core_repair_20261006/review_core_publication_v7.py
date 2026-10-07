"""Admit an exact final build35 source plan after root review. README_CORE_PUBLICATION_V7.md.

No ZIP, Git, network, native operations, runtime import or private media reads.
Root separately reviews actual native receipts and the final aggregate findings.
"""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import time
import uuid

HERE=Path(__file__).parent
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PROPOSER_SHA='7b7b484a48498447e5301fc45525cd5efa78e0efbfbd077810917ac877b27a16'


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def kernel_api():
    if os.name!='nt':raise RuntimeError('Windows host-only publication review')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    return kernel


def exact_absence(kernel,owner):
    if (owner.get('schema')!='just-peachy.host-registered-owner.v1'
        or owner.get('cpu')!=14 or owner.get('affinity_mask')!=16384
        or any(type(owner.get(key)) is not int or owner[key]<=0 for key in ('pid','creation_filetime'))):
        raise ValueError('Exact prerequisite CPU14/PID/FILETIME registration required')
    kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    ctypes.set_last_error(0)
    handle=kernel.OpenProcess(0x1000,False,owner['pid'])
    if not handle:
        error=ctypes.get_last_error()
        if error!=87:raise ctypes.WinError(error)
        return dict(pid=owner['pid'],creation_filetime=owner['creation_filetime'],state='ABSENT')
    try:
        stamps=[ctypes.c_ulonglong() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in stamps)):
            raise ctypes.WinError(ctypes.get_last_error())
        if stamps[0].value!=owner['creation_filetime']:
            return dict(pid=owner['pid'],creation_filetime=owner['creation_filetime'],state='PID_REUSED_DIFFERENT_FILETIME')
        code=ctypes.c_ulong()
        kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if code.value==259:raise ValueError('Exact proposal owner remains active')
        return dict(pid=owner['pid'],creation_filetime=owner['creation_filetime'],state='EXACT_PROCESS_EXITED',exit_code=code.value)
    finally:kernel.CloseHandle(handle)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal',type=Path,required=True)
    parser.add_argument('--proposal-sha256',required=True)
    parser.add_argument('--results-summary-sha256',required=True)
    parser.add_argument('--label',required=True)
    parser.add_argument('--root-reviewed',action='store_true',help='Only after root reviews source/privacy/links and actual native outcomes/closures')
    args=parser.parse_args()
    if (not args.root_reviewed or re.fullmatch('[a-z][a-z0-9-]{0,63}',args.label) is None
        or any(re.fullmatch('[0-9a-f]{64}',value) is None for value in
            (args.proposal_sha256,args.results_summary_sha256))):
        raise ValueError('Deliberate final root review and exact proposal/results pins required')
    kernel=kernel_api();handle=kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root=Q/'audit-preparation'/(args.label+'-'+uuid.uuid4().hex);root.mkdir(exist_ok=False)
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    raw_owner=encoded(owner)
    with (root/'REGISTERED_OWNER.json').open('xb') as stream:
        if stream.write(raw_owner)!=len(raw_owner):raise OSError('Short early owner write')
        stream.flush();os.fsync(stream.fileno())
    if (root/'REGISTERED_OWNER.json').read_bytes()!=raw_owner:raise OSError('Early owner readback differs')
    began=time.monotonic();used=65536+len(raw_owner)
    def put(name,raw):
        nonlocal used
        if re.fullmatch('[A-Za-z0-9_.-]+',name) is None:raise ValueError('Flat owned metadata output required')
        if used+len(raw)>16*1024**2 or time.monotonic()-began>600:
            raise OSError('Original16MiB/600s final review allocation')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+16*1024**2:raise OSError('Original host storage floor')
        with (root/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short final review write')
            stream.flush();os.fsync(stream.fileno())
        used+=len(raw)
        if (root/name).read_bytes()!=raw:raise OSError('Independent review readback differs')
    def triple(name,raw):
        for suffix in ('','.backup','.restore'):put(name+suffix,raw)
    put('HOST_SCOPE.json',encoded(dict(maximum_bytes=16*1024**2,maximum_seconds=600,
        directory_reserved_bytes=65536,native_action=False,zip_built=False)))
    try:
        proposer_path=HERE/'prepare_core_publication_v7.py';proposer_raw=proposer_path.read_bytes()
        if sha(proposer_raw)!=PROPOSER_SHA:raise ValueError('Exact reviewed proposer source required')
        spec=importlib.util.spec_from_file_location('core_publication_review_pure_definitions',proposer_path)
        proposer=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proposer)  # Definitions only, after durable registration.
        read,strict=proposer.read,proposer.strict
        for name in ('review_core_publication_v7.py','README_CORE_PUBLICATION_V7.md','prepare_core_publication_v7.py'):
            triple(name,read(HERE/name))
        proposal=args.proposal
        if (proposal.name!='PROPOSED_PLAN_REQUIRES_FINAL_REVIEW.json'
            or proposal.parent.parent!=Q/'audit-preparation'
            or proposal.resolve(strict=True)!=proposal):raise ValueError('Canonical closed core proposal required')
        raw=read(proposal,1024**2)
        if sha(raw)!=args.proposal_sha256:raise ValueError('Exact root-reviewed proposal pin differs')
        plan=strict(raw);review=strict(read(proposal.parent/'PLAN_REVIEW.json'))
        closed=strict(read(proposal.parent/'SOURCE_CLOSED.json'))
        prerequisite=strict(read(proposal.parent/'REGISTERED_OWNER.json'))
        closure=exact_absence(kernel,prerequisite)
        if (plan.get('schema')!='just-peachy.reviewed-public-handoff.v1'
            or plan.get('reviewed_publication') is not False
            or review.get('proposed_plan_sha256')!=args.proposal_sha256
            or review.get('base_plan_sha256')!=proposer.BASE_SHA
            or review.get('current_build')!=35
            or review.get('frozen_build31_manifest_sha256')!=proposer.PIN
            or review.get('frozen_build31_source_review_sha256')!=proposer.SOURCE_REVIEW_SHA
            or review.get('frozen_replacements')!=4
            or review.get('frozen_source_inputs')!=13
            or review.get('frozen_middle_build30_source_review_sha256')!=proposer.MIDDLE_SOURCE_REVIEW_SHA
            or review.get('frozen_middle_build30_source_inputs')!=10
            or review.get('frozen_middle_build30_replacements')!=2
            or review.get('frozen_parent_build29_source_review_sha256')!=proposer.PARENT_SOURCE_REVIEW_SHA
            or review.get('frozen_parent_build29_source_inputs')!=27
            or review.get('frozen_parent_build29_replacements')!=24
            or review.get('immutable_build31_candidate_content_sha256')!=proposer.PACKAGE_CONTENT_SHA
            or review.get('frozen_build33_manifest_sha256')!=proposer.HISTORICAL33_PIN
            or review.get('frozen_build33_source_review_sha256')!=proposer.HISTORICAL33_SOURCE_REVIEW_SHA
            or review.get('frozen_build33_source_inputs')!=30
            or review.get('frozen_build33_replacements')!=7
            or review.get('frozen_build34_manifest_sha256')!=proposer.HISTORICAL34_PINS['manifest']
            or review.get('frozen_build34_source_review_sha256')!=proposer.HISTORICAL34_PINS['source_review']
            or review.get('frozen_build34_source_inputs')!=41
            or review.get('frozen_build34_replacements')!=15
            or review.get('selected_named_control_sources')!=list(proposer.NAMED_CONTROL_PINS)
            or review.get('selected_named_shell_sources')!=list(proposer.NAMED_SHELL_SOURCES)
            or review.get('selected_explicit_subtree_sources')!=list(proposer.SUBTREE_SOURCES)
            or review.get('selected_canonical_guides')!=list(proposer.GUIDE_TARGETS)
            or review.get('selected_existing_entries')!=list(proposer.ENTRY_TARGETS)
            or review.get('final_archive_builder_sha256')!=proposer.FINAL_BUILDER_SHA
            or review.get('final_archive_adapter_sha256')!=proposer.HANDOFF_ADAPTER_SHA
            or review.get('prior_members')!=697
            or review.get('all_approved_build28_member_paths_preserved') is not True
            or review.get('independent_changed_source_restores') is not True
            or review.get('unresolved_current_links')!=[]
            or review.get('results_summary_sha256')!=args.results_summary_sha256
            or review.get('reviewed_publication') is not False
            or review.get('native_action') is not False or review.get('zip_built') is not False
            or closed.get('source_backups_and_independent_restores') is not True
            or closed.get('native_action') is not False
            or type(closed.get('prepared_allocated_bytes')) is not int
            or not 0<closed['prepared_allocated_bytes']<=16*1024**2):
            raise ValueError('Closed current35 proposal/historical-source/link/restoration review required')
        current_value=review.get('current_source_map')
        if type(current_value) is not dict:raise ValueError('Actual current35 source-map identity required')
        current_args=proposer.current_arguments(current_value.get('arguments'))
        actual_current=proposer.verify_current(current_args)
        proposer.verify_named_controls()
        current_members=[(proposer.CURRENT_MIRROR/row['path']).relative_to(proposer.ROOT).as_posix()
            for row in actual_current['files']]
        map_member=(proposer.CURRENT_MIRROR/'SOURCE_MAP.md').relative_to(proposer.ROOT).as_posix()
        current_members.append(map_member)
        if (current_value!=actual_current or review.get('current_source_map_sha256')!=sha(encoded(actual_current))
                or review.get('selected_runtime_manifest_sha256')!=current_args.current_manifest_sha256
                or review.get('current_source_map_member')!=map_member
                or review.get('current_source_mirror_members')!=current_members
                or review.get('source_mirror_independent_readbacks') is not True
                or review.get('source_mirror_maximum_bytes')!=8*1024**2):
            raise ValueError('Current35 mirror/package/member identity differs')
        for item in actual_current['files']:
            body=read(proposer.CURRENT_MIRROR/item['path'])
            if (len(body),sha(body))!=(item['bytes'],item['sha256']):
                raise ValueError('Current35 source mirror differs: '+item['path'])
        if read(proposer.CURRENT_MIRROR/'SOURCE_MAP.md')!=proposer.source_map_bytes(actual_current):
            raise ValueError('Public current35 source-map provenance differs')
        build_owner=strict(read(current_args.current_package.parent/'REGISTERED_OWNER.json'))
        build_closure=exact_absence(kernel,build_owner)
        base_raw=read(proposer.BASE,1024**2)
        if sha(base_raw)!=proposer.BASE_SHA:raise ValueError('Immutable697-source build28 baseline differs')
        base=strict(base_raw);old={row['member']:row for row in base['files']}
        rows=plan['files'];current={row['member']:row for row in rows}
        if (len(old)!=697 or len(current)!=len(rows) or not set(old)<=set(current)
            or not 1<=len(rows)<=4096):raise ValueError('Lost/duplicate/unbounded handoff members')
        whitelist=read(proposal.parent/'GIT_WHITELIST.txt').decode('utf-8').splitlines()
        if len(whitelist)!=len(set(whitelist)) or any(name not in current for name in whitelist):
            raise ValueError('Explicit public member whitelist required')
        required=set(proposer.TRACKED)|{
            (proposer.HERE/name).relative_to(proposer.ROOT).as_posix()
            for name in (*proposer.SELECTED,*proposer.SUBTREE_SOURCES,*proposer.NAMED_SHELL_SOURCES,
                *proposer.NAMED_CONTROL_PINS)}|{
            proposer.L+name for name in proposer.CROSS_SOURCES}|{review['results_summary_member']}|set(current_members)
        if not required<=set(current) or not required<=set(whitelist):
            raise ValueError('Explicit current35 mirror/helpers,13guides and3entry whitelist incomplete')
        selected=review.get('selected_stabilization_files')
        extras=review.get('selected_extra_sources')
        if (type(selected) is not list or type(extras) is not list
            or len(selected)!=len(set(selected)) or len(extras)!=len(set(extras))
            or not set(proposer.SELECTED)<=set(selected)
            or any(type(name) is not str or
                   re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*\.(?:py|md)',name) is None
                   for name in selected)):
            raise ValueError('Exact named public source selection required')
        expected_whitelist=set(proposer.TRACKED)|{
            (proposer.HERE/name).relative_to(proposer.ROOT).as_posix() for name in selected}|{
            (proposer.HERE.joinpath(*PurePosixPath(name).parts)).relative_to(proposer.ROOT).as_posix()
            for name in proposer.SUBTREE_SOURCES}|{
            proposer.extra_source_path(name).relative_to(proposer.ROOT).as_posix() for name in extras}|{
            proposer.L+name for name in proposer.CROSS_SOURCES}|{review['results_summary_member']}|set(current_members)
        expected_whitelist|={(proposer.HERE/name).relative_to(proposer.ROOT).as_posix()
            for name in proposer.NAMED_SHELL_SOURCES}
        expected_whitelist|={(proposer.HERE/name).relative_to(proposer.ROOT).as_posix()
            for name in proposer.NAMED_CONTROL_PINS}
        if set(whitelist)!=expected_whitelist or not (set(current)-set(old))<=set(whitelist):
            raise ValueError('New members must follow the exact explicit public whitelist')
        aliases=set();total=0;changed=[];compiled=[];links=[];real_inputs={}
        for row in rows:
            member=row['member'];relative=PurePosixPath(member);path=Path(row['source'])
            if (set(row)!={'member','source','bytes','sha256'} or relative.is_absolute()
                or '..' in relative.parts or '\\' in member or ':' in member
                or relative.as_posix()!=member or member.casefold() in aliases
                or (path.suffix.lower() not in {'.md','.json','.py','.txt','.toml','.h','.cpp','.c','.sh'}
                    and member not in {(proposer.HERE/name).relative_to(proposer.ROOT).as_posix()
                        for name in proposer.NAMED_SHELL_SOURCES})):
                raise ValueError('Exact unique ordinary public source row required')
            aliases.add(member.casefold())
            canonical=path.resolve(strict=True).relative_to(proposer.ROOT).as_posix()
            if canonical!=member and (member,canonical)!=(proposer.C+'START_HERE.md',proposer.C+'START_HERE_CURRENT.md'):
                raise ValueError('Only the locked current StartHere archive alias is allowed')
            content=read(path);text=content.decode('utf-8');total+=len(content)
            if path.suffix.lower()=='.ps1' and sha(content)!=proposer.NAMED_SHELL_PINS[path.name]:
                raise ValueError('Only the exact reviewed generic verifier is public shell source')
            if member in {(proposer.HERE/name).relative_to(proposer.ROOT).as_posix()
                    for name in proposer.NAMED_CONTROL_PINS} and sha(content)!=proposer.NAMED_CONTROL_PINS[path.name]:
                raise ValueError('Only the exact root-selected stage certificate is public control source')
            if (type(row['bytes']) is not int or len(content)!=row['bytes'] or sha(content)!=row['sha256']
                or total>20*1024**2):raise ValueError('Current final source bytes/hash/extent differ')
            different=member not in old or (row['bytes'],row['sha256'])!=(old[member]['bytes'],old[member]['sha256'])
            if different:
                changed.append(member)
                if canonical not in real_inputs:
                    for prefix in ('source','backup','restore'):
                        if read(proposal.parent/prefix/canonical)!=content:
                            raise ValueError('Changed-source independent restore differs: '+member)
                if path.suffix=='.py':compile(text,str(path),'exec');compiled.append(member)
                if path.suffix=='.md':
                    for target in re.findall(r'\]\(([^)]+)\)',text):
                        target=target.split('#',1)[0].strip('<>')
                        if not target or ':' in target or target.startswith('/'):continue
                        linked=(path.parent/target).resolve(strict=True)
                        if not linked.is_file():raise ValueError('Changed README target is not a file')
                        if linked.is_relative_to(proposer.ROOT) and linked.relative_to(proposer.ROOT).as_posix() not in current:
                            raise ValueError('Changed README linked file absent from public plan')
                        links.append(member+' -> '+target)
            if canonical in real_inputs and real_inputs[canonical]!=row['sha256']:
                raise ValueError('Aliased real input changed during review')
            real_inputs[canonical]=row['sha256']
        summary_member=review['results_summary_member']
        if (summary_member!=(proposer.HERE/'CORE_REPAIR_RESULTS.md').relative_to(proposer.ROOT).as_posix()
            or summary_member not in current or current[summary_member]['sha256']!=args.results_summary_sha256):
            raise ValueError('Final aggregate outcomes/limits summary is not the admitted public member')
        parent_source,middle_source,current_source=proposer.verify_frozen_sources()
        historical33=proposer.verify_historical33()
        historical34=proposer.verify_historical34()
        for row in rows:
            if sha(read(Path(row['source'])))!=row['sha256']:raise ValueError('Source changed after final review')
        if sha(read(proposer.FINAL_BUILDER))!=proposer.FINAL_BUILDER_SHA:
            raise ValueError('Current exact V2 final archive builder changed')
        if sha(read(proposer.HANDOFF_ADAPTER))!=proposer.HANDOFF_ADAPTER_SHA:
            raise ValueError('Exact verifier-only final archive adapter changed')
        final=dict(plan,reviewed_publication=True);final_raw=encoded(final)
        triple('PROPOSED_PLAN.json',raw);triple('REVIEWED_PLAN.json',final_raw)
        triple('FINAL_RESULTS_SUMMARY.md',read(Path(current[summary_member]['source'])))
        put('GIT_WHITELIST.txt',('\n'.join(sorted(whitelist))+'\n').encode())
        receipt=dict(status='FINAL_CORE_SOURCE_PLAN_REVIEW_PASSED',reviewed_plan_sha256=sha(final_raw),
            proposal_sha256=args.proposal_sha256,results_summary_member=summary_member,
            results_summary_sha256=args.results_summary_sha256,
            selected_runtime_manifest_sha256=current_args.current_manifest_sha256,
            current_build=35,current_source_map_sha256=sha(encoded(actual_current)),
            current_source_map_member=map_member,current_source_mirror_members=current_members,
            current_candidate_content_sha256=current_args.current_content_sha256,
            current_source_review_sha256=current_args.current_source_review_sha256,
            separate_deployment_archive_sha256=current_args.current_archive_sha256,
            complete_deployment_bundle_included=False,
            current_build_independent_os_closure=build_closure,
            frozen_build31_manifest_sha256=proposer.PIN,
            frozen_build31_source_review_sha256=proposer.SOURCE_REVIEW_SHA,
            frozen_middle_build30_source_review_sha256=proposer.MIDDLE_SOURCE_REVIEW_SHA,
            frozen_parent_build29_source_review_sha256=proposer.PARENT_SOURCE_REVIEW_SHA,
            frozen_build31_inputs=len(current_source['source_pins']),
            frozen_middle_build30_inputs=len(middle_source['source_pins']),
            frozen_parent_build29_inputs=len(parent_source['source_pins']),
            frozen_build33_manifest_sha256=proposer.HISTORICAL33_PIN,
            frozen_build33_source_review_sha256=proposer.HISTORICAL33_SOURCE_REVIEW_SHA,
            frozen_build33_inputs=len(historical33['source_pins']),
            frozen_build34_manifest_sha256=proposer.HISTORICAL34_PINS['manifest'],
            frozen_build34_source_review_sha256=proposer.HISTORICAL34_PINS['source_review'],
            frozen_build34_inputs=len(historical34['source_pins']),
            selected_named_control_sources=list(proposer.NAMED_CONTROL_PINS),
            selected_named_shell_sources=list(proposer.NAMED_SHELL_SOURCES),
            explicit_build31_subtree_sources=list(proposer.SUBTREE_SOURCES),
            canonical_guides=list(proposer.GUIDE_TARGETS),existing_entries=list(proposer.ENTRY_TARGETS),
            prior_members_preserved=697,members=len(rows),source_bytes=total,changed_members=changed,
            compiled_changed_python=compiled,checked_changed_readme_links=links,
            prerequisite_exact_host_closure=closure,root_source_privacy_and_actual_outcome_review_supplied=True,
            native_qualification_not_inferred_from_host_checks=True,final_archive_builder_sha256=proposer.FINAL_BUILDER_SHA,
            final_archive_adapter_sha256=proposer.HANDOFF_ADAPTER_SHA,
            prepared_allocated_bytes=used,native_action=False,zip_built=False)
        put('RESULT.json',encoded(receipt))
        put('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),prepared_allocated_bytes=used,
            source_backups_and_independent_restores=True,native_action=False,zip_built=False)))
        print(encoded(dict(output=str(root),reviewed_plan=str(root/'REVIEWED_PLAN.json'),
            reviewed_plan_sha256=sha(final_raw),members=len(rows),native_action=False,zip_built=False)).decode())
    except BaseException as error:
        put('FAILURE.json',encoded(dict(type=type(error).__name__,message=str(error)[:2048])))
        raise


if __name__=='__main__':main()
