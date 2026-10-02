"""Controlled native runtime installer and receiver; README_RUNTIME_INSTALL_V15.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,hashlib,json,os,re,shlex,shutil,sys,time,zlib
from pathlib import Path
from datetime import datetime,timezone,timedelta
MIB=1024**2
TOTAL=88696429
EXTERNAL_TARGET=89745005+(8+4+2)*MIB
EXTERNAL_HOST=181587162+2*(8+4+2)*MIB+4*MIB
ALLOCATION=dict(target_bytes=1218482528+EXTERNAL_TARGET,host_bytes=1235259744+EXTERNAL_HOST,
 combined_bytes=2453742272+EXTERNAL_TARGET+EXTERNAL_HOST)

def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('local','private','assets','prior-closure','inspection','output','scope','inputs'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--version',type=int,required=True)
    a=ap.parse_args()
    if a.version<1 or a.output.parent!=a.private:raise ValueError('New private installation output required')
    a.output.mkdir()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    def put(name,raw):
        if type(raw) is not bytes or len(raw)>262144:raise ValueError('Metadata cap')
        with (a.output/name).open('xb') as f:
            if f.write(raw)!=len(raw):raise OSError('Short metadata write')
            f.flush();os.fsync(f.fileno())
        if (a.output/name).read_bytes()!=raw:raise IOError('Metadata readback')
    def save(name,v):put(name,encoded(v))
    save('REGISTERED_OWNER.json',owner)
    scope=json.loads(a.scope.read_bytes())
    last=[0.]
    def guard():
        if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Preparation scope expired')
        if datetime.now(timezone.utc)>=datetime(2026,10,2,14,14,20,tzinfo=timezone.utc):raise TimeoutError('User deadline')
        if time.monotonic()-last[0]<2:return
        last[0]=time.monotonic()
        for drive,floor in [('C:/',50*1024**3),('G:/',75*1024**3)]:
            if shutil.disk_usage(drive).free<floor+ALLOCATION['host_bytes']:raise RuntimeError('Full host reserve')
        if sum(p.stat().st_size for p in a.output.rglob('*') if p.is_file())>ALLOCATION['host_bytes']:raise RuntimeError('Independent host allocation')
    guard()
    from field_runtime_host_precheck_v2 import inspect
    pre,details=inspect(a.local,a.private,current_owner=owner,deadline=time.monotonic()+100,guard=guard)
    save('HOST_PRECHECK.json',pre);save('HOST_PRECHECK_DETAILS.json',details)
    if pre['alive_owners']:raise RuntimeError('Other registered host owner remains alive')
    from field_runtime_profiles_v1 import verify_titanet
    assets=verify_titanet(a.assets,deadline=time.monotonic()+60,guard=guard)
    rows={r['name']:{k:r[k] for k in ('bytes','sha256')} for r in assets['files']}
    if sum(r['bytes'] for r in rows.values())!=TOTAL:raise ValueError('Exact prior asset export')

    # Reuse the independently restored prior model assets; retain both old copies.
    for name,row in rows.items():
        second=a.assets.parent/'assets-backup'/name
        for source in (a.assets/name,second):
            with source.open('rb') as f:
                if source.stat().st_size!=row['bytes'] or hashlib.file_digest(f,'sha256').hexdigest()!=row['sha256']:
                    raise IOError('Existing independent model restore changed')
    inputs=json.loads((a.inputs/'INSTALL_INPUTS.json').read_bytes())
    if a.version!=12 or inputs['release_id']!='field-runtime-v1':
        raise ValueError('This first installer binds the unused prepared release1; never retry a consumed root')
    rid='field-runtime-v12';native_root=inputs['manager_root'].rsplit('/',1)[0]+'/'+rid;asset_root='runtime-titanet-v3'
    from field_runtime_policy_v3 import validate,LIMITS,SCHEMA
    from field_local_release_plan_v2 import allocation
    from field_runtime_profiles_v1 import ROOT
    source_directory=Path(__file__).parent
    source_closed={}
    for version in (32,33,35,40,44,45,52,58,64,66,72,76,78,80,87,89,92,95):
        source_closed.update(json.loads((a.scope.parent/('SOURCE_CLOSED_V'+str(version)+'.json')).read_bytes())['files'])
    source_bytes={}
    for name in ('field_runtime_manager_v7.py','field_runtime_activation_v2.py','prepare_runtime_activation_v4.py','field_runtime_install_native_v4.py','field_runtime_start_barrier_v1.py','field_runtime_archive_encoding_v1.py','field_runtime_source_failure_v1.py','field_runtime_broker_close_v1.py','field_runtime_archive_partition_v1.py','field_runtime_recording_controls_v2.py','field_runtime_saved_modes_v3.py','field_runtime_optional_health_v1.py','field_runtime_titanet_memory_v1.py'):
        raw=(source_directory/name).read_bytes()
        if source_closed[name]!=dict(bytes=len(raw),sha256=sha(raw)):raise ValueError('Exact backed current source')
        compile(raw,name,'exec');source_bytes[name]=raw
    bundle_raw=(a.inputs/'MANAGER_BUNDLE.json').read_bytes()
    if sha(bundle_raw)!='f1df34cf1bf93b5b583a0df3d8d6339580f6633494a16d66cdc702312f8107a4':raise ValueError('Backed manager3 capsule')
    bundle=json.loads(bundle_raw)
    manager={n:base64.b64decode(v,validate=True) for n,v in bundle['files'].items()}
    if bundle['manifest']['files']!=[dict(path=n,bytes=len(r),sha256=sha(r)) for n,r in sorted(manager.items())]:raise ValueError('Complete old manager')
    manager.pop('code/field_runtime_manager_v3.py')
    manager['code/field_runtime_manager_v7.py']=source_bytes['field_runtime_manager_v7.py']
    from field_runtime_optional_health_v1 import derive as optional_health
    manager['code/field_operator_health_v1.py']=optional_health(manager['code/field_operator_health_v1.py'])
    if len(manager)!=16 or sum(map(len,manager.values()))>2*MIB or any(len(v)>131072 for v in manager.values()):raise ValueError('Manager bounds')
    manager_manifest=dict(schema='just-peachy.local-release-manifest.v1',
        files=[dict(path=n,bytes=len(r),sha256=sha(r)) for n,r in sorted(manager.items())])
    common_path=Path(inputs['common_bundle']['path']);common_raw=common_path.read_bytes()
    if sha(common_raw)!='4ec6d0f422bffbcbf85365b39707b6f0942625aeed2989e697f529b5bb051eae':raise ValueError('Pinned common six-profile capsule')
    from field_runtime_start_barrier_v1 import derive
    common_raw,barrier_review=derive(common_raw)
    save('START_BARRIER_BINDING.json',barrier_review)
    from field_runtime_archive_encoding_v1 import derive as compact_archive
    common_raw,archive_review=compact_archive(common_raw)
    save('ARCHIVE_ENCODING_BINDING.json',archive_review)
    from field_runtime_source_failure_v1 import derive as source_failure_receipt
    common_raw,source_failure_review=source_failure_receipt(common_raw)
    save('SOURCE_FAILURE_RECEIPT_BINDING.json',source_failure_review)
    from field_runtime_broker_close_v1 import derive as broker_close
    common_raw,close_review=broker_close(common_raw)
    save('BROKER_CLOSE_BINDING.json',close_review)
    from field_runtime_archive_partition_v1 import derive as archive_partition
    common_raw,partition_review=archive_partition(common_raw)
    save('ARCHIVE_PARTITION_BINDING.json',partition_review)
    from field_runtime_recording_controls_v2 import derive as recording_controls
    common_raw,recording_review=recording_controls(common_raw)
    save('RECORDING_CONTROLS_BINDING.json',recording_review)
    from field_runtime_saved_modes_v3 import derive as saved_modes,ENDPOINT_PINS
    endpoint_sources={m:(source_directory/('d1_endpoint_contract_v'+str(v[0])+'.py')).read_bytes() for m,v in ENDPOINT_PINS.items()}
    endpoint_contracts={m:(source_directory/('D1_ENDPOINT_CONTRACT_V'+str(v[0])+'.json')).read_bytes() for m,v in ENDPOINT_PINS.items()}
    common_raw,saved_review=saved_modes(common_raw,endpoint_sources,endpoint_contracts)
    save('SAVED_MODES_BINDING.json',saved_review)
    from field_runtime_titanet_memory_v1 import derive as titanet_memory
    common_raw,memory_review=titanet_memory(common_raw)
    save('TITANET_MEMORY_BINDING.json',memory_review)
    common=json.loads(common_raw)
    config=json.loads(base64.b64decode(common['files']['broker/CONFIG.json'],validate=True))
    prepared={rid+'/'+name:raw for name,raw in manager.items()}
    prepared[rid+'-profiles/COMMON_BUNDLE.json']=common_raw
    generated={}
    original_profile_pins={name:row['manifest_sha256'] for name,row in inputs['profiles'].items()}
    from field_runtime_profiles_v1 import backend_manifest,runtime_document
    installed_host=a.private/'field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12'
    catalog_raw=(installed_host/'config/backends.json').read_bytes()
    installed_manifest=json.loads((installed_host/'RELEASE_MANIFEST.json').read_bytes())
    catalog_pin=next(r for r in installed_manifest['files'] if r['path']=='config/backends.json')
    if sha(catalog_raw)!=catalog_pin['sha256']:raise ValueError('Preserved actual backend catalogue')
    mode_catalog=base64.b64decode(common['files']['code/D1_MODE_CATALOG_V1.json'],validate=True)
    for profile,row in inputs['profiles'].items():
        if profile.endswith('-saved'):
            base_profile='d1-delayed-titanet' if 'titanet' in profile else 'd1-delayed'
            raw=(a.inputs/'profiles'/(base_profile+'.json')).read_bytes()
            if sha(raw)!=original_profile_pins[base_profile]:raise ValueError('Exact existing embedding profile')
            descriptor=json.loads(raw)
            descriptor['profile']=profile
            descriptor['runtime_profile']['definition']=backend_manifest(catalog_raw,profile)
            opts=dict(d1_catalog_raw=mode_catalog)
            if 'titanet' in profile:
                opts.update(native_titanet_manifest=inputs['titanet_manifest']['path'],titanet_manifest_raw=(a.assets/'titanet_manifest.json').read_bytes())
            descriptor['runtime_document']=runtime_document(descriptor['runtime_document'],profile,**opts)
            row.update(available=True,reason='')
            generated[profile]=dict(source_profile=base_profile,selected_mode=descriptor['runtime_profile']['definition']['selection']['engine_mode'])
        else:
            if not row['available']:raise ValueError('Existing microphone profile unavailable')
            raw=(a.inputs/'profiles'/(profile+'.json')).read_bytes()
            if sha(raw)!=row['manifest_sha256']:raise ValueError('Prepared profile changed')
            descriptor=json.loads(raw)
        descriptor['template_sha256']=sha(common_raw)
        old_root=inputs['manager_root']
        for gallery in descriptor['runtime_profile']['galleries'].values():
            for key in ('root','manifest_path'):
                if not gallery[key].startswith(old_root+'-galleries/'):raise ValueError('Original gallery path')
                gallery[key]=native_root+gallery[key][len(old_root):]
        document=descriptor['runtime_document']
        if 'titanet_manifest' in document:
            if document['titanet_manifest']!=str(ROOT)+'/runtime-titanet-v2/titanet_manifest.json':raise ValueError('Original asset path')
            document['titanet_manifest']=str(ROOT)+'/'+asset_root+'/titanet_manifest.json'
        raw=encoded(descriptor);row['manifest_sha256']=sha(raw)
        prepared[rid+'-profiles/'+profile+'.json']=raw
    save('SAVED_PROFILE_DERIVATION.json',dict(profiles=generated,actual_native_qualified=False,full_original_allocation=True))
    sources={asset_root+'/'+name:a.assets/name for name in rows}
    for label in ('stage-backup','stage-restore'):
        for name,raw in prepared.items():
            path=a.output/label/name;path.parent.mkdir(exist_ok=True,parents=True)
            with path.open('xb') as f:
                for offset in range(0,len(raw),16384):
                    block=raw[offset:offset+16384]
                    if f.write(block)!=len(block):raise IOError('Short code backup')
                f.flush();os.fsync(f.fileno())
            if path.read_bytes()!=raw:raise IOError('Independent code restore readback')
    sources.update({name:a.output/'stage-restore'/name for name in prepared})
    rows={name:dict(bytes=path.stat().st_size,sha256=sha(path.read_bytes()))
          for name,path in sources.items() if not name.startswith(asset_root+'/')}|{asset_root+'/'+n:v for n,v in rows.items()}
    if len(rows)>96:raise ValueError('Finite staged file count')

    # Existing census implementation, no obsolete window/admission invocation.
    sys.path.insert(0,str(Path(__file__).parent.parent))
    from window_guard import payload_inventory
    inventory=payload_inventory(a.local)
    if inventory['errors']:raise RuntimeError('Incomplete host payload census')
    prior=json.loads((a.local/'n5/d1-anonymous-lifecycle-parent-v4/ADMISSION.json').read_bytes())['census']
    old_census_raw=Path(prior['path']).read_bytes()
    if sha(old_census_raw)!=prior['sha256']:raise ValueError('Historical reparse inventory pin')
    retained=json.loads(old_census_raw)['inventory']['reparse_not_traversed']
    if set(inventory['reparse_not_traversed'])!=set(retained):raise ValueError('New unreviewed reparse paths')
    used=0
    for rel in ('n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928'):
        item=payload_inventory(a.local/rel)
        if item['errors'] or item['reparse_not_traversed']:raise ValueError('Output inventory incomplete')
        used+=item['total_logical_bytes']
    observed=json.loads((a.inspection/'RESULT.json').read_bytes())
    baseline=dict(boot_id=observed['boot_id'],
        owners=[{k:r[k] for k in ('pid','start_ticks','boot_id')} for r in observed['current_project_processes']
                if 'launch_current.py' in r['cmdline'] or '/main.py ' in r['cmdline']],
        config_pins={r['path']:r['sha256'] for r in observed['files']})
    if len(baseline['owners'])!=2:raise ValueError('Exact actual current baseline pair')
    accounting=dict(host_window_bytes=used,host_payload_bytes=inventory['total_logical_bytes'],target_bytes=observed['target_bytes'])
    # Prospective measured allowance; no old WINDOW or closed policy is changed.
    margin=8*MIB
    accounting['combined_cap']=((used+observed['target_bytes']+ALLOCATION['combined_bytes']+margin+MIB-1)//MIB)*MIB
    accounting['payload_cap']=((inventory['total_logical_bytes']+2684354560+observed['target_bytes']+ALLOCATION['combined_bytes']+margin+MIB-1)//MIB)*MIB
    save('HOST_CENSUS.json',dict(utc=datetime.now(timezone.utc).isoformat(),accounting=accounting,allocation=ALLOCATION,
        retained_reservations_bytes=2684354560,inventory_sha256=sha(encoded(inventory)),reparse_paths_unchanged=True,
        original_window_unchanged=True,physical_bytes_credited=0))

    plan=allocation(4,16)
    policy=dict(schema=SCHEMA,release_id=rid,manager_root=native_root,
        recording_roots=[str(ROOT)+'/field-operator-sessions-v'+str(n) for n in (245,246,247,248)],
        provisioned_utc=datetime.now(timezone.utc).isoformat(),allocation=plan,limits=LIMITS,
        runtime_manifest_sha256=sha(encoded(manager_manifest)),
        installed_manifest_sha256=config['installed_manifest_sha256'],profiles=inputs['profiles'],
        measured_target_bytes=observed['target_bytes'],measured_host_bytes=used,
        measured_payload_bytes=inventory['total_logical_bytes']+2684354560+observed['target_bytes'],
        combined_output_cap_bytes=accounting['combined_cap'],total_payload_cap_bytes=accounting['payload_cap'],
        storage_semantics=dict(local_backup_before_next=True,pc_copy_deferred_until_connected=True,
            pc_reservation_independent=True,original_preserved=True,copy_not_move=True,
            failed_deleted_unused_credit=False,automatic_replenishment=False,explicit_reprovision_required=True))
    validate(policy)
    save('RELEASE.json',policy);save('MANIFEST.json',manager_manifest)
    save('SOURCE_ASSET_BACKUP.json',dict(files=rows,model_copies=[str(a.assets),str(a.assets.parent/'assets-backup')],
        code_copies=['stage-backup','stage-restore'],exact_independent_readbacks=True))

    old=json.loads(a.prior_closure.read_bytes());identities={}
    for row in old['owners']+old['additional_registered_owners']:
        v={k:row['owner'][k] for k in ('pid','start_ticks','boot_id')}
        identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    for v in [old['utility_owner']]+[json.loads(p.read_bytes()) for p in a.scope.parent.glob('install-inspection-v*/NATIVE_OWNER.json')]:
        identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    later=list(a.private.glob('runtime-titanet-v*-install/NATIVE_OWNER.json'))+list(a.private.glob('runtime-titanet-v*-install/CLOSURE_OWNER.json'))
    later+=list(a.private.glob('field-runtime-v*-offload-v*/NATIVE_OWNER.json'))
    for path in later:
        v=json.loads(path.read_bytes())
        identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    from field_local_manager_owners_v1 import identity
    late_paths=list(a.scope.parent.glob('candidate*/NATIVE_OWNER.json'))+list(a.private.glob('field-runtime-v*-preservation*/NATIVE_OWNER.json'))
    late_paths+=list(a.private.glob('field-runtime-v*-install/NATIVE_OWNER.json'))+list(a.private.glob('field-runtime-v*-install/CLOSURE_OWNER.json'))
    for path in late_paths:
        v=identity(json.loads(path.read_bytes()))
        identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    if len(identities)>1024:raise ValueError('Prior owner cap')
    historical={row['path'].split('/nemotron-20260928/',1)[1]:row['owner'] for row in old['owners']
        if set(row['owner'])!={'pid','start_ticks','boot_id'}}
    nested={
      'field-local-release-v1/launches/launch-01/OWNER.json':dict(sha256='6fe6f5b378e2ef6c66f89b8cf32cb75c93f7f7216a4e1454d1bacb2030707fbe',policy_sha256='d8600a564dc41641ab799b1f64dc977a9ef719c8c3a45847d00cd6a5023dd454',slot='launches/launch-01',purpose='METADATA_QUALIFICATION_ONLY'),
      'field-local-release-v1/launches/launch-02/OWNER.json':dict(sha256='2c3dbd0f2c4c6a9e80499346a4fac8a306865ea759849786993850fe4e65bc15',policy_sha256='d8600a564dc41641ab799b1f64dc977a9ef719c8c3a45847d00cd6a5023dd454',slot='launches/launch-02',purpose='METADATA_QUALIFICATION_ONLY')}
    tree=ast.parse((Path(__file__).parent/'collect_native_closure_v19.py').read_text(encoding='utf-8'))
    constants=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'NEW_NESTED=' in n.value]
    if len(constants)!=1:raise ValueError('Historical collector constant')
    assignment=next(n for n in ast.parse(constants[0]).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NEW_NESTED' for t in n.targets))
    for path,row in ast.literal_eval(assignment.value).items():
        nested[path]={**row,'policy_sha256':'f39a8b7dbedbebed1492687d42d5648ac033dbba0d02a4a46537175e1fa40d9c'}
    preserved=a.private/'field-runtime-v2-preservation-v2'
    proof=json.loads((preserved/'BACKUP.json').read_bytes())
    if proof['status']!='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY' or proof['manager_exact_dead'] is not True:
        raise ValueError('Complete prior failure preservation required')
    for number,purpose in ((1,'USER_RUNTIME_MANAGER'),(2,'USER_RUNTIME_STAGE'),(3,'USER_RUNTIME_GATE')):
        relative='field-runtime-v2/launches/launch-%02d/OWNER.json'%number
        raw=(preserved/'tree'/relative).read_bytes();row=json.loads(raw)
        if set(row)!={'owner','policy_sha256','slot','utc','purpose'} or row['purpose']!=purpose or row['slot']!='launches/launch-%02d'%number or row['policy_sha256']!='2e53352f4ba43981e1de283540e139c71b2358ef91272502573476ca36ad7b9d':
            raise ValueError('Exact prior runtime envelope')
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
        nested[relative]=dict(sha256=sha(raw),policy_sha256=row['policy_sha256'],slot=row['slot'],purpose=purpose)
    previous_install=a.private/'field-runtime-v3-install'
    previous_tree=a.private/'field-runtime-v3-preservation-v2'
    backup=json.loads((previous_tree/'BACKUP.json').read_bytes())
    if backup['status']!='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY' or backup['manager_exact_dead'] is not True:raise ValueError('Complete previous failed runtime3 backup')
    previous_policy=(previous_install/'RELEASE.json').read_bytes()
    previous_result=json.loads((previous_install/'RESULT.json').read_bytes())
    if sha(previous_policy)!=previous_result['policy_sha256']:raise ValueError('Actual prior installation policy')
    for number,purpose in ((1,'USER_RUNTIME_MANAGER'),(2,'USER_RUNTIME_STAGE'),(3,'USER_RUNTIME_GATE')):
        relative='field-runtime-v3/launches/launch-%02d/OWNER.json'%number
        raw=(previous_tree/'tree'/relative).read_bytes();row=json.loads(raw)
        if set(row)!={'owner','policy_sha256','slot','utc','purpose'} or row['purpose']!=purpose or row['slot']!='launches/launch-%02d'%number or row['policy_sha256']!=sha(previous_policy):raise ValueError('Exact prior runtime3 owner')
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
        nested[relative]=dict(sha256=sha(raw),policy_sha256=row['policy_sha256'],slot=row['slot'],purpose=purpose)
    previous_install=a.private/'field-runtime-v4-install'
    previous_tree=a.private/'field-runtime-v4-preservation-v1'
    backup=json.loads((previous_tree/'BACKUP.json').read_bytes())
    if backup['status']!='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY' or backup['manager_exact_dead'] is not True:raise ValueError('Complete previous failed runtime4 backup')
    previous_policy=(previous_install/'RELEASE.json').read_bytes()
    previous_result=json.loads((previous_install/'RESULT.json').read_bytes())
    if sha(previous_policy)!=previous_result['policy_sha256']:raise ValueError('Actual prior installation policy')
    for number,purpose in ((1,'USER_RUNTIME_MANAGER'),(2,'USER_RUNTIME_STAGE'),(3,'USER_RUNTIME_GATE')):
        relative='field-runtime-v4/launches/launch-%02d/OWNER.json'%number
        raw=(previous_tree/'tree'/relative).read_bytes();row=json.loads(raw)
        if set(row)!={'owner','policy_sha256','slot','utc','purpose'} or row['purpose']!=purpose or row['slot']!='launches/launch-%02d'%number or row['policy_sha256']!=sha(previous_policy):raise ValueError('Exact prior runtime4 owner')
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
        nested[relative]=dict(sha256=sha(raw),policy_sha256=row['policy_sha256'],slot=row['slot'],purpose=purpose)
    previous_install=a.private/'field-runtime-v5-install'
    previous_tree=a.private/'field-runtime-v5-preservation-v1'
    backup=json.loads((previous_tree/'BACKUP.json').read_bytes())
    if backup['status']!='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY' or backup['manager_exact_dead'] is not True:raise ValueError('Complete previous failed runtime5 backup')
    previous_policy=(previous_install/'RELEASE.json').read_bytes()
    previous_result=json.loads((previous_install/'RESULT.json').read_bytes())
    if sha(previous_policy)!=previous_result['policy_sha256']:raise ValueError('Actual prior installation policy')
    for number,purpose in ((1,'USER_RUNTIME_MANAGER'),(2,'USER_RUNTIME_STAGE'),(3,'USER_RUNTIME_GATE')):
        relative='field-runtime-v5/launches/launch-%02d/OWNER.json'%number
        raw=(previous_tree/'tree'/relative).read_bytes();row=json.loads(raw)
        if set(row)!={'owner','policy_sha256','slot','utc','purpose'} or row['purpose']!=purpose or row['slot']!='launches/launch-%02d'%number or row['policy_sha256']!=sha(previous_policy):raise ValueError('Exact prior runtime5 owner')
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
        nested[relative]=dict(sha256=sha(raw),policy_sha256=row['policy_sha256'],slot=row['slot'],purpose=purpose)
    previous_install=a.private/'field-runtime-v6-install'
    previous_tree=a.private/'field-runtime-v6-preservation-v1'
    backup=json.loads((previous_tree/'BACKUP.json').read_bytes())
    if backup['status']!='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY' or backup['manager_exact_dead'] is not True:raise ValueError('Complete previous failed runtime6 backup')
    previous_policy=(previous_install/'RELEASE.json').read_bytes()
    previous_result=json.loads((previous_install/'RESULT.json').read_bytes())
    if sha(previous_policy)!=previous_result['policy_sha256']:raise ValueError('Actual prior installation policy')
    for number,purpose in ((1,'USER_RUNTIME_MANAGER'),(2,'USER_RUNTIME_STAGE'),(3,'USER_RUNTIME_GATE')):
        relative='field-runtime-v6/launches/launch-%02d/OWNER.json'%number
        raw=(previous_tree/'tree'/relative).read_bytes();row=json.loads(raw)
        if set(row)!={'owner','policy_sha256','slot','utc','purpose'} or row['purpose']!=purpose or row['slot']!='launches/launch-%02d'%number or row['policy_sha256']!=sha(previous_policy):raise ValueError('Exact prior runtime6 owner')
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
        nested[relative]=dict(sha256=sha(raw),policy_sha256=row['policy_sha256'],slot=row['slot'],purpose=purpose)
    previous_install=a.private/'field-runtime-v7-install'
    previous_tree=a.private/'field-runtime-v7-preservation-v1'
    proof=json.loads((previous_tree/'BACKUP.json').read_bytes())
    if proof['status']!='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY' or not proof['manager_exact_dead'] or not proof['native_utility_exact_absent']:raise ValueError('Complete previous runtime7 preservation')
    prior_policy_raw=(previous_install/'RELEASE.json').read_bytes();prior_policy=json.loads(prior_policy_raw)
    if sha(prior_policy_raw)!=json.loads((previous_install/'RESULT.json').read_bytes())['policy_sha256']:raise ValueError('Actual prior runtime7 policy')
    expected_roles=('USER_RUNTIME_MANAGER','USER_RUNTIME_STAGE','USER_RUNTIME_GATE','USER_RUNTIME_COPY','USER_RUNTIME_STAGE','USER_RUNTIME_GATE')
    paths=sorted((previous_tree/'tree/field-runtime-v7/launches').glob('*/OWNER.json'))
    if len(paths)!=len(expected_roles):raise ValueError('Exact observed six launch owners')
    for number,(path,purpose) in enumerate(zip(paths,expected_roles),1):
        raw=path.read_bytes();row=json.loads(raw);slot='launches/launch-%02d'%number
        if row!=dict(owner=row['owner'],policy_sha256=sha(prior_policy_raw),slot=slot,utc=row['utc'],purpose=purpose):raise ValueError('Exact runtime7 launch envelope')
        if path.parent.name not in prior_policy['allocation']['launch_slots']:raise ValueError('Allocated previous launch')
        rel='field-runtime-v7/'+slot+'/OWNER.json'
        nested[rel]=dict(sha256=sha(raw),policy_sha256=row['policy_sha256'],slot=slot,purpose=purpose)
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    previous_install=a.private/'field-runtime-v8-install'
    previous_tree=a.private/'field-runtime-v8-preservation-v1'
    proof=json.loads((previous_tree/'BACKUP.json').read_bytes())
    if proof['status']!='COMPLETE_EXHAUSTED_SUCCESSFUL_RUNTIME_PC_COPY' or not proof['manager_exact_dead'] or not proof['native_utility_exact_absent'] or proof['recording_success'] is not True:
        raise ValueError('Complete successful exhausted runtime8 preservation')
    policy_raw=(previous_install/'RELEASE.json').read_bytes();previous_policy=json.loads(policy_raw);previous_sha=sha(policy_raw)
    if previous_sha!=json.loads((previous_install/'RESULT.json').read_bytes())['policy_sha256']:raise ValueError('Actual candidate8 policy pin')
    paths=sorted((previous_tree/'tree/field-runtime-v8/launches').glob('*/OWNER.json'))
    if len(paths)!=13:raise ValueError('Manager plus twelve actual stage/gate/copy helpers')
    for path in paths:
        raw=path.read_bytes();row=json.loads(raw);slot=row['slot'];purpose=row['purpose']
        if set(row)!={'owner','policy_sha256','slot','utc','purpose'} or row['policy_sha256']!=previous_sha or slot!='launches/'+path.parent.name or path.parent.name not in previous_policy['allocation']['launch_slots']:
            raise ValueError('Exact previous runtime8 launch envelope')
        if purpose not in ('USER_RUNTIME_MANAGER','USER_RUNTIME_STAGE','USER_RUNTIME_GATE','USER_RUNTIME_COPY'):raise ValueError('Exact launch role')
        exit_row=json.loads(path.with_name('EXIT.json').read_bytes())
        if exit_row['owner']!=row['owner'] or path.with_name('FAILURE.json').exists():raise ValueError('Successful closed launch required')
        rel='field-runtime-v8/'+slot+'/OWNER.json'
        nested[rel]=dict(sha256=sha(raw),policy_sha256=previous_sha,slot=slot,purpose=purpose)
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    previous_install=a.private/'field-runtime-v10-install'
    previous_tree=a.private/'field-runtime-v10-preservation-v1'
    proof=json.loads((previous_tree/'BACKUP.json').read_bytes())
    if proof['status']!='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY' or not proof['manager_exact_dead'] or not proof['native_utility_exact_absent']:
        raise ValueError('Complete failed saved runtime10 preservation')
    raw_policy=(previous_install/'RELEASE.json').read_bytes();previous_policy=json.loads(raw_policy);previous_sha=sha(raw_policy)
    if previous_sha!=json.loads((previous_install/'RESULT.json').read_bytes())['policy_sha256']:raise ValueError('Actual candidate10 policy pin')
    paths=sorted((previous_tree/'tree/field-runtime-v10/launches').glob('*/OWNER.json'))
    if len(paths)!=3:raise ValueError('Manager plus actual stage/gate helpers')
    for number,path in enumerate(paths,1):
        raw=path.read_bytes();row=json.loads(raw);slot='launches/launch-%02d'%number
        purpose=('USER_RUNTIME_MANAGER','USER_RUNTIME_STAGE','USER_RUNTIME_GATE')[number-1]
        if row!=dict(owner=row['owner'],policy_sha256=previous_sha,slot=slot,utc=row['utc'],purpose=purpose):raise ValueError('Exact previous runtime10 launch')
        rel='field-runtime-v10/'+slot+'/OWNER.json'
        nested[rel]=dict(sha256=sha(raw),policy_sha256=previous_sha,slot=slot,purpose=purpose)
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    previous_install=a.private/'field-runtime-v11-install'
    previous_tree=a.private/'field-runtime-v11-preservation-v1'
    proof=json.loads((previous_tree/'BACKUP.json').read_bytes())
    if proof['status']!='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY' or not proof['manager_exact_dead'] or not proof['native_utility_exact_absent']:
        raise ValueError('Complete failed saved runtime11 preservation')
    raw_policy=(previous_install/'RELEASE.json').read_bytes();previous_policy=json.loads(raw_policy);previous_sha=sha(raw_policy)
    if previous_sha!=json.loads((previous_install/'RESULT.json').read_bytes())['policy_sha256']:raise ValueError('Actual candidate11 policy pin')
    paths=sorted((previous_tree/'tree/field-runtime-v11/launches').glob('*/OWNER.json'))
    if len(paths)!=3:raise ValueError('Manager plus actual stage/gate helpers')
    for number,path in enumerate(paths,1):
        raw=path.read_bytes();row=json.loads(raw);slot='launches/launch-%02d'%number
        purpose=('USER_RUNTIME_MANAGER','USER_RUNTIME_STAGE','USER_RUNTIME_GATE')[number-1]
        if row!=dict(owner=row['owner'],policy_sha256=previous_sha,slot=slot,utc=row['utc'],purpose=purpose):raise ValueError('Exact previous runtime11 launch')
        rel='field-runtime-v11/'+slot+'/OWNER.json'
        nested[rel]=dict(sha256=sha(raw),policy_sha256=previous_sha,slot=slot,purpose=purpose)
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    now=datetime.now(timezone.utc);expiry=min(now+timedelta(seconds=600),datetime.fromisoformat(scope['expires_utc']))
    if (expiry-now).total_seconds()<180:raise TimeoutError('Complete install/closure reserve')

    unit='jp-install-'+rid
    autostart=[r for r in observed['startup_files'] if r['path']=='/home/peachyprototype/.config/autostart/just-peachy.desktop']
    if len(autostart)!=1:raise ValueError('Exact current autostart inventory')
    request=dict(schema='just-peachy.runtime-install-admission.v1',root=native_root,unit=unit,
        issued_utc=now.isoformat(),expires_utc=expiry.isoformat(),files=rows,allocation=ALLOCATION,accounting=accounting,
        prior=list(identities.values()),historical=historical,nested=nested,baseline=baseline,
        policy=base64.b64encode(encoded(policy)).decode(),manifest=base64.b64encode(encoded(manager_manifest)).decode(),
        asset_root=asset_root,reuse_assets=True,rollback_source=base64.b64encode(source_bytes['field_runtime_activation_v2.py']).decode(),
        renderer_source=base64.b64encode(source_bytes['prepare_runtime_activation_v4.py']).decode(),
        rollback_source_sha256=sha(source_bytes['field_runtime_activation_v2.py']),
        renderer_source_sha256=sha(source_bytes['prepare_runtime_activation_v4.py']),
        autostart_sha256=autostart[0]['sha256'],launcher_sha256=observed['launcher_backup']['sha256'],
        galleries=inputs['gallery_manifests'])
    payload=encoded(request);put('ADMISSION.json',payload)
    code=source_bytes['field_runtime_install_native_v4.py']
    save('SOURCE_PIN.json',dict(bytes=len(code),sha256=sha(code)))
    # Compression avoids Windows argv length; the recovered source is checked
    # against the reviewed pin before any of its code executes.
    compressed=base64.b64encode(zlib.compress(code,9)).decode()
    bootstrap="import os,base64,zlib,hashlib;os.sched_setaffinity(0,{3});code=zlib.decompress(base64.b64decode("+repr(compressed)+"));assert hashlib.sha256(code).hexdigest()=="+repr(sha(code))+";exec(compile(code,'<pinned-runtime-installer>','exec'))"

    from dispatch_b01_stack_v2 import SSH
    from field_operator_broker_host_v2 import process_phase,ssh_phase
    from field_local_manager_transport_v1 import run,TransportFailure
    argv=['systemd-run','--user','--quiet','--wait','--pipe','--collect','--unit='+unit,
        '--property=Description=JustPeachyControlledRuntimeInstallation','--property=OnFailure=jp-rollback-'+rid+'.service','--property=AllowedCPUs=2-3','--property=CPUQuota=200%',
        '--property=TasksMax=64','--property=RuntimeMaxSec=180','--property=TimeoutStopSec=10',
        '--property=LimitAS=134217728','--property=LimitSTACK=1048576','--property=LimitFSIZE=94371840',
        '/usr/bin/python3','-u','-B','-c',bootstrap,sha(payload)]
    def persist(v):save('NATIVE_OWNER.json',v);return True
    def stop():
        result=process_phase(SSH+['systemctl --user stop --no-block '+unit],timeout=10,maximum=16384)
        result.pop('stdout');result.pop('stderr');save('STOP_PHASE.json',result)
    def closed(v):
        native="import os,json,resource,signal\nfrom pathlib import Path\nos.sched_setaffinity(0,{3})\nresource.setrlimit(resource.RLIMIT_AS,(134217728,)*2);resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2);resource.setrlimit(resource.RLIMIT_FSIZE,(0,0));signal.alarm(10)\ndef ticks(pid):\n try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])\n except FileNotFoundError:return None\nboot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()\nme=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)\nprint(json.dumps(dict(utility_owner=me)),file=__import__('sys').stderr,flush=True)\nassert boot!=old['boot_id'] or ticks(old['pid'])!=old['start_ticks']\nprint(json.dumps(dict(owner=old,exact_alive=False,utility_owner=me)))"
        result=ssh_phase(['/usr/bin/python3','-u','-B','-'],payload=('old='+repr(v)+'\n'+native).encode(),timeout=15,maximum=16384)
        out=result.pop('stdout');err=result.pop('stderr');put('CLOSURE_STDOUT.bin',out);put('CLOSURE_STDERR.bin',err);save('CLOSURE_PHASE.json',result)
        helper=json.loads(err.splitlines()[0])['utility_owner'];save('CLOSURE_OWNER.json',helper)
        if result['returncode'] or result['fault'] or not result['readers_joined'] or not result['ssh_reaped']:raise RuntimeError('Independent exact closure failed')
        final=process_phase(SSH+['test ! -e /proc/'+str(helper['pid'])],timeout=10,maximum=16384)
        fout=final.pop('stdout');ferr=final.pop('stderr');put('CLOSURE_FINAL_STDOUT.bin',fout);put('CLOSURE_FINAL_STDERR.bin',ferr);save('CLOSURE_FINAL_PHASE.json',final)
        if final['returncode'] or final['fault'] or not final['readers_joined'] or not final['ssh_reaped']:raise RuntimeError('Closure helper absence failed')
        save('NATIVE_CLOSURE.json',dict(owner=v,utility_owner=helper,exact_owner_dead=True,utility_pid_absent=True));return True

    def consume(channel,v,close):
        ready=channel.json()
        if type(ready) is not dict or set(ready)!={'type','binding','files'} or ready['type']!='BACKUPS_READY':
            raise ValueError('Actual active-file backups required before Close')
        binding=ready['binding'];binding_raw=encoded(binding)
        if binding['activation_owner']!=v or binding['baseline_owners']!=baseline['owners'] or binding['manager_policy_sha256']!=sha(encoded(policy)):
            raise ValueError('Actual activation owner/policy binding')
        expected={'autostart.desktop':base64.b64decode(autostart[0]['base64'],validate=True),
                  'start-prototype.sh':base64.b64decode(observed['launcher_backup']['base64'],validate=True)}
        expected.update({Path(row['path']).name:row['text'].encode() for row in observed['files']})
        received={name:base64.b64decode(raw,validate=True) for name,raw in ready['files'].items()}
        if received!=expected:raise ValueError('Current native backup differs from prior pins')
        for label in ('active-backup','active-restore'):
            directory=a.output/label;directory.mkdir()
            for name,raw in received.items():
                path=directory/name
                with path.open('xb') as f:
                    if f.write(raw)!=len(raw):raise IOError('Short active backup')
                    f.flush();os.fsync(f.fileno())
                if path.read_bytes()!=raw:raise IOError('Independent active restore')
        save('ROLLBACK_BINDING.json',binding)
        channel.send_json(dict(type='HOST_BACKUPS_VERIFIED',binding_sha256=sha(binding_raw),
            backups_sha256=sha(encoded({n:sha(raw) for n,raw in received.items()}))))
        stage=channel.json()
        if type(stage) is not dict or set(stage)!={'type','files','reused_assets','baseline_closed','available_ram_bytes'} or stage['type']!='READY_FILES':
            raise ValueError('Native baseline closure and RAM gate before transfer')
        reused={n:r for n,r in rows.items() if n.startswith(asset_root+'/')}
        transferred={n:r for n,r in rows.items() if n not in reused}
        if stage['files']!=transferred or stage['reused_assets']!=reused or stage['baseline_closed'] is not True or type(stage['available_ram_bytes']) is not int or stage['available_ram_bytes']<850*MIB:
            raise ValueError('Actual post-Close initial resource floor')
        save('BASELINE_CLOSED_AND_COPY_READY.json',stage)
        for name,row in sorted(transferred.items()):
            h=hashlib.sha256();count=0
            with sources[name].open('rb') as f:
                while True:
                    guard();block=f.read(262144)
                    if not block:break
                    channel.send(block);h.update(block);count+=len(block)
            if count!=row['bytes'] or h.hexdigest()!=row['sha256']:raise RuntimeError('Transport source changed')
        value=channel.json()
        if set(value)!={'type','result'} or value['type']!='INSTALLED':
            raise ValueError('Exact installation terminal frame')
        result=value['result']
        if result['owner']!=v or result['files']!=rows or result['rollback_binding']!=binding or result['policy_sha256']!=sha(encoded(policy)):
            raise ValueError('Installed response binding')
        if result['reused_assets']!=reused or result['transferred_files']!=transferred:raise ValueError('Exact reused assets and transferred code')
        save('INSTALLED_PENDING_CLOSURE.json',result);close();return result

    try:
        result,receipt=run(SSH+['exec '+shlex.join(argv)],payload,persist_early=persist,consume=consume,
            verify_closed=closed,stop_owned=stop,guard=guard,timeout=105)
    except TransportFailure as exc:
        receipt=exc.receipt;put('STDERR.bin',receipt.pop('stderr'));save('TRANSPORT_FAILURE.json',receipt)
        if (a.output/'NATIVE_OWNER.json').exists() and not (a.output/'CLOSURE_PHASE.json').exists():
            try:closed(json.loads((a.output/'NATIVE_OWNER.json').read_bytes()))
            except BaseException as close_error:save('NATIVE_CLOSURE_FAILURE.json',dict(error=type(close_error).__name__,message=str(close_error)[:1024]))
        raise
    put('STDERR.bin',receipt.pop('stderr'));save('TRANSPORT.json',receipt)
    save('RESULT.json',result)
    save('INSTALL_TRANSPORT_CLOSED.json',dict(native_owner_closed=True,source_backup_before_dispatch=True,
        active_files_backup_before_close=True,model_execution=False,candidate_acceptance=False,
        complete_mutable_runtime_backup=False))
    print(json.dumps(dict(status='RUNTIME_FILES_INSTALLED_IDLE_LAUNCH_REQUESTED',files=len(rows),
        transferred_bytes=sum(r['bytes'] for n,r in rows.items() if not n.startswith(asset_root+'/')),reused_asset_bytes=TOTAL,root=request['root'],model_execution=False)))

if __name__=='__main__':main()
