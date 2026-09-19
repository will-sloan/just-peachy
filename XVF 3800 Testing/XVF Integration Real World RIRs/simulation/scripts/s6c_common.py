"""S6C durable bindings, paths and resource admission. See README_S6C.md."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
import shutil
import time
import uuid

SIM=Path(os.environ.get('JP_S6C_SIM',Path(__file__).resolve().parents[1])).resolve()
REPO=SIM.parents[2]
H2=REPO/'Software Validation from Datasets/Evaluation Tool'
APP=H2/'app/edge_speech_pipeline'
RUN='20260910T123540Z'
REPORT=SIM/'reports/S6C'/RUN
STAGING=SIM/'staging/s6c'/RUN
PAYLOAD=Path('G:/Just_Peachy_S6C')/RUN
S6B=SIM/'reports/S6B/20260909T230840Z'
S6B_PAYLOAD=Path('G:/Just_Peachy_S6B/20260909T230840Z')
S6A=SIM/'reports/S6A/20260909T202250Z'
BANK=SIM/'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json'
PACK=SIM.parent/'Just_Peachy_S6C_Integrated_Enrollment_Pack/Just_Peachy_S6C_Integrated_Enrollment_Pack'
EDGE=REPO/'.edge-speech-env/python.exe'
ANALYSIS=SIM/'staging/s5_text_metrics/analysis_env/Scripts/python.exe'
STARTED='2026-09-10T12:35:40+00:00'
NO_NEW_WORK='2026-09-13T11:35:40+00:00'
RESERVE={'C:':50*2**30,'G:':75*2**30}
CAP=120*2**30

def utc():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def bind(path,expected=None):
    p=Path(path).resolve();before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('File changed while hashing: '+str(p))
    if expected is not None and h.hexdigest()!=expected:raise RuntimeError('Binding mismatch: '+str(p))
    return dict(path=str(p),bytes=before.st_size,sha256=h.hexdigest())
def verified(b):bind(b['path'],b['sha256']);return read(b['path'])
def save(path,value,immutable=False):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    if immutable and p.exists():
        old=read(p)
        if old!=value:raise RuntimeError('Immutable artifact already exists: '+str(p))
        return bind(p)
    temp=p.with_name('.'+p.name+'.'+str(os.getpid())+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    # Windows readers/antivirus may briefly hold the destination without delete
    # sharing. Retry only that OS condition; never suppress a persistent error
    # or substitute an incomplete temp file for a durable artifact.
    for attempt in range(21):
        try:
            os.replace(temp,p)
            break
        except PermissionError:
            if attempt==20:raise
            time.sleep(.1)
    return bind(p)
def csv_write(path,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()})
    return bind(p)
def tree_bytes(root):
    total=0
    if Path(root).exists():
        for base,dirs,files in os.walk(root):
            for file in files:total+=(Path(base)/file).stat().st_size
    return total
def resources(full=False):
    import psutil
    disk={d:dict(zip(('total','used','free'),shutil.disk_usage(d+'/'))) for d in RESERVE}
    ram=psutil.virtual_memory()
    return dict(utc=utc(),disks=disk,ram_total_bytes=ram.total,ram_available_bytes=ram.available,
                new_payload_bytes=sum(tree_bytes(p) for p in (REPORT,STAGING,PAYLOAD)) if full else None,
                limits=dict(free_reserves=RESERVE,new_output_cap_bytes=CAP,maximum_workers=4,inner_threads=1,
                            no_new_work_after_utc=NO_NEW_WORK,closure_reserve_minutes=60))
def admit_work(full=False):
    if (REPORT/'STOP_REQUEST.json').exists():raise RuntimeError('S6C STOP_REQUEST present: finish current owned job and close')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(NO_NEW_WORK):raise RuntimeError('S6C closure reserve reached')
    state=resources(full)
    for disk,minimum in RESERVE.items():
        if state['disks'][disk]['free']<minimum:raise RuntimeError('Free-space reserve on '+disk)
    if state['ram_available_bytes']<12*2**30:raise RuntimeError('Available RAM below 12 GiB admission floor')
    if state['new_payload_bytes'] is not None and state['new_payload_bytes']>CAP:raise RuntimeError('New S6C payload cap reached')
    PAYLOAD.mkdir(parents=True,exist_ok=True)
    return state

if __name__=='__main__':
    print(json.dumps(resources(full=True),indent=2))
