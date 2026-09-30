"""Independent compact binding review; README_FIELD_ARCHIVE_OVERLAY_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-archive-overlay-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_INSTALLED_RETAINED_ARCHIVE_OVERLAY_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
selected=Path(a['installed_release']);assert {p.relative_to(selected).as_posix():sha(p) for p in selected.rglob('*') if p.is_file()}==a['installed_files']
doc=read(r/'OVERLAY_MANIFEST.json');assert sha(r/'OVERLAY_MANIFEST.json')==a['overlay_descriptor_sha256']==out['descriptor_sha256']
for path,h in a['retained_overlay_files'].items():assert sha(path)==h
assert set(doc['modules'])=={'app.sessions','field_archive_budget_v2'} and doc['capture_enabled'] is False
assert doc['interchange']=='UNAVAILABLE_IN_OVERLAY'
budget=read(r/doc['budget']);contract=read(r/doc['contract']);old=read(selected/'config/field_contract.json')
assert sha(r/doc['budget'])==doc['budget_sha256'] and sha(r/doc['contract'])==doc['contract_sha256']
canonical=hashlib.sha256(json.dumps(budget,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert canonical==out['budget_sha256']==doc['budget_canonical_sha256']=='d2cc2038e868f93dde009a9403feb259879bba4e8c0a05e760d1e14d087f86f8'
assert contract=={**old,'archive_budget':dict(file=doc['budget'],sha256=doc['budget_sha256'],canonical_sha256=canonical)}
assert out['health']==read(r/'OVERLAY_HEALTH.json') and out['health']['effective_contract']==contract
assert out['health']['archive_budget']==out['store_policy']['archive_budget']==budget
assert len(out['rejections'])==16 and all(row['rejected'] for row in out['rejections'])
for row in out['rejections']:assert row==read(r/(row['case']+'.json'))
assert not list(r.rglob('must-not-publish')) and not list(r.rglob('*.sqlite')) and not list(r.rglob('*.wav')) and not list(r.rglob('*.f32le'))
assert not list(r.rglob('.*.tmp')) and not (r/'data/source_receipts').exists() and not (r/'data/sessions').exists()
epoch=Path(out['archive_path']);assert epoch.parent.parent.parent==r/'data/conversations'
meta=read(epoch/'epoch.json');assert sha(epoch/'epoch.json')==out['archive_metadata_sha256']
assert meta['state']=='CLOSED' and not meta['worker_alive'] and not meta['archive_error']
assert meta['accepted_items']==meta['completed_items']==meta['queue_bytes']==meta['queue_items']==0
assert meta['archive_budget']==budget and meta['archive_budget_sha256']==canonical
assert out['module_origins']['sessions']==doc['modules']['app.sessions']['path']
assert out['module_origins']['budget']==doc['modules']['field_archive_budget_v2']['path']
for key in ['controller','pipeline','paths']:assert out['module_origins'][key]==str(selected/'app'/(key+'.py'))
assert out['module_origins']['store_parent']==str(selected/'native/field_archive_v3.py')
closed=read(r/'OWNERSHIP_CLOSURE.json')
assert closed==dict(borrowed=dict(opened=1,closed=1),outer_released=True,controller_closed=True,worker_joined=True,pending_commands=0)
assert not (r/'data/runtime.lock').exists() and out['ownership_closed'] and out['base_unchanged'] and out['private_configs_unchanged']
assert not any(out[k] for k in ['capture','models','GUI','audio','engine_constructed','package_copied','catalogue_copied','pointer_activated'])
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
print(json.dumps(dict(status=out['status'],result=out,budget_sha256=out['budget_sha256'],target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-archive-overlay-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
