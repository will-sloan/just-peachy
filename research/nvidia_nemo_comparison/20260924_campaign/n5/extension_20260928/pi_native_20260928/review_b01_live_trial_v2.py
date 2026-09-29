"""Independent bound/user trial reader. See README_B01_LIVE_TRIAL_V2.md."""
import argparse
import hashlib
import json
import re
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    assert re.fullmatch(r'b01-live-trial-alsa-boundary-v2|b01-live-trial-alsa-user-\d{8}T\d{6}Z',args.run_id)
    out=PRIVATE/(args.run_id+'-evidence')
    x=remote('RUN='+repr(args.run_id)+'\n'+r'''
import os,json,hashlib,subprocess,fcntl,math
from pathlib import Path
os.sched_setaffinity(0,{3});root=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928');d=root/RUN
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
for row in a['files']:assert sha(Path(row['path']))==row['sha256']
owners=[]
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/n).read_text());t=ticks(o['pid']);assert not(o['boot_id']==boot and t==o['start_ticks']);assert o['admission_sha256']==sha(d/'ADMISSION.json')
 owners.append(dict(owner=o,observed_start_ticks=t,exact_alive=False))
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
assert sha(Path.home()/'JustPeachy/data/live_config.json')=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for lock in [root/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with lock.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
u=dict(l.split('=',1) for l in subprocess.check_output(['systemctl','--user','show','jp-'+RUN,'-p','MainPID','-p','Result','-p','ExecMainStatus'],text=True).splitlines())
assert u==dict(MainPID='0',Result='success',ExecMainStatus='0')
r=json.loads((d/'RESULT.json').read_text());dispatch=json.loads((d/'DISPATCH_RESULT.json').read_text());assert dispatch['exit_code']==0
bindings={n:sha(d/n) for n in ['ADMISSION.json','RESULT.json','DISPATCH_RESULT.json','OWNER.json','DISPATCH_OWNER.json']}
env=json.loads((d/'ALSA_ENVIRONMENT.json').read_text());assert env['path']==str(d/'alsa_hw_only_v1.conf') and env['sha256']==sha(d/'alsa_hw_only_v1.conf')=='d81bc353dcab14d172e78b26c6116bfc8462b96e45e44b1a93ac3f217898564d' and env['process_local']
bindings['ALSA_ENVIRONMENT.json']=sha(d/'ALSA_ENVIRONMENT.json')
summary={}
if a['mode']=='boundary':
 assert not a['capture'] and not a['models_loaded'] and not a['audio_saved']
 assert r['status']=='PASS_MODEL_FREE_ACCEPTED_SAMPLE_BOUND_ONLY' and r['cases']==3
 assert not r['microphone_opened'] and not r['models_loaded']
 assert not list(d.rglob('*.wav')) and not list(d.rglob('*.npy'))
else:
 assert a['mode']=='user' and a['physically_ready_attested'] and a['private_diagnostics_consented']
 assert r['status']=='B01_USER_LIVE_COLLECTED_REQUIRES_INDEPENDENT_REVIEW'
 assert r['controller_closed'] and r['Tk_destroyed'] and r['root_withdrawn'] and not r['callback_errors']
 assert r['redim_encoder_loaded'] and r['no_scipy_loaded'] and r['model_load_counts']['asr_loads']==r['model_load_counts']['speaker_loads']==1
 assert r['source_integrity']['ok'] and r['source_integrity']['restoration_ok'] and not r['source_integrity']['restoration_issues']
 stop=r['source_stop_receipt'];assert not stop['errors'] and not stop['status']['fault'] and stop['status']['dropped_frames']==0
 assert stop['route_restoration'] and all(v=='RESTORED' for v in stop['route_restoration'].values())
 timeline=r['source_timeline'];assert timeline['model_samples_accepted']==480000 and timeline['native_frames_accepted']==1440000 and timeline['max_native_lead_ns']<=0
 assert r['source_metadata']['actual_stream_rate']==48000 and r['source_metadata']['resampler_delay_seconds']==.001
 assert len(r['sessions'])==1
 s=Path(r['sessions'][0]['session_dir']);assert s.parent==d/'data/sessions'
 final=json.loads((d/'FINAL_SNAPSHOT.json').read_text());assert not final['error']
 docs={n:json.loads((s/n).read_text()) for n in ['session_summary.json','session_finalization_v3.json','s6d_consumer_closure.json']}
 f=docs['session_finalization_v3.json'];assert f['state']=='COMPLETED' and not f['finalization_error'] and not f['live_lanes_at_finalization']
 assert f['event_and_transcript_handles_closed'] and not f['resident_bundle_lease_retained'] and f['source_samples']==f['identity_samples']==480000
 c=docs['s6d_consumer_closure.json'];assert c['full_event_consumer_drained'] and c['queues']['event_consumer']['depth']==0
 for name in ['journal','punctuation','policy']:
  q=c['queues'][name];assert q['closed'] and not q['thread_alive'] and not q['error'] and q['depth']==0 and q['accepted']==q['completed']
 t=docs['session_summary.json']['telemetry'];costs=t['component_costs']['rows']
 assert t['audio_frames_dropped']==0 and t['identity_audio_samples']==t['paired_audio_samples']==480000
 for name in ['asr_accept','diarizer_push']:assert costs[name]['successful_samples']==480000
 for row in costs.values():assert row['errors']==row['in_flight']==0 and row['started']==row['completed']
 assert t['punctuation_inference_failures']==0
 archive=final['sessions']['last_archive'];assert archive['closed'] and not archive['worker_alive'] and not archive['archive_error'] and not archive['loss']
 assert archive['source_samples']==480000 and archive['queue_items']==archive['queue_bytes']==0
 cursor=0;text_count=0
 for line in (s/'events.jsonl').read_text().splitlines():
  event=json.loads(line)
  if event['event_type']=='s6d_text_ready':text_count+=1
  if event['event_type']=='n2_diarization_frames':
   v=event['payload'];assert v['session_id']==s.name and v['frame_start']==cursor
   rows=v['probabilities'];assert rows and all(len(row)==8 and all(math.isfinite(v) and 0<=v<=1 for v in row) for row in rows);cursor+=len(rows)
 assert cursor>0 and cursor==costs['diarizer_push']['output_frames']+costs['diarizer_finish']['output_frames']
 for name in docs:bindings[str((s/name).relative_to(d))]=sha(s/name)
 bindings[str((s/'events.jsonl').relative_to(d))]=sha(s/'events.jsonl');bindings['FINAL_SNAPSHOT.json']=sha(d/'FINAL_SNAPSHOT.json')
 summary=dict(source_samples=480000,native_frames=1440000,probability_frames=cursor,text_publications=text_count,model_call_costs=costs,peak_rss_bytes=r['peak_rss_bytes'],elapsed_seconds=r['elapsed_seconds'],all_queues_and_archives_drained=True,route_restoration_checked=True)
print(json.dumps(dict(mode=a['mode'],result=r,bindings=bindings,owners=owners,unit=u,summary=summary)))
''')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    status='PASS_NATIVE_HW_ONLY_LIVE_TRIAL_BOUNDARY_ONLY' if x['mode']=='boundary' else 'PASS_USER_LIVE_B01_HW_ONLY_SHORT_FUNCTIONAL_RESOURCE_ONLY'
    review=dict(status=status,bindings=x['bindings'],owners=x['owners'],unit=x['unit'],summary=x['summary'],capture_closed=True,leases_free=True,original_app_config_install_unchanged=True,accuracy_scored=False,sustained_fit_qualified=False,stage_accepted=False)
    for name,data in [('AUDIT_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(data,f,indent=2)
    remote('RUN='+repr(args.run_id)+'\nREVIEW='+repr(review)+'\n'+"import json\nfrom pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/RUN/'REVIEW.json'\nwith p.open('x') as f:json.dump(REVIEW,f,indent=2)\nprint(json.dumps({'written':True}))")
    print(json.dumps({k:v for k,v in review.items() if k not in ['bindings','owners']}))


if __name__=='__main__':main()
