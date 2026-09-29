"""Review the closed first-use E0 failure. See README_B01_LAZY_REVIEW_V1.md."""
import hashlib,json,psutil
from dispatch_geometry_v2 import remote,PRIVATE

def main():
    psutil.Process().cpu_affinity([14])
    out=PRIVATE/'b01-lazy-e0-v1-evidence'
    launch=json.loads((out/'LAUNCH_RESULT.json').read_text());assert launch['exit_code']==1
    x=remote(r"""
import os,json,hashlib,subprocess
from pathlib import Path
from collections import Counter
os.sched_setaffinity(0,{3})
d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-lazy-e0-v1')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
assert a['address_space_max_bytes']==768*1024**2 and a['mode']=='open_with_names'
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for name in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/name).read_text());p=Path('/proc',str(o['pid']),'stat')
 ticks=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
 assert not(boot==o['boot_id'] and ticks==o['start_ticks'])
 assert o['admission_sha256']==sha(d/'ADMISSION.json')
unit=subprocess.check_output(['systemctl','--user','show','jp-b01-lazy-e0-v1','-p','ActiveState','-p','MainPID','-p','Result','-p','ExecMainCode','-p','ExecMainStatus'],text=True)
u=dict(v.split('=',1) for v in unit.splitlines())
assert u['MainPID']=='0' and u['Result']=='exit-code' and u['ExecMainStatus']=='1'
r=json.loads((d/'RESULT.json').read_text());assert r['status']=='FAILED_PRESERVED' and r['controller_closed']
assert not r['e0_lazy_loads'] and r['e0_loads_at_start_return']==0
sessions=list((d/'data/sessions').iterdir());assert len(sessions)==1;s=sessions[0]
e=[json.loads(v) for v in (s/'events.jsonl').read_text().splitlines()]
f=json.loads((s/'session_finalization_v3.json').read_text());c=json.loads((s/'s6d_consumer_closure.json').read_text())
assert f['state']=='FAILED' and not f['live_lanes_at_finalization'] and f['event_and_transcript_handles_closed'] and f['finalization_error'] is None
assert f['source_samples']==f['identity_samples']==192000
assert c['full_event_consumer_drained']
for key in ['journal','punctuation','policy']:
 q=c['queues'][key];assert q['depth']==0 and q['closed'] and not q['thread_alive'] and not q['error'] and q['accepted']==q['completed']
fail=[v['payload']['reason'] for v in e if v['event_type']=='failure'];assert len(fail)==1 and 'Load model' in fail[0] and 'redimnet2' in fail[0] and 'std::bad_alloc' in fail[0]
counts=dict(Counter(v['event_type'] for v in e));assert counts.get('research_embedding',0)==0 and counts.get('session_completed',0)==0
prob=[v['payload'] for v in e if v['event_type']=='n2_diarization_frames'];assert len(prob)==1 and prob[0]['frame_start']==0 and len(prob[0]['probabilities'])==1201
bindings={str(p.relative_to(d)):sha(p) for p in [d/'RESULT.json',d/'ADMISSION.json',d/'OWNER.json',d/'DISPATCH_OWNER.json',d/'DISPATCH_RESULT.json',d/'MEMORY.jsonl',s/'events.jsonl',s/'session_finalization_v3.json',s/'s6d_consumer_closure.json',*d.glob('*.smaps')]}
print(json.dumps(dict(result=r,unit=u,bindings=bindings,failure=fail[0],counts=counts,finalization=f,closure=c,probability_frames=len(prob[0]['probabilities']))))
""")
    r=x['result']; memory={k:max(int(v.split()[1])*1024 for row in r['memory_samples'] for v in row['values'] if v.startswith(k+':')) for k in ['VmSize','VmPeak','VmRSS']}
    review=dict(status='FAILED_LAZY_E0_LOAD_WITH_HANDLED_DRAIN',owner_closed=True,natural_exit_code=1,unit=x['unit'],bindings=x['bindings'],failure=x['failure'],controller_and_application_failure_drain=True,complete_integrated_passage=False,integrated_acceptance=False,successful_E0_calls=0,observed_D1_frames=1201,source_samples_at_failed_finalization=192000,sampled_memory_bytes=memory,ru_maxrss_bytes=r['peak_rss_bytes'],e0_loaded_at_start=False,earlier_combined_exit_handler_failure_cleared=False)
    for name,data in [('REVIEW_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(data,f,indent=2)
    remote("from pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-lazy-e0-v1/REVIEW.json')\nwith p.open('x') as f:f.write("+repr(json.dumps(review,indent=2))+")\nprint('{}')")
    print(json.dumps({k:v for k,v in review.items() if k not in ['bindings','failure']}))
if __name__=='__main__':main()
