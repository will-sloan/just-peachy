"""Fresh manager finish/reopen phase; README_FIELD_LOCAL_MIRROR_V2.md."""
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
import re,types
if type(REQUEST) is not dict or set(REQUEST)!={'operation','baseline','physical_pins','prior_pi','unit','policy','accounting_margin_bytes','files','manifest','policy_sha256','binding','phase'}:raise ValueError('Exact initializer request')
if type(REQUEST['accounting_margin_bytes']) is not int or not 0<=REQUEST['accounting_margin_bytes']<=8388608:raise ValueError('Bounded explicit margin')
if type(REQUEST['prior_pi']) is not list or not 1<=len(REQUEST['prior_pi'])<=1024:raise ValueError('Bounded exact prior owners')
for observed in REQUEST['prior_pi']:
 if type(observed) is not dict or set(observed)!={'pid','start_ticks','boot_id'} or type(observed['pid']) is not int or observed['pid']<=0 or type(observed['start_ticks']) is not int or observed['start_ticks']<=0 or type(observed['boot_id']) is not str or not re.fullmatch(r'[0-9a-f-]{36}',observed['boot_id']):raise ValueError('Exact process identity')
if type(REQUEST['unit']) is not str or not re.fullmatch(r'jp-field-local-phase-v[1-9][0-9]*\.service',REQUEST['unit']):raise ValueError('Exact initializer unit')
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
props=subprocess.check_output(['systemctl','--user','show',unit,'-p','CPUQuotaPerSecUSec','-p','AllowedCPUs','-p','TasksMax','-p','LimitAS','-p','LimitASSoft','-p','LimitSTACK','-p','LimitSTACKSoft','-p','LimitFSIZE','-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','MainPID','-p','ActiveState','-p','LimitFSIZESoft'],timeout=5,text=True)
values=dict(line.split('=',1) for line in props.splitlines())
print(json.dumps(dict(event='ENVELOPE',values=values)),flush=True)
assert values['CPUQuotaPerSecUSec']=='2s' and values['AllowedCPUs']=='2-3' and values['TasksMax']=='64'
assert values['LimitAS']==values['LimitASSoft']=='134217728' and values['LimitSTACK']==values['LimitSTACKSoft']=='1048576' and values['LimitFSIZE']=='33554432'
assert values['RuntimeMaxUSec']=='3min' and values['TimeoutStopUSec']=='15s'
assert values['MainPID']==str(owner['pid']) and values['ActiveState']=='active' and values['LimitFSIZESoft']=='33554432'
root=Path(REQUEST['policy']['root']);assert root.is_dir()
assert REQUEST['phase'] in ('finish','reopen')
assert all(Path(x).is_dir() and not Path(x).is_symlink() for x in REQUEST['policy']['recording_roots'])
assert not root.is_symlink()
for parent in [root.parent,*root.parent.parents]:
 if parent.is_symlink():raise ValueError('Real canonical parent chain')
units=subprocess.check_output(['systemctl','--user','list-units','--type=service','--state=running','--no-legend','--no-pager'],timeout=5,text=True)
assert not any(line.split()[0]!=unit and line.split()[0].startswith(('jp-','nemo-')) for line in units.splitlines() if line.split())
# Fresh measured target census includes all earlier retained roots. Never reset counters.
target=int(subprocess.check_output(['du','-sb',str(home/'research/nemotron-20260928')],timeout=15,text=True).split()[0])
a=REQUEST['policy']['allocation'];p=REQUEST['policy']
owned=sum(int(subprocess.check_output(['du','-sb',path],timeout=15,text=True).split()[0]) for path in [str(root)]+p['recording_roots'])
assert owned<=a['target_maximum_bytes']
outside=target-owned
assert outside<=p['measured_target_before_bytes']+REQUEST['accounting_margin_bytes']
assert outside+p['measured_host_before_bytes']+a['combined_request_bytes']<=p['combined_output_cap_bytes']
assert p['measured_payload_before_bytes']+(outside-p['measured_target_before_bytes'])+a['combined_request_bytes']<=p['total_payload_cap_bytes']
if type(REQUEST['files']) is not dict or not 1<=len(REQUEST['files'])<=16:raise ValueError('Bounded source map')
for name,body in REQUEST['files'].items():
 if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_]+\.py',name) or type(body) is not str or len(body)>174764:raise ValueError('Portable bounded code member')
