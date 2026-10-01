"""Single fresh native local-copy qualification; README_FIELD_LOCAL_BACKUP_V3.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,sys,json,hashlib,base64,math,time,os
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.dont_write_bytecode=True
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('preparation','census','resources','closure','extra','output'):parser.add_argument('--'+name,required=True,type=Path)
 args=parser.parse_args();args.output.mkdir();out=args.output;me=psutil.Process()
 (out/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
 here=Path(__file__).resolve().parent;private=args.preparation.parent
 from field_local_release_plan_v1 import encoded,validate_research_operation
 from field_operator_broker_host_v2 import ssh_phase,closed_owners
 from field_host_budget_v1 import floors
 now=datetime.now(timezone.utc);assert now+timedelta(seconds=600)<datetime.fromisoformat('2026-10-01T17:42:44+00:00')
 for path,age in [(args.census,900),(args.resources,300),(args.closure,300),(args.extra,60)]:
  assert time.time()-path.stat().st_mtime<age
 extra=json.loads(args.extra.read_bytes());closure=json.loads(args.closure.read_bytes());resources=json.loads(args.resources.read_bytes())
 assert extra['utility_pid_absent_after_ssh'] and all(x['exact_alive'] is False for x in extra['pi']+extra['host'])
 prior={}
 for row in closure['owners']+extra['pi']:
  o=row['owner'];prior[(o['boot_id'],o['pid'],o['start_ticks'])]=o
 for o in (closure['utility_owner'],extra['utility_owner']):prior[(o['boot_id'],o['pid'],o['start_ticks'])]=o
 for row in extra['host']:
  o=row['owner']
  try:current=psutil.Process(o['pid']).create_time()
  except psutil.NoSuchProcess:current=None
  assert current is None or abs(current-o['create_time'])>.001
 names=['field_local_broker_backup_v1.py','field_operator_health_v1.py','field_local_release_files_v2.py','field_local_release_plan_v1.py',
  'field_operator_broker_streamed_mirror_v1.py','field_host_budget_v1.py','field_operator_broker_files_v2.py',
  'field_operator_broker_layout_v2.py','field_operator_session_plan_v1.py','field_operator_session_plan_v3.py',
  'field_operator_session_ledger_v4.py','field_live_layout_v2.py','field_live_layout_v3.py']
 files={n:(here/n).read_bytes() for n in names}
 assert len(files)<=16 and sum(map(len,files.values()))<=131072
 for n,version in [('field_local_broker_backup_v1.py',1),('field_local_backup_native_v2.py',3),(Path(__file__).name,3)]:
  for folder in ('source-backup-v%d'%version,'source-restore-v%d'%version):assert (args.preparation/folder/n).read_bytes()==(here/n).read_bytes()
 def digest(raw):return hashlib.sha256(raw).hexdigest()
 manifest=dict(schema='just-peachy.local-release-manifest.v1',files=[dict(path='code/'+n,bytes=len(raw),sha256=digest(raw)) for n,raw in sorted(files.items())])
 old=private/'field-operator-sessions-v6-admission/host-backup-mirror/broker'
 config=json.loads((old/'CONFIG.json').read_bytes());template=json.loads((old/'TEMPLATE.json').read_bytes())
 oldmanifest=json.loads((old/'MANIFEST.json').read_bytes())
 for name in ('CONFIG.json','TEMPLATE.json'):
  row=next(x for x in oldmanifest['files'] if x['path']=='broker/'+name);raw=(old/name).read_bytes()
  assert len(raw)==row['bytes'] and digest(raw)==row['sha256']
 binding=template['admission']['operator_parent']
 modepath=binding['manifest_path'];modesha=binding['manifest_sha256']
 installed=next(x for x in template['admission']['files'] if x['sha256']==config['installed_manifest_sha256'])
 source_root=private/'field-operator-sessions-v6-admission/host-backup-mirror'
 launch=json.loads((private/'field-operator-sessions-v6-admission/host/metadata/LAUNCH.json').read_bytes())
 backup=json.loads((private/'field-operator-sessions-v6-admission/host-backup/metadata/BACKUP.json').read_bytes())
 source_policy=json.loads((source_root/'RELEASE.json').read_bytes())
 assert launch['policy_sha256']==digest((source_root/'RELEASE.json').read_bytes()) and source_policy['root']==launch['root']
 assert backup['source']==launch['root'] and backup['status']=='EXACT_SSH_STREAMED_BACKUP_VERIFIED'
 for rel,pin in backup['files'].items():
  path=source_root/rel;assert path.is_file() and not path.is_symlink()
  with path.open('rb') as f:observed=hashlib.file_digest(f,'sha256').hexdigest()
  assert path.stat().st_size==pin['bytes'] and observed==pin['sha256']
 mib=1048576;margin=8*mib;copy_bytes=source_policy['allocation']['target_maximum_bytes']
 a=dict(local_copy_bytes=copy_bytes,metadata_bytes=2*mib,target_maximum_bytes=copy_bytes+2*mib,
  host_maximum_bytes=copy_bytes+2*mib,combined_request_bytes=2*(copy_bytes+2*mib))
 root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-local-backup-v2'
 policy=dict(schema='just-peachy.local-backup-qualification.v1',root=root,allocation=a,
 release_manifest_sha256=digest(encoded(manifest)),measured_target_before_bytes=resources['target_bytes'],
 measured_host_before_bytes=resources['host_window_bytes'],measured_payload_before_bytes=resources['payload_bytes'],
 combined_output_cap_bytes=math.ceil((resources['combined_bytes']+a['combined_request_bytes']+margin)/mib)*mib,
 total_payload_cap_bytes=math.ceil((resources['payload_bytes']+a['combined_request_bytes']+margin)/mib)*mib)
 operation=dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),purpose='LOCAL_RELEASE_QUALIFICATION');validate_research_operation(operation)
 home='/home/peachyprototype/JustPeachy'
 physical_pins={home+'/install/current.json':config['baseline']['install_sha256'],home+'/data/live_config.json':config['baseline']['live_config_sha256'],
 '/home/peachyprototype/.config/kanshi/config':config['baseline']['display_sha256'],modepath:modesha,installed['path']:config['installed_manifest_sha256']}
 request=dict(policy=policy,policy_sha256=digest(encoded(policy)),manifest=manifest,files={n:base64.b64encode(raw).decode() for n,raw in files.items()},
 operation=operation,baseline=config['baseline'],physical_pins=physical_pins,prior_pi=list(prior.values()),unit='jp-local-backup-v2.service',accounting_margin_bytes=margin,source=launch['root'],source_policy_sha256=launch['policy_sha256'],source_unit=launch['unit']+'.service',source_files=backup['files'])
 floors(a['host_maximum_bytes']+4*mib)
 sources={**files,'field_local_backup_native_v2.py':(here/'field_local_backup_native_v2.py').read_bytes(),Path(__file__).name:Path(__file__).read_bytes()}
 outputs={'RELEASE.json':encoded(policy),'REQUEST.json':encoded(request),'SOURCE_BINDING.json':encoded(dict(launch=launch,backup_manifest_sha256=digest(encoded(backup))))}
 for folder in ('backup','restore'):(out/folder).mkdir()
 for name,raw in {**sources,**outputs}.items():
  for folder in (out,out/'backup',out/'restore'):
   with (folder/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
   assert (folder/name).read_bytes()==raw
 assert sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<4*mib
 (out/'ADMISSION_REVIEW.json').open('x').write(json.dumps(dict(status='ADMITTED_COMPLETE_LOCAL_COPY_ONLY',operation=operation,allocation=a,
  explicit_margin_bytes=margin,policy_sha256=request['policy_sha256'],production_activation=False,local_recording_backup=True,
  source_backup_and_independent_restore=True,prior_pi=len(prior),old_window_unchanged=True)))
 source=sources['field_local_backup_native_v2.py']
 payload=('REQUEST='+repr(request)+'\n').encode()+source
 cmd=['systemd-run','--user','--quiet','--wait','--pipe','--unit=jp-local-backup-v2','--description=JP_local_broker_backup',
  '-p','AllowedCPUs=2,3','-p','CPUQuota=200%','-p','TasksMax=64','-p','LimitAS=134217728','-p','LimitSTACK=1048576',
  '-p','LimitFSIZE=33554432','-p','RuntimeMaxSec=180','-p','TimeoutStopSec=15','-p','KillMode=control-group',config['python'],'-B','-']
 phase=ssh_phase(cmd,payload=payload,timeout=200,maximum=262144)
 stdout=phase.pop('stdout');stderr=phase.pop('stderr')
 (out/'STDOUT.bin').open('xb').write(stdout);(out/'STDERR.bin').open('xb').write(stderr)
 (out/'PHASE.json').open('x').write(json.dumps(phase))
 events=[json.loads(line) for line in stdout.splitlines()]
 owners=[e['owner'] for e in events if e['event']=='OWNER']
 owners += [e['data']['owner'] for e in events if e['event']=='CHILD' and e['data']['event']=='OWNER']
 (out/'NATIVE_OWNERS.json').open('x').write(json.dumps(owners))
 close_code="import os,resource,signal,json,subprocess,fcntl,hashlib\nfrom pathlib import Path\nos.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)\nresource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2);resource.setrlimit(resource.RLIMIT_FSIZE,(0,0));signal.alarm(15)\ndef ticks(pid):\n try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])\n except FileNotFoundError:return None\nboot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()\nowner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)\nprint(json.dumps(dict(event='OWNER',owner=owner)),flush=True)\nfor o in OWNERS:assert boot!=o['boot_id'] or ticks(o['pid'])!=o['start_ticks']\np=subprocess.run(['systemctl','--user','show',UNIT,'-p','ActiveState','-p','SubState','-p','MainPID','-p','LoadState'],capture_output=True,text=True,timeout=5)\nprops=dict(line.split('=',1) for line in p.stdout.splitlines())\nprint(json.dumps(dict(event='UNIT',returncode=p.returncode,properties=props)),flush=True)\nassert props.get('ActiveState') in ('inactive','failed') and props.get('MainPID')=='0'\nassert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'\nassert ticks(1013)==569 and ticks(1130)==607\nfor path,digest in PINS.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest\nfor path in ['/home/peachyprototype/JustPeachy/research/nemotron-20260928/B05_PREVIEW_DISPATCH.lock','/home/peachyprototype/JustPeachy/data/xvf-hardware.lock']:\n fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)\n try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n finally:os.close(fd)\nprint(json.dumps(dict(event='RESULT',owner=owner,capture_closed=True,leases_free=True,baseline_unchanged=True,properties=props)),flush=True)\n"
 close_payload=('OWNERS='+repr(owners)+'\nUNIT='+repr(request['unit'])+'\nPINS='+repr(physical_pins)+'\n'+close_code).encode()
 close_phase=ssh_phase(['python3','-B','-'],payload=close_payload,timeout=25,maximum=16384)
 close_stdout=close_phase.pop('stdout');close_stderr=close_phase.pop('stderr')
 (out/'CLOSE_STDOUT.bin').open('xb').write(close_stdout);(out/'CLOSE_STDERR.bin').open('xb').write(close_stderr)
 (out/'CLOSE_PHASE.json').open('x').write(json.dumps(close_phase))
 close_events=[json.loads(x) for x in close_stdout.splitlines()];close_owner=close_events[0]['owner']
 owners.append(close_owner);(out/'CLOSE_OWNER.json').open('x').write(json.dumps(close_owner))
 native_closure=closed_owners(owners);(out/'NATIVE_CLOSURE.json').open('x').write(json.dumps(native_closure))
 assert close_phase['returncode']==0 and close_phase['fault'] is None and close_events[-1]['event']=='RESULT'
 (out/'PHYSICAL_CLOSURE.json').open('x').write(json.dumps(close_events[-1]))
 trees=[e for e in events if e['event']=='TREE']
 if trees:
  assert len(trees)==1
  tree=trees[0];assert len(tree['entries'])<=500 and tree['total_bytes']+65536*(tree['directories']+1)<=a['target_maximum_bytes']
  mirror=out/'mirror';mirror.mkdir();known={};total=0;chunks=0
  for row in tree['entries']:
   rel=Path(row['path']);assert not rel.is_absolute() and '..' not in rel.parts and str(rel) not in known
   known[row['path']]=row;dst=mirror/rel
   if row['type']=='directory':dst.mkdir(parents=True,exist_ok=True)
   else:dst.parent.mkdir(parents=True,exist_ok=True);dst.open('xb').close()
  for e in events:
   if e['event']!='CHUNK':continue
   row=known[e['path']];assert row['type']=='file'
   raw=base64.b64decode(e['data'],validate=True);assert 0<len(raw)<=16384
   dst=mirror/e['path'];assert dst.stat().st_size==e['offset'] and e['offset']+len(raw)<=row['bytes']
   with dst.open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
   chunks+=1
  for rel,row in known.items():
   if row['type']!='file' or rel.startswith('tree/') or rel=='control/COPY_RESULT.json':continue
   if rel.startswith('code/'):raw=files[rel[5:]]
   elif rel=='control/RELEASE.json':raw=encoded(policy)
   elif rel=='control/MANIFEST.json':raw=encoded(manifest)
   else:raise ValueError('Unknown native metadata member')
   assert len(raw)==row['bytes'] and digest(raw)==row['sha256']
   dst=mirror/rel
   with dst.open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  # Independent host backup uses equal existing bytes, not a second Pi transfer.
  # Actual new native file hashes and membership from TREE are authoritative.
  reused_chunks=0
  for rel,row in known.items():
   if row['type']!='file' or not rel.startswith('tree/'):continue
   path=source_root/rel[5:];dst=mirror/rel
   assert path.is_file() and row['bytes']<=path.stat().st_size
   with path.open('rb') as reader,dst.open('ab') as writer:
    left=row['bytes']
    while left:
     block=reader.read(min(16384,left));assert block
     assert writer.write(block)==len(block);left-=len(block);reused_chunks+=1
    writer.flush();os.fsync(writer.fileno())
  for rel,row in known.items():
   if row['type']=='file':
    path=mirror/rel
    with path.open('rb') as f:actual_hash=hashlib.file_digest(f,'sha256').hexdigest()
    assert path.stat().st_size==row['bytes'] and actual_hash==row['sha256'];total+=row['bytes']
  assert {p.relative_to(mirror).as_posix() for p in mirror.rglob('*')}==set(known)
  assert total==tree['total_bytes']
  (out/'BACKUP.json').open('x').write(json.dumps(dict(status='EXACT_COMPLETE_NATIVE_COPY_TREE',tree=tree,chunks=chunks,local_reused_chunks=reused_chunks,payload_source='existing_host_bytes_matched_to_new_native_hashes',actual_closure=native_closure,bytes=total)))
 assert phase['returncode']==0 and phase['fault'] is None and phase['readers_joined'] and phase['ssh_reaped'],phase
 result=events[-1];assert result['event']=='RESULT' and result['status']=='PASS_NATIVE_COMPLETE_LOCAL_BROKER_BACKUP'
 assert (out/'BACKUP.json').exists() and datetime.now(timezone.utc)<datetime.fromisoformat(operation['expires_utc'])
 (out/'RESULT.json').open('x').write(json.dumps(result))
 print(json.dumps(dict(status=result['status'],native_owners=len(owners),backup_bytes=total,chunks=chunks,policy_sha256=request['policy_sha256'])))
if __name__=='__main__':main()
