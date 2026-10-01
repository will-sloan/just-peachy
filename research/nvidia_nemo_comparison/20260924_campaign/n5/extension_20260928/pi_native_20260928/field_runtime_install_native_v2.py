"""Controlled runtime installer; README_RUNTIME_ACTIVATION_V2.md."""
import os,resource,signal,json,sys,hashlib,subprocess,shutil,fcntl,datetime,base64,re,struct,stat,time
from pathlib import Path
os.sched_setaffinity(0,{3})
for kind,cap in ((resource.RLIMIT_AS,134217728),(resource.RLIMIT_STACK,1048576),(resource.RLIMIT_FSIZE,94371840),(resource.RLIMIT_CORE,0)):
 resource.setrlimit(kind,(cap,cap))
signal.alarm(160)
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
assert set(request)=={'schema','root','unit','issued_utc','expires_utc','files','allocation','accounting','prior','historical','nested','baseline','policy','manifest','asset_root','rollback_source','renderer_source','rollback_source_sha256','renderer_source_sha256','autostart_sha256','launcher_sha256','galleries'}
assert request['schema']=='just-peachy.runtime-install-admission.v1'
start=datetime.datetime.fromisoformat(request['issued_utc']);expiry=datetime.datetime.fromisoformat(request['expires_utc'])
now=datetime.datetime.now(datetime.timezone.utc)
assert start.tzinfo and expiry.tzinfo and start<=now<expiry and 0<(expiry-start).total_seconds()<=600
assert now+datetime.timedelta(seconds=120)<expiry<=datetime.datetime(2026,10,2,14,14,20,tzinfo=datetime.timezone.utc)
PRIOR=request['prior'];HISTORICAL=request['historical'];NESTED=request['nested'];PRIOR_SHA=hashlib.sha256(json.dumps(PRIOR,sort_keys=True,separators=(',',':')).encode()).hexdigest()
unit=request['unit']
assert re.fullmatch(r'jp-install-field-runtime-v[1-9][0-9]*',unit)
props=subprocess.check_output(['systemctl','--user','show',unit+'.service','-p','ActiveState','-p','MainPID','-p','AllowedCPUs','-p','CPUQuotaPerSecUSec','-p','TasksMax','-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','LimitAS','-p','LimitSTACK','-p','LimitFSIZE'],text=True,timeout=8)
actual=dict(l.split('=',1) for l in props.splitlines())
assert actual['ActiveState']=='active' and actual['MainPID']==str(os.getpid())
assert actual['AllowedCPUs']=='2-3' and actual['CPUQuotaPerSecUSec']=='2s' and actual['TasksMax']=='64'
assert actual['RuntimeMaxUSec']=='3min' and actual['TimeoutStopUSec']=='10s'
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

# Everything above this point is read-only current-owner/device/config census.
# All new destinations are independently reserved, fresh and retained on failure.
release=Path(request['root']);rid=release.name
assert release.parent==root and release.resolve()==release and re.fullmatch('field-runtime-v[1-9][0-9]*',rid)
assert unit=='jp-install-'+rid
assert request['schema']=='just-peachy.runtime-install-admission.v1'
policy=strict(base64.b64decode(request['policy'],validate=True))
manifest=strict(base64.b64decode(request['manifest'],validate=True))
policy_raw=base64.b64decode(request['policy'],validate=True);manifest_raw=base64.b64decode(request['manifest'],validate=True)
assert len(policy_raw)<=65536 and len(manifest_raw)<=131072
assert policy['manager_root']==str(release) and policy['release_id']==rid
assert sha(manifest_raw)==policy['runtime_manifest_sha256']
assert policy['allocation']['combined_request_bytes']==2453742272
assert policy['allocation']['target_maximum_bytes']==1218482528
assert policy['allocation']['host_maximum_bytes']==1235259744
assert policy['allocation']['recordings']==4 and policy['allocation']['launches']==16
assert len(policy['recording_roots'])==4 and len(set(policy['recording_roots']))==4
for name in policy['recording_roots']:
 p=Path(name)
 assert p.parent==root and p.resolve()==p and re.fullmatch('field-operator-sessions-v[1-9][0-9]*',p.name)
 assert not p.exists() and not p.is_symlink()
