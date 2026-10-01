"""Pure one-broker local-backup binding; README_FIELD_LOCAL_CAPSULE_V1.md."""
from pathlib import PurePosixPath
import hashlib
import re
from field_local_release_plan_v2 import encoded, validate_release
from field_operator_session_plan_v3 import validate_policy
from datetime import datetime

def source_binding(release, slot, policy, policy_sha256):
    validate_release(release)
    slots=release['allocation']['recording_slots']
    if slot not in slots:raise ValueError('Exact allocated recording slot')
    source=release['recording_roots'][slots.index(slot)]
    validate_policy(policy,now=datetime.fromisoformat(policy['issued_utc']))
    if policy['root']!=source:raise ValueError('Exact independently allocated source')
    if encoded(policy['allocation'])!=encoded(release['allocation']['broker_allocation']):
        raise ValueError('Exactly one broker session per manager recording')
    if type(policy_sha256) is not str or not re.fullmatch('[0-9a-f]{64}',policy_sha256):
        raise ValueError('Exact source policy digest')
    return dict(source=source,destination=release['root']+'/backups/'+slot,
        policy_sha256=policy_sha256,source_unit='jp-'+PurePosixPath(source).name+'.service',
        maximum_bytes=release['allocation']['local_backup_per_recording'])

def copy_binding(receipt, binding):
    fields={'schema','status','source','destination','policy_sha256','source_unit','unit_before','unit_after',
        'owners','chunk_bytes','data_chunks','independent_full_readback','full_reserved_bytes',
        'files','directories','bytes','reserved_bytes'}
    if type(receipt) is not dict or set(receipt)!=fields:
        raise ValueError('Exact complete local-copy receipt')
    if receipt['schema']!='just-peachy.local-broker-backup.v1' or receipt['status']!='COMPLETE_LOCAL_COPY_READBACK':
        raise ValueError('Completed independent local copy')
    for k in ('source','destination','policy_sha256','source_unit'):
        if receipt[k]!=binding[k]:raise ValueError('Copy source/destination/policy/unit drift')
    for k in ('chunk_bytes','data_chunks','full_reserved_bytes','bytes','reserved_bytes'):
        if type(receipt[k]) is not int or receipt[k]<0:raise ValueError('Exact integer copy counters')
    if receipt['chunk_bytes']!=16384 or receipt['independent_full_readback'] is not True:
        raise ValueError('Bounded copy and independent readback required')
    if receipt['full_reserved_bytes']!=binding['maximum_bytes'] or receipt['reserved_bytes']>binding['maximum_bytes']:
        raise ValueError('Independent full reservation retained')
    files=receipt['files'];directories=receipt['directories']
    if type(files) is not dict or not files or type(directories) is not list or not directories or directories[0]!='':
        raise ValueError('Complete files and root-inclusive directories')
    if len(files)>384 or len(directories)>72 or len(set(directories))!=len(directories):
        raise ValueError('One-broker copy cardinality')
    def path(name,root=False):
        if root and name=='':return
        if type(name) is not str:raise ValueError('Relative path string')
        p=PurePosixPath(name)
        if p.is_absolute() or p.as_posix()!=name or not p.parts or len(name)>480 or any(not re.fullmatch('[A-Za-z0-9_.-]{1,120}',n) or n in ('.','..') for n in p.parts):
            raise ValueError('Canonical relative copy member')
    total=0
    for name,row in files.items():
        path(name)
        if type(row) is not dict or set(row)!={'bytes','sha256'} or type(row['bytes']) is not int or not 0<=row['bytes']<=33554432:
            raise ValueError('Exact bounded file pin')
        if type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('File digest')
        parent=PurePosixPath(name).parent.as_posix()
        if ('' if parent=='.' else parent) not in directories:raise ValueError('Missing file parent')
        total+=row['bytes']
    aliases=set()
    for name in [*files,*directories]:
        path(name,True)
        if name.casefold() in aliases:raise ValueError('Duplicate or case-aliased member')
        aliases.add(name.casefold())
        if name:
            parent=PurePosixPath(name).parent.as_posix()
            if ('' if parent=='.' else parent) not in directories:raise ValueError('Missing directory parent')
    if total!=receipt['bytes'] or total+65536*len(directories)!=receipt['reserved_bytes']:
        raise ValueError('Complete logical and directory accounting')
    for key in ('unit_before','unit_after'):
        value=receipt[key]
        if type(value) is not dict or value.get('MainPID')!='0' or value.get('ActiveState') not in ('inactive','failed') or value.get('SubState') not in ('dead','failed'):
            raise ValueError('Actual unit closure fields')
    if type(receipt['owners']) is not list or not receipt['owners']:raise ValueError('Actual owner observations required')
    seen=set()
    for row in receipt['owners']:
        if type(row) is not dict or set(row)!={'path','owner','exact_alive'} or row['exact_alive'] is not False:
            raise ValueError('Closed owner observation')
        path(row['path']);o=row['owner']
        if type(o) is not dict or set(o)!={'pid','boot_id','start_ticks'} or any(type(o[k]) is not int or o[k]<=0 for k in ('pid','start_ticks')):
            raise ValueError('Exact recorded identity')
        if type(o['boot_id']) is not str or not re.fullmatch('[0-9a-f-]{36}',o['boot_id']):raise ValueError('Boot identity')
        if row['path'] in seen:raise ValueError('Duplicate owner path')
        seen.add(row['path'])
    if len(encoded(receipt))>262144-1024:raise ValueError('Journal wrapper and copy receipt share allocated256KiB')
    return hashlib.sha256(encoded(receipt)).hexdigest()
