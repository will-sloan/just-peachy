"""Separate-process actual quiet source diagnostic. See README_XVF_RECOVERY_V4.md."""
import argparse, base64, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN = 'xvf-recovery-v4'
MIB = 1024**2
NAMES = ['xvf_recovery_dispatch_v4.py','xvf_recovery_protocol_v4.py','xvf_recovery_envelope_v4.py','README_XVF_RECOVERY_V4.md','AUTONOMOUS_QUIET_AUTHORIZATION_V1.json']



def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(MIB), b''): h.update(b)
    return h.hexdigest()


def write(path, value):
    data = json.dumps(value, indent=2).encode()
    assert len(data) < 128*1024
    with Path(path).open('xb') as f: f.write(data);f.flush();os.fsync(f.fileno())


def ticks(pid):
    try: return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError: return None


def worker():
    import resource,threading
    root=Path(__file__).resolve().parent;a=json.loads((root/'ADMISSION.json').read_text())
    owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    assert owner['boot_id']==a['boot_id'] and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    write(root/'OWNER.json',owner)
    from xvf_recovery_envelope_v4 import record_envelope
    record_envelope(root,owner);threading.stack_size(MIB)
    for row in a['files']:assert sha(row['path'])==row['sha256']
    result=dict(status='FAILED_PRESERVED');began=time.monotonic()
    try:
        from xvf_recovery_protocol_v4 import run
        result=run(root,a)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
    result.update(elapsed_seconds=time.monotonic()-began,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    write(root/'RESULT.json',result)
    print(json.dumps({k:result.get(k) for k in ['status','error','elapsed_seconds','peak_rss_bytes']}))
    return int(result['status']=='FAILED_PRESERVED')


def gate():
    import fcntl, resource, signal
    os.sched_setaffinity(0, {3})
    resource.setrlimit(resource.RLIMIT_AS, (128*MIB,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(MIB,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(8*MIB,)*2)
    signal.alarm(335)
    root=Path(__file__).resolve().parent; campaign=root.parent
    a=json.loads((root/'ADMISSION.json').read_text())
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot==a['boot_id'] and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    assert ticks(1013)==569 and ticks(1130)==607
    assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
    assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
    for row in a['files']: assert sha(row['path'])==row['sha256']
    available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    assert available>=850*MIB and shutil.disk_usage(root).free>=5*1024**3+a['output_max_bytes']
    assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    with (campaign/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for o in a['preflight_pi_owners']+[json.loads((root/'STAGE_OWNER.json').read_bytes())]:
            assert not(o['boot_id']==boot and ticks(o['pid'])==o['start_ticks'])
        assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True,timeout=5).strip()
        with (Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as hardware:
            fcntl.flock(hardware,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(hardware,fcntl.LOCK_UN)
        target_bytes=int(subprocess.check_output(['du','-sb',str(campaign)],text=True,timeout=10).split()[0])
        assert a['host_window_bytes']+target_bytes+a['output_max_bytes']<=a['resource_policy']['combined_output_cap_bytes']
        assert a['payload_before_bytes']+max(0,target_bytes-a['target_before_bytes'])+a['output_max_bytes']<=a['resource_policy']['total_payload_cap_bytes']
        write(root/'DISPATCH_OWNER.json',dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot))
        python=str(Path.home()/'JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python')
        cmd=['systemd-run','--user','--unit=jp-'+RUN,'--wait','--pipe']
        for prop in ['CPUQuota=200%','TasksMax=64','LimitAS='+str(768*MIB),'LimitSTACK='+str(MIB),
                     'RuntimeMaxSec=300','TimeoutStopSec=10','LimitCORE=0','Nice=10','LimitFSIZE='+str(8*MIB)]:cmd+=['-p',prop]
        for key,value in dict(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
            NUMEXPR_NUM_THREADS='1',MALLOC_ARENA_MAX='1',MALLOC_MMAP_THRESHOLD_='131072',
            MALLOC_TRIM_THRESHOLD_='131072',CUDA_VISIBLE_DEVICES='',ORT_DISABLE_TELEMETRY='1').items():cmd+=['--setenv='+key+'='+value]
        cmd+=['taskset','-c','2,3',python,'-B',str(root/Path(__file__).name),'--worker']
        began=time.monotonic(); samples=[]; overflow=False; retained=0; memory_guard=False
        with (root/'service.log').open('xb') as log:
            proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            os.set_blocking(proc.stdout.fileno(),False)
            while proc.poll() is None:
                block=proc.stdout.read(65536)
                if block:
                    room=4*MIB-retained; log.write(block[:room]);retained+=min(room,len(block))
                    if len(block)>room and not overflow:
                        overflow=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True,timeout=15)
                op=root/'OWNER.json'
                if op.exists():
                    owner=json.loads(op.read_text())
                    if ticks(owner['pid'])==owner['start_ticks']:
                        try:
                            values=Path('/proc',str(owner['pid']),'status').read_text().splitlines()
                            samples.append(dict(t=time.monotonic()-began, **{x.split(':')[0]:int(x.split()[1]) for x in values if x.startswith(('VmSize:','VmRSS:','VmPeak:','Threads:'))}))
                        except FileNotFoundError:pass
                aggregate=0
                for op in root.rglob('*OWNER.json'):
                    owned=json.loads(op.read_text())
                    if ticks(owned['pid'])==owned['start_ticks']:
                        try:
                            values=Path('/proc',str(owned['pid']),'status').read_text().splitlines()
                            aggregate+=next(int(x.split()[1])*1024 for x in values if x.startswith('VmRSS:'))
                        except (FileNotFoundError,StopIteration):pass
                if samples:samples[-1]['aggregate_rss_bytes']=aggregate
                available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
                if available<192*MIB or aggregate>640*MIB:
                    memory_guard=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True,timeout=15)
                if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>=a['target_output_max_bytes']:
                    overflow=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True,timeout=15)
                if time.monotonic()-began>325:
                    subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True,timeout=15)
                time.sleep(.25)
            tail=proc.stdout.read() or b'';room=4*MIB-retained;log.write(tail[:room]);overflow|=len(tail)>room
        write(root/'DISPATCH_RESULT.json',dict(exit_code=proc.returncode,seconds=time.monotonic()-began,
            log_overflow=overflow,memory_guard=memory_guard,samples=samples,output_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())))
        return proc.returncode


