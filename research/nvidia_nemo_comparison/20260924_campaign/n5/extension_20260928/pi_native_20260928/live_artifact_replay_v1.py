"""Isolated native D1 ORT feature/cache cases. See README_BOUNDED_LIVE_ARTIFACTS_V1.md."""
import argparse, base64, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN = 'live-artifact-replay-v1'
MIB = 1024**2
NAMES = ['live_artifact_replay_v1.py', 'bounded_live_artifacts_v1.py', 'callback_fault_details_v1.py', 'review_live_artifacts_v1.py', 'README_BOUNDED_LIVE_ARTIFACTS_V1.md']



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
    props=subprocess.check_output(['systemctl','--user','show','jp-'+RUN+'.service','-p','LoadState','-p','ActiveState','-p','MainPID','-p','LimitAS','-p','LimitSTACK','-p','CPUQuotaPerSecUSec','-p','TasksMax','-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','LimitFSIZE','-p','ControlGroup'],text=True)
    fields=dict(x.split('=',1) for x in props.splitlines() if '=' in x)
    assert fields['TimeoutStopUSec']=='10s' and int(fields['LimitFSIZE'])==8*MIB
    assert fields['LoadState']=='loaded' and fields['ActiveState']=='active' and int(fields['MainPID'])==os.getpid()
    assert int(fields['LimitAS'])==768*MIB and fields['TasksMax']=='64' and fields['RuntimeMaxUSec']=='5min'
    quota,period=(Path('/sys/fs/cgroup')/fields['ControlGroup'].lstrip('/')/'cpu.max').read_text().split();assert int(quota)/int(period)==2
    write(root/'LIVE_ENVELOPE.json',dict(owner=owner,properties=fields,cpu_max=[quota,period],affinity=[2,3],address_space=resource.getrlimit(resource.RLIMIT_AS),stack=resource.getrlimit(resource.RLIMIT_STACK)))
    for row in a['files']:assert sha(row['path'])==row['sha256']
    result=dict(status='FAILED_PRESERVED',owner=owner,cases=[],stage_acceptance=False)
    session=None;start=time.monotonic()
    try:
        import numpy as np,wave
        from types import SimpleNamespace
        from bounded_live_artifacts_v1 import CompactJournal,PCM16Writer,OutputLimit
        for index,source in enumerate(a['journals']):
            path=Path(source['path']);assert sha(path)==source['sha256'];count=0;started=time.perf_counter()
            sink=CompactJournal(root/('journal-'+str(index)+'.compact.jsonl'),8*MIB)
            try:
                with path.open() as stream:
                    for line in stream:
                        assert len(line.encode())<=MIB
                        sink.append(json.loads(line));count+=1
                sink.close()
            finally:
                if not sink.closed:sink.close('SOURCE_FAILURE')
            assert sha(path)==source['sha256'] and count==source['events']
            result['cases'].append(dict(case='journal',index=index,source_bytes=source['bytes'],source_events=count,seconds=time.perf_counter()-started,**sink.metrics()))
        # Both byte and record limits reject before writing rejected events and keep a terminal marker.
        for name,limit,event in [('byte',512,dict(kind='fixture',payload='x'*220)),('record',128,dict(kind='fixture',payload='x'*500))]:
            sink=CompactJournal(root/('limit-'+name+'.jsonl'),1024,limit)
            for attempt in range(20):
                try:sink.append(event)
                except OutputLimit:break
            else:raise AssertionError('Output limit did not reject')
            assert sink.closed and sink.bytes<=1024 and sink.status==('BYTE_LIMIT' if name=='byte' else 'RECORD_LIMIT')
            result['cases'].append(dict(case='journal_limit',name=name,**sink.metrics()))
        with wave.open(a['source_wav'],'rb') as original:
            assert (original.getnchannels(),original.getsampwidth(),original.getframerate(),original.getnframes())==(1,2,16000,715127)
            raw=original.readframes(715127)
        samples=np.frombuffer(raw,'<i2').astype(np.float32)/32768;writer=PCM16Writer(root/'retained-source.wav',len(samples))
        for off in range(0,len(samples),3200):writer.write_float32(samples[off:off+3200],source_start_frame=off)
        writer.close();assert writer.clipped==0
        result['cases'].append(dict(case='full_pcm',**writer.metrics()))
        writer=PCM16Writer(root/'limit-pcm.wav',4);writer.write_pcm(b'\x01\x00'*3,source_start_frame=0)
        try:writer.write_pcm(b'\x02\x00'*2,source_start_frame=3)
        except OutputLimit:pass
        else:raise AssertionError('PCM frame bound ignored')
        assert writer.closed and writer.frames==3 and writer.status=='FRAME_LIMIT';result['cases'].append(dict(case='pcm_limit',**writer.metrics()))
        writer=PCM16Writer(root/'clipped-pcm.wav',6);writer.write_float32(np.array([-2,-1,0,32767/32768,1,2],np.float32),source_start_frame=0);writer.close()
        assert writer.clipped==3;result['cases'].append(dict(case='clipped_pcm',**writer.metrics()))
        writer=PCM16Writer(root/'invalid-pcm.wav',4);rejected=0
        for fn in [lambda:writer.write_pcm(b'xx',source_start_frame=1),lambda:writer.write_pcm(b'x',source_start_frame=0),lambda:writer.write_float32(np.array([float('nan')],np.float32),source_start_frame=0),lambda:writer.write_float32(np.zeros(1,np.float64),source_start_frame=0)]:
            try:fn()
            except ValueError:rejected+=1
            else:raise AssertionError('Invalid PCM accepted')
            assert writer.frames==0
        writer.close()
        try:writer.write_pcm(b'xx',source_start_frame=0)
        except RuntimeError:rejected+=1
        else:raise AssertionError('Postclose accepted')
        result['invalid_pcm_cases']=rejected
        # New end-to-end fault journal path; original callback helper remains unchanged.
        source=Path(a['prototype']);sys.path[:0]=[str(source),str(source/'vendor')]
        from app.live_audio import XVFLiveSource,LiveConfig
        from callback_fault_details_v1 import detailed_source_class
        class Abort(Exception):pass
        class Flags:
            def __init__(self,bits):
                self._flags=bits
                for i,key in enumerate(('input_underflow','input_overflow','output_underflow','output_overflow','priming_output')):setattr(self,key,bool(bits&(1<<i)))
            def __bool__(self):return bool(self._flags)
        cls=detailed_source_class(XVFLiveSource);sink=CompactJournal(root/'callback.compact.jsonl',16384);faults=[]
        for bits in [0,2]:
            s=cls(LiveConfig(host_executable='/not-opened',lease_path='/not-acquired'),sd_module=SimpleNamespace(CallbackAbort=Abort));s._capacity=4;s._route_ready=True;s._ring=np.zeros((4,480,2),np.float32)
            for name in ('_frames','_native_start','_clock','_perf_clock'):setattr(s,name,np.zeros(4,np.int64))
            for name in ('_adc','_callback_current_time'):setattr(s,name,np.zeros(4,np.float64))
            try:s._callback(np.zeros((480,2),np.float32),480,SimpleNamespace(inputBufferAdcTime=123.,currentTime=123.01),Flags(bits))
            except Abort:assert bits==2
            else:assert bits==0
            detail=s.status()['callback_fault_detail'];sink.append(dict(kind='callback_diagnostic',source_start_frame=0,callback_frames=480,detail=detail));faults.append(detail)
        sink.close();assert faults[0] is None and faults[1]['raw_status_bits']==2 and faults[1]['upstream_lost_frames'] is None
        assert 'sounddevice' not in sys.modules and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
        assert sum(x.stat().st_size for x in root.rglob('*') if x.is_file())<a['target_output_max_bytes']
        result.update(status='NATIVE_LIVE_ARTIFACT_REPLAY_REVIEW_REQUIRED',callback_records=2,models_loaded=False,capture=False,stream_constructed=False,integrated=False,real_input_gap_repaired=False)
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
                     'RuntimeMaxSec=300','TimeoutStopSec=10','LimitCORE=0','Nice=10','LimitFSIZE='+str(8*MIB)]:cmd+=['-p',prop]
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
                if available<192*MIB or (samples and samples[-1].get('VmRSS',0)*1024>640*MIB):
                    memory_guard=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
                if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>=a['target_output_max_bytes']:
                    overflow=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
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
    from window_guard_v5 import window,budget,payload_inventory
    from dispatch_geometry_v2 import remote,PRIVATE,LOCAL,REMOTE
    from dispatch_b01_stack_v2 import SSH
    w=window();c=json.loads(census_path.read_text());assert time.time()-census_path.stat().st_mtime<900
    assert c['window']['sha256']==sha(here.parent/'WINDOW_V5.json')
    for o in (c['supervisor']['host'],c['supervisor']['launcher']):
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    used=0
    for rel in ['n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928']:
        inv=payload_inventory(LOCAL/rel);assert not inv['errors'] and not inv['reparse_not_traversed'];used+=inv['total_logical_bytes']
    payload={n:base64.b64encode((here/n).read_bytes()).decode() for n in NAMES}
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
assert available>=850*1024**2 and shutil.disk_usage(r).free>=5*1024**3+64*1024**2
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
print(json.dumps(dict(boot_id=boot,available_ram_bytes=available,target_bytes=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0]),install_sha256=hashlib.sha256((Path.home()/'JustPeachy/install/current.json').read_bytes()).hexdigest(),live_config_sha256=hashlib.sha256((Path.home()/'JustPeachy/data/live_config.json').read_bytes()).hexdigest())))
''')
    assert pre['boot_id']=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43'
    assert pre['install_sha256']=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
    assert pre['live_config_sha256']=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
    delta=used-c['calculation']['window_used_bytes'];assert delta>=0
    calc=budget(c['calculation']['existing_bytes']+delta+pre['target_bytes'],used+pre['target_bytes'],64*MIB,{d:shutil.disk_usage(d+'/').free for d in ['C:','G:']},52)
    a=dict(schema='d1-ort-native.v1',admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=12)).isoformat(),
        boot_id=pre['boot_id'],install_sha256=pre['install_sha256'],live_config_sha256=pre['live_config_sha256'],
        address_space_max_bytes=768*MIB,stack_bytes=MIB,cpus=[2,3],cpu_quota_percent=200,native_threads=1,
        minimum_available_ram_bytes=850*MIB,runtime_seconds=300,tasks_max=64,output_max_bytes=64*MIB,
        combined_cap_bytes=w['maximum_new_output_bytes'],host_window_bytes=used,capture=False,
        scope='Native bounded compact event replay/PCM reopen/byte rejection and synthetic callback diagnostic path; no live stream/models',
        runtime_candidate='Model-free journal/PCM helpers; exact768MiBvirtual/1MiBstack, sampledRSS640MiB/available192MiB stops',stop_timeout_seconds=10,per_file_max_bytes=8*MIB,
        policy_sha256=sha(here.parent/'WINDOW_V5.json'),census_sha256=sha(census_path))
    inputs=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import json,hashlib
from pathlib import Path
r=Path(ROOT);old=r/'b01-live-trial-alsa-user-20260929T180625Z';journals=[]
for relative in ['data/sessions/edge_prototype_20260929T180632Z_efbf6ba0/events.jsonl','data/conversations/2d9505d0eb504233b19993a2fa9cccd9/epochs/2f4a58c0d08d468890703a0e201474e5/events.jsonl']:
 p=old/relative
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 journals.append(dict(path=str(p),sha256=h,bytes=p.stat().st_size,events=sum(1 for _ in p.open())))
prior=json.loads((r/'b01-fir-integration-v1/ADMISSION.json').read_text());source_wav=r/'d1-geometry-delayed-generic-v1/source.wav'
if not source_wav.exists():source_wav=r/'live-decimator-reference-v1/source.wav'
assert source_wav.exists(),str(source_wav)
print(json.dumps(dict(journals=journals,source_wav=str(source_wav),prototype=prior['prototype'],files=prior['files'])))
''')
    a.update(journals=inputs['journals'],source_wav=inputs['source_wav'],prototype=inputs['prototype'],prior_bound_files=inputs['files'],target_output_max_bytes=32*MIB,host_evidence_reserve_bytes=32*MIB,authority_sha256=sha(here/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json'))
    staged=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(RUN)+'\nA='+repr(a)+'\nP='+repr(payload)+'\n'+r'''
import base64,json,shutil,hashlib,sys
from pathlib import Path
r=Path(ROOT);d=r/RUN;d.mkdir()
for n,s in P.items():(d/n).write_bytes(base64.b64decode(s))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
A['files']=[dict(path=str(p),sha256=sha(p)) for p in sorted(d.rglob('*')) if p.is_file()]+A.pop('prior_bound_files')+[dict(path=x['path'],sha256=x['sha256']) for x in A['journals']]+[dict(path=A['source_wav'],sha256=sha(A['source_wav']))]
for row in A['files']:assert sha(row['path'])==row['sha256']
(d/'ADMISSION.json').write_text(json.dumps(A,indent=2))
print(json.dumps(A))
''')
    out=PRIVATE/(RUN+'-evidence');out.mkdir();write(out/'PREFLIGHT.json',dict(admission=staged,calculation=calc,target=pre))
    with (out/'launch.log').open('xb') as log:
        code=subprocess.run(SSH+['python3 -B '+REMOTE+'/'+RUN+'/live_artifact_replay_v1.py --gate'],stdout=log,stderr=subprocess.STDOUT,timeout=355).returncode
    write(out/'LAUNCH_RESULT.json',dict(exit_code=code,requires_independent_review=True))
    print(json.dumps(dict(run=RUN,exit_code=code,status='CLOSED_REVIEW_REQUIRED')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--gate',action='store_true');p.add_argument('--census',type=Path);a=p.parse_args()
    if a.worker:raise SystemExit(worker())
    elif a.gate:raise SystemExit(gate())
    else:
        if a.census is None:p.error('--census required')
        dispatch(a.census)
