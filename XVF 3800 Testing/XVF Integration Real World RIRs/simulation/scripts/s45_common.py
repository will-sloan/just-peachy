"""S4.5 paths, bounded resources and progress; see README_S45.md."""
import datetime, hashlib, json, os, shutil, threading, time, uuid
from pathlib import Path
from s4_common import bind, save, now, read, ROOT, SIM, REPO, H2, EDGE_PYTHON, RECORDER_PYTHON, BASE_PYTHON, single_thread_env

RUN_ID='20260909T031300Z'
START_UTC=datetime.datetime(2026,9,9,3,13,tzinfo=datetime.timezone.utc)
DEADLINE=START_UTC+datetime.timedelta(hours=8)
LAUNCH_CUTOFF=DEADLINE-datetime.timedelta(minutes=30)
REPORT=SIM/'reports/S4_5'/RUN_ID
BANK=SIM/'scene_bank'/('s45_v2_'+RUN_ID)
PAYLOAD=Path('G:/Just_Peachy_S4_5')/RUN_ID
PACK=ROOT/'Just_Peachy_S4_5_Overnight_Pack/Just_Peachy_S4_5_Overnight_Pack'
S4_REPORT=SIM/'reports/S4/20260909T002140Z'
HARDWARE=PAYLOAD/'hardware'
LIMITS={'canonical_scenes':240,'development':180,'reserve':60,'physical_passes':320,'active_playback_s':16200,'canonical_audio_s':12600,'new_storage_gib':60,'new_network_gib':16,'download_wait_s':5400,'C_free_gib':50,'G_free_gib':75,'attempts_per_scene':2,'consecutive_failures':3,'sentinel_scenes':24,'H2_outputs':48,'dry_jobs':24}

def storage():
    return {d:{'free_bytes':shutil.disk_usage(d+':/').free,'free_gib':shutil.disk_usage(d+':/').free/2**30} for d in ['C','G']}

def elapsed_s():return (datetime.datetime.now(datetime.timezone.utc)-START_UTC).total_seconds()
def remaining_s():return (DEADLINE-datetime.datetime.now(datetime.timezone.utc)).total_seconds()
def launch_allowed(estimated_s=0):return datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=estimated_s)<LAUNCH_CUTOFF

def check_storage():
    s=storage();assert s['C']['free_gib']>=50 and s['G']['free_gib']>=75,'Required SSD reserve reached'
    total=sum(p.stat().st_size for root in [PAYLOAD,REPORT,BANK] if root.exists() for p in root.rglob('*') if p.is_file())
    assert total<60*2**30,'New S4.5 storage budget reached'
    return total

class Progress:
    def __init__(self,stage,total=None):
        self.stage=stage;self.total=total;self.done=0;self.case=None;self.detail=None
        self.start=time.monotonic();self.stop=threading.Event();self.lock=threading.Lock()
    def emit(self,status='RUNNING'):
        elapsed=time.monotonic()-self.start;rate=self.done/elapsed if elapsed else 0
        row={'updated_utc':now(),'stage':self.stage,'status':status,'case':self.case,'elapsed_s':elapsed,'run_elapsed_s':elapsed_s(),'deadline_remaining_s':remaining_s(),'completed':self.done,'total':self.total,'items_per_s':rate,'eta_range_s':[(self.total-self.done)/rate*.85,(self.total-self.done)/rate*1.3] if rate and self.total else None,'detail':self.detail,'ssd':storage()}
        with self.lock:
            save(REPORT/'progress'/ (self.stage+'.json'),row)
            with (REPORT/'heartbeat.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    def __enter__(self):
        REPORT.mkdir(parents=True,exist_ok=True);self.emit()
        def loop():
            while not self.stop.wait(20):self.emit()
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();return self
    def __exit__(self,typ,value,tb):
        self.stop.set();self.thread.join(2)
        if value:self.detail=repr(value)
        self.emit('FAILED' if typ else 'COMPLETE')