allocation=request['allocation']
external_target=89745005+8*1024**2+4*1024**2+2*1024**2
external_host=181587162+2*(8+4+2)*1024**2+4*1024**2
assert allocation==dict(target_bytes=1218482528+external_target,host_bytes=1235259744+external_host,
 combined_bytes=2453742272+external_target+external_host)
account=request['accounting']
assert all(type(v) is int and v>=0 for v in account.values())
assert value['target_bytes']<=account['target_bytes']+1048576
assert account['host_window_bytes']+value['target_bytes']+allocation['combined_bytes']<=account['combined_cap']
assert account['host_payload_bytes']+2684354560+value['target_bytes']+allocation['combined_bytes']<=account['payload_cap']
assert policy['combined_output_cap_bytes']==account['combined_cap'] and policy['total_payload_cap_bytes']==account['payload_cap']
assert shutil.disk_usage(root).free>=5*1024**3+allocation['target_bytes']
activation=release.with_name(rid+'-activation');profiles=release.with_name(rid+'-profiles')
gallery=release.with_name(rid+'-galleries');assets=root/request['asset_root']
assert re.fullmatch('runtime-titanet-v[1-9][0-9]*',assets.name)
destinations=(release,activation,profiles,gallery,assets)
for destination in destinations:
 assert not destination.exists() and not destination.is_symlink()
pins=request['files'];assert type(pins) is dict and 1<=len(pins)<=96
aliases=set();stream_total=0
for name,row in pins.items():
 path=Path(name)
 assert path.as_posix()==name and not path.is_absolute() and '..' not in path.parts and len(path.parts)<=5
 assert path.parts[0] in {p.name for p in (release,profiles,assets)}
 assert name.casefold() not in aliases;aliases.add(name.casefold())
 assert set(row)=={'bytes','sha256'} and type(row['bytes']) is int and 0<row['bytes']<=90*1024**2
 assert re.fullmatch('[0-9a-f]{64}',row['sha256']);stream_total+=row['bytes']
 if path.parts[0]==rid:
  assert len(path.parts)==3 and path.parts[1]=='code' and path.suffix=='.py' and row['bytes']<=131072
 elif path.parts[0]==profiles.name:
  assert len(path.parts)==2 and path.name in {'COMMON_BUNDLE.json'}|{p+'.json' for p,v in policy['profiles'].items() if v['available']}
  assert row['bytes']<=1048576
 else:
  assert len(path.parts)==2 and path.name in ('titanet_manifest.json','titanet_embedding.onnx','titanet_frontend.npz')
assert stream_total<=92*1024**2
assert len(manifest['files'])==16 and sum(r['bytes'] for r in manifest['files'])<=2097152
assert {rid+'/'+r['path']:dict(bytes=r['bytes'],sha256=r['sha256']) for r in manifest['files']}=={n:r for n,r in pins.items() if n.startswith(rid+'/')}
assert pins[assets.name+'/titanet_embedding.onnx']==dict(bytes=88610787,sha256='86b64bc03a7b151231f59745a8d36619fbc68b739a4abb253bd0d9ce0c350610')
assert pins[assets.name+'/titanet_frontend.npz']==dict(bytes=84358,sha256='582f92d2fa2a29be70f6fdc13d67fc1376083ca66cb35401f8335ed85c4115b6')
rollback_source=base64.b64decode(request['rollback_source'],validate=True)
renderer_source=base64.b64decode(request['renderer_source'],validate=True)
assert len(rollback_source)<=131072 and len(renderer_source)<=16384
assert sha(rollback_source)==request['rollback_source_sha256'] and sha(renderer_source)==request['renderer_source_sha256']
# Pinned reviewed pure renderer; no imports outside the standard library.
renderer={'__name__':'_pinned_activation_renderer'}
exec(compile(renderer_source,'<pinned-runtime-launch-renderer>','exec'),renderer)
assert renderer['CAMPAIGN']==str(root)
autostart=home/'.config/autostart/just-peachy.desktop'
assert not autostart.is_symlink() and autostart.stat().st_nlink==1
original_autostart=autostart.read_bytes();original_mode=stat.S_IMODE(autostart.stat().st_mode)
assert original_mode in (420,448,493)
assert sha(original_autostart)==request['autostart_sha256']
assert sha(launcher_raw)==request['launcher_sha256']
candidate_autostart=renderer['render'](rid,sha(policy_raw),'1'*64)['autostart/just-peachy.desktop']
binding=dict(schema='just-peachy.runtime-rollback.v1',release_id=rid,manager_policy_sha256=sha(policy_raw),
 activation_unit=unit+'.service',activation_owner=who,
 autostart=dict(path=str(autostart),original_sha256=sha(original_autostart),candidate_sha256=sha(candidate_autostart),mode=original_mode),
 launcher_sha256=sha(launcher_raw),settings_sha256=request['baseline']['config_pins'][str(home/'JustPeachy/data/settings.json')],
 source_sha256=sha(rollback_source),baseline_owners=request['baseline']['owners'],rollback_attempts=16,reserved_bytes=8*1024**2)
