"""Separate-process actual quiet source diagnostic. See README_XVF_RECOVERY_V3.md."""
import argparse, base64, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN = 'xvf-recovery-v3'
MIB = 1024**2
NAMES = ['xvf_recovery_dispatch_v3.py','xvf_recovery_protocol_v3.py','xvf_recovery_envelope_v3.py','README_XVF_RECOVERY_V3.md','AUTONOMOUS_QUIET_AUTHORIZATION_V1.json']



def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(MIB), b''): h.update(b)
    return h.hexdigest()


def write(path, value):
    data = json.dumps(value, indent=2).encode()
    assert len(data) < 2*MIB
    with Path(path).open('xb') as f: f.write(data)


def ticks(pid):
    try: return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError: return None


def worker():
    import resource,threading
    root=Path(__file__).resolve().parent;a=json.loads((root/'ADMISSION.json').read_text())
    owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    assert owner['boot_id']==a['boot_id'] and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    write(root/'OWNER.json',owner)
    from xvf_recovery_envelope_v3 import record_envelope
    record_envelope(root,owner);threading.stack_size(MIB)
    for row in a['files']:assert sha(row['path'])==row['sha256']
    result=dict(status='FAILED_PRESERVED');began=time.monotonic()
    try:
        from xvf_recovery_protocol_v3 import run
        result=run(root,a)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
    result.update(elapsed_seconds=time.monotonic()-began,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    write(root/'RESULT.json',result)
    print(json.dumps({k:result.get(k) for k in ['status','error','elapsed_seconds','peak_rss_bytes']}))
    return int(result['status']=='FAILED_PRESERVED')


def gate():
    import fcntl, resource
    os.sched_setaffinity(0, {3})
    resource.setrlimit(resource.RLIMIT_AS, (128*MIB,)*2)
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
        for p in campaign.rglob('*OWNER*.json'):
            o=json.loads(p.read_text()); assert not(o['boot_id']==boot and ticks(o['pid'])==o['start_ticks'])
        assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
        with (Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as hardware:
            fcntl.flock(hardware,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(hardware,fcntl.LOCK_UN)
        target_bytes=int(subprocess.check_output(['du','-sb',str(campaign)],text=True).split()[0])
        assert a['host_window_bytes']+target_bytes+a['output_max_bytes']<=a['combined_cap_bytes']
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
                        overflow=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
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
                    memory_guard=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
                if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>=a['target_output_max_bytes']:
                    overflow=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
                if time.monotonic()-began>325:
                    subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
                time.sleep(.25)
            tail=proc.stdout.read() or b'';room=4*MIB-retained;log.write(tail[:room]);overflow|=len(tail)>room
        write(root/'DISPATCH_RESULT.json',dict(exit_code=proc.returncode,seconds=time.monotonic()-began,
            log_overflow=overflow,memory_guard=memory_guard,samples=samples,output_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())))
        return proc.returncode


def dispatch(census_path):
    import psutil
    psutil.Process().cpu_affinity([14]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent))
    from window_guard_v5 import window,budget,payload_inventory
    from dispatch_geometry_v2 import remote,PRIVATE,LOCAL,REMOTE
    from dispatch_b01_stack_v2 import SSH
    w=window();c=json.loads(census_path.read_text());assert time.time()-census_path.stat().st_mtime<900
    assert c['window']['sha256']==sha(here.parent/'WINDOW_V5.json')
    for o in (c['supervisor']['host'],c['supervisor']['launcher']):
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    used=0
    for rel in ['n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928']:
        inv=payload_inventory(LOCAL/rel);assert not inv['errors'] and not inv['reparse_not_traversed'];used+=inv['total_logical_bytes']
    payload={n:base64.b64encode((here/n).read_bytes()).decode() for n in NAMES}
    for f in PRIVATE.glob('d1-onnx-*/supervision/worker.json'):
        wr=json.loads(f.read_text());assert wr['status'] in ['FAILED','COMPLETED']
        for pk,ck in [('pid','create_time'),('child_pid','child_create_time')]:
            try:assert abs(psutil.Process(wr[pk]).create_time()-wr[ck])>.001
            except psutil.NoSuchProcess:pass
        for name in ['MODEL_OWNER.json','REGISTERED_OWNER.json']:
            q=f.parent.parent/name
            if q.exists():
                o=json.loads(q.read_text());o=o.get('owner',o)
                try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
                except psutil.NoSuchProcess:pass
    now=datetime.now(timezone.utc);assert now+timedelta(minutes=12)<datetime.fromisoformat(w['checkpoint_utc'])
    pre=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import json,hashlib,subprocess,shutil,os
from pathlib import Path
r=Path(ROOT)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert ticks(1013)==569 and ticks(1130)==607 and 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
for p in r.rglob('*OWNER*.json'):
 o=json.loads(p.read_text());assert not(o['boot_id']==boot and ticks(o['pid'])==o['start_ticks'])
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
assert available>=850*1024**2 and shutil.disk_usage(r).free>=5*1024**3+16*1024**2
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
print(json.dumps(dict(boot_id=boot,available_ram_bytes=available,target_bytes=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0]),install_sha256=hashlib.sha256((Path.home()/'JustPeachy/install/current.json').read_bytes()).hexdigest(),live_config_sha256=hashlib.sha256((Path.home()/'JustPeachy/data/live_config.json').read_bytes()).hexdigest())))
''')
    assert pre['boot_id']=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43'
    assert pre['install_sha256']=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
    assert pre['live_config_sha256']=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
    delta=used-c['calculation']['window_used_bytes'];assert delta>=0
    calc=budget(c['calculation']['existing_bytes']+delta+pre['target_bytes'],used+pre['target_bytes'],16*MIB,{d:shutil.disk_usage(d+'/').free for d in ['C:','G:']},52)
    a=dict(schema='native-xvf-autonomous-recovery.v3',admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=12)).isoformat(),
        boot_id=pre['boot_id'],install_sha256=pre['install_sha256'],live_config_sha256=pre['live_config_sha256'],
        address_space_max_bytes=768*MIB,stack_bytes=MIB,cpus=[2,3],cpu_quota_percent=200,native_threads=1,
        minimum_available_ram_bytes=850*MIB,runtime_seconds=300,tasks_max=64,output_max_bytes=16*MIB,
        combined_cap_bytes=w['maximum_new_output_bytes'],host_window_bytes=used,capture=False,
        scope='Fresh conditional one-shot XVF firmware restart for retained actual-stream readback failure; firmware-only readbacks, no capture/models/playback',
        runtime_candidate='Main768MiBAS/1MiBstack/CPU2,3/shared200%/Tasks64; command deadlines2s, sampledRSS640MiB/available192MiB stops',stop_timeout_seconds=10,per_file_max_bytes=8*MIB,
        policy_sha256=sha(here.parent/'WINDOW_V5.json'),census_sha256=sha(census_path))
    a.update(target_output_max_bytes=8*MIB,host_evidence_reserve_bytes=8*MIB,models_loaded=False,audio_saved=False,maximum_restart_commands=1)
    staged=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(RUN)+'\nA='+repr(a)+'\nP='+repr(payload)+'\n'+r'''
