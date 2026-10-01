"""Bounded recovery staging; README_XVF_RECOVERY_V4.md."""
import base64,fcntl,hashlib,json,os,platform,resource,shutil,signal,subprocess
from datetime import datetime,timezone
from pathlib import Path
MIB=1024**2

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def write(path,data):
    with path.open('xb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    if path.read_bytes()!=data:raise IOError('Stage readback')

def stage(request):
    os.sched_setaffinity(0,{3})
    resource.setrlimit(resource.RLIMIT_AS,(128*MIB,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(MIB,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(8*MIB,)*2)
    signal.alarm(30)
    a=request['admission'];root=Path(a['output_root']);campaign=root.parent
    if root.name!='xvf-recovery-v4' or root.exists():raise ValueError('Fresh exact recovery root required')
    now=datetime.now(timezone.utc);expiry=datetime.fromisoformat(a['expires_utc'])
    assert 500<(expiry-now).total_seconds()<=600 and expiry<=datetime.fromisoformat('2026-10-01T17:42:44+00:00')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
    assert boot==a['boot_id'] and platform.machine()=='aarch64'
    assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
    ram=Path('/proc/meminfo').read_text().splitlines()
    total=next(int(x.split()[1])*1024 for x in ram if x.startswith('MemTotal:'))
    available=next(int(x.split()[1])*1024 for x in ram if x.startswith('MemAvailable:'))
    assert 1800*MIB<total<2100*MIB and available>=850*MIB
    assert int(Path('/sys/class/block/mmcblk0/size').read_text())*512==31268536320
    assert ticks(1013)==569 and ticks(1130)==607
    assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
    assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
    assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True,timeout=5).strip()
    for o in a['preflight_pi_owners']:
        assert not (o['boot_id']==boot and ticks(o['pid'])==o['start_ticks'])
    for p in (campaign/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock'):
        with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert shutil.disk_usage(root.parent).free>=5*1024**3+a['output_max_bytes']
    target=int(subprocess.check_output(['du','-sb',str(campaign)],text=True,timeout=10).split()[0])
    policy=a['resource_policy']
    assert a['host_window_bytes']+target+a['output_max_bytes']<=policy['combined_output_cap_bytes']
    assert a['payload_before_bytes']+max(0,target-a['target_before_bytes'])+a['output_max_bytes']<=policy['total_payload_cap_bytes']
    for row in a['external_files']:
        p=Path(row['path']);assert not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    expected={'xvf_recovery_dispatch_v4.py','xvf_recovery_protocol_v4.py','xvf_recovery_envelope_v4.py','xvf_recovery_stage_v4.py','README_XVF_RECOVERY_V4.md','AUTONOMOUS_QUIET_AUTHORIZATION_V1.json','RECOVERY_RESOURCE_POLICY_V1.json'}
    assert set(request['payload'])==expected
    root.mkdir()
    write(root/'STAGE_OWNER.json',json.dumps(owner).encode())
    for name,row in request['payload'].items():
        raw=base64.b64decode(row['base64'],validate=True)
        assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'] and len(raw)<128*1024
        write(root/name,raw)
    assert json.loads((root/'RECOVERY_RESOURCE_POLICY_V1.json').read_bytes())==policy
    originals=[(Path(a['tool']),'XVF_HOST_BACKUP'),(Path.home()/'JustPeachy/data/live_config.json','LIVE_CONFIG_BACKUP.json'),(Path.home()/'JustPeachy/install/current.json','INSTALL_BACKUP.json')]
    for source,name in originals:
        assert source.stat().st_size<(2*MIB if name=='XVF_HOST_BACKUP' else 32768)
        for dest in (root/name,root/(name+'.restore-copy')):
            with source.open('rb') as inp,dest.open('xb') as out:
                while part:=inp.read(16384):out.write(part)
                out.flush();os.fsync(out.fileno())
            assert sha(source)==sha(dest) and source.stat().st_size==dest.stat().st_size
    a['files']=a['external_files']+[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in root.iterdir() if p.is_file()]
    raw=json.dumps(a,indent=2).encode();assert len(raw)<128*1024
    write(root/'ADMISSION.json',raw)
    assert sum(p.stat().st_size for p in root.iterdir())<8*MIB
    return dict(owner=owner,admission=a,target_before=target,staged_bytes=sum(p.stat().st_size for p in root.iterdir()),backup_restore_verified=True)
