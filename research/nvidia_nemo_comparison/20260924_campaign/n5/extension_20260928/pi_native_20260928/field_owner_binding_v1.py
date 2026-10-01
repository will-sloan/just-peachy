"""Lossless bounded owner admission; README_FIELD_OPERATOR_NATIVE_V1.md."""
import hashlib
import json
import re
SCHEMA='just-peachy.compact-pi-owners.v1'
MAXIMUM=1024
MAX_BYTES=32768
def encoded(value):
    return json.dumps(value,separators=(',',':'),sort_keys=True,allow_nan=False).encode()
def decode(value):
    if type(value) is not dict or set(value)!={'schema','count','boots','sha256'} or value['schema']!=SCHEMA:
        raise ValueError('Exact compact owner schema required')
    if type(value['count']) is not int or not 1<=value['count']<=MAXIMUM or len(encoded(value))>MAX_BYTES:
        raise ValueError('Owner cardinality/bytes')
    boots=value['boots']
    if type(boots) is not list or not 1<=len(boots)<=16:raise ValueError('Boot cardinality')
    result=[];seen=set();boot_seen=set()
    for group in boots:
        if type(group) is not dict or set(group)!={'boot_id','members'}:raise ValueError('Exact boot group')
        boot=group['boot_id'];members=group['members']
        if type(boot) is not str or not re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot) or boot in boot_seen:
            raise ValueError('Boot identity')
        boot_seen.add(boot)
        if type(members) is not list or not 1<=len(members)<=MAXIMUM:raise ValueError('Member cardinality')
        for pair in members:
            if type(pair) is not list or len(pair)!=2 or any(type(x) is not int or not 0<x<2**63 for x in pair):
                raise ValueError('Exact PID/start ticks')
            key=(boot,*pair)
            if key in seen:raise ValueError('Duplicate identity')
            seen.add(key);result.append(dict(boot_id=boot,pid=pair[0],start_ticks=pair[1]))
    if len(result)!=value['count']:raise ValueError('Owner count mismatch')
    canonical=sorted(result,key=lambda x:(x['boot_id'],x['pid'],x['start_ticks']))
    if result!=canonical or hashlib.sha256(encoded(canonical)).hexdigest()!=value['sha256']:
        raise ValueError('Owner canonical order/digest')
    return result
def pack(owners):
    if type(owners) is not list or not 1<=len(owners)<=MAXIMUM:raise ValueError('Owner cardinality')
    rows=[];seen=set()
    for row in owners:
        if type(row) is not dict or not {'boot_id','pid','start_ticks'}<=set(row):
            raise ValueError('Exact process identity required; typed closures are separate')
        item={key:row[key] for key in ('boot_id','pid','start_ticks')}
        key=(item['boot_id'],item['pid'],item['start_ticks'])
        if key in seen:raise ValueError('Deduplicate provenance explicitly before binding')
        seen.add(key);rows.append(item)
    rows.sort(key=lambda x:(x['boot_id'],x['pid'],x['start_ticks']))
    groups={}
    for row in rows:groups.setdefault(row['boot_id'],[]).append([row['pid'],row['start_ticks']])
    value=dict(schema=SCHEMA,count=len(rows),boots=[dict(boot_id=b,members=m) for b,m in groups.items()],
               sha256=hashlib.sha256(encoded(rows)).hexdigest())
    if decode(value)!=rows:raise ValueError('Lossless owner binding failed')
    return value
