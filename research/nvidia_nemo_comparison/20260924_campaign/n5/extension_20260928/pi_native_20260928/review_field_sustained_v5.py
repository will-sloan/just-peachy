"""Independent quiet-capture review. See README_REVIEW_FIELD_SUSTAINED_V5.md."""
import hashlib
import json
from pathlib import Path
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    run = 'field-sustained-v4'
    x = remote('RUN='+repr(run)+'\n'+r'''
import os,json,hashlib,subprocess,fcntl,math,wave,struct,resource,sys
from pathlib import Path
sys.dont_write_bytecode=True
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
r=Path.home()/'JustPeachy/research/nemotron-20260928';d=r/RUN
sys.path.insert(0,str(d));from review_live_artifacts_v1 import decode
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert a['mode']=='autonomous_quiet' and a['capture_seconds']==120 and a['audio_saved'] and a['capture']
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
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='6min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
assert int(env['properties']['MainPID'])==json.loads((d/'OWNER.json').read_text())['pid']
dispatch=json.loads((d/'DISPATCH_RESULT.json').read_text());v=json.loads((d/'RESULT.json').read_text())
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert v['controller_closed'] and v['Tk_destroyed'] and not v.get('closure_error')
assert v['callback_detail_bound'] and v['startup_stack_rlimit_bytes']==[1048576]*2 and v['native_default_thread_stack_bytes']==1048576
passed=v['status']=='INSTALLED_GUI_QUIET_COLLECTED_REQUIRES_INDEPENDENT_REVIEW'
assert dispatch['exit_code']==(0 if passed else 1)
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
if passed:
 assert 1920000<=n<=2080000 and terminal['sent_samples']==n and terminal['fault'] is None
 assert v['controller_save_open'] and not v['controller_worker_alive']
summary=dict(success=passed,error=v.get('error'),process_exit=dispatch['exit_code'],peak_rss_bytes=v['peak_rss_bytes'],elapsed_seconds=v['elapsed_seconds'],source_stop_receipt=stop,source_timeline=v.get('terminal_source_timeline'),new_audio_reference_pending=True)
bindings={name:sha(d/name) for name in ['ADMISSION.json','RESULT.json','DISPATCH_RESULT.json','LIVE_ENVELOPE.json','SOURCE_DERIVATIVE.json','ALSA_ENVIRONMENT.json']}

assert not passed and v['status']=='FAILED_PRESERVED' and "OutputLimit('BYTE_LIMIT')" in v['error']
assert not v['controller_worker_alive'] and v['lease_closure']['released'] and v['lease_closure']['borrowed']==dict(opened=1,closed=1)
assert not any(z['name']=='GUI_Stop_invoked' for z in v['actions']) and not v.get('controller_save_open')
assert v['lease_closure']['pid']==v['owner']['pid'] and sha(d/'candidate/state.json')==v['lease_closure']['state_sha256']
assert all(z['lease']['token']==v['lease_closure']['token'] for z in v['observations'])
integrity=v['terminal_source_integrity']
assert not integrity['ok'] and integrity['journal_samples']==n==1842720
assert integrity['source_samples']==terminal['sent_samples']==1843200 and integrity['discarded_after_failure_samples']==480
assert terminal['fault'] is None and close['final_status']['fault'] is None and close['final_status']['dropped_frames']==0
assert v['terminal_source_timeline']['model_samples_accepted']==1842880
def partial_events(path, expected_footer):
 seq=0
 with path.open() as stream:
  for line in stream:
   row=json.loads(line)
   if row['format']=='footer':
    assert row['count']==seq and row['status']==expected_footer and stream.read()==''
    return
   assert row['format']=='event' and row['seq']==seq
   seq+=1
   yield row['value']
 raise AssertionError('Missing failure footer')
item=v['sessions'][0];session=Path(item['session_dir']);assert session.parent==d/'data/sessions'
docs={name:json.loads((session/name).read_text()) for name in ['session_summary.json','session_finalization_v3.json','s6d_consumer_closure.json']}
costs=docs['session_summary.json']['telemetry']['component_costs']['rows'];f=docs['session_finalization_v3.json'];q=docs['s6d_consumer_closure.json']['queues']
assert f['state']=='FAILED' and not f['event_and_transcript_handles_closed'] and not f['resident_bundle_lease_retained'] and not f['live_lanes_at_finalization']
assert f['source_samples']==f['identity_samples']==n
assert q['journal']['accepted']==10561 and q['journal']['completed']==10558 and q['journal']['error'] and not q['journal']['thread_alive']
assert costs['asr_accept']['successful_samples']==n and costs['diarizer_push']['successful_samples']==1708640
assert costs['diarizer_finish']['started']==costs['asr_finish']['started']==0
cursor=texts=event_count=0;origin=first=None
for event in partial_events(session/'events.jsonl','BYTE_LIMIT'):
 event_count+=1;kind=event['event_type'];payload=event['payload']
 if kind=='source_started':origin=payload['source_epoch_monotonic_sec']
 if kind=='s6d_text_ready':texts+=1
 if kind=='n2_diarization_frames':
  assert payload['frame_start']==cursor and abs(payload['frame_step_sec']-.01)<1e-8
  rows=payload['probabilities'];assert rows and all(len(row)==8 and all(math.isfinite(z) and 0<=z<=1 for z in row) for row in rows)
  cursor+=len(rows)
  if first is None:first=payload['available_at_monotonic']
sessions=[dict(source_samples=n,asr_samples=costs['asr_accept']['successful_samples'],d1_samples=costs['diarizer_push']['successful_samples'],retained_d1_frames=cursor,model_output_frames=costs['diarizer_push']['output_frames'],native_event_count=event_count,native_footer='BYTE_LIMIT',text_publications=texts,E0_calls=costs['embedding']['started'],first_d1_seconds=first-origin,EOF_calls=0,model_costs=costs,finalization_state=f['state'],logical_handles_clean=False,journal_accepted=q['journal']['accepted'],journal_completed=q['journal']['completed'])]
folder=next((d/'data/conversations').glob('*/epochs/*'));m=json.loads((folder/'epoch.json').read_text())
assert m['state']=='PARTIAL' and m['archive_error']=='OutputLimit: FRAME_LIMIT' and m['recorded_samples']==960000 and m['source_samples']==n
assert m['loss']['first_unarchived_sample']==960000 and m['pcm_max_frames']==960000 and m['artifact_metrics']['audio']['status']=='FRAME_LIMIT'
floats=(folder/'model_input.f32le').read_bytes();assert len(floats)==960000*4 and sha(folder/'model_input.f32le')==m['audio_sha256']
with wave.open(str(folder/'model_input.wav'),'rb') as w:
 assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,960000)
 pcm=w.readframes(960000)
expected=bytearray();clipped=0
for value, in struct.iter_unpack('<f',floats):
 assert math.isfinite(value);clipped+=int(value < -1 or value > 32767/32768)
 expected+=struct.pack('<h',round(max(-1,min(32767/32768,value))*32768))
assert expected==pcm and clipped==0 and m['audio_bytes']==5760044
archive_events=sum(1 for z in partial_events(folder/'events.jsonl','SOURCE_FAILURE'))
archives=[dict(samples=960000,seconds=60,source_samples=n,unarchived_journal_samples=n-960000,pcm_sha256=sha(folder/'model_input.wav'),float_sha256=sha(folder/'model_input.f32le'),events=archive_events,event_bytes=(folder/'events.jsonl').stat().st_size,clipped_samples=clipped,state=m['state'],worker_alive_in_saved_snapshot=m['worker_alive'],accepted_items=m['accepted_items'],completed_items=m['completed_items'])]
trace_count=offset=native=0;previous_adc=None;epoch=None;maximum_ipc=0;verified_pcm_blocks=0
with (childdir/'TRACE.jsonl').open() as stream:
 for line in stream:
  row=json.loads(line);meta=row['metadata'];count=row['samples'];trace_count+=1
  assert meta['model_start_sample']==offset and meta['native_start_frame']==native and meta['native_frames']==count*3
  assert meta['callback_monotonic_ns']<=meta['delivery_monotonic_ns']<=row['ipc']['published_ns']<=row['ipc']['received_ns']
  if epoch is None:epoch=meta['epoch']
  assert meta['epoch']==epoch
  if previous_adc is not None:assert meta['adc_time_seconds']>=previous_adc
  previous_adc=meta['adc_time_seconds']
  if offset+count<=960000:
   assert row['audio_sha256']==hashlib.sha256(floats[offset*4:(offset+count)*4]).hexdigest();verified_pcm_blocks+=1
  maximum_ipc=max(maximum_ipc,row['ipc']['received_ns']-row['ipc']['published_ns'])
  offset+=count;native+=count*3
assert offset==n and trace_count==11517 and verified_pcm_blocks==6000 and terminal['sent_blocks']==11520
summary.update(continuous_data_ownership=True,installed_GUI_Save_Open=False,planned_GUI_Stop_reached=False,transport_samples=terminal['sent_samples'],journal_samples=n,timeline_samples=1842880,uncredited_transport_samples=480,source_callback_fault=None,transport_blocks=11520,traced_journal_blocks=trace_count,exact_saved_prefix_blocks=verified_pcm_blocks,maximum_observed_ipc_seconds=maximum_ipc/1e9,pending_raw_at_stop=close['original_stop_status']['pending_raw_blocks'],source_high_blocks=terminal['high_blocks'],source_high_bytes=terminal['high_bytes'],archive_full_coverage=False,D1_full_coverage=False,D1_EOF_qualified=False,logical_event_handle_close_failed=True)
for path in [session/'events.jsonl',folder/'epoch.json',folder/'model_input.f32le',folder/'model_input.wav',folder/'events.jsonl',childdir/'CHILD_RESULT.json',childdir/'TRACE.jsonl']:
 bindings[str(path.relative_to(d))]=sha(path)
summary['sampled_aggregate_peak_bytes']=max(z.get('aggregate_rss_bytes',0) for z in dispatch['samples'])
peaks={}
for sample in dispatch['samples']:
 for process in sample.get('process_samples',[]):
  key=str(process['owner']['pid']);r=peaks.setdefault(key,dict(rss_kib=0,vmpeak_kib=0,threads=0))
  for outkey,inkey in [('rss_kib','VmRSS'),('vmpeak_kib','VmPeak'),('threads','Threads')]:r[outkey]=max(r[outkey],process['values'].get(inkey,0))
summary['sampled_process_peaks']=peaks
series=[z for z in dispatch['samples'] if 'cpu_stat' in z and 'temperature_c' in z]
assert series
keys=['usage_usec','nr_periods','nr_throttled','throttled_usec']
summary['live_resources']=dict(samples=len(series),temperature_min=min(z['temperature_c'] for z in series),temperature_max=max(z['temperature_c'] for z in series),throttle_values=sorted(set(z['throttle'] for z in series)),cpu_stat_delta={k:series[-1]['cpu_stat'][k]-series[0]['cpu_stat'][k] for k in keys},clock_hz_min=min(v for z in series for v in z['clock_hz'].values()),clock_hz_max=max(v for z in series for v in z['clock_hz'].values()),available_ram_min_bytes=min(z['available_ram_bytes'] for z in dispatch['samples'] if 'available_ram_bytes' in z),maximum_sampled_output_bytes=max(z.get('output_bytes',0) for z in series))
built=json.loads((d/'CANDIDATE_BUILD.json').read_text());installed=Path(built['staged']['path'])
assert sha(installed/'RELEASE_MANIFEST.json')==built['manifest_sha256']
assert sha(installed/'native/field_entry_v5.py')==sha(d/'field_entry_sustained_v1.py')
assert sha(installed/'native/isolated_source_transport_v3.py')==sha(d/'isolated_source_transport_sustained_v1.py')
contract=json.loads((installed/'config/field_contract.json').read_text());assert contract['maximum_recording_seconds']==125 and contract['session_reservation_bytes']==64*1024**2 and not contract['field_release_accepted']
manifest=json.loads((installed/'RELEASE_MANIFEST.json').read_text())
for item in manifest['files']:assert sha(installed/item['path'])==item['sha256']
assert {q.relative_to(Path(a['installed_release'])).as_posix():sha(q) for q in Path(a['installed_release']).rglob('*') if q.is_file()}==a['installed_files']
assert sha(a['retained_lock'])==a['retained_lock_sha256'] and sha(a['source_state'])==a['source_state_sha256']
old_lock=json.loads(Path(a['retained_lock']).read_text());new_lock=json.loads((d/'DEPENDENCIES_DERIVED.json').read_text())
assert {k:z for k,z in old_lock.items() if k!='release_contract_sha256'}=={k:z for k,z in new_lock.items() if k!='release_contract_sha256'}
derivation=json.loads((d/'DEPENDENCY_DERIVATION.json').read_text())
assert derivation['source_sha256']==a['retained_lock_sha256'] and derivation['derived_sha256']==sha(d/'DEPENDENCIES_DERIVED.json')
assert new_lock['release_contract_sha256']==sha(installed/'config/field_contract.json')
old_contract=json.loads((Path(a['installed_release'])/'config/field_contract.json').read_text())
assert {k:[old_contract.get(k),contract.get(k)] for k in old_contract.keys()|contract.keys() if old_contract.get(k)!=contract.get(k)}=={'maximum_recording_seconds':[30,125],'session_reservation_bytes':[33554432,67108864],'sustained_target_seconds':[None,120],'archive_interchange_for_extended_recording':[None,'UNQUALIFIED']}
descriptor=json.loads((d/'SUSTAINED_DESCRIPTOR.json').read_text());assert descriptor['dependencies']==str(d/'DEPENDENCIES_DERIVED.json') and descriptor['dependencies_sha256']==sha(d/'DEPENDENCIES_DERIVED.json')

assert sha(d/'data/live_config.json')==a['live_config_sha256'] and sha(d/'data/n2_runtime.json')==a['n2_runtime_sha256']
assert (d/'data/private-preservation-canary').read_bytes()==b'PRIVATE_SYNTHETIC_CANARY\n'
assert not (d/'data/runtime.lock').exists()
with (d/'data/.runtime.guard').open('r+b') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
if passed:
 assert v['lease_closure']['released'] and v['lease_closure']['borrowed']==dict(opened=1,closed=1)
 for key in ['lease_at_stop','lease_after_drain']:
  assert v[key]['token']==v['lease_closure']['token'] and v[key]['pid']==v['owner']['pid'] and v[key]['state_sha256']==v['lease_closure']['state_sha256']
 assert sha(d/'candidate/state.json')==v['lease_closure']['state_sha256']
 assert all(row['lease']['token']==v['lease_closure']['token'] for row in v['observations'])
 summary['continuous_data_ownership']=True
 summary['installed_GUI_Save_Open']=v['controller_save_open']
summary['installed_release']=str(installed);summary['installed_manifest_sha256']=built['manifest_sha256']
summary['archive_interchange_qualified']=False
output=sum(p.stat().st_size for p in d.rglob('*') if p.is_file());assert output<a['target_output_max_bytes']
summary.update(sessions=sessions,archives=archives,target_bytes=output,capture_closed=True,leases_free=True,baseline_unchanged=True)
print(json.dumps(dict(summary=summary,bindings=bindings,owners=owners)))
''')
    out=PRIVATE/(run+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==x['summary']['process_exit']
    review=dict(status='PASS_INSTALLED_GUARDED_GUI_120S_QUIET_FUNCTIONAL_RESOURCE_ONLY' if x['summary']['success'] else 'REVIEWED_INSTALLED_SUSTAINED_QUIET_FAILURE_ONLY',**x,review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),accuracy_scored=False,numerical_reference_qualified=False,endurance_qualified=False,stage_accepted=False)
    with (out/'REVIEW.json').open('x') as f:json.dump(review,f,indent=2)
    remote('RUN='+repr(run)+'\nREVIEW='+repr(review)+'\n'+"import json\nfrom pathlib import Path\np=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN/'REVIEW.json'\nwith p.open('x') as f:json.dump(REVIEW,f,indent=2)\nprint(json.dumps({'written':True}))")
    print(json.dumps(dict(status=review['status'],sessions=[{k:v for k,v in s.items() if k!='model_costs'} for s in x['summary']['sessions']],archives=x['summary']['archives'],capture_closed=True)))


if __name__=='__main__':main()
