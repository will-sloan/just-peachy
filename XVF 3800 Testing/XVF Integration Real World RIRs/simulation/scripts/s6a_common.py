"""S6A all-bank paths, immutable bindings and resource boundaries. README_S6A.md."""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
import shutil
import threading
import time
from s4_common import SIM, REPO, H2, EDGE_PYTHON, BASE_PYTHON, now, read, save, single_thread_env
from s5_common import bind, stable_hash, population

RUN_ID = '20260909T202250Z'
START = dt.datetime(2026, 9, 9, 20, 22, 50, tzinfo=dt.timezone.utc)
DEADLINE = START + dt.timedelta(hours=12)
LAUNCH_CUTOFF = DEADLINE - dt.timedelta(minutes=45)
REPORT = SIM / 'reports/S6A' / RUN_ID
PAYLOAD = Path('G:/Just_Peachy_S6A') / RUN_ID
STAGING = SIM / 'staging/s6a' / RUN_ID
SNAPSHOT = STAGING / 'baseline_app'
PRIOR = SIM / 'reports/S4_5/20260909T031300Z'
S5 = SIM / 'reports/S5/20260909T130308Z'
BANK = SIM / 'scene_bank/s45_v2_20260909T031300Z'
PACK = SIM.parent / 'Just_Peachy_S6_Joint_Pipeline_Pack_V2/Just_Peachy_S6_Joint_Pipeline_Pack_V2'
WORKBOOK = Path('C:/Users/amiri/Downloads/XVF_Measurement_V14.docx')
ANALYSIS_PYTHON = SIM / 'staging/s5_text_metrics/analysis_env/Scripts/python.exe'
MANIFEST_SHA = '69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18'
GAINS = {'O0': 1.4125375446227544, 'O1': 1.0}

def manifest():
    bind(BANK / 'SCENE_MANIFEST.json', MANIFEST_SHA)
    value = read(BANK / 'SCENE_MANIFEST.json')
    assert value['validation']['status'] == 'PASS' and len(value['scenes']) == 240
    return value

class AllBankGuard:
    """Explicit S6 allowlist; historical split flags remain unchanged in source metadata."""
    def __init__(self, scenes, component='analysis', **kwargs):
        self.scenes = {s['case_id']: s for s in scenes}
        if len(self.scenes) != 240: raise ValueError('Expected canonical 240-scene bank')
        self.allowed = frozenset(self.scenes)
        self.component = component
        self.accesses = {}
        self.lock = threading.RLock()
    def require(self, scene, operation='performance_scoring'):
        cid = scene['case_id'] if isinstance(scene, dict) else scene
        if cid not in self.allowed: raise PermissionError('Outside S6 canonical all-bank allowlist: '+str(cid))
        original = self.scenes[cid]
        if isinstance(scene, dict) and stable_hash(scene) != stable_hash(original):
            raise ValueError('Scene metadata changed')
        with self.lock: self.accesses[operation] = self.accesses.get(operation, 0) + 1
        return original
    def verified_path(self, scene, binding, operation):
        self.require(scene, operation)
        bind(binding['path'], binding['sha256'])
        return Path(binding['path'])
    def read_json(self, scene, binding, operation='task_metadata'):
        return read(self.verified_path(scene, binding, operation))
    def receipt(self):
        return {'component': self.component, 'scope': 'S6 explicit all240 authorization; old split is historical metadata',
                'allowed_count': len(self.allowed), 'operation_counts': dict(self.accesses)}
    def flush(self):
        value = self.receipt()
        save(REPORT / 'access' / (self.component+'.json'), value)
        return value

def native_receipt(path):
    """Resolve a verified reuse chain without changing any historical receipt."""
    chain=[]; p=Path(path)
    while True:
        b=bind(p); chain.append(b); value=read(p)
        assert value['status']=='COMPLETE'
        if not value.get('reused_receipt'): return value, b, chain
        rb=value['reused_receipt']; bind(rb['path'],rb['sha256']); p=Path(rb['path'])
        if len(chain)>5: raise ValueError('Receipt cycle/depth')

def generated_bytes():
    return sum(p.stat().st_size for root in (REPORT,PAYLOAD,STAGING) if root.exists() for p in root.rglob('*') if p.is_file())

def resources(scan=False):
    import psutil
    value={'utc':now(), 'free_gib':{d:shutil.disk_usage(d+':/').free/2**30 for d in ('C','G')},
           'available_ram_gib':psutil.virtual_memory().available/2**30}
    if scan: value['new_output_bytes']=generated_bytes()
    assert value['free_gib']['C']>=50 and value['free_gib']['G']>=75, 'SSD reserve'
    assert value['available_ram_gib']>=8, 'OS RAM headroom'
    assert value.get('new_output_bytes',0)<120*2**30, 'S6 disk cap'
    return value

def launch_allowed(seconds=300):
    return dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=seconds)<LAUNCH_CUTOFF

class Progress:
    def __init__(self, phase, total):
        self.phase=phase; self.total=total; self.done=0; self.detail={}; self.started=time.monotonic(); self.stop=threading.Event()
    def emit(self, status='RUNNING'):
        elapsed=time.monotonic()-self.started; rate=self.done/elapsed if elapsed else 0
        row={'utc':now(),'phase':self.phase,'status':status,'completed':self.done,'total':self.total,
             'elapsed_s':elapsed,'items_per_minute':rate*60,'eta_s':(self.total-self.done)/rate if rate else None,**self.detail}
        save(REPORT/(self.phase.lower()+'_status.json'),row)
        with (REPORT/'heartbeat.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    def __enter__(self):
        self.emit()
        def loop():
            while not self.stop.wait(20): self.emit()
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();return self
    def __exit__(self,typ,val,tb):
        self.stop.set();self.thread.join(3)
        if val:self.detail['error']=repr(val)
        self.emit('FAILED' if typ else 'COMPLETE' if self.done==self.total else 'PARTIAL')
