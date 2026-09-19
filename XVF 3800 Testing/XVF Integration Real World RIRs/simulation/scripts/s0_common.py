"""Shared bounded S0 receipts; see ../README.md for commands and contracts."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, threading, time

SIM = Path(__file__).resolve().parents[1]
ROOT = SIM.parent
REPO = ROOT.parents[1]
PACK = ROOT / 'Just_Peachy_Post_Measurement_Codex_Pack_V1/Just_Peachy_Post_Measurement_Codex_Pack_V1'
H2 = REPO / 'Software Validation from Datasets/Evaluation Tool'
BASE_PYTHON = Path(r'C:\Users\amiri\anaconda3\python.exe')
EDGE_PYTHON = REPO / '.edge-speech-env/python.exe'

def now():
    return datetime.now(timezone.utc).isoformat()

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def save(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False)+'\n', encoding='utf-8')
    # Syncthing/indexers can briefly hold report files without delete sharing.
    # Retry only the local atomic rename, never an external/device operation.
    for attempt in range(9):
        try:
            os.replace(tmp, p)
            break
        except PermissionError:
            if attempt==8: raise
            time.sleep(min(.025*2**attempt,.4))

class HashCache:
    def __init__(self):
        self.path = SIM / 'cache/hash_receipts.json'
        self.rows = read(self.path) if self.path.exists() else {}
        self.bytes = 0; self.fresh = 0; self.hits = 0

    def bind(self, path, expected=None):
        path = Path(path).resolve(); key = str(path)
        if not path.is_file():
            return dict(path=key, expected_sha256=expected, status='MISSING')
        stat = path.stat(); sig = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
        cached = self.rows.get(key)
        if cached and cached['stat_signature'] == sig:
            row = dict(cached); self.hits += 1
        else:
            digest = hashlib.sha256()
            with path.open('rb') as f:
                for block in iter(lambda:f.read(1024*1024), b''):
                    digest.update(block); self.bytes += len(block)
            end = path.stat()
            if sig != [end.st_size,end.st_mtime_ns,end.st_ctime_ns]:
                return dict(path=key, expected_sha256=expected, status='CHANGED_DURING_READ')
            row = dict(path=key, sha256=digest.hexdigest(), bytes=stat.st_size,
                       stat_signature=sig, verified_utc=now())
            self.rows[key] = dict(row); self.fresh += 1
        row['expected_sha256'] = expected
        row['status'] = ('BOUND' if row['sha256']==expected else 'HASH_MISMATCH') if expected else 'OBSERVED_HASH'
        return row

    def flush(self):
        save(self.path, self.rows)

class Progress:
    def __init__(self, report, stage, total=None):
        self.report = Path(report); self.stage = stage; self.total = total
        self.done = 0; self.detail = ''; self.start = time.monotonic()
        self.stop = threading.Event(); self.thread = None

    def emit(self, state='RUNNING'):
        elapsed = time.monotonic()-self.start
        rate = self.done/elapsed if elapsed else 0
        row = dict(stage=self.stage,status=state,updated_utc=now(),elapsed_sec=elapsed,
                   items_completed=self.done,items_total=self.total,items_per_sec=rate,
                   eta_sec=(self.total-self.done)/rate if self.total and rate else None,detail=self.detail)
        save(self.report/'status.json', row)
        with (self.report/'heartbeat.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(row)+'\n')

    def __enter__(self):
        self.emit()
        def heartbeat():
            while not self.stop.wait(15):
                self.emit()
        self.thread=threading.Thread(target=heartbeat,daemon=True); self.thread.start()
        return self

    def __exit__(self, typ, value, tb):
        self.stop.set(); self.thread.join()
        if value: self.detail = str(value)
        self.emit('FAILED' if typ else 'COMPLETE')

def safe_child(root, relative):
    root=Path(root).resolve(); child=(root/relative).resolve()
    if not child.is_relative_to(root):
        raise ValueError('Path escapes authorized root: '+str(relative))
    return child

def parse_sums(path):
    result={}
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if line.strip():
            digest, name=line.split(maxsplit=1); name=name.lstrip('*').replace('\\','/')
            if name in result: raise ValueError('Duplicate manifest entry '+name)
            result[name]=digest
    return result
