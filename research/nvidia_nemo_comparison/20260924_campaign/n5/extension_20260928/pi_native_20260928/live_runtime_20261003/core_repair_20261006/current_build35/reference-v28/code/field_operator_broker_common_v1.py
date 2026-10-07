"""Pinned broker envelope helpers; README_FIELD_OPERATOR_BROKER_NATIVE_V1.md."""
from datetime import datetime,timezone
import os
from pathlib import Path
import shutil
import time
from field_operator_session_plan_v3 import validate_policy
from field_operator_session_ledger_v4 import read,file_pin,identity,ticks
from field_operator_broker_files_v2 import inspect

def ready(root,name,check,timeout=2):
    path=Path(root)/'broker'/name;until=time.monotonic()+timeout
    while True:
        check()
        if path.exists() and not path.with_name(name+'.pending').exists() and path.stat().st_nlink==1:
            return read(path,128*1024)
        if time.monotonic()>=until:raise TimeoutError('Bounded immutable publication barrier: '+name)
        time.sleep(.002)

def bundle(root):
    root=Path(root)
    policy=validate_policy(read(root/'RELEASE.json'))
    if policy['root']!=str(root):raise ValueError('Exact root')
    if file_pin(root/'broker/MANIFEST.json')['sha256']!=policy['release_manifest_sha256']:
        raise ValueError('Broker capsule manifest drift')
    manifest=read(root/'broker/MANIFEST.json',128*1024)
    if set(manifest)!={'schema','files'} or manifest['schema']!='just-peachy.broker-capsule.v1':
        raise ValueError('Exact capsule schema')
    expected={}
    for row in manifest['files']:
        if set(row)!={'path','bytes','sha256'}:raise ValueError('Exact capsule pin')
        name=row['path'];parts=Path(name).parts
        if len(parts)!=2 or parts[0] not in ('code','broker') or '..' in parts:
            raise ValueError('Capsule pin escape')
        if parts[0]=='broker' and parts[1] not in ('CONFIG.json','TEMPLATE.json'):
            raise ValueError('Immutable configuration pin')
        if name in expected:raise ValueError('Duplicate capsule pin')
        if file_pin(root/name)!=dict(bytes=row['bytes'],sha256=row['sha256']):
            raise ValueError('Capsule byte drift')
        expected[name]=row
    actual={'code/'+p.name for p in (root/'code').iterdir()}
    if actual!={n for n in expected if n.startswith('code/')}:
        raise ValueError('Unpinned capsule member')
    inspect(root)
    return policy,read(root/'broker/CONFIG.json'),manifest

def physical(config):
    home=Path.home()/'JustPeachy';owner=identity()
    runtime_binding(config)
    if owner['boot_id']!=config['baseline']['boot_id']:
        raise RuntimeError('Exact baseline identities changed')
    for name,path in [('install_sha256',home/'install/current.json'),('live_config_sha256',home/'data/live_config.json'),
                      ('display_sha256',Path.home()/'.config/kanshi/config')]:
        if file_pin(path)['sha256']!=config['baseline'][name]:raise ValueError('Baseline file changed')
    if config['baseline']['display_sha256']!='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b':
        raise ValueError('Authorized270degree display')
    if os.uname().machine!='aarch64' or 'Compute Module 5' not in Path('/proc/device-tree/model').read_text():
        raise ValueError('CM5 aarch64 required')
    if int(Path('/sys/class/block/mmcblk0/size').read_text())*512!=31268536320:
        raise ValueError('Physical32GB card')
    total=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))
    if not 1700*1024**2<total<2100*1024**2:raise ValueError('Physical2GB memory target')
    if Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()!='closed':raise RuntimeError('Capture busy')
    if shutil.disk_usage(home).free<5*1024**3:raise RuntimeError('Physical free floor')

