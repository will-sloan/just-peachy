"""Native natural-feature projection diagnosis. See README_D1_PROJECTION_NATIVE_V1.md."""
import argparse, base64, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN = 'd1-projection-native-v1'
MIB = 1024**2
NAMES = ['d1_projection_native_v1.py', 'README_D1_PROJECTION_NATIVE_V1.md']
CASES = ['tail','full_first','full_middle','full_tail']


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
    import resource,signal,gc
    root=Path(__file__).resolve().parent;a=json.loads((root/'ADMISSION.json').read_text())
    assert resource.getrlimit(resource.RLIMIT_AS)==(768*MIB,)*2 and resource.getrlimit(resource.RLIMIT_STACK)==(MIB,)*2
    assert sorted(os.sched_getaffinity(0))==[2,3];signal.alarm(290)
    owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=a['boot_id']);write(root/'OWNER.json',owner)
    props=subprocess.check_output(['systemctl','--user','show','jp-'+RUN+'.service','-p','LoadState','-p','ActiveState','-p','MainPID','-p','LimitAS','-p','LimitSTACK','-p','CPUQuotaPerSecUSec','-p','TasksMax','-p','RuntimeMaxUSec','-p','ControlGroup'],text=True)
    fields=dict(x.split('=',1) for x in props.splitlines() if '=' in x)
    assert fields['LoadState']=='loaded' and fields['ActiveState']=='active' and int(fields['MainPID'])==os.getpid()
    assert int(fields['LimitAS'])==768*MIB and fields['TasksMax']=='64' and fields['RuntimeMaxUSec']=='5min'
    quota,period=(Path('/sys/fs/cgroup')/fields['ControlGroup'].lstrip('/')/'cpu.max').read_text().split();assert int(quota)/int(period)==2
    write(root/'LIVE_ENVELOPE.json',dict(owner=owner,properties=fields,cpu_max=[quota,period],affinity=[2,3],address_space=resource.getrlimit(resource.RLIMIT_AS),stack=resource.getrlimit(resource.RLIMIT_STACK)))
    for row in a['files']:assert sha(row['path'])==row['sha256']
    result=dict(status='FAILED_PRESERVED',owner=owner,cases=[],stage_acceptance=False)
    session=None;start=time.monotonic()
    try:
        import numpy as np,onnxruntime as ort
        options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        options.enable_cpu_mem_arena=True
        load=time.monotonic();session=ort.InferenceSession(str(root/'preencoder.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        result['load_seconds']=time.monotonic()-load;assert session.get_providers()==['CPUExecutionProvider']
        for name in CASES:
            with np.load(root/(name+'.npz'),allow_pickle=False) as z:
                chunk=z['chunk'][None].copy();length=np.array([chunk.shape[1]],np.int64)
                before=(chunk.tobytes(),length.tobytes());first=None
                for repeat in range(2):
                    began=time.monotonic();embedding,lengths,stack=session.run(None,dict(chunk=chunk,chunk_lengths=length));seconds=time.monotonic()-began
                    assert before==(chunk.tobytes(),length.tobytes()) and np.array_equal(stack,z['stack']) and np.array_equal(lengths,z['lengths'])
                    assert embedding.shape==z['pytorch'].shape and np.isfinite(embedding).all()
                    delta=float(np.abs(embedding.astype(np.float64)-z['pytorch']).max())
                    host_delta=float(np.abs(embedding.astype(np.float64)-z['basic']).max())
                    np.savez(root/(name+'-native-'+str(repeat)+'.npz'),embedding=embedding,lengths=lengths,stack=stack)
                    if first is None:first=embedding.copy()
                    else:assert np.array_equal(first,embedding)
                    result['cases'].append(dict(case=name,repeat=repeat,seconds=seconds,reference_maxabs=delta,host_ort_maxabs=host_delta,
                        within_unchanged_gate=delta<=a['absolute_tolerance'],stack_exact=True,lengths_exact=True,inputs_unchanged=True))
        result.update(status='NATIVE_PROJECTION_OBSERVATIONS_REVIEW_REQUIRED',absolute_tolerance=a['absolute_tolerance'],
            graph_sha256=sha(root/'preencoder.onnx'),ort_version=ort.__version__,providers=session.get_providers(),
            all_reference_cases_within_gate=all(x['within_unchanged_gate'] for x in result['cases']),
            full_waveform_qualified=False,speedup_qualified=False,gate_relaxed=False)
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
    finally:
        session=None;gc.collect();result.update(session_released=True,seconds=time.monotonic()-start,ru_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write(root/'RESULT.json',result)
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
        target_bytes=int(subprocess.check_output(['du','-sb',str(campaign)],text=True).split()[0])
        assert a['host_window_bytes']+target_bytes+a['output_max_bytes']<=a['combined_cap_bytes']
        write(root/'DISPATCH_OWNER.json',dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot))
        python=str(Path.home()/'JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python')
        cmd=['systemd-run','--user','--unit=jp-'+RUN,'--wait','--pipe']
        for prop in ['CPUQuota=200%','TasksMax=64','LimitAS='+str(768*MIB),'LimitSTACK='+str(MIB),
                     'RuntimeMaxSec=300','TimeoutStopSec=10','LimitCORE=0','Nice=10','LimitFSIZE='+str(4*MIB)]:cmd+=['-p',prop]
        for key,value in dict(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
            NUMEXPR_NUM_THREADS='1',MALLOC_ARENA_MAX='1',MALLOC_MMAP_THRESHOLD_='131072',
            MALLOC_TRIM_THRESHOLD_='131072',CUDA_VISIBLE_DEVICES='',ORT_DISABLE_TELEMETRY='1').items():cmd+=['--setenv='+key+'='+value]
        cmd+=['taskset','-c','2,3',python,'-B',str(root/Path(__file__).name),'--worker']
        began=time.monotonic(); samples=[]; overflow=False; retained=0; memory_guard=False; output_guard=False
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
                available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
                if available<192*MIB or (samples and samples[-1].get('VmRSS',0)*1024>640*MIB):
                    memory_guard=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
                if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>a['output_max_bytes']:
                    output_guard=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
                if time.monotonic()-began>325:
                    subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
                time.sleep(.25)
            tail=proc.stdout.read() or b'';room=4*MIB-retained;log.write(tail[:room]);overflow|=len(tail)>room
        write(root/'DISPATCH_RESULT.json',dict(exit_code=proc.returncode,seconds=time.monotonic()-began,
            log_overflow=overflow,memory_guard=memory_guard,output_guard=output_guard,samples=samples,output_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())))
        return proc.returncode


def dispatch(census_path):
    import psutil
    psutil.Process().cpu_affinity([14]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent))
    from window_guard_v5 import window,budget,payload_inventory
    from dispatch_geometry_v2 import remote,PRIVATE,LOCAL,REMOTE
    from dispatch_b01_stack_v2 import SSH
    reference=PRIVATE/'d1-onnx-projection-v1'
    review=json.loads((reference/'REVIEW.json').read_text());assert review['status']=='REVIEWED_NATURAL_FEATURE_MATMUL_MISMATCH_LOCALIZED_ONLY'
    w=window();c=json.loads(census_path.read_text());assert time.time()-census_path.stat().st_mtime<900
    assert c['window']['sha256']==sha(here.parent/'WINDOW_V5.json')
    for o in (c['supervisor']['host'],c['supervisor']['launcher']):
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    used=0
    for rel in ['n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928']:
        inv=payload_inventory(LOCAL/rel);assert not inv['errors'] and not inv['reparse_not_traversed'];used+=inv['total_logical_bytes']
    payload={n:base64.b64encode((here/n).read_bytes()).decode() for n in NAMES}
    for n in CASES:payload[n+'.npz']=base64.b64encode((reference/(n+'.npz')).read_bytes()).decode()
    payload['preencoder.onnx']=base64.b64encode((reference/'preencoder.onnx').read_bytes()).decode()
    payload['HOST_REVIEW.json']=base64.b64encode((reference/'REVIEW.json').read_bytes()).decode()
    assert sum(len(base64.b64decode(v)) for v in payload.values())<20*MIB
    for f in PRIVATE.glob('d1-onnx-*/supervision/worker.json'):
        wr=json.loads(f.read_text());assert wr['status'] in ['FAILED','COMPLETED']
        for pk,ck in [('pid','create_time'),('child_pid','child_create_time')]:
            try:assert abs(psutil.Process(wr[pk]).create_time()-wr[ck])>.001
            except psutil.NoSuchProcess:pass
        for owner_name in ['MODEL_OWNER.json','REGISTERED_OWNER.json']:
            op=f.parent.parent/owner_name
            if op.exists():
                owner=json.loads(op.read_text());owner=owner.get('owner',owner)
                try:assert abs(psutil.Process(owner['pid']).create_time()-owner['create_time'])>.001
                except psutil.NoSuchProcess:pass
    now=datetime.now(timezone.utc);assert now+timedelta(minutes=12)<datetime.fromisoformat(w['checkpoint_utc'])
    pre=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import json,hashlib,subprocess,shutil,os
