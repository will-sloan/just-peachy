"""Independent compact binding review; README_D1_METHOD_RECOVERY_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/d1-method-recovery-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'control/ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'control/LIVE_ENVELOPE.json')
top=out
assert out['status']=='PASS_INSTALLED_D1_PREOWNER_VALIDATION_RECOVERY_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
spec=read(r/'code/D1_METHOD_RECOVERY_INPUT_V1.json')
assert out['changed_cases']==6 and out['source_samples']==out['output_frames']==0
assert out['generic_state_status_error_checked'] and out['method_failure_recovers'] and out['unknown_failure_not_cleared']
assert not any(out[k] for k in ['model_worker_created','successful_start_tested','capture','ASR','visible_rendering','physical_touch','native_failure_stress','new_speedup_claim','accuracy_claim'])
assert all(out[k] for k in ['actual_controller_constructor','actual_ui_constructor','actual_command_queue','controller_closed','command_worker_joined','application_lease_released','Tk_destroyed'])
for name,h in spec['installed_files'].items():assert sha(Path(spec['prototype'])/name)==h
for pin in spec['method_binding'].values():assert Path(pin['path']).stat().st_size==pin['bytes'] and sha(pin['path'])==pin['sha256']
for item in list(spec['availability'].values())+list(spec['saved_application_evidence'].values()):
 assert sha(r/'code'/item['receipt'])==item['sha256'] and read(r/'code'/item['receipt'])['status']==item['status']
gui=read(r/'app_receipts/RECOVERY.json');cases=gui['cases'];assert len(cases)==6
assert [c['case'] for c in cases]==['queued_profile_reject','stop_retains_validation_error','invalid_reselection_stays_error','explicit_valid_selection_recovers_both','source_kind_sentinel_blocks_selection','unrelated_error_not_cleared_after_sentinel_removed']
for i,c in enumerate(cases):
 assert c['source_samples']==0 and not c['model_worker_created']
 assert c['state']==('IDLE' if i==3 else 'ERROR')
 assert c['start_available'] is (i==3) and c['start_button']==('normal' if i==3 else 'disabled')
 assert c['recovery_available'] is (i<3)
assert cases[0]['error']==cases[1]['error'] and cases[3]['error'] is None and cases[3]['d1_error'] is None
assert cases[3]['status']=='Saved diarizer ready. Microphone is off.'
assert 'cannot clear another failure' in cases[5]['error']
assert gui['root_withdrawn'] and gui['actual_controller_constructor'] and gui['actual_ui_constructor'] and gui['actual_command_queue']
assert gui['source_kind_sentinel'] and not gui['source_or_model_failure_tested'] and not gui['successful_start_tested']
assert not list((r/'passage').glob('*.json')) and not list((r/'passage').glob('*.npy'))
assert not list((r/'passage_closure').glob('*.json'))
app=read(r/'app_receipts/APPLICATION_CLOSURE.json')
assert all(app[k] for k in ['controller_closed','command_worker_joined','application_lease_released','Tk_destroyed'])
assert app['model_worker_created'] is False and app['source_samples']==0
assert sorted(q.relative_to(r).as_posix() for q in r.rglob('*') if q.is_dir())==app['directories']
assert not (r/'data/runtime.lock').exists() and read(r/'data/DATA_SCHEMA.json')=={'schema_version':1}
assert not list((r/'data/people').iterdir()) and not list((r/'data/conversations').iterdir())
assert read(r/'app_receipts/last_application.json')['microphone_open'] is False
loaded=read(r/'app_receipts/LOADED_MODULES.json')
assert loaded['all_origins_inside_exact_release'] and len(loaded['verified_loaded_modules'])>0
assert loaded['installed_manifest_sha256']==sha(Path(spec['prototype'])/'RELEASE_MANIFEST.json')
for group,key in [('passage','passage_limits'),('passage_closure','passage_closure_limits'),('app_receipts','app_receipt_limits'),('app_failure','app_failure_limits')]:
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
    with (PRIVATE/'d1-method-recovery-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
