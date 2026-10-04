"""Bounded read-only current backup-scope discovery. README_CURRENT_BACKUP_SCOPE_V4.md."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

BASE=Path('/home/peachyprototype/JustPeachy')
CAMPAIGN=BASE/'research/nemotron-20260928'
MAX_FILES=4096
MAX_ROOTS=64


def small(path,maximum=65536):
    info=path.lstat()
    if path.resolve(strict=True)!=path or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>maximum:
        raise ValueError('Canonical bounded discovery metadata required')
    raw=path.read_bytes()
    if len(raw)>maximum:raise ValueError('Discovery metadata grew')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),value=json.loads(raw))


def children(path,maximum=1024):
    result=[]
    with os.scandir(path) as entries:
        for item in entries:
            if len(result)>=maximum:raise ValueError('Bounded discovery directory membership required')
            info=item.stat(follow_symlinks=False)
            kind='symlink' if stat.S_ISLNK(info.st_mode) else 'directory' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'special'
            result.append(dict(name=item.name,kind=kind,bytes=info.st_size))
    return sorted(result,key=lambda row:row['name'])


def absent_slot_proof(root,receipt,index,source):
    """Only the retained journal's empty or exact reservation-only slot qualifies."""
    policy=receipt['value'];slots=policy.get('allocation',{}).get('recording_slots')
    roots=policy.get('recording_roots')
    if (policy.get('manager_root')!=str(root) or not isinstance(slots,list) or
        len(slots)!=len(roots) or len(set(slots))!=len(slots) or index>=len(slots)):
        raise ValueError('Exact retained policy slot/root association required')
    slot=slots[index]
    if re.fullmatch(r'recording-[0-9]{2}',slot) is None:raise ValueError('Exact retained recording slot name required')
    directory=root/'recordings'/slot;backup=root/'backups'/slot
    result=dict(source=str(source),release=str(root),policy_path=receipt['path'],policy_sha256=receipt['sha256'],
        slot=slot,slot_directory=str(directory),root_absent=not source.exists(),
        backup_absent=not backup.exists(),eligible=False,state='UNRESOLVED_ABSENCE')
    if source.exists() or source.is_symlink() or backup.exists() or backup.is_symlink():return result
    if not directory.is_dir() or directory.resolve(strict=True)!=directory:return result
    membership=children(directory,16);result['slot_membership']=membership
    if membership==[]:
        result.update(eligible=True,state='UNUSED_NEVER_STARTED',no_start_owner_or_data_receipts=True)
    elif len(membership)==1 and membership[0]['name']=='RESERVED.json' and membership[0]['kind']=='file':
        reservation=small(directory/'RESERVED.json',16384);value=reservation['value'];operation=value.get('operation',{})
        result['reservation']=reservation
        if (value.get('policy_sha256')==receipt['sha256'] and value.get('slot')=='recordings/'+slot and
            operation.get('schema')=='just-peachy.offline-runtime-operation.v1' and
            operation.get('root')==str(source) and operation.get('slot')==slot and
            operation.get('policy_sha256')==receipt['sha256']):
            result.update(eligible=True,state='RESERVED_NEVER_STARTED',no_start_owner_or_data_receipts=True)
    return result


def validate_gallery_namespaces(value):
    """Preserve actual E0-only profiles and require E1 for TitaNet."""
    if value.get('schema') != 'just-peachy.runtime-profile-descriptor.v1':
        raise ValueError('Current profile descriptor schema required')
    profile = value.get('runtime_profile', {})
    galleries = profile.get('galleries')
    embedding = profile.get('definition', {}).get('selection', {}).get('embedding')
    if (type(galleries) is not dict or set(galleries) not in ({'E0'}, {'E0', 'E1'})
        or embedding not in ('E0', 'E1', None)
        or (embedding == 'E1' and 'E1' not in galleries)):
        raise ValueError('Exact current E0/E1 gallery namespaces required')
    return tuple(sorted(galleries))