from pathlib import Path
os.sched_setaffinity(0,{3});r=Path(ROOT)
assert os.uname().machine=='aarch64'
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert ticks(1013)==569 and ticks(1130)==607 and 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
for p in r.rglob('*OWNER*.json'):
 o=json.loads(p.read_text());assert not(o['boot_id']==boot and ticks(o['pid'])==o['start_ticks'])
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
assert available>=850*1024**2 and shutil.disk_usage(r).free>=5*1024**3+64*1024**2
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
print(json.dumps(dict(boot_id=boot,available_ram_bytes=available,target_bytes=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0]),install_sha256=hashlib.sha256((Path.home()/'JustPeachy/install/current.json').read_bytes()).hexdigest(),live_config_sha256=hashlib.sha256((Path.home()/'JustPeachy/data/live_config.json').read_bytes()).hexdigest())))
''')
    assert pre['boot_id']=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43'
    assert pre['install_sha256']=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
    assert pre['live_config_sha256']=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
    delta=used-c['calculation']['window_used_bytes'];assert delta>=0
    calc=budget(c['calculation']['existing_bytes']+delta+pre['target_bytes'],used+pre['target_bytes'],64*MIB,{d:shutil.disk_usage(d+'/').free for d in ['C:','G:']},52)
    a=dict(schema='d1-projection-native.v1',admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=12)).isoformat(),
        boot_id=pre['boot_id'],install_sha256=pre['install_sha256'],live_config_sha256=pre['live_config_sha256'],
        address_space_max_bytes=768*MIB,stack_bytes=MIB,cpus=[2,3],cpu_quota_percent=200,native_threads=1,
        minimum_available_ram_bytes=850*MIB,runtime_seconds=300,tasks_max=64,output_max_bytes=32*MIB,combined_reservation_bytes=64*MIB,
        combined_cap_bytes=w['maximum_new_output_bytes'],host_window_bytes=used,capture=False,
        scope='Native compact FP32 preencoder on retained natural features; original PyTorch references and host ORT observations. Diagnostic only, no complete diarizer' ,
        runtime_candidate='ORT1.29 CPU sequential BASIC, one thread, arena on; hard768MiBvirtual, sampled RSS640MiB/available192MiB stops',absolute_tolerance=1e-5,
        policy_sha256=sha(here.parent/'WINDOW_V5.json'),census_sha256=sha(census_path),host_reference_review_sha256=sha(reference/'REVIEW.json'),
        graph_sha256=sha(reference/'preencoder.onnx'),reference_files={n+'.npz':sha(reference/(n+'.npz')) for n in CASES})
    staged=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(RUN)+'\nA='+repr(a)+'\nP='+repr(payload)+'\n'+r'''
