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
    if owner['boot_id']!=config['baseline']['boot_id'] or ticks(1013)!=569 or ticks(1130)!=607:
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
