"""Read current installation facts without changing the Pi; README_RUNTIME_FAILURE_PRESERVATION_V9.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,hashlib,json,os,shutil,sys,time
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone,timedelta

NATIVE="import os,resource,signal,json,sys,hashlib,subprocess,shutil,fcntl,datetime,base64,re\nfrom pathlib import Path,PurePosixPath\nos.sched_setaffinity(0,{3})\nfor kind,cap in ((resource.RLIMIT_AS,134217728),(resource.RLIMIT_STACK,1048576),(resource.RLIMIT_FSIZE,0)):\n resource.setrlimit(kind,(cap,cap))\nsignal.alarm(150)\ndef ticks(pid):\n try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])\n except FileNotFoundError:return None\nboot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()\nwho=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)\nprint(json.dumps(dict(utility_owner=who)),file=sys.stderr,flush=True)\nhome=Path.home();root=home/'JustPeachy/research/nemotron-20260928'\npolicy_path=root/RID/'control/RELEASE.json'\npolicy_raw=policy_path.read_bytes()\nassert len(policy_raw)<=65536 and hashlib.sha256(policy_raw).hexdigest()==POLICY_SHA\nruntime_policy=json.loads(policy_raw)\nassert runtime_policy['release_id']==RID and runtime_policy['manager_root']==str(root/RID)\nunit='jp-'+RID+'.service'\ndef unit_state(name):\n proc=subprocess.run(['systemctl','--user','show',name,'-p','MainPID','-p','ActiveState','-p','SubState','-p','LoadState','-p','ExecMainStatus'],capture_output=True,timeout=5)\n assert proc.returncode in (0,1) and len(proc.stdout)<8192 and len(proc.stderr)<4096\n return dict(l.split('=',1) for l in proc.stdout.decode().splitlines())\ncandidate_unit=unit_state(unit);live_manager=int(candidate_unit['MainPID']);alive_candidate=[]\n\ndef identity(v):\n assert type(v) is dict and set(v)=={'pid','start_ticks','boot_id'}\n assert type(v['pid']) is int and v['pid']>0 and type(v['start_ticks']) is int and v['start_ticks']>0\n assert type(v['boot_id']) is str and re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',v['boot_id'])\n return v\ndef strict(raw):\n def pairs(rows):\n  d={}\n  for k,v in rows:\n   assert k not in d;d[k]=v\n  return d\n return json.loads(raw,object_pairs_hook=pairs)\ndef sha(raw):return hashlib.sha256(raw).hexdigest()\nassert os.uname().machine=='aarch64' and 'Compute Module 5' in Path('/proc/device-tree/model').read_text()\nassert int(Path('/sys/class/block/mmcblk0/size').read_text())*512==31268536320\nmem={k.rstrip(':'):int(v.split()[0])*1024 for k,v in (x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines())}\nassert 1700*1024**2<mem['MemTotal']<2100*1024**2 and mem['MemAvailable']>=192*1024**2\nassert shutil.disk_usage(root).free>=5*1024**3\ndef command(argv,env=None):\n p=subprocess.run(argv,capture_output=True,timeout=8,env=env)\n assert len(p.stdout)+len(p.stderr)<=32768\n return dict(returncode=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace'))\n\ndef parent_pid(pid):\n try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1])\n except FileNotFoundError:return None\ncurrent_operations={}\nruntime_helpers={}\nfor slot in runtime_policy['allocation']['launch_slots']:\n path=root/RID/'launches'/slot/'OWNER.json'\n if not path.exists():continue\n item=strict(path.read_bytes())\n assert set(item)=={'owner','policy_sha256','slot','utc','purpose'} and item['policy_sha256']==POLICY_SHA and item['slot']=='launches/'+slot\n identity(item['owner'])\n if item['purpose'] in ('USER_RUNTIME_STAGE','USER_RUNTIME_GATE','USER_RUNTIME_COPY'):\n  runtime_helpers[item['owner']['pid']]=item\nfor index,slot in enumerate(runtime_policy['allocation']['recording_slots']):\n path=root/RID/'recordings'/slot/'RESERVED.json'\n if not path.exists():continue\n receipt=strict(path.read_bytes());op=receipt['operation']\n source=Path(op['root'])\n assert str(source)==runtime_policy['recording_roots'][index] and source.parent==root\n assert op['owner']==dict(pid=live_manager,start_ticks=ticks(live_manager),boot_id=boot)\n assert op['slot']==slot and op['profile'] in runtime_policy['profiles']\n selected_profile=runtime_policy['profiles'][op['profile']]\n assert selected_profile['available'] is True and op['profile_manifest_sha256']==selected_profile['manifest_sha256']\n if source.exists():\n  bp=strict((source/'RELEASE.json').read_bytes())\n  assert bp['runtime_policy_sha256']==POLICY_SHA and bp['runtime_root']==str(root/RID)\n  assert bp['runtime_operation_sha256']==sha(json.dumps(op,sort_keys=True,separators=(',',':'),allow_nan=False).encode())\n  current_operations[source.name]=dict(operation=op,unit=unit_state('jp-'+source.name+'.service'))\nallowed_live=[]\ndef allow_live(rel,v):\n if rel.startswith(RID+'/launches/') and v['pid']==live_manager:\n  assert candidate_unit['ActiveState']=='active'\n  alive_candidate.append(v);return\n if rel.startswith(RID+'/launches/') and v['pid'] in runtime_helpers:\n  assert runtime_helpers[v['pid']]['owner']==v and parent_pid(v['pid'])==live_manager\n  allowed_live.append(dict(path=rel,owner=v,role='manager_helper'));return\n parts=rel.split('/',1)\n assert len(parts)==2 and parts[0] in current_operations,('Unexpected current owner',rel)\n state=current_operations[parts[0]]['unit'];sub=parts[1]\n direct={'broker/STAGE_OWNER.json','broker/GATE_OWNER.json','broker/OWNER.json',\n  'recordings/slot-01/control/OWNER.json','recordings/slot-01/control/REGISTERED_OWNER.json',\n  'recordings/slot-01/parent_control/OWNER.json','recordings/slot-01/source/CHILD_OWNER.json'}\n assert sub in direct\n if sub in ('broker/STAGE_OWNER.json','broker/GATE_OWNER.json'):\n  assert v['pid'] in runtime_helpers and runtime_helpers[v['pid']]['owner']==v and parent_pid(v['pid'])==live_manager\n else:\n  main=int(state['MainPID']);assert state['ActiveState']=='active' and main>0\n  if sub=='broker/OWNER.json':assert v['pid']==main\n  else:\n   pid=v['pid'];ancestors=[]\n   for i in range(5):\n    pid=parent_pid(pid)\n    if pid is None:break\n    ancestors.append(pid)\n    if pid==main:break\n   assert main in ancestors\n  cmd=Path('/proc',str(v['pid']),'cmdline').read_bytes()\n  assert str(root/parts[0]).encode() in cmd and len(cmd)<=8192\n allowed_live.append(dict(path=rel,owner=v,role=sub))\n\nowner_hash=hashlib.sha256();count=0;typed=0;all_ids=set()\nfor v in PRIOR:\n identity(v);observed=ticks(v['pid'])\n assert not(v['boot_id']==boot and observed==v['start_ticks'])\n owner_hash.update(json.dumps([v,observed],sort_keys=True).encode());all_ids.add((v['boot_id'],v['pid'],v['start_ticks']))\nfor p in sorted(root.rglob('*OWNER*.json')):\n assert not p.is_symlink() and p.is_file() and p.stat().st_size<=16384\n raw=p.read_bytes();v=strict(raw);rel=p.relative_to(root).as_posix()\n owner_hash.update(rel.encode()+b'\\0'+hashlib.sha256(raw).digest());count+=1\n if p.name=='OWNERSHIP_CLOSURE.json':\n  assert set(v)=={'borrowed','outer_released','controller_closed','worker_joined','pending_commands'}\n  assert v['outer_released'] is True and type(v['controller_closed']) is bool and type(v['worker_joined']) is bool\n  assert type(v['borrowed']) is dict and set(v['borrowed'])=={'opened','closed'}\n  assert all(type(x) is int and 0<=x<=1 for x in v['borrowed'].values()) and v['borrowed']['closed']<=v['borrowed']['opened']\n  assert v['pending_commands'] is None or type(v['pending_commands']) is int and v['pending_commands']>=0\n  typed+=1;continue\n if 'owner' in v and rel.startswith(RID+'/launches/'):\n  assert set(v)=={'owner','policy_sha256','slot','utc','purpose'}\n  assert v['policy_sha256']==POLICY_SHA and v['slot'] in {'launches/'+s for s in runtime_policy['allocation']['launch_slots']}\n  assert rel==RID+'/'+v['slot']+'/OWNER.json'\n  assert v['purpose'] in ('USER_RUNTIME_MANAGER','USER_RUNTIME_STAGE','USER_RUNTIME_GATE','USER_RUNTIME_COPY')\n  assert datetime.datetime.fromisoformat(v['utc']).tzinfo is not None\n  v=v['owner']\n elif 'owner' in v:\n  assert rel in NESTED and set(v)=={'owner','policy_sha256','slot','utc','purpose'}\n  expected=NESTED[rel]\n  assert sha(raw)==expected['sha256'] and v['policy_sha256']==expected['policy_sha256'] and v['purpose']==expected['purpose'] and v['slot']==expected['slot']\n  stamp=datetime.datetime.fromisoformat(v['utc']);assert stamp.tzinfo is not None\n  v=v['owner']\n elif set(v)!={'pid','start_ticks','boot_id'}:\n  assert rel in HISTORICAL and json.dumps(v,sort_keys=True,separators=(',',':'))==json.dumps(HISTORICAL[rel],sort_keys=True,separators=(',',':')), ('Unrecognized completed owner',rel,sorted(v))\n  v={k:v[k] for k in ('pid','start_ticks','boot_id')}\n identity(v);observed=ticks(v['pid'])\n if v['boot_id']==boot and observed==v['start_ticks']:\n  allow_live(rel,v)\n all_ids.add((v['boot_id'],v['pid'],v['start_ticks']))\nunits=command(['systemctl','--user','list-units','--state=active,activating,deactivating','--plain','--no-legend','jp-*'])\nassert units['returncode']==0 and {l.split()[0] for l in units['stdout'].splitlines() if l.strip()}<={unit,'jp-rollback-'+RID+'.service'}|{'jp-'+n+'.service' for n in current_operations}\ncapture={}\nfor p in sorted(Path('/proc/asound').glob('card*/pcm*c/sub*/status')):\n text=p.read_text();assert len(text)<=4096;capture[str(p)]=text.strip()\nassert capture and all(v=='closed' for v in capture.values())\nleases=[]\nfor p in (root/'B05_PREVIEW_DISPATCH.lock',home/'JustPeachy/data/xvf-hardware.lock'):\n with p.open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)\n leases.append(str(p))\nfiles=[]\nfor rel in ('JustPeachy/install/current.json','JustPeachy/data/live_config.json','JustPeachy/data/settings.json','.config/kanshi/config'):\n p=home/rel;assert p.is_file() and not p.is_symlink() and p.stat().st_size<=65536\n raw=p.read_bytes();files.append(dict(path=str(p),bytes=len(raw),sha256=sha(raw),text=raw.decode()))\nsettings=json.loads((home/'JustPeachy/data/settings.json').read_bytes())\nassert settings.get('auto_start_listening') is False\nassert sha((home/'.config/kanshi/config').read_bytes())=='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b'\nprocesses=[]\nfor p in Path('/proc').iterdir():\n if not p.name.isdigit() or int(p.name)==who['pid']:continue\n try:\n  with (p/'cmdline').open('rb') as f:raw=f.read(8193)\n except (FileNotFoundError,PermissionError,ProcessLookupError):continue\n if b'JustPeachy' not in raw and b'just-peachy' not in raw:continue\n assert len(raw)<=8192 and len(processes)<64\n start=ticks(int(p.name))\n if start is not None:processes.append(dict(pid=int(p.name),start_ticks=start,boot_id=boot,cmdline=raw.replace(b'\\0',b' ').decode(errors='replace')))\nstartup=[];candidates=set((home/'.config/autostart').glob('*.desktop'))\ncandidates|=set((home/'.config/systemd/user').glob('*peach*'))\ncandidates|={home/'.config/labwc/autostart',home/'.config/wayfire.ini',home/'.config/lxsession/LXDE-pi/autostart'}\ntotal=0\nfor p in sorted(candidates):\n if not p.exists() or p.is_dir():continue\n assert not p.is_symlink() and p.stat().st_size<=65536\n raw=p.read_bytes();total+=len(raw);assert total<=65536\n startup.append(dict(path=str(p),bytes=len(raw),sha256=sha(raw),base64=base64.b64encode(raw).decode()))\n\ndef file_hash(path,limit):\n before=path.lstat()\n assert not path.is_symlink() and path.is_file() and before.st_size<=limit and before.st_nlink==1\n h=hashlib.sha256();count=0\n with path.open('rb') as f:\n  while True:\n   block=f.read(16384)\n   if not block:break\n   h.update(block);count+=len(block)\n after=path.lstat()\n assert count==before.st_size and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)\n return dict(bytes=count,sha256=h.hexdigest())\ntitanet_assets=[]\nfor name in ('titanet_manifest.json','titanet_embedding.onnx','titanet_frontend.npz'):\n for p in (home/'JustPeachy').rglob(name):\n  assert len(titanet_assets)<32\n  if p.is_symlink():\n   titanet_assets.append(dict(path=str(p),symlink=True));continue\n  asset_pin=file_hash(p,90*1024**2)\n  asset_pin['path']=str(p);titanet_assets.append(asset_pin)\ngalleries=[]\ngallery_roots=[home/'JustPeachy/data/people']\nspaces=home/'JustPeachy/data/embedding_spaces'\nif spaces.exists():\n entries=list(spaces.iterdir());assert len(entries)<=32 and not spaces.is_symlink()\n gallery_roots += [p/'people' for p in entries if p.is_dir() and not p.is_symlink()]\nfor folder in gallery_roots:\n row=dict(root=str(folder),exists=folder.exists(),files={},directories=[])\n if folder.exists():\n  for base,dirs,names in os.walk(folder,followlinks=False):\n   p=Path(base);assert not p.is_symlink()\n   rel=p.relative_to(folder).as_posix();row['directories'].append('' if rel=='.' else rel)\n   assert len(row['directories'])<=64\n   for name in names:\n    q=p/name;row['files'][q.relative_to(folder).as_posix()]=file_hash(q,32*1024**2)\n    assert len(row['files'])<=256\n  row['bytes']=sum(p['bytes'] for p in row['files'].values())\n  row['reserved_bytes']=row['bytes']+65536*len(row['directories'])\n  assert row['reserved_bytes']<=128*1024**2\n galleries.append(row)\nlauncher=home/'JustPeachy/start-prototype.sh'\nlauncher_raw=launcher.read_bytes()\nassert not launcher.is_symlink() and len(launcher_raw)<=65536\nlauncher_backup=dict(path=str(launcher),bytes=len(launcher_raw),sha256=sha(launcher_raw),base64=base64.b64encode(launcher_raw).decode())\n\nenv=dict(os.environ,XDG_RUNTIME_DIR='/run/user/1000',WAYLAND_DISPLAY='wayland-0')\ndisplay=command(['wlr-randr'],env)\nassert display['returncode']==0 and 'Transform: 270' in display['stdout'] and 'Enabled: yes' in display['stdout']\nvalue=dict(schema='just-peachy.runtime-install-inspection.v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),utility_owner=who,\n boot_id=boot,owner_paths_read=count,prior_identities_checked=len(PRIOR),unique_recorded_identities=len(all_ids),typed_nonidentity_closures=typed,\n owner_inventory_sha256=owner_hash.hexdigest(),prior_closure_sha256=PRIOR_SHA,\n titanet_assets=titanet_assets,galleries=galleries,launcher_backup=launcher_backup,files=files,current_project_processes=processes,startup_files=startup,units=units,capture=capture,free_leases=leases,display=display,\n sound_cards=Path('/proc/asound/cards').read_text(),available_ram_bytes=mem['MemAvailable'],target_free_bytes=shutil.disk_usage(root).free,\n target_bytes=int(subprocess.check_output(['du','-sb',str(root)],text=True,timeout=8).split()[0]),native_writes=False,capture_started=False)\n\nvalue['candidate_unit']=candidate_unit\nvalue['live_manager_owners']=alive_candidate\nvalue['policy_sha256']=POLICY_SHA\nvalue['candidate_ui']=None\nvalue['manager_log']=command(['journalctl','--user','-u',unit,'--no-pager','-n','25','-o','cat'])\nvalue['status']='CANDIDATE_IDLE_VISIBLE' if value['candidate_ui'] and value['candidate_ui']['viewable'] else 'CANDIDATE_NOT_VISIBLE_REVIEW_REQUIRED'\n\n\nvalue['active_recorded_owners']=allowed_live\nvalue['recording_controls']={}\nfor slot in runtime_policy['allocation']['recording_slots']:\n folder=root/RID/'recordings'/slot\n for path in folder.glob('*.json'):\n  assert path.stat().st_size<=65536\n  value['recording_controls'][slot+'/'+path.name]=strict(path.read_bytes())\nvalue['operation_receipts']={}\nfor name in current_operations:\n folder=root/name\n for rel in ('broker/RESULT.json','broker/GATE_RESULT.json','broker/ENVELOPE.json'):\n  path=folder/rel\n  if path.exists():\n   assert path.stat().st_size<=65536\n   value['operation_receipts'][name+'/'+rel]=strict(path.read_bytes())\nvalue['status']='CURRENT_OPERATION_INSPECTED'\n\n\n\nimport time,zlib\nassert candidate_unit['ActiveState']=='active' and candidate_unit['SubState']=='running'\nassert len(alive_candidate)==1 and not allowed_live\nassert 1<=len(current_operations)<=len(runtime_policy['allocation']['recording_slots'])\nfailed=[]\nfor name,operation in current_operations.items():\n result=strict((root/name/'broker/GATE_RESULT.json').read_bytes())\n assert type(result['logical_success']) is bool and result['capture_closed'] is True\n assert result['worker_exact_dead'] is True and result['pipe_closed'] is True\n if result['logical_success'] is False:failed.append((name,result))\nassert len(failed)==1,'One preserved failed operation required'\nsource_name,gate_result=failed[0]\nmanager_owner=alive_candidate[0]\nassert ticks(manager_owner['pid'])==manager_owner['start_ticks']\nprint(json.dumps(dict(preservation_phase='FAILED_RUNTIME_STOP_REQUEST',owner=manager_owner)),file=sys.stderr,flush=True)\nstopped=command(['systemctl','--user','stop','--no-block',unit])\nassert stopped['returncode']==0\nuntil=time.monotonic()+47\nwhile ticks(manager_owner['pid'])==manager_owner['start_ticks']:\n if time.monotonic()>=until:raise TimeoutError('Failed manager did not close within its service Stop bound')\n time.sleep(.05)\nfinal_service=unit_state(unit)\nassert final_service['MainPID']=='0' and final_service['ActiveState'] in ('inactive','failed')\nfor p in Path('/proc/asound').glob('card*/pcm*c/sub*/status'):assert p.read_text().strip()=='closed'\nprint(json.dumps(dict(preservation_phase='FAILED_RUNTIME_EXACT_DEAD',owner=manager_owner,unit=final_service)),file=sys.stderr,flush=True)\nroots=[root/RID]+[root/name for name in sorted(current_operations)];packed={};compressed_total=0\nlimits=[runtime_policy['allocation']['metadata_maximum_bytes']+len(runtime_policy['allocation']['recording_slots'])*runtime_policy['allocation']['local_backup_per_recording']]+[runtime_policy['allocation']['broker_allocation']['target_maximum_bytes']]*len(current_operations)\ndef members(folder):\n fs={};dirs=[]\n for base,subdirs,names in os.walk(folder,followlinks=False):\n  p=Path(base);assert not p.is_symlink()\n  rel=p.relative_to(folder).as_posix();dirs.append('' if rel=='.' else rel);assert len(dirs)<=264\n  for name in names:\n   q=p/name;s=q.lstat();assert not q.is_symlink() and q.is_file() and s.st_nlink==1 and s.st_size<=33554432\n   fs[q.relative_to(folder).as_posix()]=(s.st_ino,s.st_size,s.st_mtime_ns)\n   assert len(fs)<=1162\n return fs,sorted(dirs)\nfor folder,maximum in zip(roots,limits):\n fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)\n try:\n  fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)\n  initial,dirs=members(folder)\n  assert sum(v[1] for v in initial.values())+65536*len(dirs)<=maximum\n  files={}\n  for name,st in sorted(initial.items()):\n   q=folder/name\n   with q.open('rb') as f:\n    h=hashlib.sha256();size=0\n    while True:\n     chunk=f.read(16384)\n     if not chunk:break\n     h.update(chunk);size+=len(chunk)\n   assert size==st[1]\n   digest=h.hexdigest();row=dict(bytes=size,sha256=digest,identity=list(st))\n   if digest not in KNOWN:\n    pass  # All members are streamed after the complete closed census.\n   files[name]=row\n  assert members(folder)==(initial,dirs), 'Closed source changed during complete hashing'\n  packed[folder.name]=dict(files=files,directories=dirs,maximum_bytes=maximum,\n       bytes=sum(v[1] for v in initial.values()),reserved_bytes=sum(v[1] for v in initial.values())+65536*len(dirs))\n finally:os.close(fd)\nassert ticks(manager_owner['pid'])!=manager_owner['start_ticks']\nvalue['preservation']=dict(status='FAILED_SOURCE_AND_MANAGER_CLOSED_CENSUS',manager_owner=manager_owner,\n exact_manager_dead=True,service=final_service,roots=packed,compressed_payload_bytes=compressed_total,\n model_start_status='REVIEW_NATIVE_SESSION_RECEIPTS',capture_start_status='REVIEW_ACTUAL_CAPTURE_AND_CLOSED_AUDIO_RECEIPTS',original_failure=gate_result,\n no_success_or_journal_backup_claim=True)\nvalue['status']='FAILED_SOURCE_AND_MANAGER_CLOSED_CENSUS'\nvalue['native_writes']='NORMAL_FAILED_MANAGER_STOP_AND_PINNED_ROLLBACK'\n# Restore using the already-backed installed rollback service after exact closure.\nactivation=root/(RID+'-activation')\nfirst=activation/'attempts/01/OWNER.json'\nrollback_unit='jp-rollback-'+RID+'.service'\nbefore_rollback=unit_state(rollback_unit)\nrequested=False\nif not first.exists():\n assert before_rollback['ActiveState']=='inactive' and before_rollback['MainPID']=='0'\n outcome=command(['systemctl','--user','start',rollback_unit])\n assert outcome['returncode']==0\n requested=True\nelse:outcome=None\nuntil=time.monotonic()+20\nwhile unit_state(rollback_unit)['ActiveState'] in ('activating','active','deactivating'):\n if time.monotonic()>=until:raise TimeoutError('Pinned rollback did not finish in20seconds')\n time.sleep(.05)\nvalue['rollback_after_preservation']=dict(requested_once=requested,command=outcome,unit=unit_state(rollback_unit))\nassert value['rollback_after_preservation']['unit']['ActiveState']=='inactive'\nassert value['rollback_after_preservation']['unit']['MainPID']=='0'\nassert first.exists()\nrollback_owner=strict(first.read_bytes());identity(rollback_owner)\nassert ticks(rollback_owner['pid'])!=rollback_owner['start_ticks']\nresult_path=first.with_name('RESULT.json')\nassert result_path.exists() and result_path.stat().st_size<=65536\nvalue['rollback_after_preservation']['result']=strict(result_path.read_bytes())\nvalue['rollback_after_preservation']['owner']=rollback_owner\nfor p in Path('/proc/asound').glob('card*/pcm*c/sub*/status'):assert p.read_text().strip()=='closed'\n\n# Every complete root census gets its own unchanged bounded frame.\nvalue['recording_controls']={k:v for k,v in value['recording_controls'].items() if k.endswith('/RESERVED.json')}\nvalue['operation_receipts']={k:dict(bytes=len(json.dumps(v,sort_keys=True).encode()),sha256=sha(json.dumps(v,sort_keys=True).encode())) for k,v in value['operation_receipts'].items()}\nvalue['preservation']['roots']={k:{key:v[key] for key in ('bytes','reserved_bytes','maximum_bytes')} for k,v in packed.items()}\nemit_frame(value)\nfor folder in roots:\n tree=packed[folder.name]\n emit_frame(dict(type='ROOT_CENSUS',root=folder.name,tree=tree))\n fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)\n try:\n  fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)\n  expected={n:tuple(v['identity']) for n,v in tree['files'].items()}\n  assert members(folder)==(expected,tree['directories'])\n  for name,row in sorted(tree['files'].items()):\n   emit_frame(dict(root=folder.name,file=name,bytes=row['bytes']))\n   h=hashlib.sha256();size=0\n   with (folder/name).open('rb') as f:\n    while True:\n     block=f.read(16384)\n     if not block:break\n     sys.stdout.buffer.write(block);h.update(block);size+=len(block)\n   sys.stdout.buffer.flush()\n   assert size==row['bytes'] and h.hexdigest()==row['sha256']\n  assert members(folder)==(expected,tree['directories'])\n  emit_frame(dict(status='SOURCE_TREE_UNCHANGED',root=folder.name))\n finally:os.close(fd)\nassert ticks(manager_owner['pid'])!=manager_owner['start_ticks']\nemit_frame(dict(status='COMPLETE_CLOSED_SOURCE_STREAM',roots=[p.name for p in roots]))\n"

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('private','local','prior-closure','previous-inspection','scope','output','candidate-install'):
        ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    def put(name,raw):
        with (a.output/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if (a.output/name).read_bytes()!=raw:raise IOError('Exact inspection readback')
    def save(name,value):put(name,(json.dumps(value,sort_keys=True,indent=2)+'\n').encode())
    save('REGISTERED_OWNER.json',owner)
    sys.path.insert(0,'G:\\Just_Peachy_N1\\20260924_campaign\\worktree\\research\\nvidia_nemo_comparison\\20260924_campaign\\n5\\extension_20260928\\pi_native_20260928')
    scope=json.loads(a.scope.read_bytes());last_guard=[0.]
    def guard():
        now=datetime.now(timezone.utc)
        if now>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Host scope expired')
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
    issued=json.loads((a.candidate_install/'ADMISSION.json').read_bytes())
    installed=json.loads((a.candidate_install/'RESULT.json').read_bytes())
    if issued['root']!=installed['root'] or hashlib.sha256((a.candidate_install/'RELEASE.json').read_bytes()).hexdigest()!=installed['policy_sha256']:
        raise ValueError('Exact issued candidate prior-owner binding')
    for row in issued['prior']:
        v=identity(row);identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    later=list(a.scope.parent.glob('install-inspection-v*/NATIVE_OWNER.json'))+list(a.private.glob('runtime-titanet-v*-install/NATIVE_OWNER.json'))+list(a.private.glob('runtime-titanet-v*-install/CLOSURE_OWNER.json'))
    later=[p for p in later if tuple(identity(json.loads(p.read_bytes()))[k] for k in ('boot_id','pid','start_ticks')) not in identities]
    if len(later)>16:raise ValueError('Bounded explicit inspection continuation owners')
    for path in later:
        v=identity(json.loads(path.read_bytes()))
        identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    assert len(identities)<=1088
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
    collector=(Path('G:\\Just_Peachy_N1\\20260924_campaign\\worktree\\research\\nvidia_nemo_comparison\\20260924_campaign\\n5\\extension_20260928\\pi_native_20260928')/'collect_native_closure_v19.py').read_text(encoding='utf-8')
    # Extract only its literal native source constant; no collector execution.
    constants=[n.value for n in ast.walk(ast.parse(collector)) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'NEW_NESTED=' in n.value]
    if len(constants)!=1:raise ValueError('Selected historical collector boundary')
    native_tree=ast.parse(constants[0])
    assignment=next(n for n in native_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NEW_NESTED' for t in n.targets))
    for path,row in ast.literal_eval(assignment.value).items():
        nested[path]={**row,'policy_sha256':'f39a8b7dbedbebed1492687d42d5648ac033dbba0d02a4a46537175e1fa40d9c'}
    candidate_admission=json.loads((a.candidate_install/'ADMISSION.json').read_bytes())
    for path,row in candidate_admission['nested'].items():
        if path in nested and nested[path]!=row:raise ValueError('Historical owner conflict')
        nested[path]=row
    candidate_result=json.loads((a.candidate_install/'RESULT.json').read_bytes())
    rid=Path(candidate_result['root']).name
    policy_sha=hashlib.sha256((a.candidate_install/'RELEASE.json').read_bytes()).hexdigest()
    if candidate_result['policy_sha256']!=policy_sha or candidate_result['root']!=candidate_admission['root']:
        raise ValueError('Exact installed candidate admission/result')
    for path in a.private.glob('field-runtime-v*-install/NATIVE_CLOSURE.json'):
        proof=json.loads(path.read_bytes())
        if proof['exact_owner_dead'] is not True or proof['utility_pid_absent'] is not True:raise ValueError('Actual installer closure')
        for k in ('owner','utility_owner'):
            v=proof[k];identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    for path in a.private.glob('field-runtime-v*/NATIVE_OWNER.json'):
        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    if len(identities)>1088:raise ValueError('Bounded full prior owner set')
    for path in a.private.glob('field-runtime-v*-raw-pair-v*/ARECORD_OWNER.json'):
        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    if len(identities)>1088:raise ValueError('Complete prior owner bound')
    for path in a.private.glob('field-runtime-v*-source-recovery-mounted-v*/NATIVE_OWNER.json'):
        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    for path in (a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'):
        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    if len(identities)>1088:raise ValueError('Original owner cap')
    guard()
    if datetime.now(timezone.utc)+timedelta(seconds=90)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Complete read-only closure reserve')

    policy=json.loads((a.candidate_install/'RELEASE.json').read_bytes())
    full_copy=policy['allocation']['target_maximum_bytes']
    if type(full_copy) is not int or full_copy<=0:raise ValueError('Original independent full target copy reservation')
    if shutil.disk_usage('G:/').free<75*1024**3+full_copy+4*1024**2:raise RuntimeError('Complete copy plus host floor')
    save('COPY_ALLOCATION.json',dict(full_independent_copy_bytes=full_copy,metadata_bytes=4*1024**2,small_tree_credit=False))
    # Use actual immutable installation copies; no recopy of the neural assets.
    known={}
    stage=a.candidate_install/'stage-backup'
    for path in stage.rglob('*.py'):
        if not path.is_file() or path.is_symlink() or path.stat().st_size>131072:raise ValueError('Bounded backed code')
        data=path.read_bytes();known[hashlib.sha256(data).hexdigest()]=data
    common_paths=list(stage.rglob('COMMON_BUNDLE.json'))
    if len(common_paths)!=1:raise ValueError('Exact installed common source copy')
    common=json.loads(common_paths[0].read_bytes())
    for name,token in common['files'].items():
        data=base64.b64decode(token,validate=True)
        if len(data)>131072:raise ValueError('Original code member ceiling')
        known[hashlib.sha256(data).hexdigest()]=data
    if len(known)>128 or sum(map(len,known.values()))>2097152:raise ValueError('Complete bounded known source set')

    code='KNOWN='+repr(set(known))+'\n'+'PRIOR='+repr(list(identities.values()))+'\nPRIOR_SHA='+repr(hashlib.sha256(prior_raw).hexdigest())+'\nNESTED='+repr(nested)+'\nHISTORICAL='+repr(historical)+'\nRID='+repr(rid)+'\nPOLICY_SHA='+repr(policy_sha)+'\n'+NATIVE
    compile(code,'<runtime-install-inspection>','exec')
    save('PRESERVATION_ADMISSION.json',dict(issued_utc=datetime.now(timezone.utc).isoformat(),expires_utc=scope['expires_utc'],
        maximum_seconds=105,maximum_output_bytes=155669036,native_writes="FAILED_MANAGER_NORMAL_STOP",capture=False,precheck_sha256=hashlib.sha256((a.output/'HOST_PRECHECK.json').read_bytes()).hexdigest(),source_sha256=hashlib.sha256(code.encode()).hexdigest()))
    from field_operator_broker_host_v2 import ssh_phase,process_phase
    from dispatch_b01_stack_v2 import SSH
    SSH[-1:-1]=['-o','Hostname=192.168.2.57']

    import shlex
    from field_local_manager_transport_v1 import run,TransportFailure
    from field_local_manager_ssh_mirror_v1 import validate_plan
    bootstrap="import os,sys,struct,json,resource,signal\nfrom pathlib import Path\nos.sched_setaffinity(0,{3})\nfor k,n in ((resource.RLIMIT_AS,134217728),(resource.RLIMIT_STACK,1048576),(resource.RLIMIT_FSIZE,0)):resource.setrlimit(k,(n,n))\nsignal.alarm(100)\ndef emit_frame(v):\n r=json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()\n assert 0<len(r)<=262144\n sys.stdout.buffer.write(struct.pack('!I',len(r))+r);sys.stdout.buffer.flush()\nown=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())\nemit_frame(dict(early_owner=own))\ndef exact(n):\n out=bytearray()\n while len(out)<n:\n  b=sys.stdin.buffer.read(min(16384,n-len(out)))\n  if not b:raise EOFError('Payload')\n  out.extend(b)\n return bytes(out)\nn=struct.unpack('!I',exact(4))[0];assert 0<n<=262144\nraw=exact(n)\nimport hashlib\nassert hashlib.sha256(raw).hexdigest()==sys.argv[1]\nemit_frame(dict(type='HELLO',owner=own))\nexec(compile(raw,'<runtime-stream-preservation>','exec'))\n"
    payload=code.encode()
    command=SSH+['python3 -u -B -c '+shlex.quote(bootstrap)+' '+hashlib.sha256(payload).hexdigest()]
    closure_proof={}
    def early(who):
        save('NATIVE_OWNER.json',who);return True
    def verify_closed(who):
        observed=process_phase(SSH+['test ! -e /proc/'+str(who['pid'])],timeout=10,maximum=16384)
        out=observed.pop('stdout');err=observed.pop('stderr')
        put('CLOSURE_STDOUT.bin',out);put('CLOSURE_STDERR.bin',err);save('CLOSURE_PHASE.json',observed)
        if observed['returncode'] or observed['fault'] is not None or not observed['readers_joined'] or not observed['ssh_reaped']:
            raise RuntimeError('Independent exact native closure')
        closure_proof.update(owner=who,exact_pid_absent=True,natural_returncode=0)
        save('NATIVE_CLOSURE.json',closure_proof);return True
    def stop_owned():
        # Native alarm and this watchdog bound only this injected exporter.
        # The manager Stop path remains the single native action above.
        pass
    copied={}
    def consume(channel,who,close):
        value=channel.json();put('STDOUT.bin',json.dumps(value,sort_keys=True).encode())
        if value['utility_owner']!=who:raise ValueError('Actual early owner mismatch')
        preserved=value['preservation']
        if not preserved['exact_manager_dead'] or preserved['status']!='FAILED_SOURCE_AND_MANAGER_CLOSED_CENSUS':
            raise ValueError('Actual failed source closure required')
        destination=a.output/'tree';destination.mkdir()
        selected=sorted(Path(v['operation']['root']).name for k,v in value['recording_controls'].items() if k.endswith('/RESERVED.json'))
        policy=json.loads((a.candidate_install/'RELEASE.json').read_bytes())
        allowed={Path(p).name for p in policy['recording_roots']}
        if not 1<=len(selected)<=4 or len(set(selected))!=len(selected) or not set(selected)<=allowed:raise ValueError('Exact existing admitted recording roots')
        if set(preserved['roots'])!={rid,*selected}:raise ValueError('Complete manager and all current recording roots')
        # Conservative existing transport ceiling; original independent reservations remain charged.
        if sum(r['bytes'] for r in preserved['roots'].values())>155669036:raise ValueError('This transfer needs separate bounded root exports')
        for rootname in [rid]+selected:
            packet=channel.json()
            if set(packet)!={'type','root','tree'} or packet['type']!='ROOT_CENSUS' or packet['root']!=rootname:raise ValueError('Exact bounded root census frame')
            tree=packet['tree']
            if {k:tree[k] for k in ('bytes','reserved_bytes','maximum_bytes')}!=preserved['roots'][rootname]:raise ValueError('Root census summary mismatch')
            save('CENSUS-'+rootname+'.json',tree)
            pins={n:{k:r[k] for k in ('bytes','sha256')} for n,r in tree['files'].items()}
            plan={k:tree[k] for k in ('directories','bytes','reserved_bytes')};plan['files']=pins
            validate_plan(plan,pins,min(tree['maximum_bytes'],155669036),allow_empty=True)
            folder=destination/rootname;folder.mkdir()
            for relative in sorted(tree['directories'],key=lambda n:(n.count('/'),n)):
                if relative:folder.joinpath(*PurePosixPath(relative).parts).mkdir()
            chunks=0
            for name,row in sorted(pins.items()):
                guard()
                if channel.json()!=dict(root=rootname,file=name,bytes=row['bytes']):raise ValueError('Exact file header')
                path=folder.joinpath(*PurePosixPath(name).parts);h=hashlib.sha256();remaining=row['bytes']
                with path.open('xb',buffering=0) as f:
                    while remaining:
                        data=channel.exact(min(16384,remaining))
                        view=memoryview(data)
                        while view:
                            n=f.write(view)
                            if not n:raise IOError('Short full backup write')
                            view=view[n:]
                        h.update(data);remaining-=len(data);chunks+=1
                    os.fsync(f.fileno())
                if h.hexdigest()!=row['sha256']:raise IOError('Complete transferred file digest')
                with path.open('rb') as f:
                    if path.stat().st_size!=row['bytes'] or hashlib.file_digest(f,'sha256').hexdigest()!=row['sha256']:
                        raise IOError('Independent complete PC readback')
            if channel.json()!=dict(status='SOURCE_TREE_UNCHANGED',root=rootname):raise ValueError('Source identity/membership terminal')
            actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
            dirs={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_dir()}|{''}
            if actual!=set(pins) or dirs!=set(tree['directories']):raise ValueError('Full destination membership')
            copied[rootname]=dict(files=len(pins),directories=len(dirs),bytes=sum(r['bytes'] for r in pins.values()),
                data_chunks=chunks,manifest_sha256=hashlib.sha256(json.dumps(pins,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        if channel.json()!=dict(status='COMPLETE_CLOSED_SOURCE_STREAM',roots=[rid]+selected):raise ValueError('Complete source stream')
        close()
        value['utility_pid_absent_after_ssh']=True;value['prior_failed_inspector_checked_dead']=previous
        return value
    try:
        value,transport=run(command,payload,persist_early=early,consume=consume,verify_closed=verify_closed,
            stop_owned=stop_owned,guard=guard,timeout=105)
    except TransportFailure as exc:
        transport=exc.receipt;put('STDERR.bin',transport.pop('stderr'));save('PHASE.json',transport)
        raise
    err=transport.pop('stderr');put('STDERR.bin',err);save('PHASE.json',transport)
    lines=err.splitlines()
    if not lines or json.loads(lines[0])!={'utility_owner':value['utility_owner']} or not all('preservation_phase' in json.loads(s) for s in lines[1:]):
        raise ValueError('Exact native diagnostics')
    save('RESULT.json',value)
    save('BACKUP.json',dict(status='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY',copies=copied,
        native_utility_exact_absent=True,manager_exact_dead=True,recording_success=False,
        verified_local_source_reconstruction=False,verified_complete_stream_and_readback=True,all_prior_failures_preserved=True))

    print(json.dumps({k:value[k] for k in ('utc','status','candidate_unit','candidate_ui','available_ram_bytes','target_free_bytes','native_writes')}))


if __name__=='__main__':main()
