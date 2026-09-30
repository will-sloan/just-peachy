"""Independent saved-controller/GUI receipts and backup; README_REVIEW_SEQUENTIAL_GUI_V2.md."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import psutil
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
from dispatch_b01_stack_v2 import SSH


def main(run):
    psutil.Process().cpu_affinity([14])
    assert run in ('sequential-gui-v1','sequential-gui-v2')
    out=PRIVATE/(run+'-evidence')
    x=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(run)+'\n'+r'''
import fcntl,hashlib,json,os,resource,signal,subprocess,wave
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2);signal.alarm(110)
root=Path(ROOT)/RUN
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');d=read(root/'DISPATCH_RESULT.json');e=read(root/'LIVE_ENVELOPE.json')
assert not d['memory_guard'] and not d['log_overflow'] and a['capture']==False
assert e['address_space']==[1536*1024**2]*2 and e['stack']==[1048576]*2 and e['affinity']==[2,3]
pr=e['properties'];assert pr['LoadState']=='loaded' and pr['ActiveState']=='active' and int(pr['MainPID'])==e['owner']['pid']
assert int(pr['LimitAS'])==1536*1024**2 and int(pr['LimitSTACK'])==1048576 and pr['TasksMax']=='64'
assert pr['RuntimeMaxUSec']=='5min' and pr['TimeoutStopUSec']=='10s' and int(pr['LimitFSIZE'])==8*1024**2
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==a['boot_id']
owners=list(root.rglob('*OWNER.json'))
for p in owners:
 o=read(p);assert o['boot_id']==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
for p in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
peak=max(x.get('aggregate_rss_bytes',0) for x in d['samples']);assert 0<peak<=1152*1024**2
review=dict(actual_live_envelope_verified=True,exact_owners_closed=len(owners),baseline_unchanged=True,capture_closed=True,leases_free=True,
 sampled_aggregate_rss_bytes=peak,main_peak_rss_bytes=r['peak_rss_bytes'],elapsed_seconds=r['elapsed_seconds'],actual_capture=False,physical_gui=False,accuracy_scored=False,diarizer_loaded=False)
if RUN=='sequential-gui-v1':
 assert d['exit_code']==1 and r['status']=='FAILED_PRESERVED' and r['error']=='TclError: unknown option "-state"'
 assert len(owners)==2 and not list(root.rglob('CHILD_OWNER.json'))
 review.update(status='REVIEWED_NATIVE_GUI_WIDGET_BINDING_FAILURE_ONLY',error=r['error'],model_children_created=0,natural_exit_code=1,controller_gui_qualified=False)
else:
 assert d['exit_code']==0 and r['status']=='SEQUENTIAL_CONTROLLER_GUI_COLLECTED_REVIEW_REQUIRED'
 assert r['controller_closed'] and r['Tk_destroyed'] and r['root_withdrawn'] and not r['callback_errors']
 assert not r['capture'] and not r['diarizer_loaded'] and not r['accuracy_scored'] and r['actual_controller_and_widgets']
 assert r['base_model_loads']==0 and r['models_in_separate_processes'] and r['primary_immutable'] and r['reopened_exact'] and r['rejected_controls']==5
 assert len(owners)==5 and sha(a['source_wav'])==r['source_sha256']
 with wave.open(a['source_wav'],'rb') as w:assert (w.getnframes(),w.getframerate(),w.getnchannels(),w.getsampwidth())==(715127,16000,1,2)
 history=r['history'];assert [t['phase'] for t in history]==['sherpa','a2','a2']
 assert [t['state'] for t in history]==['PRIMARY_READY','REFINEMENT_CANCELLED','COMPLETE']
 assert [t['child_exit'] for t in history]==[0,2,0]
 assert all(t['reaped_ns']<u['launch_ns'] for t,u in zip(history,history[1:]))
 timeline=[json.loads(s) for s in (root/'data/sequential_reviews/CONTROLLER_EVENTS.jsonl').read_text().splitlines()]
 assert [s['value'] for s in timeline if s['kind']=='terminal']==history
 assert all(t['monotonic_ns']<=u['monotonic_ns'] for t,u in zip(timeline,timeline[1:]))
 refs={'sherpa':[{k:v for k,v in e.items() if k!='available_seconds'} for e in read(a['sherpa_reference'])['events']],'a2':read(a['a2_reference'])}
 metrics=[];texts=[];total=0
 for index,t in enumerate(history):
  job=Path(t['job']);assert job.is_relative_to(root/'data/sequential_reviews') and read(job/'ADMISSION.json')==a
  assert read(job/'TERMINAL.json')==t and t['owner_closed'] and not t['forced'] and t['primary_retained']
  phase=t['phase'];q=job/phase;v=read(q/'RESULT.json');owner=read(q/'CHILD_OWNER.json')
  assert owner==v['owner'] and ticks(owner['pid'])!=owner['start_ticks'] and v['model_closed']
  assert v['source_samples']==715127 and v['source_sha256']==r['source_sha256']
  assert v['address_space']==[(768 if phase=='sherpa' else 1536)*1024**2]*2 and v['stack']==[1048576]*2 and v['affinity']==[2,3]
  assert t['launch_ns']<v['ended_monotonic_ns']<t['reaped_ns']
  rows=[json.loads(s) for s in (q/'EVENTS.jsonl').read_text().splitlines()];events=[s['event'] for s in rows]
  assert len(events)==t['publications']==v['event_count'] and len(events)>0
  assert events==refs[phase][:len(events)]
  if index==1:
   assert v['status']=='PHASE_CANCELLED' and not v['canonical_reference_exact'] and 0<v['accepted_samples']<715127
   assert read(q/'CANCEL.json')=={'cancel':True}
  else:
   assert v['status']=='PHASE_COLLECTED' and v['canonical_reference_exact'] and v['accepted_samples']==715127 and events==refs[phase]
   if phase=='sherpa':assert v['final_text']==read(a['sherpa_reference'])['final_text']
  pubs=[s for s in timeline if s['kind']=='publication' and t['launch_ns']<=s['monotonic_ns']<=t['reaped_ns']]
  assert [s['value']['publication'] for s in pubs]==rows
  assert all(s['value']['backend']==phase and s['value']['source_sha256']==r['source_sha256'] for s in pubs)
  delays=[s['monotonic_ns']-s['value']['publication']['available_monotonic_ns'] for s in pubs];assert min(delays)>=0
  by_utterance={}
  for event in events:by_utterance[str(event['utterance'])]=event.get('raw_text',event.get('text',''))
  texts.append('\n'.join(s for s in by_utterance.values() if s));total+=len(events)
  metrics.append(dict(phase=phase,status=v['status'],events=len(events),accepted_samples=v['accepted_samples'],load_seconds=v['load_seconds'],elapsed_seconds=v['elapsed_seconds'],source_elapsed_seconds=v.get('source_elapsed_seconds'),cpu_seconds=v['cpu_seconds'],maximum_controller_ingestion_seconds=max(delays)/1e9,child_reported_ru_maxrss_bytes=v['peak_rss_bytes']))
 assert total==sum(s['kind']=='publication' for s in timeline)
 saved=[read(r[k]) for k in ['saved_primary','saved_cancelled','saved_complete']]
 assert [s['phase'] for s in saved]==['PRIMARY_READY','REFINEMENT_CANCELLED','COMPLETE'] and all(not s['owned'] for s in saved)
 assert saved[0]['primary']==saved[1]['primary']==saved[2]['primary']
 assert saved[0]['refined']==saved[1]['refined']==None and not saved[1]['refined_text']
 for value in saved:
  assert value['source_sha256']==r['source_sha256'] and value['primary_text']==texts[0]
  for key in ['primary','refined']:
   artifact=value[key]
   if artifact:
    for field in ['events','result']:assert sha(artifact[field])==artifact[field+'_sha256']
 assert saved[2]['refined_text']==texts[2]
 expected=dict(saved[2]);expected['saved']=r['saved_complete'];assert r['completed_snapshot']==expected
 gui=read(root/'GUI_SNAPSHOT.json');assert gui==dict(primary_text='Primary (Sherpa):\n'+texts[0],refined_text='Refinement (Nemotron):\n'+texts[2],phase='COMPLETE')
 cancel=r['cancelling_owned_snapshot'];assert cancel['owned'] and cancel['phase']=='CANCELLING' and cancel['job']==history[1]['job']
 assert history[1]['launch_ns']<cancel['monotonic_ns']<history[1]['reaped_ns']
 review.update(status='PASS_NATIVE_SAVED_SEQUENTIAL_CONTROLLER_CANCEL_RETRY_ARCHIVE_WITHDRAWN_GUI_ONLY',phases=metrics,natural_exit_code=0,
  full_source_samples=715127,canonical_events_exact=True,cancelled_events_exact_prefix=True,primary_retained_immutable=True,model_lifetimes_disjoint=True,
  cancel_to_closed_seconds=r['cancel_return_seconds'],cancel_owned_until_reaped=True,saved_reopened_and_gui_text_exact=True,rejected_controls=5,controller_Tk_closed=True,
  controller_gui_qualified=True,live_mode_qualified=False,arbitrary_source_picker_qualified=False,endurance_qualified=False)
files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.rglob('*') if p.is_file()}
size=sum(v['bytes'] for v in files.values());assert size<a['target_output_max_bytes'] and all(v['bytes']<=8*1024**2 for v in files.values())
review.update(target_output_bytes=size,combined_output_allowance_bytes=a['output_max_bytes'])
print(json.dumps(dict(review=review,files=files)))
''')
    expected_code=1 if run.endswith('v1') else 0
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==expected_code
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/'+run+' -cf - .'],timeout=90)
    backup=out/'target';backup.mkdir();seen=set()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tar:
        for member in tar:
            name=member.name[2:] if member.name.startswith('./') else member.name
            path=PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in name
            if member.isdir():continue
            assert member.isfile() and name in x['files'] and name not in seen
            raw=tar.extractfile(member).read();expected=x['files'][name]
            assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256']
            dest=backup.joinpath(*path.parts);dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:f.write(raw)
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==expected['sha256'];seen.add(name)
    assert seen==set(x['files'])
    combined=x['review']['target_output_bytes']+sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert combined+128*1024<x['review']['combined_output_allowance_bytes']
    x['review'].update(backup_verified=True,backup_files=len(seen),combined_stage_backup_bytes=combined)
    for name,value in [('BACKUP.json',x['files']),('REVIEW.json',x['review'])]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
    print(json.dumps(x['review']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);main(p.parse_args().run)
