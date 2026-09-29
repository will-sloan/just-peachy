"""Stage existing A2 weights only; README_STAGE_A2_ASSET_V1.md."""
import argparse,base64,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone,timedelta

SIZE=699872960
DIGEST='d9a01898d2a611c8764e23a1c2f45e70bbd5a425dc4de93692ac951dd603812d'
RUN='a2-asset-stage-v1'
MIB=1024**2

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(MIB),b''):h.update(chunk)
    return h.hexdigest()

def receive():
    import fcntl,resource,signal
    root=Path(__file__).resolve().parent;r=root.parent
    a=json.loads((root/'ADMISSION.json').read_text())
    assert a['asset_bytes']==SIZE and a['asset_sha256']==DIGEST
    assert a['capture'] is False and a['models_loaded'] is False
    assert resource.getrlimit(resource.RLIMIT_AS)==(a['address_space_max_bytes'],)*2
    assert resource.getrlimit(resource.RLIMIT_STACK)==(a['stack_bytes'],)*2
    assert sorted(os.sched_getaffinity(0))==a['cpus']==[2,3]
    assert sha(Path(__file__))==a['script_sha256']
    assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    signal.alarm(a['runtime_seconds'])
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    def ticks(pid):
        try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
        except FileNotFoundError:return None
    assert boot==a['boot_id'] and ticks(1013)==569 and ticks(1130)==607
    assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
    assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
    import shutil
    assert shutil.disk_usage(r).free>=5*1024**3+a['output_max_bytes']
    assert next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))>=850*MIB
    assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    with (r/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for f in r.rglob('*OWNER*.json'):
            o=json.loads(f.read_text());assert not(o['boot_id']==boot and ticks(o['pid'])==o['start_ticks'])
        units=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True)
        assert all(line.split()[0]=='jp-'+RUN+'.service' for line in units.splitlines() if line.strip())
        with (Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as hardware:
            fcntl.flock(hardware,fcntl.LOCK_EX|fcntl.LOCK_NB)
            used=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0])
            assert a['host_window_bytes']+used+a['output_max_bytes']<=a['combined_output_cap_bytes']
            owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot,admission_sha256=sha(root/'ADMISSION.json'))
            with (root/'OWNER.json').open('x') as f:json.dump(owner,f)
            print('READY',flush=True)
            h=hashlib.sha256();count=0;part=root/'A2.gguf.partial'
            try:
                with part.open('xb') as f:
                    while count<SIZE:
                        block=sys.stdin.buffer.read(min(MIB,SIZE-count))
                        if not block:raise EOFError('Incomplete transfer; preserve partial')
                        f.write(block);h.update(block);count+=len(block)
                    f.flush();os.fsync(f.fileno())
                assert not sys.stdin.buffer.read(1),'Unexpected excess input'
                assert count==SIZE and h.hexdigest()==DIGEST
                part.rename(root/'A2.gguf')
                result=dict(status='ASSET_STAGED_NOT_MODEL_QUALIFIED',bytes=count,sha256=h.hexdigest(),capture=False,models_loaded=False,owner=owner)
                with (root/'RESULT.json').open('x') as f:json.dump(result,f,indent=2)
                print(json.dumps(result),flush=True)
            except BaseException as exc:
                with (root/'FAILURE.json').open('x') as f:json.dump(dict(status='FAILED_PRESERVED_PARTIAL',bytes=count,error=type(exc).__name__),f)
                raise

