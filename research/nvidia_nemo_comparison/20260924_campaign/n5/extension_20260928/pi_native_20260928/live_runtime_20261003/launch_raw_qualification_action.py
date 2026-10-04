"""Injected owned raw/source or headless qualification. README_QUALIFICATION_DISPATCH.md."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time

CAMPAIGN = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
MIB = 1024**2


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate qualification field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def put(path, value):
    raw = encoded(value)
    if len(raw) > 262144:
        raise ValueError('Qualification receipt bound')
    with Path(path).open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short qualification receipt')
        stream.flush(); os.fsync(stream.fileno())
    if Path(path).read_bytes() != raw:
        raise OSError('Qualification receipt readback differs')
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def inventory(package, expected_sha):
    """Pure complete inventory before any project import or native launch."""
    package = Path(package)
    if package.is_symlink() or package.resolve(strict=True) != package:
        raise ValueError('Canonical immutable package required')
    manifest_path = package/'PACKAGE_MANIFEST.json'
    if manifest_path.stat().st_size > 262144 or sha(manifest_path) != expected_sha:
        raise ValueError('Pinned package manifest changed')
    manifest = strict(manifest_path.read_bytes())
    if manifest.get('schema') != 'just-peachy.v29.package.v1' or not 1 <= len(manifest['files']) <= 512:
        raise ValueError('Bounded v29 package inventory required')
    expected = {'PACKAGE_MANIFEST.json'}
    total = 0
    for row in manifest['files']:
        name = row['path']; relative = PurePosixPath(name)
        if (relative.is_absolute() or relative.as_posix() != name or '..' in relative.parts
            or '\\' in name or name in expected or type(row['bytes']) is not int
            or not 0 <= row['bytes'] <= 2*MIB):
            raise ValueError('Invalid package member')
        expected.add(name); total += row['bytes']
        if total > 16*MIB:
            raise ValueError('Package extent exceeds preparation bound')
        path = package.joinpath(*relative.parts)
        if path.resolve(strict=True) != path or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError('Package member ownership/path changed')
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('Package member hash/extent changed')
    actual = set(); count = 0
    for directory, children, files in os.walk(package, followlinks=False):
        count += 1 + len(children) + len(files)
        if count > 2048:
            raise ValueError('Package tree membership bound')
        for name in children:
            if (Path(directory)/name).is_symlink():
                raise ValueError('Package directory symlink')
        for name in files:
            path = Path(directory)/name
            if path.is_symlink():
                raise ValueError('Package file symlink')
            actual.add(path.relative_to(package).as_posix())
    if actual != expected:
        raise ValueError('Full package inventory differs')
    return manifest


def load_pure(package, name):
    spec = importlib.util.spec_from_file_location('verified_qualification_'+name, package/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_template(template, payload, binding_sha, package):
    if hashlib.sha256(encoded(template)).hexdigest() != payload['raw_admission_template_sha256']:
        raise ValueError('Canonical reviewed raw template hash differs')
    expected = dict(schema='just-peachy.raw-qualification-template.v1', reviewed=True,
        duration_seconds=5, target=str(package), binding_sha256=binding_sha,
        package_manifest_sha256=payload['package_manifest_sha256'], boot_id=payload['boot_id'],
        installed_source_sha256=sha(package/'installed_source.py'), raw_capture_sha256=sha(package/'raw_capture.py'),
        source_batch_sha256=sha(package/'source_batch.py'))
    if any(template.get(key) != value for key, value in expected.items()):
        raise ValueError('Exact reviewed five-second raw template required')
    if type(template.get('expires_unix')) not in (int, float) or not time.time() < template['expires_unix'] <= payload['expires_unix']:
        raise ValueError('Raw template expiry is not fresh and bounded')
    return dict(template)


def budget_plan(package, binding, payload, kind):
    if kind == 'backup':
        helper=load_pure(package,'backup_reconciliation')
        spec=helper.validate_spec(payload['backup_scope'])
        if (payload['maximum_output_bytes']!=16*MIB or
            payload.get('full_backup_reservation_bytes')!=spec['maximum_payload_bytes'] or
            hashlib.sha256(encoded(spec)).hexdigest()!=payload.get('backup_scope_sha256')):
            raise ValueError('Exact independent full PC backup and16MiB native metadata reservations required')
        return dict(maximum_output_bytes=16*MIB,runtime_seconds=spec['runtime_seconds'],stop_seconds=30,
            file_limit_bytes=16*MIB,session_seconds=0,mode='read_only_snapshot',
            independent_full_backup_bytes=spec['maximum_payload_bytes'])
    if kind == 'gui':
        profiles=load_pure(package,'profiles');storage=load_pure(package,'storage')
        selection=profiles.RuntimeSelection(**payload['selection']);chosen=selection.validate()
        policy=profiles.SessionPolicy()
        if payload.get('policy')!=policy.validate() or payload.get('workflow')!='capture-save-replay-discard':
            raise ValueError('GUI check requires unchanged300s operator policy and full two-session workflow')
        stop=payload.get('stop_after_seconds')
        stop_mode=payload.get('stop_mode','button');save_raw=payload.get('save_raw',False)
        if type(stop) not in (int,float) or not 1<=stop<=300 or stop_mode not in ('button','policy'):
            raise ValueError('Explicit finite GUI Stop boundary1..300 seconds required')
        if stop_mode=='policy' and (stop!=300 or chosen['input_source']!='live'):
            raise ValueError('Policy Stop qualification requires the complete live300s source')
        if type(save_raw) is not bool or (save_raw and (chosen['input_source']!='live' or binding.get('raw_adapter_enabled') is not True)):
            raise ValueError('Save raw requires the separately qualified live raw binding')
        if chosen['provisional_correction'] or chosen.get('optional_d1_refiner') or chosen['refinement_profile']!='current_delayed' or chosen['refinement_period_seconds']!=5:
            raise ValueError('GUI plan cannot enable an unadmitted or absent control')
        disk=storage.StoragePolicy(**binding.get('storage_policy',{}))
        metadata=16*MIB+policy.maximum_session_seconds*256*1024
        allocations=[]
        for source in (chosen['input_source'],'saved'):
            spec=dict(duration_seconds=policy.maximum_session_seconds,sample_rate=16000,
                mode='processed',metadata_reserve_bytes=metadata)
            if source=='live' and binding.get('raw_adapter_enabled') is True:
                spec.update(mode='raw_processed',raw=dict(sample_rate=16000,channels=4,sample_width_bytes=4,
                    encoding='PCM_S32LE',qualification=dict(qualified=True,evidence='budget only; worker verifies actual receipt')))
            allocations.append(dict(mode=spec['mode'],audio_and_metadata_bytes=disk.estimate_bytes(spec),
                additional_allocation_bytes=metadata+disk.metadata_allowance_bytes+10*MIB))
        gui_allowance=24*MIB  #256 bounded64KiB action receipts plus8MiB wrapper/GUI output.
        required=sum(row['audio_and_metadata_bytes']+row['additional_allocation_bytes'] for row in allocations)+gui_allowance
        runtime=2*policy.total_deadline_seconds+300
        if (type(payload.get('maximum_output_bytes')) is not int or payload['maximum_output_bytes']!=required
            or required>1024*MIB or payload.get('runtime_seconds')!=runtime):
            raise ValueError('Exact independent GUI output/lifetime allocation required: bytes=%d runtime=%d'%(required,runtime))
        return dict(maximum_output_bytes=required,runtime_seconds=runtime,stop_seconds=30,
            file_limit_bytes=required,maximum_files=1024,session_seconds=300,mode='gui_two_sessions',
            session_allocations=allocations,gui_metadata_bytes=gui_allowance,selection=chosen,policy=policy.validate(),
            workflow=payload['workflow'],stop_after_seconds=stop,stop_mode=stop_mode,save_raw=save_raw)
    if kind == 'storage':
        if payload['maximum_output_bytes'] != 16*MIB:
            raise ValueError('Storage fixture check requires independent16MiB reservations')
        return dict(maximum_output_bytes=16*MIB,runtime_seconds=180,stop_seconds=30,
                    file_limit_bytes=16*MIB,session_seconds=0,mode='synthetic_storage_only')
    if kind == 'raw':
        if payload['maximum_output_bytes'] != 16*MIB:
            raise ValueError('Raw qualification needs independent 16 MiB output reservations')
        return dict(maximum_output_bytes=16*MIB, runtime_seconds=180, stop_seconds=30,
                    file_limit_bytes=32*MIB, session_seconds=5, mode='raw_processed')
    profiles = load_pure(package, 'profiles')
    storage = load_pure(package, 'storage')
    selection = profiles.RuntimeSelection(**payload['selection'])
    policy = profiles.SessionPolicy(**payload['policy'])
    selection.validate(); policy.validate()
    if kind=='full_app_hour':
        expected=profiles.SessionPolicy(3600,True,max_drain_seconds=600,max_backlog_seconds=120)
        if (policy.validate()!=expected.validate() or selection.input_source!='saved'
                or selection.optional_d1_refiner or selection.provisional_correction
                or payload.get('workflow')!='continuous-full-application-repeated-wav'
                or payload.get('repeat_input_seconds')!=3600
                or payload.get('runtime_seconds')!=4680
                or payload.get('independent_pc_copy_bytes')!=payload.get('maximum_output_bytes')):
            raise ValueError('Exact independent one-hour primary full-application admission required')
    elif policy.developer_soak:
        raise ValueError('Short headless qualification cannot admit a soak')
    metadata = 16*MIB + policy.maximum_session_seconds*256*1024
    spec = dict(duration_seconds=policy.maximum_session_seconds, sample_rate=16000,
                mode='processed', metadata_reserve_bytes=metadata)
    if binding.get('raw_adapter_enabled') is True and selection.input_source == 'live':
        # Raw is activated only by the worker's separately verified native proof.
        spec.update(mode='raw_processed', raw=dict(sample_rate=16000, channels=4,
            sample_width_bytes=4, encoding='PCM_S32LE',
            qualification=dict(qualified=True, evidence='budget-only; worker checks actual receipt')))
    disk = storage.StoragePolicy(**binding.get('storage_policy', {}))
    audio_metadata = disk.estimate_bytes(spec)
    # Complete independent allocation includes SQLite/journal duplicate, native
    # metadata, bounded process logs and wrapper receipts; no 5s-audio shortcut.
    extra = metadata + disk.metadata_allowance_bytes + (32*MIB if kind=='full_app_hour' else 10*MIB)
    required = audio_metadata + extra
    if type(payload['maximum_output_bytes']) is not int or payload['maximum_output_bytes'] != required:
        raise ValueError('Explicit full pipeline output budget differs from derived reservation: '+str(required))
    if not required <= (3*1024*MIB if kind=='full_app_hour' else 512*MIB):
        raise ValueError('Qualification output bound exceeds this short action')
    # The fresh history database is initialized by Manager before worker
    # derives its narrower SQLite ceiling. Its pages are not zero bytes.
    # Inherit the complete independently reserved output bound; worker still
    # narrows it using actual database size and available free-space reserve.
    file_limit = required
    return dict(maximum_output_bytes=required, runtime_seconds=policy.total_deadline_seconds+300,
        stop_seconds=30, file_limit_bytes=file_limit, session_seconds=policy.maximum_session_seconds,
        mode=spec['mode'], audio_and_metadata_bytes=audio_metadata, additional_allocation_bytes=extra,
        maximum_files=2048 if kind=='full_app_hour' else 256,
        selection=selection.validate(), policy=policy.validate())


def wrapper_source(settings):
    prefix = 'SETTINGS='+repr(settings)+'\n'
    body = r'''
import os,resource
os.sched_setaffinity(0,{2,3})
for kind,cap in ((resource.RLIMIT_AS,768*1024**2),(resource.RLIMIT_STACK,1024**2),(resource.RLIMIT_FSIZE,SETTINGS['budget']['file_limit_bytes']),(resource.RLIMIT_CORE,0)):
 resource.setrlimit(kind,(cap,cap))
import json,time,sys,runpy,fcntl,signal,hashlib,threading,subprocess,importlib.util,shutil,stat
from pathlib import Path
sys.dont_write_bytecode=True
threading.stack_size(1024**2)
out=Path(SETTINGS['output']);package=Path(SETTINGS['package'])
def put(name,value):
 raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 if len(raw)>262144:raise ValueError('Bounded job receipt')
 with (out/name).open('xb') as f:
  if f.write(raw)!=len(raw):raise OSError('Short job receipt')
  f.flush();os.fsync(f.fileno())
 if (out/name).read_bytes()!=raw:raise OSError('Job receipt readback differs')
 fd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
put('OWNER.json',owner)
# The actual identity above precedes every project-source read/import.
class Log:
 def __init__(self,name):self.f=(out/name).open('xb',buffering=0);self.n=0
 def write(self,text):
  raw=str(text).encode('utf-8','replace')
  if self.n+len(raw)>65536:raise RuntimeError('Finite diagnostic limit')
  count=self.f.write(raw);self.n+=count
  if count!=len(raw):raise OSError('Short diagnostic write')
  return len(text)
 def flush(self):self.f.flush();os.fsync(self.f.fileno())
sys.stdout=Log('stdout.log');sys.stderr=Log('stderr.log')
leases=[];code=1;error=None;budget_fault=None;unit_receipt=None
watch_done=threading.Event()
native_read,native_write=os.pipe()
os.dup2(native_write,1);os.dup2(native_write,2);os.close(native_write)
def native_diagnostics():
 global budget_fault
 count=0
 with (out/'native.log').open('xb',buffering=0) as stream:
  while True:
   raw=os.read(native_read,4096)
   if not raw:break
   if count+len(raw)>262144:
    budget_fault='Native diagnostic prefix exceeded 256 KiB; job failed'
    put('NATIVE_DIAGNOSTIC_FAILURE.json',dict(error=budget_fault,captured_bytes=count,physical_closure_claimed=False))
    os.kill(os.getpid(),signal.SIGTERM)
    break
   if stream.write(raw)!=len(raw):raise OSError('Short native diagnostic write')
   count+=len(raw)
  stream.flush();os.fsync(stream.fileno())
 os.close(native_read)
native_reader=threading.Thread(target=native_diagnostics,name='qualification-native-diagnostics',daemon=True)
unit_memory_stream=None;unit_memory_bytes=0;last_unit_memory=-float('inf')
def record_unit_memory():
 global unit_memory_stream,unit_memory_bytes,last_unit_memory
 if SETTINGS['kind']!='full_app_hour' or unit_receipt is None or time.monotonic()-last_unit_memory<1:return
 last_unit_memory=time.monotonic()
 group=unit_receipt['control_group'];root=Path('/sys/fs/cgroup'+group)
 pids=set();directories=0
 for directory,children,files in os.walk(root):
  directories+=1
  if directories>64:raise RuntimeError('Owned cgroup directory bound')
  if len(children)>64:raise RuntimeError('Owned cgroup child bound')
  if 'cgroup.procs' in files:
   raw=(Path(directory)/'cgroup.procs').read_text()
   if len(raw)>4096:raise RuntimeError('Owned process inventory bound')
   pids.update(int(value) for value in raw.split())
   if len(pids)>64:raise RuntimeError('Owned process count bound')
 rows=[];complete=True
 for pid in sorted(pids):
  path=Path('/proc')/str(pid)
  try:
   before=int((path/'stat').read_text().rsplit(')',1)[1].split()[19])
   status=dict(line.split(':',1) for line in (path/'status').read_text().splitlines() if ':' in line)
   rollup=dict(line.split(':',1) for line in (path/'smaps_rollup').read_text().splitlines() if ':' in line)
   after=int((path/'stat').read_text().rsplit(')',1)[1].split()[19])
   if before!=after:raise RuntimeError('Owned memory sample PID changed')
   rows.append(dict(pid=pid,start_ticks=before,rss_bytes=int(status['VmRSS'].split()[0])*1024,
    pss_bytes=int(rollup['Pss'].split()[0])*1024,virtual_bytes=int(status['VmSize'].split()[0])*1024,
    vm_peak_bytes=int(status['VmPeak'].split()[0])*1024,swap_bytes=int(status['VmSwap'].split()[0])*1024))
  except (FileNotFoundError,ProcessLookupError):complete=False
 memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line)
 available=int(memory['MemAvailable'].split()[0])*1024
 row=dict(monotonic_sec=last_unit_memory,unit=SETTINGS['unit'],invocation_id=unit_receipt['invocation_id'],
  control_group=group,boot_id=owner['boot_id'],physical_ram_bytes=int(memory['MemTotal'].split()[0])*1024,
  available_ram=available,complete_process_sample=complete,owners=rows,
  combined_rss_bytes=sum(value['rss_bytes'] for value in rows),combined_pss_bytes=sum(value['pss_bytes'] for value in rows))
 temperature=Path('/sys/class/thermal/thermal_zone0/temp')
 row['temperature_millicelsius']=int(temperature.read_text()) if temperature.is_file() else None
 row['throttling_flags']=None
 raw=json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
 if len(raw)>16384 or unit_memory_bytes+len(raw)>16*1024**2:raise RuntimeError('Finite whole-unit memory trace allowance exhausted')
 if unit_memory_stream is None:unit_memory_stream=(out/'WHOLE_UNIT_MEMORY.jsonl').open('xb')
 if unit_memory_stream.write(raw)!=len(raw):raise OSError('Short whole-unit memory trace write')
 unit_memory_stream.flush();os.fsync(unit_memory_stream.fileno());unit_memory_bytes+=len(raw)
 if available<192*1024**2:raise MemoryError('Whole-unit available RAM crossed192MiB stop floor')
def bounded_output():
 total=count=0
 def fail(reason,path,info=None,peer=None):
  detail=dict(reason=reason,path=str(path),nlink=None if info is None else info.st_nlink,
   mode=None if info is None else info.st_mode,device=None if info is None else info.st_dev,
   inode=None if info is None else info.st_ino,count=count,bytes_counted=total,
   maximum_files=SETTINGS['budget'].get('maximum_files',256),maximum_bytes=SETTINGS['budget']['maximum_output_bytes'],
   peer=None if peer is None else str(peer))
  raise ValueError('Output membership bound: '+json.dumps(detail,sort_keys=True,separators=(',',':')))
 for directory,children,files in os.walk(out,followlinks=False):
  for child in children:
   path=Path(directory)/child
   if path.is_symlink():fail('directory_symlink',path,path.lstat())
  for name in files:
   path=Path(directory)/name
   try:info=path.lstat()
   except FileNotFoundError:continue
   if not stat.S_ISREG(info.st_mode):fail('nonregular_member',path,info)
   if info.st_nlink!=1:
    # publish() briefly exposes exactly final + final.pending. Both names must
    # resolve directly to the same regular inode with exactly two links; this
    # proves there is no third alias outside the output tree. Unknown links fail.
    peer=path.with_name(name[:-8]) if name.endswith('.pending') and len(name)>8 else path.with_name(name+'.pending')
    try:other=peer.lstat()
    except FileNotFoundError:other=None
    try:current=path.lstat()
    except FileNotFoundError:
     # A listed pending/SQLite member can disappear during publication/cleanup.
     # No existing file or unexplained link is omitted from this traversal.
     continue
    if (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino) or not stat.S_ISREG(current.st_mode):
     fail('member_identity_changed',path,current,peer)
    if current.st_nlink==1:info=current
    elif (info.st_nlink==2 and current.st_nlink==2 and other is not None
      and stat.S_ISREG(other.st_mode) and other.st_nlink==2
      and (other.st_dev,other.st_ino)==(current.st_dev,current.st_ino)):
     info=current
    else:fail('unrecognized_hardlink',path,current,peer)
   count+=1
   if count>SETTINGS['budget'].get('maximum_files',256):fail('file_count',path,info)
   # A visible publication pair is charged twice, conservatively, rather than
   # granting additional output space or skipping one member's bytes.
   total+=info.st_size
   if total>SETTINGS['budget']['maximum_output_bytes']-262144:fail('output_bytes',path,info)
 return total
def watch():
 global budget_fault
 while not watch_done.wait(.2):
  try:
   record_unit_memory()
   bounded_output()
   if shutil.disk_usage(out).free<5*1024**3:raise OSError('Native free-space floor crossed')
  except BaseException as exc:
   budget_fault=repr(exc)
   put('OUTPUT_BUDGET_FAILURE.json',dict(error=budget_fault,physical_closure_claimed=False))
   os.kill(os.getpid(),signal.SIGTERM)
   return
def interrupted(signum,frame):raise TimeoutError('Finite qualification supervisor signal '+str(signum))
signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGALRM,interrupted)
signal.alarm(SETTINGS['budget']['runtime_seconds']-10)
native_reader.start()
watcher=threading.Thread(target=watch,name='qualification-output-guard',daemon=True)
try:
 if owner['boot_id']!=SETTINGS['boot_id'] or time.time()>=SETTINGS['expires_unix']:raise ValueError('Fresh native job admission expired')
 # Never acquire xvf-hardware.lock here. The isolated physical source owns it.
 lock=open(SETTINGS['research_lock'],'rb');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);leases.append(lock)
 scope_path=package/'native_scope.py'
 if hashlib.sha256(scope_path.read_bytes()).hexdigest()!=SETTINGS['scope_sha256']:raise ValueError('Pinned pure native scope helper changed')
 spec=importlib.util.spec_from_file_location('verified_job_scope',scope_path)
 scope=importlib.util.module_from_spec(spec);sys.modules[spec.name]=scope;spec.loader.exec_module(scope)
 scope.verified_inventory(package,SETTINGS['package_manifest_sha256'])
 state=scope.properties(SETTINGS['unit'])
 if (state['ActiveState']!='active' or state['MainPID']!=str(owner['pid']) or state['InvocationID']!=os.environ.get('INVOCATION_ID')
  or not state['InvocationID'] or state['AllowedCPUs'] not in ('2-3','2,3') or state['CPUQuotaPerSecUSec']!='2s'
  or state['TasksMax']!='64' or scope.duration_seconds(state['RuntimeMaxUSec'])!=SETTINGS['budget']['runtime_seconds']):raise ValueError('Actual owned qualification unit differs')
 group=state['ControlGroup']
 if not group.startswith('/user.slice/') or '..' in group.split('/') or not any(line.endswith(':'+group) for line in Path('/proc/self/cgroup').read_text().splitlines()):raise ValueError('Exact owned cgroup membership differs')
 unit_receipt=dict(unit=SETTINGS['unit'],invocation_id=state['InvocationID'],control_group=group,main_pid=owner['pid'],owner=owner,
  runtime_max_seconds=SETTINGS['budget']['runtime_seconds'],deadline_monotonic=time.monotonic()+SETTINGS['budget']['runtime_seconds']-5,idle_timeout_seconds=300)
 sys.path.insert(0,str(package))
 if SETTINGS['kind']=='raw':
  template=SETTINGS['template']
  if time.time()>=template['expires_unix']:raise ValueError('Raw template expired before source admission')
  binding_sha=hashlib.sha256((package/'BINDING.json').read_bytes()).hexdigest()
  if binding_sha!=template['binding_sha256']:raise ValueError('Template binding changed')
  for name,key in (('installed_source.py','installed_source_sha256'),('raw_capture.py','raw_capture_sha256'),('source_batch.py','source_batch_sha256')):
   if hashlib.sha256((package/name).read_bytes()).hexdigest()!=template[key]:raise ValueError('Template raw module changed')
  admission=dict(template,status='RAW_NATIVE_QUALIFICATION_ADMITTED',unit=SETTINGS['unit'],invocation_id=state['InvocationID'],
   owner=owner,issued_unix=time.time(),raw_template_sha256=SETTINGS['template_sha256'])
  put('RAW_ADMISSION.json',admission)
  admission_sha=hashlib.sha256((out/'RAW_ADMISSION.json').read_bytes()).hexdigest()
  unit_receipt['raw_admission_sha256']=admission_sha
  argv=[str(package/'raw_qualification.py'),'--binding',str(package/'BINDING.json'),'--binding-sha256',binding_sha,
   '--admission',str(out/'RAW_ADMISSION.json'),'--admission-sha256',admission_sha,'--unit',SETTINGS['unit'],
   '--unit-ownership',str(out/'UNIT_OWNERSHIP.json'),'--owner-directory',str(out/'qualification')]
 else:
  argv=SETTINGS['argv']
 put('UNIT_OWNERSHIP.json',unit_receipt)
 watcher.start();sys.argv=argv
 try:runpy.run_path(argv[0],run_name='__main__');code=0
 except SystemExit as exc:code=exc.code if type(exc.code) is int else (0 if exc.code is None else 1)
 if budget_fault is not None:raise RuntimeError(budget_fault)
 bounded_output()
except BaseException as exc:
 error=dict(type=type(exc).__name__,message=str(exc)[:4096]);code=code or 1
 import traceback;traceback.print_exc()
finally:
 watch_done.set()
 if watcher.is_alive():watcher.join(2)
 if watcher.is_alive():code=1;error=dict(type='TimeoutError',message='Output/memory watchdog still owned')
 elif unit_memory_stream is not None:unit_memory_stream.flush();os.fsync(unit_memory_stream.fileno());unit_memory_stream.close()
 os.close(1);os.close(2);native_reader.join(2)
 if native_reader.is_alive():code=1;error=dict(type='TimeoutError',message='Native diagnostic reader still owned')
 for f in reversed(leases):fcntl.flock(f,fcntl.LOCK_UN);f.close()
 signal.alarm(0)
 put('JOB_EXIT.json',dict(owner=owner,unit=SETTINGS['unit'],invocation_id=os.environ.get('INVOCATION_ID'),
  natural_returncode=code,error=error,leases_released=True,utc_unix=time.time(),output_budget_failure=budget_fault))
 sys.stdout.flush();sys.stderr.flush()
sys.exit(code)
'''
    source = prefix+body
    compile(source, '<owned-qualification-wrapper>', 'exec')
    return source


def launch(payload, baseline, *, kind='raw'):
    p = dict(payload)
    if kind not in ('raw', 'pipeline', 'storage', 'gui', 'backup','full_app_hour'):
        raise ValueError('Explicit qualification kind required')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot != p['boot_id'] or not time.time() < p['expires_unix'] <= time.time()+600:
        raise ValueError('Fresh current-boot action required')
    if baseline.get('current_project_processes') or baseline.get('active_recorded_owners') or baseline.get('live_manager_owners'):
        raise ValueError('Full existing ownership inspection must be clear')
    package = Path(p['package'])
    if package.parent != CAMPAIGN or not re.fullmatch(r'field-runtime-v29-build-\d{2}', package.name):
        raise ValueError('Explicit immutable candidate build required')
    manifest = inventory(package, p['package_manifest_sha256'])
    binding = strict((package/'BINDING.json').read_bytes())
    if manifest.get('target') != str(package) or binding.get('target') != str(package):
        raise ValueError('Exact package/binding target differs')
    binding_sha = sha(package/'BINDING.json')
    sys.dont_write_bytecode = True
    budget = budget_plan(package, binding, p, kind)
    if shutil.disk_usage(CAMPAIGN).free < 5*1024**3 + budget['maximum_output_bytes']:
        raise OSError('Native reserve plus independent complete-output allocation unavailable')
    expected_label = {'raw':r'raw-qualification-\d{2}', 'pipeline':r'pipeline-qualification-\d{2}',
                      'storage':r'storage-check-\d{2}','gui':r'gui-qualification-\d{2}',
                      'backup':r'production-backup-\d{2}','full_app_hour':r'full-app-hour-\d{2}'}[kind]
    if not re.fullmatch(expected_label, p['label']):
        raise ValueError('Fresh named qualification output root required')
    unit = 'jp-v29-'+p['label']+'.service'
    old = subprocess.run(['systemctl','--user','show',unit,'--property=LoadState'],
        capture_output=True,text=True,timeout=5)
    if old.stdout.strip() != 'LoadState=not-found':
        raise ValueError('Unique unused qualification unit required')
    template = validate_template(p['raw_admission_template'], p, binding_sha, package) if kind == 'raw' else None
    parent = CAMPAIGN/'live-runtime-tests-20261003'
    if parent.is_symlink():
        raise ValueError('Real trial parent required')
    parent.mkdir(exist_ok=True)
    output = parent/p['label']
    settings = dict(output=str(output), package=str(package), unit=unit, boot_id=boot, expires_unix=p['expires_unix'],
        package_manifest_sha256=p['package_manifest_sha256'], scope_sha256=sha(package/'native_scope.py'),
        research_lock=str(CAMPAIGN/'B05_PREVIEW_DISPATCH.lock'), budget=budget, kind=kind,
        template=template, template_sha256=p.get('raw_admission_template_sha256'))
    if kind == 'backup':
        settings['argv']=[str(package/'native_backup_guard.py'),'--output',str(output),
            '--scope-sha256',p['backup_scope_sha256']]
    elif kind in ('pipeline','full_app_hour'):
        chosen=budget['selection'];policy=budget['policy']
        argv=[str(package/'launcher.py'),'--binding',str(package/'BINDING.json'),'--data-root',str(output/'data'),
            '--unit',unit,'--unit-ownership',str(output/'UNIT_OWNERSHIP.json'),'--headless','--keep-processed',
            '--input-source',chosen['input_source'],'--diarizer',chosen['diarizer'],'--embedding',chosen['embedding'],
            '--maximum-session-seconds',str(policy['maximum_session_seconds']),
            '--max-drain-seconds',str(policy['max_drain_seconds']),'--max-backlog-seconds',str(policy['max_backlog_seconds']),
            '--embedding-schedule',chosen['embedding_schedule'],'--embedding-refresh-seconds',str(chosen['embedding_refresh_seconds']),
            '--speaker-attribution',chosen['speaker_attribution'],'--revision-window-seconds',str(chosen['revision_window_seconds'])]
        if chosen['nemotron_profile']:argv.extend(['--nemotron-profile',chosen['nemotron_profile']])
        if chosen['allow_experimental']:argv.append('--allow-experimental')
        if kind=='full_app_hour':argv.extend(['--developer-soak','--repeat-input-seconds','3600'])
        if chosen['input_source']=='saved':
            wav=Path(p['input'])
            if wav.resolve(strict=True)!=wav or CAMPAIGN not in wav.parents or wav.stat().st_size>32*MIB or sha(wav)!=p['input_sha256']:
                raise ValueError('Pinned finite saved input required')
            argv.extend(['--saved-path',str(wav)])
        settings['argv']=argv
    elif kind == 'storage':
        settings['argv']=[str(package/'native_storage_check.py'),'--binding',str(package/'BINDING.json'),
            '--package-manifest-sha256',p['package_manifest_sha256'],'--unit',unit,
            '--unit-ownership',str(output/'UNIT_OWNERSHIP.json'),'--owner-directory',str(output/'storage-check'),
            '--data-root',str(output/'storage-check/fixtures')]
    elif kind == 'gui':
        selection_raw=encoded(budget['selection'])
        argv=[str(package/'native_gui_driver.py'),'--binding',str(package/'BINDING.json'),
            '--package-manifest-sha256',p['package_manifest_sha256'],'--unit',unit,
            '--unit-ownership',str(output/'UNIT_OWNERSHIP.json'),'--owner-directory',str(output/'gui'),
            '--data-root',str(output/'data'),'--selection',str(output/'GUI_SELECTION.json'),
            '--selection-sha256',hashlib.sha256(selection_raw).hexdigest(),'--workflow',budget['workflow'],
            '--stop-after-seconds',str(budget['stop_after_seconds']), '--stop-mode',budget['stop_mode']]
        if budget['save_raw']:argv.append('--save-raw')
        if budget['selection']['input_source']=='saved':
            saved=Path(p['saved_path'])
            if saved.is_symlink() or saved.resolve(strict=True)!=saved or saved.stat().st_size>32*MIB or sha(saved)!=p['saved_sha256']:
                raise ValueError('Exact bounded GUI saved input required')
            argv.extend(['--saved-path',str(saved),'--saved-sha256',p['saved_sha256']])
        # Copy only display-address fields from the actual existing user manager.
        shown=subprocess.run(['systemctl','--user','show-environment'],capture_output=True,text=True,timeout=5,check=True)
        if len(shown.stdout)>65536:raise ValueError('Bounded user-manager environment required')
        manager_env=dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
        gui_env={name:manager_env[name] for name in ('DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS') if name in manager_env}
        if not gui_env.get('DISPLAY') or not gui_env.get('WAYLAND_DISPLAY') or not gui_env.get('XDG_RUNTIME_DIR'):
            raise ValueError('Existing desktop DISPLAY/WAYLAND_DISPLAY/XDG_RUNTIME_DIR must be present; never guess display addresses')
        if any(not value or len(value)>512 or '\n' in value or '\r' in value for value in gui_env.values()):
            raise ValueError('Bounded existing display environment required')
        settings['argv']=argv
    wrapper=wrapper_source(settings)
    output.mkdir()
    if kind=='backup':
        put(output/'BACKUP_SCOPE.json',p['backup_scope'])
    if kind=='gui':
        put(output/'GUI_SELECTION.json',budget['selection'])
        if (output/'GUI_SELECTION.json').read_bytes()!=selection_raw:raise OSError('GUI selection pin readback differs')
        put(output/'DISPLAY_ENVIRONMENT.json',gui_env)
    deadline=time.time()+budget['runtime_seconds']+budget['stop_seconds']+15
    put(output/'ADMISSION.json',dict(payload=p,budget=budget,baseline_available_ram=baseline.get('memory'),
        target_reservation_bytes=budget['maximum_output_bytes'],independent_host_reservation_bytes=budget['maximum_output_bytes'],
        binding_sha256=binding_sha,wrapper_sha256=hashlib.sha256(wrapper.encode()).hexdigest(),deadline_unix=deadline,
        capture=kind=='raw' or kind in ('pipeline','gui') and budget['selection']['input_source']=='live',asr=kind in ('pipeline','gui','full_app_hour'),source_only=kind=='raw',
        hardware_lock_owned_by='snapshot guard; capture disabled' if kind=='backup' else 'isolated physical source',native_qualification_claimed=False))
    with (output/'wrapper.py').open('xb') as stream:
        raw=wrapper.encode()
        if stream.write(raw)!=len(raw):raise OSError('Short wrapper write')
        stream.flush();os.fsync(stream.fileno())
    args=['systemd-run','--user','--unit='+unit,'--description=JustPeachyQualification',
        '--property=AllowedCPUs=2,3','--property=CPUQuota=200%','--property=TasksMax=64',
        '--property=RuntimeMaxSec='+str(budget['runtime_seconds']),'--property=TimeoutStopSec=30',
        '--property=KillMode=control-group']
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        args.append('--setenv='+key+'=1')
    for key,value in {'MALLOC_ARENA_MAX':'1','MALLOC_MMAP_THRESHOLD_':'131072','MALLOC_TRIM_THRESHOLD_':'131072'}.items():
        args.append('--setenv='+key+'='+value)
    if kind=='gui':
        args.extend('--setenv='+key+'='+value for key,value in gui_env.items())
    args.extend(['--setenv=PYTHONDONTWRITEBYTECODE=1',binding['python'],'-B',str(output/'wrapper.py')])
    started=subprocess.run(args,capture_output=True,text=True,timeout=10)
    put(output/'SYSTEMD_RUN.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    if started.returncode:
        raise RuntimeError('Qualification service creation failed; evidence retained')
    limit=time.monotonic()+5
    while not (output/'OWNER.json').exists() and time.monotonic()<limit:
        time.sleep(.05)
    owner=strict((output/'OWNER.json').read_bytes()) if (output/'OWNER.json').exists() else None
    shown=subprocess.run(['systemctl','--user','show',unit,'--property=InvocationID,MainPID,ActiveState,ControlGroup'],
        capture_output=True,text=True,timeout=5,check=True)
    props=dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
    result=dict(schema='just-peachy.native-component-job.v1',boot_id=boot,unit=unit,
        invocation_id=props.get('InvocationID'),control_group=props.get('ControlGroup'),owner=owner,output_root=str(output),
        maximum_output_bytes=budget['maximum_output_bytes'],package_manifest_sha256=p['package_manifest_sha256'],
        issued_unix=time.time(),deadline_unix=deadline,properties=props)
    if kind=='backup':
        result.update(full_backup_reservation_bytes=budget['independent_full_backup_bytes'],
            backup_scope_sha256=p['backup_scope_sha256'])
    if kind=='full_app_hour':
        result.update(workflow=p['workflow'],duration_seconds=3600,repeat_input_seconds=3600,
            maximum_output_files=2048,independent_pc_copy_bytes=budget['maximum_output_bytes'])
    put(output/'JOB.json',result)
    return result


if 'PAYLOAD' in globals():
    RESULT = launch(PAYLOAD, BASELINE)
