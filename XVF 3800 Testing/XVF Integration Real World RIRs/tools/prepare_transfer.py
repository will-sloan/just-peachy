"""Read-only dataset inventory and lossless transfer preparation."""
from pathlib import Path
import hashlib, json, os, time
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path('C:/Users/amiri/XVF_Transfer_20260907')
STAGE.mkdir(exist_ok=True)
EXTERNAL = Path('C:/Users/amiri/Downloads')
DOCS = ['Just_Peachy_H2_XVF3800_Master_Workbook_and_Experiment_Plan_V4.docx',
        'Just_Peachy_XVF3800_Project_and_Experiment_CONTEXT.md',
        'Just_Peachy_XVF3800_Excitation_and_Logging_Pack_V2.zip',
        'xvf3800_datasheet_v3.2.1.pdf', 'xvf3800_programming_guide_v3.2.1.pdf', 'xvf3800_user_guide_v3.2.1.pdf',
        'XVF3800-Binary_v3_2_1.zip', 'XVF3800-Software_v3_2_1.zip',
        'host_xvf_control---application-source-code_v3_0_0.zip', 'XK-VOICE-SQ66-Design-Files_1V1.zip',
        'XK-VOICE-SQ66-Design-Files(1V1).zip']

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

if __name__ == '__main__':
    sources = [(p, 'project/'+p.relative_to(ROOT).as_posix()) for p in ROOT.rglob('*') if p.is_file()]
    sources += [(EXTERNAL/name, 'reference_documents/'+name) for name in DOCS if (EXTERNAL/name).is_file()]
    records = []; unique = {}; start = time.monotonic()
    for index, (p, rel) in enumerate(sources):
        before = p.stat()
        digest = sha(p)
        after = p.stat()
        if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
            raise RuntimeError(f'Source changed during hashing: {p}')
        entry = {'path':rel, 'source':str(p), 'bytes':before.st_size, 'mtime_ns':before.st_mtime_ns, 'sha256':digest}
        records.append(entry); unique.setdefault(digest, entry)
        if index%5000 == 0:
            print(json.dumps({'hashed_files':index,'total_files':len(sources),'elapsed_s':round(time.monotonic()-start)}),flush=True)
    (STAGE/'inventory.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    stats = {'files':len(records),'logical_bytes':sum(x['bytes'] for x in records), 'unique_files':len(unique),
             'unique_bytes':sum(x['bytes'] for x in unique.values()), 'source_root':str(ROOT), 'stage':str(STAGE)}
    (STAGE/'inventory_summary.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    print(json.dumps(stats),flush=True)
