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
assert values['LimitAS']=='134217728' and values['LimitSTACK']=='1048576' and values['LimitFSIZE']=='33554432'
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
assert sum(map(len,files.values()))<=131072 and len(files)<=16
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
root.mkdir();results=[];owners=[]
try:
 (root/'code').mkdir();(root/'control').mkdir()
 for name,raw in files.items():
  assert Path(name).name==name and name.endswith('.py')
  write(root/'code'/name,raw)
 write(root/'control/MANIFEST.json',rawmanifest);write(root/'control/RELEASE.json',rawpolicy)
 sync(root/'code');sync(root/'control');sync(root);sync(root.parent)
 for phase in ('create','reopen','fault','fenced'):
  deadline()
  req=dict(root=str(root),policy_sha256=REQUEST['policy_sha256'],operation=REQUEST['operation'],phase=phase)
  proc=subprocess.Popen([sys.executable,'-B',str(root/'code/field_local_journal_check_v1.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:stdout,stderr=proc.communicate(json.dumps(req).encode(),timeout=25)
  except BaseException:
   proc.kill();proc.wait(timeout=5);raise
  assert len(stdout)<=32768 and len(stderr)<=8192
  lines=stdout.splitlines()
  for line in lines:
   event=json.loads(line);print(json.dumps(dict(event='CHILD',phase=phase,data=event)),flush=True)
   if event['event']=='OWNER':owners.append(event['owner'])
  print(json.dumps(dict(event='CHILD_EXIT',phase=phase,returncode=proc.returncode,stderr=base64.b64encode(stderr).decode())),flush=True)
  assert proc.returncode==0 and len(lines)==2
  o=json.loads(lines[0])['owner'];assert o['pid']==proc.pid and ticks(o['pid'])!=o['start_ticks']
  results.append(json.loads(lines[1])['result'])
finally:
 # Preserve the complete tree even after a test assertion fails. Export is read-only.
 entries=[];total=0
 for f in sorted(root.rglob('*')):
  rel=f.relative_to(root).as_posix();s=f.lstat()
  assert not f.is_symlink()
  if f.is_dir():entries.append(dict(path=rel,type='directory'));continue
  assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=131072
  raw=f.read_bytes();total+=len(raw);assert total<=262144
  row=dict(path=rel,type='file',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());entries.append(row)
  for n in range(0,len(raw),16384):
   print(json.dumps(dict(event='CHUNK',path=rel,offset=n,data=base64.b64encode(raw[n:n+16384]).decode())),flush=True)
  assert f.read_bytes()==raw
 assert len(entries)<=64
 print(json.dumps(dict(event='TREE',entries=entries,total_bytes=total)),flush=True)
 for fd in leasefds:os.close(fd)
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
deadline()
print(json.dumps(dict(event='RESULT',status='PASS_NATIVE_METADATA_REOPEN_AND_PENDING_FENCE',owner=owner,children=owners,phases=results,systemd_properties=values,target_before_bytes=target,capture=False,application_started=False,local_backup=False,production_activation=False)),flush=True)