def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
binding_raw=encoded(binding);binding_sha=sha(binding_raw)
launch_files=renderer['render'](rid,sha(policy_raw),binding_sha)
assert launch_files['autostart/just-peachy.desktop']==candidate_autostart
unit_directory=home/'.config/systemd/user'
assert (home/'.config').is_dir() and not (home/'.config').is_symlink()
for parent in (home/'.config/systemd',unit_directory):
 assert not parent.is_symlink() and (not parent.exists() or parent.is_dir())
assert (home/'Desktop').is_dir() and not (home/'Desktop').is_symlink()
for name in launch_files:
 if name.startswith('systemd/'):
  destination=unit_directory/Path(name).name
  assert not destination.exists() and not destination.is_symlink()
frame(dict(type='HELLO',owner=who))
def sync(path):
 fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
def put(path,data,cap=262144):
 assert len(data)<=cap
 with path.open('xb') as f:
  for offset in range(0,len(data),16384):
   block=data[offset:offset+16384]
   if f.write(block)!=len(block):raise OSError('Short publication')
  f.flush();os.fsync(f.fileno())
 sync(path.parent)
 assert path.read_bytes()==data
def guard():
 assert datetime.datetime.now(datetime.timezone.utc)<expiry-datetime.timedelta(seconds=45)
 available=next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
 assert available>=192*1024**2 and shutil.disk_usage(root).free>=5*1024**3
def mkdir(path):
 path.mkdir();sync(path.parent)
guard();mkdir(activation)
put(activation/'OWNER.json',encoded(who),16384)
put(activation/'ADMISSION.json',REQUEST_RAW)
put(activation/'field_runtime_activation_v2.py',rollback_source,131072)
put(activation/'ROLLBACK.json',binding_raw)
for name in ('backup','restore','attempts'):mkdir(activation/name)
for number in range(1,17):mkdir(activation/'attempts'/('%02d'%number))
backups={'autostart.desktop':original_autostart,'start-prototype.sh':launcher_raw}
for row in files:
 backups[Path(row['path']).name]=base64.b64decode(base64.b64encode(row['text'].encode()))
assert len(backups)==6
for label in ('backup','restore'):
 for name,raw in backups.items():put(activation/label/name,raw,65536)
for name,raw in backups.items():assert (activation/'backup'/name).read_bytes()==raw==(activation/'restore'/name).read_bytes()
# Newly created unit parents are explicitly included in the activation directory reserve.
for parent in (home/'.config/systemd',unit_directory):
 if not parent.exists():mkdir(parent)
 assert parent.is_dir() and not parent.is_symlink()
# Arm local rollback before normal Close. Earlier failures leave baseline untouched.
for name,data in launch_files.items():
 if name.startswith('systemd/'):put(unit_directory/Path(name).name,data,16384)
