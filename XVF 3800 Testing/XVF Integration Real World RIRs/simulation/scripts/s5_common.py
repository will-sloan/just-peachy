"""S5-only paths, immutable inputs and development access boundary. README_S5.md."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
from s4_common import SIM, REPO, H2, EDGE_PYTHON, BASE_PYTHON, now, read, save, single_thread_env
RUN_ID = '20260909T130308Z'
START = dt.datetime(2026, 9, 9, 13, 3, 8, tzinfo=dt.timezone.utc)
DEADLINE = START + dt.timedelta(hours=8)
LAUNCH_CUTOFF = DEADLINE - dt.timedelta(minutes=30)
REPORT = SIM / 'reports/S5' / RUN_ID
PAYLOAD = Path('G:/Just_Peachy_S5') / RUN_ID
PRIOR = SIM / 'reports/S4_5/20260909T031300Z'
BANK = SIM / 'scene_bank/s45_v2_20260909T031300Z'
PACK = SIM.parent / 'Just_Peachy_S5_Codex_Pack/Just_Peachy_S5_Codex_Pack'
WORKBOOK = Path('C:/Users/amiri/Downloads/XVF_Measurement_V10.docx')
MANIFEST_SHA = '69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18'
GAINS = {'O0': 1.4125375446227544, 'O1': 1.0}
_HASH_CACHE = {}
_HASH_LOCK = threading.Lock()

def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str).encode()).hexdigest()

def bind(path, expected=None):
    """Cache verified content by resolved path, byte count and nanosecond mtime."""
    p = Path(path).resolve()
    st = p.stat()
    key = (str(p), st.st_size, st.st_mtime_ns)
    with _HASH_LOCK:
        row = _HASH_CACHE.get(key)
    if row is None:
        h = hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        after = p.stat()
        if (after.st_size, after.st_mtime_ns) != key[1:]:
            raise RuntimeError('Input changed while hashing: ' + str(p))
        row = {'path': str(p), 'sha256': h.hexdigest(), 'bytes': st.st_size}
        with _HASH_LOCK:
            _HASH_CACHE[key] = row
    if expected and row['sha256'] != expected:
        raise ValueError('Hash mismatch: ' + str(p))
    return dict(row)

def manifest():
    bind(BANK / 'SCENE_MANIFEST.json', MANIFEST_SHA)
    data = read(BANK / 'SCENE_MANIFEST.json')
    assert data['validation']['status'] == 'PASS'
    return data

class DevelopmentGuard:
    """Mandatory case allowlist before any task audio/prediction/scoring access."""
    def __init__(self, scenes, component='runner', receipt=True):
        self.component = component
        self.scenes = {s['case_id']: s for s in scenes}
        self.allowed = frozenset(k for k, s in self.scenes.items()
                                if s['split'] == 'development' and s['task_scoring_allowed'] is True)
        self.counts = {}
        self.denied = []
        self.receipt = receipt
    def require(self, case_id, operation):
        if case_id not in self.allowed:
            self.denied.append({'case_id': case_id, 'operation': operation})
            raise PermissionError('S5 development allowlist refused ' + str(case_id))
        self.counts[operation] = self.counts.get(operation, 0) + 1
        return self.scenes[case_id]
    def flush(self):
        row = {'component': self.component, 'updated_utc': now(),
               'allowed_development_cases': sorted(self.allowed),
               'permitted_operation_calls': self.counts,
               'denied_before_open': self.denied, 'reserve_task_accesses': 0,
               'metadata_rows_parsed': len(self.scenes),
               'scope': 'Application boundary receipts, not an OS file-access trace; checks precede payload opens and model/scorer calls.'}
        if self.receipt:
            save(REPORT / 'access' / (self.component + '.json'), row)
        return row

def population(scene):
    if not scene['all_speaker_reference_complete']:
        return 'ambient_incomplete'
    words = any(str(r.get('transcript', '')).strip() for r in scene.get('all_speaker_references', []))
    if not words:
        return 'strict_empty'
    return 'overlap_complete' if scene.get('overlap_intervals') else 'primary_nonoverlap'

def generated_bytes():
    return sum(p.stat().st_size for root in (REPORT, PAYLOAD) if root.exists()
               for p in root.rglob('*') if p.is_file())

def resources(*, scan=False):
    import psutil
    row = {'utc': now(), 'free_gib': {d: shutil.disk_usage(d + ':/').free / 2**30 for d in ('C', 'G')},
           'available_ram_gib': psutil.virtual_memory().available / 2**30}
    if scan:
        row['new_output_bytes'] = generated_bytes()
    assert row['free_gib']['C'] >= 50 and row['free_gib']['G'] >= 75, 'SSD free-space floor'
    assert row['available_ram_gib'] >= 8, 'Preserve at least 8 GiB current available OS RAM'
    assert row.get('new_output_bytes', 0) < 40 * 2**30, 'S5 40 GiB output cap'
    return row

def launch_allowed(seconds=240):
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds) < LAUNCH_CUTOFF
