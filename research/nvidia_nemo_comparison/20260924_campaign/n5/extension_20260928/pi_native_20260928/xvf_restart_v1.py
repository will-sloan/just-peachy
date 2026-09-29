"""One-shot XVF recovery; never captures or plays audio. See README_XVF_RESTART_V1.md."""
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
 r=dict(status='FAILED_PRESERVED',owner=owner,mode=a['mode'],real_capture=a['mode']=='user',audio_saved=False,models_loaded=False)
 try:
  source=Path(a['prototype']);sys.path[:0]=[str(source),str(source/'vendor'),str(source/'tests')]
  from app import live_audio as L
  
  import signal
  def interrupted(signum,frame):raise KeyboardInterrupt('Bounded stop requested')
  signal.signal(signal.SIGTERM,interrupted)
  assert a['mode']=='reset' and not a['capture']
  config=json.loads((d/'live_config.json').read_text());config['control_timeout_seconds']=2.
  cfg=L.LiveConfig(**config)
  assert cfg.control_protocol=='i2c' and cfg.hostapi=='ALSA' and cfg.native_rate==48000
  assert cfg.host_executable=='/home/peachyprototype/JustPeachy/tools/native_xvf_usb/bin/xvf_host'
  assert cfg.lease_path=='/home/peachyprototype/JustPeachy/data/xvf-hardware.lock'
  assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
  with L.DeviceLease(cfg.lease_path):
   control=L.HostControl(cfg)
   before=dict(version=control.values('VERSION'),build=control.query('BLD_MSG'))
   assert before['version']==[3,2,1] and 'intdev-lr48-lin-i2c' in before['build']
   # Persist intent before the single setter. An uncertain reply is not retried.
   with (d/'RESTART_INTENT.json').open('x') as f:json.dump(dict(command='TEST_CORE_BURN',arguments=[0],before=before,monotonic=time.monotonic()),f)
   try:r['restart_reply']=control.query('TEST_CORE_BURN',0)
   except Exception as exc:r['restart_reply_error']=type(exc).__name__+': '+str(exc)
   time.sleep(2.)
   after=dict(version=control.values('VERSION'),build=control.query('BLD_MSG'))
   assert after==before and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
   r.update(status='SINGLE_XVF_RESTART_SENT_FIRMWARE_READBACK_ONLY',before=before,after=after,commands=control.receipts,volatile_DSP_state_reset=True,unreadable_prior_DSP_state_restored=False,capture_opened=False)
  r['hardware_lease_released']=True
 except BaseException as e:r['error']=type(e).__name__+': '+str(e)
 r['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 with (d/'RESULT.json').open('x') as f:json.dump(r,f,indent=2)
 print(json.dumps({k:v for k,v in r.items() if k not in ['cases','probe']}));return int(r['status']=='FAILED_PRESERVED')

if __name__=='__main__':raise SystemExit(main())
