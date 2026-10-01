"""Exact existing TitaNet asset installer; README_RUNTIME_TITANET_INSTALL_V1.md."""
import os,resource,signal,json,sys,hashlib,subprocess,shutil,fcntl,datetime,base64,re,struct,stat,time
from pathlib import Path
os.sched_setaffinity(0,{3})
for kind,cap in ((resource.RLIMIT_AS,134217728),(resource.RLIMIT_STACK,1048576),(resource.RLIMIT_FSIZE,94371840),(resource.RLIMIT_CORE,0)):
 resource.setrlimit(kind,(cap,cap))
signal.alarm(80)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
who=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
def frame(v):
 raw=json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 assert 0<len(raw)<=262144
 sys.stdout.buffer.write(struct.pack('!I',len(raw))+raw);sys.stdout.buffer.flush()
def exact(n):
 assert type(n) is int and 0<=n<=262144
 out=bytearray()
 while len(out)<n:
  b=sys.stdin.buffer.read(min(16384,n-len(out)))
  if not b:raise EOFError('Incomplete asset transfer')
  out.extend(b)
 return bytes(out)
frame(dict(early_owner=who))
raw=exact(struct.unpack('!I',exact(4))[0])
assert hashlib.sha256(raw).hexdigest()==sys.argv[1]
request=json.loads(raw)
REQUEST_RAW=raw
assert set(request)=={'schema','root','unit','issued_utc','expires_utc','files','allocation','accounting','prior','historical','nested','baseline'}
assert request['schema']=='just-peachy.titanet-asset-install.v1'
start=datetime.datetime.fromisoformat(request['issued_utc']);expiry=datetime.datetime.fromisoformat(request['expires_utc'])
now=datetime.datetime.now(datetime.timezone.utc)
assert start.tzinfo and expiry.tzinfo and start<=now<expiry and 0<(expiry-start).total_seconds()<=600
assert now+datetime.timedelta(seconds=120)<expiry<=datetime.datetime(2026,10,2,14,14,20,tzinfo=datetime.timezone.utc)
PRIOR=request['prior'];HISTORICAL=request['historical'];NESTED=request['nested'];PRIOR_SHA='current-request-bound'
unit=request['unit']
assert re.fullmatch(r'jp-titanet-assets-v[1-9][0-9]*',unit)
props=subprocess.check_output(['systemctl','--user','show',unit+'.service','-p','ActiveState','-p','MainPID','-p','AllowedCPUs','-p','CPUQuotaPerSecUSec','-p','TasksMax','-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','LimitAS','-p','LimitSTACK','-p','LimitFSIZE'],text=True,timeout=8)
actual=dict(l.split('=',1) for l in props.splitlines())
assert actual['ActiveState']=='active' and actual['MainPID']==str(os.getpid())
assert actual['AllowedCPUs']=='2-3' and actual['CPUQuotaPerSecUSec']=='2s' and actual['TasksMax']=='64'
assert actual['RuntimeMaxUSec']=='1min 30s' and actual['TimeoutStopUSec']=='10s'
assert actual['LimitAS']=='134217728' and actual['LimitSTACK']=='1048576' and actual['LimitFSIZE']=='94371840'
home=Path.home();root=home/'JustPeachy/research/nemotron-20260928'
def identity(v):
 assert type(v) is dict and set(v)=={'pid','start_ticks','boot_id'}
 assert type(v['pid']) is int and v['pid']>0 and type(v['start_ticks']) is int and v['start_ticks']>0
 assert type(v['boot_id']) is str and re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',v['boot_id'])
 return v
def strict(raw):
 def pairs(rows):
  d={}
  for k,v in rows:
   assert k not in d;d[k]=v
  return d
 return json.loads(raw,object_pairs_hook=pairs)
