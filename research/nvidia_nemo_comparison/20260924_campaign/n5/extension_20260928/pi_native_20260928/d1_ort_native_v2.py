"""Isolated native D1 ORT feature/cache cases. See README_D1_ORT_NATIVE_V2.md."""
import argparse, base64, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN = 'd1-ort-native-v2'
MIB = 1024**2
NAMES = ['d1_ort_native_v2.py', 'README_D1_ORT_NATIVE_V2.md']


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
    assert resource.getrlimit(resource.RLIMIT_AS)==(1536*MIB,)*2 and resource.getrlimit(resource.RLIMIT_STACK)==(MIB,)*2
    assert sorted(os.sched_getaffinity(0))==[2,3];signal.alarm(290)
    owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=a['boot_id']);write(root/'OWNER.json',owner)
    props=subprocess.check_output(['systemctl','--user','show','jp-'+RUN+'.service','-p','LoadState','-p','ActiveState','-p','MainPID','-p','LimitAS','-p','LimitSTACK','-p','CPUQuotaPerSecUSec','-p','TasksMax','-p','RuntimeMaxUSec','-p','ControlGroup'],text=True)
    fields=dict(x.split('=',1) for x in props.splitlines() if '=' in x)
    assert fields['LoadState']=='loaded' and fields['ActiveState']=='active' and int(fields['MainPID'])==os.getpid()
    assert int(fields['LimitAS'])==1536*MIB and fields['TasksMax']=='64' and fields['RuntimeMaxUSec']=='5min'
    quota,period=(Path('/sys/fs/cgroup')/fields['ControlGroup'].lstrip('/')/'cpu.max').read_text().split();assert int(quota)/int(period)==2
    write(root/'LIVE_ENVELOPE.json',dict(owner=owner,properties=fields,cpu_max=[quota,period],affinity=[2,3],address_space=resource.getrlimit(resource.RLIMIT_AS),stack=resource.getrlimit(resource.RLIMIT_STACK)))
    for row in a['files']:assert sha(row['path'])==row['sha256']
    result=dict(status='FAILED_PRESERVED',owner=owner,cases=[],stage_acceptance=False)
    session=None;start=time.monotonic()
    try:
        import numpy as np
        import onnxruntime as ort
        assert ort.__version__=='1.29.0'
        so=ort.SessionOptions();so.intra_op_num_threads=1;so.inter_op_num_threads=1
        so.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;so.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        so.add_session_config_entry('session.intra_op.allow_spinning','0');so.add_session_config_entry('session.inter_op.allow_spinning','0')
        write(root/'PROGRESS_LOAD.json',dict(phase='before_session',monotonic=time.monotonic()))
        begin=time.monotonic();session=ort.InferenceSession(a['graph_path'],so,providers=['CPUExecutionProvider'])
        result['load_seconds']=time.monotonic()-begin;result['providers']=session.get_providers();assert result['providers']==['CPUExecutionProvider']
        write(root/'LOADED.json',dict(load_seconds=result['load_seconds'],providers=result['providers']))
        names=[x.name for x in session.get_inputs()];outputs=[x.name for x in session.get_outputs()]
        assert outputs==['spkcache_fifo_chunk_preds','chunk_pre_encode_embs','chunk_pre_encode_lengths','high_resolution_preds']
        assert names==['chunk','chunk_lengths','spkcache','spkcache_lengths','fifo','fifo_lengths']
        for name in ['delayed_warm','cold_short','dynamic_tail']:
            with np.load(root/(name+'.npz'),allow_pickle=False) as z:
                feed={n:z['input_'+n].copy() for n in names};reference=[z['reference_'+str(i)].copy() for i in range(4)]
            hashes={n:hashlib.sha256(v.tobytes()).hexdigest() for n,v in feed.items()};runs=[];secs=[]
            for repeat in range(2):
                before=time.monotonic();got=session.run(outputs,feed);secs.append(time.monotonic()-before)
                assert all(hashlib.sha256(feed[n].tobytes()).hexdigest()==h for n,h in hashes.items())
                diffs=[]
                for ref,actual in zip(reference,got):
                    assert ref.shape==actual.shape and np.isfinite(actual).all() and np.isfinite(ref).all()
                    diffs.append(float(np.max(np.abs(ref.astype('float64')-actual.astype('float64')))) if ref.size else 0.0)
                np.savez(root/(name+'-native-'+str(repeat)+'.npz'),**{'output_'+str(i):v for i,v in enumerate(got)})
                runs.append(got)
                write(root/(name+'-metrics-'+str(repeat)+'.json'),dict(seconds=secs[-1],max_abs=diffs,shapes=[list(v.shape) for v in got]))
                assert max(diffs[:2])<=a['absolute_tolerance'] and diffs[2]==0 and diffs[3]<=a['absolute_tolerance'],'Unchanged1e-5 native/reference gate failed'
            assert all(np.array_equal(x,y) for x,y in zip(*runs))
            result['cases'].append(dict(case=name,seconds=secs,repeat_exact=True,input_bytes_unchanged=True,max_abs=diffs))
        result.update(status='NATIVE_ORT_THREE_CASES_REVIEW_REQUIRED',ort_version=ort.__version__,graph_sha256=sha(a['graph_path']),high_resolution_qualified=True,complete_driver=False,speedup_qualified=False)
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
    assert available>=1408*MIB and shutil.disk_usage(root).free>=5*1024**3+a['output_max_bytes']
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
        for prop in ['CPUQuota=200%','TasksMax=64','LimitAS='+str(1536*MIB),'LimitSTACK='+str(MIB),
                     'RuntimeMaxSec=300','TimeoutStopSec=10','LimitCORE=0','Nice=10','LimitFSIZE='+str(4*MIB)]:cmd+=['-p',prop]
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
                available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
                if available<192*MIB or (samples and samples[-1].get('VmRSS',0)*1024>1152*MIB):
                    memory_guard=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
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
    from window_guard_v4 import window,budget,payload_inventory
    from dispatch_geometry_v2 import remote,PRIVATE,LOCAL,REMOTE
    from dispatch_b01_stack_v2 import SSH
    review=json.loads((PRIVATE/'d1-onnx-stage-v2-evidence/REVIEW.json').read_text());assert review['status']=='PASS_D1_GRAPH_BYTES_ENVELOPE_AND_CLOSURE_ONLY'
    w=window();c=json.loads(census_path.read_text());assert time.time()-census_path.stat().st_mtime<900
    assert c['window']['sha256']==sha(here.parent/'WINDOW_V4.json')
    for o in (c['supervisor']['host'],c['supervisor']['launcher']):
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    used=0
    for rel in ['n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928']:
        inv=payload_inventory(LOCAL/rel);assert not inv['errors'] and not inv['reparse_not_traversed'];used+=inv['total_logical_bytes']
    from stage_d1_onnx_v2 import DIGEST
    payload={n:base64.b64encode((here/n).read_bytes()).decode() for n in NAMES}
    for n in ['delayed_warm','cold_short','dynamic_tail']:payload[n+'.npz']=base64.b64encode((PRIVATE/'d1-onnx-export-v4'/(n+'.npz')).read_bytes()).decode()
    for f in PRIVATE.glob('d1-onnx-*/supervision/worker.json'):
        wr=json.loads(f.read_text());assert wr['status'] in ['FAILED','COMPLETED']
        for pk,ck in [('pid','create_time'),('child_pid','child_create_time')]:
            try:assert abs(psutil.Process(wr[pk]).create_time()-wr[ck])>.001
            except psutil.NoSuchProcess:pass
    now=datetime.now(timezone.utc);assert now+timedelta(minutes=12)<datetime.fromisoformat(w['checkpoint_utc'])
    pre=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import json,hashlib,subprocess,shutil
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
assert available>=1408*1024**2 and shutil.disk_usage(r).free>=5*1024**3+32*1024**2
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
print(json.dumps(dict(boot_id=boot,available_ram_bytes=available,target_bytes=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0]),install_sha256=hashlib.sha256((Path.home()/'JustPeachy/install/current.json').read_bytes()).hexdigest(),live_config_sha256=hashlib.sha256((Path.home()/'JustPeachy/data/live_config.json').read_bytes()).hexdigest())))
''')
    assert pre['install_sha256']=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
    assert pre['live_config_sha256']=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
    delta=used-c['calculation']['window_used_bytes'];assert delta>=0
    calc=budget(c['calculation']['existing_bytes']+delta+pre['target_bytes'],used+pre['target_bytes'],32*MIB,{d:shutil.disk_usage(d+'/').free for d in ['C:','G:']},52)
    a=dict(schema='d1-ort-native.v1',admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=12)).isoformat(),
        boot_id=pre['boot_id'],install_sha256=pre['install_sha256'],live_config_sha256=pre['live_config_sha256'],
        address_space_max_bytes=1536*MIB,stack_bytes=MIB,cpus=[2,3],cpu_quota_percent=200,native_threads=1,
        minimum_available_ram_bytes=1408*MIB,runtime_seconds=300,tasks_max=64,output_max_bytes=32*MIB,
        combined_cap_bytes=w['maximum_new_output_bytes'],host_window_bytes=used,capture=False,
        graph_path=REMOTE+'/d1-onnx-stage-v2/D1_highres_fp32.onnx',scope='Native CPU ORT FP32 feature/cache cases only; no complete waveform/state driver',
        runtime_candidate='ORT1.29 CPU sequential one thread, BASIC graph optimization; isolated1536MiBvirtual justified by400MBgraph plus loading/initializer/activation headroom, RSS1152MiB and available192MiB sampled stops retained',absolute_tolerance=1e-5,
        policy_sha256=sha(here.parent/'WINDOW_V4.json'),census_sha256=sha(census_path))
    staged=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(RUN)+'\nA='+repr(a)+'\nP='+repr(payload)+'\nDIGEST='+repr(DIGEST)+'\n'+r'''
