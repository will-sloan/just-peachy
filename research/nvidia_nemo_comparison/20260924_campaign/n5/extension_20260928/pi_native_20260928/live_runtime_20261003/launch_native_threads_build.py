"""Injected bounded native thread2 build action. See README_NATIVE_THREADS_BUILD.md."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

SOURCE_SHA = '9d83b3c063f7cd0c56362648f0b8f8b5a9962e884f9a533631074c59f47c895c'
MAXIMUM_OUTPUT = 64*1024**2

BUILD_SCRIPT = r'''
import os,resource
os.sched_setaffinity(0,{2,3})
for kind,cap in ((resource.RLIMIT_AS,768*1024**2),(resource.RLIMIT_STACK,1024**2),(resource.RLIMIT_FSIZE,8*1024**2),(resource.RLIMIT_CORE,0),(resource.RLIMIT_CPU,150)):
 resource.setrlimit(kind,(cap,cap))
import json,time,sys,hashlib,subprocess,shutil,fcntl,signal,threading
from pathlib import Path
sys.dont_write_bytecode=True
out=Path(OUTPUT)
def put(name,value):
 raw=json.dumps(value,sort_keys=True,allow_nan=False).encode()
 if len(raw)>262144:raise ValueError('Receipt limit')
 with (out/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
put('OWNER.json',owner)
signal.alarm(170)
leases=[];code=1;error=None
result=dict(schema='just-peachy.native-thread-build.v1',status='FAILED_PRESERVED',owner=owner,commands=[],native_execution=False,models_loaded=False,quality_evaluated=False,numerical_equivalence_evaluated=False)
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(65536),b''):h.update(block)
 return h.hexdigest()
def require(condition,message):
 if not condition:raise RuntimeError(message)
def guard():
 require(time.monotonic()<END,'Build finite deadline')
 available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
 require(available>=192*1024**2,'Build RAM floor')
 require(shutil.disk_usage(out).free>=5*1024**3,'Build disk floor')
 require(sum(x.stat().st_size for x in out.rglob('*') if x.is_file())<64*1024**2,'Build output budget')
def run(name,args,cwd):
 guard();began=time.monotonic();over=[]
 with (out/(name+'.log')).open('xb') as log:
  proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=cwd,start_new_session=True)
  def consume():
   total=0
   try:
    while True:
     block=proc.stdout.read(4096)
     if not block:break
     if total+len(block)>1024**2:
      over.append('Diagnostic cap');os.killpg(proc.pid,signal.SIGKILL);break
     log.write(block);total+=len(block)
   except BaseException as exc:over.append(type(exc).__name__)
  reader=threading.Thread(target=consume,daemon=True);reader.start()
  try:rc=proc.wait(timeout=min(65,max(.1,END-time.monotonic())))
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5);raise TimeoutError('Owned compiler command deadline')
  finally:
   reader.join(timeout=5)
   if reader.is_alive():
    try:os.killpg(proc.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    raise RuntimeError('Diagnostic drain did not close')
   proc.stdout.close();log.flush();os.fsync(log.fileno())
 result['commands'].append(dict(name=name,argv=args,returncode=rc,wall_seconds=time.monotonic()-began))
 require(rc==0 and not over,'Owned command failed: '+name+' '+str(over))
 guard()
try:
 require(os.getuid()!=0 and sorted(os.sched_getaffinity(0))==[2,3],'Non-root CPU2/3 scope required')
 require(owner['boot_id']==BOOT and time.time()<EXPIRES,'Boot/admission expiry')
 for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):require(os.environ.get(key)=='1','Numerical library environment')
 props=subprocess.run(['systemctl','--user','show',UNIT,'--property=AllowedCPUs,CPUQuotaPerSecUSec,TasksMax'],capture_output=True,text=True,timeout=5,check=True).stdout
 props=dict(line.split('=',1) for line in props.splitlines() if '=' in line)
 require(props.get('AllowedCPUs') in ('2-3','2,3') and props.get('CPUQuotaPerSecUSec')=='2s' and props.get('TasksMax')=='64','Actual resource unit properties')
 require(any(line.rstrip().endswith('/'+UNIT) for line in Path('/proc/self/cgroup').read_text().splitlines()),'Actual resource unit membership')
 for name in (CAMPAIGN+'/B05_PREVIEW_DISPATCH.lock','/home/peachyprototype/JustPeachy/data/xvf-hardware.lock'):
  f=open(name,'rb');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);leases.append(f)
 END=time.monotonic()+155
 campaign=Path(CAMPAIGN);parent=campaign/'scheduler-native-v1';dest=parent/'inputs';source=dest/'source'
 manifest_path=parent/'bundle.tar.json'
 require(sha(manifest_path)=='c1fab2b4a3041412add0a1243919600b442785e4a76be9e65aa9b5397f090066','Retained build manifest pin')
 manifest=json.loads(manifest_path.read_bytes())
 require(len(manifest['files'])==2436 and sum(row['bytes'] for row in manifest['files'])==32153457,'Exact bounded retained input set')
 for row in manifest['files']:
  path=dest/row['name']
  require(path.is_file() and not path.is_symlink() and dest in path.resolve().parents,'Canonical retained input')
  expected='b88e2ba3e4bd4f55a909e9898f5580fc559c222f3e9a257387540a21366a60c3' if row['name']=='source/src/runtime/ggml/session.cpp' else row['sha256']
  require(sha(path)==expected,'Retained input pin: '+row['name'])
 guard()
 require(sha(out/'session.cpp')==SOURCE_SHA,'Thread2 source pin')
 original=source/'src/asr/diar/sortformer_model.cpp'
 require(sha(original)=='831d819e0a3986b7b6007987a67b4ccc5f2895d6d68247ca138ed4d9c3c3d2c9','Sortformer original source pin')
 raw=original.read_bytes();needle=b'session_->set_run_cache_capacity(48);'
 require(raw.count(needle)==1,'Retained LRU patch context')
 raw=raw.replace(needle,b'session_->set_run_cache_capacity(8);')
 require(hashlib.sha256(raw).hexdigest()=='3bd6f10bc8017cd840609a35f2dae45f980c25fde880a32a4bbe24cd24eb2c86','Same retained LRU8 source pin')
 with (out/'sortformer_model.cpp').open('xb') as f:f.write(raw)
 work=out/'build';work.mkdir()
 run('compiler-version',['g++','--version'],work)
 require((out/'compiler-version.log').read_text().splitlines()[0]=='g++ (Debian 12.2.0-14+deb12u1) 12.2.0','Retained compiler version')
 common=['g++','-DGGML_BACKEND_SHARED','-DGGML_SHARED','-DGGML_USE_CPU','-DNEMO_SPEECH_VERSION_STR="0.1.0"']
 flags=['-march=armv8-a','-O3','-DNDEBUG','-std=gnu++17','-fPIC','-Wall','-Wextra']
 includes=['src/runtime/ggml','ggml/include','ggml/src','src/common']
 run('compile-session',common+['-I'+str(source/x) for x in includes]+flags+['-fvisibility=hidden','-fvisibility-inlines-hidden','-o','session.cpp.o','-c',str(out/'session.cpp')],work)
 shutil.copyfile(dest/'prebuilt/runtime.a',work/'runtime.a')
 run('replace-session',['ar','r','runtime.a','session.cpp.o'],work)
 run('index-runtime',['ranlib','runtime.a'],work)
 includes=['src/asr','src/asr/features','src/asr/encoder','src/asr/decoders','src/asr/vad','src/asr/diar','src/asr/postproc','src/asr/pnc','src/runtime/ggml','ggml/include','ggml/src','src/common']
 run('compile-sortformer',common+['-I'+str(source/x) for x in includes]+flags+['-o','sortformer_model.cpp.o','-c',str(out/'sortformer_model.cpp')],work)
 objects=sorted((dest/'objects').rglob('*.o'))
 require(len(objects)==28,'Retained object inventory')
 old=[x for x in objects if x.relative_to(dest/'objects').as_posix()=='diar/sortformer_model.cpp.o']
 require(len(old)==1,'Retained Sortformer object selection')
 objects=[str(x) for x in objects if x!=old[0]]+[str(work/'sortformer_model.cpp.o')]
 args=['g++','-fPIC','-march=armv8-a','-O3','-DNDEBUG','-Wl,--exclude-libs,libsentencepiece.a','-shared','-Wl,-soname,libnemo_speech_asr.so','-o','libnemo_speech_asr.so']+objects
 args+=['-Wl,-rpath,$ORIGIN:$ORIGIN/../lib',str(dest/'prebuilt/common.a'),'runtime.a',str(dest/'prebuilt/libsentencepiece.a')]
 args += [str(dest/'prebuilt'/x) for x in ['libggml.so.0.12.0','libggml-cpu.so.0.12.0','libggml-base.so.0.12.0']]
 run('link-asr',args,work)
 run('elf-dynamic',['readelf','-d','libnemo_speech_asr.so'],work)
 runtime=out/'runtime';runtime.mkdir()
 retained=campaign/'d1-geometry-chunk52-a76-v1/nemo-arm64/lib'
 native_files=[]
 groups=[('libggml-base.so','aab12d9b5aac8e4a23c54f9fc1c24cd95d20c62ad8f7db44e918170ea28bf48b',['','.0','.0.12.0']),('libggml.so','91e7e842bd2839bbd0b8a03ecdf9e8d9a3c4e278661915d8094b2a6cd81fc3bd',['','.0','.0.12.0']),('libggml-cpu.so','f12ac1b3912855a88bdc899fb468297d940c8730ee5942a991cc45ddf825a557',['','.0','.0.12.0']),('libnemo_speech_asr_c.so','9600de4c486aa4ea8209b6f2d78ec33fb3148d74c8a4395bd23eeaf00137915f',['','.1'])]
 copied=0
 for stem,expected,suffixes in groups:
  for suffix in suffixes:
   original=retained/(stem+suffix)
   require(campaign in original.resolve().parents and original.is_file() and sha(original)==expected,'Retained runtime library pin')
   copied+=original.stat().st_size;require(copied<=8*1024**2,'Runtime dependency copy bound')
   target=runtime/original.name;shutil.copyfile(original,target)
   require(not target.is_symlink() and sha(target)==expected,'Copied runtime library readback')
   native_files.append(dict(path=str(target),sha256=expected,bytes=target.stat().st_size))
 core=runtime/'libnemo_speech_asr.so';shutil.copyfile(work/core.name,core)
 core_sha=sha(core);require(core_sha==sha(work/core.name),'New core copy readback')
 native_files.append(dict(path=str(core),sha256=core_sha,bytes=core.stat().st_size))
 descriptor=dict(schema='just-peachy.n2.runtime.v1',nemotron_model=str(campaign/'d1-geometry-chunk52-a76-v1/D1.gguf'),nemotron_model_sha256='08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1',nemotron_library=str(runtime/'libnemo_speech_asr_c.so.1'),nemotron_library_sha256=groups[-1][1],native_runtime_files=native_files,streaming_profile='native_cm5_chunk52',native_device=dict(kind='cpu',gpu_index=-1),native_variant=dict(id='chunk52-native-threads2',configured_graph_threads=2,source_sha256=SOURCE_SHA,core_sha256=core_sha,geometry=[52,1,0,80,264,40],graph_cache_entries=8,native_qualified=False,numerical_comparison_required=True))
 put('RUNTIME_VARIANT.json',descriptor)
 put('SOURCE_VARIANT.json',dict(schema='just-peachy.native-thread-source-variant.v1',source_sha256=SOURCE_SHA,retained_metadata_sha256='679ce2e01202723e7f94233df362ad38751f5380882a6e0964db63270dac4726',native_graph_threads_requested=2,change='one graph-helper argument: 1 to 2',input_manifest_sha256=sha(manifest_path)))
 result.update(status='NATIVE_BUILD_COLLECTED_NOT_INFERENCE',source_sha256=SOURCE_SHA,source_variant_sha256=sha(out/'SOURCE_VARIANT.json'),input_manifest_sha256=sha(manifest_path),core_sha256=core_sha,runtime_variant_sha256=sha(out/'RUNTIME_VARIANT.json'),native_runtime_files=native_files,configured_native_graph_threads=2,retained_lru_entries=8,input_files_verified=len(manifest['files']))
 guard();code=0
except BaseException as exc:
 error=dict(type=type(exc).__name__,message=str(exc)[:4096]);result['error']=error
finally:
 for f in reversed(leases):fcntl.flock(f,fcntl.LOCK_UN);f.close()
 signal.alarm(0)
 put('BUILD_RESULT.json',result)
 put('JOB_EXIT.json',dict(owner=owner,unit=UNIT,invocation_id=os.environ.get('INVOCATION_ID'),natural_returncode=code,error=error,leases_released=True,utc_unix=time.time()))
sys.exit(code)
'''


def put(path,value):
    raw=json.dumps(value,sort_keys=True,allow_nan=False).encode()
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def launch(payload):
    campaign=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert os.getuid()!=0 and payload['boot_id']==boot
    assert 0<payload['expires_unix']-time.time()<=600
    assert type(payload['maximum_output_bytes']) is int and payload['maximum_output_bytes']==MAXIMUM_OUTPUT
    assert re.fullmatch('[a-z0-9-]{4,48}',payload['label'])
    assert payload['source_sha256']==SOURCE_SHA and len(payload['source_b64'])<65536
    raw=base64.b64decode(payload['source_b64'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA
    assert shutil.disk_usage(campaign).free>=5*1024**3+MAXIMUM_OUTPUT
    available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    assert available>=850*1024**2
    unit='jp-v29-'+payload['label']+'.service'
    prior=subprocess.run(['systemctl','--user','show',unit,'--property=LoadState'],capture_output=True,text=True,timeout=5)
    assert prior.stdout.strip()=='LoadState=not-found'
    parent=campaign/'live-runtime-tests-20261003';assert not parent.is_symlink();parent.mkdir(exist_ok=True)
    output=parent/payload['label'];output.mkdir()
    with (output/'session.cpp').open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    prefix='\n'.join(key+'='+repr(value) for key,value in dict(OUTPUT=str(output),CAMPAIGN=str(campaign),BOOT=boot,EXPIRES=payload['expires_unix'],UNIT=unit,SOURCE_SHA=SOURCE_SHA).items())+'\n'
    wrapper=prefix+BUILD_SCRIPT;compile(wrapper,'<native-thread-build>','exec')
    with (output/'wrapper.py').open('xb') as stream:stream.write(wrapper.encode());stream.flush();os.fsync(stream.fileno())
    deadline=time.time()+200
    put(output/'ADMISSION.json',dict(payload={k:v for k,v in payload.items() if k!='source_b64'},source_bytes=len(raw),wrapper_sha256=hashlib.sha256(wrapper.encode()).hexdigest(),target_reservation_bytes=MAXIMUM_OUTPUT,independent_host_reservation_bytes=MAXIMUM_OUTPUT,baseline_available_ram=available,deadline_unix=deadline,models_loaded=False,build_only=True))
    python='/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python'
    argv=['systemd-run','--user','--unit='+unit,'--description=JustPeachyNativeThreadBuild','--property=AllowedCPUs=2,3','--property=CPUQuota=200%','--property=TasksMax=64','--property=RuntimeMaxSec=180','--property=TimeoutStopSec=15','--property=KillMode=control-group']
    argv+=['--setenv='+key+'=1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')]
    argv+=['--setenv=PYTHONDONTWRITEBYTECODE=1',python,'-B',str(output/'wrapper.py')]
    started=subprocess.run(argv,capture_output=True,text=True,timeout=10)
    put(output/'SYSTEMD_RUN.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    assert started.returncode==0
    end=time.monotonic()+3
    while not (output/'OWNER.json').exists() and time.monotonic()<end:time.sleep(.05)
    owner=json.loads((output/'OWNER.json').read_bytes()) if (output/'OWNER.json').exists() else None
    shown=subprocess.run(['systemctl','--user','show',unit,'--property=InvocationID,MainPID,ActiveState,ControlGroup'],capture_output=True,text=True,timeout=5)
    props=dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
    result=dict(schema='just-peachy.native-component-job.v1',job_kind='native-thread-build',boot_id=boot,unit=unit,invocation_id=props.get('InvocationID'),control_group=props.get('ControlGroup'),owner=owner,output_root=str(output),maximum_output_bytes=MAXIMUM_OUTPUT,package_manifest_kind='retained-native-build-bundle',package_manifest_sha256='c1fab2b4a3041412add0a1243919600b442785e4a76be9e65aa9b5397f090066',issued_unix=time.time(),deadline_unix=deadline,properties=props)
    put(output/'JOB.json',result)
    return result


RESULT=launch(PAYLOAD)