def sha(raw):return hashlib.sha256(raw).hexdigest()
assert os.uname().machine=='aarch64' and 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
assert int(Path('/sys/class/block/mmcblk0/size').read_text())*512==31268536320
mem={k.rstrip(':'):int(v.split()[0])*1024 for k,v in (x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines())}
assert 1700*1024**2<mem['MemTotal']<2100*1024**2 and mem['MemAvailable']>=192*1024**2
assert shutil.disk_usage(root).free>=5*1024**3
def command(argv,env=None):
 p=subprocess.run(argv,capture_output=True,timeout=8,env=env)
 assert len(p.stdout)+len(p.stderr)<=32768
 return dict(returncode=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace'))
owner_hash=hashlib.sha256();count=0;typed=0;all_ids=set()
for v in PRIOR:
 identity(v);observed=ticks(v['pid'])
 assert not(v['boot_id']==boot and observed==v['start_ticks'])
 owner_hash.update(json.dumps([v,observed],sort_keys=True).encode());all_ids.add((v['boot_id'],v['pid'],v['start_ticks']))
for p in sorted(root.rglob('*OWNER*.json')):
 assert not p.is_symlink() and p.is_file() and p.stat().st_size<=16384
 raw=p.read_bytes();v=strict(raw);rel=p.relative_to(root).as_posix()
 owner_hash.update(rel.encode()+b'\0'+hashlib.sha256(raw).digest());count+=1
 if p.name=='OWNERSHIP_CLOSURE.json':
  assert set(v)=={'borrowed','outer_released','controller_closed','worker_joined','pending_commands'}
  assert v['outer_released'] is True and type(v['controller_closed']) is bool and type(v['worker_joined']) is bool
  assert type(v['borrowed']) is dict and set(v['borrowed'])=={'opened','closed'}
  assert all(type(x) is int and 0<=x<=1 for x in v['borrowed'].values()) and v['borrowed']['closed']<=v['borrowed']['opened']
  assert v['pending_commands'] is None or type(v['pending_commands']) is int and v['pending_commands']>=0
  typed+=1;continue
 if 'owner' in v:
  assert rel in NESTED and set(v)=={'owner','policy_sha256','slot','utc','purpose'}
  expected=NESTED[rel]
  assert sha(raw)==expected['sha256'] and v['policy_sha256']==expected['policy_sha256'] and v['purpose']==expected['purpose'] and v['slot']==expected['slot']
  stamp=datetime.datetime.fromisoformat(v['utc']);assert stamp.tzinfo is not None
  v=v['owner']
 elif set(v)!={'pid','start_ticks','boot_id'}:
  assert rel in HISTORICAL and json.dumps(v,sort_keys=True,separators=(',',':'))==json.dumps(HISTORICAL[rel],sort_keys=True,separators=(',',':')), ('Unrecognized completed owner',rel,sorted(v))
  v={k:v[k] for k in ('pid','start_ticks','boot_id')}
 identity(v);observed=ticks(v['pid'])
 assert not(v['boot_id']==boot and observed==v['start_ticks'])
 all_ids.add((v['boot_id'],v['pid'],v['start_ticks']))
units=command(['systemctl','--user','list-units','--state=active,activating,deactivating','--plain','--no-legend','jp-*'])
assert units['returncode']==0 and all(l.split()[0]==unit+'.service' for l in units['stdout'].splitlines() if l.strip())
capture={}
for p in sorted(Path('/proc/asound').glob('card*/pcm*c/sub*/status')):
 text=p.read_text();assert len(text)<=4096;capture[str(p)]=text.strip()
assert capture and all(v=='closed' for v in capture.values())
leases=[]
for p in (root/'B05_PREVIEW_DISPATCH.lock',home/'JustPeachy/data/xvf-hardware.lock'):
 with p.open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
 leases.append(str(p))
files=[]
for rel in ('JustPeachy/install/current.json','JustPeachy/data/live_config.json','JustPeachy/data/settings.json','.config/kanshi/config'):
 p=home/rel;assert p.is_file() and not p.is_symlink() and p.stat().st_size<=65536
 raw=p.read_bytes();files.append(dict(path=str(p),bytes=len(raw),sha256=sha(raw),text=raw.decode()))
settings=json.loads((home/'JustPeachy/data/settings.json').read_bytes())
assert settings.get('auto_start_listening') is False
assert sha((home/'.config/kanshi/config').read_bytes())=='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b'
processes=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==who['pid']:continue
 try:
  with (p/'cmdline').open('rb') as f:raw=f.read(8193)
 except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 if raw.split(b'\0',1)[0] not in (b'/usr/bin/python3.11',b'/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python'):continue
 assert len(raw)<=8192 and len(processes)<64
 start=ticks(int(p.name))
 if start is not None:processes.append(dict(pid=int(p.name),start_ticks=start,boot_id=boot,cmdline=raw.replace(b'\0',b' ').decode(errors='replace')))
startup=[];candidates=set((home/'.config/autostart').glob('*.desktop'))
candidates|=set((home/'.config/systemd/user').glob('*peach*'))
candidates|={home/'.config/labwc/autostart',home/'.config/wayfire.ini',home/'.config/lxsession/LXDE-pi/autostart'}
total=0
for p in sorted(candidates):
 if not p.exists() or p.is_dir():continue
 assert not p.is_symlink() and p.stat().st_size<=65536
 raw=p.read_bytes();total+=len(raw);assert total<=65536
 startup.append(dict(path=str(p),bytes=len(raw),sha256=sha(raw),base64=base64.b64encode(raw).decode()))

def file_hash(path,limit):
 before=path.lstat()
 assert not path.is_symlink() and path.is_file() and before.st_size<=limit and before.st_nlink==1
 h=hashlib.sha256();count=0
 with path.open('rb') as f:
  while True:
   block=f.read(16384)
   if not block:break
   h.update(block);count+=len(block)
 after=path.lstat()
 assert count==before.st_size and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
 return dict(bytes=count,sha256=h.hexdigest())
titanet_assets=[]
for name in ('titanet_manifest.json','titanet_embedding.onnx','titanet_frontend.npz'):
 for p in (home/'JustPeachy').rglob(name):
  assert len(titanet_assets)<32
  if p.is_symlink():
   titanet_assets.append(dict(path=str(p),symlink=True));continue
  asset_pin=file_hash(p,90*1024**2)
  asset_pin['path']=str(p);titanet_assets.append(asset_pin)
galleries=[]
gallery_roots=[home/'JustPeachy/data/people']
spaces=home/'JustPeachy/data/embedding_spaces'
if spaces.exists():
 entries=list(spaces.iterdir());assert len(entries)<=32 and not spaces.is_symlink()
 gallery_roots += [p/'people' for p in entries if p.is_dir() and not p.is_symlink()]
for folder in gallery_roots:
 row=dict(root=str(folder),exists=folder.exists(),files={},directories=[])
 if folder.exists():
  for base,dirs,names in os.walk(folder,followlinks=False):
   p=Path(base);assert not p.is_symlink()
   rel=p.relative_to(folder).as_posix();row['directories'].append('' if rel=='.' else rel)
   assert len(row['directories'])<=64
   for name in names:
    q=p/name;row['files'][q.relative_to(folder).as_posix()]=file_hash(q,32*1024**2)
    assert len(row['files'])<=256
  row['bytes']=sum(p['bytes'] for p in row['files'].values())
  row['reserved_bytes']=row['bytes']+65536*len(row['directories'])
  assert row['reserved_bytes']<=128*1024**2
 galleries.append(row)
launcher=home/'JustPeachy/start-prototype.sh'
launcher_raw=launcher.read_bytes()
assert not launcher.is_symlink() and len(launcher_raw)<=65536
launcher_backup=dict(path=str(launcher),bytes=len(launcher_raw),sha256=sha(launcher_raw),base64=base64.b64encode(launcher_raw).decode())

env=dict(os.environ,XDG_RUNTIME_DIR='/run/user/1000',WAYLAND_DISPLAY='wayland-0')
display=command(['wlr-randr'],env)
assert display['returncode']==0 and 'Transform: 270' in display['stdout'] and 'Enabled: yes' in display['stdout']
value=dict(schema='just-peachy.runtime-install-inspection.v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),utility_owner=who,
 boot_id=boot,owner_paths_read=count,prior_identities_checked=len(PRIOR),unique_recorded_identities=len(all_ids),typed_nonidentity_closures=typed,
 owner_inventory_sha256=owner_hash.hexdigest(),prior_closure_sha256=PRIOR_SHA,
 titanet_assets=titanet_assets,galleries=galleries,launcher_backup=launcher_backup,files=files,current_project_processes=processes,startup_files=startup,units=units,capture=capture,free_leases=leases,display=display,
 sound_cards=Path('/proc/asound/cards').read_text(),available_ram_bytes=mem['MemAvailable'],target_free_bytes=shutil.disk_usage(root).free,
 target_bytes=int(subprocess.check_output(['du','-sb',str(root)],text=True,timeout=8).split()[0]),native_writes=False,capture_started=False)
raw=json.dumps(value)
assert len(raw.encode())<=262144
assert boot==request['baseline']['boot_id']
for old in request['baseline']['owners']:
 assert old['boot_id']==boot and ticks(old['pid'])==old['start_ticks']
for row in files:
 assert request['baseline']['config_pins'].get(row['path'])==row['sha256']
assert mem['MemAvailable']>=850*1024**2
destination=Path(request['root'])
assert destination.parent==root and re.fullmatch('runtime-titanet-v[1-9][0-9]*',destination.name) and destination.resolve()==destination
assert not destination.exists() and not destination.is_symlink()
expected={'titanet_manifest.json':1284,'titanet_embedding.onnx':88610787,'titanet_frontend.npz':84358}
assert set(request['files'])==set(expected)
for name,size in expected.items():
 row=request['files'][name];assert set(row)=={'bytes','sha256'} and type(row['bytes']) is int and row['bytes']==size
 assert re.fullmatch('[0-9a-f]{64}',row['sha256'])
assert request['files']['titanet_embedding.onnx']['sha256']=='86b64bc03a7b151231f59745a8d36619fbc68b739a4abb253bd0d9ce0c350610'
assert request['files']['titanet_frontend.npz']['sha256']=='582f92d2fa2a29be70f6fdc13d67fc1376083ca66cb35401f8335ed85c4115b6'
total=sum(expected.values());allocation=request['allocation']
assert allocation==dict(target_bytes=total+1048576,host_bytes=2*total+4194304,combined_bytes=3*total+5242880)
account=request['accounting']
assert all(type(v) is int and v>=0 for v in account.values())
assert value['target_bytes']<=account['target_bytes']+1048576
assert account['host_window_bytes']+value['target_bytes']+allocation['combined_bytes']<=account['combined_cap']
assert account['host_payload_bytes']+2684354560+value['target_bytes']+allocation['combined_bytes']<=account['payload_cap']
assert shutil.disk_usage(root).free>=5*1024**3+allocation['target_bytes']
locks=[]
try:
 for path in (root/'B05_PREVIEW_DISPATCH.lock',home/'JustPeachy/data/xvf-hardware.lock'):
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(fd)
 def guard():
  assert datetime.datetime.now(datetime.timezone.utc)<expiry-datetime.timedelta(seconds=30)
  available=next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
  assert available>=192*1024**2 and shutil.disk_usage(root).free>=5*1024**3
 def sync(path):
  fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:os.fsync(fd)
  finally:os.close(fd)
 def put(name,data):
  assert len(data)<=262144
  with (destination/name).open('xb') as f:
   assert f.write(data)==len(data);f.flush();os.fsync(f.fileno())
  assert (destination/name).read_bytes()==data
 guard();destination.mkdir();sync(root)
 put('OWNER.json',json.dumps(who,sort_keys=True).encode())
 put('ADMISSION.json',REQUEST_RAW)
 frame(dict(type='HELLO',owner=who))
 for name in sorted(expected):
  row=request['files'][name];h=hashlib.sha256();remaining=row['bytes']
  with (destination/name).open('xb') as f:
   while remaining:
    guard();block=exact(min(16384,remaining))
    if f.write(block)!=len(block):raise OSError('Short target asset write')
    remaining-=len(block);h.update(block)
   f.flush();os.fsync(f.fileno())
  assert h.hexdigest()==row['sha256']
  assert file_hash(destination/name,row['bytes'])==row
 sync(destination)
 verified={name:file_hash(destination/name,size) for name,size in sorted(expected.items())}
 assert verified==request['files']
 result=dict(schema='just-peachy.titanet-assets-installed.v1',owner=who,root=str(destination),files=verified,
  unit_properties=actual,preflight=value,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  model_loaded=False,capture_started=False,active_configuration_changed=False)
 put('RESULT.json',json.dumps(result,sort_keys=True).encode());sync(destination)
 assert {p.name for p in destination.iterdir()}==set(expected)|{'OWNER.json','ADMISSION.json','RESULT.json'}
 frame(dict(type='INSTALLED',result=result))
finally:
 for fd in reversed(locks):os.close(fd)
