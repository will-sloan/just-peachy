"""Injected, finite native benchmark launch. See README_BENCHMARK_DISPATCH.md."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def put(path, value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    with path.open('xb') as f:
        assert f.write(raw) == len(raw)
        f.flush(); os.fsync(f.fileno())


def launch(p):
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot == p['boot_id']
    assert time.time() < p['expires_unix'] and 0 < p['expires_unix'] - time.time() <= 600
    package = Path(p['package'])
    campaign = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
    assert package.parent == campaign and re.fullmatch(r'field-runtime-v29-build-\d{2}', package.name)
    assert sha(package/'PACKAGE_MANIFEST.json') == p['package_manifest_sha256']
    manifest = json.loads((package/'PACKAGE_MANIFEST.json').read_bytes())
    expected = {'PACKAGE_MANIFEST.json'}
    for item in manifest['files']:
        path = package/item['path']
        assert path.is_file() and not path.is_symlink() and package in path.resolve().parents
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
        expected.add(item['path'])
    assert {str(x.relative_to(package)) for x in package.rglob('*') if x.is_file()} == expected
    binding = json.loads((package/'BINDING.json').read_bytes())
    binding_sha = sha(package/'BINDING.json')
    # Pure configuration validation precedes creating a native trial root.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('verified_benchmark_profiles', package/'profiles.py')
    profiles = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = profiles
    spec.loader.exec_module(profiles)
    profiles.RuntimeSelection('nemotron', 'anonymous', 'saved', p['profile'], p.get('experimental',False)).validate()
    variant_path = p.get('native_variant')
    variant_sha = p.get('native_variant_sha256')
    assert (variant_path is None) == (variant_sha is None)
    if variant_path is not None:
        assert p['profile']=='chunk52' and p.get('experimental') is True
        assert type(variant_path) is str and type(variant_sha) is str and re.fullmatch('[0-9a-f]{64}',variant_sha)
        variant_file=Path(variant_path)
        assert variant_file.name=='RUNTIME_VARIANT.json' and variant_file.parent.parent==campaign/'live-runtime-tests-20261003'
        assert re.fullmatch('[a-z0-9-]{4,48}',variant_file.parent.name)
        assert variant_file.resolve(strict=True)==variant_file and variant_file.is_file() and not variant_file.is_symlink()
        assert variant_file.stat().st_size<=262144 and sha(variant_file)==variant_sha
    wav = Path(p['input'])
    assert campaign in wav.resolve().parents and not wav.is_symlink() and wav.stat().st_size <= 32*1024**2
    assert sha(wav) == p['input_sha256']
    native_timing = p.get('native_timing',False)
    assert type(native_timing) is bool
    required_output = (40 if native_timing else 8)*1024**2
    assert type(p['maximum_output_bytes']) is int and p['maximum_output_bytes'] == required_output
    assert shutil.disk_usage(campaign).free >= 5*1024**3 + p['maximum_output_bytes']
    assert type(p['label']) is str and re.fullmatch(r'[a-z0-9-]{4,48}', p['label'])
    unit = 'jp-v29-' + p['label'] + '.service'
    old = subprocess.run(['systemctl','--user','show',unit,'--property=LoadState'], capture_output=True, text=True, timeout=5)
    assert old.stdout.strip() == 'LoadState=not-found'
    parent = campaign/'live-runtime-tests-20261003'
    assert not parent.is_symlink()
    parent.mkdir(exist_ok=True)
    output = parent/p['label']; output.mkdir()
    argv = [str(package/'native_benchmark.py'), '--execute-native', '--unit', unit,
            '--binding', str(package/'BINDING.json'), '--binding-sha256', binding_sha,
            '--input', str(wav), '--input-sha256', p['input_sha256'],
            '--profile', p['profile'], '--output', str(output/'benchmark')]
    if p.get('experimental') is True: argv.append('--experimental')
    if p.get('wall_paced') is True: argv.append('--wall-paced')
    if variant_path is not None:
        argv.extend(['--native-variant',variant_path,'--native-variant-sha256',variant_sha])
    wrapper = r'''
import os, resource
os.sched_setaffinity(0,{2,3})
for kind,cap in ((resource.RLIMIT_AS,768*1024**2),(resource.RLIMIT_STACK,1024**2),(resource.RLIMIT_FSIZE,32*1024**2),(resource.RLIMIT_CORE,0)):
 resource.setrlimit(kind,(cap,cap))
import json,time,sys,runpy,fcntl,signal,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
out=Path(OUTPUT)
def put(name,value):
 raw=json.dumps(value,sort_keys=True,allow_nan=False).encode()
 with (out/name).open('xb') as f:
  assert f.write(raw)==len(raw);f.flush();os.fsync(f.fileno())
owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
put('OWNER.json',owner)
class Log:
 def __init__(self,name):self.f=(out/name).open('xb',buffering=0);self.n=0
 def write(self,text):
  raw=str(text).encode('utf-8','replace')
  if self.n+len(raw)>65536:raise RuntimeError('Finite diagnostic limit')
  n=self.f.write(raw);self.n+=n
  if n!=len(raw):raise IOError('Short diagnostic write')
  return len(text)
 def flush(self):self.f.flush()
sys.stdout=Log('stdout.log');sys.stderr=Log('stderr.log')
native_log=None
if NATIVE_TIMING:
 native_log=(out/'native.log').open('xb',buffering=0)
 os.dup2(native_log.fileno(),1);os.dup2(native_log.fileno(),2)
signal.alarm(470)
leases=[];code=1;error=None
try:
 assert owner['boot_id']==BOOT and time.time()<EXPIRES
 for path in (CAMPAIGN+'/B05_PREVIEW_DISPATCH.lock','/home/peachyprototype/JustPeachy/data/xvf-hardware.lock'):
  f=open(path,'rb');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);leases.append(f)
 sys.path.insert(0,PACKAGE);sys.argv=ARGV
 try:runpy.run_path(ARGV[0],run_name='__main__');code=0
 except SystemExit as exc:code=exc.code if type(exc.code) is int else (0 if exc.code is None else 1)
except BaseException as exc:
 error=dict(type=type(exc).__name__,message=str(exc)[:4096])
 import traceback;traceback.print_exc()
finally:
 for f in reversed(leases):fcntl.flock(f,fcntl.LOCK_UN);f.close()
 signal.alarm(0)
 put('JOB_EXIT.json',dict(owner=owner,unit=UNIT,invocation_id=os.environ.get('INVOCATION_ID'),natural_returncode=code,error=error,leases_released=True,utc_unix=time.time()))
 sys.stdout.flush();sys.stderr.flush()
 if native_log is not None:os.fsync(native_log.fileno());native_log.close()
sys.exit(code)
'''
    deadline = time.time()+495
    prefix = '\n'.join(f'{k}={v!r}' for k,v in dict(OUTPUT=str(output),PACKAGE=str(package),CAMPAIGN=str(campaign),ARGV=argv,BOOT=boot,EXPIRES=p['expires_unix'],UNIT=unit,NATIVE_TIMING=native_timing).items())+'\n'
    wrapper = prefix+wrapper
    compile(wrapper, '<component-wrapper>', 'exec')
    put(output/'ADMISSION.json', dict(payload=p,baseline_available_ram=BASELINE.get('memory'),
        target_reservation_bytes=p['maximum_output_bytes'], independent_host_reservation_bytes=p['maximum_output_bytes'],
        binding_sha256=binding_sha,wrapper_sha256=hashlib.sha256(wrapper.encode()).hexdigest(),deadline_unix=deadline,
        capture=False,asr=False,embedding=False,component_only=True))
    with (output/'wrapper.py').open('xb') as f:
        raw=wrapper.encode();assert f.write(raw)==len(raw);f.flush();os.fsync(f.fileno())
    args=['systemd-run','--user','--unit='+unit,'--description=JustPeachyNativeComponent',
          '--property=AllowedCPUs=2,3','--property=CPUQuota=200%','--property=TasksMax=64',
          '--property=RuntimeMaxSec=480','--property=TimeoutStopSec=15','--property=KillMode=control-group']
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        args.append('--setenv='+key+'=1')
    if native_timing:args.append('--setenv=NEMO_SPEECH_TIMING=1')
    args.extend(['--setenv=PYTHONDONTWRITEBYTECODE=1',binding['python'],'-B',str(output/'wrapper.py')])
    started=subprocess.run(args,capture_output=True,text=True,timeout=10)
    put(output/'SYSTEMD_RUN.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    assert started.returncode==0,(started.returncode,started.stderr)
    limit=time.monotonic()+3
    while not (output/'OWNER.json').exists() and time.monotonic()<limit:time.sleep(.05)
    owner=json.loads((output/'OWNER.json').read_bytes()) if (output/'OWNER.json').exists() else None
    shown=subprocess.run(['systemctl','--user','show',unit,'--property=InvocationID,MainPID,ActiveState,ControlGroup'],capture_output=True,text=True,timeout=5)
    props=dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
    result=dict(schema='just-peachy.native-component-job.v1',boot_id=boot,unit=unit,
        invocation_id=props.get('InvocationID'),control_group=props.get('ControlGroup'),owner=owner,output_root=str(output),
        maximum_output_bytes=p['maximum_output_bytes'],package_manifest_sha256=p['package_manifest_sha256'],
        issued_unix=time.time(),deadline_unix=deadline,properties=props)
    put(output/'JOB.json',result)
    return result


RESULT = launch(PAYLOAD)
