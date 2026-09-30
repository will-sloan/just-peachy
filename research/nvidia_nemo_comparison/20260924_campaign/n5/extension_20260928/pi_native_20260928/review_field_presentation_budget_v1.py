"""Independent compact binding review; README_FIELD_PRESENTATION_BUDGET_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-presentation-budget-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_SELECTED_PRESENTATION_FAILURE_AND_STOP_METHODS_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
cases=read(r/'PRESENTATION_CASES.json')
assert len(cases)==13 and len({x['case'] for x in cases})==13
for row in cases[:6]:
 assert row['rejected'] and not row['directory_created'] and not (r/'fixtures'/row['case']).exists()
for row in cases[6:]:
 name=row['case'];d=r/'fixtures'/name
 assert row['worker_joined'] and row['pending_commands']==0 and row['actions'].count('session-cleanup-stub')==1
 failed=name!='mapped-write'
 assert row['source_stop_requested']==failed and bool(row['error'])==failed
 assert row['state']==('ERROR' if failed else 'STOPPED')
 if failed:assert row['error']=='GUI_PRESENTATION_WRITE_FAILED' and row['source_error']=='ISOLATED_LIVE_FAILURE: GUI_PRESENTATION_WRITE_FAILED'
 if name=='queue-full':assert row['failure']['source_stop_requested'] and not row['failure']['stop_enqueued'] and row['actions'][0]=='noop'
 if name=='diagnostic-quota':assert not row['failure']['raw_retained'] and not row['failure']['receipt_retained']
 elif failed:
  raw=d/'failure/presentation.bin';f=row['failure'];assert raw.stat().st_size==f['bytes'] and sha(raw)==f['sha256']
  assert read(d/'failure/presentation.json')['receipt_retained']
 if name=='closure-quota':assert row['closure'] is None and row['finish_failure'] and not (d/'closure_reserve/PRESENTATION_CLOSURE.json').exists()
 else:
  closure=read(d/'closure_reserve/PRESENTATION_CLOSURE.json');assert closure==row['closure']
  assert closure['logical_success']==(not failed) and closure['cleanup_returned']==(name!='cleanup-failure')
 assert row['cleanup_outcome']['cleanup_returned']==(name!='cleanup-failure')
 trace=d/'telemetry/gui_presentation.jsonl'
 assert trace.exists()==(name in ['mapped-write','append-quota'])
 if trace.exists():assert trace.stat().st_size==row['telemetry_bytes'] and sha(trace)==row['telemetry_sha256'] and len(trace.read_text().splitlines())==1
 cfg=read(r/(name+'-DESCRIPTOR.json'))
 for group,limits in cfg['groups'].items():
  sizes=[p.stat().st_size for p in (d/group).iterdir() if p.name!='.budget.guard']
  assert sum(sizes)<=limits['maximum_bytes'] and len(sizes)<=limits['maximum_files'] and all(n<=limits['maximum_file_bytes'] for n in sizes)
for guard in r.rglob('.budget.guard'):
 assert guard.stat().st_size==0
 with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert out['cases']==13 and out['descriptor_rejections']==6 and out['selected_method_cases']==out['worker_loops']==7
assert out['controller_constructors']==out['source_audio_samples']==0
assert not any(out[k] for k in ['models','capture','GUI','physical_cleanup','whole_run_integrated','policy_changed'])
assert not list(r.rglob('*.pending')) and not list(r.rglob('*.wav'))
for sample in dispatch['samples']:
 ids=[tuple(i) for i in sample.get('aggregate_unique_identities',[])]
 assert len(ids)==len(set(ids))
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
    with (PRIVATE/'field-presentation-budget-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
