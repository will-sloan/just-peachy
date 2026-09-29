"""Explicit quiet-route probe or no-device native contract checks. See README_LIVE_READY_V1.md."""
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
  from live_route_probe_v1 import probe
  import signal
  def interrupted(signum,frame):raise KeyboardInterrupt('Bounded stop requested')
  signal.signal(signal.SIGTERM,interrupted)
  if a['mode']=='user':
   assert a['physically_ready_attested'] is True and a['capture_seconds']==12
   config=json.loads((d/'live_config.json').read_text());config['evidence_dir']=str(d/'route-receipts');config['control_timeout_seconds']=2.
   r['probe']=probe(L,L.LiveConfig(**config),12.)
   assert r['probe']['status']=='SOURCE_COUNTS_COLLECTED_REQUIRES_REVIEW'
   r['status']='USER_QUIET_ROUTE_COLLECTED_REQUIRES_REVIEW'
  else:
   assert a['mode']=='mock' and not a['capture']
   import copy,types
   from unittest.mock import patch,Mock
   from test_live_audio import FakeSD,FakeControl,INITIAL
   from test_live_stop_ownership import StopOwnershipTests
   import unittest
   cases=[]
   initial=copy.deepcopy(INITIAL);initial.pop('USB_BIT_DEPTH');initial['BLD_MSG']='BLD_MSG intdev-lr48-lin-i2c'
   endpoint='XMOSDevice: I2S fixture (hw:2,1)'
   def config(name,**kwargs):return L.LiveConfig('fixture-host-never-executed',str(d/(name+'.lock')),hostapi='ALSA',control_protocol='i2c',endpoint_name=endpoint,expected_array_type=1,**kwargs)
   state={'endpoints':[dict(index=7,name=endpoint,max_input_channels=2,hostapi_name='ALSA')],'windows_audio':{}}
   diag=types.ModuleType('app.beam_diagnostics')
   class Diagnostics:
    def __init__(self,*args,**kwargs):pass
    def start(self):pass
    def stop(self,**kwargs):return True
   diag.BeamDiagnostics=Diagnostics
   def fixture(name,fail=None,tap='O0'):
    sd=FakeSD();control=FakeControl(initial=initial);control.diagnostic_values=lambda command:[]
    if fail=='lost_reply':control.fail_command='AUDIO_MGR_MIC_GAIN'
    if fail=='firmware':control.state['VERSION']=[0,0,0]
    before=copy.deepcopy(control.state)
    def ctl(cfg):control.stream=sd.streams[0];return control
    with patch.dict(sys.modules,{'sounddevice':sd,'app.beam_diagnostics':diag}),patch.object(L,'inventory',return_value=state),patch.object(L,'HostControl',side_effect=ctl),patch.object(L,'endpoint_snapshot',return_value={'status':'FAKE'}),patch.object(L,'compare_defaults',return_value={'status':'UNCHANGED_FIXTURE'}):
     answer=probe(L,config(name,tap=tap),.03,pump=lambda src:sd.streams[0].send())
    assert len(sd.streams)==1 and sd.streams[0].closed and not sd.streams[0].active and answer['lease_released']
    assert control.state==before
    if fail:assert answer['status']=='FAILED_PRESERVED' and answer['samples']==0
    else:
     assert answer['status']=='SOURCE_COUNTS_COLLECTED_REQUIRES_REVIEW' and answer['samples']==480 and answer['native_frames']==1440
     assert answer['integrity']['ok'] and answer['metadata']['route']['control_protocol']=='i2c'
     expected=.1*10**(3/20) if tap=='O0' else .2
     # Bound the chosen channel/gain, allowing FIR transition overshoot.
     assert expected*.9<=answer['maximum_absolute_amplitude']<expected*1.2
    L.DeviceLease(config(name).lease_path).acquire().close()
    return dict(name=name,pass_case=True,probe=answer,restored_exact=True,mocked_only=True)
   with patch.object(L,'DeviceLease') as lease:
    try:L.XVFLiveSource(config('no-consent')).start()
    except L.LiveAudioError:pass
    else:raise AssertionError('Consent gate failed')
    lease.assert_not_called()
   cases.append(dict(name='consent_required_before_lease',pass_case=True))
   cases.extend([fixture('O0'),fixture('O1',tap='O1'),fixture('lost_reply',fail='lost_reply'),fixture('firmware',fail='firmware')])
   result=unittest.TestResult();StopOwnershipTests('test_active_failed_close_retains_lease_and_retry_can_finish').run(result)
   assert result.wasSuccessful() and result.testsRun==1,(result.errors,result.failures)
   cases.append(dict(name='active_failed_close_retains_lease_until_retry',pass_case=True))
   assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
   r.update(status='MOCK_LIVE_ROUTE_GUARDS_COLLECTED_REQUIRES_REVIEW',cases=cases,actual_device_opened=False)
 except BaseException as e:r['error']=type(e).__name__+': '+str(e)
 r['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 with (d/'RESULT.json').open('x') as f:json.dump(r,f,indent=2)
 print(json.dumps({k:v for k,v in r.items() if k not in ['cases','probe']}));return int(r['status']=='FAILED_PRESERVED')

if __name__=='__main__':raise SystemExit(main())
