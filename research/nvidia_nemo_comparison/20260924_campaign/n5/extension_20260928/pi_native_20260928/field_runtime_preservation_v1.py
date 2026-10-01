"""Finite runtime preservation partitions and owners; README_FIELD_RUNTIME_PRESERVATION_V1.md."""
from datetime import datetime
import hashlib
from pathlib import PurePosixPath
import re

from field_runtime_policy_v2 import validate as validate_policy, digest, encoded
from field_local_release_plan_v2 import CONTROL_RECORDS,LAUNCH_RECORDS,RECORDING_RECORDS
from field_local_manager_owners_v1 import strict,identity,key,decode as decode_old
from field_local_manager_tree_v1 import broker_projection
from field_operator_broker_streamed_mirror_v1 import portable,MAX_FILES,MAX_DIRS,MAX_FILE,MAX_MANIFEST

PURPOSES={'USER_RUNTIME_MANAGER','USER_RUNTIME_STAGE','USER_RUNTIME_GATE','USER_RUNTIME_COPY'}


def decode_owners(records,policy):
    """Completed owner records only; pending bytes remain ordinary preserved files."""
    validate_policy(policy);allocation=policy['allocation'];policy_sha=digest(policy)
    maximum=allocation['launches']+9*allocation['recordings']
    if type(records) is not dict or len(records)>maximum:
        raise ValueError('Independent allocated runtime owner cardinality')
    direct={};typed=set()
    for recording in allocation['recording_slots']:
        prefix='backups/'+recording+'/'
        for name in ('STAGE_OWNER.json','GATE_OWNER.json','OWNER.json'):
            direct[prefix+'broker/'+name]=True
        child=prefix+'recordings/slot-01/'
        for name in ('control/OWNER.json','control/REGISTERED_OWNER.json','parent_control/OWNER.json','source/CHILD_OWNER.json'):
            direct[child+name]=True
        typed|={child+n+'/OWNERSHIP_CLOSURE.json' for n in ('control','parent_control')}
    rows=[];closures=[];launches=[]
    for name,raw in sorted(records.items()):
        value=strict(raw)
        if name in direct:who=identity(value)
        elif name in typed:
            # Reuse the exact existing typed decoder, never turn a closure into an identity.
            canonical=re.sub(r'^backups/recording-0[1-4]/','backups/recording-01/',name)
            result=decode_old({canonical:raw},policy_sha)
            if result['records'] or len(result['typed_nonidentity_closures'])!=1:
                raise ValueError('Exact typed nonidentity closure')
            row=result['typed_nonidentity_closures'][0];row['path']=name;closures.append(row)
            continue
        else:
            match=re.fullmatch(r'launches/(launch-[0-9]{2})/OWNER.json',name)
            if not match or match[1] not in allocation['launch_slots']:
                raise ValueError('Unknown completed runtime owner path')
            if type(value) is not dict or set(value)!={'owner','policy_sha256','slot','utc','purpose'}:
                raise ValueError('Exact runtime launch owner envelope')
            if value['policy_sha256']!=policy_sha or value['slot']!='launches/'+match[1] or value['purpose'] not in PURPOSES:
                raise ValueError('Pinned release, allocated slot and reviewed runtime role')
            stamp=datetime.fromisoformat(value['utc'])
            if stamp.tzinfo is None or stamp.utcoffset().total_seconds()!=0:
                raise ValueError('Actual aware UTC registration')
            who=identity(value['owner'])
            launches.append(dict(slot=match[1],purpose=value['purpose'],owner=who))
        rows.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),owner=who))
    return dict(records=rows,launches=launches,typed_nonidentity_closures=closures,
        identities=list({key(row['owner']):row['owner'] for row in rows}.values()))