def dispatch(plan_path,owner_receipt):
    import psutil
    psutil.Process().cpu_affinity([14])
    owner=dict(pid=os.getpid(),create_time=psutil.Process().create_time(),affinity=[14])
    write(owner_receipt,owner)
    here=Path(__file__).resolve().parent
    from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
    from dispatch_b01_stack_v2 import SSH
    plan=json.loads(plan_path.read_text(encoding='utf-8'));a=plan['admission']
    now=datetime.now(timezone.utc)
    assert 590<(datetime.fromisoformat(a['expires_utc'])-now).total_seconds()<=600
    assert a['output_max_bytes']==22*MIB and a['target_output_max_bytes']==8*MIB and a['host_evidence_reserve_bytes']==14*MIB
    assert time.time()-Path(plan['census']).stat().st_mtime<900
    for row in plan['host_files']:
        assert Path(row['path']).stat().st_size==row['bytes'] and sha(row['path'])==row['sha256']
    for o in plan['prior_host_owners']:
        try:seen=psutil.Process(o['pid']).create_time()
        except psutil.NoSuchProcess:seen=None
        assert seen is None or abs(seen-o['create_time'])>.001
    for drive,floor in [('C:/',50*1024**3),('G:/',75*1024**3)]:
        assert shutil.disk_usage(drive).free>=floor+14*MIB
    out=Path(plan['output']);out.mkdir()
    write(out/'REGISTERED_OWNER.json',owner)
    write(out/'PLAN.json',plan)
    payload={Path(row['path']).name:dict(base64=base64.b64encode(Path(row['path']).read_bytes()).decode(),bytes=row['bytes'],sha256=row['sha256']) for row in plan['stage_files']}
    staged=remote((here/'xvf_recovery_stage_v4.py').read_text(encoding='utf-8')+'\nprint(json.dumps(stage('+repr(dict(admission=a,payload=payload))+')))')
    write(out/'PREFLIGHT.json',staged)
    # The bounded utility records its identity as well as the ended stage owner.
    closure_code=OWNED_READ_ENVELOPE+'\nO='+repr(staged['owner'])+"\nassert ticks(O['pid'])!=O['start_ticks']\nprint(json.dumps(dict(owner=identity(),stage_owner=O,stage_exact_dead=True)))"
    closed=remote(closure_code);write(out/'STAGE_CLOSURE.json',closed)
    assert subprocess.run(SSH+['test ! -e /proc/'+str(closed['owner']['pid'])],timeout=10).returncode==0
    before=out/'before';before.mkdir();restore=out/'restore-copy';restore.mkdir();manifest={}
    for name in ['XVF_HOST_BACKUP','LIVE_CONFIG_BACKUP.json','INSTALL_BACKUP.json','ADMISSION.json']:
        assert sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<6*MIB
        export_code=OWNED_READ_ENVELOPE+"\nprint(json.dumps(dict(owner=identity())),flush=True)\nos.execlp('cat','cat',"+repr(a['output_root']+'/'+name)+")"
        import base64 as b64,threading
        command='python3 -c '+__import__('shlex').quote("import base64;exec(base64.b64decode("+repr(b64.b64encode(export_code.encode()).decode())+"))")
        proc=subprocess.Popen(SSH+[command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        timer=threading.Timer(25,proc.kill);timer.daemon=True;timer.start()
        header=proc.stdout.readline(1025);assert len(header)<1025
        exporter=json.loads(header);write(out/('BEFORE_EXPORT_OWNER_'+name+'.json'),exporter)
        length=0;deadline=time.monotonic()+20
        with (before/name).open('xb') as dest:
            while part:=proc.stdout.read(16384):
                length+=len(part)
                if length>2*MIB or time.monotonic()>deadline:
                    proc.kill();proc.wait(timeout=5);raise ValueError('Before-backup stream ceiling')
                dest.write(part)
            dest.flush();os.fsync(dest.fileno())
        err=proc.stderr.read(65537);assert proc.wait(timeout=5)==0 and len(err)<65536
        proc.stdout.close();proc.stderr.close();timer.cancel()
        assert subprocess.run(SSH+['test ! -e /proc/'+str(exporter['owner']['pid'])],timeout=10).returncode==0
        digest=sha(before/name)
        if name=='ADMISSION.json':assert json.loads((before/name).read_bytes())==staged['admission']
        else:assert digest==next(x['sha256'] for x in staged['admission']['files'] if x['path']==a['output_root']+'/'+name)
        with (before/name).open('rb') as src,(restore/name).open('xb') as dest:
            while part:=src.read(16384):dest.write(part)
            dest.flush();os.fsync(dest.fileno())
        assert sha(restore/name)==digest and (restore/name).stat().st_size==length
        manifest[name]=dict(sha256=digest,bytes=length)
    write(out/'BEFORE_BACKUP.json',dict(files=manifest,independent_restore_copy_verified=True))
    ack=remote(OWNED_READ_ENVELOPE+'\nROOT='+repr(a['output_root'])+'\nV='+repr(dict(verified=True,files=manifest))+r'''
d=Path(ROOT);raw=json.dumps(V,indent=2).encode();assert len(raw)<8192
with (d/'HOST_BACKUP_VERIFIED.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
assert (d/'HOST_BACKUP_VERIFIED.json').read_bytes()==raw
print(json.dumps(dict(owner=identity(),written=True)))
''')
    write(out/'ACK_OWNER.json',ack)
    assert subprocess.run(SSH+['test ! -e /proc/'+str(ack['owner']['pid'])],timeout=10).returncode==0
    code=None
    try:
        with (out/'launch.log').open('xb') as log:
            code=subprocess.run(SSH+['python3 -B '+a['output_root']+'/xvf_recovery_dispatch_v4.py --gate'],stdout=log,stderr=subprocess.STDOUT,timeout=355).returncode
    except subprocess.TimeoutExpired:
        subprocess.run(SSH+['systemctl --user stop --no-block jp-'+RUN],timeout=10,check=False,capture_output=True)
        raise
    finally:
        write(out/'LAUNCH_RESULT.json',dict(exit_code=code,requires_independent_review=True))
    # The reader backs up a closed failed tree before applying logical success assertions.
    cp=subprocess.run([sys.executable,'-B',str(here/'review_xvf_recovery_v4.py'),'--evidence',str(out),'--owner-receipt',str(out/'REVIEW_OWNER.json')],capture_output=True,timeout=100)
    with (out/'REVIEW_STDOUT.txt').open('xb') as f:f.write(cp.stdout[:65536])
    with (out/'REVIEW_STDERR.txt').open('xb') as f:f.write(cp.stderr[:65536])
    assert len(cp.stdout)<=65536 and len(cp.stderr)<=65536
    print(json.dumps(dict(run=RUN,exit_code=code,reader_exit_code=cp.returncode,status='CLOSED_REVIEW_REQUIRED')))
    return int(code!=0 or cp.returncode!=0)

OWNED_READ_ENVELOPE = r'''
import os,json,resource,signal
from pathlib import Path
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1024**2,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(16384,)*2)
signal.alarm(15)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def identity():return dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
'''

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--worker',action='store_true');p.add_argument('--gate',action='store_true')
    p.add_argument('--plan',type=Path);p.add_argument('--owner-receipt',type=Path);args=p.parse_args()
    if args.worker:raise SystemExit(worker())
    if args.gate:raise SystemExit(gate())
    if args.plan is None or args.owner_receipt is None:p.error('--plan and --owner-receipt required')
    raise SystemExit(dispatch(args.plan,args.owner_receipt))
