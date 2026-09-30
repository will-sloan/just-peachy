"""Independent compact binding review; README_D1_APPLICATION_CONTROLS_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/d1-application-controls-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'control/ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'control/LIVE_ENVELOPE.json')
assert out['status']=='PASS_D1_CONTROLS_WITHDRAWN_DETACHED_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
spec=read(r/'code/D1_APPLICATION_CONTROLS_BINDING_V1.json');installed=r.parent/spec['installed_relative_root']
for name,key in [('controller.py','controller_sha256'),('ui.py','ui_sha256'),('n2_models.py','models_sha256')]:assert sha(installed/'app'/name)==spec[key]
assert sha(r/'code/d1_modes_v1.py')==spec['selector_sha256'] and sha(r/'code/D1_MODE_CATALOG_V1.json')==spec['catalog_sha256']
cases=read(r/'passage/CASES.json');assert len(cases)==out['cases']==18 and len({x['case'] for x in cases})==18
assert out['expected_rejections']==12 and sum('error' in x for x in cases)==12
assert all(x['selection_unchanged'] for x in cases if 'selection_unchanged' in x)
assert out['actual_Tk_buttons'] and out['Tk_withdrawn'] and out['selected_installed_queue_methods'] and out['selected_installed_UI_call']
assert not any(out[k] for k in ['visible_rendering','physical_touch','controller_constructor','models','capture','application_launchable','full_application_installed'])
assert out['source_audio_samples']==out['pending_commands']==0 and out['all_command_threads_joined']
closure=read(r/'passage_closure/CONTROL_CLOSURE.json')
assert closure==dict(all_command_threads_joined=True,command_threads=3,pending_commands=0,Tk_destroy_called=True,checks_complete=True,old_start_delegations=0)
snapshot=read(r/'passage/CONTROL_SNAPSHOT.json');request=read(r/'passage/LAUNCH_REQUEST.json')
assert snapshot['selected']['id']=='chunk52' and not snapshot['pending'] and snapshot['can_select'] and not snapshot['launch_available']
assert request['selection']==snapshot['selected'] and request['launchable'] is False and request['requires_fresh_process'] and request['requires_independent_session']
assert [(m['id'],m['native_factory_checked']) for m in snapshot['modes']]==[('delayed',True),('streaming',False),('chunk52',False)]
for group,key in [('passage','passage_limits'),('passage_closure','passage_closure_limits')]:
 files=[q for q in (r/group).iterdir() if q.name!='.budget.guard'];limit=a[key]
 assert len(files)<=limit['maximum_files'] and sum(q.stat().st_size for q in files)<=limit['maximum_bytes']
 assert all(q.stat().st_size<=limit['maximum_file_bytes'] for q in files)
for group,limits in a['metadata_limits'].items():
 sizes=[p.stat().st_size for p in (r/group).iterdir() if p.name!='.budget.guard']
 assert sum(sizes)<=limits['maximum_bytes'] and len(sizes)<=limits['maximum_files'] and all(x<=limits['maximum_file_bytes'] for x in sizes)
assert not any((r/n).exists() for n in ['OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','ADMISSION.json'])
assert all((r/'control'/n).exists() for n in ['OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','ADMISSION.json'])
for guard in r.rglob('.budget.guard'):
 assert guard.stat().st_size==0
 with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
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
assert sha(r/'control/LIVE_CONFIG_BACKUP.json')==a['live_config_sha256'] and sha(r/'control/INSTALL_BACKUP.json')==a['install_sha256']
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for p in owners:
 o=read(p);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<4*1024**2
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in samples),default=None),resource_rows=len(samples),temperature_range_c=[min(x['temperature_c'] for x in samples),max(x['temperature_c'] for x in samples)],throttle_states=sorted(set(x['throttle'] for x in samples)),minimum_available_ram_bytes=min(x['available_ram_bytes'] for x in samples))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'d1-application-controls-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