import base64,json,shutil,hashlib,sys
from pathlib import Path
r=Path(ROOT);d=r/RUN;d.mkdir()
for n,s in P.items():(d/n).write_bytes(base64.b64decode(s))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(A['graph_path'])==DIGEST
A['files']=[dict(path=str(p),sha256=sha(p)) for p in sorted(d.rglob('*')) if p.is_file()]+[dict(path=A['graph_path'],sha256=DIGEST)]
(d/'ADMISSION.json').write_text(json.dumps(A,indent=2))
print(json.dumps(A))
''')
    out=PRIVATE/(RUN+'-evidence');out.mkdir();write(out/'PREFLIGHT.json',dict(admission=staged,calculation=calc,target=pre))
    with (out/'launch.log').open('xb') as log:
        code=subprocess.run(SSH+['python3 -B '+REMOTE+'/'+RUN+'/d1_ort_native_v2.py --gate'],stdout=log,stderr=subprocess.STDOUT,timeout=355).returncode
    write(out/'LAUNCH_RESULT.json',dict(exit_code=code,requires_independent_review=True))
    print(json.dumps(dict(run=RUN,exit_code=code,status='CLOSED_REVIEW_REQUIRED')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--gate',action='store_true');p.add_argument('--census',type=Path);a=p.parse_args()
    if a.worker:raise SystemExit(worker())
    elif a.gate:raise SystemExit(gate())
    else:
        if a.census is None:p.error('--census required')
        dispatch(a.census)