p=command(['systemctl','--user','daemon-reload']);assert p['returncode']==0
put(activation/'ARMED.json',encoded(dict(binding_sha256=binding_sha,owner=who,backups_sha256=sha(encoded({n:sha(v) for n,v in backups.items()})))))
frame(dict(type='BACKUPS_READY',binding=binding,files={n:base64.b64encode(v).decode() for n,v in backups.items()}))
ack=strict(exact(struct.unpack('!I',exact(4))[0]))
assert ack==dict(type='HOST_BACKUPS_VERIFIED',binding_sha256=binding_sha,backups_sha256=sha(encoded({n:sha(v) for n,v in backups.items()})))
# Fresh identity and source pins immediately before the one normal UI Close.
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
for old in request['baseline']['owners']:assert ticks(old['pid'])==old['start_ticks']
for row in files:assert sha(Path(row['path']).read_bytes())==row['sha256']
assert sha(autostart.read_bytes())==sha(original_autostart)
os.environ.update(DISPLAY=':0',XAUTHORITY=str(home/'.Xauthority'),XDG_RUNTIME_DIR='/run/user/1000')
import tkinter as tk
control=tk.Tk();control.withdraw()
try:
 matches=[]
 for name in control.tk.splitlist(control.tk.call('winfo','interps')):
  if name==control.tk.call('tk','appname'):continue
  observed_pid=int(control.tk.call('send',name,'pid'))
  if observed_pid in {r['pid'] for r in request['baseline']['owners']}:
   protocol=str(control.tk.call('send',name,'wm','protocol','.','WM_DELETE_WINDOW'))
   assert protocol and len(protocol)<4096;matches.append((name,observed_pid,protocol))
 assert len(matches)==1
 name,pid,protocol=matches[0]
 put(activation/'CLOSE_INTENT.json',encoded(dict(owner=who,app_pid=pid,protocol_sha256=sha(protocol.encode()))))
 control.tk.call('send','-async',name,protocol)
finally:control.destroy()
close_end=time.monotonic()+20
while any(ticks(v['pid'])==v['start_ticks'] for v in request['baseline']['owners']):
 guard();assert time.monotonic()<close_end;time.sleep(.05)
assert all(p.read_text().strip()=='closed' for p in Path('/proc/asound').glob('card*/pcm*c/sub*/status'))
for lock in (root/'B05_PREVIEW_DISPATCH.lock',home/'JustPeachy/data/xvf-hardware.lock'):
 with lock.open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
available=next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
put(activation/'BASELINE_CLOSED.json',encoded(dict(owners=request['baseline']['owners'],exact_dead=True,available_ram_bytes=available,normal_ui_close=True)))
assert available>=850*1024**2
for destination in (release,profiles,gallery,assets):mkdir(destination)
for name in ('code','control','recordings','launches','backups'):mkdir(release/name)
for slot in policy['allocation']['recording_slots']:mkdir(release/'recordings'/slot)
for slot in policy['allocation']['launch_slots']:mkdir(release/'launches'/slot)
frame(dict(type='READY_FILES',files=pins,baseline_closed=True,available_ram_bytes=available))
for name,row in sorted(pins.items()):
 guard();destination=root/name;h=hashlib.sha256();remaining=row['bytes']
 with destination.open('xb') as f:
  while remaining:
   guard();block=exact(min(16384,remaining))
   if f.write(block)!=len(block):raise OSError('Short installed file write')
   remaining-=len(block);h.update(block)
  f.flush();os.fsync(f.fileno())
 assert h.hexdigest()==row['sha256'] and file_hash(destination,row['bytes'])==row
 sync(destination.parent)
