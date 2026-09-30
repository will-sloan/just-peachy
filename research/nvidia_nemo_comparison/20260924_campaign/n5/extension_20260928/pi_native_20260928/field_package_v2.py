"""Native offline package/activation/rollback boundary; README_FIELD_PACKAGE_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2)


def command(root,python,main,args,label):
    owner=root/(label+'_OWNER.json')
    code="""import os,json,sys,runpy,signal
from pathlib import Path
signal.alarm(60)
o=dict(pid=os.getpid(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))
with Path(sys.argv[1]).open('x') as f:json.dump(o,f)
sys.argv=sys.argv[2:]
sys.path.insert(0,str(Path(sys.argv[0]).resolve().parent))
runpy.run_path(sys.argv[0],run_name='__main__')
"""
    with (root/(label+'.stdout')).open('xb') as out,(root/(label+'.stderr')).open('xb') as err:
        result=subprocess.run([python,'-B','-c',code,str(owner),str(main),*args],stdout=out,stderr=err,timeout=70)
    return dict(exit_code=result.returncode,stdout=str(root/(label+'.stdout')),stderr=str(root/(label+'.stderr')))


def run(root,a):
    root=Path(root);began=time.monotonic()
    source=root/'source';shutil.copytree(Path(a['prototype']),source)
    # Only code/config/notices are packaged by the existing release allowlist.
    (source/'native').mkdir(exist_ok=True);(source/'docs').mkdir(exist_ok=True)
    helpers=['field_entry_v1.py','source_quiet_factory_v1.py','isolated_pipeline_source_v2.py','isolated_live_facade_v2.py','live_source_bridge_v2.py','isolated_source_transport_v3.py']
    for name in helpers:shutil.copyfile(root/name,source/'native'/name)
    for name in ['AUTONOMOUS_QUIET_AUTHORIZATION_V1.json','alsa_hw_only_v1.conf']:
        shutil.copyfile(root/name,source/'config'/name)
    shutil.copyfile(root/'README_FIELD_PACKAGE_V1.md',source/'docs/README_FIELD_PACKAGE_V1.md')
    (source/'main.py').write_text("\"\"\"Offline B01 candidate; docs/README_FIELD_PACKAGE_V1.md.\"\"\"\nfrom native.field_entry_v1 import main\nif __name__=='__main__':raise SystemExit(main())\n")
    runtime=json.loads((root/'N2_RUNTIME_BACKUP.json').read_text())
    extras=[]
    for path in [runtime['nemotron_model'],runtime['nemotron_library'],*[x['path'] for x in runtime['native_runtime_files']]]:
        p=Path(path);extras.append(dict(path=str(p),resolved=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p)))
    contract=dict(schema='just-peachy.offline-field-candidate.v1',models_root=str(Path.home()/'JustPeachy/install/models'),
                  runtime_prefix=sys.prefix,extra_assets=extras,backend='nemotron_hybrid',mode='open_with_names',recipe='balanced',tap='O0',
                  minimum_free_bytes=5*1024**3,private_data_quota_bytes=512*1024**2,session_reservation_bytes=32*1024**2,
                  maximum_recording_seconds=30,field_release_accepted=False,visible_gui_qualified=False,gui_launch_requires_fresh_admission=True,
                  dependencies_are_shared=True,research_asset_paths_retained=True,asset_relocation_qualified=False,
                  sequential_refinement='UNAVAILABLE_IN_THIS_PACKAGE; separate V52 saved controller evidence only',
                  evidence='V54 B01 quiet passage; this package derivative needs installed launch/visible/endurance qualification')
    write(source/'config/field_contract.json',contract)
    sys.path.insert(0,str(source))
    from release_tools import release
    versions=['b01-offline-20260930-v1a','b01-offline-20260930-v1b']
    built=[release.build(source,root/'archives',version) for version in versions]
    deployment=root/'deployment';data=root/'candidate-data';data.mkdir()
    write(data/'DATA_SCHEMA.json',dict(schema_version=1))
    write(data/'preserved-private-canary.json',dict(synthetic=True,value='must-survive-pointer-change'))
    shutil.copyfile(root/'N2_RUNTIME_BACKUP.json',data/'n2_runtime.json')
    shutil.copyfile(root/'LIVE_CONFIG_BACKUP.json',data/'live_config.json')
    preserved={p.name:sha(p) for p in data.iterdir() if p.is_file()}
    staged=[release.stage(row['archive'],deployment,row['sha256']) for row in built]
    # Shared models are referenced, not copied. Resolve through the explicit model store only.
    (deployment/'models').symlink_to(Path(contract['models_root']),target_is_directory=True)
    activate_a=release.activate(deployment,data,versions[0],require_assets=True)
    with (root/'CURRENT_BEFORE.json').open('xb') as f:f.write((deployment/'current.json').read_bytes())
    health_a=release.healthcheck(deployment,data,check_models=True,check_imports=False)
    activate_b=release.activate(deployment,data,versions[1],require_assets=True)
    assert release.read_json(deployment/'previous.json')==release.read_json(root/'CURRENT_BEFORE.json')
    rollback=release.rollback(deployment,data)
    assert release.read_json(deployment/'current.json')['version']==versions[0]
    for name,digest in preserved.items():assert sha(data/name)==digest
    selected=deployment/'releases'/versions[0]
    health_command=command(root,sys.executable,selected/'main.py',['health'],'installed_health')
    assert health_command['exit_code']==0,health_command
    idle_command=command(root,sys.executable,selected/'main.py',['controller-check','--data-root',str(data)],'installed_controller')
    assert idle_command['exit_code']==0,idle_command
    for name,digest in preserved.items():assert sha(data/name)==digest
    assert not (data/'runtime.lock').exists()
    # Installation must refuse a bad archive checksum without creating its target version.
    try:release.stage(built[0]['archive'],root/'bad-hash-deployment','0'*64)
    except ValueError as e:checksum_rejected=str(e)
    else:raise AssertionError('Bad archive hash accepted')
    assert not (root/'bad-hash-deployment').exists()
    # Private-data ownership must reject activation before pointer/data changes.
    pointer=sha(deployment/'current.json')
    from release_tools.runtime_lock import RuntimeLock
    lock=RuntimeLock(data,'package-test-owner')
    try:
        try:release.activate(deployment,data,versions[1])
        except RuntimeError as e:busy_rejected=str(e)
        else:raise AssertionError('Busy activation accepted')
        assert sha(deployment/'current.json')==pointer
    finally:lock.close()
    # An installed-code integrity failure is tested on a retained derivative, never repaired in place.
    damaged=root/'damaged-release';shutil.copytree(selected,damaged)
    with (damaged/'main.py').open('ab') as f:f.write(b'\n# deliberate integrity negative fixture\n')
    try:release.verify_release(damaged)
    except ValueError as e:damage_rejected=str(e)
    else:raise AssertionError('Damaged release accepted')
    inventory={}
    for asset in release.assets_list(selected):
        path=Path(contract['models_root'])/asset['sha256']/asset['filename'];stat=path.stat()
        inventory[(stat.st_dev,stat.st_ino)]=dict(path=str(path),bytes=stat.st_size,sha256=asset['sha256'])
    for row in extras:
        path=Path(row['path']);stat=path.stat();inventory[(stat.st_dev,stat.st_ino)]=row
    runtime_bytes=sum(p.stat().st_size for p in Path(sys.prefix).rglob('*') if p.is_file() and not p.is_symlink())
    code_bytes=sum(x['bytes'] for x in release.verify_release(selected)['files'])
    unique_assets=sum(x['bytes'] for x in inventory.values())
    free=shutil.disk_usage(root).free
    assert free>=5*1024**3+contract['private_data_quota_bytes']+2*code_bytes
    result=dict(status='OFFLINE_PACKAGE_INSTALL_HEALTH_POINTER_ROLLBACK_PASS_ONLY',versions=versions,built=built,staged=staged,
                activation=[activate_a,activate_b],rollback=rollback,health=health_a,installed_health=health_command,installed_controller=idle_command,
                negative_checks=dict(checksum=checksum_rejected,busy_data=busy_rejected,damaged_code=damage_rejected),
                preserved_private_hashes=preserved,unique_asset_files=len(inventory),unique_asset_bytes=unique_assets,assets=list(inventory.values()),
                shared_runtime_bytes=runtime_bytes,unpacked_release_bytes=code_bytes,two_release_code_bytes=2*code_bytes,
                proposed_private_quota_bytes=contract['private_data_quota_bytes'],actual_device_bytes=31268536320,free_bytes=free,
                max_pcm_plus_float_bytes_per_30s=480000*6+44,private_quota_is_not_endurance_acceptance=True,
                capture_opened=False,model_inference=False,visible_gui=False,baseline_install_activated=False,
                rollback_scope='two same-code candidate versions in isolated installation; original active baseline never changed',
                research_asset_paths_retained=True,asset_relocation_qualified=False,field_release_accepted=False,seconds=time.monotonic()-began)
    return result
