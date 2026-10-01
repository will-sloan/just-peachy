"""Native broker qualification component; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V1.md."""
import hashlib
from pathlib import Path
import re
from field_operator_broker_streamed_mirror_v1 import _inventory,portable,MAX_MANIFEST
from field_host_budget_v1 import encoded

def validate(binding):
    if type(binding) is not dict or set(binding)!={'source_root','policy_sha256','initializer_owner','members'}:
        raise ValueError('Exact partial-initializer binding')
    root=binding['source_root']
    if not isinstance(root,str) or not re.fullmatch(r'/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-operator-sessions-v[1-9][0-9]*',root):
        raise ValueError('Exact initializer root')
    if not re.fullmatch('[0-9a-f]{64}',binding['policy_sha256']):raise ValueError('Policy digest')
    owner=binding['initializer_owner']
    if type(owner) is not dict or set(owner)!={'pid','start_ticks','boot_id'} or type(owner['pid']) is not int or type(owner['start_ticks']) is not int or owner['pid']<=0 or owner['start_ticks']<0:
        raise ValueError('External exact initializer identity')
    if not re.fullmatch('[0-9a-f-]{36}',owner['boot_id']):raise ValueError('Boot identity')
    members=binding['members'];code_count=code_bytes=0
    if type(members) is not dict or not 5<=len(members)<=69:raise ValueError('Initializer member count')
    required={'RELEASE.json':65536,'broker/STAGE_OWNER.json':16384,'broker/MANIFEST.json':131072,
        'broker/CONFIG.json':65536,'broker/TEMPLATE.json':131072}
    if not set(required).issubset(members):raise ValueError('Complete initializer output map')
    for name,size in members.items():
        portable(name)
        if type(size) is not int or size<=0:raise ValueError('Strict positive member ceiling')
        if name in required:
            if size>required[name]:raise ValueError('Initializer control ceiling')
        else:
            parts=name.split('/')
            if len(parts)!=2 or parts[0]!='code' or size>131072:raise ValueError('Only initialized code members')
            code_count+=1;code_bytes+=size
    if not 1<=code_count<=64 or code_bytes>2097152:raise ValueError('Original code ceiling')
    return binding

def inventory(root,deadline,binding):
    validate(binding)
    files,dirs=_inventory(root,deadline)
    if not dirs.issubset({'','code','broker'}):raise ValueError('Initializer never created runtime/recording directories')
    for name,ident in files.items():
        if name not in binding['members'] or ident[2]>binding['members'][name]:
            raise ValueError('Outside original initializer physical slot')
    if len(files)>69:raise ValueError('Initializer file cardinality')
    return files,dirs

def plan(root,pins,deadline,maximum,binding):
    validate(binding)
    if type(pins) is not dict or len(pins)>69 or len(encoded(pins))>MAX_MANIFEST:raise ValueError('Partial tree manifest')
    files,dirs=inventory(root,deadline,binding)
    if set(files)!=set(pins):raise ValueError('Exact partial membership')
    for name,row in pins.items():
        if type(row) is not dict or set(row)!={'bytes','sha256'} or type(row['bytes']) is not int or row['bytes']!=files[name][2] or not re.fullmatch('[0-9a-f]{64}',row['sha256']):
            raise ValueError('Exact partial member pin')
    size=sum(v['bytes'] for v in pins.values());reserved=size+len(dirs)*65536
    if type(maximum) is not int or reserved>maximum:raise ValueError('Retained whole target allocation')
    return dict(files=pins,directories=sorted(dirs),bytes=size,reserved_bytes=reserved,source_identities=files)

def projection(files,dirs,binding):
    validate(binding)
    if not set(dirs).issubset({'','code','broker'}):raise ValueError('Only initializer directories')
    if len(files)>69:raise ValueError('Initializer file cardinality')
    for name,row in files.items():
        if name not in binding['members'] or type(row['bytes']) is not int or not 0<=row['bytes']<=binding['members'][name]:
            raise ValueError('Original initializer member ceiling before destination creation')