def runtime_binding(config):
    from field_runtime_policy_v3 import validate,validate_operation,digest,identity as exact_identity
    binding=config.get('runtime')
    fields={'root','policy_sha256','operation_sha256','slot','manager_owner','launch_slot',
            'manager_unit','slice','settings_sha256','baseline_owners','baseline_expected'}
    if type(binding) is not dict or set(binding)!=fields:
        raise ValueError('Exact runtime supervisor binding')
    root=Path(binding['root'])
    runtime=validate(read(root/'control/RELEASE.json',65536))
    if runtime['manager_root']!=str(root) or file_pin(root/'control/RELEASE.json')['sha256']!=binding['policy_sha256']:
        raise ValueError('Actual immutable runtime policy')
    slot=binding['slot']
    if slot not in runtime['allocation']['recording_slots']:raise ValueError('Allocated runtime slot')
    reserved=read(root/'recordings'/slot/'RESERVED.json',16384)
    if reserved.get('policy_sha256')!=binding['policy_sha256'] or reserved.get('slot')!='recordings/'+slot:
        raise ValueError('Actual manager reservation envelope')
    operation=validate_operation(reserved['operation'],runtime,now=datetime.now(timezone.utc))
    manager=exact_identity(binding['manager_owner'])
    if operation['owner']!=manager or digest(operation)!=binding['operation_sha256']:
        raise ValueError('Current manager operation binding')
    now=identity()
    if manager['boot_id']!=now['boot_id'] or ticks(manager['pid'])!=manager['start_ticks']:
        raise RuntimeError('Current manager process is absent')
    if binding['launch_slot'] not in runtime['allocation']['launch_slots']:raise ValueError('Allocated launch')
    launch=read(root/'launches'/binding['launch_slot']/'OWNER.json',16384)
    if launch.get('owner')!=manager or launch.get('policy_sha256')!=binding['policy_sha256']:
        raise ValueError('Actual durable manager launch owner')
    if (root/'launches'/binding['launch_slot']/'EXIT.json').exists():
        raise RuntimeError('Manager has closed this launch')
    if binding['manager_unit']!='jp-'+root.name+'.service' or binding['slice']!='jpfield'+root.name.replace('-','')+'.slice':
        raise ValueError('Exact shared runtime service and slice')
    if file_pin(Path.home()/'JustPeachy/data/settings.json')['sha256']!=binding['settings_sha256']:
        raise ValueError('Idle startup settings drift')
    owners=binding['baseline_owners']
    if type(owners) is not list or len(owners)!=2 or binding['baseline_expected'] not in ('idle','stopped'):
        raise ValueError('Independently observed prior application lifecycle')
    for old in owners:
        exact_identity(old)
        alive=old['boot_id']==now['boot_id'] and ticks(old['pid'])==old['start_ticks']
        if alive!=(binding['baseline_expected']=='idle'):raise RuntimeError('Baseline lifecycle changed')
    runtime_units(config)
    return runtime,operation,binding


