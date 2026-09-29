"""Fresh isolated supervisor plus owned bounded export. README_D1_ONNX_EXPORT_V2.md."""
import argparse,ctypes,hashlib,json,os,sys,time,shutil
from pathlib import Path
from datetime import datetime,timezone,timedelta
import psutil
HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
BASE=LOCAL/'n5/research-extension-20260928/pi-native-20260928'
ROOT=BASE/'d1-onnx-export-v2'
sys.path.insert(0,str(HERE.parent));sys.path.insert(0,str(HERE.parents[1]));sys.path.insert(0,str(HERE.parents[2]/'supervision'))
from window_guard_v2 import window,budget,payload_inventory
import supervisor
from private_application_two_cpu_v1 import PrivateApplicationProcess,EXTENDED_LIMIT,checked
from common import bind,verify


def save(path,x):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)


def guard():
    psutil.Process().cpu_affinity([14]);a=json.loads((ROOT/'ADMISSION.json').read_text(encoding='utf-8'))
    assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    for b in a['bindings']:verify(b)
    result=dict(status='FAILED_PRESERVED');job=None;start=time.monotonic();samples=[]
    with supervisor.lock(BASE/'HOST_EXPORT.lock'):
        try:
            job=PrivateApplicationProcess(ROOT/'lifetime',executable_binding=bind(a['python']),script_binding=bind(HERE/'d1_onnx_export_worker_v2.py'),arguments=['--root',str(ROOT)])
            owner=job.spawn_suspended()
            limits=EXTENDED_LIMIT();limits.BasicLimitInformation.LimitFlags=0x2000|0x10|0x8|0x200
            limits.BasicLimitInformation.Affinity=(1<<4)|(1<<14);limits.BasicLimitInformation.ActiveProcessLimit=16
            limits.JobMemoryLimit=6*1024**3
            checked(job.kernel.SetInformationJobObject(job.job,9,ctypes.byref(limits),ctypes.sizeof(limits)))
            observed=EXTENDED_LIMIT();checked(job.kernel.QueryInformationJobObject(job.job,9,ctypes.byref(observed),ctypes.sizeof(observed),None))
            assert observed.JobMemoryLimit==6*1024**3 and observed.BasicLimitInformation.Affinity==(1<<4)|(1<<14)
            save(ROOT/'JOB_ENVELOPE.json',dict(owner=owner,hard_job_commit_bytes=int(observed.JobMemoryLimit),affinity=[4,14],kill_on_close=True,max_processes=16))
            job.resume(lambda identity,**kw:save(ROOT/'REGISTERED_OWNER.json',dict(owner=identity,**kw)))
            while not job.root_exited():
                elapsed=time.monotonic()-start
                size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
                proc=psutil.Process(owner['pid']);assert abs(proc.create_time()-owner['create_time'])<.001
                rss=proc.memory_info().rss;samples.append(dict(seconds=elapsed,rss_bytes=rss,output_bytes=size))
                assert elapsed<600,'Wall-time bound'
                assert size<a['output_max_bytes'],'Output bound'
                assert psutil.virtual_memory().available>=8*1024**3,'Host available RAM floor'
                assert all(shutil.disk_usage(d+'/').free>=floor*1024**3 for d,floor in [('C:',50),('G:',75)]),'Disk floor'
                time.sleep(.5)
            result['status']='WORKER_EXITED_REVIEW_REQUIRED'
        except Exception as e:result['error']=repr(e)
        finally:
            if job is not None:result['lifetime']=job.close(grace_seconds=0)
            result.update(seconds=time.monotonic()-start,samples=samples,output_bytes=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()))
            save(ROOT/'GUARD_RESULT.json',result)
    return int(result['status']!='WORKER_EXITED_REVIEW_REQUIRED' or result['lifetime']['root_exit_code']!=0)


def prepare(census):
    psutil.Process().cpu_affinity([14]);w=window();now=datetime.now(timezone.utc)
    assert not ROOT.exists() and time.time()-census.stat().st_mtime<900
    c=json.loads(census.read_text(encoding='utf-8'));assert not c['active_allocations']
    original=json.loads((LOCAL/'supervision/worker.json').read_text(encoding='utf-8'));assert original['status']=='COMPLETED'
    for pk,ck in [('pid','create_time'),('child_pid','child_create_time')]:
        try:assert abs(psutil.Process(original[pk]).create_time()-original[ck])>.001
        except psutil.NoSuchProcess:pass
    # No competing export supervisors may be active even though the original ledger stays closed.
    for p in BASE.glob('d1-onnx-*/supervision/worker.json'):
        rec=json.loads(p.read_text(encoding='utf-8'));supervisor.require_no_active_worker(rec)
    from dispatch_geometry_v2 import remote,REMOTE
    target=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import json,subprocess,shutil,fcntl,os
