"""Read preserved first live failure. See README_B01_LIVE_GAP_V1.md."""
import json
import psutil
from dispatch_geometry_v2 import remote, PRIVATE, REMOTE


def main():
    psutil.Process().cpu_affinity([14])
    run = 'b01-live-trial-alsa-user-20260929T180625Z'
    out = PRIVATE/(run+'-evidence')
    log = (out/'launch.log').read_text()
    assert 'INPUT_STATUS_GAP' in log and 'DROPPED_NATIVE_FRAMES' in log and 'code=exited/status=1' in log
    assert 'insufficient memory' not in log and 'std::bad_alloc' not in log
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code'] == 1
    x = remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(run)+'\n'+r'''
import json,hashlib,subprocess,fcntl,re,collections
from pathlib import Path
r=Path(ROOT);d=r/RUN
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot==a['boot_id'] and a['private_diagnostics_consented'] and a['physically_ready_attested']
for row in a['files']:assert sha(Path(row['path']))==row['sha256']
owners=[]
for name in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/name).read_text());t=ticks(o['pid'])
 assert o['boot_id']==boot and t!=o['start_ticks'] and o['admission_sha256']==sha(d/'ADMISSION.json')
 owners.append(dict(owner=o,observed_start_ticks=t,exact_alive=False))
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
assert sha(Path.home()/'JustPeachy/data/live_config.json')=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for lock in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with lock.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
unit=dict(l.split('=',1) for l in subprocess.check_output(['systemctl','--user','show','jp-'+RUN,'-p','MainPID','-p','Result','-p','ExecMainStatus'],text=True).splitlines())
assert unit==dict(MainPID='0',Result='exit-code',ExecMainStatus='1'),unit
result=json.loads((d/'RESULT.json').read_text());assert result['status']=='FAILED_PRESERVED' and result['controller_closed'] and result['Tk_destroyed'] and 'INPUT_STATUS_GAP' in result['error']
paths=list((d/'data/device_receipts').glob('*.json'));assert len(paths)==1
receipt=json.loads(paths[0].read_text());status=receipt['status']
assert status['finished'] and status['fault']=='INPUT_STATUS_GAP' and status['dropped_frames']==480 and status['converted_samples']==420000
assert receipt['errors']==[] and receipt['route_restoration'] and set(receipt['route_restoration'].values())=={'RESTORED'}
before=receipt['metadata']['route']['before'];commands=receipt['commands']
def values(stdout):
 result=[]
 for v in stdout.split()[1:]:
  m=re.fullmatch(r'.*\[(-?\d+)\]',v)
  result.append(float(m.group(1) if m else v))
 return result
for key in receipt['metadata']['route']['changed']:
 matching=[c for c in commands if c['command']==key]
 assert matching[-1]['arguments']==[] and matching[-1]['exit_code']==0
 assert values(matching[-1]['stdout'])==before[key],key
assert not any(c['command']=='TEST_CORE_BURN' for c in commands)
session=next((d/'data/sessions').iterdir());events=[json.loads(l) for l in (session/'events.jsonl').read_text().splitlines()]
types=collections.Counter(e['event_type'] for e in events)
failures=[e for e in events if e['event_type']=='failure']
assert len(failures)==1 and 'INPUT_STATUS_GAP' in failures[0]['payload']['reason']
assert types['s6d_text_ready']>0 and types['n2_diarization_frames']>0 and types['source_stopped']==1
final=json.loads((session/'session_finalization_v3.json').read_text());assert final['state']=='FAILED' and final['source_samples']==final['identity_samples']==420000
assert final['event_and_transcript_handles_closed'] and not final['live_lanes_at_finalization'] and not final['resident_bundle_lease_retained']
consumer=json.loads((session/'s6d_consumer_closure.json').read_text());assert consumer['full_event_consumer_drained'] and consumer['queues']['event_consumer']['depth']==0
for name in ['journal','punctuation','policy']:
 q=consumer['queues'][name];assert q['closed'] and not q['thread_alive'] and not q['error'] and q['depth']==0 and q['accepted']==q['completed']
summary=json.loads((session/'session_summary.json').read_text());costs=summary['telemetry']['component_costs']['rows']
assert costs['asr_accept']['successful_samples']==420000 and costs['diarizer_push']['successful_samples']==339360
assert costs['embedding']['completed']==29
for row in costs.values():assert not row['errors'] and not row['in_flight'] and row['started']==row['completed']
import math
cursor=0
for event in events:
 if event['event_type']=='n2_diarization_frames':
  v=event['payload'];assert v['frame_start']==cursor
  rows=v['probabilities'];assert rows and all(len(row)==8 and all(math.isfinite(v) and 0<=v<=1 for v in row) for row in rows);cursor+=len(rows)
assert cursor==2112 and cursor==costs['diarizer_push']['output_frames']
assert not costs['diarizer_finish']['started']
memory=[json.loads(l) for l in (d/'MEMORY.jsonl').read_text().splitlines()]
maxima={}
for row in memory:
 for item in row['values']:
  key,value=item.split(':',1);value=int(value.split()[0]);maxima[key]=max(maxima.get(key,0),value)
assert maxima['VmPeak']<768*1024 and maxima['VmSize']<=768*1024
bindings={str(p.relative_to(d)):sha(p) for p in d.rglob('*') if p.is_file() and p.suffix in ['.json','.jsonl','.py','.md']}
print(json.dumps(dict(status='REVIEWED_LIVE_INPUT_GAP_WITH_HANDLED_FAILURE_CLOSURE_ONLY',owners=owners,unit=unit,bindings=bindings,converted_samples=status['converted_samples'],source_seconds=status['converted_samples']/16000,caption_publications=types['s6d_text_ready'],probability_frames=cursor,diarizer_successful_samples=339360,embedding_calls=29,model_inference_errors=0,handled_failure_workers_queues_handles_closed=True,sampled_memory_kib=maxima,route_restore_readbacks_verified=True,capture_closed=True,leases_free=True,clean_application_finalization=False,full_trial_passed=False,accuracy_scored=False,original_app_config_install_unchanged=True)))
''')
    import hashlib
    x['host_launch_log_sha256'] = hashlib.sha256((out/'launch.log').read_bytes()).hexdigest()
    with (out/'GAP_REVIEW_V1.json').open('x', encoding='utf-8') as f:
        json.dump(x, f, indent=2)
    print(json.dumps({k:v for k,v in x.items() if k not in ['bindings','owners']}))


if __name__ == '__main__':
    main()
