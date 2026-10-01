"""Local startup rollback for a versioned runtime; README_RUNTIME_ACTIVATION_V1.md.

Only standard library modules. Installation must pin this source and binding,
verify independent active-file backups, and arm the service before closing the
baseline. A rollback never deletes candidate files or rewrites user settings.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import stat
import subprocess
import sys
import time

CAMPAIGN=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
HOME=Path('/home/peachyprototype')
MAX_ATTEMPTS=16
MIB=1024**2

def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()

def strict(raw):
    def pairs(rows):
        value={}
        for k,v in rows:
            if k in value:raise ValueError('Duplicate key')
            value[k]=v
        return value
    def bad(v):raise ValueError('Nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)

def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def identity(v):
    if type(v) is not dict or set(v)!={'pid','start_ticks','boot_id'}:raise ValueError('Exact native identity')
    if any(type(v[k]) is not int or v[k]<=0 for k in ('pid','start_ticks')):raise ValueError('Positive PID/ticks')
    if type(v['boot_id']) is not str or not re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',v['boot_id']):raise ValueError('Boot UUID')
    return v

def owner():
    return identity(dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),
                         boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()))

def read(path,cap=65536):
    path=Path(path)
    for parent in path.parents:
        if parent.is_symlink() or not parent.is_dir():raise ValueError('Real ancestors')
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>cap:raise ValueError('Bounded regular member')
    raw=path.read_bytes();after=path.lstat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise RuntimeError('Member changed')
    return raw

def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def put(path,raw,cap=65536):
    if len(raw)>cap:raise ValueError('Publication cap')
    with Path(path).open('xb') as f:
        for offset in range(0,len(raw),16384):
            block=raw[offset:offset+16384]
            if f.write(block)!=len(block):raise IOError('Short write')
        f.flush();os.fsync(f.fileno())
    sync(Path(path).parent)
    if read(path,cap)!=raw:raise IOError('Independent publication readback')

def validate_binding(root,value):
    fields={'schema','release_id','manager_policy_sha256','activation_unit','activation_owner',
            'autostart','launcher_sha256','settings_sha256','source_sha256','baseline_owners',
            'rollback_attempts','reserved_bytes'}
    if type(value) is not dict or set(value)!=fields or value['schema']!='just-peachy.runtime-rollback.v1':raise ValueError('Exact rollback binding')
    rid=value['release_id']
    if type(rid) is not str or not re.fullmatch('field-runtime-v[1-9][0-9]*',rid):raise ValueError('Versioned release')
    if root!=CAMPAIGN/(rid+'-activation'):raise ValueError('Canonical activation tree')
    if value['activation_unit']!='jp-install-'+rid+'.service':raise ValueError('Exact installer unit')
    identity(value['activation_owner'])
    if type(value['baseline_owners']) is not list or len(value['baseline_owners'])!=2:raise ValueError('Two baseline owners')
    for v in value['baseline_owners']:identity(v)
    if len({encode(v) for v in value['baseline_owners']})!=2:raise ValueError('Distinct baseline identities')
    for key in ('manager_policy_sha256','launcher_sha256','settings_sha256','source_sha256'):
        if type(value[key]) is not str or not re.fullmatch('[0-9a-f]{64}',value[key]):raise ValueError('Exact digest')
    row=value['autostart']
    if type(row) is not dict or set(row)!={'path','original_sha256','candidate_sha256','mode'}:raise ValueError('Autostart binding')
    if row['path']!=str(HOME/'.config/autostart/just-peachy.desktop'):raise ValueError('Exact startup path')
    if any(type(row[k]) is not str or not re.fullmatch('[0-9a-f]{64}',row[k]) for k in ('original_sha256','candidate_sha256')):raise ValueError('Startup pins')
    if type(row['mode']) is not int or row['mode'] not in (420,448,493):raise ValueError('Reviewed original file mode')
    if type(value['rollback_attempts']) is not int or value['rollback_attempts']!=MAX_ATTEMPTS:raise ValueError('Finite rollback count')
    # 16 independent owner/result/failure sets, backup/restore, code/control and directory reserve.
    if type(value['reserved_bytes']) is not int or value['reserved_bytes']!=8*MIB:raise ValueError('Full activation allocation')
    return value

def run_command(argv,timeout=5,cap=16384):
    result=subprocess.run(argv,capture_output=True,timeout=timeout)
    if result.returncode or len(result.stdout)>cap or len(result.stderr)>4096:raise RuntimeError('Bounded local command failed')
    return result.stdout.decode()

def baseline_processes():
    rows=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            with (p/'cmdline').open('rb') as f:argv=f.read(8193).split(b'\0')
        except (FileNotFoundError,PermissionError,ProcessLookupError):continue
        if len(argv)>1 and argv[1] in (
                b'/home/peachyprototype/JustPeachy/install/releases/proto1-cm5-20260923-rc5/main.py',
                b'/home/peachyprototype/JustPeachy/install/releases/proto1-cm5-20260923-rc5/release_tools/launch_current.py'):
            start=ticks(int(p.name))
            if start is not None:
                rows.append(dict(pid=int(p.name),start_ticks=start,
                                 boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()))
    if len(rows)>2:raise RuntimeError('Unexpected duplicate baseline processes')
    return rows

def rollback(root,binding_sha):
    native=owner()
    # Claim one preallocated receipt slot before reading any project control/source.
    if root.parent!=CAMPAIGN or not re.fullmatch('field-runtime-v[1-9][0-9]*-activation',root.name) or root.resolve()!=root:raise ValueError('Exact root')
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        slots=[root/'attempts'/('%02d'%i) for i in range(1,MAX_ATTEMPTS+1)]
        used=[i for i,p in enumerate(slots) if any(p.iterdir())]
        if used!=list(range(len(used))) or len(used)==MAX_ATTEMPTS:raise RuntimeError('Rollback slots exhausted or malformed')
        attempt=slots[len(used)];put(attempt/'OWNER.json',encode(native),16384)
        try:
            raw=read(root/'ROLLBACK.json')
            if sha(raw)!=binding_sha:raise ValueError('Rollback binding pin')
            binding=validate_binding(root,strict(raw))
            if sha(read(root/'field_runtime_activation_v1.py',131072))!=binding['source_sha256']:raise ValueError('Rollback code pin')
            unit='jp-rollback-'+binding['release_id']+'.service'
            actual=dict(line.split('=',1) for line in run_command(['systemctl','--user','show',unit,
                '-p','MainPID','-p','ActiveState','-p','LimitAS','-p','LimitSTACK','-p','LimitFSIZE',
                '-p','AllowedCPUs','-p','CPUQuotaPerSecUSec','-p','TasksMax','-p','RuntimeMaxUSec']).splitlines())
            if actual!=dict(MainPID=str(native['pid']),ActiveState='active',LimitAS='134217728',
                LimitSTACK='1048576',LimitFSIZE='33554432',AllowedCPUs='2-3',
                CPUQuotaPerSecUSec='2s',TasksMax='64',RuntimeMaxUSec='1min'):
                raise RuntimeError('Actual rollback service envelope')
            manager='jp-'+binding['release_id']+'.service'
            state=run_command(['systemctl','--user','show',manager,'-p','ActiveState','--value']).strip()
            if state in ('active','activating','deactivating'):raise RuntimeError('Do not rollback a running candidate')
            original=read(root/'backup/autostart.desktop')
            if sha(original)!=binding['autostart']['original_sha256'] or read(root/'restore/autostart.desktop')!=original:raise IOError('Independent original startup restore')
            launcher=HOME/'JustPeachy/start-prototype.sh'
            if sha(read(launcher))!=binding['launcher_sha256']:raise ValueError('Preserved baseline launcher changed')
            settings=read(HOME/'JustPeachy/data/settings.json')
            if sha(settings)!=binding['settings_sha256'] or strict(settings).get('auto_start_listening') is not False:raise RuntimeError('Preserve capture-off personal settings')
            live=[]
            for p in sorted(Path('/proc/asound').glob('card*/pcm*c/sub*/status')):
                live.append(p.read_text().strip())
            if not live or any(v!='closed' for v in live):raise RuntimeError('Capture not closed; preserve failure')
            for lock in (CAMPAIGN/'B05_PREVIEW_DISPATCH.lock',HOME/'JustPeachy/data/xvf-hardware.lock'):
                lockfd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW)
                try:fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                finally:os.close(lockfd)
            target=Path(binding['autostart']['path']);current=sha(read(target))
            if current not in (binding['autostart']['original_sha256'],binding['autostart']['candidate_sha256']):raise RuntimeError('Unrelated startup change; no overwrite')
            replaced=False
            if current!=binding['autostart']['original_sha256']:
                pending=target.with_name(target.name+'.'+binding['release_id']+'-rollback.pending')
                put(pending,original);os.chmod(pending,binding['autostart']['mode'])
                if sha(read(target))!=current:raise RuntimeError('Startup changed before restore')
                os.replace(pending,target);sync(target.parent)
                if read(target)!=original:raise IOError('Actual restored startup readback')
                replaced=True
            existing=baseline_processes()
            if not existing:
                # Local systemd owns and records the restored user's idle baseline.
                # This service is distinct from the finite rollback utility.
                baseline_unit='just-peachy-restored-'+binding['release_id']
                run_command(['systemd-run','--user','--collect','--quiet','--unit='+baseline_unit,
                    '--property=Description=JustPeachyRestoredIdleBaseline',
                    '--property=AllowedCPUs=2-3','--property=CPUQuota=200%','--property=TasksMax=64',
                    '--setenv=DISPLAY=:0','--setenv=XAUTHORITY='+str(HOME/'.Xauthority'),
                    '--setenv=XDG_RUNTIME_DIR=/run/user/1000','--setenv=WAYLAND_DISPLAY=wayland-0',
                    '--setenv=HF_HUB_OFFLINE=1','--setenv=TRANSFORMERS_OFFLINE=1',
                    '/bin/sh',str(launcher)])
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    existing=baseline_processes()
                    if len(existing)==2:break
                    time.sleep(.1)
                if len(existing)!=2:raise RuntimeError('Restored baseline startup not observed')
            if len(existing)!=2:raise RuntimeError('Partial baseline remains; no duplicate start')
            put(attempt/'RESULT.json',encode(dict(status='STARTUP_RESTORED_BASELINE_OBSERVED',
                utility_owner=native,baseline_owners=existing,autostart_replaced=replaced,
                capture_started=False,settings_changed=False,physical_closure_claimed=False)))
        except BaseException as exc:
            put(attempt/'FAILURE.json',encode(dict(error=type(exc).__name__,message=str(exc)[:1024],owner=native)))
            raise
    finally:os.close(fd)

def main():
    os.sched_setaffinity(0,{3})
    for kind,cap in ((resource.RLIMIT_AS,128*MIB),(resource.RLIMIT_STACK,MIB),
                     (resource.RLIMIT_FSIZE,32*MIB),(resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(cap,cap))
    signal.alarm(50);sys.dont_write_bytecode=True
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--binding-sha256',required=True)
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{64}',args.binding_sha256):raise ValueError('Exact binding SHA')
    rollback(args.root,args.binding_sha256)

if __name__=='__main__':main()