if len({n.casefold() for n in REQUEST['files']})!=len(REQUEST['files']):raise ValueError('Code case alias')
files={k:base64.b64decode(v,validate=True) for k,v in REQUEST['files'].items()}
assert 1<=len(files)<=16 and sum(map(len,files.values()))<=2097152
assert all(0<len(raw)<=131072 for raw in files.values())
expected=dict(schema='just-peachy.local-release-manifest.v1',files=[dict(path='code/'+k,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for k,v in sorted(files.items())])
encode=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
assert encode(REQUEST['manifest'])==encode(expected)
rawmanifest=json.dumps(REQUEST['manifest'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()
rawpolicy=json.dumps(p,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
assert hashlib.sha256(rawmanifest).hexdigest()==p['release_manifest_sha256']
assert hashlib.sha256(rawpolicy).hexdigest()==REQUEST['policy_sha256']
assert len(rawmanifest)<=131072 and len(rawpolicy)<=65536
# Execute only the three hash-verified pure allocation modules in memory.
# These temporary origins are explicit and are removed BEFORE filesystem imports.
validation_names=['field_operator_session_plan_v1','field_operator_broker_layout_v2','field_local_release_plan_v2']
try:
 for name in validation_names:
  if name in sys.modules:raise ValueError('Unexpected preexisting validation module')
  module=types.ModuleType(name);module.__file__='<verified-capsule:'+name+'>'
  sys.modules[name]=module
  exec(compile(files[name+'.py'],module.__file__,'exec'),module.__dict__)
 validator=sys.modules[validation_names[-1]]
 validator.validate_release(p);validator.validate_research_operation(REQUEST['operation'])
 if a['recordings']!=1 or a['launches']!=3:raise ValueError('One recording/three launches')
finally:
 for name in validation_names:sys.modules.pop(name,None)
assert root.parent==home/'research/nemotron-20260928'
assert shutil.disk_usage(root.parent).free>=5*1024**3+a['target_maximum_bytes']
binding=REQUEST['binding']
if type(binding) is not dict or set(binding)!={'schema','root','release_sha256','manifest_sha256','recording_slot','launch_slot','operation'} or binding['schema']!='just-peachy.local-gate-binding.v1':
 raise ValueError('Exact initial binding fields')
if binding['root']!=str(root) or binding['release_sha256']!=REQUEST['policy_sha256'] or binding['manifest_sha256']!=p['release_manifest_sha256'] or encode(binding['operation'])!=encode(REQUEST['operation']) or binding['launch_slot']!='launch-03' or binding['recording_slot']!='recording-01':
 raise ValueError('Exact finish/reopen binding BEFORE mutation')
deadline()


def exact_file(path,expected):
 before=path.lstat()
 if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=len(expected):
  raise ValueError('Exact regular installed capsule member')
 if path.read_bytes()!=expected:raise ValueError('Installed capsule bytes changed')
 after=path.lstat()
 if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
  raise ValueError('Installed capsule identity changed')
try:
 if (root/'code').is_symlink() or not (root/'code').is_dir():raise ValueError('Real installed code')
 if {x.name for x in (root/'code').iterdir()}!=set(files):raise ValueError('Exact installed code membership')
 for name,raw in files.items():exact_file(root/'code'/name,raw)
 exact_file(root/'control/MANIFEST.json',rawmanifest);exact_file(root/'control/RELEASE.json',rawpolicy)
 # Only probe the outer leases here. Actual copier owns both throughout its
 # copy/readback; holding a second descriptor here would self-conflict.
 for fd in leasefds:os.close(fd)
 leasefds.clear()
 sys.path.insert(0,str(root/'code'))
 import field_local_supervisor_v3 as supervisor
 if Path(supervisor.__file__).resolve()!=root/'code/field_local_supervisor_v3.py':raise ValueError('Exact supervisor origin')
 result=supervisor.phase(binding,REQUEST['phase'])
 assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
 for path in (home/'research/nemotron-20260928/B05_PREVIEW_DISPATCH.lock',home/'data/xvf-hardware.lock'):
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  finally:os.close(fd)
 deadline()
 print(json.dumps(dict(event='RESULT',owner=owner,phase=REQUEST['phase'],result=result,
  systemd_properties=values,target_bytes=target,own_target_bytes=owned,
  physical_closure_claimed=False,capture=False,production_activation=False)),flush=True)
finally:
 for fd in leasefds:os.close(fd)
