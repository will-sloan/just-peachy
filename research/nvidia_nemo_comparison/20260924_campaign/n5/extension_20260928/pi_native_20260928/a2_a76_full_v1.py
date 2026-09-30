"""A2 A76 CPU comparison. See README_A2_A76_FULL_V1.md."""
import argparse, base64, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN = 'a2-a76-full-v1'
MIB = 1024**2
NAMES = ['a2_a76_full_v1.py', 'README_A2_A76_FULL_V1.md']


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
    import resource, signal
    root = Path(__file__).resolve().parent
    a = json.loads((root/'ADMISSION.json').read_text())
    assert resource.getrlimit(resource.RLIMIT_AS) == (a['address_space_max_bytes'],)*2
    assert resource.getrlimit(resource.RLIMIT_STACK) == (MIB,)*2
    assert sorted(os.sched_getaffinity(0)) == [2, 3]
    signal.alarm(590)
    owner = dict(pid=os.getpid(), start_ticks=ticks(os.getpid()), boot_id=a['boot_id'])
    write(root/'OWNER.json', owner)
    # Retain actual live properties, never garbage-collected unit defaults.
    props = subprocess.check_output(['systemctl', '--user', 'show', 'jp-'+RUN+'.service',
        '-p', 'LoadState', '-p', 'ActiveState', '-p', 'MainPID', '-p', 'LimitAS',
        '-p', 'LimitSTACK', '-p', 'CPUQuotaPerSecUSec', '-p', 'TasksMax',
        '-p', 'RuntimeMaxUSec', '-p', 'ControlGroup'], text=True)
    fields = dict(x.split('=', 1) for x in props.splitlines() if '=' in x)
    assert fields['LoadState'] == 'loaded' and fields['ActiveState'] == 'active'
    assert int(fields['MainPID']) == os.getpid()
    assert int(fields['LimitAS']) == a['address_space_max_bytes']
    assert int(fields['LimitSTACK']) == MIB and fields['TasksMax'] == '64'
    cg = Path('/sys/fs/cgroup')/fields['ControlGroup'].lstrip('/')
    quota, period = (cg/'cpu.max').read_text().split()
    assert quota != 'max' and int(quota) / int(period) == 2
    write(root/'LIVE_ENVELOPE.json', dict(properties=fields, affinity=[2, 3],
        cpu_max=[quota, period], address_space=resource.getrlimit(resource.RLIMIT_AS),
        stack=resource.getrlimit(resource.RLIMIT_STACK), owner=owner))
    for row in a['files']: assert sha(row['path']) == row['sha256'], row['path']
    sys.path.insert(0, str(root))
    import n3_asr_native as adapter
    import numpy as np
    import wave
    binding = json.loads((root/'BINDING.json').read_text())
    result = dict(status='FAILED_PRESERVED', owner=owner, sessions=[], stage_acceptance=False,
        scope='A2 A76 kernel candidate: full-source/resident repeat and exact retained generic canonical events; no accuracy or logits-parity qualification')
    model = None
    start = time.monotonic()
    try:
        with wave.open(a['source_wav'], 'rb') as wav:
            assert wav.getframerate() == 16000 and wav.getnchannels() == 1 and wav.getsampwidth() == 2
            samples = np.frombuffer(wav.readframes(715127), dtype='<i2').astype(np.float32)/32768
        assert len(samples) == 715127
        write(root/'PROGRESS_LOAD.json', dict(phase='before_create', monotonic=time.monotonic()))
        model = adapter.NativeRecognizer(binding)
        result['loaded_cpu_mapping']=[line for line in Path('/proc/self/maps').read_text().splitlines() if 'libggml-cpu' in line]
        assert result['loaded_cpu_mapping'] and all(str(root/'lib') in line for line in result['loaded_cpu_mapping'])
        result['load_seconds'] = time.monotonic()-start
        write(root/'PROGRESS_LOADED.json', dict(load_seconds=result['load_seconds']))
        for index in range(2):
            stream = model.stream(); events=[]; began=time.monotonic()
            try:
                for offset in range(0, len(samples), 1280): events.extend(stream.feed(samples[offset:offset+1280]))
                events.extend(stream.finish_events())
                assert stream.finish_events() == []
                try: stream.feed(samples[:1])
                except RuntimeError: rejected=True
                else: rejected=False
                assert rejected and stream.input_samples == 715127
                assert any(e['raw_text'].strip() for e in events), 'No nonempty text passage'
                canonical = [{k:v for k,v in e.items() if k!='available_at_monotonic'} for e in events]
                write(root/('EVENTS_'+str(index)+'.json'), canonical)
                result['sessions'].append(dict(input_samples=stream.input_samples, events=len(events),
                    seconds=time.monotonic()-began, event_sha256=sha(root/('EVENTS_'+str(index)+'.json')),
                    finish_idempotent=True, post_finish_rejected=True))
                write(root/('SESSION_'+str(index)+'_COMPLETED.json'),result['sessions'][-1])
            finally: stream.close()
        assert result['sessions'][0]['event_sha256'] == result['sessions'][1]['event_sha256']
        reference=json.loads(Path(a['generic_events']).read_text())
        result['generic_event_matches']=[json.loads((root/('EVENTS_'+str(i)+'.json')).read_text())==reference for i in range(2)]
        assert all(result['generic_event_matches']), 'A76 canonical event mismatch against retained generic source'
        result['status'] = 'A76_FULL_SOURCE_REFERENCE_COLLECTED_REVIEW_REQUIRED'
    except Exception as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
    finally:
        if model is not None: model.close()
        result['elapsed_seconds'] = time.monotonic()-start
        result['ru_maxrss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result['model_closed'] = model is None or not bool(model.handle)
        write(root/'RESULT.json', result)
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
                     'RuntimeMaxSec=600','TimeoutStopSec=10','LimitCORE=0','Nice=10','LimitFSIZE='+str(4*MIB)]:cmd+=['-p',prop]
        for key,value in dict(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
            NUMEXPR_NUM_THREADS='1',MALLOC_ARENA_MAX='1',MALLOC_MMAP_THRESHOLD_='131072',
            MALLOC_TRIM_THRESHOLD_='131072',CUDA_VISIBLE_DEVICES='',NEMO_SPEECH_MEMSTATS='1',
            LD_LIBRARY_PATH=str(root/'lib')).items():cmd+=['--setenv='+key+'='+value]
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
                if available<192*MIB or (samples and samples[-1].get('VmRSS',0)*1024>1152*MIB):
                    memory_guard=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
                if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>a['target_output_max_bytes']-2*MIB:
                    output_guard=True;subprocess.run(['systemctl','--user','stop','jp-'+RUN+'.service'],check=True)
                if time.monotonic()-began>625:
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
    review=json.loads((PRIVATE/'a2-memory-build-v1-evidence/BUILD_REVIEW.json').read_text());assert review['status']=='PASS_A2_METADATA16_BUILD_ONLY'
    w=window();c=json.loads(census_path.read_text());assert time.time()-census_path.stat().st_mtime<900
    assert c['window']['sha256']==sha(here.parent/'WINDOW_V5.json')
    for o in (c['supervisor']['host'],c['supervisor']['launcher']):
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    used=0
    for rel in ['n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928']:
        inv=payload_inventory(LOCAL/rel);assert not inv['errors'] and not inv['reparse_not_traversed'];used+=inv['total_logical_bytes']
    from stage_a2_asset_v1 import DIGEST
    payload={n:base64.b64encode((here/n).read_bytes()).decode() for n in NAMES}
    for f in PRIVATE.glob('d1-onnx-*/supervision/worker.json'):
        wr=json.loads(f.read_text());owners=[dict(pid=wr[pk],create_time=wr[ck]) for pk,ck in [('pid','create_time'),('child_pid','child_create_time')] if wr.get(pk) is not None]
        for name in ['MODEL_OWNER.json','REGISTERED_OWNER.json']:
            q=f.parent.parent/name
            if q.exists():
                rec=json.loads(q.read_text());owners.append(rec.get('owner',rec))
        for o in owners:
            try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
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
    calc=budget(c['calculation']['existing_bytes']+delta+pre['target_bytes'],used+pre['target_bytes'],64*MIB,{d:shutil.disk_usage(d+'/').free for d in ['C:','G:']},52)
    a=dict(schema='a2-native-full.v1',admitted_utc=now.isoformat(),expires_utc=(now+timedelta(minutes=12)).isoformat(),
        boot_id=pre['boot_id'],install_sha256=pre['install_sha256'],live_config_sha256=pre['live_config_sha256'],
        address_space_max_bytes=1536*MIB,stack_bytes=MIB,cpus=[2,3],cpu_quota_percent=200,native_threads=1,
        minimum_available_ram_bytes=1408*MIB,runtime_seconds=600,tasks_max=64,output_max_bytes=64*MIB,target_output_max_bytes=32*MIB,host_evidence_reserve_bytes=32*MIB,
        combined_cap_bytes=w['maximum_new_output_bytes'],host_window_bytes=used,capture=False,
        source_wav=REMOTE+'/d1-generic-v1/source.wav',scope='A2 only A76 CPU library replacement, exact generic canonical events/full/resident repeat; not integrated B02 or accuracy',
        runtime_candidate='A2-specific metadata16,8192/95%guard,original cache unchanged; lane-preserving A76 CPU candidate',
        policy_sha256=sha(here.parent/'WINDOW_V5.json'),census_sha256=sha(census_path))
    staged=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(RUN)+'\nA='+repr(a)+'\nP='+repr(payload)+'\nDIGEST='+repr(DIGEST)+'\n'+r'''
import base64,json,shutil,hashlib,sys
from pathlib import Path
r=Path(ROOT);d=r/RUN;d.mkdir()
for n,s in P.items():(d/n).write_bytes(base64.b64decode(s))
parent=r/'a2-native-full-v1';prior=json.loads((parent/'ADMISSION.json').read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for row in prior['files']:assert sha(row['path'])==row['sha256']
reference=parent/'EVENTS_0.json';v=json.loads((parent/'RESULT.json').read_text())
assert v['status']=='FULL_SOURCE_LIFECYCLE_COLLECTED_REVIEW_REQUIRED' and v['model_closed']
assert sha(reference)==v['sessions'][0]['event_sha256']==v['sessions'][1]['event_sha256']
shutil.copytree(parent/'lib',d/'lib');shutil.copyfile(parent/'n3_asr_native.py',d/'n3_asr_native.py')
optimized=r/'d1-geometry-delayed-lru1-v1/nemo-arm64/lib'
for name in ['libggml-base.so','libggml.so']:assert sha(parent/'lib'/name)==sha(optimized/name)
for path in (d/'lib').glob('libggml-cpu.so*'):
 assert sha(optimized/path.name)=='f12ac1b3912855a88bdc899fb468297d940c8730ee5942a991cc45ddf825a557'
 shutil.copyfile(optimized/path.name,path)
assert sha(d/'lib/libnemo_speech_asr.so')=='6415fb2a77aa5483bbb91e5ecaf5d58c6c3f9edbfe92575f1ab2389d6064bc1b'
assert sha(r/'a2-asset-stage-v1/A2.gguf')==DIGEST
changed=[p.name for p in (d/'lib').iterdir() if sha(p)!=sha(parent/'lib'/p.name)]
assert len(changed)==3 and all(n.startswith('libggml-cpu.so') for n in changed)
(d/'CPU_DERIVATIVE.json').write_text(json.dumps(dict(parent=str(parent),parent_admission_sha256=sha(parent/'ADMISSION.json'),changed=changed,cpu_sha256=sha(d/'lib/libggml-cpu.so'),ASR_sha256=sha(d/'lib/libnemo_speech_asr.so')),indent=2))
A['generic_events']=str(reference)
files=[dict(path=str(p),sha256=sha(p)) for p in sorted((d/'lib').iterdir())]
binding=dict(schema='just-peachy.n3.native-asr.v1',variant='A2',model_revision='ebe59e5a817142986528bbbee5dba8db7b38ed50',model_sha256=DIGEST,runtime_revision='97a15afa5caa9bce5baaa86c1184103877af4101',precision='Q8_0',gpu=-1,right_context=1,language='en-US',stop_history_eou_ms=800,decoder='greedy',model_path=str(r/'a2-asset-stage-v1/A2.gguf'),library_path=str(d/'lib/libnemo_speech_asr_c.so'),runtime_files=files)
(d/'BINDING.json').write_text(json.dumps(binding,indent=2))
A['files']=[dict(path=str(p),sha256=sha(p)) for p in sorted(d.rglob('*')) if p.is_file()]+[dict(path=A['source_wav'],sha256=sha(A['source_wav'])),dict(path=A['generic_events'],sha256=sha(A['generic_events']))]
(d/'ADMISSION.json').write_text(json.dumps(A,indent=2))
print(json.dumps(A))
''')
    out=PRIVATE/(RUN+'-evidence');out.mkdir();write(out/'PREFLIGHT.json',dict(admission=staged,calculation=calc,target=pre))
    with (out/'launch.log').open('xb') as log:
        code=subprocess.run(SSH+['python3 -B '+REMOTE+'/'+RUN+'/a2_a76_full_v1.py --gate'],stdout=log,stderr=subprocess.STDOUT,timeout=655).returncode
    write(out/'LAUNCH_RESULT.json',dict(exit_code=code,requires_independent_review=True))
    print(json.dumps(dict(run=RUN,exit_code=code,status='CLOSED_REVIEW_REQUIRED')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--gate',action='store_true');p.add_argument('--census',type=Path);a=p.parse_args()
    if a.worker:raise SystemExit(worker())
    elif a.gate:raise SystemExit(gate())
    else:
        if a.census is None:p.error('--census required')
        dispatch(a.census)
