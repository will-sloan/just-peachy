"""Offline local manager; README_RUNTIME_HISTORY_COMPAT_V1.md."""
# Only standard-library imports before native early-owner registration.
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime,timezone

MIB=1024**2
CAMPAIGN=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def owner():return dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def strict(raw):
    def pairs(rows):
        out={}
        for k,v in rows:
            if k in out:raise ValueError('Duplicate JSON key')
            out[k]=v
        return out
    def bad(value):raise ValueError('Nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def read(path,cap=65536):
    path=Path(path)
    for parent in path.parents:
        if parent.is_symlink() or not parent.is_dir():raise ValueError('Real source ancestors')
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>cap:
        raise ValueError('Bounded unique real member')
    raw=path.read_bytes();after=path.lstat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or len(raw)!=before.st_size:
        raise RuntimeError('Source changed during read')
    return raw


def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def publish(path,raw,maximum):
    if len(raw)>maximum:raise ValueError('Allocated publication cap')
    path=Path(path)
    if path.exists() or path.is_symlink():raise FileExistsError('Preserve consumed publication')
    with path.open('xb') as f:
        for offset in range(0,len(raw),16384):
            block=raw[offset:offset+16384]
            if f.write(block)!=len(block):raise OSError('Short publication')
        f.flush();os.fsync(f.fileno())
    sync(path.parent)
    if read(path,maximum)!=raw:raise IOError('Independent publication readback')


def native_limits():
    os.sched_setaffinity(0,{3})
    for kind,limit in ((resource.RLIMIT_AS,128*MIB),(resource.RLIMIT_STACK,MIB),
                       (resource.RLIMIT_FSIZE,32*MIB),(resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(limit,limit))
    if os.uname().machine!='aarch64':raise ValueError('Native CM5 runtime only')
    sys.dont_write_bytecode=True


def verify_manager(root,policy_sha):
    if root.parent!=CAMPAIGN or root.resolve()!=root or not root.name.startswith('field-runtime-v'):
        raise ValueError('Canonical installed runtime root')
    raw=read(root/'control/RELEASE.json')
    if sha(raw)!=policy_sha:raise ValueError('Immutable manager policy pin')
    policy=strict(raw);manifest_raw=read(root/'control/MANIFEST.json',131072)
    if sha(manifest_raw)!=policy['runtime_manifest_sha256']:raise ValueError('Manager manifest drift')
    manifest=strict(manifest_raw);rows=manifest['files']
    if manifest['schema']!='just-peachy.local-release-manifest.v1' or not 1<=len(rows)<=16:
        raise ValueError('Complete finite manager capsule')
    names=set();total=0
    for row in rows:
        path=Path(row['path'])
        if set(row)!={'path','bytes','sha256'} or len(path.parts)!=2 or path.parts[0]!='code' or path.suffix!='.py' or path.as_posix()!=row['path']:
            raise ValueError('Exact manager code pin')
        if path.name.casefold() in names:raise ValueError('Manager case alias')
        names.add(path.name.casefold());data=read(root/path,131072);total+=len(data)
        if type(row['bytes']) is not int or len(data)!=row['bytes'] or sha(data)!=row['sha256']:
            raise ValueError('Manager source pin drift')
    if total>2*MIB or names!={p.name.casefold() for p in (root/'code').iterdir()}:
        raise ValueError('Complete manager code membership')
    return policy


def bootstrap_manager(root,policy_sha):
    # Actual early identity and immutable owner are persisted before project imports.
    native_limits();signal.alarm(60)
    policy=verify_manager(root,policy_sha)
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        who=owner();slots=policy['allocation']['launch_slots'];used=[]
        for index,slot in enumerate(slots):
            directory=root/'launches'/slot;names={p.name for p in directory.iterdir()}
            if not names:continue
            used.append(index)
            if not {'OWNER.json','EXIT.json'}<=names or any(n.endswith('.pending') for n in names):
                raise RuntimeError('Prior unfinished launch requires recovery')
            row=strict(read(directory/'OWNER.json',16384))
            old=row['owner']
            if old['boot_id']==who['boot_id'] and ticks(old['pid'])==old['start_ticks']:
                raise RuntimeError('Prior exact runtime owner is still alive')
        if used!=list(range(len(used))) or len(used)==len(slots):
            raise RuntimeError('Finite launch allocation exhausted or incomplete')
        slot=slots[len(used)]
        row=dict(policy_sha256=policy_sha,slot='launches/'+slot,utc=datetime.now(timezone.utc).isoformat(),
                 owner=who,purpose='USER_RUNTIME_MANAGER')
        target=root/'launches'/slot/'OWNER.json';pending=target.with_name('OWNER.json.pending')
        publish(pending,encoded(row),16384)
        os.link(pending,target,follow_symlinks=False);sync(target.parent);pending.unlink();sync(target.parent)
        if strict(read(target,16384))!=row:raise IOError('Early owner readback')
        sys.path.insert(0,str(root/'code'))
        from field_runtime_journal_v3 import RuntimeJournal
        journal=RuntimeJournal(root,policy_sha,inherited_lock_fd=fd,early_launch=slot)
        fd=None;journal.begin_launch();current_activation(root,policy,journal.owner);signal.alarm(0)
        return journal
    finally:
        if fd is not None:os.close(fd)



def current_activation(root,policy,manager_owner):
    """Check this boot locally; the immutable activation records the original switch."""
    activation=strict(read(root/'control/ACTIVATION.json',65536))
    fields={'schema','policy_sha256','settings_sha256','baseline_owners','baseline_expected','baseline','launch_slot'}
    if type(activation) is not dict or set(activation)!=fields or activation['schema']!='just-peachy.runtime-activation.v1':
        raise ValueError('Exact completed activation required')
    if activation['policy_sha256']!=sha(read(root/'control/RELEASE.json')) or activation['baseline_expected']!='stopped':
        raise ValueError('Production activation requires stopped prior app')
    from field_runtime_policy_v3 import identity
    identity(manager_owner);boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if manager_owner['boot_id']!=boot or ticks(manager_owner['pid'])!=manager_owner['start_ticks']:
        raise RuntimeError('Current boot manager identity changed')
    old=activation['baseline_owners']
    if type(old) is not list or len(old)!=2 or len({encoded(identity(v)) for v in old})!=2:
        raise ValueError('Exact two original baseline identities')
    for prior in old:
        if prior['boot_id']==boot and ticks(prior['pid'])==prior['start_ticks']:
            raise RuntimeError('Prior app remains alive')
    home=Path.home();base=activation['baseline']
    for path,key in ((home/'JustPeachy/install/current.json','install_sha256'),
                     (home/'JustPeachy/data/live_config.json','live_config_sha256')):
        if sha(read(path))!=base[key]:raise RuntimeError('Installed baseline configuration drift')
    settings=read(home/'JustPeachy/data/settings.json')
    if sha(settings)!=activation['settings_sha256'] or strict(settings).get('auto_start_listening') is not False:
        raise RuntimeError('Explicit capture-off startup settings required')
    if sha(read(home/'.config/kanshi/config'))!='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b':
        raise RuntimeError('Saved display270 drift')
    if os.uname().machine!='aarch64' or 'Compute Module 5' not in Path('/proc/device-tree/model').read_text():
        raise RuntimeError('Actual CM5 device required')
    if int(Path('/sys/class/block/mmcblk0/size').read_text())*512!=31268536320:
        raise RuntimeError('Actual32GB device binding')
    # Detect a newly restarted baseline, even when its old boot/PIDs are gone.
    for item in Path('/proc').iterdir():
        if not item.name.isdigit() or int(item.name)==os.getpid():continue
        try:
            with (item/'cmdline').open('rb') as f:argv=f.read(8193).split(b'\0')
        except (FileNotFoundError,PermissionError,ProcessLookupError):continue
        if len(argv)>1 and b'/JustPeachy/install/releases/' in argv[1] and argv[1].endswith((b'/main.py',b'/release_tools/launch_current.py')):
            raise RuntimeError('Another baseline frontend is running')
    statuses=list(Path('/proc/asound').glob('card*/pcm*c/sub*/status'))
    if not statuses or any(p.read_text().strip()!='closed' for p in statuses):
        raise RuntimeError('Capture must be closed at entry')
    for path in (CAMPAIGN/'B05_PREVIEW_DISPATCH.lock',home/'JustPeachy/data/xvf-hardware.lock'):
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        finally:os.close(fd)
    def observation(argv,cap=8192):
        p=subprocess.run(argv,capture_output=True,timeout=5)
        if p.returncode or len(p.stdout)>cap or len(p.stderr)>4096:
            raise RuntimeError('Bounded local startup observation failed')
        return p.stdout.decode()
    unit='jp-'+root.name+'.service';slice_name='jpfield'+root.name.replace('-','')+'.slice'
    props=('MainPID','ActiveState','LimitAS','LimitSTACK','LimitFSIZE','TasksMax','Slice','RuntimeMaxUSec')
    actual=dict(l.split('=',1) for l in observation(['systemctl','--user','show',unit]+[v for k in props for v in ('-p',k)]).splitlines())
    if actual!=dict(MainPID=str(manager_owner['pid']),ActiveState='active',LimitAS='134217728',LimitSTACK='1048576',
                    LimitFSIZE='33554432',TasksMax='64',Slice=slice_name,RuntimeMaxUSec='1d'):
        raise RuntimeError('Actual manager service envelope')
    props=('CPUQuotaPerSecUSec','TasksMax','AllowedCPUs','ActiveState')
    actual_slice=dict(l.split('=',1) for l in observation(['systemctl','--user','show',slice_name]+[v for k in props for v in ('-p',k)]).splitlines())
    if actual_slice!=dict(CPUQuotaPerSecUSec='2s',TasksMax='64',AllowedCPUs='2-3',ActiveState='active'):
        raise RuntimeError('Combined manager and child slice envelope')
    await_installer_exit(root,sha(read(root/'control/RELEASE.json')),observation)
    active=observation(['systemctl','--user','list-units','--state=active,activating,deactivating','--plain','--no-legend','jp-*'],16384)
    if {l.split()[0] for l in active.splitlines() if l.strip()}!={unit}:
        raise RuntimeError('Unexpected active research/runtime unit')
    display=observation(['wlr-randr'])
    if 'Transform: 270' not in display or 'Enabled: yes' not in display:
        raise RuntimeError('Actual enabled display270 required')
    # A new in-memory boot binding is derived only after the observations above.
    result=strict(encoded(activation))
    result['baseline']['boot_id']=boot
    return result



def await_installer_exit(root,policy_sha,observation):
    """Allow only the pinned installation owner to finish its final launch step."""
    reference=strict(read(root/'control/ROLLBACK.json'))
    if type(reference) is not dict or set(reference)!={'schema','path','sha256'} or reference['schema']!='just-peachy.runtime-rollback-reference.v1':
        raise ValueError('Exact rollback reference')
    expected=root.with_name(root.name+'-activation')/'ROLLBACK.json'
    if reference['path']!=str(expected):raise ValueError('Canonical rollback binding')
    raw=read(expected)
    if sha(raw)!=reference['sha256']:raise ValueError('Rollback binding drift')
    binding=strict(raw)
    fields={'schema','release_id','manager_policy_sha256','activation_unit','activation_owner',
            'autostart','launcher_sha256','settings_sha256','source_sha256','baseline_owners',
            'rollback_attempts','reserved_bytes'}
    if type(binding) is not dict or set(binding)!=fields or binding['schema']!='just-peachy.runtime-rollback.v1':
        raise ValueError('Complete rollback binding')
    if binding['release_id']!=root.name or binding['manager_policy_sha256']!=policy_sha:
        raise ValueError('Rollback policy mismatch')
    from field_runtime_policy_v3 import identity
    prior=identity(binding['activation_owner'])
    installer='jp-install-'+root.name+'.service'
    if binding['activation_unit']!=installer:raise ValueError('Exact installation service')
    unit='jp-'+root.name+'.service';end=time.monotonic()+10
    while True:
        active=observation(['systemctl','--user','list-units','--state=active,activating,deactivating','--plain','--no-legend','jp-*'],16384)
        names={line.split()[0] for line in active.splitlines() if line.strip()}
        if names=={unit}:return
        if names!={unit,installer}:raise RuntimeError('Unexpected unit during activation')
        props=dict(line.split('=',1) for line in observation(['systemctl','--user','show',installer,
            '-p','MainPID','-p','ActiveState']).splitlines())
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if prior['boot_id']!=boot or props['MainPID'] not in ('0',str(prior['pid'])):
            raise RuntimeError('Installer identity differs')
        actual=ticks(prior['pid'])
        if props['MainPID']!='0' and actual!=prior['start_ticks']:
            raise RuntimeError('Installer PID was reused')
        if props['ActiveState'] not in ('active','deactivating') or time.monotonic()>=end:
            raise RuntimeError('Exact installer did not finish naturally')
        time.sleep(.05)


def profile_descriptor(root,policy,profile):
    from field_runtime_policy_v3 import PROFILES,pin
    if profile not in PROFILES:raise ValueError('Unknown profile')
    selected=policy['profiles'][profile]
    if not selected['available']:raise ValueError(selected['reason'])
    directory=root.with_name(root.name+'-profiles')
    raw=read(directory/(profile+'.json'),65536)
    if sha(raw)!=selected['manifest_sha256']:raise ValueError('Immutable profile descriptor pin')
    value=strict(raw)
    fields={'schema','profile','template_sha256','runtime_profile','runtime_document'}
    if type(value) is not dict or set(value)!=fields or value['schema']!='just-peachy.runtime-profile-descriptor.v1' or value['profile']!=profile:
        raise ValueError('Exact profile descriptor')
    pin(value['template_sha256'])
    runtime=value['runtime_profile']
    if type(runtime) is not dict or set(runtime)!={'definition','galleries'}:
        raise ValueError('Exact controller profile binding')
    definition=runtime['definition'];route=definition['selection']
    if route['profile']!=profile or route['input_kind']!=selected['input_kind']:
        raise ValueError('Profile input selection differs')
    routes={
        'baseline':('microphone','baseline','E0'),'baseline-titanet':('microphone','baseline','E1'),
        'baseline-anonymous':('microphone','baseline','E0'),'d1-anonymous':('microphone','delayed','E0'),
        'd1-delayed':('microphone','delayed','E0'),'d1-delayed-titanet':('microphone','delayed','E1'),
        'd1-streaming-saved':('saved','streaming','E0'),'d1-streaming-titanet-saved':('saved','streaming','E1'),
        'd1-chunk52-saved':('saved','chunk52','E0'),'d1-chunk52-titanet-saved':('saved','chunk52','E1')}
    expected_input,expected_mode,expected_encoder=routes[profile]
    if route['input_kind']!=expected_input:raise ValueError('Exact saved/microphone route')
    if route['engine_mode']!=expected_mode or route['embedding']!=expected_encoder:
        raise ValueError('Exact selected engine/embedding route')
    if definition['automatic_capture'] is not False or definition['silent_fallback'] is not False:
        raise ValueError('Idle explicit selection required')
    composition_sha=hashlib.sha256(json.dumps(definition['composition'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    if definition['backend_manifest_id']!='sha256:'+composition_sha:raise ValueError('Actual backend composition pin')
    document=value['runtime_document']
    if document.get('schema')!='just-peachy.n2.runtime.v1' or document.get('native_device')!={'kind':'cpu','gpu_index':-1}:
        raise ValueError('Pinned CPU model document')
    if expected_encoder=='E1':
        if not {'titanet_manifest','titanet_manifest_sha256','embedding_namespace'}<=set(document):
            raise ValueError('Explicit TitaNet manifest/namespace required')
    elif {'titanet_manifest','titanet_manifest_sha256','embedding_namespace'}&set(document):
        raise ValueError('E0 profile must not depend on E1')
    return value


def bundle_for_operation(root,policy,operation):
    profile=operation['profile']
    descriptor=profile_descriptor(root,policy,profile)
    asset=root.with_name(root.name+'-profiles')/'COMMON_BUNDLE.json'
    raw=read(asset,MIB)
    if sha(raw)!=descriptor['template_sha256']:raise ValueError('Pinned shared code template')
    value=strict(raw);files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
    rows=value['manifest']['files'];pins={r['path']:r for r in rows}
    if len(pins)!=len(rows) or set(pins)!=set(files):raise ValueError('Complete profile template')
    for name,data in files.items():
        if pins[name]!=dict(path=name,bytes=len(data),sha256=sha(data)):raise ValueError('Profile member drift')
    activation=current_activation(root,policy,operation['owner'])
    config=strict(files['broker/CONFIG.json']);config['baseline']=activation['baseline']
    launch_matches=[]
    for launch_slot in policy['allocation']['launch_slots']:
        path=root/'launches'/launch_slot/'OWNER.json'
        if path.exists() and strict(read(path,16384)).get('owner')==operation['owner']:
            launch_matches.append(launch_slot)
    if len(launch_matches)!=1:raise ValueError('Unique actual current manager launch')
    config['runtime']=dict(root=str(root),policy_sha256=sha(read(root/'control/RELEASE.json')),
        operation_sha256=sha(encoded(operation)),slot=operation['slot'],manager_owner=operation['owner'],
        launch_slot=launch_matches[0],manager_unit='jp-'+root.name+'.service',
        slice='jpfield'+root.name.replace('-','')+'.slice',settings_sha256=activation['settings_sha256'],
        baseline_owners=activation['baseline_owners'],baseline_expected=activation['baseline_expected'])
    template=strict(files['broker/TEMPLATE.json']);a=template['admission']
    a['runtime_profile']=descriptor['runtime_profile']
    selection=descriptor['runtime_profile']['definition']['selection']
    a['capture']=selection['input_kind']=='microphone'
    if selection['diarization']=='D1':
        a['d1_binding']['mode']=selection['engine_mode']
        a['operator_parent']['mode']=selection['engine_mode']
    template['data_files']['n2_runtime.json']=descriptor['runtime_document']
    a.update(boot_id=operation['owner']['boot_id'],created_utc=operation['issued_utc'],
        expires_utc=operation['expires_utc'],quiet_only=False,
        install_sha256=config['baseline']['install_sha256'],live_config_sha256=config['baseline']['live_config_sha256'],
        host_window_bytes=policy['measured_host_bytes'],target_before_bytes=policy['measured_target_bytes'],
        payload_before_bytes=policy['measured_payload_bytes'],
        authority_sha256=sha(files['code/OFFLINE_RUNTIME_AUTHORITY_V1.json']))
    files['broker/CONFIG.json']=encoded(config);files['broker/TEMPLATE.json']=encoded(template)
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[
        dict(path=name,bytes=len(data),sha256=sha(data)) for name,data in sorted(files.items())])
    broker=dict(schema='just-peachy.offline-broker-policy.v1',root=operation['root'],
        issued_utc=operation['issued_utc'],expires_utc=operation['expires_utc'],
        allocation=policy['allocation']['broker_allocation'],combined_output_cap_bytes=policy['combined_output_cap_bytes'],
        total_payload_cap_bytes=policy['total_payload_cap_bytes'],mode=descriptor['runtime_profile']['definition']['selection']['engine_mode'],
        release_manifest_sha256=sha(encoded(manifest)),boot_id=operation['owner']['boot_id'],
        host_window_bytes=policy['measured_host_bytes'],target_before_bytes=policy['measured_target_bytes'],
        payload_before_bytes=policy['measured_payload_bytes'],runtime_policy_sha256=sha(read(root/'control/RELEASE.json')),
        runtime_operation_sha256=sha(encoded(operation)),runtime_root=str(root),slot=operation['slot'],profile=profile)
    from field_runtime_policy_v3 import validate_broker_policy
    validate_broker_policy(broker,policy,operation)
    return broker,config,manifest,files


def stage_phase(root,policy_sha,slot):
    policy=verify_manager(root,policy_sha)
    sys.path.insert(0,str(root/'code'))
    from field_runtime_policy_v3 import validate_operation
    operation=strict(read(root/'recordings'/slot/'RESERVED.json',16384))['operation']
    validate_operation(operation,policy,now=datetime.now(timezone.utc))
    broker,config,manifest,files=bundle_for_operation(root,policy,operation)
    destination=Path(operation['root'])
    if destination.parent!=CAMPAIGN or destination.exists() or destination.is_symlink():
        raise ValueError('Fresh canonical broker destination')
    if not 575<=(datetime.fromisoformat(operation['expires_utc'])-datetime.now(timezone.utc)).total_seconds()<=600:
        raise TimeoutError('Full stage/gate/backup time reservation')
    code=[n for n in files if n.startswith('code/')]
    if len(code)>64 or sum(len(files[n]) for n in code)>2*MIB or any(len(v)>131072 for v in files.values()):
        raise ValueError('Original capsule resource caps')
    import types,shutil
    module=types.ModuleType('runtime_stage_common')
    exec(compile(files['code/field_operator_broker_common_v1.py'],'<runtime-stage-injected:common>','exec'),module.__dict__)
    module.physical(config)
    locks=[]
    try:
        for path in (CAMPAIGN/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock'):
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BaseException:os.close(fd);raise
            locks.append(fd)
        ram=next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
        if ram<850*MIB or shutil.disk_usage(CAMPAIGN).free<5*1024**3+policy['allocation']['target_maximum_bytes']:
            raise RuntimeError('Initial RAM and complete remaining reservation')
        total=int(subprocess.check_output(['du','-sb',str(CAMPAIGN)],timeout=10,text=True).split()[0])
        # Count existing manager and completed independent roots once; retain all full reservations.
        own=int(subprocess.check_output(['du','-sb',str(root)],timeout=10,text=True).split()[0])
        outside=total-own
        for source in policy['recording_roots']:
            p=Path(source)
            if p.exists():outside-=int(subprocess.check_output(['du','-sb',source],timeout=10,text=True).split()[0])
        full=policy['allocation']['combined_request_bytes']
        if (policy['measured_host_bytes']+outside+full>policy['combined_output_cap_bytes']
            or policy['measured_payload_bytes']+max(0,outside-policy['measured_target_bytes'])+full>policy['total_payload_cap_bytes']):
            raise RuntimeError('Fresh target-inclusive complete allocation')
        destination.mkdir();(destination/'code').mkdir();(destination/'broker').mkdir()
        publish(destination/'broker/STAGE_OWNER.json',encoded(owner()),16384)
        publish(destination/'RELEASE.json',encoded(broker),65536)
        publish(destination/'broker/MANIFEST.json',encoded(manifest),131072)
        for name,data in files.items():publish(destination/name,data,65536 if name=='broker/CONFIG.json' else 131072)
        for path in (destination/'code',destination/'broker',destination,CAMPAIGN):sync(path)
        module.bundle(destination)
        return dict(root=str(destination),policy_sha256=sha(encoded(broker)),owner=owner(),
            complete_readback=True,files=len(files))
    finally:
        for fd in locks:os.close(fd)


def copy_phase(root,policy_sha,slot):
    policy=verify_manager(root,policy_sha);sys.path.insert(0,str(root/'code'))
    from field_runtime_policy_v3 import validate_operation
    from field_runtime_backup_v2 import copy_closed
    operation=strict(read(root/'recordings'/slot/'RESERVED.json',16384))['operation']
    validate_operation(operation,policy,now=datetime.now(timezone.utc))
    source=Path(operation['root']);pins={}
    deadline=time.monotonic()+90
    from field_operator_broker_streamed_mirror_v1 import inventory
    observed,_=inventory(source,deadline)
    for name in observed:
        path=source/name;h=hashlib.sha256();count=0
        with path.open('rb') as f:
            while True:
                if time.monotonic()>=deadline:raise TimeoutError('Whole copy preparation deadline')
                data=f.read(16384)
                if not data:break
                h.update(data);count+=len(data)
        pins[name]=dict(bytes=count,sha256=h.hexdigest())
    remaining=(datetime.fromisoformat(operation['expires_utc'])-datetime.now(timezone.utc)).total_seconds()
    if remaining<10:raise TimeoutError('No complete copy reserve')
    return copy_closed(source,root/'backups'/slot,sha(read(source/'RELEASE.json')),
        'jp-'+source.name+'.service',pins,operation=operation,runtime=policy,
        deadline=min(deadline,time.monotonic()+remaining-3),
        maximum_bytes=policy['allocation']['local_backup_per_recording'])


def helper(phase):
    native_limits();signal.alarm(80)
    who=owner()
    print(encoded(dict(type='HELLO',owner=who,phase=phase)).decode(),flush=True)
    line=sys.stdin.buffer.readline(4097)
    if len(line)>4096 or not line.endswith(b'\n'):raise ValueError('Bounded parent acknowledgment')
    request=strict(line)
    if set(request)!={'owner','root','policy_sha256','slot'} or request['owner']!=who:
        raise ValueError('Early helper owner must be durably registered before project imports')
    root=Path(request['root']);policy=verify_manager(root,request['policy_sha256'])
    slot=request['slot']
    if slot not in policy['allocation']['recording_slots']:raise ValueError('Allocated operation')
    if phase=='stage':
        signal.alarm(45);result=stage_phase(root,request['policy_sha256'],slot)
    elif phase=='copy':
        signal.alarm(110);result=copy_phase(root,request['policy_sha256'],slot)
    elif phase=='gate':
        operation=strict(read(root/'recordings'/slot/'RESERVED.json',16384))['operation']
        source=Path(operation['root']);broker=strict(read(source/'RELEASE.json'))
        manifest=strict(read(source/'broker/MANIFEST.json',131072))
        if sha(encoded(manifest))!=broker['release_manifest_sha256']:raise ValueError('Gate manifest')
        for row in manifest['files']:
            raw=read(source/row['path'],131072)
            if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Gate project graph pin')
        sys.path.insert(0,str(source/'code'))
        from field_operator_broker_gate_v8 import main
        signal.alarm(0)
        rc=main(source,sha(read(source/'RELEASE.json')))
        if rc:raise RuntimeError('Broker gate failed; preserve complete tree')
        result=dict(root=str(source),natural_gate_success=True)
    else:raise ValueError('Exact native helper phase')
    raw=encoded(dict(type='RESULT',phase=phase,value=result))
    if len(raw)>262144:raise ValueError('Complete helper result framing cap')
    print(raw.decode(),flush=True)


class Manager:
    def __init__(self,journal,selected):
        import tkinter as tk
        self.journal=journal;self.root=journal.root;self.proc=None;self.phase=None
        self.operation=None;self.child_owner=None;self.helper_slot=None;self.buffer=b'';self.error_bytes=b''
        self.result=None;self.closed=False;self.fault=None;self.started_record=False;self.history_window=None;self.last_history_result=None
        self.stop_requested=False;self.failure_stop_time=None;self.failure_output_discarded=0
        signal.signal(signal.SIGTERM,lambda signum,frame:setattr(self,'stop_requested',True))
        self.ui=tk.Tk(screenName=':0');self.ui.withdraw();self.ui.title('Just Peachy')
        self.ui.geometry('480x800+0+0')
        self.ui.configure(bg='#111827')
        tk.Label(self.ui,text='Just Peachy',fg='white',bg='#111827',font=('DejaVu Sans',24)).pack(pady=18)
        tk.Label(self.ui,text='Offline recording',fg='white',bg='#111827',font=('DejaVu Sans',16)).pack()
        self.status=tk.Label(self.ui,text='Capture is off',fg='white',bg='#111827',wraplength=440,font=('DejaVu Sans',13))
        self.status.pack(pady=15)
        profile_frame=tk.Frame(self.ui,bg='#111827');profile_frame.pack(fill='x',padx=16)
        self.profiles=tk.Listbox(profile_frame,font=('DejaVu Sans',13),height=7,exportselection=False)
        scrollbar=tk.Scrollbar(profile_frame,orient='vertical',command=self.profiles.yview,width=28)
        self.profiles.configure(yscrollcommand=scrollbar.set)
        self.profiles.pack(side='left',fill='x',expand=True);scrollbar.pack(side='right',fill='y')
        self.names=list(journal.policy['profiles'])
        for name in self.names:
            row=journal.policy['profiles'][name]
            mode='Streaming' if 'streaming' in name else 'Chunk52' if 'chunk52' in name else 'Delayed'
            diarizer='D1 '+mode if name.startswith('d1-') else 'Baseline'
            embedding='TitaNet' if 'titanet' in name else ('Anonymous' if name=='d1-anonymous' else 'ReDimNet anonymous') if name.endswith('-anonymous') else 'ReDimNet'
            label=diarizer+' / '+embedding+' / '+('WAV' if name.endswith('-saved') else 'Mic')
            self.profiles.insert('end',label+('' if row['available'] else ' - unavailable'))
        if selected not in self.names:raise ValueError('Unknown shortcut profile')
        self.profiles.selection_set(self.names.index(selected));self.profiles.see(self.names.index(selected))
        if not journal.policy['profiles'][selected]['available']:
            self.status.configure(text=journal.policy['profiles'][selected]['reason'])
        self.start=tk.Button(self.ui,text='New recording',command=self.new,font=('DejaVu Sans',16),height=2)
        self.start.pack(fill='x',padx=16,pady=18)
        self.notice=tk.Label(self.ui,text='Mic/Chunk52: up to 120s. Streaming WAV: 30s.\nChoose Audio off or Processed, then Start/Stop.\nA verified local copy is kept before the next slot.',fg='white',bg='#111827',wraplength=440,font=('DejaVu Sans',12))
        self.notice.pack(pady=8)
        self.history_button=tk.Button(self.ui,text='Saved recordings',command=self.history,font=('DejaVu Sans',14),height=2)
        self.history_button.pack(fill='x',padx=16,pady=5)
        self.exit=tk.Button(self.ui,text='Close',command=self.close,font=('DejaVu Sans',16),height=2)
        self.exit.pack(side='bottom',fill='x',padx=16,pady=18)
        self.ui.protocol('WM_DELETE_WINDOW',self.close)
        self.ui.report_callback_exception=lambda k,v,t:self.fail(k.__name__+': '+str(v))
        self.refresh();self.show()


    def show(self):
        root=self.ui
        root.attributes('-fullscreen',False)
        root.minsize(480,800);root.maxsize(480,800);root.geometry('480x800+0+0')
        root.deiconify();root.update()
        if self.closed:return
        root.geometry('480x800+0+0');root.attributes('-fullscreen',True);root.lift();root.update()
        if self.closed:return
        end=time.monotonic()+3;stable=0
        while time.monotonic()<end:
            root.update()
            if self.closed:return
            exact=(root.winfo_viewable() and root.winfo_ismapped() and root.winfo_geometry()=='480x800+0+0' and root.winfo_rootx()==root.winfo_rooty()==0)
            stable=stable+1 if exact else 0
            if stable>=10:return
            time.sleep(.02)
        raise RuntimeError('Manager fullscreen geometry did not settle')

    def refresh(self):
        rows=self.journal.inspect()
        count=sum(bool(rows['recordings/'+s]) for s in self.journal.plan['recording_slots'])
        self.status.configure(text='Capture is off. '+str(len(self.journal.plan['recording_slots'])-count)+' recording slots remain.')
        self.start.configure(state='normal' if count<len(self.journal.plan['recording_slots']) else 'disabled')


    def history_journal(self, path):
        from field_runtime_journal_v3 import RuntimeJournal
        if path == self.root:
            return self.journal, False
        raw=read(path/'control/RELEASE.json')
        policy=verify_manager(path,sha(raw))
        journal=RuntimeJournal(path,sha(raw))
        try:
            # Read-only history must preserve the original closed-receipt schema.
            # Earlier journals did not include broker/RESULT.json in source_pins.
            legacy=read(path/'code/field_runtime_journal_v3.py',131072)
            current=read(self.root/'code/field_runtime_journal_v3.py',131072)
            if legacy!=current:
                if sha(legacy)!='3ff6f58e33701f2d5b532a4aae81794d0e5b38552af7dbc927fe67ad4c765f37':
                    raise ValueError('Historical journal reader version is unavailable')
                import types
                tree=ast.parse(legacy)
                cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RuntimeJournal')
                method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_closed_source')
                namespace=dict(RuntimeJournal._closed_source.__globals__)
                exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),
                    '<pinned-historical-journal-read-only>','exec'),namespace)
                journal._closed_source=types.MethodType(namespace['_closed_source'],journal)
            rows=journal.inspect();who=owner()
            for slot in journal.plan['launch_slots']:
                item=rows['launches/'+slot]
                if not item:continue
                prior=item.get('OWNER',{}).get('owner')
                from field_runtime_policy_v3 import identity
                identity(prior)
                if prior['boot_id']==who['boot_id'] and ticks(prior['pid'])==prior['start_ticks']:
                    raise RuntimeError('Historical manager/helper still alive')
            return journal, True
        except BaseException:
            journal.close();raise

    def history(self):
        if self.proc is not None or self.fault or self.history_window is not None:return
        import tkinter as tk
        self.journal._physical_idle()
        window=tk.Toplevel(self.ui);self.history_window=window
        window.title('Saved recordings');window.geometry('480x800+0+0')
        window.attributes('-fullscreen',True);window.configure(bg='#111827')
        tk.Label(window,text='Saved recordings',font=('DejaVu Sans',20),bg='#111827',fg='white').pack(pady=12)
        message=tk.Label(window,text='Reading closed recording indexes...',wraplength=440,bg='#111827',fg='white')
        message.pack(pady=8)
        frame=tk.Frame(window);frame.pack(fill='x',padx=12)
        listing=tk.Listbox(frame,height=8,font=('DejaVu Sans',11),exportselection=False)
        scroll=tk.Scrollbar(frame,width=28,command=listing.yview);listing.configure(yscrollcommand=scroll.set)
        listing.pack(side='left',fill='x',expand=True);scroll.pack(side='right',fill='y')
        body=tk.Text(window,height=15,wrap='word',font=('DejaVu Sans',11),state='disabled')
        body.pack(fill='both',expand=True,padx=12,pady=8)
        rows=[];unavailable=[];deadline=time.monotonic()+30
        try:
            roots=[p for p in CAMPAIGN.iterdir() if re.fullmatch(r'field-runtime-v[1-9][0-9]*',p.name)]
            if len(roots)>64:raise ValueError('History batch listing cap')
            roots.sort(key=lambda p:int(p.name.rsplit('v',1)[1]),reverse=True)
            for path in roots:
                if time.monotonic()>=deadline:raise TimeoutError('History listing deadline')
                other=None;owned=False
                try:
                    other,owned=self.history_journal(path)
                    records=other.inspect()
                    for slot in reversed(other.plan['recording_slots']):
                        record=records['recordings/'+slot]
                        if set(record)!={'RESERVED','STARTED','CLOSED','BACKUP'}:continue
                        if record['CLOSED'].get('recording_created') is False:continue
                        operation=record['RESERVED']['operation']
                        rows.append(dict(manager=str(path),policy_sha256=other.policy_sha,slot=slot,
                            profile=operation['profile'],closed_sha256=sha(read(path/'recordings'/slot/'CLOSED.json'))))
                        listing.insert('end',path.name+' / '+slot+' / '+operation['profile'])
                        if len(rows)>256:raise ValueError('History recording listing cap')
                except (OSError,ValueError,RuntimeError) as exc:
                    unavailable.append(path.name+': '+type(exc).__name__)
                finally:
                    if other is not None and owned:other.close()
            message.configure(text=str(len(rows))+' closed recordings. '+str(len(unavailable))+
                ' preserved batches unavailable. Select a recording and Open.')
        except Exception as exc:
            message.configure(text='History unavailable: '+str(exc)[:160])
        def back():
            self.history_window=None
            window.destroy()
            if not self.closed:self.refresh()
        def open_selected():
            selection=listing.curselection()
            if len(selection)!=1:message.configure(text='Select a saved recording.');return
            selected=rows[selection[0]];other=None;owned=False
            try:
                self.journal._physical_idle()
                other,owned=self.history_journal(Path(selected['manager']))
                if other.policy_sha!=selected['policy_sha256']:raise ValueError('History policy changed')
                slot=selected['slot'];control=other.root/'recordings'/slot
                if sha(read(control/'CLOSED.json'))!=selected['closed_sha256']:raise ValueError('History closure changed')
                record=other.inspect()['recordings/'+slot]
                fact=other.verify_closed_backup(slot,record)
                source=Path(fact['binding']['source'])
                config=strict(read(source/'broker/CONFIG.json',65536))
                if config['installed_manifest_sha256']!=other.policy['installed_manifest_sha256']:
                    raise ValueError('Installed history release binding')
                parent=source/'recordings/slot-01/data/conversations'
                folders=list(parent.iterdir())
                if len(folders)!=1:raise ValueError('One source conversation')
                folder=folders[0]
                raw=history_bytes(folder/'conversation.json',65536,time.monotonic()+5)
                result=history_open(Path(config['installed_release']),config['installed_manifest_sha256'],
                    folder,dict(bytes=len(raw),sha256=sha(raw)),deadline=time.monotonic()+45)
                lines=[str(result['metadata'].get('title') or folder.name),
                    'Profile: '+selected['profile'],'Audio: '+('Processed' if result['audio_recorded'] else 'Off'),
                    'Saved: '+str(result['metadata'].get('created_utc','')),
                    'Read only. Recording files and local backup verified.','']
                for row in result['rows']:
                    text=row.get('archived_final_formatted_text') or row.get('archived_provisional_display_text') or row.get('text') or row.get('caption') or ''
                    lines.append(str(row.get('source_start_sec',''))+' - '+str(row.get('source_end_sec',''))+
                        '  '+str(row.get('speaker_name') or row.get('speaker_label') or 'Unknown')+'\n'+str(text)+'\n')
                if not result['rows']:lines.append('No caption rows were recorded for this session.')
                output='\n'.join(lines)
                if len(output.encode('utf-8'))>262144:raise ValueError('History display bound')
                body.configure(state='normal');body.delete('1.0','end');body.insert('end',output);body.configure(state='disabled')
                message.configure(text=str(len(result['rows']))+' caption rows. Capture remains off.')
                self.last_history_result=dict(manager=selected['manager'],slot=slot,rows=len(result['rows']),
                    audio_recorded=result['audio_recorded'],read_only=True,capture_started=False)
            except Exception as exc:
                message.configure(text='Preserved recording unavailable: '+str(exc)[:160])
            finally:
                if other is not None and owned:other.close()
        tk.Button(window,text='Open selected recording',command=open_selected,font=('DejaVu Sans',13),height=2).pack(fill='x',padx=12,pady=4)
        tk.Button(window,text='Back',command=back,font=('DejaVu Sans',15),height=2).pack(fill='x',padx=12,pady=8)
        window.protocol('WM_DELETE_WINDOW',back)
        self.start.configure(state='disabled')

    def new(self):
        if self.proc is not None or self.fault or self.history_window is not None:return
        selection=self.profiles.curselection()
        if len(selection)!=1:self.status.configure(text='Select a recording profile.');return
        profile=self.names[selection[0]];row=self.journal.policy['profiles'][profile]
        if not row['available']:self.status.configure(text=row['reason']);return
        profile_descriptor(self.root,self.journal.policy,profile)
        self.operation=self.journal.reserve_recording(profile)
        self.start.configure(state='disabled');self.status.configure(text='Preparing the recording screenÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦')
        self.spawn('stage')

    def spawn(self,phase):
        self.phase=phase;self.child_owner=None;self.helper_slot=None;self.buffer=b'';self.error_bytes=b'';self.result=None
        self.stdout_eof=False;self.stderr_eof=False
        self.phase_start=time.monotonic()
        self.proc=subprocess.Popen([sys.executable,'-B',str(Path(__file__)), '--helper',phase],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0,close_fds=True)
        os.set_blocking(self.proc.stdout.fileno(),False);os.set_blocking(self.proc.stderr.fileno(),False)

    def register(self,who):
        from field_runtime_policy_v3 import identity
        identity(who)
        if who!=dict(pid=self.proc.pid,start_ticks=ticks(self.proc.pid),boot_id=owner()['boot_id']):
            raise ValueError('Exact actual helper process before payload')
        rows=self.journal.inspect();used=[]
        for i,slot in enumerate(self.journal.plan['launch_slots']):
            r=rows['launches/'+slot]
            if not r:continue
            used.append(i)
            if slot==self.journal.launch_slot:continue
            if set(r)!={'OWNER','EXIT'}:raise RuntimeError('Unclosed earlier helper')
            prior=r['OWNER']['owner']
            if prior['boot_id']==who['boot_id'] and ticks(prior['pid'])==prior['start_ticks']:
                raise RuntimeError('Earlier helper is still alive')
        slots=self.journal.plan['launch_slots']
        if used!=list(range(len(used))) or len(used)==len(slots):raise RuntimeError('Helper launches exhausted')
        slot=slots[len(used)]
        self.journal._publish('launches/'+slot,'OWNER',dict(owner=who,purpose='USER_RUNTIME_'+self.phase.upper()))
        self.child_owner=who;self.helper_slot=slot
        packet=encoded(dict(owner=who,root=str(self.root),policy_sha256=self.journal.policy_sha,
            slot=self.operation['slot']))+b'\n'
        if len(packet)>4096:raise ValueError('Bounded helper payload')
        if self.proc.stdin.write(packet)!=len(packet):raise IOError('Incomplete helper acknowledgment')
        self.proc.stdin.close()

    def poll(self):
        if self.proc is None:return
        limit={'stage':55,'gate':570,'copy':120}[self.phase]
        if time.monotonic()-self.phase_start>limit:raise TimeoutError('Native phase deadline')
        for pipe,is_error in ((self.proc.stdout,False),(self.proc.stderr,True)):
            while True:
                data=pipe.read(16384)
                if data is None:break
                if not data:
                    if is_error:self.stderr_eof=True
                    else:self.stdout_eof=True
                    break
                if is_error:
                    if len(self.error_bytes)+len(data)>8192:raise RuntimeError('Bounded helper stderr overflow')
                    self.error_bytes+=data
                else:
                    self.buffer+=data
                    if len(self.buffer)>262145:raise RuntimeError('Bounded helper frame overflow')
                    while b'\n' in self.buffer:
                        line,self.buffer=self.buffer.split(b'\n',1)
                        if not line:raise ValueError('Empty helper frame')
                        value=strict(line)
                        if value.get('type')=='HELLO':
                            if self.child_owner is not None or value.get('phase')!=self.phase:raise ValueError('Duplicate helper identity')
                            self.register(value['owner'])
                        elif value.get('type')=='RESULT':
                            if self.result is not None or value.get('phase')!=self.phase:raise ValueError('Duplicate helper result')
                            self.result=value['value']
                        elif self.phase!='gate' or set(value)!={'logical_success','returncode','failure'}:
                            raise ValueError('Unknown helper output')
        if self.phase=='gate' and not self.started_record:
            source=Path(self.operation['root'])
            if (source/'broker/ENVELOPE.json').exists():
                self.journal.recording_started(self.operation['slot']);self.started_record=True
        if self.proc.poll() is None:return
        if not (self.stdout_eof and self.stderr_eof):return
        rc=self.proc.wait(timeout=1)
        if self.child_owner is None or ticks(self.child_owner['pid'])==self.child_owner['start_ticks']:
            raise RuntimeError('Exact helper closure unverified')
        if self.buffer or rc or self.result is None or self.error_bytes:
            raise RuntimeError('Helper failed: '+self.error_bytes.decode(errors='replace')[-1024:])
        self.proc.stdout.close();self.proc.stderr.close()
        self.journal._publish('launches/'+self.helper_slot,'EXIT',dict(owner=self.child_owner,
            purpose='USER_RUNTIME_'+self.phase.upper(),natural_returncode=rc,exact_process_dead=True))
        phase=self.phase;result=self.result;self.proc=None
        if phase=='stage':
            self.ui.withdraw();self.started_record=False;self.spawn('gate')
        elif phase=='gate':
            self.journal.recording_closed(self.operation['slot'])
            self.show();self.status.configure(text='Recording closed. Verifying the local backupÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦')
            self.spawn('copy')
        else:
            self.journal.accept_local_backup(self.operation['slot'],result)
            self.operation=None;self.refresh()

    def fail(self,reason):
        if self.fault:return
        self.fault=str(reason)[:512]
        self.failure_stop_time=time.monotonic()
        # Target only the current exact owned child/unit. Preserve failure evidence.
        if self.operation is not None:
            unit='jp-'+Path(self.operation['root']).name+'.service'
            subprocess.run(['systemctl','--user','stop','--no-block',unit],timeout=5,check=False)
        if self.phase!='gate' and self.proc is not None and self.child_owner and ticks(self.child_owner['pid'])==self.child_owner['start_ticks']:
            self.proc.terminate()
        self.start.configure(state='disabled');self.show()
        self.status.configure(text='Recording stopped. Preserved files need recovery. '+self.fault)

    def failure_poll(self):
        if self.proc is None:return
        for pipe in (self.proc.stdout,self.proc.stderr):
            if pipe.closed:continue
            while True:
                data=pipe.read(16384)
                if not data:break
                keep=min(len(data),max(0,8192-len(self.error_bytes)))
                self.error_bytes+=data[:keep];self.failure_output_discarded+=len(data)-keep
        if self.proc.poll() is None:
            if time.monotonic()-self.failure_stop_time<35:return
            if self.child_owner and ticks(self.child_owner['pid'])==self.child_owner['start_ticks']:
                self.proc.kill()
            elif self.child_owner is None:
                # Popen's unreaped child handle is exact even if HELLO failed.
                self.proc.kill()
            return
        rc=self.proc.wait(timeout=1)
        for pipe in (self.proc.stdout,self.proc.stderr):
            if not pipe.closed:pipe.close()
        if self.proc.stdin and not self.proc.stdin.closed:self.proc.stdin.close()
        if self.child_owner and ticks(self.child_owner['pid'])==self.child_owner['start_ticks']:
            raise RuntimeError('Failed helper exact identity remains alive')
        if self.helper_slot:
            try:
                self.journal._publish('launches/'+self.helper_slot,'FAILURE',dict(reason=self.fault,
                    bounded_output=self.error_bytes.decode(errors='replace'),discarded_bytes=self.failure_output_discarded))
                self.journal._publish('launches/'+self.helper_slot,'EXIT',dict(owner=self.child_owner,
                    purpose='USER_RUNTIME_'+self.phase.upper(),returncode=rc,exact_process_dead=True,
                    successful=False))
            except BaseException:
                pass  # Preserved pending/failed publication continues to fence recovery.
        self.proc=None

    def close(self):
        if self.history_window is not None:
            self.history_window.destroy();self.history_window=None;self.refresh();return
        if self.proc is not None:
            self.status.configure(text='Return from the recording screen and wait for the backup first.');return
        if self.fault:
            self.journal._physical_idle()
            try:
                self.journal._publish('launches/'+self.journal.launch_slot,'FAILURE',dict(reason=self.fault,recovery_required=True))
                self.journal._publish('launches/'+self.journal.launch_slot,'EXIT',dict(owner=self.journal.owner,
                    status='RECOVERY_REQUIRED_CAPTURE_OFF',exit_is_intent=True,successful=False))
            finally:
                self.closed=True;self.ui.destroy();self.journal.close()
            return
        self.journal.end_launch();self.closed=True
        try:self.ui.destroy()
        finally:self.journal.close()

    def run(self):
        while not self.closed:
            try:
                if self.stop_requested and not self.fault:self.fail('Runtime service Stop requested')
                if self.fault:self.failure_poll()
                else:self.journal._live();self.poll()
                self.ui.update()
                if self.closed:break
                if self.stop_requested and self.proc is None:self.close()
            except BaseException as exc:self.fail(type(exc).__name__+': '+str(exc))
            time.sleep(.01)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path);parser.add_argument('--policy-sha256')
    parser.add_argument('--profile',default='d1-delayed');parser.add_argument('--helper',choices=('stage','gate','copy'))
    args=parser.parse_args()
    if args.helper:return helper(args.helper)
    if args.root is None or args.policy_sha256 is None:parser.error('Installed root and exact policy SHA required')
    journal=bootstrap_manager(args.root,args.policy_sha256)
    print(encoded(dict(offline_socket_proof=offline_socket_check())).decode(),flush=True)
    Manager(journal,args.profile).run()


def offline_socket_check():
    """Verify this process has no inherited Internet socket and cannot create one."""
    import errno
    import socket
    from pathlib import Path
    import os
    status = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            status[k] = v.strip()
    if status.get('NoNewPrivs') != '1' or status.get('Seccomp') != '2':
        raise RuntimeError('Actual kernel socket restriction missing')
    local = set()
    for name, column in (('unix', 6), ('netlink', 9)):
        raw = Path('/proc/net', name).read_bytes()
        if len(raw) > 262144:
            raise ValueError('Bounded inherited-socket census')
        for line in raw.decode().splitlines()[1:]:
            parts = line.split()
            if len(parts) > column:
                local.add(parts[column])
    inherited = 0
    for fd in Path('/proc/self/fd').iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        if target.startswith('socket:['):
            if target[8:-1] not in local:
                raise RuntimeError('Inherited nonlocal socket rejected')
            inherited += 1
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.close()
    denied = {}
    for family, kind in ((socket.AF_INET, socket.SOCK_STREAM), (socket.AF_INET6, socket.SOCK_DGRAM)):
        try:
            probe = socket.socket(family, kind)
        except OSError as exc:
            if exc.errno not in (errno.EAFNOSUPPORT, errno.EPERM, errno.EACCES):
                raise
            denied[str(int(family))] = exc.errno
        else:
            probe.close()
            raise RuntimeError('Internet socket creation was not denied')
    return dict(schema='just-peachy.offline-sockets.v1',pid=os.getpid(),
        seccomp=2,no_new_privileges=True,ipv4_ipv6_socket_denied=denied,
        inherited_local_sockets=inherited,physical_disconnect_tested=False)

"""Read-only historical compact recordings; README_RUNTIME_HISTORY_V1.md."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager

_HISTORY_STATE = threading.local()
_HISTORY_AUDIT_INSTALLED = False
_HISTORY_CAPS = {'conversation.json':65536, 'epoch.json':65536,
    'events.jsonl':16777216, 'resources.jsonl':2097152, 'windows.jsonl':2097152,
    'model_input.f32le':8388608, 'model_input.wav':4194304}


def _history_audit(event, args):
    if not getattr(_HISTORY_STATE, 'reading', False): return
    if event == 'open':
        mode, flags = args[1:3]
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise PermissionError('History cannot open a writer')
    if event in {'os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink',
                 'os.chmod','os.chown','os.truncate','os.utime','sqlite3.connect','subprocess.Popen','os.system'}:
        raise PermissionError('History cannot mutate or launch')


@contextmanager
def history_reading():
    import sys
    global _HISTORY_AUDIT_INSTALLED
    if not _HISTORY_AUDIT_INSTALLED:
        sys.addaudithook(_history_audit); _HISTORY_AUDIT_INSTALLED = True
    if getattr(_HISTORY_STATE,'reading',False): raise RuntimeError('Nested history read')
    _HISTORY_STATE.reading = True
    try: yield
    finally: _HISTORY_STATE.reading = False


def history_bytes(path, maximum, deadline):
    if time.monotonic() >= deadline: raise TimeoutError('History read deadline')
    path = Path(path)
    for parent in (path.parent,*path.parents):
        if parent.is_symlink() or not parent.is_dir(): raise ValueError('Real history ancestors')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
        raise ValueError('History file bound or type')
    raw = path.read_bytes(); after = path.lstat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) != (
            after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or len(raw) != before.st_size:
        raise RuntimeError('History changed during read')
    return raw


def history_json(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result: raise ValueError('Duplicate history JSON key')
            result[key] = value
        return result
    def bad(value): raise ValueError('Nonfinite history JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def history_census(folder, deadline):
    folder = Path(folder)
    result = {}; directories = []
    for base,names,files in os.walk(folder,followlinks=False):
        if time.monotonic() >= deadline: raise TimeoutError('History census deadline')
        parent=Path(base)
        if parent.is_symlink() or not parent.is_dir(): raise ValueError('Linked history folder')
        directories.append(parent.relative_to(folder).as_posix())
        if len(directories)>3: raise ValueError('One history epoch only')
        for name in names:
            path=parent/name
            if path.is_symlink() or not path.is_dir(): raise ValueError('Linked history child')
        for name in files:
            if name not in _HISTORY_CAPS: raise ValueError('Unknown history member')
            path=parent/name;relative=path.relative_to(folder).as_posix()
            if name=='conversation.json':
                if relative!=name: raise ValueError('History metadata location')
            elif not re.fullmatch(r'epochs/[0-9a-f]{32}/'+re.escape(name),relative):
                raise ValueError('History epoch path')
            before=path.lstat()
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>_HISTORY_CAPS[name]:
                raise ValueError('History member type or ceiling')
            h=hashlib.sha256();count=0
            with path.open('rb') as stream:
                while True:
                    if time.monotonic()>=deadline: raise TimeoutError('History hash deadline')
                    block=stream.read(16384)
                    if not block:break
                    h.update(block);count+=len(block)
            after=path.lstat()
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or count!=before.st_size:
                raise RuntimeError('History hash changed')
            result[relative]=dict(bytes=count,sha256=h.hexdigest())
            if len(result)>7:raise ValueError('History file count')
    if len(result) not in (5,7) or sum(v['bytes'] for v in result.values())>31*1024**2:
        raise ValueError('Complete Off or Processed history required')
    return result


def history_decoder(release, manifest_sha256, deadline):
    """Compile unchanged installed reader methods only; no model/store constructor."""
    release=Path(release)
    raw=history_bytes(release/'RELEASE_MANIFEST.json',262144,deadline)
    if hashlib.sha256(raw).hexdigest()!=manifest_sha256:raise ValueError('History installed manifest drift')
    manifest=history_json(raw);pins={r['path']:r for r in manifest['files']}
    if len(pins)!=len(manifest['files']):raise ValueError('Duplicate installed member')
    selected={'native/field_artifact_limits_v1.py':('validate','resolved','digest'),
              'app/bounded_live_artifacts_v1.py':('encoded',),
              'app/app_bounded_artifacts_v1.py':('compact_records','compact_rows'),
              'app/sessions.py':('folder','metadata','epoch','_quiet','list','iter_rows','rows')}
    sources={};trees={}
    for name in selected:
        raw=history_bytes(release/name,262144,deadline);pin=pins[name]
        if len(raw)!=pin['bytes'] or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Installed history reader drift')
        sources[name]=raw;trees[name]=ast.parse(raw)
    ns=dict(__builtins__=__builtins__,Path=Path,hashlib=hashlib,json=json,copy=copy,
        deepcopy=copy.deepcopy,OrderedDict=OrderedDict,re=re,threading=threading,MIB=1024**2,RATE=16000,
        read_json=lambda p:history_json(history_bytes(p,65536,deadline)),
        size_tree=lambda p:sum(v['bytes'] for v in history_census(p,deadline).values()))
    limits=trees['native/field_artifact_limits_v1.py']
    nodes=[n for n in limits.body if isinstance(n,ast.Assign) and any(
        isinstance(t,ast.Name) and t.id in ('MIB','SCHEMA','DEFAULT') for t in n.targets)]
    for name,names in selected.items():
        tree=trees[name]
        if name=='app/sessions.py':
            cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SessionStore')
            methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
            if {n.name for n in methods}!=set(names):raise ValueError('Installed history method set')
            nodes.append(ast.ClassDef(name='SessionStore',bases=[],keywords=[],body=methods,decorator_list=[]))
        else:
            found=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
            if {n.name for n in found}!=set(names):raise ValueError('Installed decoder function set')
            nodes.extend(found)
    # Nodes are the actual original AST bodies. Imports and constructors are excluded.
    module=ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[]))
    exec(compile(module,'<pinned-installed-history-readers>','exec'),ns)
    return ns,sources


def history_open(release,manifest_sha256,folder,metadata_pin,*,deadline):
    folder=Path(folder);identifier=folder.name
    if not re.fullmatch('[0-9a-f]{32}',identifier):raise ValueError('History conversation ID')
    with history_reading():
        before=history_census(folder,deadline)
        if before['conversation.json']!=metadata_pin:raise ValueError('Closed history metadata pin changed')
        metadata=history_json(history_bytes(folder/'conversation.json',65536,deadline))
        if metadata.get('id')!=identifier or metadata.get('state')!='SAVED' or metadata.get('pinned') is not True:
            raise ValueError('Saved pinned history only')
        epochs=metadata.get('epochs')
        if type(epochs) is not list or len(epochs)!=1 or not re.fullmatch('[0-9a-f]{32}',epochs[0]):
            raise ValueError('One complete epoch')
        epoch=history_json(history_bytes(folder/'epochs'/epochs[0]/'epoch.json',65536,deadline))
        if epoch.get('event_format')!='compact-patch-v1' or epoch.get('state')!='CLOSED' or epoch.get('worker_alive') or epoch.get('archive_error'):
            raise ValueError('Closed compact history only')
        expected={'conversation.json'}|{'epochs/'+epochs[0]+'/'+n for n in ('epoch.json','events.jsonl','resources.jsonl','windows.jsonl')}
        audio={'epochs/'+epochs[0]+'/'+n for n in ('model_input.f32le','model_input.wav')}
        if set(before) not in (expected,expected|audio):raise ValueError('Complete exact archive membership')
        ns,sources=history_decoder(release,manifest_sha256,deadline)
        store=ns['SessionStore'].__new__(ns['SessionStore'])
        store.root=folder.parent;store.active={};store.lock=threading.RLock()
        # Source binding restricts this parent to one recorded conversation.
        if {p.name for p in folder.parent.iterdir()}!={identifier}:raise ValueError('One source conversation')
        listing=store.list()
        if len(listing)!=1 or listing[0]['id']!=identifier:raise ValueError('Installed list selection')
        rows=store.rows(identifier,limit=512)
        if len(rows)>512:raise ValueError('History row cap')
        if time.monotonic()>=deadline:raise TimeoutError('History decode deadline')
        if history_census(folder,deadline)!=before:raise RuntimeError('History files changed')
        for name,raw in sources.items():
            if history_bytes(Path(release)/name,262144,deadline)!=raw:raise RuntimeError('Installed reader changed')
    return dict(metadata=listing[0],rows=rows,member_pins=before,read_only=True,
        capture_started=False,constructor_called=False,audio_recorded=bool(set(before)&audio))


if __name__=='__main__':main()
