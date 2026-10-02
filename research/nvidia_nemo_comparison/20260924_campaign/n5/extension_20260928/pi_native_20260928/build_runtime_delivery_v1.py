"""Build a private prepared-device delivery kit; README_RUNTIME_DELIVERY_KIT_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,hashlib,json,os,shutil,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
MIB=1024**2
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    a=argparse.ArgumentParser(description=__doc__)
    for n in ('private','sources','docs','install','output','scope'):
        a.add_argument('--'+n,type=Path,required=True)
    a=a.parse_args();a.output.mkdir()
    me=psutil.Process()
    def save(n,v):
        raw=(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        with (a.output/n).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if (a.output/n).read_bytes()!=raw:raise IOError('Receipt readback')
    save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    scope=json.loads(a.scope.read_bytes());deadline=time.monotonic()+540
    if scope['maximum_bytes']!=512*MIB or not scope['host_only']:raise ValueError('Full512MiB independent kit allocation')
    def guard():
        if time.monotonic()>deadline or datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Finite build')
        for drive,floor in (('C:/',50),('G:/',75)):
            if shutil.disk_usage(drive).free<floor*1024**3+512*MIB:raise RuntimeError('Full independent kit floor')
    guard()
    result=json.loads((a.install/'RESULT.json').read_bytes())
    release=(a.install/'RELEASE.json').read_bytes()
    if sha(release)!=result['policy_sha256']:raise ValueError('Current release pin')
    source_map={}
    def add(path,name):
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:raise ValueError('Ordinary source required')
        if name.startswith('/') or '..' in Path(name).parts or name in source_map:raise ValueError('Unique relative member')
        source_map[name]=path
    # Immutable old code is retained as provenance, not advertised as runnable
    # user profiles. Only the current operator entry is an activation command.
    for suffix in ('.py','.json','.md','.ps1'):
        for p in sorted(a.sources.glob('*'+suffix)):add(p,'operator-sources/'+p.name)
    for name in ('MODE_GUIDE.md','BACKEND_COMBINATIONS.md','INSTALL_HEALTH_AND_RECOVERY.md','FIELD_VALIDATION.md','FIELD_RUN_TEMPLATE.json','HARDWARE_CAPABILITIES.json','PATHS_AND_BACKUPS.md'):
        add(a.docs/name,'guides/'+name)
    for p in (a.install/'stage-restore').rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(a.install/'stage-restore').as_posix()
        raw=p.read_bytes()
        if result['files'][rel]!=dict(bytes=len(raw),sha256=sha(raw)):raise ValueError('Installed source pin')
        if (a.install/'stage-backup'/rel).read_bytes()!=raw:raise ValueError('Independent installed source backup')
        add(p,'installed-code/'+rel)
    for n in ('RELEASE.json','MANIFEST.json','ADMISSION.json','RESULT.json','ROLLBACK_BINDING.json','SOURCE_ASSET_BACKUP.json','PREVIOUS_BATCH_BINDING.json'):
        add(a.install/n,'installed-receipts/'+n)
    assets=a.private/'runtime-titanet-v1-install/assets-restore'
    for p in assets.iterdir():
        if not p.is_file():continue
        if p.read_bytes()!=(assets.parent/'assets-backup'/p.name).read_bytes():raise ValueError('Independent TitaNet assets')
        pin=result['files']['runtime-titanet-v3/'+p.name]
        with p.open('rb') as f:
            if p.stat().st_size!=pin['bytes'] or hashlib.file_digest(f,'sha256').hexdigest()!=pin['sha256']:raise ValueError('Installed asset pin')
        add(p,'local-model-assets/runtime-titanet-v3/'+p.name)
    work=a.private/'deployable-runtime-resume-v1'
    for n in ('INSTALL_INPUTS.json','MANAGER_BUNDLE.json'):
        add(work/'boot-launch-inputs-v1'/n,'prepared-inputs/'+n)
    for p in (work/'boot-launch-inputs-v1/profiles').glob('*.json'):add(p,'prepared-inputs/profiles/'+p.name)
    common=json.loads((work/'boot-launch-inputs-v1/INSTALL_INPUTS.json').read_bytes())['common_bundle']
    cp=Path(common['path'])
    if cp.stat().st_size!=common['bytes'] or sha(cp.read_bytes())!=common['sha256']:raise ValueError('Prepared common source')
    add(cp,'prepared-inputs/COMMON_BUNDLE_SOURCE.json')
    for p in work.glob('SOURCE_CLOSED_V*.json'):add(p,'source-receipts/'+p.name)
    add(work/'PREINSTALL_PRIOR_BINDING_V6.json','prepared-inputs/PRIOR_BINDING.json')
    if len(source_map)>3000 or sum(p.stat().st_size for p in source_map.values())>160*MIB:raise ValueError('Complete finite package bounds')
    manifest=dict(schema='just-peachy.prepared-cm5-delivery-kit.v1',release=result['root'].rsplit('/',1)[1],
        policy_sha256=result['policy_sha256'],purpose='Backup and fresh-version deployment on the prepared PC/CM5',
        standalone_os_image=False,arbitrary_device_portable=False,recordings_or_gallery_vectors_included=False,
        external_dependencies='Existing pinned CM5 base environment, Sherpa/PnC/Pyannote/ReDimNet and Nemotron runtime/assets remain required; see INSTALL_HEALTH_AND_RECOVERY.md.',
        install_entry='operator-sources/Refresh-JustPeachy.ps1',members={})
    for name,p in sorted(source_map.items()):
        guard()
        with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        manifest['members'][name]=dict(bytes=p.stat().st_size,sha256=digest)
    encoded=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    if len(encoded)>2*MIB:raise ValueError('Manifest bound')
    package=a.output/'JustPeachy-prepared-CM5-runtime.zip'
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('DEPLOYMENT_MANIFEST.json',encoded)
        for name,p in sorted(source_map.items()):guard();z.write(p,name)
    if package.stat().st_size>160*MIB:raise ValueError('Archive bound')
    restore=a.output/'independent-restore';restore.mkdir()
    # Stream each exact member to a new file; re-read independently after close.
    with zipfile.ZipFile(package) as z:
        if len(z.infolist())!=len(source_map)+1 or len(set(z.namelist()))!=len(z.namelist()):raise ValueError('Exact ZIP membership')
        if z.read('DEPLOYMENT_MANIFEST.json')!=encoded:raise ValueError('ZIP manifest')
        for name,row in manifest['members'].items():
            guard();dest=restore/name;dest.parent.mkdir(parents=True,exist_ok=True)
            total=0;dig=hashlib.sha256()
            with z.open(name) as src,dest.open('xb') as out:
                while True:
                    part=src.read(65536)
                    if not part:break
                    total+=len(part)
                    if total>row['bytes'] or out.write(part)!=len(part):raise IOError('Bounded restore write')
                    dig.update(part)
                out.flush();os.fsync(out.fileno())
            with dest.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
            if total!=row['bytes'] or actual!=row['sha256'] or dig.hexdigest()!=actual:raise IOError('Full restore readback')
    backup=a.output/'independent-package-copy.zip'
    with package.open('rb') as src,backup.open('xb') as dst:
        while True:
            guard();part=src.read(65536)
            if not part:break
            if dst.write(part)!=len(part):raise OSError('Archive copy')
        dst.flush();os.fsync(dst.fileno())
    def filehash(p):
        with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    digest=filehash(package)
    if filehash(backup)!=digest:raise IOError('Independent package readback')
    used=sum(p.stat().st_size for p in a.output.rglob('*') if p.is_file())
    if used+2*MIB>scope['maximum_bytes']:raise ValueError('Whole package allocation')
    guard()
    save('BACKUP.json',dict(status='COMPLETE_PREPARED_DEVICE_KIT_AND_INDEPENDENT_RESTORE',utc=datetime.now(timezone.utc).isoformat(),
        package=str(package),bytes=package.stat().st_size,sha256=digest,members=len(source_map)+1,
        source_bytes=sum(v['bytes'] for v in manifest['members'].values()),total_private_bytes=used,
        native_dispatched=False,full_zip_readback=True,all_members_independently_restored_and_read=True,
        manifest_sha256=sha(encoded),release=manifest['release'],scope_sha256=sha(a.scope.read_bytes())))
    print(json.dumps(dict(status='PREPARED_DEVICE_KIT_CLOSED',members=len(source_map)+1,bytes=package.stat().st_size,sha256=digest)))
if __name__=='__main__':main()
