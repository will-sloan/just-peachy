"""Independent native package review and private backup; README_REVIEW_FIELD_PACKAGE_V1.md."""
import argparse
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import subprocess
import tarfile
import psutil


def main():
    psutil.Process().cpu_affinity([14])
    p=argparse.ArgumentParser();p.add_argument('--run',choices=['field-package-v1','field-package-v2'],required=True);args=p.parse_args()
    from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
    from dispatch_b01_stack_v2 import SSH
    x=remote('RUN='+repr(args.run)+'\n'+r'''
import os,json,hashlib,resource,subprocess,fcntl,zipfile
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2)
root=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');dispatch=read(root/'DISPATCH_RESULT.json');env=read(root/'LIVE_ENVELOPE.json')
for row in a['files']:assert sha(row['path'])==row['sha256']
assert not a['capture'] and not a['models_loaded'] and not a['audio_saved']
assert env['affinity']==[2,3] and env['address_space']==[768*1024**2]*2 and env['stack']==[1048576]*2
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==8*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
owners=list(root.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for path in owners:
 o=read(path);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for path in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
archives=[]
for archive in sorted((root/'archives').glob('*.zip')):
 with zipfile.ZipFile(archive) as z:
  names=z.namelist();manifest=json.loads(z.read('RELEASE_MANIFEST.json'));entries={r['path']:r for r in manifest['files']}
  assert len(names)==len(set(names)) and set(names)==set(entries)|{'RELEASE_MANIFEST.json'}
  assert all(not any(x in Path(name).parts for x in ['people','sessions','conversations','models','evidence','private']) for name in names)
  assert not any(Path(name).suffix.lower() in ['.wav','.onnx','.gguf','.npy','.f32le'] for name in names)
  for name,row in entries.items():
   data=z.read(name);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
   installed=root/'deployment/releases'/manifest['version']/name
   assert installed.stat().st_size==row['bytes'] and sha(installed)==row['sha256']
  archives.append(dict(version=manifest['version'],files=len(entries),bytes=archive.stat().st_size,unpacked_bytes=sum(x['bytes'] for x in entries.values()),sha256=sha(archive)))
assert len(archives)==2
passed=r['status']=='OFFLINE_PACKAGE_INSTALL_HEALTH_POINTER_ROLLBACK_PASS_ONLY'
if passed:
 assert dispatch['exit_code']==0 and r['capture_opened']==r['model_inference']==r['visible_gui']==r['baseline_install_activated']==False
 assert read(root/'deployment/current.json')['version']==r['versions'][0]
 assert read(root/'deployment/previous.json')['version']==r['versions'][1]
 for name,digest in r['preserved_private_hashes'].items():assert sha(root/'candidate-data'/name)==digest
 health=read(root/'installed_health.stdout');controller=read(root/'installed_controller.stdout')
 assert health['status']=='OFFLINE_CODE_AND_ASSETS_HEALTHY' and controller['status']=='INSTALLED_CONTROLLER_IDLE_CHECK_PASS'
 assert controller['model_loads']==0 and not controller['capture_opened'] and len(controller['unavailable_rejections'])==3
 assert set(r['negative_checks'])=={'checksum','busy_data','damaged_code'} and all(r['negative_checks'].values())
 assert not (root/'bad-hash-deployment').exists() and not (root/'candidate-data/runtime.lock').exists()
 selected=root/'deployment/releases'/r['versions'][0]
 assert (root/'damaged-release/main.py').read_bytes()==(selected/'main.py').read_bytes()+b'\n# deliberate integrity negative fixture\n'
 unique={}
 for row in r['assets']:
  path=Path(row['path']);st=path.stat();assert st.st_size==row['bytes'] and sha(path)==row['sha256'];unique[(st.st_dev,st.st_ino)]=st.st_size
 assert len(unique)==r['unique_asset_files'] and sum(unique.values())==r['unique_asset_bytes']
 summary={k:r[k] for k in ['versions','unique_asset_files','unique_asset_bytes','shared_runtime_bytes','unpacked_release_bytes','two_release_code_bytes','proposed_private_quota_bytes','actual_device_bytes','free_bytes','max_pcm_plus_float_bytes_per_30s','research_asset_paths_retained','asset_relocation_qualified','rollback_scope','seconds']}
 status='PASS_NATIVE_OFFLINE_PACKAGE_HEALTH_CONTROLLER_AND_ISOLATED_POINTER_ROLLBACK_ONLY'
else:
 assert RUN=='field-package-v1' and dispatch['exit_code']==1 and r['status']=='FAILED_PRESERVED'
 assert "No module named 'native'" in (root/'installed_health.stderr').read_text()
 assert not (root/'installed_controller_OWNER.json').exists()
 summary=dict(error=r['error'],scope='Wrapper omitted installed release sys.path; health/controller acceptance not reached',seconds=r['elapsed_seconds'])
 status='REVIEWED_PACKAGE_V1_INSTALLED_ENTRYPOINT_WRAPPER_FAILURE_ONLY'
links={p.relative_to(root).as_posix():os.readlink(p) for p in root.rglob('*') if p.is_symlink()}
assert links=={'deployment/models':str(Path.home()/'JustPeachy/install/models')}
files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
size=sum(x['bytes'] for x in files.values());assert size<a['target_output_max_bytes']==32*1024**2
summary.update(status=status,archives=archives,owners_closed=len(owners),peak_rss_bytes=r['peak_rss_bytes'],sampled_aggregate_peak_bytes=max(x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),target_bytes=size,baseline_unchanged=True,capture_closed=True,leases_free=True,field_release_accepted=False,visible_gui=False,model_inference=False)
print(json.dumps(dict(summary=summary,files=files,links=links)))
''')
    out=PRIVATE/(args.run+'-evidence');backup=out/'target';backup.mkdir();seen=set();seen_links=set()
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/'+args.run+' -cf - .'],timeout=90)
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as archive:
        for member in archive:
            if member.isdir():continue
            assert member.name.startswith('./');name=member.name[2:];path=PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts
            if member.issym():
                assert name in x['links'] and name not in seen_links and member.linkname==x['links'][name];seen_links.add(name);continue
            assert member.isfile() and name in x['files'] and name not in seen
            raw=archive.extractfile(member).read();assert len(raw)==x['files'][name]['bytes'] and hashlib.sha256(raw).hexdigest()==x['files'][name]['sha256']
            target=backup.joinpath(*path.parts);target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(raw)
            assert hashlib.sha256(target.read_bytes()).hexdigest()==x['files'][name]['sha256'];seen.add(name)
    assert seen==set(x['files']) and seen_links==set(x['links'])
    combined=x['summary']['target_bytes']+sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert combined+1024**2<64*1024**2
    x['summary'].update(private_backup_verified=True,backup_files=len(seen),backup_links=len(seen_links),combined_bytes=combined)
    for name,value in [('REVIEW.json',x['summary']),('BACKUP.json',dict(files=x['files'],links=x['links'])),('SYMLINKS.json',x['links'])]:
        with (out/name).open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps(x['summary']))


if __name__=='__main__':main()
