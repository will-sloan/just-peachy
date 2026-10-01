"""Check changed manager profile dispatch without native execution; README_RUNTIME_PROFILE_DISPATCH_CHECK_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,copy,hashlib,json,os
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone,timedelta


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('bundle','manager','catalog','titanet-manifest','output','scope'):
        ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir();me=psutil.Process()
    (a.output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    scope=json.loads(a.scope.read_bytes())
    if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Scope')
    if sum(p.stat().st_size for p in a.scope.parent.rglob('*') if p.is_file())+65536>scope['maximum_bytes']:raise ValueError('Cumulative budget')
    from field_runtime_profiles_v1 import backend_manifest,titanet_namespace
    from field_runtime_policy_v3 import ROOT,PROFILES,SCHEMA,LIMITS,issue_operation,digest
    from field_local_release_plan_v2 import allocation
    raw=a.bundle.read_bytes();value=json.loads(raw)
    if hashlib.sha256(raw).hexdigest()!='4ec6d0f422bffbcbf85365b39707b6f0942625aeed2989e697f529b5bb051eae':raise ValueError('Selected common capsule')
    files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
    original=json.loads(files['broker/TEMPLATE.json'])
    encode=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    memory={}
    class FixturePath(PurePosixPath):
        def exists(self):return str(self) in memory
    selected={'encoded','sha','strict','profile_descriptor','bundle_for_operation'}
    tree=ast.parse(a.manager.read_bytes())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in selected]
    if len(nodes)!=len(selected):raise ValueError('Actual selected manager functions')
    def read(p,cap=65536):
        data=memory[str(p)]
        if len(data)>cap:raise ValueError('Original member cap')
        return data
    ns=dict(Path=FixturePath,json=json,base64=base64,hashlib=hashlib,MIB=1048576,read=read)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(a.manager)+':actual-functions','exec'),ns)
    now=datetime.now(timezone.utc);owner=dict(pid=50,start_ticks=100,boot_id='11111111-2222-3333-4444-555555555555')
    root=FixturePath(str(ROOT/'field-runtime-v999'))
    plan=allocation(1,4);catalog=a.catalog.read_bytes();tm=a.titanet_manifest.read_bytes()
    profiles={n:dict(available=False,input_kind='saved' if n.endswith('-saved') else 'microphone',manifest_sha256=None,reason='Not part of this fixture') for n in PROFILES}
    policy=dict(schema=SCHEMA,release_id=root.name,manager_root=str(root),recording_roots=[str(ROOT/'field-operator-sessions-v999')],
        provisioned_utc=(now-timedelta(seconds=1)).isoformat(),allocation=plan,limits=copy.deepcopy(LIMITS),
        runtime_manifest_sha256='b'*64,installed_manifest_sha256='c'*64,profiles=profiles,
        measured_target_bytes=100,measured_host_bytes=200,measured_payload_bytes=400,
        combined_output_cap_bytes=300+plan['combined_request_bytes'],total_payload_cap_bytes=400+plan['combined_request_bytes'],
        storage_semantics=dict(local_backup_before_next=True,pc_copy_deferred_until_connected=True,pc_reservation_independent=True,
            original_preserved=True,copy_not_move=True,failed_deleted_unused_credit=False,automatic_replenishment=False,explicit_reprovision_required=True))
    passed=[];rejected=[]
    def reject(name,fn):
        try:fn()
        except (ValueError,RuntimeError):rejected.append(name)
        else:raise AssertionError('Unexpected acceptance '+name)
    for profile in [n for n in PROFILES if not n.endswith('-saved')]:
        definition=backend_manifest(catalog,profile);doc=copy.deepcopy(original['data_files']['n2_runtime.json'])
        galleries={k:dict(root=str(root.with_name(root.name+'-galleries')/k/'people'),
            manifest_path=str(root.with_name(root.name+'-galleries')/k/'MANIFEST.json'),manifest_sha256='9'*64)
            for k in (('E0','E1') if definition['selection']['embedding']=='E1' else ('E0',))}
        if definition['selection']['embedding']=='E1':
            doc.update(titanet_manifest=str(ROOT/'field-runtime-v999-assets/titanet/titanet_manifest.json'),
                titanet_manifest_sha256=hashlib.sha256(tm).hexdigest(),embedding_namespace=titanet_namespace(json.loads(tm)))
        descriptor=dict(schema='just-peachy.runtime-profile-descriptor.v1',profile=profile,template_sha256=hashlib.sha256(raw).hexdigest(),
            runtime_profile=dict(definition=definition,galleries=galleries),runtime_document=doc)
        descriptor_path=str(root.with_name(root.name+'-profiles')/(profile+'.json'))
        memory.clear();memory[descriptor_path]=encode(descriptor)
        profiles[profile]=dict(available=True,input_kind='microphone',manifest_sha256=hashlib.sha256(encode(descriptor)).hexdigest(),reason='')
        memory[str(root.with_name(root.name+'-profiles')/'COMMON_BUNDLE.json')]=raw
        memory[str(root/'control/RELEASE.json')]=encode(policy)
        baseline=copy.deepcopy(json.loads(files['broker/CONFIG.json'])['baseline']);baseline['boot_id']=owner['boot_id']
        activation=dict(schema='just-peachy.runtime-activation.v1',policy_sha256=digest(policy),settings_sha256='d'*64,
            baseline_owners=[owner],baseline_expected='stopped',baseline=baseline,launch_slot=plan['launch_slots'][0])
        memory[str(root/'control/ACTIVATION.json')]=encode(activation)
        memory[str(root/'launches'/plan['launch_slots'][0]/'OWNER.json')]=encode(dict(owner=owner))
        operation=issue_operation(policy,slot=plan['recording_slots'][0],profile=profile,owner=owner,now=now)
        broker,config,manifest,generated=ns['bundle_for_operation'](root,policy,operation)
        t=json.loads(generated['broker/TEMPLATE.json'])
        assert broker['profile']==profile and broker['mode']==definition['selection']['engine_mode']
        assert t['admission']['runtime_profile']==descriptor['runtime_profile'] and t['data_files']['n2_runtime.json']==doc
        assert manifest['files']==[dict(path=n,bytes=len(r),sha256=hashlib.sha256(r).hexdigest()) for n,r in sorted(generated.items())]
        assert len([n for n in generated if n.startswith('code/')])==64
        passed.append(profile)
    # Last profile fixture: source-hash drift must fail before any staging.
    memory[descriptor_path]+=b' '
    reject('descriptor-byte-drift',lambda:ns['bundle_for_operation'](root,policy,operation))
    memory[descriptor_path]=encode(descriptor)
    memory[str(root.with_name(root.name+'-profiles')/'COMMON_BUNDLE.json')]+=b' '
    reject('shared-code-drift',lambda:ns['bundle_for_operation'](root,policy,operation))
    memory[str(root.with_name(root.name+'-profiles')/'COMMON_BUNDLE.json')]=raw
    changed=copy.deepcopy(descriptor);changed['runtime_document']['titanet_manifest']='unwanted'
    memory[descriptor_path]=encode(changed)
    policy['profiles'][profile]['manifest_sha256']=hashlib.sha256(encode(changed)).hexdigest()
    reject('E0-acquires-E1-dependency',lambda:ns['profile_descriptor'](root,policy,profile))
    result=dict(status='PASS_CHANGED_SIX_LIVE_PROFILE_DISPATCH',profiles=passed,rejects=rejected,
        actual_extracted_manager_functions=True,actual_common_capsule=True,
        native_executed=False,model_constructed=False,synthetic_policy_owners_activation_galleries=True,
        memory_read_adapter=True,filesystem_staging_executed=False)
    out=(json.dumps(result,indent=2)+'\n').encode()
    with (a.output/'RESULT.json').open('xb') as f:f.write(out);f.flush();os.fsync(f.fileno())
    assert (a.output/'RESULT.json').read_bytes()==out
    print(json.dumps(dict(status=result['status'],profiles=len(passed),rejects=len(rejected))))


if __name__=='__main__':main()

