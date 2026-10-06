"""Review the current source handoff after real evidence; README_FINAL_PLAN_REVIEW.md."""
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
BASE=Q/'audit-preparation/final-build26-approved-plan-a99d594386ea48e28b08ca73efdbda2c/REVIEWED_PLAN.json'
BASE_SHA='7dcf9975ad82e1ff57480a56beef18a6de9564ef316394ea58e988f9e74c6f9e'
PROPOSER_SHA='5843e4c20871bd3149bc7508be6999c83e066a1be5375aa08b6f7c98f65abb58'
PIN='e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b'
BOOT='31ead85c-17cf-49c3-909a-8f2e1108a151'
ACTIVE_DESKTOP_SHA='8c917153c58c57d73d8ce0d0e5662b42b3f7d698de0cee4189b844f8cfc70ac0'
PREPARER_OWNER=Q/'audit-preparation/activation28-payload-7b12325f3aa64e9f8d09e9600d9b00b3/REGISTERED_OWNER.json'
C='research/nvidia_nemo_comparison/20260924_campaign/n5/completion_20261001/'
APPEND=('activate_full_desktop_action_v5.py','README_STABILIZATION_ACTIVATION_V5.md',
    'prepare_stabilization_activation28_v2.py','README_PREPARE_ACTIVATION28_V2.md',
    'review_stabilization_activation28.py','README_REVIEW_ACTIVATION28.md',
    'review_final_stabilization_plan_v1.py','README_FINAL_PLAN_REVIEW.md')

def enc(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
def read(path,maximum=2*1024**2):
    before=path.lstat();resolved=path.resolve(strict=True)
    if (path.is_symlink() or any(p.is_symlink() for p in path.parents) or not stat.S_ISREG(before.st_mode)
        or before.st_nlink!=1 or before.st_size>maximum
        or os.path.normcase(str(path.absolute()))!=os.path.normcase(str(resolved))):raise ValueError('Canonical bounded ordinary input required: '+str(path))
    raw=path.read_bytes();after=path.stat()
    identity=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns)
    if identity(before)!=identity(after) or len(raw)!=before.st_size:raise ValueError('Input changed during read')
    return raw
