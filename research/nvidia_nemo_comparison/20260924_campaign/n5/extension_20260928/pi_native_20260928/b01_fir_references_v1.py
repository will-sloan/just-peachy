"""No-capture native FIR diagnostic. See README_B01_FIR_REFERENCES_V1.md."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['ORT_DISABLE_TELEMETRY']='1'
import json,hashlib,resource,sys,time,wave
from pathlib import Path
from datetime import datetime,timezone

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def mem():
 return {line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines() if line.startswith(('VmRSS:','VmSize:','VmPeak:'))}

def main():
 d=Path(__file__).resolve().parent;a=json.loads((d/'ADMISSION.json').read_text())
 assert sorted(os.sched_getaffinity(0))==[2,3] and os.getuid()!=0
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==a['boot_id']
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
 assert resource.getrlimit(resource.RLIMIT_STACK)==(1048576,1048576)
 resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,)*2);resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 cg=next(v.split(':',2)[2] for v in Path('/proc/self/cgroup').read_text().splitlines() if v.startswith('0::'))
 q,period=(Path('/sys/fs/cgroup')/cg.lstrip('/')/'cpu.max').read_text().split();assert q!='max' and int(q)/int(period)<=2
 for row in a['files']:assert sha(Path(row['path']))==row['sha256']
 owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=a['boot_id'],admission_sha256=sha(d/'ADMISSION.json'))
 with (d/'OWNER.json').open('x') as f:json.dump(owner,f)
 r=dict(status='FAILED_PRESERVED',owner=owner,capture=False,playback=False,accuracy_scored=False)
 try:
  import numpy as np
  cfg=json.loads((d/'runtime.json').read_text());plan=json.loads((d/'PLAN.json').read_text());audio=np.load(d/'filtered.npy',allow_pickle=False)
  assert audio.shape==(715127,) and audio.dtype==np.float32 and np.isfinite(audio).all()
  digest=hashlib.sha256(audio.tobytes()).hexdigest();assert digest==plan['filtered_float32_sha256']
  sys.path.insert(0,str(Path(a['prototype'])/'vendor'))
  from edge_speech_pipeline.nemotron_diarization import NemotronDiarizer
  rows=[]
  with NemotronDiarizer(cfg['nemotron_model'],cfg['nemotron_library'],profile=cfg['streaming_profile'],gpu=-1,expected_library_sha256=cfg['nemotron_library_sha256']) as model:
   for index,session in enumerate(plan['sessions']):
    expected=np.asarray(session['probabilities'],dtype=np.float32);arrays=[]
    for repeat in range(2):
     model.reset(session_id=f'ref{index}_{repeat}');values=[];cursor=0;start=time.perf_counter()
     for offset in range(0,session['samples'],1600):
      chunk=audio[offset:min(offset+1600,session['samples'])].copy();prior=chunk.tobytes();u=model.push(chunk)
      assert chunk.tobytes()==prior and u.frame_start==cursor;cursor=u.frame_end;values.append(u.probabilities)
     u=model.finish();assert u.frame_start==cursor;cursor=u.frame_end;values.append(u.probabilities)
     y=np.concatenate(values);assert y.shape==expected.shape and np.isfinite(y).all()
     err=float(np.max(np.abs(y-expected)));assert err<=1e-5,err
     arrays.append(y);rows.append(dict(session=index,repeat=repeat,samples=session['samples'],frames=len(y),max_abs=err,seconds=time.perf_counter()-start))
     assert model.finish().probabilities.size==0
     try:model.push(np.zeros(1,np.float32))
     except RuntimeError:pass
     else:raise AssertionError('post-finish push accepted')
    assert np.max(np.abs(arrays[0]-arrays[1]))<=1e-5
    np.save(d/f'd1_{index}.npy',np.stack(arrays),allow_pickle=False)
  r['D1_closed']=True;r['D1']=rows
  import onnxruntime as ort
  options=ort.SessionOptions();options.intra_op_num_threads=options.inter_op_num_threads=1
  options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
  session=ort.InferenceSession(a['e0_model'],sess_options=options,providers=['CPUExecutionProvider']);assert session.get_providers()==['CPUExecutionProvider']
  rows=[]
  for index,q in enumerate(plan['embeddings']):
   x=audio[q['first']:q['last']].copy();assert 8000<=len(x)<=32000;before=x.tobytes();expected=np.asarray(q['expected'],dtype=np.float32);ys=[]
   for repeat in range(2):
    start=time.perf_counter();y=np.asarray(session.run(None,{'waveform':x[None,:]})[0][0],dtype=np.float32)
    assert y.shape==(192,) and np.isfinite(y).all();y=y/np.linalg.norm(y);assert abs(float(np.linalg.norm(y))-1)<1e-5 and x.tobytes()==before
    err=float(np.max(np.abs(y-expected)));assert err<=1e-5,err;ys.append(y)
    rows.append(dict(query=index,repeat=repeat,max_abs=err,seconds=time.perf_counter()-start,input_sha256=hashlib.sha256(before).hexdigest()))
   assert np.max(np.abs(ys[0]-ys[1]))<=1e-5;np.save(d/f'e0_{index:03d}.npy',np.stack(ys),allow_pickle=False)
  del session
  import gc;gc.collect();assert hashlib.sha256(audio.tobytes()).hexdigest()==digest
  r.update(status='FILTERED_D1_E0_REFERENCE_COLLECTED_REQUIRES_REVIEW',E0=rows,E0_released=True,tolerance=1e-5,plan_sha256=sha(d/'PLAN.json'),filtered_sha256=sha(d/'filtered.npy'))
 except Exception as e:r['error']=type(e).__name__+': '+str(e)
 r['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 with (d/'RESULT.json').open('x') as f:json.dump(r,f,indent=2)
 print(json.dumps({k:v for k,v in r.items() if k not in ['D1','E0']}));return int(r['status']=='FAILED_PRESERVED')

if __name__=='__main__':raise SystemExit(main())
