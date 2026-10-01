"""Exact owner decoding and current-boot binding; README_FIELD_LOCAL_EXPORT_V1.md."""
from datetime import datetime,timezone
import hashlib,json,re

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def digest(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}',value):
        raise ValueError('Exact SHA256')
    return value

def identity(value):
    if type(value) is not dict or set(value)!={'pid','start_ticks','boot_id'}:
        raise ValueError('Exact process identity')
    for k in ('pid','start_ticks'):
        if type(value[k]) is not int or value[k]<=0:raise ValueError('Positive identity integer')
    if type(value['boot_id']) is not str or not re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['boot_id']):
        raise ValueError('Exact boot UUID')
    return value

def key(value):
    identity(value)
    return value['boot_id'],value['pid'],value['start_ticks']

def strict(raw):
    if type(raw) is not bytes or len(raw)>16384:raise ValueError('Bounded raw owner record')
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('Duplicate JSON key')
            out[k]=v
        return out
    def bad(value):raise ValueError('Owner JSON has non-integer number')
    return json.loads(raw,object_pairs_hook=pairs,parse_float=bad,parse_constant=bad)

def decode(records,policy_sha256):
    digest(policy_sha256)
    if type(records) is not dict or len(records)>16:raise ValueError('Bounded completed owner records')
    purposes={'launch-01':'LOCAL_INSTALL-RESERVE','launch-02':'LOCAL_GATE_BEFORE_ACK','launch-03':'LOCAL_FINISH'}
    prefix='backups/recording-01/'
    direct={prefix+'broker/'+n for n in ('STAGE_OWNER.json','GATE_OWNER.json','OWNER.json')}
    child=prefix+'recordings/slot-01/'
    direct|={child+n for n in ('control/OWNER.json','control/REGISTERED_OWNER.json','parent_control/OWNER.json','source/CHILD_OWNER.json')}
    typed={child+n+'/OWNERSHIP_CLOSURE.json' for n in ('control','parent_control')}
    rows=[];closures=[]
    for name,raw in sorted(records.items()):
        value=strict(raw)
        if name in direct:owner=identity(value)
        elif name in typed:
            if type(value) is not dict or set(value)!={'borrowed','outer_released','controller_closed','worker_joined','pending_commands'}:
                raise ValueError('Exact typed ownership closure')
            if type(value['borrowed']) is not dict or set(value['borrowed'])!={'opened','closed'}:
                raise ValueError('Exact borrowed fields')
            if any(type(v) is not int or not 0<=v<=1 for v in value['borrowed'].values()):
                raise ValueError('Bounded borrowed values')
            if value['borrowed']['closed']>value['borrowed']['opened']:raise ValueError('Borrowed closure count')
            if value['outer_released'] is not True or any(type(value[k]) is not bool for k in ('controller_closed','worker_joined')):
                raise ValueError('Typed closure booleans')
            n=value['pending_commands']
            if n is not None and (type(n) is not int or n<0):raise ValueError('Pending command type')
            closures.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),receipt=value));continue
        else:
            match=re.fullmatch(r'launches/(launch-0[1-3])/OWNER.json',name)
            if not match:raise ValueError('Unknown completed owner path')
            slot='launches/'+match[1]
            if type(value) is not dict or set(value)!={'owner','policy_sha256','slot','utc','purpose'}:
                raise ValueError('Exact nested launch envelope')
            if value['policy_sha256']!=policy_sha256 or value['slot']!=slot or value['purpose']!=purposes[match[1]]:
                raise ValueError('Exact launch role, slot and release')
            stamp=datetime.fromisoformat(value['utc'])
            if stamp.tzinfo is None:raise ValueError('Aware recorded publication time')
            owner=identity(value['owner'])
        rows.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),owner=owner))
    return dict(records=rows,typed_nonidentity_closures=closures,
                identities=list({key(r['owner']):r['owner'] for r in rows}.values()))

def lifecycle(value,expected_sha256,now=None):
    digest(expected_sha256)
    keys={'schema','observed_utc','boot_id','baseline_owners','install_sha256','live_config_sha256','display_config_sha256'}
    if type(value) is not dict or set(value)!=keys or value['schema']!='just-peachy.current-boot-binding.v1':
        raise ValueError('Exact observed lifecycle binding')
    if hashlib.sha256(encoded(value)).hexdigest()!=expected_sha256:raise ValueError('Pinned lifecycle receipt')
    stamp=datetime.fromisoformat(value['observed_utc']);now=datetime.now(timezone.utc) if now is None else now
    if stamp.tzinfo is None or not 0<=(now-stamp).total_seconds()<=120:raise ValueError('Fresh observed boot binding')
    owners=value['baseline_owners']
    if type(owners) is not list or len(owners)!=2 or len({key(o) for o in owners})!=2 or len({o['pid'] for o in owners})!=2:
        raise ValueError('Two distinct recorded baseline roles')
    if any(o['boot_id']!=value['boot_id'] for o in owners):raise ValueError('Same actual baseline boot')
    for k in ('install_sha256','live_config_sha256','display_config_sha256'):digest(value[k])
    if value['display_config_sha256']!='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b':
        raise ValueError('User-selected270degree display')
    return value