from pathlib import Path
r=Path(ROOT)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43' and ticks(1013)==569 and ticks(1130)==607
assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text() and os.uname().machine=='aarch64'
for p in r.rglob('*OWNER*.json'):
 o=json.loads(p.read_text());assert not(o['boot_id']==boot and ticks(o['pid'])==o['start_ticks'])
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
print(json.dumps(dict(boot=boot,target_bytes=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0]),free_bytes=shutil.disk_usage(r).free,available_ram_bytes=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))))
''')
    used=0
    for rel in ['n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928']:
        inv=payload_inventory(LOCAL/rel);assert not inv['errors'] and not inv['reparse_not_traversed'];used+=inv['total_logical_bytes']
    delta=used-c['calculation']['window_used_bytes'];assert delta>=0
    cap=1024**3
    calc=budget(c['calculation']['existing_bytes']+delta+target['target_bytes'],used+target['target_bytes'],cap,{d:shutil.disk_usage(d+'/').free for d in ['C:','G:']},50)
    assert psutil.virtual_memory().available>=12*1024**3
    expiry=now+timedelta(seconds=660);assert expiry<datetime.fromisoformat(w['checkpoint_utc'])
    env=LOCAL/'n2/nemo-py312';model_source=env/'Lib/site-packages/nemo/collections/asr/models/sortformer_diar_models.py'
    module_source=env/'Lib/site-packages/nemo/collections/asr/modules/sortformer_modules.py'
    ckpt=LOCAL/'n2/diarization/reference/867c53f552998f772e5b5e5c082962ae85ee7ca5669c2bc17d7f615133d4e96d/Nemotron-3-Diarization.nemo'
    bindings=[bind(p) for p in [HERE/'d1_onnx_export_worker_v2.py',HERE/'d1_export_attention_v1.py',Path(__file__),HERE/'README_D1_ONNX_EXPORT_V2.md',ckpt,model_source,module_source,HERE.parent/'WINDOW_V2.json',HERE.parent/'window_guard_v2.py',HERE.parents[1]/'private_application_two_cpu_v1.py',Path(supervisor.__file__),env/'Scripts/python.exe']]
    assert bind(ckpt)['sha256']=='867c53f552998f772e5b5e5c082962ae85ee7ca5669c2bc17d7f615133d4e96d'
    assert bind(model_source)['sha256']=='bd6624df8a0ad2edb3659592b3f711b6a093a0d801b364599fc95bc7361bb877'
    assert bind(module_source)['sha256']=='ead9804248b45153a1abfbe54ba67fab3c1d418da904f025ade5500168e7ee7c'
    ROOT.mkdir();save(ROOT/'ADMISSION.json',dict(scope='HOST_EXPORT_FOR_NATIVE_D1',admitted_utc=now.isoformat(),expires_utc=expiry.isoformat(),campaign_checkpoint=w['checkpoint_utc'],
        output_max_bytes=cap,wall_seconds=600,hard_job_commit_bytes=6*1024**3,minimum_available_ram_bytes=8*1024**3,affinity=[4,14],model_cpus=[4,14],coordinator_cpu=14,threads=1,gpu=False,
        python=str(env/'Scripts/python.exe'),checkpoint=str(ckpt),model_source_sha256=bind(model_source)['sha256'],bindings=bindings,target=target,budget=calc,census=bind(census),
        absolute_tolerance=1e-5,parity_scope='same FP32 graph outputs on three feature/cache cases; no Q8, waveform driver or native Pi qualification'))
    # Fresh supervisor state only; original closed campaign files remain untouched.
    state=ROOT/'supervision';campaign=supervisor.init(state,'01a0d3df-f647-75f1-bd82-aab88c1f570b',now.isoformat())
    campaign.update(stage='N5_D1_ONNX_EXPORT',target_utc=expiry.isoformat(),user_constraints=['Native Pi preparation CPU export only','No capture/playback/downloads','No Windows focus/input takeover'],scope='Fresh bounded export; original campaign preserved')
    supervisor.atomic(state/'campaign.json',campaign)
    spec=ROOT/'worker_spec.json';save(spec,dict(argv=[str(Path(sys.executable)),'-B',str(Path(__file__)),'--guard'],cwd=str(HERE)))
    started=supervisor.start(state,spec);save(ROOT/'STARTED.json',started)
    print(json.dumps(dict(status='STARTED_NOT_QUALIFIED',root=str(ROOT),supervisor=started)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--census',type=Path);p.add_argument('--guard',action='store_true');a=p.parse_args()
    if a.guard:raise SystemExit(guard())
    assert a.census is not None;prepare(a.census)
