"""Independent compact binding review; README_FIELD_SIDECAR_BUDGET_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-sidecar-budget-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_NATIVE_SIDECAR_PREWRITE_BOUNDARIES_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
plan=read(r/'FIELD_WHOLE_RUN_ALLOCATION_V1.json')
assert plan['retained_component_maxima']==dict(compact_epoch=31485484,native_journal=16777216,conversation_controls=131072)
assert sum(plan['retained_component_maxima'].values())+sum(v['maximum_bytes'] for v in plan['sidecar_groups'].values())==plan['target_maximum_bytes']==76*1024**2
assert plan['host_target_copy_maximum_bytes']==plan['target_maximum_bytes'] and plan['host_metadata_maximum_bytes']==4*1024**2
assert plan['host_maximum_bytes']==80*1024**2 and plan['combined_request_bytes']==156*1024**2
assert plan['sidecar_groups']['trace']['maximum_bytes']==12*1024**2 and plan['sidecar_groups']['closure_reserve']['maximum_bytes']==5083604
for v in plan['sidecar_groups'].values():
 assert set(v)=={'maximum_bytes','maximum_file_bytes','maximum_files','maximum_write_bytes','minimum_free_bytes'}
 assert all(type(x) is int and x>0 for x in v.values()) and v['minimum_free_bytes']==5*1024**3
 assert v['maximum_write_bytes']<=v['maximum_file_bytes']<=v['maximum_bytes']<=12*1024**2
 assert v['maximum_files']<=128
assert not any(plan[k] for k in ['whole_run_integrated','capture_admitted','policy_changed'])
cases=read(r/'SIDECAR_CASES.json');assert len(cases)==20 and len({row['case'] for row in cases})==20
assert sum(row['rejected'] for row in cases)==17
for row in cases:
 assert row==read(r/(row['case']+'-CASE.json'))
 if row['rejected']:assert row['unchanged'] and row['error']
 else:
  assert row['case'] in ['utf8-exact','replacement-committed','partial-temp-preserved']
  snap=row['snapshot'];assert snap['bytes']==sum(snap['sizes'].values())<=snap['budget']['maximum_bytes']
  assert snap['files']==len(snap['sizes'])<=snap['budget']['maximum_files']
  directory={'utf8-exact':'utf8','replacement-committed':'group','partial-temp-preserved':'interrupted'}[row['case']]
  files={x.name:dict(bytes=x.stat().st_size,sha256=sha(x)) for x in (r/'fixtures'/directory).iterdir()}
  assert files==row['inventory']
utf=r/'fixtures/utf8';value=read(utf/'control.json');raw=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
assert (utf/'control.json').read_bytes()==raw and (utf/'trace.jsonl').read_bytes()==raw+b'\n'
assert any(x>127 for x in raw)
assert (r/'fixtures/file/one.log').read_bytes()==b'a'*90
assert (r/'fixtures/group/one.bin').read_bytes()==b'c'*40
assert (r/'fixtures/interrupted/old.json').read_bytes()==b'old'
assert (r/'fixtures/interrupted/old.json.pending').read_bytes()==b'ne'
assert list(r.rglob('*.pending'))==[r/'fixtures/interrupted/old.json.pending']
for name in ['unknown-key','bool-limit','wrong-floor','bad-order','overmax-files']:assert not list((r/'fixtures'/name).iterdir())
for folder in (r/'fixtures').iterdir():
 for x in folder.iterdir():assert x.is_file() and not x.is_symlink() and x.stat().st_nlink==1
 guard=folder/'.budget.guard'
 if guard.exists():
  assert guard.stat().st_size==0
  with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert out['cases']==20 and out['rejections']==17 and out['normal_and_failed_writes_preserved'] and out['ownership_closed']
assert not any(out[k] for k in ['models','capture','GUI','audio','controller','whole_run_integrated','capture_admitted','policy_changed'])
assert not list(r.rglob('*.wav')) and not list(r.rglob('epoch.json')) and not (r/'deployment').exists() and not (r/'data').exists()
assert sha(r/'LIVE_CONFIG_BACKUP.json')==a['live_config_sha256'] and sha(r/'INSTALL_BACKUP.json')==a['install_sha256']
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for p in owners:
 o=read(p);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<4*1024**2
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-sidecar-budget-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
