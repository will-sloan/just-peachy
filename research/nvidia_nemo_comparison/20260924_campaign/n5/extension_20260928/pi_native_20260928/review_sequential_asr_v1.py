"""Independent sequential model lifetime/event reader; README_REVIEW_SEQUENTIAL_ASR_V1.md."""
import json
from pathlib import Path
import psutil
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE


def main():
    psutil.Process().cpu_affinity([14]);run='sequential-asr-v1'
    review=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(run)+'\n'+r'''
import fcntl,hashlib,json,os,resource,signal,subprocess,wave
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2);signal.alarm(60)
root=Path(ROOT)/RUN
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');d=read(root/'DISPATCH_RESULT.json');e=read(root/'LIVE_ENVELOPE.json')
assert r['status']=='SEQUENTIAL_ASR_COLLECTED_REVIEW_REQUIRED' and d['exit_code']==0 and not d['memory_guard'] and not d['log_overflow']
assert r['capture']==a['capture']==False and not r['models_overlap'] and not r['gui_integrated'] and not r['diarizer_loaded'] and not r['accuracy_scored']
assert e['address_space']==[1536*1024**2]*2 and e['stack']==[1048576]*2 and e['affinity']==[2,3]
pr=e['properties'];assert pr['LoadState']=='loaded' and pr['ActiveState']=='active' and int(pr['MainPID'])==e['owner']['pid'] and int(pr['LimitAS'])==1536*1024**2
assert pr['TasksMax']=='64' and pr['RuntimeMaxUSec']=='5min' and pr['TimeoutStopUSec']=='10s' and int(pr['LimitFSIZE'])==8*1024**2
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
assert sha(a['source_wav'])==r['source_sha256']
with wave.open(a['source_wav'],'rb') as w:assert (w.getnframes(),w.getframerate(),w.getnchannels(),w.getsampwidth())==(715127,16000,1,2)
assert [x['phase'] for x in r['phases']]==['sherpa','a2']
assert [x['phase'] for x in r['states']]==['TRANSCRIBING','PRIMARY_READY','REFINING','COMPLETE']
assert r['states'][1]['primary']==r['states'][2]['primary']==r['states'][3]['primary'] and r['states'][1]['refined'] is None
assert r['states'][3]['refined'] and r['states'][3]['refined']!=r['states'][3]['primary']
assert r['state_checks']=={'rejected':5,'failed_refinement_preserves_primary':True,'no_silent_retry':True}
timeline=[json.loads(x) for x in (root/'COORDINATOR_EVENTS.jsonl').read_text().splitlines()]
assert [x['value'] for x in timeline if x['kind']=='state']==r['states']
assert all(x['monotonic_ns']<=y['monotonic_ns'] for x,y in zip(timeline,timeline[1:]))
metrics=[];seen=0
for phase in r['phases']:
 name=phase['phase'];q=root/name;v=read(q/'RESULT.json');owner=read(q/'CHILD_OWNER.json')
 assert phase['owner']==owner==v['owner'] and phase['exact_owner_closed'] and phase['exit_code']==0 and not phase['forced']
 assert ticks(owner['pid'])!=owner['start_ticks'] and v['status']=='PHASE_COLLECTED' and v['model_closed'] and v['canonical_reference_exact']
 assert v['accepted_samples']==v['source_samples']==715127 and v['source_sha256']==r['source_sha256']
 assert v['address_space']==[(768 if name=='sherpa' else 1536)*1024**2]*2 and v['stack']==[1048576]*2 and v['affinity']==[2,3]
 assert phase['launch_ns']<v['ended_monotonic_ns']<phase['reaped_ns']
 assert sha(q/'RESULT.json')==phase['result']['sha256'] and phase['result']['backend']==name
 rows=[json.loads(x) for x in (q/'EVENTS.jsonl').read_text().splitlines()];canonical=[x['event'] for x in rows]
 assert len(rows)==phase['publications']==v['event_count'] and any((x.get('text') or x.get('raw_text','')).strip() for x in canonical)
 if name=='sherpa':
  ref=read(a['sherpa_reference']);assert canonical==[{k:v for k,v in ev.items() if k!='available_seconds'} for ev in ref['events']] and v['final_text']==ref['final_text']
  assert v['endpoint_count']==ref['endpoint_count'] and v['source_elapsed_seconds']>=715127/16000
 else:assert canonical==read(a['a2_reference'])
 publications=[x for x in timeline if x['kind']=='publication' and x['value']['backend']==name]
 assert [x['value']['event'] for x in publications]==rows
 delays=[x['monotonic_ns']-x['value']['event']['available_monotonic_ns'] for x in publications]
 assert all(x>=0 for x in delays) and all(phase['launch_ns']<=x['monotonic_ns']<=phase['reaped_ns'] for x in publications)
 seen+=len(rows)
 metrics.append(dict(backend=name,source_samples=715127,events=len(rows),canonical_reference_exact=True,load_seconds=v['load_seconds'],source_elapsed_seconds=v['source_elapsed_seconds'],drain_seconds=v['drain_seconds'],cpu_seconds=v['cpu_seconds'],peak_rss_bytes=v['peak_rss_bytes'],maximum_coordinator_delivery_seconds=max(delays)/1e9,phase_process_seconds=(phase['reaped_ns']-phase['launch_ns'])/1e9))
assert seen==sum(x['kind']=='publication' for x in timeline)
assert r['phases'][0]['reaped_ns']<r['phases'][1]['launch_ns']
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
owners=list(root.rglob('*OWNER.json'));assert len(owners)==4
for p in owners:
 o=read(p);assert o['boot_id']==boot and ticks(o['pid'])!=o['start_ticks']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
for p in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file());assert size<a['target_output_max_bytes']
assert all(p.stat().st_size<=8*1024**2 for p in root.rglob('*') if p.is_file())
peak=max(x.get('aggregate_rss_bytes',0) for x in d['samples']);assert 0<peak<=1152*1024**2
print(json.dumps(dict(status='PASS_NATIVE_SEQUENTIAL_SHERPA_A2_SAVED_SOURCE_ONLY',phases=metrics,states=[x['phase'] for x in r['states']],same_source_samples=715127,separate_primary_refinement_artifacts=True,exact_canonical_references=True,model_process_lifetimes_disjoint=True,elapsed_seconds=r['elapsed_seconds'],main_peak_rss_bytes=r['peak_rss_bytes'],sampled_aggregate_rss_bytes=peak,output_bytes=size,all_four_owners_closed=True,baseline_unchanged=True,leases_free=True,capture=False,gui_integrated=False,diarizer_integrated=False,accuracy_scored=False,hashes={n:sha(root/n) for n in ['ADMISSION.json','RESULT.json','DISPATCH_RESULT.json','LIVE_ENVELOPE.json']})))
''')
    out=PRIVATE/(run+'-evidence');assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    with (out/'REVIEW.json').open('x') as f:json.dump(review,f,indent=2)
    remote('ROOT='+repr(REMOTE+'/'+run)+'\nV='+repr(review)+'\nimport json\nfrom pathlib import Path\nwith (Path(ROOT)/"REVIEW.json").open("x") as f:json.dump(V,f,indent=2)\nprint(json.dumps({"written":True}))')
    print(json.dumps({k:v for k,v in review.items() if k!='hashes'}))


if __name__=='__main__':main()
