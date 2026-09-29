"""Independent filtered native model reader. See README_B01_FIR_REFERENCES_V1.md."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import base64,hashlib,io,json,psutil
from dispatch_geometry_v2 import remote,PRIVATE

def main():
 psutil.Process().cpu_affinity([14])
 import numpy as np
 run='b01-fir-references-v1';out=PRIVATE/(run+'-evidence');assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
 x=remote(r"""
import json,os,hashlib,subprocess,base64
from pathlib import Path
os.sched_setaffinity(0,{3});d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-fir-references-v1')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text());r=json.loads((d/'RESULT.json').read_text());plan=json.loads((d/'PLAN.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();owners=[]
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/n).read_text());pp=Path('/proc',str(o['pid']),'stat');t=int(pp.read_text().rsplit(')',1)[1].split()[19]) if pp.exists() else None
 assert not(boot==o['boot_id'] and t==o['start_ticks']);assert o['admission_sha256']==sha(d/'ADMISSION.json');owners.append(dict(owner=o,observed=t,exact_alive=False))
u=dict(v.split('=',1) for v in subprocess.check_output(['systemctl','--user','show','jp-'+d.name,'-p','MainPID','-p','Result','-p','ExecMainStatus'],text=True).splitlines());assert u['MainPID']=='0' and u['Result']=='success' and u['ExecMainStatus']=='0'
assert json.loads((d/'DISPATCH_RESULT.json').read_text())['exit_code']==0
assert a['reference_tolerance']==plan['tolerance']==r['tolerance']==1e-5
assert r['plan_sha256']==sha(d/'PLAN.json') and r['filtered_sha256']==sha(d/'filtered.npy')
old=d.parent/'b01-fir-integration-v1';assert plan['application_review_sha256']==sha(old/'REVIEW.json')
review=json.loads((old/'REVIEW.json').read_text());assert review['status']=='PASS_CONSTRUCTED_FIR_INTEGRATION_LIFECYCLE_MODEL_REFERENCES_PENDING'
assert plan['filtered_float32_sha256']==review['conversion']['output_float32_sha256']
queries=[]
for index,s in enumerate(plan['sessions']):
 ep=Path(s['events_path']);assert sha(ep)==s['events_sha256'];events=[json.loads(v) for v in ep.read_text().splitlines()]
 prob=[e['payload'] for e in events if e['event_type']=='n2_diarization_frames'];cursor=0;expected=[]
 for e in prob:
  assert e['frame_start']==cursor;expected.extend(e['probabilities']);cursor+=len(e['probabilities'])
 assert expected==s['probabilities'] and s['samples']==review['sessions'][index]['samples']
 for event in events:
  if event['event_type']=='research_embedding':
   q=event['payload'];assert q['left_padding_sec']==0
   queries.append(dict(session=index,event_id=q['event_id'],first=round(q['source_start_sec']*16000),last=round(q['source_end_sec']*16000),expected=q['normalized_embedding']))
assert queries==plan['embeddings']
names=['RESULT.json','PLAN.json','ADMISSION.json','OWNER.json','DISPATCH_OWNER.json','DISPATCH_RESULT.json','filtered.npy']+[f'd1_{i}.npy' for i in range(2)]+[f'e0_{i:03d}.npy' for i in range(len(queries))]
print(json.dumps(dict(result=r,plan=plan,owners=owners,units=u,bindings={n:sha(d/n) for n in names},arrays={n:base64.b64encode((d/n).read_bytes()).decode() for n in names if n.endswith('.npy')},application_review_sha256=sha(old/'REVIEW.json'))))
""")
 r=x['result'];plan=x['plan'];assert r['status']=='FILTERED_D1_E0_REFERENCE_COLLECTED_REQUIRES_REVIEW' and r['D1_closed'] and r['E0_released']
 assert not r['capture'] and not r['playback'] and not r['accuracy_scored']
 data={k:base64.b64decode(v) for k,v in x.pop('arrays').items()}
 for k,v in data.items():assert hashlib.sha256(v).hexdigest()==x['bindings'][k]
 arrays={k:np.load(io.BytesIO(v),allow_pickle=False) for k,v in data.items()};audio=arrays['filtered.npy']
 assert audio.shape==(715127,) and audio.dtype==np.float32 and hashlib.sha256(audio.tobytes()).hexdigest()==plan['filtered_float32_sha256']
 assert len(plan['sessions'])==2 and len(r['D1'])==4 and len(r['E0'])==2*len(plan['embeddings'])
 d1=[];e0=[]
 for index,s in enumerate(plan['sessions']):
  y=arrays[f'd1_{index}.npy'];expected=np.asarray(s['probabilities'],dtype=np.float32)
  assert y.shape==(2,*expected.shape) and y.shape[2]==8 and np.isfinite(y).all() and (y>=0).all() and (y<=1).all()
  err=float(np.max(np.abs(y-expected)));repeat=float(np.max(np.abs(y[0]-y[1])));assert err<=1e-5 and repeat<=1e-5
  d1.append(dict(session=index,samples=s['samples'],frames=len(expected),application_max_abs=err,repeat_max_abs=repeat))
 for index,q in enumerate(plan['embeddings']):
  y=arrays[f'e0_{index:03d}.npy'];expected=np.asarray(q['expected'],dtype=np.float32)
  assert y.shape==(2,192) and np.isfinite(y).all() and np.max(np.abs(np.linalg.norm(y,axis=1)-1))<1e-5
  err=float(np.max(np.abs(y-expected)));repeat=float(np.max(np.abs(y[0]-y[1])));assert err<=1e-5 and repeat<=1e-5
  digest=hashlib.sha256(audio[q['first']:q['last']].tobytes()).hexdigest()
  rows=[z for z in r['E0'] if z['query']==index];assert len(rows)==2 and {z['repeat'] for z in rows}=={0,1} and all(z['input_sha256']==digest for z in rows)
  e0.append(dict(query=index,application_max_abs=err,repeat_max_abs=repeat))
 review=dict(status='PASS_NATIVE_FILTERED_APPLICATION_D1_E0_REFERENCES_ONLY',bindings=x['bindings'],application_review_sha256=x['application_review_sha256'],D1=d1,E0_windows=len(e0),E0_calls=len(r['E0']),E0_application_max_abs=max(z['application_max_abs'] for z in e0),E0_repeat_max_abs=max(z['repeat_max_abs'] for z in e0),tolerance=1e-5,peak_rss_bytes=r['peak_rss_bytes'],owners=x['owners'],units=x['units'],constructed_only=True,live_route_qualified=False,stage_accepted=False)
 for n,v in data.items():
  with (out/n).open('xb') as f:f.write(v)
 for n,v in [('RESULT.json',r),('AUDIT_INPUTS.json',x),('REVIEW.json',review)]:
  with (out/n).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
 remote('REVIEW='+repr(review)+'\n'+"from pathlib import Path\nimport json\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-fir-references-v1/REVIEW.json')\nwith p.open('x') as f:json.dump(REVIEW,f,indent=2)\nprint(json.dumps({'written':True}))")
 print(json.dumps({k:v for k,v in review.items() if k not in ['bindings','owners','units']}))

if __name__=='__main__':main()
