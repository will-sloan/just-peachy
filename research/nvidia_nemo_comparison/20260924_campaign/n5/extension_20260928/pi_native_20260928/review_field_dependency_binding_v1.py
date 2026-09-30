"""Independent compact binding review; README_FIELD_DEPENDENCY_BINDING_V1.md."""
import hashlib
import json
from pathlib import Path
import psutil


def main():
    psutil.Process().cpu_affinity([14])
    from dispatch_geometry_v2 import remote,PRIVATE
    result=remote(r'''
import os,sys,resource
sys.dont_write_bytecode=True;os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2)
import json,hashlib,fcntl,subprocess
from pathlib import Path
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-dependency-binding-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_NATIVE_COMPACT_DEPENDENCY_BINDING_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
selected=Path(a['installed_release']);assert {p.relative_to(selected).as_posix():sha(p) for p in selected.rglob('*') if p.is_file()}==a['installed_files']
assert sha(a['retained_lock'])==a['retained_lock_sha256']=='fcbbfdbc281117eff4b7237240456d4a2a2d502fcc15a46aec2f922311903db1'
binding=read(r/'CONTRACT_BINDING.json');checked=read(r/'BINDING_VERIFIED.json')
assert set(binding)=={'schema','base_lock','base_release','selected_release','patch','artifact_limits'}
assert binding['schema']=='just-peachy.retained-contract-binding.v1' and checked==out['verification']
assert checked['binding_sha256']==sha(r/'CONTRACT_BINDING.json') and checked['binding_bytes']==(r/'CONTRACT_BINDING.json').stat().st_size<32768
base=read(a['retained_lock']);assert len(base['entries'])==7890 and base['unique_files']==7847 and base['unique_logical_bytes']==791871486
assert checked['dependency_check']==dict(status='RETAINED_DEPENDENCIES_EXACT',entries=7890,unique_files=7847,unique_logical_bytes=791871486)
assert binding['base_lock']==dict(path=a['retained_lock'],sha256=a['retained_lock_sha256'])
for key,expected in [('base_release',a['base_release']),('selected_release',a['installed_release'])]:
 v=binding[key];assert v['path']==expected and v['manifest_sha256']==sha(Path(expected)/'RELEASE_MANIFEST.json') and v['contract_sha256']==sha(Path(expected)/'config/field_contract.json')
assert base['release_contract_sha256']==binding['base_release']['contract_sha256']
old=read(Path(a['base_release'])/'config/field_contract.json');new=read(selected/'config/field_contract.json')
differences={k:[old.get(k),new.get(k)] for k in old.keys()|new.keys() if old.get(k)!=new.get(k)}
assert binding['patch']==differences=={'maximum_recording_seconds':[30,125],'session_reservation_bytes':[33554432,67108864],'sustained_target_seconds':[None,120],'archive_interchange_for_extended_recording':[None,'UNQUALIFIED'],'artifact_limits':[None,new['artifact_limits']]}
assert binding['artifact_limits']==new['artifact_limits'] and binding['artifact_limits']['canonical_sha256']=='6b066469dc6baca11450d3710928a282416eadb5a17dcaa557a6c797191d89fd'
assert len(out['rejections'])==8
for row in out['rejections']:assert row==read(r/(row['case']+'.json')) and row['rejected']
assert not any(checked[k] for k in ['catalogue_copied','recollection','import_probe','ldd','models','capture'])
assert not any(out[k] for k in ['controller_started','GUI','models','capture','pointer_activated'])
assert not any((r/n).exists() for n in ['source','deployment','archives','DEPENDENCIES.json'])
assert not any((r/'data'/n).exists() for n in ['sessions','source_receipts','conversations','runtime.lock'])
assert read(r/'LEASE_CLOSED.json')['released']
assert sha(r/'data/live_config.json')==a['live_config_sha256'] and sha(r/'data/n2_runtime.json')==a['n2_runtime_sha256']
with (r/'data/.runtime.guard').open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for p in owners:
 o=read(p);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<4*1024**2
print(json.dumps(dict(status=out['status'],result=out,binding_sha256=sha(r/'CONTRACT_BINDING.json'),binding_bytes=checked['binding_bytes'],target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-dependency-binding-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
