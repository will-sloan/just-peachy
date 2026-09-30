"""Exact retained dependency and pointer-gate qualification. README_FIELD_DEPENDENCIES_V2.md."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from field_dependencies_v2 import sha, read, exclusive, collect, verify, activate, rollback, check_descriptor, configure_output


def run(root,a):
    sys.dont_write_bytecode=True
    configure_output(root,a['target_output_max_bytes'])
    release=Path(a['installed_release']);previous=Path(a['rollback_release'])
    for path,key in [(release,'release_manifest_sha256'),(previous,'rollback_manifest_sha256')]:
        assert sha(path/'RELEASE_MANIFEST.json')==a[key]
    sys.path.insert(0,str(release))
    from release_tools import release as rt
    from release_tools.runtime_lock import RuntimeLock
    rt.verify_release(release);rt.verify_release(previous)
    assert sha(release/'config/field_contract.json')==sha(previous/'config/field_contract.json')
    source_lock=Path(a['retained_lock']);assert sha(source_lock)==a['retained_lock_sha256']
    dependencies=read(source_lock);lock_sha=sha(source_lock)
    exact=verify(source_lock,lock_sha)
    # The retained import/link observation is reused, not rerun.
    assert sha(a['retained_probe'])==a['retained_probe_sha256']
    probe=read(a['retained_probe']);assert probe['status']=='IMPORTED_AND_LINKED_WITHOUT_MODEL_OR_CAPTURE'
    deployment=root/'deployment';deployment.mkdir();data=root/'data';data.mkdir()
    rt.write_json(data/'DATA_SCHEMA.json',dict(schema_version=1))
    (data/'private-preservation-canary').write_bytes(b'PRIVATE_SYNTHETIC_CANARY\n')
    shutil.copyfile(root/'LIVE_CONFIG_BACKUP.json',data/'live_config.json')
    preserved={p.name:sha(p) for p in data.iterdir() if p.is_file()}
    descriptors=[]
    for candidate in [previous,release]:
        manifest=read(candidate/'RELEASE_MANIFEST.json');path=root/(manifest['version']+'.deployment.json')
        d=dict(schema='just-peachy.retained-deployment.v1',version=manifest['version'],release=str(candidate),resolved_release=str(candidate.resolve()),
               manifest_sha256=sha(candidate/'RELEASE_MANIFEST.json'),contract_sha256=sha(candidate/'config/field_contract.json'),
               dependencies=str(source_lock),dependencies_sha256=lock_sha,candidate_root=str(deployment.resolve()),data_root=str(data.resolve()),
               original_rc5_activation=False,assets_copied=False)
        exclusive(path,d);descriptors.append(path)
    first=activate(deployment,data,descriptors[0],sha(descriptors[0]),None,rt)
    first_hash=sha(deployment/'current.json')
    second=activate(deployment,data,descriptors[1],sha(descriptors[1]),first_hash,rt)
    second_hash=sha(deployment/'current.json');previous_hash=sha(deployment/'previous.json')
    rejected=[]
    def reject(name,fn,expected):
        before={n:sha(deployment/n) for n in ['current.json','previous.json']}
        history={p.name:sha(p) for p in (deployment/'history').iterdir()}
        try:fn()
        except (ValueError,RuntimeError,FileNotFoundError) as exc:
            assert expected in str(exc),(name,str(exc));rejected.append(dict(case=name,error=str(exc),pointer_unchanged=True))
        else:raise AssertionError('Missing rejection: '+name)
        assert before=={n:sha(deployment/n) for n in before}
        assert history=={p.name:sha(p) for p in (deployment/'history').iterdir()}
    reject('stale_current_pointer',lambda:activate(deployment,data,descriptors[0],sha(descriptors[0]),first_hash,rt),'current pointer changed')
    reject('wrong_descriptor_digest',lambda:activate(deployment,data,descriptors[0],'0'*64,second_hash,rt),'descriptor hash')
    reject('wrong_previous_digest',lambda:rollback(deployment,data,second_hash,'0'*64,rt),'Previous pointer hash')
    # Malformed lock fixtures are new documents; no dependency byte or original pointer is changed.
    for name,mutate,message in [
        ('wrong_dependency_hash',lambda d:d['entries'][0].update(sha256='0'*64),'Dependency changed'),
        ('missing_dependency',lambda d:d['entries'][0].update(path=str(root/'nonexistent-asset')),'No such file'),
        ('wrong_resolved_target',lambda d:d['entries'][0].update(resolved=str(root/'unexpected-target')),'Dependency changed')]:
        altered=dict(schema=dependencies['schema'],release_contract_sha256=dependencies['release_contract_sha256'],roots={},entries=[copy.deepcopy(dependencies['entries'][0])],elf=[],unique_files=1,unique_logical_bytes=dependencies['entries'][0]['bytes']);mutate(altered);lock=root/(name+'.json');exclusive(lock,altered)
        d=read(descriptors[1]);d.update(dependencies=str(lock),dependencies_sha256=sha(lock));path=root/(name+'.deployment.json');exclusive(path,d)
        reject(name,lambda path=path:activate(deployment,data,path,sha(path),second_hash,rt),message)
    reject('prewrite_output_bound',lambda:exclusive(root/'must-not-exist.json',dict(fixture=True),total_budget_bytes=1),'before write')
    assert not (root/'must-not-exist.json').exists()
    owner=RuntimeLock(data,'explicit_test_application_owner')
    try:reject('busy_private_data',lambda:activate(deployment,data,descriptors[0],sha(descriptors[0]),second_hash,rt),'owns')
    finally:owner.close()
    rolled=rollback(deployment,data,second_hash,previous_hash,rt)
    assert rolled==first and read(deployment/'current.json')==first
    for name,digest in preserved.items():assert sha(data/name)==digest
    assert not (data/'runtime.lock').exists()
    final=verify(source_lock,lock_sha)
    assert final==exact
    for candidate,key in [(release,'release_manifest_sha256'),(previous,'rollback_manifest_sha256')]:
        assert sha(candidate/'RELEASE_MANIFEST.json')==a[key];rt.verify_release(candidate)
    unique_by_category={}
    for category in sorted({r['category'] for r in dependencies['entries']}):
        unique={r['resolved']:r['bytes'] for r in dependencies['entries'] if r['category']==category and r['kind']=='file'}
        unique_by_category[category]=dict(files=len(unique),bytes=sum(unique.values()))
    storage=dict(device_bytes=31268536320,free_bytes=shutil.disk_usage(root).free,minimum_free_bytes=5*1024**3,
                 pinned_unique_bytes=dependencies['unique_logical_bytes'],category_totals=unique_by_category,
                 quota_reservation_bytes=512*1024**2,incremental_asset_bytes=0,incremental_release_bytes=0,
                 code_versions_already_present_bytes=sum(sum(p.stat().st_size for p in x.rglob('*') if p.is_file()) for x in [previous,release]),
                 remaining_after_private_quota_reservation=shutil.disk_usage(root).free-512*1024**2,
                 existing_research_already_in_free_space=True)
    assert storage['remaining_after_private_quota_reservation']>storage['minimum_free_bytes']
    exclusive(root/'STORAGE.json',storage);exclusive(root/'REJECTIONS.json',rejected)
    exclusive(root/'POINTER_SEQUENCE.json',dict(first=first,second=second,rolled_back=rolled))
    return dict(status='PASS_RETAINED_DEPENDENCY_GUARDED_CANDIDATE_ROLLBACK_AND_PREWRITE_QUOTA_ONLY',dependency_check=exact,
                dependency_lock_sha256=lock_sha,elf_roots=len(dependencies['elf']),mapped_elf_count=len(probe['mapped_elf']),
                new_import_probe=False,retained_lock=str(source_lock),retained_probe=a['retained_probe'],descriptor_count=2,rejections=len(rejected),data_unchanged=True,assets_copied=False,releases_copied=False,
                baseline_activated=False,capture_opened=False,models_loaded=False,GUI_opened=False,storage=storage,
                retained_placement=True,relocation_qualified=False,field_release_accepted=False)
