"""S4 local receipts and bounded progress. See README_S4.md."""
import hashlib, json, os, shutil, threading, time, uuid
from pathlib import Path
from s0_common import ROOT, SIM, REPO, H2, EDGE_PYTHON, now, read

RUN_ID = '20260909T002140Z'
REPORT = SIM / 'reports/S4' / RUN_ID
BANK = SIM / 'scene_bank' / ('s4_v2_' + RUN_ID)
PACK = ROOT / 'Just_Peachy_S4_Complete_Pack_V2/Just_Peachy_S4_Complete_Pack_V2'
RECORDER_PYTHON = Path(r'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
BASE_PYTHON = Path(r'C:\Users\amiri\anaconda3\python.exe')

def save(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False,default=str)+'\n',encoding='utf-8')
    for i in range(9):
        try: os.replace(temp,path); break
        except PermissionError:
            if i==8: raise
            time.sleep(min(.025*2**i,.4))

def bind(path, expected=None):
    path=Path(path).resolve(); before=path.stat()
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    after=path.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'Changed during hash'
    digest=h.hexdigest()
    if expected is not None and digest!=expected: raise ValueError('Hash mismatch: '+str(path))
    return {'path':str(path),'sha256':digest,'bytes':after.st_size,'verified_utc':now()}

def storage():
    return {d:{'free_bytes':shutil.disk_usage(d+':/').free,'free_gib':shutil.disk_usage(d+':/').free/2**30} for d in ['C','D','F','G']}

def check_storage():
    assert shutil.disk_usage(SIM).free>=50*2**30,'C SSD reserve below 50 GiB'
    generated=sum(p.stat().st_size for base in [REPORT,BANK] if base.exists() for p in base.rglob('*') if p.is_file())
    assert generated<5*2**30,'S4 generated storage budget of 5 GiB reached'
    return generated

class Progress:
    def __init__(self,stage,total=None):
        self.stage=stage; self.total=total; self.done=0; self.case=None; self.detail=None
        self.start=time.monotonic(); self.stop=threading.Event(); self.lock=threading.Lock()
    def emit(self,status='RUNNING'):
        elapsed=time.monotonic()-self.start;rate=self.done/elapsed if elapsed else 0
        row={'updated_utc':now(),'stage':self.stage,'status':status,'case':self.case,
             'elapsed_s':elapsed,'completed':self.done,'total':self.total,'items_per_s':rate,
             'eta_s':(self.total-self.done)/rate if rate and self.total else None,'detail':self.detail}
        with self.lock:
            save(REPORT/'status.json',row)
            with (REPORT/'heartbeat.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    def __enter__(self):
        self.emit()
        def loop():
            while not self.stop.wait(15): self.emit()
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();return self
    def __exit__(self,typ,value,tb):
        self.stop.set();self.thread.join(2)
        if value:self.detail=repr(value)
        self.emit('FAILED' if typ else 'COMPLETE')

def single_thread_env():
    env=os.environ.copy()
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:env[k]='1'
    env['PYTHONDONTWRITEBYTECODE']='1'
    return env
