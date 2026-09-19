"""S6B shared paths, atomic JSON and uncached file bindings. See README_S6B.md."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

SIM = Path(os.environ.get('JP_S6B_SIM', Path(__file__).resolve().parents[1])).resolve()
REPO = SIM.parents[2]
H2 = REPO / 'Software Validation from Datasets/Evaluation Tool'
APP = H2 / 'app/edge_speech_pipeline'
RUN = '20260909T230840Z'
REPORT = SIM / 'reports/S6B' / RUN
STAGING = SIM / 'staging/s6b' / RUN
PAYLOAD = Path('G:/Just_Peachy_S6B') / RUN
S6A = SIM / 'reports/S6A/20260909T202250Z'
PACK = SIM.parent / 'Just_Peachy_S6B_After_S6A_Pack/Just_Peachy_S6B_After_S6A_Pack'
BANK = SIM / 'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json'
EDGE = REPO / '.edge-speech-env/python.exe'
ANALYSIS = SIM / 'staging/s5_text_metrics/analysis_env/Scripts/python.exe'

def utc(): return datetime.now(timezone.utc).isoformat()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
def bind(path, expected=None):
    path = Path(path).resolve()
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns): raise RuntimeError('File changed while binding: '+str(path))
    if expected is not None and h.hexdigest() != expected: raise RuntimeError('SHA256 mismatch: '+str(path))
    return dict(path=str(path), bytes=before.st_size, sha256=h.hexdigest())
def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.'+path.name+'.'+str(os.getpid())+'.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def prepare():
    import shutil
    import zipfile
    import xml.etree.ElementTree as ET
    REPORT.mkdir(parents=True, exist_ok=True)
    if (REPORT/'ADMISSION_RECEIPT.json').exists(): return read(REPORT/'ADMISSION_RECEIPT.json')
    STAGING.mkdir(parents=True, exist_ok=True); PAYLOAD.mkdir(parents=True, exist_ok=True)
    pack_bindings = [bind(PACK/r['path'], r['sha256']) for r in read(PACK/'PACK_MANIFEST.json')['files']]
    prompt = bind(Path.home()/'Downloads/Codex_S6B_Joint_Comparison_After_S6A.md')
    if prompt['sha256'] != pack_bindings[0]['sha256']: raise RuntimeError('Downloads/pack task mismatch')
    predecessor = bind(SIM/'handoffs/S6A_JOINT_CHATGPT_HANDOFF_20260909T202250Z.zip', '2df6f426a81d29fbb4c5a5392484b78494c04a5e30988ab1913291ef82b30646')
    with zipfile.ZipFile(predecessor['path']) as z:
        bad = z.testzip()
        if bad: raise RuntimeError('S6A ZIP CRC failed: '+bad)
    bind(APP/'research_tracking.py', 'c4fbb435d1c8152117c4500bf52811d7952c189dd833b18c3682cb263edaa0a8')
    snapshot = STAGING/'s6a_v2_app/edge_speech_pipeline'
    if snapshot.exists(): raise RuntimeError('Snapshot exists without completed receipt; inspect before continuing')
    shutil.copytree(APP, snapshot, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    app_rows=[]
    for source in sorted(APP.rglob('*')):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
            original = bind(source); frozen = bind(snapshot/source.relative_to(APP), original['sha256'])
            app_rows.append(dict(relative_path=source.relative_to(APP).as_posix(), original=original, snapshot=frozen))
    workbook = bind(Path.home()/'Downloads/XVF_Measurement_V15.docx')
    with zipfile.ZipFile(workbook['path']) as z:
        tree = ET.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs=[''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in tree.findall('.//w:p',ns)]
    text_path=STAGING/'XVF_Measurement_V15_extracted.txt'
    text_path.write_text('\n'.join(paragraphs),encoding='utf-8')
    result=dict(status='ADMITTED', run_id=RUN, started_utc='2026-09-09T23:08:40+00:00', admitted_utc=utc(),
        invocation_budget_hours=24, closure_reserve_minutes=45, pack_files=pack_bindings, task=prompt,
        predecessor_zip=predecessor, exact_s6a_v2_snapshot=app_rows, workbook=workbook,
        workbook_text=bind(text_path), bank=bind(BANK,'69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18'),
        boundaries=['No RIR regeneration','No H2 baseline replacement','No hardware playback','No downloads/training','No S6C'],
        snapshot_purpose='Exact pre-S6B application copy, including S6A V2 research path; scientific B0 snapshot remains separate and unchanged')
    save(REPORT/'ADMISSION_RECEIPT.json',result)
    return dict(status=result['status'],app_files=len(app_rows),workbook=result['workbook'],text_path=str(text_path))

if __name__ == '__main__': print(json.dumps(prepare(),indent=2))