def dispatch(census_path):
    import psutil
    psutil.Process().cpu_affinity([14])
    if os.name=='nt':psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent))
    from window_guard_v2 import window,budget,payload_inventory
    from dispatch_geometry_v2 import remote,PRIVATE,LOCAL,REMOTE
    from dispatch_b01_stack_v2 import SSH
    w=window();c=json.loads(census_path.read_text())
    assert time.time()-census_path.stat().st_mtime<900
    assert c['window']['sha256']==sha(here.parent/'WINDOW_V2.json')
    for o in (c['supervisor']['host'],c['supervisor']['launcher']):
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    source=LOCAL/'assets/sha256'/DIGEST/'nemotron-speech-streaming-en-0.6b.q8_0.gguf'
    assert source.stat().st_size==SIZE and sha(source)==DIGEST
    used=0
    for rel in ['n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928']:
        inv=payload_inventory(LOCAL/rel);assert not inv['errors'] and not inv['reparse_not_traversed'];used+=inv['total_logical_bytes']
    delta=used-c['calculation']['window_used_bytes'];assert delta>=0
    out=PRIVATE/(RUN+'-evidence');out.mkdir()
    requested=704*MIB
    import shutil
    free={d:shutil.disk_usage(d+'/').free for d in ['C:','G:']}
    pre=remote('ROOT='+repr(REMOTE)+'\n'+r"""
import json,subprocess,hashlib,shutil
from pathlib import Path
r=Path(ROOT);boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
assert boot=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43' and ticks(1013)==569 and ticks(1130)==607
assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
for f in r.rglob('*OWNER*.json'):
 o=json.loads(f.read_text());assert not(o['boot_id']==boot and ticks(o['pid'])==o['start_ticks'])
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
print(json.dumps(dict(boot_id=boot,target_bytes=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0]),install_sha256=hashlib.sha256((Path.home()/'JustPeachy/install/current.json').read_bytes()).hexdigest(),live_config_sha256=hashlib.sha256((Path.home()/'JustPeachy/data/live_config.json').read_bytes()).hexdigest())))
""")
    assert pre['install_sha256']=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
    assert pre['live_config_sha256']=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
    calc=budget(c['calculation']['existing_bytes']+delta+pre['target_bytes'],used+pre['target_bytes'],requested,free,50)
    now=datetime.now(timezone.utc);assert now+timedelta(minutes=12)<datetime.fromisoformat(w['checkpoint_utc'])
    a=dict(schema='a2-asset-stage.v1',admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=12)).isoformat(),asset_bytes=SIZE,asset_sha256=DIGEST,script_sha256=sha(__file__),readme_sha256=sha(here/'README_STAGE_A2_ASSET_V1.md'),boot_id=pre['boot_id'],install_sha256=pre['install_sha256'],live_config_sha256=pre['live_config_sha256'],cpus=[2,3],cpu_quota_percent=200,tasks_max=64,address_space_max_bytes=128*MIB,stack_bytes=MIB,runtime_seconds=600,stop_timeout_seconds=10,output_max_bytes=requested,host_window_bytes=used,combined_output_cap_bytes=w['maximum_new_output_bytes'],capture=False,models_loaded=False,policy_sha256=sha(here.parent/'WINDOW_V2.json'),census_sha256=sha(census_path))
    payload={n:base64.b64encode((here/n).read_bytes()).decode() for n in ['stage_a2_asset_v1.py','README_STAGE_A2_ASSET_V1.md']}
    staged=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(RUN)+'\nA='+repr(a)+'\nP='+repr(payload)+'\n'+r"""
from pathlib import Path
import json,base64
r=Path(ROOT)/RUN;r.mkdir()
for n,s in P.items():(r/n).write_bytes(base64.b64decode(s))
with (r/'ADMISSION.json').open('x') as f:json.dump(A,f,indent=2)
print(json.dumps({'staged':True}))
""")
    with (out/'PREFLIGHT.json').open('x') as f:json.dump(dict(admission=a,calculation=calc,target=pre),f,indent=2)
    command='systemd-run --user --unit=jp-'+RUN+' --wait --pipe -p CPUQuota=200% -p TasksMax=64 -p LimitAS='+str(128*MIB)+' -p LimitSTACK='+str(MIB)+' -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 python3 -B '+REMOTE+'/'+RUN+'/stage_a2_asset_v1.py --receive'
    with (out/'launch.log').open('xb') as log:
        proc=subprocess.Popen(SSH+[command],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
        ready=proc.stdout.readline();assert ready.strip()==b'READY',ready
        try:
            with source.open('rb') as f:
                for block in iter(lambda:f.read(MIB),b''):proc.stdin.write(block)
            proc.stdin.close();code=proc.wait(timeout=630);output=proc.stdout.read();log.write(output)
        finally:
            if proc.poll() is None:proc.stdin.close()
        with (out/'LAUNCH_RESULT.json').open('x') as f:json.dump(dict(exit_code=code,bytes_sent=SIZE,requires_independent_review=True),f)
        assert code==0
    print(json.dumps({'run':RUN,'status':'TRANSFER_CLOSED_REVIEW_REQUIRED','bytes':SIZE}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--receive',action='store_true');p.add_argument('--census',type=Path);a=p.parse_args()
    if a.receive:receive()
    else:
        if a.census is None:p.error('--census required')
        dispatch(a.census)
