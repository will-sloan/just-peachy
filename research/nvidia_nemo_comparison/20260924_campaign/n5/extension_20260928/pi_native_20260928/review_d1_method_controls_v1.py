"""Independent compact binding review; README_D1_METHOD_CONTROLS_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/d1-method-controls-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'control/ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'control/LIVE_ENVELOPE.json')
assert out['status']=='PASS_D1_METHOD_CONTRACT_AND_WITHDRAWN_CONTROLS_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
contract=read(r/'code/D1_METHOD_CONTRACT_V1.json')
assert sha(r/'code/METHOD_EVIDENCE_V1.json')==contract['evidence_sha256']
cases=read(r/'passage/CASES.json');profiles=read(r/'passage/PROFILES.json');texts=read(r/'passage/TEXT.json')
assert len(cases)==out['cases']==30 and len({x['case'] for x in cases})==30
assert sum(x.get('rejected',False) for x in cases)==out['expected_rejections']==18
assert all(out[k] for k in ['actual_new_navigation','installed_Base_fixture','all_audio_policy_retained'])
assert not any(out[k] for k in ['production_start_executed','models','ASR','capture','visible_rendering','physical_touch','new_benchmark','old_model_passages_rerun'])
assert out['source_samples']==0 and out['actual_Tk_views']==9
for mode,profile in profiles.items():
 assert profile['geometry']==contract['modes'][mode]['geometry'] and profile['assets_sha256']==contract['modes'][mode]['assets_sha256']
 assert profile['resources']['executable_graph_lru']==(1 if mode=='delayed' else 8)
 assert profile['all_audio_retained'] and profile['live_start_available'] is False
 c=profile['retained_kernel_comparison']
 assert c['source_samples']==715127 and c['max_abs']==0 and c['original_rc5_concurrent']
 assert abs(c['less_wall_percent']-(1-c['a76_seconds']/c['generic_seconds'])*100)<1e-10
 assert not c['measured_application_speedup'] and not c['sustained_speedup'] and not c['cross_geometry_speedup']
 assert 'No application/sustained/cross-mode speedup' in texts[mode]['kernel']
 assert 'All audio is retained' in texts[mode]['unavailable']
 assert c['selected_main_equals_comparison_main'] is (mode!='delayed')
closure=read(r/'passage_closure/CONTROL_CLOSURE.json')
assert closure==dict(Tk_destroyed=True,command_threads_created=0,model_workers_created=0,source_samples=0,fixture_start_delegations=1)
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
    with (PRIVATE/'d1-method-controls-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
