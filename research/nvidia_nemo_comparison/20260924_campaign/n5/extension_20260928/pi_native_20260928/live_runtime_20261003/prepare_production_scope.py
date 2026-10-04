"""Local exact scope from actual discovery; README_PRODUCTION_SCOPE.md."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import time


def build_scope(discovery, assets, maximum_payload_bytes, runtime_seconds):
    if (discovery.get('schema')!='just-peachy.production-scope-discovery.v1' or
        discovery.get('scope_locked_during_discovery') is not True or discovery.get('issues')):
        raise ValueError('Complete actually observed locked scope required')
    missing=discovery.get('missing_known_roots',[]);proofs=discovery.get('slot_absence_proofs',[])
    for row in missing:
        matches=[proof for proof in proofs if proof.get('source')==row['path']]
        if (len(matches)!=1 or matches[0].get('eligible') is not True or
            matches[0].get('state') not in ('UNUSED_NEVER_STARTED','RESERVED_NEVER_STARTED') or
            not all(matches[0].get(key) is True for key in ('root_absent','backup_absent','no_start_owner_or_data_receipts'))):
            raise ValueError('Unresolved missing known root; exact unused/reserved never-started journal proof required')
    roots=discovery['roots'];members=discovery['members']
    if not 1<=len(roots)<=64 or len(members)>4096:raise ValueError('Current bounded complete scope required')
    by_path={row['path']:row for row in members}
    if len(by_path)!=len(members):raise ValueError('Duplicate discovery source')
    from desktop_consolidation_action import OWNED
    # Test fixtures may use a private synthetic home; derive the common Desktop
    # parent only from observed members, never invent an absent source path.
    portable=[PurePosixPath(path.replace('\\','/')) for path in by_path]
    desktop_members=[path for path in portable if path.parent.name=='Desktop']
    if not set(OWNED)<=set(path.name for path in desktop_members):
        raise ValueError('All11 known retained Desktop files must be present in current scope')
    if type(assets) is not list or len(assets)>128:raise ValueError('Bounded explicit immutable model references required')
    external=0;seen=set()
    for row in assets:
        path=row['path'];sha=row['sha256']
        if (path in seen or path not in by_path or row.get('resolved_path')!=path or
            type(row.get('bytes')) is not int or row['bytes']!=by_path[path]['bytes'] or
            not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha)):
            raise ValueError('External model reference must match actual current discovered extent and exact pin')
        if PurePosixPath(path).suffix.lower() not in ('.onnx','.ort','.pt','.pth','.bin','.safetensors','.tflite'):
            raise ValueError('Only explicitly pinned immutable model weights may be external references')
        seen.add(path);external+=row['bytes']
    estimated=sum(row['bytes'] for row in members)-external
    if type(maximum_payload_bytes) is not int or maximum_payload_bytes<estimated or maximum_payload_bytes<=0:
        raise ValueError('Independent full-copy reservation must cover all observed non-model bytes')
    if type(runtime_seconds) is not int or not 180<=runtime_seconds<=3600:raise ValueError('Finite180..3600second snapshot lifetime required')
    spec=dict(schema='just-peachy.production-backup-scope.v1',reviewed=True,
        roots=[dict(source=row['source'],destination=row['destination']) for row in roots],
        external_assets=assets,maximum_payload_bytes=maximum_payload_bytes,
        maximum_external_asset_bytes=external,runtime_seconds=runtime_seconds)
    if proofs:spec['absent_reserved_slots']=proofs
    return spec,dict(observed_nonmodel_bytes=estimated,external_model_bytes=external,
        current_files=len(members),current_roots=len(roots),explicit_absent_unused_slots=proofs,complete_backup_claimed=False)


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
    value=json.loads(raw);discovery=value.get('action_result',value)
    spec,summary=build_scope(discovery,json.loads(pins_raw),args.maximum_payload_bytes,args.runtime_seconds)
    # Import only after the actual CPU14 owner is durable; this is a pure check.
    from backup_external_common import validate_native_source
    from launch_backup_external_action import external_bytes, COMMON_SHA256, COMMON_BYTES, SCHEMA
    unsupported=[]
    for row in discovery['roots']:
        is_file=row['source'] in {member['path'] for member in discovery['members']}
        try:validate_native_source(row['source'],is_file=is_file)
        except ValueError:unsupported.append(row['source'])
    save('SCOPE.json',spec)
    common_raw=Path(__file__).with_name('backup_external_common.py').read_bytes()
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
