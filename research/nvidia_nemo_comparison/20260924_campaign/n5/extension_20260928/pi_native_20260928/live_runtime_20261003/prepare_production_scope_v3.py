"""Decode bounded discovery transport into current scope. README_PRODUCTION_SCOPE_V3.md."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import time
import zlib


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate discovery JSON field')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite discovery JSON')))


def decode_discovery(transport):
    fields={'schema','encoding','uncompressed_bytes','sha256','payload'}
    if (type(transport) is not dict or set(transport)!=fields or
        transport['schema']!='just-peachy.production-scope-transport.v1' or transport['encoding']!='zlib-base64'):
        raise ValueError('Exact bounded compressed discovery envelope required')
    size=transport['uncompressed_bytes'];sha=transport['sha256'];payload=transport['payload']
    if (type(size) is not int or not 1<=size<=2*1024**2 or not isinstance(sha,str) or
        len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha) or
        not isinstance(payload,str) or not 1<=len(payload)<=65536):
        raise ValueError('Finite discovery extent/hash/payload required')
    compressed=base64.b64decode(payload,validate=True)
    decoder=zlib.decompressobj()
    raw=decoder.decompress(compressed,size+1)
    if (len(raw)!=size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or
        hashlib.sha256(raw).hexdigest()!=sha):
        raise ValueError('Discovery compressed extent, EOF or SHA differs')
    value=strict_json(raw)
    if type(value) is not dict or value.get('schema')!='just-peachy.production-scope-discovery.v2':
        raise ValueError('Indexed discovery.v2 required exactly once')
    roots=value.get('roots');members=value.get('members')
    if type(roots) is not list or not 1<=len(roots)<=64 or type(members) is not list or len(members)>4096:
        raise ValueError('Finite complete indexed discovery required')
    root_paths=[]
    for row in roots:
        source=row.get('source') if type(row) is dict else None
        if not isinstance(source,str) or len(source)>2048:
            raise ValueError('Bounded canonical discovery root required')
        path=PurePosixPath(source)
        if (not path.is_absolute() or str(path)!=source or '..' in path.parts or
            any(c in source for c in '\\\x00') or any(ord(c)<32 for c in source)):
            raise ValueError('Canonical absolute POSIX discovery root required')
        if any(path==prior or path in prior.parents or prior in path.parents for prior in root_paths):
            raise ValueError('Indexed roots overlap')
        root_paths.append(path)
    decoded=[];seen=set();per_root={};root_file=set();total=0
    for row in members:
        if type(row) is not dict or set(row)!={'root_index','relative','bytes'}:
            raise ValueError('Exact indexed member fields required')
        index=row['root_index'];relative=row['relative'];size=row['bytes']
        if (type(index) is not int or not 0<=index<len(roots) or not isinstance(relative,str) or
            len(relative)>1024 or type(size) is not int or not 0<=size<2**63):
            raise ValueError('Bounded indexed member required')
        if relative:
            path=PurePosixPath(relative)
            if (path.is_absolute() or str(path)!=relative or '..' in path.parts or
                any(c in relative for c in '\\\x00') or any(ord(c)<32 for c in relative)):
                raise ValueError('Canonical relative discovery member required')
            full=str(root_paths[index]/path)
        else:
            full=str(root_paths[index]);root_file.add(index)
        per_root[index]=per_root.get(index,0)+1
        if full in seen:raise ValueError('Duplicate decoded discovery member')
        seen.add(full);decoded.append(dict(path=full,bytes=size));total+=size
    if any(per_root[index]!=1 for index in root_file):
        raise ValueError('Exact root-file member cannot have descendants')
    if (type(value.get('total_files')) is not int or value['total_files']!=len(decoded) or
        type(value.get('total_bytes')) is not int or value['total_bytes']!=total):
        raise ValueError('Indexed discovery total differs')
    result=dict(value,schema='just-peachy.production-scope-discovery.v1',members=decoded)
    result['source_discovery_transport']={key:transport[key] for key in ('schema','encoding','uncompressed_bytes','sha256')}
    result['source_discovery_transport']['payload_sha256']=hashlib.sha256(compressed).hexdigest()
    result['source_discovery_transport']['inner_schema']=value['schema']
    result['indexed_members_sha256']=hashlib.sha256(json.dumps(members,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--discovery',type=Path,required=True)
    ap.add_argument('--external-model-pins',type=Path,required=True)
    ap.add_argument('--maximum-payload-bytes',type=int,required=True)
    ap.add_argument('--runtime-seconds',type=int,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--package',required=True)
    ap.add_argument('--package-manifest-sha256',required=True)
    ap.add_argument('--label',required=True)
    args=ap.parse_args()
    import psutil
    me=psutil.Process();me.cpu_affinity([14]);args.output.mkdir()
    def write(name,raw):
        with (args.output/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short production-scope preparation')
            stream.flush();os.fsync(stream.fileno())
        if (args.output/name).read_bytes()!=raw:raise OSError('Scope readback mismatch')
    def save(name,value):write(name,json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    raw=args.discovery.read_bytes();pins_raw=args.external_model_pins.read_bytes()
    if len(raw)>16*1024**2 or len(pins_raw)>65536:raise ValueError('Finite reviewed preparation inputs required')
    value=strict_json(raw);transport=value.get('action_result',value);discovery=decode_discovery(transport)
    from prepare_production_scope_v2 import build_scope
    spec,summary=build_scope(discovery,json.loads(pins_raw),args.maximum_payload_bytes,args.runtime_seconds)
    spec['discovery_evidence_sha256']=hashlib.sha256(raw).hexdigest()
    spec['source_discovery_transport']=discovery['source_discovery_transport']
    spec['indexed_members_sha256']=discovery['indexed_members_sha256']
    spec['selected_assets_evidence_sha256']=hashlib.sha256(pins_raw).hexdigest()
    # Import only after the actual CPU14 owner is durable; this is a pure check.
    from backup_external_common_v2 import validate_native_source
    from launch_backup_external_action_v2 import external_bytes, COMMON_SHA256, COMMON_BYTES, SCHEMA
    unsupported=[]
    for row in discovery['roots']:
        is_file=row['source'] in {member['path'] for member in discovery['members']}
        try:validate_native_source(row['source'],is_file=is_file)
        except ValueError:unsupported.append(row['source'])
    save('SCOPE.json',spec)
    common_raw=Path(__file__).with_name('backup_external_common_v2.py').read_bytes()
    external=dict(schema=SCHEMA,sha256=COMMON_SHA256,bytes=COMMON_BYTES,base64=base64.b64encode(common_raw).decode())
    external_bytes(dict(external_backup_common=external))
    payload=dict(package=args.package,package_manifest_sha256=args.package_manifest_sha256,
        boot_id=discovery['boot_id'],expires_unix=time.time()+600,label=args.label,
        maximum_output_bytes=16*1024**2,full_backup_reservation_bytes=args.maximum_payload_bytes,
        backup_scope=spec,backup_scope_sha256=hashlib.sha256((args.output/'SCOPE.json').read_bytes()).hexdigest(),
        external_backup_common=external)
    save('PAYLOAD.json',payload)
    write('EXTERNAL_COMMON.py.backup',common_raw);write('EXTERNAL_COMMON.py.restore',common_raw)
    for name,blob in (('DISCOVERY',raw),('MODEL_PINS',pins_raw)):
        write(name+'.backup',blob);write(name+'.restore',blob)
    summary.update(scope_sha256=hashlib.sha256((args.output/'SCOPE.json').read_bytes()).hexdigest(),
        discovery_sha256=hashlib.sha256(raw).hexdigest(),unsupported_current_guard_roots=unsupported,
        ready_for_guard=not unsupported,native_executed=False)
    save('PREPARATION.json',summary);print(json.dumps(summary))
    if unsupported:raise SystemExit('Preserved complete scope; exact guard extension required before transfer')


if __name__=='__main__':main()
