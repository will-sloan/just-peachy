"""Changed finite runtime preservation check; README_FIELD_RUNTIME_EXPORT_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import json
import os
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();args.output.mkdir();me=psutil.Process()
    (args.output/'REGISTERED_OWNER.json').write_bytes(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode())
    import hashlib,io,copy
    from datetime import datetime,timezone
    from field_runtime_policy_v3 import ROOT,SCHEMA,LIMITS,PROFILES,digest,encoded,validate
    from field_local_release_plan_v2 import allocation
    from field_runtime_preservation_io_v1 import census,send_census,read_census,export_files,receive_files,read_frame
    from field_runtime_auxiliary_v1 import analyze,STDLIB,ENTRY
    import ast
    a=allocation(2,7);raw=b'x = 123\n';now=datetime.now(timezone.utc).isoformat()
    manifest=dict(schema='just-peachy.local-release-manifest.v1',files=[dict(path='code/fixture.py',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())])
    policy=dict(schema=SCHEMA,release_id='field-runtime-v999',manager_root=str(ROOT/'field-runtime-v999'),
        recording_roots=[str(ROOT/('field-operator-sessions-v%d'%n)) for n in (998,999)],
        provisioned_utc=now,allocation=a,limits=copy.deepcopy(LIMITS),runtime_manifest_sha256=digest(manifest),
        installed_manifest_sha256='a'*64,profiles={n:dict(available=False,input_kind='saved' if n.endswith('-saved') else 'microphone',manifest_sha256=None,reason='Synthetic preservation fixture') for n in PROFILES},
        measured_target_bytes=0,measured_host_bytes=0,measured_payload_bytes=0,
        combined_output_cap_bytes=a['combined_request_bytes'],total_payload_cap_bytes=a['combined_request_bytes'],
        storage_semantics=dict(local_backup_before_next=True,pc_copy_deferred_until_connected=True,pc_reservation_independent=True,
            original_preserved=True,copy_not_move=True,failed_deleted_unused_credit=False,automatic_replenishment=False,explicit_reprovision_required=True))
    validate(policy)
    source=args.output/'source';source.mkdir()
    dirs=['code','control','launches','launches/launch-01','recordings','backups','backups/recording-01',
          'backups/recording-01/code','backups/recording-01/broker','backups/recording-01/recordings',
          'backups/recording-02','backups/recording-02/broker']
    for name in dirs:(source/name).mkdir()
    who=dict(pid=123,start_ticks=456,boot_id='11111111-2222-3333-4444-555555555555')
    files={'code/fixture.py':raw,'control/RELEASE.json':encoded(policy),'control/MANIFEST.json':encoded(manifest),
        'launches/launch-01/OWNER.json':encoded(dict(owner=who,policy_sha256=digest(policy),slot='launches/launch-01',utc=now,purpose='USER_RUNTIME_MANAGER')),
        'backups/recording-01/code/fixture.py':raw,'backups/recording-01/broker/STAGE_OWNER.json':encoded(who),
        'backups/recording-02/broker/OWNER.json.pending':b'{"p'}
    for name,value in files.items():(source/name).write_bytes(value)
    def guard():pass
    value=census(source,policy,manifest,guard);wire=io.BytesIO()
    send_census(wire,value,guard);export_files(wire,source,value,policy,guard)
    original=wire.getvalue();wire.seek(0);expected=read_census(wire,policy,manifest,guard)
    result=receive_files(wire,args.output/'mirror',expected,policy,manifest,guard,lambda:True)
    assert result['files']==len(files) and len(value['plan']['partitions'])==3 and len(result['ownership']['records'])==2
    assert wire.read()==b'' and all((args.output/'mirror'/n).read_bytes()==v for n,v in files.items())
    rejects=[]
    def reject(label,fn):
        try:fn()
        except (ValueError,EOFError):rejects.append(label)
        else:raise AssertionError(label)
    reject('truncated-frame',lambda:read_frame(io.BytesIO(b'\0\0\0\x05{}'),guard))
    reject('existing-destination',lambda:receive_files(io.BytesIO(),args.output/'mirror',expected,policy,manifest,guard,lambda:True))
    bad=copy.deepcopy(expected);bad['files']['unknown.json']=dict(bytes=0,sha256=hashlib.sha256(b'').hexdigest())
    reject('unallocated-member-before-mkdir',lambda:receive_files(io.BytesIO(),args.output/'bad-path',bad,policy,manifest,guard,lambda:True))
    assert not (args.output/'bad-path').exists()
    again=io.BytesIO(original);read_census(again,policy,manifest,guard)
    reject('missing-exact-closure',lambda:receive_files(again,args.output/'closure-failed-preserved',expected,policy,manifest,guard,lambda:False))
    assert not list((args.output/'closure-failed-preserved').rglob('BACKUP.json'))
    modules={};todo=[ENTRY];base=Path(__file__).parent
    while todo:
        name=todo.pop()
        if name in modules:continue
        source_text=(base/(name+'.py')).read_bytes().decode();modules[name]=source_text
        for node in ast.walk(ast.parse(source_text)):
            names=[v.name for v in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) else []
            for dependency in names:
                if dependency not in STDLIB and dependency not in modules:todo.append(dependency)
    review=analyze(modules,{n:hashlib.sha256(s.encode()).hexdigest() for n,s in modules.items()})
    receipt=dict(status='PASS_CHANGED_RUNTIME_PARTITION_IO_AND_GRAPH',positive_groups=2,rejects=rejects,
        copy=result,wire_bytes=len(original),graph_modules=len(modules),graph_bytes=sum(len(s.encode()) for s in modules.values()),
        synthetic_policy_identity_and_closure=True,native_executed=False,linux_durability_claimed=False)
    (args.output/'RESULT.json').write_bytes(json.dumps(receipt,indent=2).encode())
    print(json.dumps({k:receipt[k] for k in ('status','positive_groups','rejects','graph_modules','graph_bytes','wire_bytes')}))
if __name__=='__main__':main()

