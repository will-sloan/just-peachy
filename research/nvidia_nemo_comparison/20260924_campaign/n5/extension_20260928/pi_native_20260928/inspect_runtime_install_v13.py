"""Inspect current baseline and candidate14 preservation; README_RUNTIME_INSTALL_INSPECTION_V13.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,hashlib,json,os,shutil,sys,time
from pathlib import Path
from datetime import datetime,timezone,timedelta

NATIVE="import os,resource,signal,json,sys,hashlib,subprocess,shutil,fcntl,datetime,base64,re\nfrom pathlib import Path\nos.sched_setaffinity(0,{3})\nfor kind,cap in ((resource.RLIMIT_AS,134217728),(resource.RLIMIT_STACK,1048576),(resource.RLIMIT_FSIZE,0)):\n resource.setrlimit(kind,(cap,cap))\nsignal.alarm(55)\ndef ticks(pid):\n try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])\n except FileNotFoundError:return None\nboot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()\nwho=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)\nprint(json.dumps(dict(utility_owner=who)),file=sys.stderr,flush=True)\nhome=Path.home();root=home/'JustPeachy/research/nemotron-20260928'\ndef identity(v):\n assert type(v) is dict and set(v)=={'pid','start_ticks','boot_id'}\n assert type(v['pid']) is int and v['pid']>0 and type(v['start_ticks']) is int and v['start_ticks']>0\n assert type(v['boot_id']) is str and re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',v['boot_id'])\n return v\ndef strict(raw):\n def pairs(rows):\n  d={}\n  for k,v in rows:\n   assert k not in d;d[k]=v\n  return d\n return json.loads(raw,object_pairs_hook=pairs)\ndef sha(raw):return hashlib.sha256(raw).hexdigest()\nassert os.uname().machine=='aarch64' and 'Compute Module 5' in Path('/proc/device-tree/model').read_text()\nassert int(Path('/sys/class/block/mmcblk0/size').read_text())*512==31268536320\nmem={k.rstrip(':'):int(v.split()[0])*1024 for k,v in (x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines())}\nassert 1700*1024**2<mem['MemTotal']<2100*1024**2 and mem['MemAvailable']>=192*1024**2\nassert shutil.disk_usage(root).free>=5*1024**3\ndef command(argv,env=None):\n p=subprocess.run(argv,capture_output=True,timeout=8,env=env)\n assert len(p.stdout)+len(p.stderr)<=32768\n return dict(returncode=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace'))\nowner_hash=hashlib.sha256();count=0;typed=0;all_ids=set()\nfor v in PRIOR:\n identity(v);observed=ticks(v['pid'])\n assert not(v['boot_id']==boot and observed==v['start_ticks'])\n owner_hash.update(json.dumps([v,observed],sort_keys=True).encode());all_ids.add((v['boot_id'],v['pid'],v['start_ticks']))\nfor p in sorted(root.rglob('*OWNER*.json')):\n assert not p.is_symlink() and p.is_file() and p.stat().st_size<=16384\n raw=p.read_bytes();v=strict(raw);rel=p.relative_to(root).as_posix()\n owner_hash.update(rel.encode()+b'\\0'+hashlib.sha256(raw).digest());count+=1\n if p.name=='OWNERSHIP_CLOSURE.json':\n  assert set(v)=={'borrowed','outer_released','controller_closed','worker_joined','pending_commands'}\n  assert v['outer_released'] is True and type(v['controller_closed']) is bool and type(v['worker_joined']) is bool\n  assert type(v['borrowed']) is dict and set(v['borrowed'])=={'opened','closed'}\n  assert all(type(x) is int and 0<=x<=1 for x in v['borrowed'].values()) and v['borrowed']['closed']<=v['borrowed']['opened']\n  assert v['pending_commands'] is None or type(v['pending_commands']) is int and v['pending_commands']>=0\n  typed+=1;continue\n if 'owner' in v:\n  assert rel in NESTED and set(v)=={'owner','policy_sha256','slot','utc','purpose'}\n  expected=NESTED[rel]\n  assert sha(raw)==expected['sha256'] and v['policy_sha256']==expected['policy_sha256'] and v['purpose']==expected['purpose'] and v['slot']==expected['slot']\n  stamp=datetime.datetime.fromisoformat(v['utc']);assert stamp.tzinfo is not None\n  v=v['owner']\n elif set(v)!={'pid','start_ticks','boot_id'}:\n  assert rel in HISTORICAL and json.dumps(v,sort_keys=True,separators=(',',':'))==json.dumps(HISTORICAL[rel],sort_keys=True,separators=(',',':')), ('Unrecognized completed owner',rel,sorted(v))\n  v={k:v[k] for k in ('pid','start_ticks','boot_id')}\n identity(v);observed=ticks(v['pid'])\n assert not(v['boot_id']==boot and observed==v['start_ticks'])\n all_ids.add((v['boot_id'],v['pid'],v['start_ticks']))\nunits=command(['systemctl','--user','list-units','--state=active,activating,deactivating','--plain','--no-legend','jp-*'])\nassert units['returncode']==0 and not units['stdout'].strip()\ncapture={}\nfor p in sorted(Path('/proc/asound').glob('card*/pcm*c/sub*/status')):\n text=p.read_text();assert len(text)<=4096;capture[str(p)]=text.strip()\nassert capture and all(v=='closed' for v in capture.values())\nleases=[]\nfor p in (root/'B05_PREVIEW_DISPATCH.lock',home/'JustPeachy/data/xvf-hardware.lock'):\n with p.open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)\n leases.append(str(p))\nfiles=[]\nfor rel in ('JustPeachy/install/current.json','JustPeachy/data/live_config.json','JustPeachy/data/settings.json','.config/kanshi/config'):\n p=home/rel;assert p.is_file() and not p.is_symlink() and p.stat().st_size<=65536\n raw=p.read_bytes();files.append(dict(path=str(p),bytes=len(raw),sha256=sha(raw),text=raw.decode()))\nsettings=json.loads((home/'JustPeachy/data/settings.json').read_bytes())\nassert settings.get('auto_start_listening') is False\nassert sha((home/'.config/kanshi/config').read_bytes())=='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b'\nprocesses=[]\nfor p in Path('/proc').iterdir():\n if not p.name.isdigit() or int(p.name)==who['pid']:continue\n try:\n  with (p/'cmdline').open('rb') as f:raw=f.read(8193)\n except (FileNotFoundError,PermissionError,ProcessLookupError):continue\n if b'JustPeachy' not in raw and b'just-peachy' not in raw:continue\n assert len(raw)<=8192 and len(processes)<64\n start=ticks(int(p.name))\n if start is not None:processes.append(dict(pid=int(p.name),start_ticks=start,boot_id=boot,cmdline=raw.replace(b'\\0',b' ').decode(errors='replace')))\nstartup=[];candidates=set((home/'.config/autostart').glob('*.desktop'))\ncandidates|=set((home/'.config/systemd/user').glob('*peach*'))\ncandidates|={home/'.config/labwc/autostart',home/'.config/wayfire.ini',home/'.config/lxsession/LXDE-pi/autostart'}\ntotal=0\nfor p in sorted(candidates):\n if not p.exists() or p.is_dir():continue\n assert not p.is_symlink() and p.stat().st_size<=65536\n raw=p.read_bytes();total+=len(raw);assert total<=65536\n startup.append(dict(path=str(p),bytes=len(raw),sha256=sha(raw),base64=base64.b64encode(raw).decode()))\n\ndef file_hash(path,limit):\n before=path.lstat()\n assert not path.is_symlink() and path.is_file() and before.st_size<=limit and before.st_nlink==1\n h=hashlib.sha256();count=0\n with path.open('rb') as f:\n  while True:\n   block=f.read(16384)\n   if not block:break\n   h.update(block);count+=len(block)\n after=path.lstat()\n assert count==before.st_size and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)\n return dict(bytes=count,sha256=h.hexdigest())\ntitanet_assets=[]\nfor name in ('titanet_manifest.json','titanet_embedding.onnx','titanet_frontend.npz'):\n for p in (home/'JustPeachy').rglob(name):\n  assert len(titanet_assets)<32\n  if p.is_symlink():\n   titanet_assets.append(dict(path=str(p),symlink=True));continue\n  asset_pin=file_hash(p,90*1024**2)\n  asset_pin['path']=str(p);titanet_assets.append(asset_pin)\ngalleries=[]\ngallery_roots=[home/'JustPeachy/data/people']\nspaces=home/'JustPeachy/data/embedding_spaces'\nif spaces.exists():\n entries=list(spaces.iterdir());assert len(entries)<=32 and not spaces.is_symlink()\n gallery_roots += [p/'people' for p in entries if p.is_dir() and not p.is_symlink()]\nfor folder in gallery_roots:\n row=dict(root=str(folder),exists=folder.exists(),files={},directories=[])\n if folder.exists():\n  for base,dirs,names in os.walk(folder,followlinks=False):\n   p=Path(base);assert not p.is_symlink()\n   rel=p.relative_to(folder).as_posix();row['directories'].append('' if rel=='.' else rel)\n   assert len(row['directories'])<=64\n   for name in names:\n    q=p/name;row['files'][q.relative_to(folder).as_posix()]=file_hash(q,32*1024**2)\n    assert len(row['files'])<=256\n  row['bytes']=sum(p['bytes'] for p in row['files'].values())\n  row['reserved_bytes']=row['bytes']+65536*len(row['directories'])\n  assert row['reserved_bytes']<=128*1024**2\n galleries.append(row)\nlauncher=home/'JustPeachy/start-prototype.sh'\nlauncher_raw=launcher.read_bytes()\nassert not launcher.is_symlink() and len(launcher_raw)<=65536\nlauncher_backup=dict(path=str(launcher),bytes=len(launcher_raw),sha256=sha(launcher_raw),base64=base64.b64encode(launcher_raw).decode())\n\nenv=dict(os.environ,XDG_RUNTIME_DIR='/run/user/1000',WAYLAND_DISPLAY='wayland-0')\ndisplay=command(['wlr-randr'],env)\nassert display['returncode']==0 and 'Transform: 270' in display['stdout'] and 'Enabled: yes' in display['stdout']\nvalue=dict(schema='just-peachy.runtime-install-inspection.v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),utility_owner=who,\n boot_id=boot,owner_paths_read=count,prior_identities_checked=len(PRIOR),unique_recorded_identities=len(all_ids),typed_nonidentity_closures=typed,\n owner_inventory_sha256=owner_hash.hexdigest(),prior_closure_sha256=PRIOR_SHA,\n titanet_assets=titanet_assets,galleries=galleries,launcher_backup=launcher_backup,files=files,current_project_processes=processes,startup_files=startup,units=units,capture=capture,free_leases=leases,display=display,\n sound_cards=Path('/proc/asound/cards').read_text(),available_ram_bytes=mem['MemAvailable'],target_free_bytes=shutil.disk_usage(root).free,\n target_bytes=int(subprocess.check_output(['du','-sb',str(root)],text=True,timeout=8).split()[0]),native_writes=False,capture_started=False)\n# Private exact readback of the installed ReDimNet gallery metadata; no model or capture.\nimport base64\nvalue['gallery_metadata']={}\nfor gallery in galleries:\n if gallery['root']!=str(home/'JustPeachy/data/people'):continue\n for name,pin in gallery['files'].items():\n  if not name.endswith('/person.json'):continue\n  path=Path(gallery['root'])/name\n  assert path.is_file() and not path.is_symlink() and path.stat().st_nlink==1 and pin['bytes']<=65536\n  raw=path.read_bytes();assert len(raw)==pin['bytes'] and sha(raw)==pin['sha256']\n  value['gallery_metadata'][name]=dict(pin=pin,base64=base64.b64encode(raw).decode())\n assert sum(r['pin']['bytes'] for r in value['gallery_metadata'].values())<=65536\n\nraw=json.dumps(value)\nassert len(raw.encode())<=262144\nprint(raw,flush=True)\n"

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('private','local','prior-closure','previous-inspection','scope','output'):
        ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    def put(name,raw):
        with (a.output/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if (a.output/name).read_bytes()!=raw:raise IOError('Exact inspection readback')
    def save(name,value):put(name,(json.dumps(value,sort_keys=True,indent=2)+'\n').encode())
    save('REGISTERED_OWNER.json',owner)
    scope=json.loads(a.scope.read_bytes());last_guard=[0.]
    def guard():
        now=datetime.now(timezone.utc)
        if now>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Host scope expired')
        if now>=datetime(2026,10,2,14,14,20,tzinfo=timezone.utc):raise TimeoutError('User deadline')
        if time.monotonic()-last_guard[0]<2:return
        last_guard[0]=time.monotonic()
        if sum(p.stat().st_size for p in a.scope.parent.rglob('*') if p.is_file())+1048576>scope['maximum_bytes']:raise ValueError('Full metadata reserve')
        if shutil.disk_usage('C:/').free<50*1024**3 or shutil.disk_usage('G:/').free<75*1024**3:raise RuntimeError('Host floors')
    guard()
    from field_runtime_host_precheck_v2 import inspect
    pre,details=inspect(a.local,a.private,current_owner=owner,deadline=time.monotonic()+100,guard=guard)
    save('HOST_PRECHECK.json',pre);save('HOST_PRECHECK_DETAILS.json',details)
    if pre['alive_owners']:raise RuntimeError('Other live host owner; leave it untouched')
    prior_raw=a.prior_closure.read_bytes();old=json.loads(prior_raw);identities={}
    for row in old['owners']+old['additional_registered_owners']:
        v={k:row['owner'][k] for k in ('pid','start_ticks','boot_id')};identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    v=old['utility_owner'];identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    previous=json.loads((a.previous_inspection/'NATIVE_OWNER.json').read_bytes())
    from field_local_manager_owners_v1 import identity
    identity(previous);identities[(previous['boot_id'],previous['pid'],previous['start_ticks'])]=previous
    later=list(a.previous_inspection.parent.glob('install-inspection-v*/NATIVE_OWNER.json'))+list(a.private.glob('runtime-titanet-v*-install/NATIVE_OWNER.json'))+list(a.private.glob('runtime-titanet-v*-install/CLOSURE_OWNER.json'))
    if len(later)>16:raise ValueError('Bounded explicit inspection continuation owners')
    for path in later:
        v=identity(json.loads(path.read_bytes()))
        identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    assert len(identities)<=1024
    historical={row['path'].split('/nemotron-20260928/',1)[1]:row['owner'] for row in old['owners']
        if set(row['owner'])!={'pid','start_ticks','boot_id'}}
    nested={}
    for row in old['owners']:
        rel=Path(row['path']).as_posix().split('/nemotron-20260928/',1)[-1]
        if rel.startswith('field-local-release-v') and '/launches/' in rel:
            mirrored=a.private/('field-local-release-v1-admission' if rel.startswith('field-local-release-v1/') else 'field-local-release-v2-admission')
    # Exact immutable historical envelope pins from the selected collector.
    nested={
      'field-local-release-v1/launches/launch-01/OWNER.json':dict(sha256='6fe6f5b378e2ef6c66f89b8cf32cb75c93f7f7216a4e1454d1bacb2030707fbe',policy_sha256='d8600a564dc41641ab799b1f64dc977a9ef719c8c3a45847d00cd6a5023dd454',slot='launches/launch-01',purpose='METADATA_QUALIFICATION_ONLY'),
      'field-local-release-v1/launches/launch-02/OWNER.json':dict(sha256='2c3dbd0f2c4c6a9e80499346a4fac8a306865ea759849786993850fe4e65bc15',policy_sha256='d8600a564dc41641ab799b1f64dc977a9ef719c8c3a45847d00cd6a5023dd454',slot='launches/launch-02',purpose='METADATA_QUALIFICATION_ONLY')}
    collector=(Path(__file__).parent/'collect_native_closure_v19.py').read_text(encoding='utf-8')
    # Extract only its literal native source constant; no collector execution.
    constants=[n.value for n in ast.walk(ast.parse(collector)) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'NEW_NESTED=' in n.value]
    if len(constants)!=1:raise ValueError('Selected historical collector boundary')
    native_tree=ast.parse(constants[0])
    assignment=next(n for n in native_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NEW_NESTED' for t in n.targets))
    for path,row in ast.literal_eval(assignment.value).items():
        nested[path]={**row,'policy_sha256':'f39a8b7dbedbebed1492687d42d5648ac033dbba0d02a4a46537175e1fa40d9c'}
    # Bind the complete already-preserved final manager and every prior nested launch.
    installed=a.private/'field-runtime-v14-install';preserved=a.private/'field-runtime-v14-preservation-v5'
    admission=json.loads((installed/'ADMISSION.json').read_bytes())
    for rel,row in admission['nested'].items():
        if rel in nested and nested[rel]!=row:raise ValueError('Historical owner mismatch')
        nested[rel]=row
    backup=json.loads((preserved/'BACKUP.json').read_bytes())
    if not backup['manager_exact_dead'] or not backup['native_utility_exact_absent']:raise ValueError('Complete previous preservation')
    raw_policy=(installed/'RELEASE.json').read_bytes();policy=json.loads(raw_policy);ph=hashlib.sha256(raw_policy).hexdigest()
    if ph!=json.loads((installed/'RESULT.json').read_bytes())['policy_sha256']:raise ValueError('Actual preserved policy')
    for path in sorted((preserved/'tree/field-runtime-v14/launches').glob('*/OWNER.json')):
        raw=path.read_bytes();row=json.loads(raw);slot=path.parent.name
        if slot not in policy['allocation']['launch_slots'] or set(row)!={'owner','policy_sha256','slot','utc','purpose'}:raise ValueError('Exact allocated nested launch')
        if row['slot']!='launches/'+slot or row['policy_sha256']!=ph or row['purpose'] not in ('USER_RUNTIME_MANAGER','USER_RUNTIME_STAGE','USER_RUNTIME_GATE','USER_RUNTIME_COPY'):raise ValueError('Exact actual launch role')
        rel='field-runtime-v14/'+row['slot']+'/OWNER.json'
        nested[rel]=dict(sha256=hashlib.sha256(raw).hexdigest(),policy_sha256=ph,slot=row['slot'],purpose=row['purpose'])
        v=identity(row['owner']);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    for path in list(a.scope.parent.glob('candidate*/NATIVE_OWNER.json'))+list(a.private.glob('field-runtime-v*-preservation*/NATIVE_OWNER.json'))+list(a.private.glob('field-runtime-v*-offload*/NATIVE_OWNER.json')):
        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    for path in a.private.glob('field-runtime-v*-install/NATIVE_CLOSURE.json'):
        proof=json.loads(path.read_bytes())
        if not proof['exact_owner_dead'] or not proof['utility_pid_absent']:raise ValueError('Installer exact closure')
        for key in ('owner','utility_owner'):
            v=identity(proof[key]);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    assert len(identities)<=1024
    guard()
    if datetime.now(timezone.utc)+timedelta(seconds=90)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Complete read-only closure reserve')
    code='PRIOR='+repr(list(identities.values()))+'\nPRIOR_SHA='+repr(hashlib.sha256(prior_raw).hexdigest())+'\nNESTED='+repr(nested)+'\nHISTORICAL='+repr(historical)+'\n'+NATIVE
    compile(code,'<runtime-install-inspection>','exec')
    save('READONLY_ADMISSION.json',dict(issued_utc=datetime.now(timezone.utc).isoformat(),expires_utc=scope['expires_utc'],
        maximum_seconds=70,maximum_output_bytes=262144,native_writes=False,capture=False,precheck_sha256=hashlib.sha256((a.output/'HOST_PRECHECK.json').read_bytes()).hexdigest(),source_sha256=hashlib.sha256(code.encode()).hexdigest()))
    from field_operator_broker_host_v2 import ssh_phase,process_phase
    from dispatch_b01_stack_v2 import SSH
    result=ssh_phase(['python3','-u','-B','-'],payload=code.encode(),timeout=65,maximum=262144)
    out=result.pop('stdout');err=result.pop('stderr')
    put('STDOUT.bin',out);put('STDERR.bin',err);save('PHASE.json',result)
    native_owner=None
    if err.splitlines():
        native_owner=json.loads(err.splitlines()[0])['utility_owner'];save('NATIVE_OWNER.json',native_owner)
    if native_owner is None:raise RuntimeError('Missing early native identity; raw failure preserved')
    closed=process_phase(SSH+['test ! -e /proc/'+str(native_owner['pid'])],timeout=10,maximum=16384)
    cout=closed.pop('stdout');cerr=closed.pop('stderr')
    put('CLOSURE_STDOUT.bin',cout);put('CLOSURE_STDERR.bin',cerr);save('CLOSURE_PHASE.json',closed)
    if closed['returncode'] or closed['fault'] is not None or not closed['readers_joined'] or not closed['ssh_reaped']:raise RuntimeError('Exact inspector closure not certified')
    save('NATIVE_CLOSURE.json',dict(owner=native_owner,exact_pid_absent=True,natural_returncode=result['returncode']))
    if result['returncode'] or result['fault'] is not None or not result['readers_joined'] or not result['ssh_reaped']:
        raise RuntimeError('Preserved native read-only failure; inspector absence independently checked')
    value=json.loads(out)
    if value['utility_owner']!=native_owner or len(err.splitlines())!=1:raise ValueError('Actual early identity')
    value['utility_pid_absent_after_ssh']=True
    value['prior_failed_inspector_checked_dead']=previous
    save('RESULT.json',value)
    print(json.dumps({k:value[k] for k in ('utc','boot_id','owner_paths_read','prior_identities_checked','available_ram_bytes','target_free_bytes','target_bytes','native_writes')}))


if __name__=='__main__':main()
