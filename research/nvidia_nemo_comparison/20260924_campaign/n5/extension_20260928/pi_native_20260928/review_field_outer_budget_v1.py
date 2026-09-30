"""Independent compact binding review; README_FIELD_OUTER_BUDGET_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-outer-budget-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_OUTER_OUTPUT_FAILURE_FIXTURES_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
cases=read(r/'OUTER_CASES.json')
assert len(cases)==9 and len({x['case'] for x in cases})==9
for row in cases:
 name=row['case'];d=r/'fixtures'/name;v=row['outcome'];raw=(r/(name+'-INPUT.bin')).read_bytes()
 assert not v['logical_success'] and v['work_complete'] and v['exit_code']==0
 assert v['rejected_bytes']==len(raw) and v['rejected_sha256']==hashlib.sha256(raw).hexdigest()
 assert row['stop_calls']==(0 if name=='closure' else 1)
 if name=='diagnostic':assert not v['raw_retention_complete'] and not (d/'failure/fixture-rejected.bin').exists()
 elif raw:assert v['raw_retention_complete'] and (d/'failure/fixture-rejected.bin').read_bytes()==raw
 if name=='closure':assert not v['closure_retained'] and not (d/'closure_reserve/fixture-OUTPUT_CLOSURE.json').exists()
 else:assert v['closure_retained'] and read(d/'closure_reserve/fixture-OUTPUT_CLOSURE.json')==v
 if name=='log-append-tail':assert (d/'logs/service.log').read_bytes()==b'old' and raw==b'REJECTEDTAIL'
 elif name in ['log-first','diagnostic','stop-error']:assert not (d/'logs/service.log').exists()
 if name=='stop-error':assert 'counted Stop failure' in v['stop_error']
 if name=='nonfinite':assert v['failure']['error_type']=='ValueError' and not raw
for directory,cfg_path in [(r/'outer',r/'OUTER_DESCRIPTOR.json')]+[(r/'fixtures'/x['case'],r/(x['case']+'-DESCRIPTOR.json')) for x in cases]:
 cfg=read(cfg_path);dirs=[directory]+list(directory.iterdir());assert len(dirs)==6
 assert sum(max(p.stat().st_size,p.stat().st_blocks*512) for p in dirs)<=cfg['directory_reserve_bytes']
 for group,limits in cfg['groups'].items():
  sizes=[p.stat().st_size for p in (directory/group).iterdir() if p.name!='.budget.guard']
  assert sum(sizes)<=limits['maximum_bytes'] and len(sizes)<=limits['maximum_files'] and all(n<=limits['maximum_file_bytes'] for n in sizes)
for guard in r.rglob('.budget.guard'):
 assert guard.stat().st_size==0
 with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert out['cases']==9 and out['child_processes']==out['source_audio_samples']==0
assert not any(out[k] for k in ['models','capture','GUI','whole_run_integrated'])
assert not list(r.rglob('*.pending')) and not list(r.rglob('*.wav'))
samples=[json.loads(line) for line in (r/'outer/telemetry/resources.jsonl').read_bytes().splitlines()]
assert len(samples)==dispatch['resource_rows']>=1
for sample in samples:
 ids=[tuple(i) for i in sample['aggregate_unique_identities']];assert len(ids)==len(set(ids))
assert dispatch['process_reaped'] and dispatch['pipe_closed']
for role in ['gate','worker']:
 closure=read(r/'outer/closure_reserve'/(role+'-OUTPUT_CLOSURE.json'))
 assert closure['logical_success'] and closure['closure_retained'] and closure['work_complete'] and closure['failure'] is None
 assert closure['raw_retention_complete'] and closure['rejected_bytes']==0
 if role=='gate':assert closure['log_bytes']==(r/'outer/logs/service.log').stat().st_size and closure['resource_rows']==len(samples)
assert not (r/'RESULT.json').exists() and not (r/'DISPATCH_RESULT.json').exists() and not (r/'service.log').exists()
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
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in samples),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-outer-budget-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
