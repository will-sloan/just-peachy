"""Independent compact binding review; README_D1_VISIBLE_ENTRY_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/d1-visible-entry-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'control/ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'control/LIVE_ENVELOPE.json')
top=out
assert out['status']=='PASS_VISIBLE_D1_ENTRY_INSPECTION_AND_RETURN_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h

assert all(out[k] for k in ['actual_controller_constructor','actual_ui_constructor','visible_rendering','actual_return_button','Tk_destroyed','command_worker_joined','application_lease_released','parent_closed_by_button','visible_parent_return','child_reaped','child_pipe_closed','child_deadline_watcher_joined','child_owner_acknowledged','fresh_process_mode_entry'])
assert not any(out[k] for k in ['physical_touch','model_start_available','model_loaded','capture','ASR','native_failure_stress','new_speedup_claim','accuracy_claim'])
assert out['source_samples']==out['frames']==0 and a['models_loaded'] is False
app=read(r/'app_receipts/APPLICATION_CLOSURE.json');gui=read(r/'app_receipts/VISIBLE_CONTROLS.json')
assert all(app[k] for k in ['controller_closed','command_worker_joined','no_model_worker_created','application_lease_released','Tk_destroyed','actual_return_button'])
assert sorted(q.relative_to(r).as_posix() for q in r.rglob('*') if q.is_dir())==app['directories']
assert gui['model_start_disabled'] and gui['application_lease_owned'] and not gui['physical_touch']
selection=gui['selection'];assert selection['inspection_only'] and not selection['start_available'] and not selection['owned']
assert selection['samples']==selection['frames']==0 and selection['selected']['selection']['id']=='streaming'
profile=selection['implemented_methods']
assert profile['mode']=='streaming' and profile['resources']['gpu'] is False and profile['all_audio_retained'] is True
assert profile['contract_sha256']=='1ae32a068914370a4c237a5a0545c9452fd56c95346b8a8f9b091b39bdf2d629'
assert out['selected_profile_sha256']==hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
assert not (r/'data/runtime.lock').exists() and read(r/'data/DATA_SCHEMA.json')=={'schema_version':1}
assert not list((r/'data/people').iterdir()) and not list((r/'data/conversations').iterdir())
assert read(r/'app_receipts/last_application.json')['microphone_open'] is False
assert not (r/'passage/START_REQUEST.json').exists() and not (r/'passage/PROBABILITIES.npy').exists()
for group in ['passage','passage_closure','app_failure']:assert not [q for q in (r/group).iterdir() if q.name!='.budget.guard']
packet=read(r/'launch_meta/REQUEST.json');owner=read(r/'launch_meta/ENTRY_OWNER.json');ack=read(r/'launch_meta/ACK.json')
assert ack==dict(owner=owner,request_sha256=sha(r/'launch_meta/REQUEST.json'))
assert packet['request']==out['mode_entry_request'] and packet['request']['mode']=='streaming'
assert packet['request']['session_id']=='d1-visible-entry-v1' and packet['request']['registry_sha256']==sha(r/'code/D1_MODE_ENTRY_MANIFEST_V1.json')
assert out['launcher_parent']==packet['parent'] and out['child_owner']==owner and owner['pid']!=packet['parent']['pid']
launch=read(r/'launch_meta/LAUNCH_CLOSURE.json');child=read(r/'launch_meta/CHILD_RESULT.json')
assert launch['owner']==owner and launch['reaped'] and launch['pipe_closed'] and launch['acknowledged']
assert child['parent_acknowledged_before_constructor'] and child['status']==out['status']
assert launch['watcher']['returncode']==0 and not launch['watcher']['terminate_sent'] and not launch['watcher']['kill_sent']
assert launch['output_bytes']==(r/'launch_logs/child.log').stat().st_size==0
assert packet['deadline']['hard_ns']-packet['deadline']['issued_ns']==60_000_000_000 and packet['deadline']['grace_ns']==2_000_000_000
assert launch['watcher']['reaped_ns']<packet['deadline']['soft_ns']
visual=read(r/'visual_meta/VISIBLE_LIFECYCLE.json')
assert visual['child_reaped_before_return'] and visual['parent_closed_by_button'] and not visual['physical_touch']
assert [visual['chooser'],visual['returned']]==out['parent_screenshots'] and gui['screenshot']==out['child_screenshot']
for shot in out['parent_screenshots']+[out['child_screenshot']]:
 q=r/'visual_images'/(shot['name']+'.png');raw=q.read_bytes()
 assert sha(q)==shot['sha256'] and len(raw)==shot['bytes']<=256*1024 and shot['returncode']==0
 assert shot['geometry']=='480x800+0+0' and shot['compositor_capture'] and not shot['physical_touch']
 assert raw[:8]==b'\x89PNG\r\n\x1a\n' and int.from_bytes(raw[16:20],'big')==480 and int.from_bytes(raw[20:24],'big')==800
 assert read(r/'visual_meta'/(shot['name']+'-OWNER.json'))==shot['owner']
for boxes in [visual['chooser_rectangles'],visual['returned_rectangles'],gui['rectangles']]:
 for rect in boxes.values():assert rect['x']>=0 and rect['y']>=0 and rect['width']>1 and rect['height']>1 and rect['x']+rect['width']<=480 and rect['y']+rect['height']<=800
os.environ.update(WAYLAND_DISPLAY='wayland-0',XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()))
display=subprocess.check_output(['wlr-randr'],text=True)
assert 'Transform: 270' in display and 'Enabled: yes' in display
assert sha(Path.home()/'.config/kanshi/config')=='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b'
for group,key in [('passage','passage_limits'),('passage_closure','passage_closure_limits'),('app_receipts','app_receipt_limits'),('app_failure','app_failure_limits'),('launch_meta','launch_metadata_limits'),('launch_logs','launch_log_limits'),('visual_images','visual_image_limits'),('visual_meta','visual_metadata_limits')]:
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
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in samples),default=None),resource_rows=len(samples),temperature_range_c=[min(x['temperature_c'] for x in samples),max(x['temperature_c'] for x in samples)],throttle_states=sorted(set(x['throttle'] for x in samples)),minimum_available_ram_bytes=min(x['available_ram_bytes'] for x in samples),display_after=display,screenshot_visual_review_pending=True)))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'d1-visible-entry-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
