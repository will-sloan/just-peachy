"""User-authorized clean OS shutdown; see README_USER_POWEROFF_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse, base64, datetime, hashlib, json, os, sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('inspect','schedule'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    O=args.output
    me=psutil.Process()
    (O/(args.phase.upper()+'_HOST_OWNER.json')).open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    scope=json.loads((O/'HOST_SCOPE_V1.json').read_bytes())
    now=datetime.datetime.now(datetime.timezone.utc)
    expiry=datetime.datetime.fromisoformat(scope['expires_utc'])
    assert now+datetime.timedelta(seconds=120)<expiry
    assert now+datetime.timedelta(seconds=120)<datetime.datetime(2026,10,1,17,42,44,tzinfo=datetime.timezone.utc)
    assert not (O/(args.phase.upper()+'_RESULT.json')).exists()
    from field_operator_broker_host_v2 import ssh_phase
    from dispatch_b01_stack_v2 import SSH
    import subprocess
    expected={}
    if args.phase=='schedule':
        inspected=json.loads((O/'INSPECT_RESULT.json').read_bytes())
        expected={x['path']:x['sha256'] for x in inspected['files']}
        receipt=json.loads((O/'CONFIG_BACKUP.json').read_bytes())
        assert receipt['files']==inspected['files']
        for row in receipt['files']:
            for folder in ('config-backup','config-restore-copy'):
                p=O/folder/row['name']
                assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
        age=(now-datetime.datetime.fromisoformat(inspected['utc'])).total_seconds()
        assert 0<=age<=120
    native=r"""
import os,resource,signal,json,sys,hashlib,subprocess,shutil,fcntl,base64,datetime
from pathlib import Path
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(0,)*2)
signal.alarm(30)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
print(json.dumps(dict(utility_owner=owner)),file=sys.stderr,flush=True)
assert boot=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43'
assert ticks(1013)==569 and ticks(1130)==607
assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
assert os.uname().machine=='aarch64'
mem={k.rstrip(':'):int(v.split()[0])*1024 for k,v in (x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines())}
assert 1500000000<mem['MemTotal']<2200000000 and mem['MemAvailable']>=192*1024**2
r=Path.home()/'JustPeachy/research/nemotron-20260928'
assert int(Path('/sys/class/block/mmcblk0/size').read_text())*512==31268536320
assert shutil.disk_usage(r).free>=5*1024**3
capture=Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()
assert capture=='closed'
for p in (r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock'):
 with p.open('r+b') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  fcntl.flock(f,fcntl.LOCK_UN)
units=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True,timeout=5)
assert not units.strip()
pins={'JustPeachy/install/current.json':'fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3','JustPeachy/data/live_config.json':'568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395','.config/kanshi/config':'c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b'}
files=[];payload={}
for rel,digest in pins.items():
 p=Path.home()/rel
 assert p.is_file() and p.stat().st_size<=65536
 raw=p.read_bytes()
 assert hashlib.sha256(raw).hexdigest()==digest
 name=rel.replace('/','__')
 files.append(dict(path=str(p),name=name,bytes=len(raw),sha256=digest))
 if PHASE=='inspect':payload[name]=base64.b64encode(raw).decode()
 if PHASE=='schedule':assert EXPECTED[str(p)]==digest
shutdown=shutil.which('shutdown')
assert shutdown and os.path.isabs(shutdown)
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),utility_owner=owner,files=files,capture=capture,research_lease_free=True,hardware_lease_free=True,units=units,available_ram_bytes=mem['MemAvailable'],target_free_bytes=shutil.disk_usage(r).free,baseline=[dict(pid=1013,start_ticks=569),dict(pid=1130,start_ticks=607)],shutdown_binary=shutdown,display_rotation=270)
if PHASE=='inspect':
 q=subprocess.run(['sudo','-n','-l',shutdown,'-P','+1'],capture_output=True,text=True,timeout=5)
 result.update(privilege_returncode=q.returncode,privilege_stdout=q.stdout,privilege_stderr=q.stderr,payload=payload)
 assert q.returncode==0
else:
 assert set(EXPECTED)=={x['path'] for x in files}
 os.sync()
 q=subprocess.run(['sudo','-n',shutdown,'-P','+1'],capture_output=True,text=True,timeout=10)
 result.update(shutdown_returncode=q.returncode,shutdown_stdout=q.stdout,shutdown_stderr=q.stderr,shutdown_requested=True,physical_power_observed=False)
 print(json.dumps(result),flush=True)
 assert q.returncode==0
 sys.exit(0)
print(json.dumps(result),flush=True)
"""
    payload=('PHASE='+repr(args.phase)+'\nEXPECTED='+repr(expected)+'\n'+native).encode()
    response=ssh_phase(['python3','-B','-'],payload=payload,timeout=40,maximum=262144)
    out=response.pop('stdout');err=response.pop('stderr')
    for suffix,raw in (('STDOUT.bin',out),('STDERR.bin',err)):
        (O/(args.phase.upper()+'_'+suffix)).open('xb').write(raw)
    (O/(args.phase.upper()+'_PHASE.json')).open('x').write(json.dumps(response))
    lines=err.splitlines()
    if lines:
        (O/(args.phase.upper()+'_NATIVE_OWNER.json')).open('x').write(json.dumps(json.loads(lines[0])['utility_owner']))
    assert response['returncode']==0 and response['fault'] is None and response['readers_joined'] and response['ssh_reaped']
    result=json.loads(out)
    assert result['utility_owner']==json.loads(lines[0])['utility_owner']
    closed=subprocess.run(SSH+['test ! -e /proc/'+str(result['utility_owner']['pid'])],capture_output=True,timeout=10)
    assert closed.returncode==0
    result['utility_pid_absent_after_ssh']=True
    if args.phase=='inspect':
        encoded=result.pop('payload')
        for folder in ('config-backup','config-restore-copy'):
            dest=O/folder;dest.mkdir()
            for row in result['files']:
                raw=base64.b64decode(encoded[row['name']],validate=True)
                assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
                with (dest/row['name']).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
                assert (dest/row['name']).read_bytes()==raw
        (O/'CONFIG_BACKUP.json').open('x').write(json.dumps(dict(files=result['files'],independent_restore_verified=True)))
    (O/(args.phase.upper()+'_RESULT.json')).open('x').write(json.dumps(result))
    print(json.dumps({k:result[k] for k in ('utc','utility_owner','capture','utility_pid_absent_after_ssh')}))
if __name__=='__main__':
    main()