def runtime_units(config):
    import subprocess
    binding=config['runtime']
    command=['systemctl','--user','show',binding['manager_unit'],'-p','MainPID','-p','ActiveState',
             '-p','LimitAS','-p','LimitSTACK','-p','LimitFSIZE','-p','TasksMax','-p','Slice','-p','RuntimeMaxUSec']
    proc=subprocess.run(command,capture_output=True,timeout=5)
    if proc.returncode or len(proc.stdout)>8192 or len(proc.stderr)>4096:raise RuntimeError('Manager service observation failed')
    row=dict(line.split('=',1) for line in proc.stdout.decode().splitlines())
    expected={'MainPID':str(binding['manager_owner']['pid']),'ActiveState':'active',
              'LimitAS':'134217728','LimitSTACK':'1048576','LimitFSIZE':'33554432','TasksMax':'64',
              'Slice':binding['slice'],'RuntimeMaxUSec':'1d'}
    if row!=expected:raise RuntimeError('Actual manager service envelope differs')
    proc=subprocess.run(['systemctl','--user','show',binding['slice'],'-p','CPUQuotaPerSecUSec',
        '-p','TasksMax','-p','AllowedCPUs','-p','ActiveState'],capture_output=True,timeout=5)
    if proc.returncode or len(proc.stdout)>4096 or len(proc.stderr)>4096:raise RuntimeError('Shared slice observation failed')
    row=dict(line.split('=',1) for line in proc.stdout.decode().splitlines())
    if row!={'CPUQuotaPerSecUSec':'2s','TasksMax':'64','AllowedCPUs':'2-3','ActiveState':'active'}:
        raise RuntimeError('Actual combined manager/broker CPU and task budget absent')
    proc=subprocess.run(['systemctl','--user','list-units','--state=active,activating,deactivating',
        '--no-legend','--plain','jp-*'],capture_output=True,timeout=5)
    if proc.returncode or len(proc.stdout)>16384 or len(proc.stderr)>4096:raise RuntimeError('Bounded active unit inventory')
    names={line.split()[0] for line in proc.stdout.decode().splitlines() if line.strip()}
    allowed={binding['manager_unit']}
    reservation=read(Path(binding['root'])/'recordings'/binding['slot']/'RESERVED.json',16384)
    source=Path(reservation['operation']['root']);broker_unit='jp-'+source.name+'.service'
    if broker_unit in names:
        owner_path=source/'broker/OWNER.json'
        who=read(owner_path,16384) if owner_path.exists() else identity()
        if who['boot_id']!=identity()['boot_id'] or ticks(who['pid'])!=who['start_ticks']:
            raise RuntimeError('Active broker exact identity missing')
        observation=subprocess.run(['systemctl','--user','show',broker_unit,'-p','MainPID','-p','Slice',
            '-p','ActiveState'],capture_output=True,timeout=5)
        if observation.returncode or len(observation.stdout)>4096 or len(observation.stderr)>4096:
            raise RuntimeError('Owned broker unit observation failed')
        actual=dict(line.split('=',1) for line in observation.stdout.decode().splitlines())
        if actual!={'MainPID':str(who['pid']),'Slice':binding['slice'],'ActiveState':'active'}:
            raise RuntimeError('Unexpected broker service identity or shared slice')
        allowed.add(broker_unit)
    if names!=allowed:
        raise RuntimeError('Unexpected research/runtime unit remains; leave it untouched')
    return row


def runtime_started(root,policy,gate,worker,check):
    config=read(root/'broker/CONFIG.json');binding=config['runtime']
    path=Path(binding['root'])/'recordings'/binding['slot']/'STARTED.json'
    end=time.monotonic()+12
    import stat
    pending=path.with_name(path.name+'.pending')
    while True:
        check()
        if ticks(binding['manager_owner']['pid'])!=binding['manager_owner']['start_ticks']:
            raise RuntimeError('Manager disappeared before actual STARTED')
        if path.exists():
            observed=path.lstat()
            if not stat.S_ISREG(observed.st_mode) or observed.st_size>16384:
                raise ValueError('Bounded regular STARTED publication required')
            if observed.st_nlink==1 and not pending.exists():break
            if observed.st_nlink not in (1,2):raise ValueError('Unexpected STARTED link count')
        if time.monotonic()>=end:raise TimeoutError('Manager durable Start acknowledgment')
        time.sleep(.01)
    row=read(path,16384)
    if (row.get('policy_sha256')!=binding['policy_sha256'] or row.get('slot')!='recordings/'+binding['slot']
            or row.get('owner')!=worker or row.get('gate_owner')!=gate
            or row.get('binding',{}).get('source')!=str(root)
            or row['binding'].get('policy_sha256')!=file_pin(root/'RELEASE.json')['sha256']
            or row.get('unit',{}).get('MainPID')!=str(worker['pid'])
            or row['unit'].get('ActiveState')!='active'):
        raise RuntimeError('Actual durable STARTED must bind broker, gate, unit and policy before ACK')
    return row