def discover(base=BASE,campaign=CAMPAIGN,home=Path('/home/peachyprototype')):
    """Actual existing roots only; missing known historical roots are explicit."""
    observed=children(campaign);by_name={row['name']:row for row in observed}
    roots=[];missing=[];issues=[];receipts=[];absences=[]
    def add(path,reason):
        if not path.exists():missing.append(dict(path=str(path),reason=reason));return
        if path.resolve(strict=True)!=path:raise ValueError('Review source symlinks before constructing full scope')
        if not any(path==prior or prior in path.parents for prior,_ in roots):
            roots[:]=[(prior,why) for prior,why in roots if path not in prior.parents]
            roots.append((path,reason))
    for release in ('field-runtime-v27','field-runtime-v28'):
        root=campaign/release;add(root,'retained release source/control/backups')
        if root.exists():
            receipt=small(root/'control/RELEASE.json');receipts.append(receipt)
            names=receipt['value'].get('recording_roots')
            if not isinstance(names,list) or not names:raise ValueError('Retained RELEASE recording roots required')
            for index,name in enumerate(names):
                path=Path(name)
                if path.parent!=campaign or not re.fullmatch(r'field-operator-sessions-v[0-9]+',path.name):
                    raise ValueError('Exact retained recording-root reference required')
                if not path.exists():absences.append(absent_slot_proof(root,receipt,index,path))
                add(path,'recording root named by '+release)
    # Current-release backup is distinct from an unchanged historical campaign
    # inventory. Every exclusion remains explicit; no old root is mutated.
    recording_numbers=[int(Path(name).name.rsplit('v',1)[1])
        for receipt in receipts for name in receipt['value']['recording_roots']]
    if not recording_numbers:raise ValueError('Current release recording references required')
    newest_reserved=max(recording_numbers)
    for version in (27,28):
        profile_root=campaign/('field-runtime-v%d-profiles'%version)
        if not profile_root.is_dir():raise ValueError('Current profile root missing')
        add(profile_root,'current v%d profile definitions'%version)
        descriptors=[row for row in children(profile_root,128)
            if row['kind']=='file' and row['name'].endswith('.json') and row['name']!='COMMON_BUNDLE.json']
        if not 1<=len(descriptors)<=16:raise ValueError('Bounded current profile descriptors required')
        for descriptor in descriptors:
            profile=small(profile_root/descriptor['name'],65536);receipts.append(profile)
            galleries=profile['value'].get('runtime_profile',{}).get('galleries')
            validate_gallery_namespaces(profile['value'])
            for namespace,row in galleries.items():
                person_root=Path(row['root']);manifest=Path(row['manifest_path'])
                gallery=person_root.parent.parent
                if (gallery.parent!=campaign or re.fullmatch(r'field-runtime-v[0-9]+-galleries',gallery.name) is None
                    or person_root!=gallery/namespace/'people' or manifest!=gallery/namespace/'MANIFEST.json'):
                    raise ValueError('Exact current gallery reference requires separate review')
                add(gallery,'gallery referenced by actual current profile '+str(profile_root/descriptor['name']))
    for row in observed:
        match=re.fullmatch(r'field-operator-sessions-v([0-9]+)',row['name'])
        if match and int(match.group(1))>newest_reserved:
            add(campaign/row['name'],'newer operator recording beyond current reserved range')
    exclusions=[]
    selected={str(path) for path,_ in roots}
    for row in observed:
        if (re.fullmatch(r'field-operator-sessions-v[0-9]+',row['name']) or
            re.fullmatch(r'field-runtime-v[0-9]+-(profiles|galleries)',row['name'])):
            path=str(campaign/row['name'])
            if path not in selected:
                exclusions.append(dict(source=path,classification='unchanged_historical_campaign_root',
                    current_release_reference=False,new_backup_claimed=False,source_mutated=False,
                    preservation='Original native root and earlier private backups retained; not part of this selected-release copy'))
    for directory in (base/'data',base/'config'):
        if directory.exists():add(directory,'complete current data/config tree including every child')
    selector=small(base/'install/current.json');receipts.append(selector)
    relative=PurePosixPath(selector['value']['relative_path'])
    if (relative.is_absolute() or '..' in relative.parts or len(relative.parts)!=2 or
        relative.parts[0]!='releases'):raise ValueError('Exact selected installed release required')
    add(base/'install'/str(relative),'actual install/current.json selected source')
    add(base/'install/current.json','current install selector')
    add(base/'start-prototype.sh','current startup entry script')
    add(home/'.config/kanshi/config','current display/calibration orientation configuration')
    add(home/'.config/autostart/just-peachy.desktop','current disabled desktop-first startup')
    desktop=children(home/'Desktop',128)
    for row in desktop:
        if re.fullmatch(r'just-peachy-field-runtime-v28-[a-z0-9-]+\.desktop',row['name']):
            add(home/'Desktop'/row['name'],'actual owned retained shortcut')
    if len(roots)>MAX_ROOTS:
        return dict(schema='just-peachy.production-scope-discovery.v1',
            status='COMPLETE_ROOT_LIST_NEEDS_GROUPING_REVIEW',
            roots=[dict(source=str(path),reason=reason) for path,reason in roots],
            missing_known_roots=missing,slot_absence_proofs=absences,
            issues=['complete root membership exceeds64; no scope admitted or data omitted'],
            metadata_receipts=receipts,historical_roots_preserved_outside_copy=exclusions,campaign_membership=observed,desktop_membership=desktop,
            observed_root_count=len(roots),capture=False,models_loaded=False,source_files_changed=False)
    members=[];result=[];total=0
    for index,(root,reason) in enumerate(sorted(roots,key=lambda pair:str(pair[0]))):
        pending=[root];root_members=[]
        while pending:
            path=pending.pop();info=path.lstat()
            if path.resolve(strict=True)!=path:raise ValueError('Discovery symlink requires exact separate review')
            if stat.S_ISDIR(info.st_mode):
                entries=children(path,MAX_FILES)
                pending.extend(path/row['name'] for row in entries)
                if len(pending)+len(members)>MAX_FILES:raise ValueError('Complete discovery membership exceeds4096bound')
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('Single-link regular current source required')
            if len(members)>=MAX_FILES:raise ValueError('Complete discovery exceeds4096files')
            row=dict(path=str(path),bytes=info.st_size,mtime_ns=info.st_mtime_ns,device=info.st_dev,inode=info.st_ino)
            members.append(row);root_members.append(row);total+=info.st_size
        result.append(dict(source=str(root),destination='root-%02d'%index,reason=reason,
            files=len(root_members),bytes=sum(row['bytes'] for row in root_members)))
    value=dict(schema='just-peachy.production-scope-discovery.v1',roots=result,members=members,
        missing_known_roots=missing,slot_absence_proofs=absences,issues=issues,metadata_receipts=receipts,historical_roots_preserved_outside_copy=exclusions,campaign_membership=observed,
        desktop_membership=desktop,total_files=len(members),total_bytes=total,hashes_verified=False,
        capture=False,models_loaded=False,source_files_changed=False)
    if len(json.dumps(value,separators=(',',':')).encode())>2*1024**2:raise ValueError('Discovery2MiB output bound')
    return value


def dispatch(payload,baseline):
    import fcntl
    if any(baseline.get(key) for key in ('current_project_processes','active_recorded_owners','live_manager_owners')):
        raise ValueError('All runtime owners must close before read-only scope discovery')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot!=payload['boot_id'] or not time.time()<payload['expires_unix']<=time.time()+600:
        raise ValueError('Fresh same-boot discovery admission required')
    handles=[]
    try:
        for path in (CAMPAIGN/'B05_PREVIEW_DISPATCH.lock',BASE/'data/xvf-hardware.lock'):
            stream=path.open('rb');fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);handles.append(stream)
        value=discover();value.update(boot_id=boot,issued_unix=time.time(),scope_locked_during_discovery=True)
        return value
    finally:
        for stream in reversed(handles):fcntl.flock(stream,fcntl.LOCK_UN);stream.close()


if 'PAYLOAD' in globals():RESULT=dispatch(PAYLOAD,BASELINE)
