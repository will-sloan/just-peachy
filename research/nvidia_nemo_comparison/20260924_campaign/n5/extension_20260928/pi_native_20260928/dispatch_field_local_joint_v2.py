"""One current-boot joint qualification; README_FINAL_MANAGER_DISPATCH_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,base64,hashlib,json,math,os,shlex,sys,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.dont_write_bytecode=True

PREFLIGHT=r"""
import os,sys,resource,signal,json,hashlib,shutil,fcntl,subprocess
from pathlib import Path
from datetime import datetime,timezone
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(0,)*2);signal.alarm(25)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
me=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
print(json.dumps(dict(owner=me)),flush=True)
q=json.loads(sys.stdin.buffer.readline(65537))
assert boot==q['boot_id']=='892ed9fa-e39c-48af-8653-eae5e123daad'
assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text() and os.uname().machine=='aarch64'
assert int(Path('/sys/class/block/mmcblk0/size').read_text())*512==31268536320
assert all(o['boot_id']==boot and ticks(o['pid'])==o['start_ticks'] for o in q['baseline_owners'])
for o in q['prior']:
 assert type(o['pid']) is int and type(o['start_ticks']) is int and o['pid']>0 and o['start_ticks']>0
 assert o['boot_id']!=boot or ticks(o['pid'])!=o['start_ticks']
home=Path.home();r=home/'JustPeachy/research/nemotron-20260928'
for name,digest in q['pins'].items():
 assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for path in (r/'B05_PREVIEW_DISPATCH.lock',home/'JustPeachy/data/xvf-hardware.lock'):
 with path.open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
units=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','--plain','jp-*'],text=True,timeout=5)
assert not units.strip()
ram=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
assert ram>=850*1024**2 and shutil.disk_usage(r).free>=5*1024**3
life=dict(schema='just-peachy.current-boot-binding.v1',observed_utc=datetime.now(timezone.utc).isoformat(),
 boot_id=boot,baseline_owners=q['baseline_owners'],install_sha256=q['pins'][str(home/'JustPeachy/install/current.json')],
 live_config_sha256=q['pins'][str(home/'JustPeachy/data/live_config.json')],
 display_config_sha256=q['pins'][str(home/'.config/kanshi/config')])
print(json.dumps(dict(lifecycle=life,owner=me,prior_count=len(q['prior']),capture='closed',units=units,
 ram=ram,free=shutil.disk_usage(r).free,target_bytes=int(subprocess.check_output(['du','-sb',str(r)],text=True,timeout=10).split()[0]))),flush=True)
