"""One fault-bound conditional XVF maintenance action. README_XVF_RECOVERY.md."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def qualifying_fault(value):
    commands=value.get('receipt',{}).get('commands',[])
    return bool(value.get('kind')=='CLOSED' and value.get('stream_closed') is True and
        value.get('lease_released') is True and value.get('sent_samples')==0 and
        value.get('processed_acknowledgements')==0 and value.get('integrity',{}).get('route') is None and
        value.get('integrity',{}).get('restoration_ok') is True and
        value.get('receipt',{}).get('metadata',{}).get('stream_start_return_perf_counter_ns',0)>0 and
        value.get('status',{}).get('converted_samples')==0 and len(commands)==3 and
        [row.get('command') for row in commands]==['VERSION','BLD_MSG','AEC_MIC_ARRAY_TYPE'] and
        [row.get('exit_code') for row in commands]==[0,0,255] and
        commands[0].get('stdout','').split()==['VERSION','3','2','1'] and
        'intdev-lr48-lin-i2c' in commands[1].get('stdout','') and
        'Resource could not respond' in commands[2].get('stderr',''))


SEQUENCE_SOURCE = r'''
def recovery_sequence(command,save,sleep,fault_sha):
    """Pure tested command sequence; no automatic retry or audio operation."""
    def firmware():
        version=command('VERSION');build=command('BLD_MSG')
        if (version['timeout'] or build['timeout'] or version['exit_code']!=0 or build['exit_code']!=0
            or version['stdout'].split()!=['VERSION','3','2','1'] or 'intdev-lr48-lin-i2c' not in build['stdout']):
            raise ValueError('Expected retained firmware readback unavailable')
        return dict(version=version['stdout'],build=build['stdout'])
    before=firmware();probe=command('AEC_MIC_ARRAY_TYPE')
    if not probe['timeout'] and probe['exit_code']==0:
        return dict(status='NO_SEND_CURRENT_AEC_READABLE',before=before,current_aec=probe,maintenance_sends=0)
    if probe['timeout'] or probe['exit_code']!=255 or 'Resource could not respond' not in probe['stderr']:
        raise ValueError('Fresh exact AEC255 required; no maintenance command sent')
    save('RESTART_INTENT.json',dict(fault_sha256=fault_sha,maximum_sends=1,
        command=['TEST_CORE_BURN','0'],before=before,current_aec=probe,volatile_state_restorable=False))
    reply=command('TEST_CORE_BURN',('0',))
    if reply['timeout'] or reply['exit_code']!=0:
        raise RuntimeError('Maintenance send failed or uncertain; never retry this fault')
    sleep(2)
    after=firmware()
    if after!=before:raise ValueError('Post-maintenance firmware differs')
    post=command('AEC_MIC_ARRAY_TYPE')
    if post['timeout']:raise RuntimeError('Post-maintenance AEC read timed out; no retry')
    return dict(status='SINGLE_SEND_POST_READBACK',before=before,after=after,current_aec=probe,
        maintenance_reply=reply,post_aec=post,post_aec_readable=post['exit_code']==0,
        maintenance_sends=1,audio_qualified=False,volatile_state_restored=False)
'''
exec(compile(SEQUENCE_SOURCE,'<reviewed-conditional-recovery-sequence>','exec'))


DRIVER = r'''
import os,resource,json,hashlib,time,fcntl,subprocess,sys,re,signal
from pathlib import Path
out=Path(sys.argv[1]);inputs=json.loads((out/'RECOVERY_INPUT.json').read_bytes())
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,128*1024**2))
resource.setrlimit(resource.RLIMIT_FSIZE,(65536,65536))
def save(name,value):
 raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 if len(raw)>65536:raise ValueError('Recovery receipt bound')
 with (out/name).open('xb') as stream:
  if stream.write(raw)!=len(raw):raise OSError('Short recovery receipt')
  stream.flush();os.fsync(stream.fileno())
 if (out/name).read_bytes()!=raw:raise OSError('Recovery receipt readback')
 fd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def identity(pid):
 try:ticks=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
 return dict(pid=pid,start_ticks=ticks,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
def pins_unchanged():
 for path,pin in inputs['pins'].items():
  source=Path(path)
  if source.resolve(strict=True)!=source or source.is_symlink() or source.stat().st_size!=pin['bytes']:raise ValueError('Recovery file identity/extent changed')
  with source.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
  if sha!=pin['sha256']:raise ValueError('Recovery file pin changed')
def streams_closed():
 paths=list(Path('/proc/asound').glob('card*/pcm*c/sub*/status'))
 if not paths or len(paths)>64 or any(path.read_text().strip()!='closed' for path in paths):raise ValueError('All capture streams must be closed')
commands=[]
def command(name,args=()):
 if (name,args) not in [('VERSION',()),('BLD_MSG',()),('AEC_MIC_ARRAY_TYPE',()),('TEST_CORE_BURN',('0',))] or len(commands)>=7:raise ValueError('Exact bounded command sequence required')
 if time.time()+5>=inputs['expires_unix']:raise TimeoutError('Recovery admission expired')
 index=len(commands)+1;paths=[out/('COMMAND_%02d.%s'%(index,suffix)) for suffix in ('stdout','stderr')]
 handles=[path.open('xb') for path in paths];child=None;owned=None;timed_out=False
 started=time.monotonic_ns()
 try:
  child=subprocess.Popen([inputs['tool'],'-u','i2c',name,*args],cwd=str(Path(inputs['tool']).parent),
   stdin=subprocess.DEVNULL,stdout=handles[0],stderr=handles[1])
  owned=identity(child.pid)
  if owned is None:raise RuntimeError('Actual directly owned tool identity missing')
  save('COMMAND_%02d_OWNER.json'%index,owned)
  try:child.wait(timeout=2)
  except subprocess.TimeoutExpired:
   timed_out=True
   if identity(child.pid)!=owned:raise RuntimeError('Refuse signalling any changed tool identity')
   child.kill();child.wait(timeout=2)
 finally:
  for handle in handles:handle.flush();os.fsync(handle.fileno());handle.close()
 if child is None or child.poll() is None:raise RuntimeError('Control command did not reap')
 blobs=[path.read_bytes() for path in paths]
 if any(len(raw)>65536 for raw in blobs):raise ValueError('Tool output exceeded inherited file bound')
 row=dict(command=name,arguments=list(args),exit_code=child.returncode,timeout=timed_out,owner=owned,
  directly_reaped=True,exact_owner_gone=identity(owned['pid'])!=owned,started_ns=started,ended_ns=time.monotonic_ns(),
  stdout=blobs[0].decode('utf-8','replace') if len(blobs[0])<=4096 else '',
  stderr=blobs[1].decode('utf-8','replace') if len(blobs[1])<=4096 else '',
  output_files=[dict(path=path.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for path,raw in zip(paths,blobs)])
 commands.append(row);save('COMMAND_%02d.json'%index,row)
 if not row['exact_owner_gone'] or any(len(raw)>4096 for raw in blobs):raise RuntimeError('Tool closure/output invalid; no retry')
 return row
result=dict(status='FAILED_PRESERVED',capture_opened=False,models_loaded=False,audio_qualified=False,
 fault_sha256=inputs['fault_entry']['sha256'],underlying_cause_proven=False)
lease=None
try:
 if identity(os.getpid())!=json.loads((out/'OWNER.json').read_bytes()):raise ValueError('Early actual wrapper owner differs')
 pins_unchanged();streams_closed()
 lease=Path('/home/peachyprototype/JustPeachy/data/xvf-hardware.lock').open('rb')
 fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
 # A durable intent anywhere in the bounded recovery roots consumes this exact
 # fault's one send, even if the earlier command outcome was uncertain.
 with os.scandir(out.parent) as entries:
  for index,entry in enumerate(entries):
   if index>=1024:raise ValueError('Recovery root membership bound')
   if re.fullmatch(r'xvf-recovery-[0-9]{2}',entry.name) and entry.is_dir(follow_symlinks=False):
    intent=Path(entry.path)/'RESTART_INTENT.json'
    if intent.exists():
     if intent.is_symlink() or intent.stat().st_size>65536:raise ValueError('Bounded exact prior recovery intent required')
     if json.loads(intent.read_bytes()).get('fault_sha256')==inputs['fault_entry']['sha256']:raise ValueError('This exact source fault already has a maintenance intent; no retry')
 result.update(recovery_sequence(command,save,time.sleep,inputs['fault_entry']['sha256']))
 pins_unchanged();streams_closed()
 result['files_unchanged']=True
except BaseException as exc:
 result['error']=dict(type=type(exc).__name__,message=str(exc)[:2048])
finally:
 if lease is not None:fcntl.flock(lease,fcntl.LOCK_UN);lease.close()
 result['hardware_lease_released']=True;result['commands']=commands
 result['maintenance_sends_attempted']=int((out/'RESTART_INTENT.json').exists())
 completed_sends=sum(row['command']=='TEST_CORE_BURN' for row in commands)
 result['maintenance_sends']=None if result['maintenance_sends_attempted'] and not completed_sends else completed_sends
 save('RECOVERY.json',result)
if result.get('error'):raise RuntimeError('Conditional recovery failed; receipts retained and no retry permitted')
'''


def dispatch(p,baseline):
    if baseline.get('current_project_processes') or baseline.get('active_recorded_owners') or baseline.get('live_manager_owners'):
        raise ValueError('Full current ownership precheck must be clear')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if p['boot_id']!=boot or not time.time()<p['expires_unix']<=time.time()+600:
        raise ValueError('Fresh exact boot/expiry admission required')
    if p.get('maximum_output_bytes')!=16*1024**2 or p.get('maximum_restart_commands')!=1:
        raise ValueError('One conditional send with independent16MiB output reserves required')
    campaign=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928');package=Path(p['package'])
    if package.parent!=campaign or re.fullmatch(r'field-runtime-v29-build-\d{2}',package.name) is None:
        raise ValueError('Exact admitted immutable package required')
    manifest_raw=(package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(manifest_raw)>262144 or hashlib.sha256(manifest_raw).hexdigest()!=p['package_manifest_sha256']:
        raise ValueError('Exact package manifest pin required')
    manifest=json.loads(manifest_raw);row=next(row for row in manifest['files'] if row['path']=='launch_raw_qualification_action.py')
    path=package/row['path'];source=path.read_bytes()
    if path.resolve(strict=True)!=path or len(source)!=row['bytes'] or hashlib.sha256(source).hexdigest()!=row['sha256']:
        raise ValueError('Exact shared owned wrapper source required')
    helper=dict(__name__='verified_recovery_wrapper',__file__=str(path));exec(compile(source,str(path),'exec'),helper)
    helper['inventory'](package,p['package_manifest_sha256']);binding=json.loads((package/'BINDING.json').read_bytes())
    probe=helper['load_pure'](package,'native_job_probe');utilities=[];probe.emit=utilities.append
    fault_job=p['fault_job'];root,closed=probe.inspect(fault_job)
    if (fault_job['boot_id']!=boot or fault_job['package_manifest_sha256']!=p['package_manifest_sha256']
        or not all(closed.get(key) is True for key in ('closed','exact_owner_gone','cgroup_empty'))):
        raise ValueError('Exact current-boot failed source job closure required')
    entry=p['fault_entry']
    if re.fullmatch(r'qualification/recordings/sessions/[0-9a-f]{32}/work/source/SOURCE_CLOSE.json',entry['path']) is None:
        raise ValueError('Exact closed raw-source failure member required')
    fault=root/entry['path'];raw=fault.read_bytes()
    if (fault.resolve(strict=True)!=fault or len(raw)>65536 or len(raw)!=entry['identity']['bytes'] or
        hashlib.sha256(raw).hexdigest()!=entry['sha256']):raise ValueError('Actual failed source bytes differ')
    value=json.loads(raw)
    if not qualifying_fault(value) or probe.identity(value['owner']['pid'])==value['owner']:
        raise ValueError('Actual closed active-stream AEC255 failure required')
    tool='/home/peachyprototype/JustPeachy/tools/native_xvf_usb/bin/xvf_host'
    expected={tool,'/home/peachyprototype/JustPeachy/data/live_config.json',
        '/home/peachyprototype/JustPeachy/install/current.json','/home/peachyprototype/JustPeachy/data/settings.json',
        '/home/peachyprototype/.config/kanshi/config'}
    if set(p['pins'])!=expected or p['tool']!=tool or p.get('host_backup_readback') is not True:
        raise ValueError('Exact independent tool/config/install/display backup pins required')
    if p['pins'][tool]!=dict(bytes=1773304,sha256='8cc5eebcb499faa61278c9378f7fcb92c6063a437176218404e56e610265e982'):
        raise ValueError('Previously exercised exact control tool required')
    if shutil.disk_usage(campaign).free<5*1024**3+16*1024**2:raise OSError('Independent native reserve unavailable')
    label=p['label']
    if re.fullmatch(r'xvf-recovery-\d{2}',label) is None:raise ValueError('Fresh recovery root required')
    unit='jp-v29-'+label+'.service';out=campaign/'live-runtime-tests-20261003'/label
    old=subprocess.run(['systemctl','--user','show',unit,'--property=LoadState'],capture_output=True,text=True,timeout=5)
    if old.stdout.strip()!='LoadState=not-found':raise ValueError('Unused one-attempt recovery unit required')
    out.mkdir();put=helper['put']
    for directory in ('before','restore'): (out/directory).mkdir()
    for index,(name,pin) in enumerate(sorted(p['pins'].items())):
        path=Path(name)
        if path.resolve(strict=True)!=path or path.is_symlink() or path.stat().st_nlink!=1 or path.stat().st_size!=pin['bytes'] or not 0<=pin['bytes']<=2*1024**2:
            raise ValueError('Pinned bounded current file required')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=pin['sha256']:raise ValueError('Current tool/config/install/display differs from PC restore copies')
        for directory in ('before','restore'):
            destination=out/directory/str(index)
            with destination.open('xb') as stream:
                if stream.write(data)!=len(data):raise OSError('Short independent native restore copy')
                stream.flush();os.fsync(stream.fileno())
            if destination.read_bytes()!=data:raise OSError('Independent native restore readback differs')
    put(out/'RESTORE_COPIES.json',dict(pins=p['pins'],index=sorted(p['pins']),independent_readbacks=True,volatile_state_restorable=False))
    put(out/'RECOVERY_INPUT.json',p)
    # Embed the exact pure sequence reviewed by host tests; no project recovery
    # module is inserted into or imported from the unchanged installed package.
    sequence=SEQUENCE_SOURCE
    if hashlib.sha256(sequence.encode()).hexdigest()!=p['sequence_sha256']:
        raise ValueError('Reviewed sequence pin differs')
    driver=(sequence+'\n'+DRIVER).encode()
    settings=dict(output=str(out),package=str(package),unit=unit,boot_id=boot,expires_unix=p['expires_unix'],
        package_manifest_sha256=p['package_manifest_sha256'],scope_sha256=helper['sha'](package/'native_scope.py'),
        research_lock=str(campaign/'B05_PREVIEW_DISPATCH.lock'),kind='conditional_xvf_recovery',template=None,
        budget=dict(maximum_output_bytes=16*1024**2,runtime_seconds=90,stop_seconds=10,file_limit_bytes=2*1024**2),
        argv=[str(out/'recovery_driver.py'),str(out)])
    wrapper=helper['wrapper_source'](settings).encode()
    for name,data in (('recovery_driver.py',driver),('wrapper.py',wrapper)):
        with (out/name).open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        if (out/name).read_bytes()!=data:raise OSError('Recovery driver readback')
    put(out/'ADMISSION.json',dict(payload=p,closed_fault_job=closed,source_probe_utilities=utilities,
        driver_sha256=hashlib.sha256(driver).hexdigest(),wrapper_sha256=hashlib.sha256(wrapper).hexdigest(),
        hardware_lease_owned_by='conditional maintenance driver',capture=False,models_loaded=False))
    args=['systemd-run','--user','--unit='+unit,'--description=JustPeachyConditionalXVFRecovery',
        '--property=AllowedCPUs=2,3','--property=CPUQuota=200%','--property=TasksMax=64',
        '--property=RuntimeMaxSec=90','--property=TimeoutStopSec=10','--property=KillMode=control-group',
        '--setenv=PYTHONDONTWRITEBYTECODE=1',binding['python'],'-B',str(out/'wrapper.py')]
    started=subprocess.run(args,capture_output=True,text=True,timeout=10)
    put(out/'SYSTEMD_RUN.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    if started.returncode:raise RuntimeError('Conditional recovery unit failed to launch')
    deadline=time.monotonic()+5
    while not (out/'OWNER.json').exists() and time.monotonic()<deadline:time.sleep(.05)
    owner=json.loads((out/'OWNER.json').read_bytes()) if (out/'OWNER.json').exists() else None
    shown=subprocess.run(['systemctl','--user','show',unit,'--property=InvocationID,MainPID,ActiveState,ControlGroup'],capture_output=True,text=True,timeout=5,check=True)
    props=dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
    result=dict(schema='just-peachy.native-component-job.v1',boot_id=boot,unit=unit,owner=owner,
        invocation_id=props.get('InvocationID'),control_group=props.get('ControlGroup'),properties=props,
        output_root=str(out),maximum_output_bytes=16*1024**2,package_manifest_sha256=p['package_manifest_sha256'],
        issued_unix=time.time(),deadline_unix=time.time()+115)
    put(out/'JOB.json',result);return result


if 'PAYLOAD' in globals():RESULT=dispatch(PAYLOAD,BASELINE)
