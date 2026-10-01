"""Fresh manager installation/reservation only; README_FIELD_LOCAL_JOINT_V1.md."""
import os,sys,resource,signal,json,hashlib,base64,subprocess,time,stat,fcntl,shutil
from pathlib import Path
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2);resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(33554432,)*2);signal.alarm(150);sys.dont_write_bytecode=True
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
print(json.dumps(dict(event='OWNER',owner=owner)),flush=True)
from datetime import datetime,timezone
def deadline():
 assert datetime.now(timezone.utc)<datetime.fromisoformat(REQUEST['operation']['expires_utc'])
 assert shutil.disk_usage(Path.home()).free>=5*1024**3
 mem=dict((x.split(':')[0],int(x.split()[1])*1024) for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith(('MemAvailable:','MemTotal:')))
 assert mem['MemAvailable']>=192*1024**2
 return mem
mem=deadline();assert mem['MemAvailable']>=850*1024**2 and 1700*1024**2<mem['MemTotal']<2100*1024**2
assert os.uname().machine=='aarch64' and 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
assert int(Path('/sys/class/block/mmcblk0/size').read_text())*512==31268536320
assert boot==REQUEST['baseline']['boot_id'] and ticks(1013)==569 and ticks(1130)==607
home=Path.home()/'JustPeachy'
for path,digest in REQUEST['physical_pins'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for o in REQUEST['prior_pi']:
 assert o['boot_id']!=boot or ticks(o['pid'])!=o['start_ticks']
leasefds=[]
for path in (home/'research/nemotron-20260928/B05_PREVIEW_DISPATCH.lock',home/'data/xvf-hardware.lock'):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);leasefds.append(fd)
unit=REQUEST['unit']
props=subprocess.check_output(['systemctl','--user','show',unit,'-p','CPUQuotaPerSecUSec','-p','AllowedCPUs','-p','TasksMax','-p','LimitAS','-p','LimitASSoft','-p','LimitSTACK','-p','LimitSTACKSoft','-p','LimitFSIZE','-p','RuntimeMaxUSec','-p','TimeoutStopUSec'],timeout=5,text=True)
values=dict(line.split('=',1) for line in props.splitlines())
print(json.dumps(dict(event='ENVELOPE',values=values)),flush=True)
assert values['CPUQuotaPerSecUSec']=='2s' and values['AllowedCPUs']=='2-3' and values['TasksMax']=='64'
assert values['LimitAS']==values['LimitASSoft']=='134217728' and values['LimitSTACK']==values['LimitSTACKSoft']=='1048576' and values['LimitFSIZE']=='33554432'
assert values['RuntimeMaxUSec']=='3min' and values['TimeoutStopUSec']=='15s'
root=Path(REQUEST['policy']['root']);assert not root.exists()
assert all(not Path(x).exists() for x in REQUEST['policy']['recording_roots'])
# Fresh measured target census includes all earlier retained roots. Never reset counters.
target=int(subprocess.check_output(['du','-sb',str(home/'research/nemotron-20260928')],timeout=15,text=True).split()[0])
a=REQUEST['policy']['allocation'];p=REQUEST['policy']
assert target<=p['measured_target_before_bytes']+REQUEST['accounting_margin_bytes']
assert target+p['measured_host_before_bytes']+a['combined_request_bytes']<=p['combined_output_cap_bytes']
assert p['measured_payload_before_bytes']+(target-p['measured_target_before_bytes'])+a['combined_request_bytes']<=p['total_payload_cap_bytes']
files={k:base64.b64decode(v,validate=True) for k,v in REQUEST['files'].items()}
assert 1<=len(files)<=16 and sum(map(len,files.values()))<=2097152
assert all(0<len(raw)<=131072 for raw in files.values())
assert REQUEST['manifest']['files']==[dict(path='code/'+k,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for k,v in sorted(files.items())]
rawmanifest=json.dumps(REQUEST['manifest'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()
rawpolicy=json.dumps(p,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
assert hashlib.sha256(rawmanifest).hexdigest()==p['release_manifest_sha256']
assert hashlib.sha256(rawpolicy).hexdigest()==REQUEST['policy_sha256']
def write(path,raw):
 assert len(raw)<=131072
 with path.open('xb') as f:
  for n in range(0,len(raw),16384):assert f.write(raw[n:n+16384])==len(raw[n:n+16384])
  f.flush();os.fsync(f.fileno())
 assert path.read_bytes()==raw
def sync(path):
 fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
root.mkdir()
try:
 (root/'code').mkdir();(root/'control').mkdir()
 for name,raw in files.items():
  if Path(name).name!=name or not name.endswith('.py'):raise ValueError('Exact code basename')
  write(root/'code'/name,raw)
 write(root/'control/MANIFEST.json',rawmanifest);write(root/'control/RELEASE.json',rawpolicy)
 sync(root/'code');sync(root/'control');sync(root);sync(root.parent)
 # Recheck the entire capsule before importing the prepared supervisor.
 for name,raw in files.items():
  if (root/'code'/name).read_bytes()!=raw:raise ValueError('Native source readback')
 sys.path.insert(0,str(root/'code'))
 import field_local_supervisor_v3 as supervisor
 if Path(supervisor.__file__).resolve()!=root/'code/field_local_supervisor_v3.py':
  raise ValueError('Exact supervisor origin')
 binding=REQUEST['binding']
 if binding['root']!=str(root) or binding['release_sha256']!=REQUEST['policy_sha256'] or binding['manifest_sha256']!=p['release_manifest_sha256'] or binding['operation']!=REQUEST['operation'] or binding['launch_slot']!='launch-01' or binding['recording_slot']!='recording-01':
  raise ValueError('Exact initial reservation binding')
 result=supervisor.phase(binding,'install-reserve')
 # OWNER/EXIT intent belongs to this real process; host must observe death.
 print(json.dumps(dict(event='RESULT',status='MANAGER_INSTALLED_AND_RESERVED',
  owner=owner,result=result,systemd_properties=values,target_before_bytes=target,
  source_root_absent=not Path(p['recording_roots'][0]).exists(),
  capture=False,production_activation=False,physical_closure_claimed=False)),flush=True)
finally:
 for fd in leasefds:os.close(fd)
deadline()