# Exact source gallery copies, including an explicitly empty TitaNet namespace.
assert set(request['galleries'])=={'E0','E1'}
assert sum(v['reserved_bytes'] for v in request['galleries'].values())+4*65536<=2*1024**2
for encoder,document in request['galleries'].items():
 assert encoder in ('E0','E1') and document['schema']=='just-peachy.runtime-gallery-snapshot.v1'
 folder=gallery/encoder;mkdir(folder);people=folder/'people';mkdir(people)
 assert len(document['directories'])<=64 and len(document['files'])<=256
 for rel in sorted(document['directories']):
  if not rel:continue
  path=Path(rel);assert not path.is_absolute() and '..' not in path.parts and path.as_posix()==rel
  mkdir(people/path)
 for rel,row in document['files'].items():
  assert encoder=='E0'
  path=Path(rel);assert not path.is_absolute() and '..' not in path.parts and path.as_posix()==rel
  source=home/'JustPeachy/data/people'/rel
  assert file_hash(source,32*1024**2)==row
  with source.open('rb') as f,(people/rel).open('xb') as g:
   while True:
    guard();block=f.read(16384)
    if not block:break
    if g.write(block)!=len(block):raise OSError('Short gallery snapshot')
   g.flush();os.fsync(g.fileno())
  assert file_hash(people/rel,32*1024**2)==row==file_hash(source,32*1024**2)
  sync((people/rel).parent)
 put(folder/'MANIFEST.json',encoded(document),65536)
# Publish the exact inert code/policy before the new manager constructor executes.
put(release/'control/RELEASE.json',policy_raw,65536)
put(release/'control/MANIFEST.json',manifest_raw,131072)
base=dict(boot_id=boot,install_sha256=request['baseline']['config_pins'][str(home/'JustPeachy/install/current.json')],
 live_config_sha256=request['baseline']['config_pins'][str(home/'JustPeachy/data/live_config.json')],
 display_sha256='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b')
activation_record=dict(schema='just-peachy.runtime-activation.v1',policy_sha256=sha(policy_raw),
 settings_sha256=binding['settings_sha256'],baseline_owners=request['baseline']['owners'],baseline_expected='stopped',baseline=base,launch_slot='launch-01')
put(release/'control/ACTIVATION.json',encoded(activation_record),65536)
put(release/'control/ROLLBACK.json',encoded(dict(schema='just-peachy.runtime-rollback-reference.v1',path=str(activation/'ROLLBACK.json'),sha256=binding_sha)),65536)
for sub in ('bin','systemd','desktop','autostart'):mkdir(profiles/sub)
for name,data in launch_files.items():put(profiles/name,data,65536)
os.chmod(profiles/'bin/launch-profile',0o755)
for name,data in launch_files.items():
 if name.startswith('desktop/'):
  destination=home/'Desktop'/('just-peachy-'+rid+'-'+Path(name).name)
  assert destination.parent.is_dir() and not destination.exists() and not destination.is_symlink()
  put(destination,data,65536);os.chmod(destination,0o755)
# Pure policy validation after complete source pin verification, no model/UI import.
sys.dont_write_bytecode=True;sys.path.insert(0,str(release/'code'))
from field_runtime_policy_v3 import validate
assert validate(policy)==policy
for row in manifest['files']:assert file_hash(release/row['path'],131072)==dict(bytes=row['bytes'],sha256=row['sha256'])
for row in files:assert sha(Path(row['path']).read_bytes())==row['sha256']
guard()
pending=autostart.with_name(autostart.name+'.'+rid+'.pending')
assert sha(autostart.read_bytes())==sha(original_autostart)
put(pending,candidate_autostart,65536);os.chmod(pending,original_mode)
assert sha(autostart.read_bytes())==sha(original_autostart)
os.replace(pending,autostart);sync(autostart.parent)
assert autostart.read_bytes()==candidate_autostart
result=dict(schema='just-peachy.runtime-install-result.v1',owner=who,root=str(release),policy_sha256=sha(policy_raw),
 rollback_binding=binding,files=pins,activation=activation_record,unit_properties=actual,
 baseline_closed_normally=True,all_transferred_files_hash_readback=True,models_executed=False,
 candidate_runtime_accepted=False,capture_started=False,launch_requested=True)
put(activation/'INSTALL_READY.json',encoded(result))
# Final action: manager4 waits for this exact installer to exit before its unit census.
launched=command([str(profiles/'bin/launch-profile'),'--profile','d1-delayed'])
assert launched['returncode']==0
frame(dict(type='INSTALLED',result=result))