import base64,json,shutil,hashlib,sys,os
from pathlib import Path
os.sched_setaffinity(0,{3});r=Path(ROOT);d=r/RUN;d.mkdir()
for n,s in P.items():(d/n).write_bytes(base64.b64decode(s))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
A['files']=[dict(path=str(p),sha256=sha(p)) for p in sorted(d.rglob('*')) if p.is_file()]
(d/'ADMISSION.json').write_text(json.dumps(A,indent=2))
print(json.dumps(A))
''')
    out=PRIVATE/(RUN+'-evidence');out.mkdir();write(out/'PREFLIGHT.json',dict(admission=staged,calculation=calc,target=pre))
    with (out/'launch.log').open('xb') as log:
        code=subprocess.run(SSH+['python3 -B '+REMOTE+'/'+RUN+'/d1_projection_native_v1.py --gate'],stdout=log,stderr=subprocess.STDOUT,timeout=355).returncode
    write(out/'LAUNCH_RESULT.json',dict(exit_code=code,requires_independent_review=True))
    print(json.dumps(dict(run=RUN,exit_code=code,status='CLOSED_REVIEW_REQUIRED')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--gate',action='store_true');p.add_argument('--census',type=Path);a=p.parse_args()
    if a.worker:raise SystemExit(worker())
    elif a.gate:raise SystemExit(gate())
    else:
        if a.census is None:p.error('--census required')
        dispatch(a.census)
