"""Independent quiet-capture review. See README_REVIEW_FIELD_LIVE_GUI_V3.md."""
import hashlib
import json
from pathlib import Path
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    run = 'field-live-gui-v2'
    x = remote('RUN='+repr(run)+'\n'+r'''
import os,json,hashlib,subprocess,fcntl,math,wave,struct,resource,sys
sys.dont_write_bytecode=True
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2)
r=Path.home()/'JustPeachy/research/nemotron-20260928';d=r/RUN
sys.path.insert(0,str(d));from review_live_artifacts_v1 import decode
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert a['mode']=='autonomous_quiet' and a['capture_seconds']==28 and a['audio_saved'] and a['capture']
assert sha(d/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')==a['authority_sha256']
for row in a['files']:assert sha(row['path'])==row['sha256'],row['path']
owners=[]
for path in sorted(d.rglob('*OWNER.json')):
 o=json.loads(path.read_text());t=ticks(o['pid']);assert not(o['boot_id']==boot and t==o['start_ticks']);owners.append(dict(owner=o,observed_start_ticks=t,exact_alive=False))
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for lock in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with lock.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
env=json.loads((d/'LIVE_ENVELOPE.json').read_text());assert env['affinity']==[2,3] and env['address_space']==[768*1024**2]*2 and env['stack']==[1048576]*2
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==8*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
assert int(env['properties']['MainPID'])==json.loads((d/'OWNER.json').read_text())['pid']
dispatch=json.loads((d/'DISPATCH_RESULT.json').read_text());v=json.loads((d/'RESULT.json').read_text())
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert v['controller_closed'] and v['Tk_destroyed'] and not v.get('closure_error')
assert v['callback_detail_bound'] and v['startup_stack_rlimit_bytes']==[1048576]*2 and v['native_default_thread_stack_bytes']==1048576
passed=v['status']=='INSTALLED_GUI_QUIET_COLLECTED_REQUIRES_INDEPENDENT_REVIEW'
assert dispatch['exit_code']==(0 if passed else 1)
assert not passed and v['error']=="RuntimeError: AttributeError: 'N2ResidentModels' object has no attribute 'punctuation_loads'"
assert v['callback_errors']==["AttributeError: 'N2ResidentModels' object has no attribute 'punctuation_loads'"]
captured=True
stop=v.get('terminal_source_stop_receipt') or v.get('source_stop_receipt')
n=v.get('terminal_source_samples',0)
if stop:
 terminal=stop['terminal'];close=terminal['source_close']
 assert not close['errors'] and all(x in ('RESTORED','ALREADY_RESTORED') for x in close['route_restoration'].values())
 assert stop['child_exit']==0 and not stop['forced_close'] and close['stream_closed'] and close['lease_released']
 childdir=next((d/'data/source_receipts').iterdir())
 child=json.loads((childdir/'CHILD_RESULT.json').read_text())
 assert child.pop('terminal_sent') and child.pop('terminal_acknowledged') and child==terminal
 assert child['address_space']==[256*1024**2]*2 and child['stack']==[1048576]*2 and child['affinity']==[2,3]
 assert child['high_blocks']<=64 and child['high_bytes']<=65536
 assert json.loads((childdir/'PRE_ROUTE_SNAPSHOT.json').read_text())==json.loads((childdir/'POST_ROUTE_SNAPSHOT.json').read_text())
 assert close['final_status']['pending_raw_blocks']==0
if captured:
 assert 448000<=n<=512000 and terminal['sent_samples']==n and terminal['fault'] is None
 assert not v.get('controller_save_open') and not v['controller_worker_alive']
summary=dict(success=passed,functional_capture_and_GUI_Stop_verified=captured,error=v.get('error'),process_exit=dispatch['exit_code'],peak_rss_bytes=v['peak_rss_bytes'],elapsed_seconds=v['elapsed_seconds'],source_stop_receipt=stop,source_timeline=v.get('terminal_source_timeline'),new_audio_reference_pending=True)
bindings={name:sha(d/name) for name in ['ADMISSION.json','RESULT.json','DISPATCH_RESULT.json','LIVE_ENVELOPE.json','SOURCE_DERIVATIVE.json','ALSA_ENVIRONMENT.json']}
sessions=[]
for item in v.get('sessions',[]):
 s=Path(item['session_dir']);assert s.parent==d/'data/sessions'
 docs={name:json.loads((s/name).read_text()) for name in ['session_summary.json','session_finalization_v3.json','s6d_consumer_closure.json']}
 events=decode(s/'events.jsonl');cursor=0;texts=0;embedding_calls=0;first_text=None;first_d1=None;origin=None;completed=None
 for e in events:
  q=e['payload'];kind=e['event_type']
  if kind=='source_started':origin=q['source_epoch_monotonic_sec'];assert q['session_id']==s.name
  if kind=='s6d_text_ready':
   texts+=1;first_text=q['publication_monotonic_sec'] if first_text is None else first_text
  if kind=='research_embedding':embedding_calls+=1
  if kind=='session_completed':completed=q['publication_monotonic_sec']
  if kind=='n2_diarization_frames':
   assert q['session_id']==s.name and q['frame_start']==cursor and abs(q['frame_step_sec']-.01)<1e-8
   rows=q['probabilities'];assert rows and all(len(row)==8 and all(math.isfinite(z) and 0<=z<=1 for z in row) for row in rows)
   cursor+=len(rows);first_d1=q['available_at_monotonic'] if first_d1 is None else first_d1
 t=docs['session_summary.json']['telemetry'];costs=t['component_costs']['rows'];f=docs['session_finalization_v3.json'];c=docs['s6d_consumer_closure.json']
 assert f['event_and_transcript_handles_closed'] and not f['resident_bundle_lease_retained'] and not f['live_lanes_at_finalization']
 assert c['full_event_consumer_drained'] and c['queues']['event_consumer']['depth']==0
 for name in ['journal','punctuation','policy']:
  q=c['queues'][name];assert q['closed'] and not q['thread_alive'] and not q['error'] and q['depth']==0 and q['accepted']==q['completed']
 if captured:
  assert f['state']=='COMPLETED' and not f['finalization_error'] and f['source_samples']==f['identity_samples']==n
  assert t['audio_frames_dropped']==0 and t['identity_audio_samples']==t['paired_audio_samples']==n
  for name in ['asr_accept','diarizer_push']:assert costs[name]['successful_samples']==n
  for cost in costs.values():assert cost['errors']==cost['in_flight']==0 and cost['started']==cost['completed']
  assert cursor>0 and cursor==costs['diarizer_push']['output_frames']+costs['diarizer_finish']['output_frames'] and t['punctuation_inference_failures']==0
 sessions.append(dict(source_samples=f['source_samples'],probability_frames=cursor,text_publications=texts,E0_calls=embedding_calls,first_text_seconds=None if first_text is None else first_text-origin,first_d1_seconds=None if first_d1 is None else first_d1-origin,completion_seconds=None if completed is None else completed-origin,model_costs=costs,finalization_state=f['state']))
 for name in docs:bindings[str((s/name).relative_to(d))]=sha(s/name)
 bindings[str((s/'events.jsonl').relative_to(d))]=sha(s/'events.jsonl')
archives=[]
for folder in (d/'data/conversations').glob('*/epochs/*'):
 m=json.loads((folder/'epoch.json').read_text());assert m['closed'] and not m['archive_error'] and m['audio_enabled'] and m['queue_items']==m['queue_bytes']==0 and m['accepted_items']==m['completed_items']
 floats=(folder/'model_input.f32le').read_bytes();n=len(floats)//4;assert len(floats)==n*4 and n==m['recorded_samples']==m['source_samples']
 with wave.open(str(folder/'model_input.wav'),'rb') as w:
  assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,n);pcm=w.readframes(n)
 expected=bytearray();clipped=0
 for value, in struct.iter_unpack('<f',floats):
  assert math.isfinite(value);clipped+=int(value < -1 or value > 32767/32768)
  expected+=struct.pack('<h',round(max(-1,min(32767/32768,value))*32768))
 assert pcm==expected and clipped==m['artifact_metrics']['audio']['clipped_samples']
 count=sum(1 for _ in decode(folder/'events.jsonl'))
 assert sha(folder/'model_input.f32le')==m['audio_sha256'] and m['audio_bytes']==6*n+44
 if captured:assert n==v['terminal_source_samples'] and m['state']=='CLOSED' and m['artifact_metrics']['events']['status']==m['artifact_metrics']['audio']['status']=='COMPLETE'
 archives.append(dict(samples=n,pcm_sha256=sha(folder/'model_input.wav'),float_sha256=sha(folder/'model_input.f32le'),events=count,event_bytes=(folder/'events.jsonl').stat().st_size,clipped_samples=clipped,state=m['state']))
 for name in ['epoch.json','model_input.wav','model_input.f32le','events.jsonl']:bindings[str((folder/name).relative_to(d))]=sha(folder/name)
if captured:
 assert len(sessions)==len(archives)==1 and not close['final_status']['fault'] and close['final_status']['dropped_frames']==0
 assert archives[0]['samples']==n==sessions[0]['source_samples']
 assert archives[0]['float_sha256']==terminal['audio_sha256']
 t=v['terminal_source_timeline'];assert t['model_samples_accepted']==n and t['native_frames_accepted']==n*3 and t['max_native_lead_ns']<=0
 assert v['terminal_source_metadata']['actual_stream_rate']==48000 and v['terminal_source_metadata']['resampler_delay_seconds']==.001
 assert v['terminal_source_integrity']['ok'] and not v['root_withdrawn']
 summary['optional_model_load_counts_not_collected']=True
 summary['post_Stop_Save_Open_and_stopped_image_not_reached']=True
 trace=[json.loads(line) for line in (childdir/'TRACE.jsonl').read_text().splitlines()]
 assert len(trace)==terminal['sent_blocks']
 offset=0;native=0;epoch=None;previous_adc=None;maximum_ipc=0
 for item in trace:
  m=item['metadata'];count=item['samples'];assert m['model_start_sample']==offset and m['native_start_frame']==native and m['native_frames']==count*3
  assert m['callback_monotonic_ns']<=m['delivery_monotonic_ns']<=item['ipc']['published_ns']<=item['ipc']['received_ns']
  if epoch is None:epoch=m['epoch']
  assert m['epoch']==epoch and item['audio_sha256']==hashlib.sha256(floats[offset*4:(offset+count)*4]).hexdigest()
  if previous_adc is not None:assert m['adc_time_seconds']>=previous_adc
  previous_adc=m['adc_time_seconds'];maximum_ipc=max(maximum_ipc,item['ipc']['received_ns']-item['ipc']['published_ns'])
  offset+=count;native+=m['native_frames']
 assert offset==n and native==n*3==close['bridge_native_frames'] and close['bridge_model_samples']==n
 summary.update(source_blocks=len(trace),maximum_observed_ipc_seconds=maximum_ipc/1e9,pending_raw_at_stop=close['original_stop_status']['pending_raw_blocks'],final_pending_raw=0,stop_request_samples=v['stop_requested_at']['samples'])
if captured:
 assert v['stop_requested_at']['via']=='actual_GUI_start_stop_button'
 actions=[x['name'] for x in v['actions']]
 assert actions==['Start_opened_consent','authorized_quiet_Start_confirmed','GUI_Stop_invoked'],actions
 for obs in v['observations']:
  assert (obs['width'],obs['height'])==(480,800) and sha(d/(obs['name']+'.png'))==obs['sha256']
 assert {x['name'] for x in v['observations']}=={'idle','consent','running'}
 installed=Path(a['installed_release'])
 assert {x.relative_to(installed).as_posix():sha(x) for x in installed.rglob('*') if x.is_file()}==a['installed_files']
 assert sha(installed/'RELEASE_MANIFEST.json')==a['release_manifest_sha256']
 built=json.loads((d/'CANDIDATE_BUILD.json').read_text());candidate=Path(built['staged']['path'])
 assert candidate==Path(v['installed_release']) and sha(candidate/'RELEASE_MANIFEST.json')==built['manifest_sha256']
 assert sha(Path(built['built']['archive']))==built['built']['sha256']
 manifest=json.loads((candidate/'RELEASE_MANIFEST.json').read_text())
 for row in manifest['files']:assert sha(candidate/row['path'])==row['sha256'] and (candidate/row['path']).stat().st_size==row['bytes']
 assert manifest['version']=='b01-offline-20260930-v5'
 assert sha(candidate/'config/alsa_hw_only_v1.conf')=='d81bc353dcab14d172e78b26c6116bfc8462b96e45e44b1a93ac3f217898564d'
 assert not (candidate/'config/unrelated.conf').exists() and built['unrelated_conf_excluded']
 old=(installed/'release_tools/release.py').read_text()
 before="if path.suffix.lower() not in ALLOWED_SUFFIXES and path.name != 'LICENSE':"
 after="if path.suffix.lower() not in ALLOWED_SUFFIXES and path.name != 'LICENSE' and rel.as_posix() != 'config/alsa_hw_only_v1.conf':"
 assert (candidate/'release_tools/release.py').read_text()==old.replace(before,after)
 assert sha(candidate/'native/field_entry_v5.py')==sha(d/'field_entry_v5.py')
 summary['candidate_build']=built
 bindings['CANDIDATE_BUILD.json']=sha(d/'CANDIDATE_BUILD.json')

 summary.update(actions=actions,observations=v['observations'],installed_release_unchanged=True,physical_touch=False)
series=[z for z in dispatch['samples'] if 'cpu_stat' in z]
assert len(series)>=3
keys=['usage_usec','nr_periods','nr_throttled','throttled_usec']
assert all(series[-1]['cpu_stat'][k]>=series[0]['cpu_stat'][k] for k in keys)
summary['live_resources']=dict(samples=len(series),temperature_min=min(z['temperature_c'] for z in series),temperature_max=max(z['temperature_c'] for z in series),throttle_values=sorted(set(z['throttle'] for z in series)),cpu_stat_delta={k:series[-1]['cpu_stat'][k]-series[0]['cpu_stat'][k] for k in keys},clock_hz_min=min(v for z in series for v in z['clock_hz'].values()),clock_hz_max=max(v for z in series for v in z['clock_hz'].values()))
summary['sampled_aggregate_peak_bytes']=max(z.get('aggregate_rss_bytes',0) for z in dispatch['samples'])
peaks={}
for sample in dispatch['samples']:
 for process in sample.get('process_samples',[]):
  key=str(process['owner']['pid']);r=peaks.setdefault(key,dict(rss_kib=0,vmpeak_kib=0,threads=0))
  for outkey,inkey in [('rss_kib','VmRSS'),('vmpeak_kib','VmPeak'),('threads','Threads')]:r[outkey]=max(r[outkey],process['values'].get(inkey,0))
summary['sampled_process_peaks']=peaks
output=sum(p.stat().st_size for p in d.rglob('*') if p.is_file());assert output<a['target_output_max_bytes']
summary.update(sessions=sessions,archives=archives,target_bytes=output,capture_closed=True,leases_free=True,baseline_unchanged=True)
print(json.dumps(dict(summary=summary,bindings=bindings,owners=owners)))
''')
    out=PRIVATE/(run+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==x['summary']['process_exit']
    review=dict(status='REVIEWED_INSTALLED_GUI_CAPTURE_STOP_WITH_POSTCHECK_FAILURE',**x,review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),accuracy_scored=False,numerical_reference_qualified=False,endurance_qualified=False,stage_accepted=False)
    with (out/'REVIEW.json').open('x') as f:json.dump(review,f,indent=2)
    remote('RUN='+repr(run)+'\nREVIEW='+repr(review)+'\n'+"import json\nfrom pathlib import Path\np=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN/'REVIEW.json'\nwith p.open('x') as f:json.dump(REVIEW,f,indent=2)\nprint(json.dumps({'written':True}))")
    import subprocess,tarfile,io
    from pathlib import PurePosixPath
    from dispatch_b01_stack_v2 import SSH
    from dispatch_geometry_v2 import REMOTE
    inventory=remote('RUN='+repr(run)+'\n'+"import json,hashlib\nfrom pathlib import Path\nr=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN\nassert not any(p.is_symlink() for p in r.rglob('*'))\ndef sha(p):\n with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()\nprint(json.dumps({p.relative_to(r).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in r.rglob('*') if p.is_file()}))")
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/'+run+' -cf - .'],timeout=90)
    backup=out/'target';backup.mkdir();seen=set()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as archive:
        for member in archive:
            if member.isdir():continue
            assert member.name.startswith('./');name=member.name[2:];path=PurePosixPath(name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts and name in inventory and name not in seen
            raw=archive.extractfile(member).read();assert len(raw)==inventory[name]['bytes'] and hashlib.sha256(raw).hexdigest()==inventory[name]['sha256']
            target=backup.joinpath(*path.parts);target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(raw)
            assert hashlib.sha256(target.read_bytes()).hexdigest()==inventory[name]['sha256'];seen.add(name)
    assert seen==set(inventory)
    total=sum(v['bytes'] for v in inventory.values());combined=total+sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert total<32*1024**2 and combined+1024**2<64*1024**2
    receipt=dict(status='EXACT_PRIVATE_TARGET_BACKUP_VERIFIED',files=inventory,target_bytes=total,combined_bytes=combined)
    with (out/'BACKUP.json').open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(dict(status=review['status'],success=x['summary']['success'],source_samples=[s['source_samples'] for s in x['summary']['sessions']],target_bytes=total,backup_files=len(seen),backup_verified=True,live_resources=x['summary']['live_resources'])))


if __name__=='__main__':main()