def exact_host_absence(owner):
    if (owner.get('schema')!='just-peachy.host-registered-owner.v1' or owner.get('cpu')!=14 or owner.get('affinity_mask')!=16384
        or any(type(owner.get(k)) is not int or owner[k]<=0 for k in ('pid','creation_filetime'))):raise ValueError('Exact CPU14/Filetime owner required')
    _k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];_k.OpenProcess.restype=ctypes.c_void_p
    _k.CloseHandle.argtypes=[ctypes.c_void_p];ctypes.set_last_error(0)
    handle=_k.OpenProcess(0x1000,False,owner['pid'])
    if not handle:
        error=ctypes.get_last_error()
        if error!=87:raise ctypes.WinError(error)
        return dict(pid=owner['pid'],creation_filetime=owner['creation_filetime'],state='ABSENT')
    try:
        times=[ctypes.c_ulonglong() for _ in range(4)]
        if not _k.GetProcessTimes(handle,*(ctypes.byref(v) for v in times)):raise ctypes.WinError(ctypes.get_last_error())
        state='PID_REUSED_DIFFERENT_FILETIME'
        if times[0].value==owner['creation_filetime']:
            code=ctypes.c_ulong();_k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
            if not _k.GetExitCodeProcess(handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
            if code.value==259:raise ValueError('Exact prerequisite host process remains active')
            state='EXACT_PROCESS_EXITED'
        return dict(pid=owner['pid'],creation_filetime=owner['creation_filetime'],state=state)
    finally:_k.CloseHandle(handle)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal',type=Path,required=True)
    parser.add_argument('--activation-review',type=Path,required=True)
    parser.add_argument('--native-check32',type=Path,required=True)
    parser.add_argument('--native-check33',type=Path,required=True)
    parser.add_argument('--label',required=True)
    parser.add_argument('--root-reviewed',action='store_true',help='Root supplies only after reviewing actual evidence and final source/docs')
    args=parser.parse_args()
    if not args.root_reviewed or re.fullmatch('[a-z][a-z0-9-]{0,63}',args.label) is None:raise ValueError('Deliberate final root review and fresh label required')
    times=[ctypes.c_ulonglong() for _ in range(4)]
    _k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not _k.GetProcessTimes(_h,*(ctypes.byref(v) for v in times)):raise ctypes.WinError(ctypes.get_last_error())
    out=Q/'audit-preparation'/(args.label+'-'+uuid.uuid4().hex);out.mkdir()
    started=time.monotonic();used=65536
    def guard(extra=0):
        if used+extra>16*1024**2 or time.monotonic()-started>600:raise OSError('Original16MiB/600s final plan review scope')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+16*1024**2:raise OSError('Original host storage floor')
    def put(name,raw):
        nonlocal used
        if re.fullmatch('[A-Za-z0-9_.-]+',name) is None:raise ValueError('Flat owned review output required')
        guard(len(raw))
        with (out/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short review output write')
            stream.flush();os.fsync(stream.fileno())
        used+=len(raw)
        if read(out/name,16*1024**2)!=raw:raise OSError('Independent review readback differs')
    def triple(name,raw):
        for suffix in ('','.backup','.restore'):put(name+suffix,raw)
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,
        creation_filetime=times[0].value,create_time=(times[0].value-116444736000000000)/10000000)
    put('REGISTERED_OWNER.json',enc(owner));put('HOST_SCOPE.json',enc(dict(maximum_bytes=16*1024**2,maximum_seconds=600,directory_reserved_bytes=65536,native_action=False,zip_built=False)))
    try:
        for name in APPEND:
            triple(name,read(HERE/name))
        base_raw=read(BASE,1024**2)
        if sha(base_raw)!=BASE_SHA:raise ValueError('Immutable approved643-source plan changed')
        base=strict(base_raw);old={row['member']:row for row in base['files']}
        if (base.get('schema')!='just-peachy.reviewed-public-handoff.v1' or base.get('reviewed_publication') is not True
            or len(old)!=643 or len(base['files'])!=643):raise ValueError('Exact prior reviewed member denominator required')
        triple('PRIOR_APPROVED_PLAN.json',base_raw)
        proposal=args.proposal
        if proposal.name!='PROPOSED_PLAN_REQUIRES_FINAL_REVIEW.json' or proposal.parent.parent!=Q/'audit-preparation':raise ValueError('Canonical new V4 proposal required')
        proposer=read(HERE/'prepare_stabilization_publication_v4.py')
        if sha(proposer)!=PROPOSER_SHA:raise ValueError('Frozen V4 proposer differs')
        triple('PROPOSER_SOURCE.py',proposer)
        plan_raw=read(proposal,2*1024**2);plan=strict(plan_raw)
        plan_review_raw=read(proposal.parent/'PLAN_REVIEW.json');plan_review=strict(plan_review_raw)
        closed_raw=read(proposal.parent/'SOURCE_CLOSED.json');closed=strict(closed_raw)
        if (plan.get('schema')!=base['schema'] or plan.get('reviewed_publication') is not False
            or plan_review.get('proposed_plan_sha256')!=sha(plan_raw) or plan_review.get('selected_runtime_manifest_sha256')!=PIN
            or plan_review.get('base_plan_sha256')!=BASE_SHA or plan_review.get('prior_members')!=643
            or plan_review.get('all_approved_build26_member_paths_preserved') is not True
            or plan_review.get('independent_changed_source_restores') is not True
            or plan_review.get('unresolved_current_links')!=[]
            or closed.get('source_backups_and_independent_restores') is not True
            or type(closed.get('prepared_allocated_bytes')) is not int or not 0<closed['prepared_allocated_bytes']<=16*1024**2):raise ValueError('Closed current proposal/restoration/link review required')
        for name,raw in (('PROPOSAL.json',plan_raw),('PROPOSAL_REVIEW.json',plan_review_raw),('PROPOSAL_CLOSED.json',closed_raw)):triple(name,raw)
        activation_raw=read(args.activation_review);activation=strict(activation_raw)
        if (args.activation_review.name!='RESULT.json' or not args.activation_review.is_relative_to(Q/'audit-preparation')
            or activation.get('status')!='ACTUAL_DESKTOP_ACTIVATION_PC_BYTE_READBACK_PASSED'
            or activation.get('package_manifest_sha256')!=PIN or activation.get('active_sha256')!=ACTIVE_DESKTOP_SHA
            or activation.get('independent_pc_before_restore_readbacks') is not True
            or activation.get('action_source_unchanged') is not True or activation.get('native_action') is not False):raise ValueError('Actual closed activation28 PC byte review required')
        activation_closed=strict(read(args.activation_review.parent/'SOURCE_CLOSED.json'))
        if activation_closed.get('source_backups_and_independent_restores') is not True:raise ValueError('Activation PC review must be closed')
        host_closures=[]
        for path,pid,filetime in ((PREPARER_OWNER,38376,134357687920273852),(args.activation_review.parent/'REGISTERED_OWNER.json',55344,134357688528427757)):
            owner_raw=read(path);registered=strict(owner_raw)
            if (registered.get('pid'),registered.get('creation_filetime'))!=(pid,filetime):raise ValueError('Exact actual prerequisite host owner differs')
            host_closures.append(exact_host_absence(registered));triple('ACTUAL_HOST_OWNER_'+str(pid)+'.json',owner_raw)
        native_activation_path=Path(activation['native_dispatch'])
        if native_activation_path!=Q/'operation-stabilization-desktop28-01/dispatch/RESULT.json':raise ValueError('Actual activation28 dispatcher required')
        native_activation_raw=read(native_activation_path);native_activation=strict(native_activation_raw);a=native_activation['action_result']
        utility=native_activation.get('utility_owner')
        if (native_activation.get('boot_id')!=BOOT or native_activation.get('utility_pid_absent_after_ssh') is not True
            or type(utility) is not dict or set(utility)!={'pid','start_ticks','boot_id'} or utility.get('boot_id')!=BOOT
            or any(type(utility.get(k)) is not int or utility[k]<=0 for k in ('pid','start_ticks'))
            or a.get('status')!='CLASSIC_SHORTCUT_ACTIVATED' or a.get('package_manifest_sha256')!=PIN
            or a.get('desktop_sha256')!=ACTIVE_DESKTOP_SHA or a.get('boot_id')!=BOOT
            or a.get('application_started') is not False
            or any(a.get(k) is not True for k in ('capture_off','login_autostart_disabled','rollback_package_preserved','recordings_and_galleries_unchanged','independent_before_restore_readbacks'))):raise ValueError('Actual same-boot activation and exact utility closure differ')
        for suffix in ('','.backup','.restore'):
            if read(args.activation_review.parent/('ACTUAL_ACTIVATION_DISPATCH.json'+suffix))!=native_activation_raw:raise ValueError('Independent activation dispatcher copies differ')
        triple('ACTUAL_ACTIVATION_PC_REVIEW.json',activation_raw);triple('ACTUAL_ACTIVATION_NATIVE_RESULT.json',native_activation_raw)
        proof_pins={}
        for number,path,diarizer in (('32',args.native_check32,'pyannote'),('33',args.native_check33,'nemotron')):
            if path!=Q/('classic-ui-check-'+number+'-finalized-monitor-01/closed-output/NATIVE_CHECK_V2.json'):raise ValueError('Exact independently finalized native proof required')
            raw=read(path);proof=strict(raw)
            if (proof.get('status')!='PASS' or proof.get('boot_id')!=BOOT or proof.get('package_manifest_sha256')!=PIN
                or any(proof.get(k) is not True for k in ('actual_portrait_ui','capture_function_passed','workers_closed','main_exact_owner_gone','unit_recursively_empty','independent_native_finalize'))
                or proof['actual_processing_evidence']['selection'].get('diarizer')!=diarizer):raise ValueError('Current independently finalized native functional proof differs')
            triple('ACTUAL_FINALIZED_CHECK'+number+'.json',raw);proof_pins[number]=sha(raw)
        rows={row['member']:dict(row) for row in plan['files']}
        if len(rows)!=len(plan['files']) or not set(old)<=set(rows):raise ValueError('Duplicate or lost prior handoff member')
        whitelist=read(proposal.parent/'GIT_WHITELIST.txt').decode('utf-8').splitlines()
        triple('PROPOSAL_GIT_WHITELIST.txt',('\n'.join(whitelist)+'\n').encode())
        added=[]
        for name in APPEND:
            path=HERE/name;member=path.relative_to(ROOT).as_posix();raw=read(path)
            row=dict(member=member,source=str(path),bytes=len(raw),sha256=sha(raw))
            if member in rows and rows[member]!=row:raise ValueError('Appended source already has different proposal pin')
            if member not in rows:rows[member]=row;added.append(member)
            if member not in whitelist:whitelist.append(member)
        aliases=set();total=0;changed=[];compiled=[];checked_links=[];real_inputs={}
        for member,row in sorted(rows.items()):
            guard()
            if type(row) is not dict or set(row)!={'member','source','bytes','sha256'}:raise ValueError('Exact public row shape required')
            rel=PurePosixPath(member);path=Path(row['source'])
            if (rel.is_absolute() or rel.as_posix()!=member or '..' in rel.parts or '\\' in member
                or member.casefold() in aliases or path.suffix.lower() not in {'.md','.json','.py','.txt','.toml','.h','.cpp','.c','.sh'}):raise ValueError('Bounded unique source-only member required')
            aliases.add(member.casefold());relative=path.resolve(strict=True).relative_to(ROOT).as_posix()
            if relative!=member and (member,relative)!=(C+'START_HERE.md',C+'START_HERE_CURRENT.md'):raise ValueError('Only locked current StartHere alias allowed')
            raw=read(path);text=raw.decode('utf-8');total+=len(raw)
            if type(row['bytes']) is not int or row['bytes']!=len(raw) or row['sha256']!=sha(raw):raise ValueError('Current source differs from reviewed proposal: '+member)
            if total>20*1024**2 or len(rows)>4096:raise ValueError('Original20MiB/4096 public-source bounds')
            different=member not in old or (row['bytes'],row['sha256'])!=(old[member]['bytes'],old[member]['sha256'])
            if different:
                changed.append(member)
                if member not in added and relative not in real_inputs:
                    for prefix in ('source','backup','restore'):
                        if read(proposal.parent/prefix/relative)!=raw:raise ValueError('V4 independent changed-source restore differs: '+member)
                if path.suffix=='.py':compile(text,str(path),'exec');compiled.append(member)
                if path.suffix=='.md':
                    for target in re.findall(r'\]\(([^)]+)\)',text):
                        target=target.split('#',1)[0].strip('<>')
                        if not target or ':' in target or target.startswith('/'):continue
                        candidate=(path.parent/target).resolve(strict=True)
                        if not candidate.is_file():raise ValueError('Changed README link is not a file: '+member+' -> '+target)
                        if candidate.is_relative_to(ROOT):
                            linked=candidate.relative_to(ROOT).as_posix()
                            if linked not in rows:raise ValueError('Changed README links missing public member: '+linked)
                        checked_links.append(member+' -> '+target)
                if path.suffix=='.py':
                    for name in set(re.findall(r'\b(README[A-Za-z0-9_.-]*\.md)\b',text)):
                        target=path.parent/name
                        if target.is_file() and target.relative_to(ROOT).as_posix() not in rows:raise ValueError('Changed code README absent from handoff: '+str(target))
            if relative in real_inputs and real_inputs[relative]!=row['sha256']:raise ValueError('Alias source changed during review')
            real_inputs[relative]=row['sha256']
        for member in whitelist:
            if member not in rows:raise ValueError('Git whitelist is not an explicit reviewed public member')
        final=dict(schema=base['schema'],reviewed_publication=True,
            scope='Build28 current-boot first-Start/manual-listening repair and actual desktop activation; short Pyannote and Delayed functional evidence, retained prior scopes; no new sustained-real-time or speech-quality qualification.',
            files=[rows[m] for m in sorted(rows)])
        for member,row in rows.items():
            if sha(read(Path(row['source'])))!=row['sha256']:raise ValueError('Source changed after compile/link review: '+member)
        final_raw=enc(final);triple('REVIEWED_PLAN.json',final_raw)
        put('GIT_WHITELIST.txt',('\n'.join(sorted(set(whitelist)))+'\n').encode())
        summary=dict(status='FINAL_SOURCE_PLAN_REVIEW_PASSED',output=str(out),reviewed_plan_sha256=sha(final_raw),proposal_sha256=sha(plan_raw),
            members=len(rows),prior_members_preserved=643,source_bytes=total,appended_members=added,compiled_changed_python=compiled,
            checked_changed_readme_links=checked_links,changed_members=changed,actual_activation_review_sha256=sha(activation_raw),native_proof_sha256=proof_pins,prerequisite_exact_host_closures=host_closures,
            root_review_deliberately_supplied=True,unchanged_prior_sources_reuse_closed_backups=True,v4_changed_source_restores_reused=True,
            prepared_allocated_bytes=used,native_action=False,zip_built=False,model_media_credentials_included=False)
        put('RESULT.json',enc(summary));put('SOURCE_CLOSED.json',enc(dict(closed_unix=time.time(),prepared_allocated_bytes=used,source_backups_and_independent_restores=True,native_action=False)))
        print(json.dumps(dict(output=str(out),reviewed_plan_sha256=sha(final_raw),members=len(rows),source_bytes=total,zip_built=False)))
    except BaseException as error:
        put('FAILURE.json',enc(dict(type=type(error).__name__,message=str(error)[:2048])));raise

if __name__=='__main__':main()