"""

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('capsules','template','census','precheck','prior','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--manager-version',type=int,required=True);ap.add_argument('--broker-version',type=int,required=True)
    args=ap.parse_args();args.output.mkdir()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    (args.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
    from field_operator_broker_host_v2 import ssh_phase,closed_owners,process_phase
    from field_local_release_plan_v2 import allocation,encoded,validate_release
    from field_local_joint_contract_v3 import bind
    from field_local_postboot_capsule_v1 import derive
    from field_owner_binding_v1 import pack,decode
    from field_host_budget_v1 import HostStore,floors
    from dispatch_b01_stack_v2 import SSH
    from field_local_manager_receiver_v1 import session
    here=Path(__file__).resolve().parent;now=datetime.now(timezone.utc)
    if now+timedelta(seconds=600)>=datetime.fromisoformat('2026-10-01T16:14:58+00:00'):raise ValueError('Effective deadline')
    if now>=datetime.fromisoformat('2026-10-01T15:14:58+00:00'):raise ValueError('Finalization reserve')
    if min(args.manager_version,args.broker_version)<=1:raise ValueError('Fresh versioned roots')
    if time.time()-args.census.stat().st_mtime>900 or time.time()-args.precheck.stat().st_mtime>120:raise ValueError('Fresh all-owner/census review')
    pre=json.loads(args.precheck.read_bytes())
    if pre['native_dispatched'] is not False or pre['hosts_closed']<726:raise ValueError('Complete host ownership review')
    prior=decode(json.loads(args.prior.read_bytes()))
    boot='892ed9fa-e39c-48af-8653-eae5e123daad'
    baseline=[dict(pid=1008,start_ticks=476,boot_id=boot),dict(pid=1124,start_ticks=514,boot_id=boot)]
    home='/home/peachyprototype';campaign=home+'/JustPeachy/research/nemotron-20260928'
    pins={home+'/JustPeachy/install/current.json':'fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3',
          home+'/JustPeachy/data/live_config.json':'568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395',
          home+'/.config/kanshi/config':'c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b',
          home+'/JustPeachy/data/settings.json':'d94face8f202cc0aceac059bf32500721ab5da5b8e18446291642e9464ef0b57'}
    hostlimits={'metadata':(262144,262144,24),'failure':(262144,131072,8),'closure':(65536,32768,8)}
    store=HostStore(args.output/'host',hostlimits).create({'REGISTERED_OWNER.json':encoded(owner)})
    failures=[];external=[];phase_owners=[];closures=[];phase_number=0
    def all_prior():
        # Retain each phase observation separately, then explicitly deduplicate
        # the process-identity vector used for the bounded owner binding.
        return list({(o['boot_id'],o['pid'],o['start_ticks']):o for o in prior+phase_owners+closures}.values())
    def sha(v):return hashlib.sha256(v).hexdigest()
    def write(path,raw):
        with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if path.read_bytes()!=raw:raise IOError('Exact readback')
    # Separate finite admission/preparation metadata, included in the explicit8MiB
    # measured margin; not taken from a failed or unused recording reservation.
    admission_root=args.output/'admission';admission_root.mkdir()
    for n in ('backup','restore'):(admission_root/n).mkdir()
    def private(name,raw):
        if len(raw)>1048576:raise ValueError('Admission member ceiling')
        used=sum(x.stat().st_size for x in admission_root.rglob('*') if x.is_file())
        if used+len(raw)>4*1048576:raise ValueError('Admission metadata ceiling')
        write(admission_root/name,raw)
    def good(r):return r['returncode']==0 and r['fault'] is None and not r['overflow'] and r['readers_joined'] and r['ssh_reaped']
    def rows(r):return [json.loads(x) for x in r['stdout'].splitlines() if x]
    def rawphase(label,r):
        private(label+'_STDOUT.bin',r['stdout']);private(label+'_STDERR.bin',r['stderr'])
        private(label+'_PHASE.json',encoded({k:v for k,v in r.items() if k not in ('stdout','stderr')}))
    def dead(owners,label):
        observation=closed_owners(owners)
        closures.append(observation['utility_owner'])
        private(label+'_EXACT_CLOSURE.json',encoded(observation))
        return observation
    def probe(label):
        r=ssh_phase(['python3','-u','-B','-c',PREFLIGHT],
                    payload=encoded(dict(boot_id=boot,baseline_owners=baseline,prior=all_prior(),pins=pins))+b'\n',
                    timeout=30,maximum=16384)
        rawphase(label,r);rs=rows(r)
        if rs and set(rs[0])=={'owner'}:
            phase_owners.append(rs[0]['owner']);private(label+'_OWNER.json',encoded(rs[0]['owner']))
            dead([rs[0]['owner']],label)
        if not good(r) or len(rs)!=2:raise RuntimeError('Fresh native preflight failed')
        stamp=datetime.fromisoformat(rs[1]['lifecycle']['observed_utc'])
        received=datetime.now(timezone.utc);ahead=(stamp-received).total_seconds()
        if not -120<=ahead<=5:raise RuntimeError('Observed cross-host clock bound')
        began=time.monotonic()
        while datetime.now(timezone.utc)<stamp:
            if time.monotonic()-began>5:raise TimeoutError('Clock observation barrier')
            time.sleep(.01)
        private(label+'_CLOCK.json',encoded(dict(native_observed_utc=stamp.isoformat(),
          host_received_utc=received.isoformat(),observed_native_ahead_seconds=ahead,
          wait_seconds=time.monotonic()-began,host_after_utc=datetime.now(timezone.utc).isoformat(),
          native_stamp_unchanged=True)))
        return rs[1]
    observed=probe('PREFLIGHT')
    life=observed['lifecycle']
    # Host inventory is measured again after current source backups.
    sys.path.insert(0,str(here.parent))
    from window_guard import payload_inventory
    from dispatch_geometry_v2 import LOCAL
    used=0
    for rel in ('n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928'):
        inv=payload_inventory(LOCAL/rel)
        if inv['errors'] or inv['reparse_not_traversed']:raise ValueError('Host inventory incomplete')
        used+=inv['total_logical_bytes']
    census=json.loads(args.census.read_bytes())['calculation']
    payload=census['existing_bytes']+census['retained_reservations_bytes']+observed['target_bytes']+max(0,used-census['window_used_bytes'])
    manager=json.loads((args.capsules/'MANAGER_BUNDLE.json').read_bytes())
    broker=derive(json.loads((args.capsules/'BUNDLE.json').read_bytes()),manager,life)
    cfg=json.loads(base64.b64decode(broker['files']['broker/CONFIG.json']))
    child=json.loads(base64.b64decode(broker['files']['broker/TEMPLATE.json']))
    release=json.loads(args.template.read_bytes());full=allocation(1,3)
    release.update(schema='just-peachy.local-release-policy.v2',root=campaign+'/field-local-release-v'+str(args.manager_version),
      recording_roots=[campaign+'/field-operator-sessions-v'+str(args.broker_version)],allocation=full,
      release_manifest_sha256=sha(encoded(manager['manifest'])),installed_manifest_sha256=cfg['installed_manifest_sha256'],
      mode_registry_sha256=child['admission']['operator_parent']['manifest_sha256'],
      measured_target_before_bytes=observed['target_bytes'],measured_host_before_bytes=used,measured_payload_before_bytes=payload,
      combined_output_cap_bytes=math.ceil((used+observed['target_bytes']+full['combined_request_bytes']+8388608)/1048576)*1048576,
      total_payload_cap_bytes=math.ceil((payload+full['combined_request_bytes']+8388608)/1048576)*1048576)
    validate_release(release);floors(full['host_maximum_bytes']+8388608)
    issued=datetime.now(timezone.utc);end=issued+timedelta(seconds=600)
    operation=dict(issued_utc=issued.isoformat(),expires_utc=end.isoformat(),purpose='LOCAL_RELEASE_QUALIFICATION')
    joint=bind(broker,manager,release,operation,all_prior(),now=issued)
    manager_request=dict(operation=operation,baseline=cfg['baseline'],physical_pins=pins,prior_pi=all_prior(),
      unit='jp-field-local-install-v'+str(args.manager_version)+'.service',policy=release,accounting_margin_bytes=8388608,
      files={Path(n).name:v for n,v in manager['files'].items()},manifest=manager['manifest'],
      policy_sha256=sha(encoded(release)),binding=joint['reserve_binding'])
    outputs={'RELEASE.json':encoded(release),'OPERATION.json':encoded(operation),
             'MANAGER_REQUEST.json':encoded(manager_request),'BROKER_REQUEST.json':encoded(joint['broker_request']),
             'BINDINGS.json':encoded({k:v for k,v in joint.items() if k!='broker_request'})}
    for name,raw in outputs.items():
        for parent in (admission_root,admission_root/'backup',admission_root/'restore'):write(parent/name,raw)
    if sum(x.stat().st_size for x in admission_root.rglob('*') if x.is_file())+4*65536>4*1048576:raise ValueError('Admission backup allocation')
    store.json('ADMISSION.json',dict(operation=operation,policy_sha256=sha(encoded(release)),
       allocation=full,measured_host=used,measured_target=observed['target_bytes'],measured_payload=payload,
       explicit_margin=8388608,original_window_unchanged=True,failed_slot_credit=False))
    remaining=lambda:(end-datetime.now(timezone.utc)).total_seconds()
    python=home+'/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python'
    def manager_phase(label,request,source):
        code=(here/source).read_text()
        marker='from datetime import datetime,timezone'
        if code.count(marker)!=1:raise ValueError('Reviewed phase injection point')
        code=code.replace(marker,"REQUEST=json.loads(sys.stdin.buffer.readline(4*1024**2+1))\n"+marker,1)
        argv=['systemd-run','--user','--unit='+request['unit'],'--description=JustPeachy-local-phase','--wait','--pipe','--quiet']
        for prop in ('CPUQuota=200%','AllowedCPUs=2,3','TasksMax=64','LimitAS=134217728','LimitSTACK=1048576','LimitFSIZE=33554432','LimitCORE=0','RuntimeMaxSec=180','TimeoutStopSec=15','Nice=10'):
            argv+=['-p',prop]
        argv += ['--setenv=OPENBLAS_NUM_THREADS=1','--setenv=OMP_NUM_THREADS=1','--setenv=CUDA_VISIBLE_DEVICES=',python,'-u','-B','-c',code]
        r=ssh_phase(argv,payload=encoded(request)+b'\n',timeout=30,maximum=32768);rawphase(label,r)
        rs=rows(r);o=next((v['owner'] for v in rs if v.get('event')=='OWNER'),None)
        if o:
            external.append(o);phase_owners.append(o);private(label+'_OWNER.json',encoded(o))
        if not good(r):
            stop=process_phase(SSH+['systemctl --user stop '+request['unit']],timeout=20,maximum=4096);rawphase(label+'_STOP',stop)
        if o:dead([o],label)
        if not good(r) or not any(v.get('event')=='RESULT' for v in rs):raise RuntimeError(label+' failed')
        return rs[-1]
    broker_request=joint['broker_request'];bp=broker_request['policy'];root=bp['root'];bp_sha=sha(encoded(bp))
    stage_owner=None;gate_attempted=False;tree=None;manager_result=None;broker_backup=None
    try:
        manager_phase('INSTALL',manager_request,'field_local_manager_initialize_v4.py')
        if remaining()<585:raise TimeoutError('Full broker initializer/gate reserve')
        r=ssh_phase([python,'-u','-B','-c',(here/'field_operator_broker_initialize_v1.py').read_text()],
                    payload=encoded(broker_request)+b'\n',timeout=25,maximum=16384)
        rawphase('STAGE',r);rs=rows(r)
        if rs and set(rs[0])=={'owner'}:
            stage_owner=rs[0]['owner'];phase_owners.append(stage_owner);private('STAGE_OWNER.json',encoded(stage_owner));dead([stage_owner],'STAGE')
        if not good(r) or len(rs)!=2 or rs[-1].get('readback_exact') is not True:raise RuntimeError('Broker stage failed')
        if remaining()<570:raise TimeoutError('Full gate freshness')
        gate_attempted=True
        r=ssh_phase([python,'-u','-B',root+'/code/field_operator_broker_gate_v12.py','--root',root,'--policy-sha256',bp_sha],
                    timeout=100,stop_unit='jp-'+Path(root).name,maximum=131072)
        rawphase('GATE',r)
        if not good(r):failures.append('Native gate failed')
    except BaseException as exc:failures.append(type(exc).__name__+': '+str(exc)[:512])
    # Preserve the full source even when qualification failed.
    try:
        partial=None
        if not gate_attempted and stage_owner is not None:
            members={v['path']:v['bytes'] for v in broker_request['manifest']['files']}
            members.update({'RELEASE.json':len(encoded(bp)),'broker/MANIFEST.json':len(encoded(broker_request['manifest'])),'broker/STAGE_OWNER.json':16384})
            partial=dict(source_root=root,policy_sha256=bp_sha,initializer_owner=stage_owner,members=members)
        code=(here/'field_operator_broker_census_v3.py').read_text()+"\nprint(json.dumps(collect("+repr(root)+","+repr(bp)+","+repr(bp_sha)+","+repr([stage_owner] if stage_owner else [])+","+repr(partial)+")),flush=True)\n"
        r=ssh_phase([python,'-u','-B','-c',code],timeout=35,maximum=131072);rawphase('BROKER_CENSUS',r);rs=rows(r)
        if rs and 'utility_owner' in rs[0]:
            phase_owners.append(rs[0]['utility_owner']);dead([rs[0]['utility_owner']],'BROKER_CENSUS')
        if not good(r) or len(rs)!=2:raise RuntimeError('Broker census failed')
        tree=rs[1];store.json('CENSUS.json',tree)
        if tree.get('gate',{}).get('gate_owner'):
            external.append(tree['gate']['gate_owner'])
        phase_owners.extend(tree['owners'])
        if not failures and tree.get('gate',{}).get('logical_success') is True:
            if remaining()<400:raise TimeoutError('Finish plus independent copies reserve')
            for i,phase in enumerate(('finish','reopen')):
                request=dict(manager_request,binding=joint['finish_binding'],phase=phase,
                    prior_pi=all_prior(),unit='jp-field-local-phase-v'+str(args.manager_version*10+i)+'.service')
                manager_phase(phase.upper(),request,'field_local_manager_phase_v2.py')
        elif not failures:failures.append('Gate logical success missing')
        if tree['status']!='NO_TARGET_ROOT':
            if remaining()<370:raise TimeoutError('Both independent PC copies reserve')
            from mirror_field_operator_broker_v3 import MODULES
            def pin(path):
                raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=sha(raw))
            needed=[here/(n+'.py') for n in (*MODULES,'field_operator_broker_host_v2','mirror_field_operator_broker_v3','dispatch_b01_stack_v2','dispatch_geometry_v2')]
            manifest_path=args.output/'host/metadata/CENSUS.json';needed.append(manifest_path)
            a=dict(expires_utc=end.isoformat(),pi_readonly_export=True,capture=False,host_affinity=[14],session_count=1,
              maximum_host_output_bytes=bp['allocation']['target_maximum_bytes']+4194304,mirror_maximum_bytes=bp['allocation']['target_maximum_bytes'],
              target_payload_writes=False,output=str(args.output/'broker-copy'),manifest=str(manifest_path),input_pins=[pin(x) for x in needed],
              module_sha256={n:sha((here/(n+'.py')).read_text().encode()) for n in MODULES},
              coordinator_sha256=pin(here/'mirror_field_operator_broker_v3.py')['sha256'],boot_id=boot,source_relative=Path(root).name,
              export_unit='jp-field-broker-export-v'+str(args.broker_version)+'.service',policy_sha256=bp_sha,partial_initializer=partial,policy=bp,
              install_sha256=cfg['baseline']['install_sha256'],live_config_sha256=cfg['baseline']['live_config_sha256'],
              closed_owners=pack(all_prior()),live_owners=tree['owners'])
            store.json('REVIEW.json',a)
            r=process_phase([sys.executable,'-u','-B',str(here/'mirror_field_operator_broker_v3.py'),
                            '--admission',str(args.output/'host/metadata/REVIEW.json'),'--output',a['output'],
                            '--owner-receipt',str(args.output/'BROKER_MIRROR_OWNER.json')],timeout=140,maximum=16384)
            rawphase('BROKER_MIRROR',r)
            if not good(r) or not (Path(a['output'])/'metadata/BACKUP.json').is_file():raise RuntimeError('Broker PC mirror failed')
            host_owner=json.loads((args.output/'BROKER_MIRROR_OWNER.json').read_bytes())
            try:created=psutil.Process(host_owner['pid']).create_time()
            except psutil.NoSuchProcess:created=None
            if created is not None and abs(created-host_owner['create_time'])<.001:raise RuntimeError('Mirror coordinator remains')
            copy_result=json.loads((Path(a['output'])/'metadata/RESULT.json').read_bytes())
            phase_owners.append(copy_result['remote_owner'])
            closures.append(copy_result['remote_closure']['utility_owner'])
            broker_backup=str(Path(a['output'])/'metadata/BACKUP.json')
    except BaseException as exc:failures.append(type(exc).__name__+': '+str(exc)[:512])
    try:
        # Native exporter binds each completed nested launch to these actual
        # independently closed external phase identities.
        external=list({(v['boot_id'],v['pid'],v['start_ticks']):v for v in external}.values())
        if not external:raise RuntimeError('Missing actual external owner; no invented manager closure')
        from field_local_auxiliary_v1 import STDLIB,analyze
        import ast
        modules={};todo=['field_local_manager_export_v2']
        while todo:
            name=todo.pop()
            if name in modules:continue
            source=(here/(name+'.py')).read_text();modules[name]=source
            for node in ast.walk(ast.parse(source)):
                imports=[x.name.split('.')[0] for x in node.names] if isinstance(node,ast.Import) else ([node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else [])
                todo.extend(n for n in imports if n not in STDLIB and n not in modules)
        modulepins={n:sha(s.encode()) for n,s in modules.items()};analyze(modules,modulepins)
        count=[0]
        def fresh_life():
            count[0]+=1
            return probe('EXPORT_PREFLIGHT_'+str(count[0]))['lifecycle']
        a=dict(schema='just-peachy.manager-export-admission.v1',phase='census',
           issued_utc=issued.isoformat(),expires_utc=end.isoformat(),unit='jp-field-manager-census-v'+str(args.manager_version)+'.service',
           manager_binding=dict(schema='just-peachy.manager-tree-binding.v1',policy=release,policy_sha256=sha(encoded(release)),manifest=manager['manifest']),
           lifecycle=life,lifecycle_sha256=sha(encoded(life)),module_sha256=modulepins,external_owners=external,
           closed_owners=pack(all_prior()),mirror_maximum_bytes=155669036)
        manager_result=session(args.output/'manager-copy',args.output/'manager-copy-closure',owner,a,modules,
              (here/'field_local_auxiliary_v1.py').read_text(),(here/'field_local_manager_bootstrap_v1.py').read_text(),SSH,lifecycle_refresh=fresh_life)
    except BaseException as exc:failures.append(type(exc).__name__+': '+str(exc)[:512])
    result=dict(logical_success=not failures and broker_backup is not None and manager_result is not None,
                failures=failures,broker_backup=broker_backup,manager_result=manager_result,
                phase_owners=phase_owners,closure_owners=closures,external_owners=external,
                native_policy_sha256=sha(encoded(release)),production_entry_ready=False,offline_ready=False,
                remaining_seconds=remaining())
    store.json('RESULT.json',result)
    private('FINAL_RESULT.json',encoded(result))
    print(json.dumps({k:result[k] for k in ('logical_success','failures','production_entry_ready','remaining_seconds')}))
    return int(not result['logical_success'])

if __name__=='__main__':raise SystemExit(main())
