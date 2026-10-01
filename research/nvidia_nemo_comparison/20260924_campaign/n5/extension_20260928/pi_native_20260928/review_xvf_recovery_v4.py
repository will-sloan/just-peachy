"""Preserve and independently review one closed recovery tree. README_XVF_RECOVERY_V4.md."""
import argparse,base64,hashlib,json,os,shlex,subprocess,sys,tarfile,threading,time
from pathlib import Path
MIB=1024**2
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):
    raw=json.dumps(v,indent=2).encode();assert len(raw)<128*1024
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
CENSUS=r'''
import os,resource,signal,json,hashlib,fcntl,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1024**2,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(0,)*2)
signal.alarm(30)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
d=Path(ROOT);a=json.loads((d/'ADMISSION.json').read_bytes());owners=[]
assert boot==a['boot_id']
for p in d.glob('*OWNER.json'):
 o=json.loads(p.read_bytes());assert o['boot_id']==boot and ticks(o['pid'])!=o['start_ticks'];owners.append(o)
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True,timeout=5).strip()
assert ticks(1013)==569 and ticks(1130)==607
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
for p in [d.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
files={}
for p in d.iterdir():
 assert p.is_file() and not p.is_symlink()
 files[p.name]=dict(bytes=p.stat().st_size,sha256=sha(p))
assert len(files)<=64 and sum(r['bytes'] for r in files.values())<8*1024**2
print(json.dumps(dict(owner=owner,closed_owners=owners,files=files,baseline_unchanged=True,capture_closed=True,leases_free=True)))
'''
def main(out,owner_path):
    import psutil
    psutil.Process().cpu_affinity([14])
    write(owner_path,dict(pid=os.getpid(),create_time=psutil.Process().create_time(),affinity=[14]))
    from dispatch_geometry_v2 import remote
    from dispatch_b01_stack_v2 import SSH
    plan=json.loads((out/'PLAN.json').read_bytes());a=plan['admission'];root=a['output_root']
    assert time.time()<__import__('datetime').datetime.fromisoformat(a['expires_utc']).timestamp()-75
    census=remote('ROOT='+repr(root)+'\n'+CENSUS);write(out/'CLOSED_TREE_CENSUS.json',census)
    assert subprocess.run(SSH+['test ! -e /proc/'+str(census['owner']['pid'])],timeout=10).returncode==0
    export="""import os,json,resource,signal
from pathlib import Path
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(0,)*2)
signal.alarm(45)
ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
print(json.dumps(dict(pid=os.getpid(),start_ticks=ticks,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())),flush=True)
os.execlp('tar','tar','-C',ROOT,'-cf','-','.')
"""
    command='python3 -c '+shlex.quote("import base64;exec(base64.b64decode("+repr(base64.b64encode(('ROOT='+repr(root)+'\n'+export).encode()).decode())+"))")
    proc=subprocess.Popen(SSH+[command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    timer=threading.Timer(55,proc.kill);timer.daemon=True;timer.start()
    header=proc.stdout.readline(1025);assert len(header)<1025
    exporter=json.loads(header);write(out/'EXPORT_OWNER.json',exporter)
    target=out/'target';target.mkdir();seen=set();chunks=0;total=0
    try:
        with tarfile.open(fileobj=proc.stdout,mode='r|',bufsize=16384) as tar:
            for member in tar:
                if member.isdir():assert member.name=='.';continue
                assert member.isfile() and member.name.startswith('./')
                name=member.name[2:]
                assert '/' not in name and '\\' not in name and name in census['files'] and name not in seen
                row=census['files'][name];assert member.size==row['bytes']
                stream=tar.extractfile(member);written=0
                with (target/name).open('xb') as dest:
                    while part:=stream.read(16384):
                        written+=len(part);total+=len(part);chunks+=1
                        assert total<=8*MIB and written<=row['bytes']
                        assert sum(p.stat().st_size for p in out.rglob('*') if p.is_file())+len(part)<14*MIB
                        dest.write(part)
                    dest.flush();os.fsync(dest.fileno())
                assert written==row['bytes'] and sha(target/name)==row['sha256'];seen.add(name)
        # Drain bounded tar padding before waiting for SSH natural closure.
        padding=proc.stdout.read(16385);assert len(padding)<=16384
        err=proc.stderr.read(65537);assert len(err)<65536 and proc.wait(timeout=5)==0
    finally:
        timer.cancel();proc.stdout.close();proc.stderr.close()
        if proc.poll() is None:proc.kill();proc.wait(timeout=5)
    assert seen==set(census['files'])
    assert subprocess.run(SSH+['test ! -e /proc/'+str(exporter['pid'])],timeout=10).returncode==0
    after=remote('ROOT='+repr(root)+'\n'+CENSUS);write(out/'POST_BACKUP_CENSUS.json',after)
    assert subprocess.run(SSH+['test ! -e /proc/'+str(after['owner']['pid'])],timeout=10).returncode==0
    assert after['files']==census['files']
    write(out/'BACKUP.json',dict(verified=True,files=census['files'],files_count=len(seen),bytes=total,chunks_16k=chunks,exporter=exporter,exporter_natural_exit=0,exporter_pid_absent=True))
    review=dict(status='FAILED_PRESERVED',backup_verified=True,capture_closed=True,leases_free=True,baseline_unchanged=True,microphone_function_qualified=False,live_B01_qualified=False)
    try:
        read=lambda n:json.loads((target/n).read_bytes())
        actual=read('ADMISSION.json');v=read('RESULT.json');di=read('DISPATCH_RESULT.json');e=read('LIVE_ENVELOPE.json')
        assert di['exit_code']==0 and not di['memory_guard'] and not di['log_overflow']
        assert not v['capture_opened'] and not v['models_loaded'] and not v['volatile_state_restored'] and v['hardware_lease_released']
        assert e['address_space']==[768*MIB]*2 and e['stack']==[MIB]*2 and e['affinity']==[2,3]
        props=e['properties']
        assert props['TasksMax']=='64' and props['RuntimeMaxUSec']=='5min' and props['TimeoutStopUSec']=='10s' and int(props['LimitFSIZE'])==8*MIB
        assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
        before=json.loads((out/'BEFORE_BACKUP.json').read_bytes())['files']
        for n,row in before.items():
            assert sha(out/'before'/n)==sha(out/'restore-copy'/n)==sha(target/n)==row['sha256']
        commands=[read(p.name) for p in sorted(target.glob('COMMAND_*.json'))]
        assert commands==v['commands'] and all(not c['timeout'] and c['argv'][:3]==[a['tool'],'-u','i2c'] for c in commands)
        assert all(c['started_ns']<c['ended_ns']<=u['started_ns'] for c,u in zip(commands,commands[1:]))
        assert all(c['ended_ns']-c['started_ns']<2500000000 for c in commands)
        if v['status']=='SINGLE_MAINTENANCE_SEND_FIRMWARE_READBACK_ONLY':
            assert len(commands)==6 and v['restart_commands']==1
            assert [c['argv'][3:] for c in commands]==[['VERSION'],['BLD_MSG'],['AEC_MIC_ARRAY_TYPE'],['TEST_CORE_BURN','0'],['VERSION'],['BLD_MSG']]
            assert [c['exit_code'] for c in commands]==[0,0,255,0,0,0]
            assert commands[4]['started_ns']-commands[3]['ended_ns']>=2000000000 and v['before']==v['after']
            intent=read('RESTART_INTENT.json')
            assert intent['maximum_sends']==1 and commands[2]['ended_ns']<=intent['monotonic_ns']<=commands[3]['started_ns']
            assert 'Resource could not respond' in commands[2]['stderr']
            review['status']='PASS_CONDITIONAL_SINGLE_MAINTENANCE_SEND_FIRMWARE_READBACK_ONLY'
        else:
            assert v['status']=='NO_RESTART_CURRENT_CONTROL_READABLE' and len(commands)==3 and v['restart_commands']==0
            assert [c['argv'][3:] for c in commands]==[['VERSION'],['BLD_MSG'],['AEC_MIC_ARRAY_TYPE']]
            assert all(c['exit_code']==0 for c in commands) and not (target/'RESTART_INTENT.json').exists()
            review['status']='PASS_NO_RESTART_CURRENT_CONTROL_READABLE_ONLY'
        review.update(restart_commands=v['restart_commands'],elapsed_seconds=v['elapsed_seconds'],peak_rss_bytes=v['peak_rss_bytes'],actual_envelope_verified=True,volatile_state_restored=False,closed_owner_records=len(census['closed_owners']),backup_files=len(seen),target_bytes=total,measured_chunks=chunks)
    except Exception as exc:review['error']=type(exc).__name__+': '+str(exc)
    write(out/'REVIEW.json',review);print(json.dumps(review))
    return int(review['status']=='FAILED_PRESERVED')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--owner-receipt',type=Path,required=True);a=p.parse_args()
    raise SystemExit(main(a.evidence,a.owner_receipt))
