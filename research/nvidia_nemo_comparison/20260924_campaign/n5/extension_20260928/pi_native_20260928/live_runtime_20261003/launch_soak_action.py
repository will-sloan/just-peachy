"""Injected explicit continuous saved-component soak. See README_SOAK_DISPATCH.md."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time

CAMPAIGN=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
MAX_OUTPUT=256*1024**2


def require(condition,message):
    if not condition:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def put(path,value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    require(len(raw)<=262144,'Bounded soak receipt')
    with path.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short soak receipt write')
        stream.flush();os.fsync(stream.fileno())
    require(path.read_bytes()==raw,'Independent soak receipt readback')


def identity(pid):
    try:start=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None
    return dict(pid=pid,start_ticks=start,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def utility(argv,receipts,timeout=10,allowed_returncodes=(0,)):
    child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    owner=identity(child.pid)
    try:out,error=child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        child.kill();child.communicate(timeout=3)
        raise TimeoutError('Directly owned launch utility exceeded deadline; no success claim')
    require(owner is not None and len(out)<=16384 and len(error)<=4096,'Bounded actual launch utility')
    require(identity(owner['pid'])!=owner,'Launch utility exact owner remains')
    receipts.append(dict(owner=owner,returncode=child.returncode,naturally_reaped=True,exact_owner_gone=True))
    require(child.returncode in allowed_returncodes,'Launch utility failed: '+error.decode('utf-8','replace'))
    return out.decode('utf-8','strict')


def pure_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module


def native_variant_args(p):
    path,pin=p.get('native_variant'),p.get('native_variant_sha256')
    require((path is None)==(pin is None),'Native variant path and SHA256 must be supplied together')
    if path is None:return []
    require(type(path) is str and type(pin) is str and re.fullmatch('[0-9a-f]{64}',pin) is not None,
        'Exact native variant path/SHA256 required')
    name=PurePosixPath(path)
    require(name.as_posix()==path and '\\' not in path and '..' not in name.parts
        and name.name=='RUNTIME_VARIANT.json'
        and name.parent.parent==PurePosixPath(CAMPAIGN.as_posix())/'live-runtime-tests-20261003'
        and re.fullmatch('[a-z0-9-]{4,48}',name.parent.name) is not None,
        'Exact isolated native variant job descriptor required')
    require(p.get('profile') in ('chunk52','chunk52_threads2') and p.get('experimental') is True,
        'Native thread variant needs an explicit experimental Chunk52 selection')
    return ['--native-variant',path,'--native-variant-sha256',pin]


def derive_plan(p,profiles,benchmark,info):
    require(p.get('developer_soak') is True and p.get('wall_paced') is True,
        'Explicit wall-paced developer soak required')
    duration=p['duration_seconds']
    require(type(duration) is int and 3600<=duration<=86400,'Explicit continuous duration >=3600s')
    require(p.get('repeat_seconds')==duration,'Exact explicit repeat duration must match policy')
    require(type(p.get('experimental')) is bool,'Explicit experimental choice')
    require(type(p.get('maximum_output_bytes')) is int and p['maximum_output_bytes']==MAX_OUTPUT,
        'Explicit independent 256MiB source/PC output reservation required')
    require(p.get('independent_pc_copy_bytes')==MAX_OUTPUT,'Independent PC allocation must cover all output')
    selection=profiles.RuntimeSelection('nemotron','anonymous','saved',p['profile'],p['experimental'])
    policy=profiles.SessionPolicy(duration,True,p['drain_seconds'],p['backlog_seconds'])
    plan=benchmark.make_plan(info,selection,policy,repeat_seconds=duration,wall_paced=True,
        block_samples=p['block_samples'])
    variant=native_variant_args(p)
    if variant:
        plan['requested_native_variant']=dict(path=variant[1],sha256=variant[3],verified=False)
    # Reserve the entire capped C diagnostic file, Python logs, wrapper and all
    # admission/ownership/manifest receipts in addition to the benchmark plan.
    required=plan['maximum_output_bytes']+32*1024**2+2*1024**2
    require(required<=MAX_OUTPUT,'Policy/call geometry exceeds complete 256MiB output allocation')
    return policy,plan,required


WRAPPER=r'''
import os,resource
os.sched_setaffinity(0,{2,3})
for kind,cap in ((resource.RLIMIT_AS,768*1024**2),(resource.RLIMIT_STACK,1024**2),(resource.RLIMIT_FSIZE,32*1024**2),(resource.RLIMIT_CORE,0)):
 resource.setrlimit(kind,(cap,cap))
import json,time,sys,runpy,fcntl,signal,hashlib,threading
from pathlib import Path
threading.stack_size(1024**2)
sys.dont_write_bytecode=True
out=Path(OUTPUT)
def check(condition,message):
 if not condition:raise ValueError(message)
def put(name,value):
 raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 check(len(raw)<=262144,'Bounded wrapper receipt')
 with (out/name).open('xb') as stream:
  check(stream.write(raw)==len(raw),'Short wrapper receipt');stream.flush();os.fsync(stream.fileno())
owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
put('OWNER.json',owner)
# Actual owner is durable before package, input, lock or admission reads.
class Log:
 def __init__(self,name):self.stream=(out/name).open('xb',buffering=0);self.count=0
 def write(self,text):
  raw=str(text).encode('utf-8','replace');check(self.count+len(raw)<=65536,'Finite Python diagnostic cap')
  count=self.stream.write(raw);self.count+=count;check(count==len(raw),'Short diagnostic write');return len(text)
 def flush(self):self.stream.flush()
sys.stdout=Log('stdout.log');sys.stderr=Log('stderr.log')
native_log=(out/'native.log').open('xb',buffering=0)
os.dup2(native_log.fileno(),1);os.dup2(native_log.fileno(),2)
def deadline(signum,frame):raise TimeoutError('Finite admitted soak wrapper deadline')
signal.signal(signal.SIGALRM,deadline);signal.alarm(ALARM_SECONDS)
leases=[];code=1;failure=None
try:
 check(owner['boot_id']==BOOT and time.time()<EXPIRES,'Fresh exact boot-bound soak admission')
 gate=out/'UNIT_OWNERSHIP.json';wait_end=time.monotonic()+20
 while not gate.exists():
  check(time.monotonic()<wait_end,'External exact-unit ACK missing');time.sleep(.05)
 check(gate.stat().st_size<=65536 and not gate.is_symlink(),'Bounded owned-unit gate')
 receipt=json.loads(gate.read_bytes())
 check(receipt['owner']==owner and receipt['main_pid']==owner['pid'] and receipt['unit']==UNIT,
       'Exact actual main owner differs')
 check(receipt['invocation_id']==os.environ.get('INVOCATION_ID'),'Systemd invocation differs')
 check(any(line.rstrip().endswith(':'+receipt['control_group']) for line in Path('/proc/self/cgroup').read_text().splitlines()),
       'Soak outside its exact resource unit')
 check(receipt['runtime_max_seconds']==RUNTIME_SECONDS,'Admitted finite lifetime differs')
 check(time.time()<EXPIRES,'Reviewed admission expired before model gate')
 for name in (CAMPAIGN+'/B05_PREVIEW_DISPATCH.lock','/home/peachyprototype/JustPeachy/data/xvf-hardware.lock'):
  stream=open(name,'rb');fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);leases.append(stream)
 sys.path.insert(0,PACKAGE)
 check(hashlib.sha256((Path(PACKAGE)/'native_scope.py').read_bytes()).hexdigest()==SCOPE_SHA256,
       'Pinned verifier source changed before project import')
 import native_scope
 native_scope.verified_inventory(Path(PACKAGE),MANIFEST_SHA256)
 sys.argv=ARGV
 try:runpy.run_path(ARGV[0],run_name='__main__');code=0
 except SystemExit as exc:code=exc.code if type(exc.code) is int else (0 if exc.code is None else 1)
except BaseException as exc:
 failure=dict(type=type(exc).__name__,message=str(exc)[:4096])
 try:
  import traceback;traceback.print_exc()
 except BaseException:pass
finally:
 for stream in reversed(leases):fcntl.flock(stream,fcntl.LOCK_UN);stream.close()
 signal.alarm(0)
 put('JOB_EXIT.json',dict(owner=owner,unit=UNIT,invocation_id=os.environ.get('INVOCATION_ID'),
  natural_returncode=code,error=failure,leases_released=True,utc_unix=time.time(),component_only=True,
  capture=False,asr=False,embedding=False,one_continuous_native_state=True))
 sys.stdout.flush();sys.stderr.flush();os.fsync(native_log.fileno());native_log.close()
sys.exit(code)
'''


def launch(p,baseline):
    import resource
    require(os.sched_getaffinity(0)=={3} and resource.getrlimit(resource.RLIMIT_AS)[1]<=128*1024**2,
        'Dispatch must remain in its already registered CPU3/128MiB metadata envelope')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();now=time.time()
    require(p.get('schema')=='just-peachy.v29.saved-component-soak-admission.v1'
        and p.get('reviewed') is True and p.get('reviewer') and p.get('boot_id')==boot
        and type(p.get('expires_unix')) in (int,float) and math.isfinite(p['expires_unix'])
        and 0<p['expires_unix']-now<=600,'Explicit fresh reviewed soak admission required')
    package=Path(p['package'])
    require(package.parent==CAMPAIGN and re.fullmatch(r'field-runtime-v29-build-[0-9]+',package.name)
        and not package.is_symlink(),'Exact immutable candidate package')
    require(sha(package/'PACKAGE_MANIFEST.json')==p['package_manifest_sha256'],'Package manifest pin differs')
    manifest=json.loads((package/'PACKAGE_MANIFEST.json').read_bytes())
    require(manifest.get('schema')=='just-peachy.v29.package.v1' and manifest.get('target')==str(package)
        and 0<len(manifest['files'])<=512,'Bounded exact package manifest target/members')
    expected={'PACKAGE_MANIFEST.json'};total=0
    for row in manifest['files']:
        relative=PurePosixPath(row['path']);path=package/row['path'];total+=row['bytes']
        require(not relative.is_absolute() and relative.as_posix()==row['path'] and '..' not in relative.parts
            and '\\' not in row['path'] and row['path'] not in expected,'Safe unique package member')
        require(total<=16*1024**2 and 0<=row['bytes']<=2*1024**2 and path.is_file()
            and not path.is_symlink() and path.resolve()==path and path.stat().st_size==row['bytes']
            and sha(path)==row['sha256'],'Exact pinned package source required')
        expected.add(row['path'])
    require({path.relative_to(package).as_posix() for path in package.rglob('*') if path.is_file()}==expected,
        'Complete immutable package membership differs')
    binding=json.loads((package/'BINDING.json').read_bytes());binding_sha=sha(package/'BINDING.json')
    sys.dont_write_bytecode=True
    profiles=pure_module(package/'profiles.py','verified_soak_profiles')
    benchmark=pure_module(package/'native_benchmark.py','verified_soak_benchmark')
    wav=Path(p['input'])
    require(CAMPAIGN in wav.resolve(strict=True).parents and not wav.is_symlink()
        and wav.stat().st_size<=32*1024**2,'Bounded existing saved source, explicitly replayed')
    info=benchmark.inspect_wav(wav,p['input_sha256'])
    policy,plan,required=derive_plan(p,profiles,benchmark,info)
    variant=native_variant_args(p)
    if variant:
        path=Path(variant[1])
        require(path.is_file() and not path.is_symlink() and path.resolve(strict=True)==path
            and 0<path.stat().st_size<=262144 and sha(path)==variant[3],
            'Pinned isolated native variant descriptor changed')
    require(shutil.disk_usage(CAMPAIGN).free>=5*1024**3+MAX_OUTPUT,'Existing 5GiB floor plus full output allocation')
    require(type(p['label']) is str and re.fullmatch('[a-z0-9-]{4,48}',p['label']),'Unique simple soak label')
    unit='jp-v29-'+p['label']+'.service';utilities=[]
    require(utility(['systemctl','--user','show',unit,'--property=LoadState'],utilities,
        allowed_returncodes=(0,4)).strip()=='LoadState=not-found',
        'Never reuse an existing native unit')
    parent=CAMPAIGN/'live-runtime-tests-20261003'
    require(not parent.is_symlink(),'Real current iteration output parent');parent.mkdir(exist_ok=True)
    output=parent/p['label'];output.mkdir()
    argv=[str(package/'native_benchmark.py'),'--execute-native','--unit',unit,'--binding',str(package/'BINDING.json'),
        '--binding-sha256',binding_sha,'--input',str(wav),'--input-sha256',p['input_sha256'],
        '--profile',p['profile'],'--output',str(output/'benchmark'),'--duration',str(p['duration_seconds']),
        '--developer-soak','--repeat-seconds',str(p['repeat_seconds']),'--wall-paced',
        '--block-samples',str(p['block_samples']),'--drain',str(p['drain_seconds']),'--backlog',str(p['backlog_seconds'])]
    if p['experimental']:argv.append('--experimental')
    argv.extend(variant)
    runtime=math.ceil(policy.total_deadline_seconds)+150;alarm=runtime-30;stop_grace=30
    values=dict(OUTPUT=str(output),PACKAGE=str(package),CAMPAIGN=str(CAMPAIGN),ARGV=argv,BOOT=boot,
        EXPIRES=p['expires_unix'],UNIT=unit,MANIFEST_SHA256=p['package_manifest_sha256'],
        ALARM_SECONDS=alarm,RUNTIME_SECONDS=runtime,SCOPE_SHA256=sha(package/'native_scope.py'))
    wrapper='\n'.join(key+'='+repr(value) for key,value in values.items())+'\n'+WRAPPER
    compile(wrapper,'<continuous-soak-wrapper>','exec')
    with (output/'wrapper.py').open('xb') as stream:
        raw=wrapper.encode();require(stream.write(raw)==len(raw),'Short wrapper write');stream.flush();os.fsync(stream.fileno())
    issued=time.time();deadline=issued+runtime+stop_grace
    put(output/'ADMISSION.json',dict(payload=p,plan=plan,baseline_memory=baseline.get('memory'),
        required_output_bytes=required,maximum_output_bytes=MAX_OUTPUT,independent_pc_copy_bytes=MAX_OUTPUT,
        binding_sha256=binding_sha,wrapper_sha256=hashlib.sha256(raw).hexdigest(),
        runtime_max_seconds=runtime,alarm_seconds=alarm,stop_grace_seconds=stop_grace,deadline_unix=deadline,
        component_only=True,capture=False,asr=False,embedding=False,native_qualified=False))
    command=['systemd-run','--user','--quiet','--service-type=exec','--unit='+unit,
        '--description=JustPeachyContinuousSavedComponentSoak','--property=AllowedCPUs=2,3',
        '--property=CPUQuota=200%','--property=TasksMax=64','--property=RuntimeMaxSec='+str(runtime),
        '--property=TimeoutStopSec='+str(stop_grace),'--property=KillMode=control-group','--property=SendSIGKILL=yes']
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        command.append('--setenv='+key+'=1')
    for key,value in {'MALLOC_ARENA_MAX':'1','MALLOC_MMAP_THRESHOLD_':'131072','MALLOC_TRIM_THRESHOLD_':'131072'}.items():
        command.append('--setenv='+key+'='+value)
    command.extend(['--setenv=PYTHONDONTWRITEBYTECODE=1',binding['python'],'-B',str(output/'wrapper.py')])
    utility(command,utilities)
    end=time.monotonic()+5
    while not (output/'OWNER.json').exists() and time.monotonic()<end:time.sleep(.05)
    require((output/'OWNER.json').exists(),'Early actual soak owner missing; service remains finite')
    owner=json.loads((output/'OWNER.json').read_bytes())
    raw=utility(['systemctl','--user','show',unit,
        '--property=InvocationID,MainPID,ActiveState,ControlGroup,AllowedCPUs,CPUQuotaPerSecUSec,TasksMax,RuntimeMaxUSec'],utilities)
    props=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
    scope=pure_module(package/'native_scope.py','verified_soak_scope')
    require(props.get('ActiveState')=='active' and props.get('MainPID')==str(owner['pid']) and identity(owner['pid'])==owner
        and props.get('AllowedCPUs') in ('2-3','2,3') and props.get('CPUQuotaPerSecUSec')=='2s'
        and props.get('TasksMax')=='64' and scope.duration_seconds(props['RuntimeMaxUSec'])==runtime
        and re.fullmatch('[0-9a-f]{32}',props.get('InvocationID','')) and props.get('ControlGroup','').startswith('/user.slice/')
        and props['ControlGroup'].endswith('/'+unit),
        'Actual exact soak unit/owner/resource envelope differs; model gate remains closed')
    job=dict(schema='just-peachy.native-component-job.v1',boot_id=boot,unit=unit,owner=owner,
        invocation_id=props['InvocationID'],control_group=props['ControlGroup'],output_root=str(output),
        maximum_output_bytes=MAX_OUTPUT,package_manifest_sha256=p['package_manifest_sha256'],
        issued_unix=issued,deadline_unix=deadline,properties=props)
    put(output/'JOB.json',job);put(output/'LAUNCH_UTILITIES.json',utilities)
    put(output/'UNIT_OWNERSHIP.json',dict(unit=unit,invocation_id=props['InvocationID'],control_group=props['ControlGroup'],
        main_pid=owner['pid'],owner=owner,runtime_max_seconds=runtime))
    return job


if 'PAYLOAD' in globals():RESULT=launch(PAYLOAD,BASELINE)
