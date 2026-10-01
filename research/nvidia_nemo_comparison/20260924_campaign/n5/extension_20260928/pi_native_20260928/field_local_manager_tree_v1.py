"""One-recording manager tree preservation; README_FIELD_LOCAL_MIRROR_V1.md."""
import hashlib
from pathlib import Path,PurePosixPath
import re
from field_local_release_plan_v2 import (encoded,validate_release,CONTROL_RECORDS,
    LAUNCH_RECORDS,RECORDING_RECORDS)
from field_operator_broker_layout_v2 import ONCE,APPEND
from field_operator_session_plan_v3 import RECORDS
from field_operator_broker_streamed_mirror_v1 import (
    _inventory,portable,MAX_FILES,MAX_DIRS,MAX_FILE,MAX_MANIFEST)

def validate(binding):
    if type(binding) is not dict or set(binding)!={'schema','policy','policy_sha256','manifest'}:
        raise ValueError('Exact manager mirror binding')
    if binding['schema']!='just-peachy.manager-tree-binding.v1':raise ValueError('Binding schema')
    p=validate_release(binding['policy']);a=p['allocation']
    if a['recordings']!=1 or a['launches']!=3:raise ValueError('One-recording three-launch qualification only')
    if hashlib.sha256(encoded(p)).hexdigest()!=binding['policy_sha256']:raise ValueError('Actual expected release bytes')
    m=binding['manifest']
    if type(m) is not dict or set(m)!={'schema','files'} or m['schema']!='just-peachy.local-release-manifest.v1':
        raise ValueError('Exact expected manager manifest')
    if hashlib.sha256(encoded(m)).hexdigest()!=p['release_manifest_sha256']:raise ValueError('Manifest binding')
    if type(m['files']) is not list or not 1<=len(m['files'])<=16:raise ValueError('Code count')
    aliases=set();total=0
    for r in m['files']:
        if type(r) is not dict or set(r)!={'path','bytes','sha256'}:raise ValueError('Exact expected code row')
        n=r['path'];portable(n)
        if not re.fullmatch(r'code/[A-Za-z0-9_]+\.py',n) or n.casefold() in aliases:raise ValueError('Unique manager code name')
        aliases.add(n.casefold())
        if type(r['bytes']) is not int or not 0<r['bytes']<=131072:raise ValueError('Code member size')
        if type(r['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',r['sha256']):raise ValueError('Code digest')
        total+=r['bytes']
    if total>2097152:raise ValueError('Original code aggregate')
    return p

def broker_projection(files,dirs,allocation):
    """Same independent broker/child partitions, including incomplete sources."""
    slots=set(allocation['slot_names']);child={n:[0,0,0] for n in slots}
    code_count=code_bytes=0
    for name in dirs:
        parts=PurePosixPath(name).parts
        if not parts:continue
        if parts[0]=='recordings' and len(parts)>=2:
            if parts[1] not in slots:raise ValueError('Unallocated child directory')
            child[parts[1]][1]+=1;child[parts[1]][2]+=65536
        elif name not in {'broker','code','recordings',*slots}:raise ValueError('Unknown broker directory')
    for name,row in files.items():
        parts=PurePosixPath(name).parts;size=row['bytes']
        if parts[0]=='recordings' and len(parts)>=3:
            if parts[1] not in slots:raise ValueError('Unallocated child file')
            child[parts[1]][0]+=1;child[parts[1]][2]+=size
        elif len(parts)==2 and parts[0]=='code':
            if size>131072:raise ValueError('Broker code member')
            code_count+=1;code_bytes+=size
        elif len(parts)==2 and parts[0]=='broker':
            n=parts[1];cap=ONCE.get(n[:-8]) if n.endswith('.pending') else ONCE.get(n,APPEND.get(n))
            if cap is None or size>cap:raise ValueError('Broker producer slot')
        elif len(parts)==2 and parts[0] in slots:
            if parts[1] not in {k+'.json'+suffix for k in RECORDS for suffix in ('','.pending')} or size>16384:
                raise ValueError('Broker ledger slot')
        elif name not in ('RELEASE.json','.lease') or size>(65536 if name=='RELEASE.json' else 0):
            raise ValueError('Unknown broker file')
    if code_count>64 or code_bytes>2097152:raise ValueError('Broker code aggregate')
    for count,ndirs,total in child.values():
        if count>256 or ndirs>64 or total>146919980:raise ValueError('Independent child allocation')
    reserved=sum(r['bytes'] for r in files.values())+len(dirs)*65536
    if reserved>allocation['target_maximum_bytes']:raise ValueError('Independent local broker mirror')
    return reserved

def projection(files,directories,binding):
    p=validate(binding);a=p['allocation']
    if type(files) is not dict or len(files)>MAX_FILES or type(directories) not in (list,set):
        raise ValueError('Bounded inventory containers')
    dirs=set(directories)
    if len(dirs)!=len(directories) or not 1<=len(dirs)<=MAX_DIRS or '' not in dirs:
        raise ValueError('Exact directory membership')
    aliases=set()
    for n in list(files)+[n for n in dirs if n]:
        portable(n)
        if n.casefold() in aliases:raise ValueError('Path alias or collision')
        aliases.add(n.casefold())
        parent=PurePosixPath(n).parent.as_posix()
        if ('' if parent=='.' else parent) not in dirs:raise ValueError('Missing parent directory')
    for row in files.values():
        if type(row) is not dict or set(row)!={'bytes','sha256'} or type(row['bytes']) is not int or not 0<=row['bytes']<=MAX_FILE:
            raise ValueError('Exact bounded file row')
        if type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('File digest')
    caps={'control':CONTROL_RECORDS}
    caps.update({'launches/'+s:LAUNCH_RECORDS for s in a['launch_slots']})
    caps.update({'recordings/'+s:RECORDING_RECORDS for s in a['recording_slots']})
    metadata_dirs={'','code','control','launches','recordings','backups',*caps}
    backup_root='backups/recording-01'
    local_files={};local_dirs=set();metadata_bytes=0;metadata_count=0
    code={r['path']:r['bytes'] for r in binding['manifest']['files']}
    for n in dirs:
        if n==backup_root or n.startswith(backup_root+'/'):
            local_dirs.add(n[len(backup_root):].lstrip('/'))
        elif n not in metadata_dirs:raise ValueError('Unallocated manager directory')
    for n,row in files.items():
        size=row['bytes'];parent=PurePosixPath(n).parent.as_posix()
        if n.startswith(backup_root+'/'):
            local_files[n[len(backup_root)+1:]]=row;continue
        if n in code:
            if size>code[n]:raise ValueError('Expected code member grew')
        elif parent in caps:
            member=PurePosixPath(n).name
            base=member[:-8] if member.endswith('.pending') else member
            if not base.endswith('.json') or base[:-5] not in caps[parent] or size>caps[parent][base[:-5]]:
                raise ValueError('Unallocated manager producer slot')
        else:raise ValueError('Unallocated manager file')
        metadata_bytes+=size;metadata_count+=1
    metadata_directory_count=len(dirs)-len(local_dirs)
    if metadata_directory_count>a['metadata_directories'] or metadata_bytes+metadata_directory_count*65536>a['metadata_maximum_bytes']:
        raise ValueError('Independent manager metadata reservation')
    if local_dirs:broker_projection(local_files,local_dirs,a['broker_allocation'])
    elif local_files:raise ValueError('Missing mirror directory')
    total=sum(row['bytes'] for row in files.values());reserved=total+len(dirs)*65536
    # The external original broker is NOT inside this manager tree.
    maximum=a['metadata_maximum_bytes']+a['local_backup_per_recording']
    if reserved>maximum:raise ValueError('Full manager tree allocation')
    return dict(files=files,directories=sorted(dirs),bytes=total,reserved_bytes=reserved)

def inventory(root,deadline,binding):
    files,dirs=_inventory(root,deadline)
    projection({n:dict(bytes=i[2],sha256='0'*64) for n,i in files.items()},dirs,binding)
    return files,dirs

def plan(root,pinned_files,deadline,binding):
    from field_operator_broker_ssh_mirror_v2 import validate_plan
    before,dirs=inventory(root,deadline,binding)
    if set(before)!=set(pinned_files) or any(before[n][2]!=pinned_files[n]['bytes'] for n in before):
        raise ValueError('Entire actual tree differs from pinned census')
    value=projection(pinned_files,dirs,binding)
    a=binding['policy']['allocation'];maximum=a['metadata_maximum_bytes']+a['local_backup_per_recording']
    validate_plan(value,pinned_files,maximum,True)
    return dict(value,source_identities=before)
