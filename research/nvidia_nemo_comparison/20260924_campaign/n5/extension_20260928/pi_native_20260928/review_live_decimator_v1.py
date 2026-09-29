"""Independent FIR reader. See README_LIVE_DECIMATOR_V1.md."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import argparse,base64,hashlib,io,json,wave,psutil
from dispatch_geometry_v2 import remote,PRIVATE

def main():
 psutil.Process().cpu_affinity([14])
 import numpy as np
 p=argparse.ArgumentParser();p.add_argument('--run-id',choices=['live-decimator-reference-v1','live-decimator-numpy-v1'],required=True);args=p.parse_args()
 out=PRIVATE/(args.run_id+'-evidence');assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
 x=remote('RUN='+repr(args.run_id)+'\n'+r"""
import os,json,hashlib,base64,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3});root=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928');d=root/RUN

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text());r=json.loads((d/'RESULT.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
assert a['reference_tolerance']==r['reference_tolerance']==1e-7 and a['address_space_max_bytes']==768*1024**2
owners=[]
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/n).read_text());pp=Path('/proc',str(o['pid']),'stat');t=int(pp.read_text().rsplit(')',1)[1].split()[19]) if pp.exists() else None
 assert not(o['boot_id']==boot and o['start_ticks']==t);assert o['admission_sha256']==sha(d/'ADMISSION.json');owners.append(dict(owner=o,observed_ticks=t,exact_alive=False))
u=dict(l.split('=',1) for l in subprocess.check_output(['systemctl','--user','show','jp-'+RUN,'-p','MainPID','-p','ActiveState','-p','Result','-p','ExecMainStatus'],text=True).splitlines())
assert u['MainPID']=='0' and u['Result']=='success' and u['ExecMainStatus']=='0'
assert json.loads((d/'DISPATCH_RESULT.json').read_text())['exit_code']==0
assert r['status']=='COLLECTED_REQUIRES_REVIEW' and not r['capture'] and not r['playback'] and not r['accuracy_scored']
names=['ADMISSION.json','RESULT.json','OWNER.json','DISPATCH_OWNER.json','DISPATCH_RESULT.json','taps.npy','source.wav']+[z['name']+'.npy' for z in r['cases']]
for z in r['cases']:assert sha(d/(z['name']+'.npy'))==z['output_sha256']
assert sha(d/'source.wav')==r['source_sha256'] and sha(d/'taps.npy')==r['taps_sha256']
data={n:base64.b64encode((d/n).read_bytes()).decode() for n in names}
ref={}
if a['kind']=='numpy':
 rd=Path(a['reference']);rr=json.loads((rd/'REVIEW.json').read_text());assert rr['status']=='PASS_NATIVE_ORIGINAL_FIR_COMPONENT_ONLY'
 for n in ['taps.npy']+[z['name']+'.npy' for z in r['cases']]:
  assert sha(rd/n)==rr['bindings'][n];ref[n]=base64.b64encode((rd/n).read_bytes()).decode()
print(json.dumps(dict(data=data,reference=ref,units=u,owners=owners,bindings={n:sha(d/n) for n in names})))
""")
 raw={k:base64.b64decode(v) for k,v in x.pop('data').items()};reference={k:base64.b64decode(v) for k,v in x.pop('reference').items()}
 for k,v in raw.items():assert hashlib.sha256(v).hexdigest()==x['bindings'][k]
 r=json.loads(raw['RESULT.json']);a=json.loads(raw['ADMISSION.json'])
 taps=np.load(io.BytesIO(raw['taps.npy']),allow_pickle=False);assert taps.shape==(97,) and taps.dtype==np.float64 and np.isfinite(taps).all()
 assert r['scipy_loaded']==(a['kind']=='reference') and r['filter_delay_seconds']==.001
 with wave.open(io.BytesIO(raw['source.wav']),'rb') as w:
  assert (w.getframerate(),w.getnchannels(),w.getsampwidth(),w.getnframes())==(16000,1,2,715127)
  full=np.repeat(np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768,3)
 inputs={'saved_full':full,'saved_irregular':full,'saved_repeat':full,'impulse_tail':np.r_[np.float32(1),np.zeros(4800,dtype=np.float32)],'quiet_short':np.full(1001,1e-6,dtype=np.float32),'empty_fresh':np.empty(0,dtype=np.float32)}
 assert [v['name'] for v in r['cases']]==list(inputs)
 rows=[];expected_full=np.convolve(full.astype(np.float64),taps,mode='full')[:len(full):3].astype(np.float32)
 for row in r['cases']:
  name=row['name'];v=inputs[name];y=np.load(io.BytesIO(raw[name+'.npy']),allow_pickle=False)
  assert row['input_sha256']==hashlib.sha256(v.tobytes()).hexdigest() and row['native_count']==row['native_samples']==len(v)
  assert row['model_samples']==len(y)==(len(v)+2)//3 and y.dtype==np.float32 and np.isfinite(y).all()
  expected=expected_full if name.startswith('saved_') else np.convolve(v.astype(np.float64),taps,mode='full')[:len(v):3].astype(np.float32) if len(v) else np.empty(0,dtype=np.float32)
  error=float(np.max(np.abs(y.astype(np.float64)-expected))) if len(y) else 0.;assert error<=1e-7,(name,error)
  rr=dict(name=name,independent_convolution_max_abs=error,native_samples=len(v),model_samples=len(y))
  if reference:
   z=np.load(io.BytesIO(reference[name+'.npy']),allow_pickle=False);assert z.shape==y.shape
   err=float(np.max(np.abs(y.astype(np.float64)-z))) if len(y) else 0.;assert err<=1e-7
   rr['original_native_max_abs']=err
  rows.append(rr)
 if reference:assert raw['taps.npy']==reference['taps.npy']
 result=dict(status='PASS_NATIVE_ORIGINAL_FIR_COMPONENT_ONLY' if a['kind']=='reference' else 'PASS_NATIVE_NUMPY_FIR_COMPONENT_ONLY',bindings=x['bindings'],closed_owners=x['owners'],units=x['units'],cases=rows,tolerance=1e-7,constructed_only=True,live_route_qualified=False,application_integration_qualified=False,memory=r['memory'],peak_rss_bytes=r['peak_rss_bytes'],initialization_seconds=r['initialization_seconds'],work_seconds={z['name']:z['work_seconds'] for z in r['cases']})
 for n,v in raw.items():
  with (out/n).open('xb') as f:f.write(v)
 with (out/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
 remote('RUN='+repr(args.run_id)+'\nREVIEW='+repr(result)+'\n'+"from pathlib import Path\nimport json\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/RUN/'REVIEW.json'\nwith p.open('x') as f:json.dump(REVIEW,f,indent=2)\nprint(json.dumps({'written':str(p)}))")
 print(json.dumps(dict(status=result['status'],peak_rss_mib=r['peak_rss_bytes']/1024**2,memory=r['memory'],work_seconds=result['work_seconds'],maximum_error=max(z['independent_convolution_max_abs'] for z in rows))))

if __name__=='__main__':main()