import base64,json,hashlib,os
from pathlib import Path
r=Path(ROOT)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
d=r/RUN;d.mkdir()
for n,s in P.items():(d/n).write_bytes(base64.b64decode(s))
(d/'LIVE_CONFIG_BACKUP.json').write_bytes((Path.home()/'JustPeachy/data/live_config.json').read_bytes())
(d/'INSTALL_BACKUP.json').write_bytes((Path.home()/'JustPeachy/install/current.json').read_bytes())
assert sha(d/'LIVE_CONFIG_BACKUP.json')==A['live_config_sha256'] and sha(d/'INSTALL_BACKUP.json')==A['install_sha256']
A['authority_sha256']=sha(d/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')
tool=Path.home()/'JustPeachy/tools/native_xvf_usb/bin/xvf_host'
assert sha(tool)=='8cc5eebcb499faa61278c9378f7fcb92c6063a437176218404e56e610265e982' and tool.stat().st_size<2*1024**2
(d/'XVF_HOST_BACKUP').write_bytes(tool.read_bytes());assert sha(d/'XVF_HOST_BACKUP')==sha(tool)
prior=r/'source-quiet-v1/quiet/SOURCE_START_FAILURE.json'
assert prior.exists()
A['tool']=str(tool);A['tool_sha256']=sha(tool);A['prior_failure']=str(prior);A['prior_failure_sha256']=sha(prior)
paths=[x for x in d.iterdir() if x.is_file()]+[tool,prior,r/'xvf-restart-v2/RESULT.json',r/'xvf-restart-v2/MAINTENANCE_COMMAND.json']
A['files']=[dict(path=str(x),sha256=sha(x)) for x in paths]
(d/'ADMISSION.json').write_text(json.dumps(A,indent=2))
print(json.dumps(A))
''')
    out=PRIVATE/(RUN+'-evidence');out.mkdir();write(out/'PREFLIGHT.json',dict(admission=staged,calculation=calc,target=pre))
    # Verify host restoration copies before allowing the maintenance command.
    backup=out/'before';backup.mkdir();manifest={}
    for name in ['XVF_HOST_BACKUP','LIVE_CONFIG_BACKUP.json','INSTALL_BACKUP.json','ADMISSION.json']:
        raw=subprocess.check_output(SSH+['cat '+REMOTE+'/'+RUN+'/'+name],timeout=30)
        with (backup/name).open('xb') as f:f.write(raw)
        digest=sha(backup/name)
        if name!='ADMISSION.json':assert digest==next(x['sha256'] for x in staged['files'] if x['path'].endswith('/'+name))
        else:assert json.loads(raw)==staged
        manifest[name]=dict(sha256=digest,bytes=len(raw))
    write(out/'BEFORE_BACKUP.json',manifest)
    remote('ROOT='+repr(REMOTE+'/'+RUN)+'\nV='+repr(dict(verified=True,files=manifest))+'\nfrom pathlib import Path\nimport json\nwith (Path(ROOT)/"HOST_BACKUP_VERIFIED.json").open("x") as f:json.dump(V,f,indent=2)\nprint(json.dumps({"written":True}))')
    with (out/'launch.log').open('xb') as log:
        code=subprocess.run(SSH+['python3 -B '+REMOTE+'/'+RUN+'/xvf_recovery_dispatch_v3.py --gate'],stdout=log,stderr=subprocess.STDOUT,timeout=355).returncode
    write(out/'LAUNCH_RESULT.json',dict(exit_code=code,requires_independent_review=True))
    print(json.dumps(dict(run=RUN,exit_code=code,status='CLOSED_REVIEW_REQUIRED')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--gate',action='store_true');p.add_argument('--census',type=Path);a=p.parse_args()
    if a.worker:raise SystemExit(worker())
    elif a.gate:raise SystemExit(gate())
    else:
        if a.census is None:p.error('--census required')
        dispatch(a.census)