def partitions(files,directories,policy,manifest):
    """Keep each independent backup within the existing per-broker framing limits."""
    validate_policy(policy);a=policy['allocation']
    if type(manifest) is not dict or set(manifest)!={'schema','files'} or manifest['schema']!='just-peachy.local-release-manifest.v1':
        raise ValueError('Exact runtime code manifest')
    if digest(manifest)!=policy['runtime_manifest_sha256']:
        raise ValueError('Pinned runtime manifest')
    code={}
    if type(manifest['files']) is not list or not 1<=len(manifest['files'])<=16:
        raise ValueError('Original manager code count')
    for row in manifest['files']:
        if type(row) is not dict or set(row)!={'path','bytes','sha256'}:
            raise ValueError('Exact code row')
        name=row['path'];portable(name)
        if not re.fullmatch(r'code/[A-Za-z0-9_]+\.py',name) or name in code:
            raise ValueError('Unique manager Python member')
        if type(row['bytes']) is not int or not 0<row['bytes']<=131072 or not re.fullmatch('[0-9a-f]{64}',row['sha256']):
            raise ValueError('Original manager code member cap and digest')
        code[name]=row
    if sum(r['bytes'] for r in code.values())>2097152:raise ValueError('Original manager code total')
    caps={'control':CONTROL_RECORDS}
    caps.update({'launches/'+s:LAUNCH_RECORDS for s in a['launch_slots']})
    caps.update({'recordings/'+s:RECORDING_RECORDS for s in a['recording_slots']})
    metadata_dirs={'','code','control','launches','recordings','backups',*caps}
    metadata_file_cap=16+2*sum(len(v) for v in caps.values())
    maximum_files=metadata_file_cap+a['recordings']*MAX_FILES
    maximum_dirs=a['metadata_directories']+a['recordings']*MAX_DIRS
    if type(files) is not dict or len(files)>maximum_files or type(directories) not in (list,set):
        raise ValueError('Sum of independent finite partition inventories')
    dirs=set(directories)
    if len(dirs)!=len(directories) or not 1<=len(dirs)<=maximum_dirs or '' not in dirs:
        raise ValueError('Complete unique directory membership')
    aliases=set()
    for name in list(files)+[n for n in dirs if n]:
        portable(name)
        if name.casefold() in aliases:raise ValueError('Path alias or collision')
        aliases.add(name.casefold())
        parent=PurePosixPath(name).parent.as_posix()
        if ('' if parent=='.' else parent) not in dirs:raise ValueError('Missing directory parent')
    result={'metadata':dict(prefix='',files={},directories=set(),maximum_bytes=a['metadata_maximum_bytes'])}
    for slot in a['recording_slots']:
        result[slot]=dict(prefix='backups/'+slot,files={},directories=set(),maximum_bytes=a['local_backup_per_recording'])
    def partition(name):
        parts=PurePosixPath(name).parts
        if len(parts)>=2 and parts[0]=='backups':
            slot=parts[1]
            if slot not in a['recording_slots']:raise ValueError('Unallocated independent local backup')
            return slot,'/'.join(parts[2:])
        return 'metadata',name
    for name in dirs:
        group,relative=partition(name)
        if group=='metadata' and name not in metadata_dirs:raise ValueError('Unallocated manager directory')
        result[group]['directories'].add(relative)
    for name,row in files.items():
        if type(row) is not dict or set(row)!={'bytes','sha256'} or type(row['bytes']) is not int or not 0<=row['bytes']<=MAX_FILE:
            raise ValueError('Exact bounded member')
        if type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('Exact member digest')
        group,relative=partition(name)
        if group=='metadata':
            parent=PurePosixPath(name).parent.as_posix();member=PurePosixPath(name).name
            if name in code:
                if row['bytes']>code[name]['bytes']:raise ValueError('Pinned code member overflow')
            elif parent in caps:
                base=member[:-8] if member.endswith('.pending') else member
                if not base.endswith('.json') or base[:-5] not in caps[parent] or row['bytes']>caps[parent][base[:-5]]:
                    raise ValueError('Independent runtime producer cap')
            else:raise ValueError('Unallocated runtime file')
        result[group]['files'][relative]=row
    public={};total=0;count=0
    for group,row in result.items():
        fs=row['files'];ds=row['directories']
        if not ds:
            if fs:raise ValueError('Missing backup root')
            continue
        if len(fs)>MAX_FILES or len(ds)>MAX_DIRS:raise ValueError('Original per-frame member limits retained')
        reserved=sum(v['bytes'] for v in fs.values())+len(ds)*65536
        if group=='metadata':
            if len(ds)>a['metadata_directories'] or len(fs)>metadata_file_cap or reserved>a['metadata_maximum_bytes']:
                raise ValueError('Complete independent metadata allocation')
        else:broker_projection(fs,ds,a['broker_allocation'])
        if reserved>row['maximum_bytes']:raise ValueError('Independent partition allocation')
        value=dict(prefix=row['prefix'],files=fs,directories=sorted(ds),
            bytes=sum(v['bytes'] for v in fs.values()),reserved_bytes=reserved,maximum_bytes=row['maximum_bytes'])
        if len(encoded(value))>MAX_MANIFEST:raise ValueError('Original256KiB partition framing cap')
        public[group]=value;total+=reserved;count+=len(fs)
    maximum=a['metadata_maximum_bytes']+a['recordings']*a['local_backup_per_recording']
    if total>maximum or count!=len(files):raise ValueError('Complete nonoverlapping manager tree accounting')
    # A small index pins separate full manifests; no enlarged monolithic frame.
    index={name:dict(prefix=v['prefix'],manifest_sha256=digest(v),files=len(v['files']),
        directories=len(v['directories']),reserved_bytes=v['reserved_bytes']) for name,v in public.items()}
    if len(encoded(index))>16384:raise ValueError('Bounded complete partition index')
    return dict(partitions=public,index=index,files=count,reserved_bytes=total,
        maximum_bytes=maximum,global_manifest_sha256=digest(index))

