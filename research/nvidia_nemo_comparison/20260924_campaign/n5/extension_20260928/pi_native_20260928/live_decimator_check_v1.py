"""No-capture native FIR diagnostic. See README_LIVE_DECIMATOR_V1.md."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
os.environ['CUDA_VISIBLE_DEVICES']='-1'
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
 r=dict(status='FAILED_PRESERVED',owner=owner,kind=a['kind'],capture=False,playback=False,accuracy_scored=False,memory={'before_numpy':mem()})
 try:
  import numpy as np
  r['memory']['after_numpy']=mem()
  if a['kind']=='reference':
   source=Path(a['prototype']);sys.path[:0]=[str(source),str(source/'vendor')]
   from app.live_audio import StreamingDecimator
   r['memory']['after_app_import']=mem()
   begin=time.perf_counter();initial=StreamingDecimator();r['initialization_seconds']=time.perf_counter()-begin
   taps=initial.taps.copy();factory=StreamingDecimator
  else:
   from decimator_numpy_v1 import NumpyDecimator
   taps=np.load(Path(a['reference'])/'taps.npy',allow_pickle=False)
   begin=time.perf_counter();initial=NumpyDecimator(taps);r['initialization_seconds']=time.perf_counter()-begin
   factory=lambda:NumpyDecimator(taps)
  r['memory']['after_initialization']=mem()
  np.save(d/'taps.npy',taps,allow_pickle=False)
  with wave.open(str(d/'source.wav'),'rb') as w:
   assert (w.getframerate(),w.getnchannels(),w.getsampwidth(),w.getnframes())==(16000,1,2,715127)
   saved=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
  # Explicit constructed diagnostic, not captured48k audio or an accuracy input.
  full=np.repeat(saved,3);input_digest=hashlib.sha256(full.tobytes()).hexdigest()
  cases=[('saved_full',full,[960]),('saved_irregular',full,[1,2,3,7,959,961,479]),('saved_repeat',full,[960]),
         ('impulse_tail',np.r_[np.float32(1),np.zeros(4800,dtype=np.float32)],[1,479,960]),
         ('quiet_short',np.full(1001,1e-6,dtype=np.float32),[17,960]),('empty_fresh',np.empty(0,dtype=np.float32),[])]
  rows=[]
  for name,values,widths in cases:
   model=factory();outputs=[];cursor=0;index=0;calls=0;work=0.;maximum=0.
   while cursor<len(values):
    n=min(widths[index%len(widths)],len(values)-cursor);raw=values[cursor:cursor+n].copy();original=raw.tobytes()
    start=time.perf_counter();y=model.convert(raw);elapsed=time.perf_counter()-start
    assert raw.tobytes()==original and y.dtype==np.float32 and np.isfinite(y).all()
    assert len(y)==(cursor+n+2)//3-(cursor+2)//3
    outputs.append(y);cursor+=n;index+=1;calls+=1;work+=elapsed;maximum=max(maximum,elapsed)
   out=np.concatenate(outputs) if outputs else np.empty(0,dtype=np.float32)
   assert len(out)==(len(values)+2)//3 and model.native_count==len(values) and model.delay_seconds==.001
   np.save(d/(name+'.npy'),out,allow_pickle=False)
   rows.append(dict(name=name,native_samples=len(values),model_samples=len(out),calls=calls,work_seconds=work,max_call_seconds=maximum,native_count=model.native_count,input_sha256=hashlib.sha256(values.tobytes()).hexdigest(),output_sha256=sha(d/(name+'.npy'))))
  assert hashlib.sha256(full.tobytes()).hexdigest()==input_digest
  r.update(status='COLLECTED_REQUIRES_REVIEW',cases=rows,taps_sha256=sha(d/'taps.npy'),source_sha256=sha(d/'source.wav'),scipy_loaded=any(k=='scipy' or k.startswith('scipy.') for k in sys.modules),filter_delay_seconds=.001,constructed_input='np.repeat(saved_PCM16_float32,3); zero-order-hold diagnostic',flush_policy='Existing source has no tail flush; output counts only received native samples, no appended filter tail',reference_tolerance=1e-7)
  r['memory']['terminal']=mem()
 except Exception as e:r['error']=type(e).__name__+': '+str(e)
 r['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 with (d/'RESULT.json').open('x') as f:json.dump(r,f,indent=2)
 print(json.dumps({k:v for k,v in r.items() if k not in ['cases','memory']}));return int(r['status']=='FAILED_PRESERVED')

if __name__=='__main__':raise SystemExit(main())
