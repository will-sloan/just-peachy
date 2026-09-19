from pathlib import Path
import json, hashlib, os
STAGE=Path(__file__).resolve().parent
rows=json.loads((STAGE/'inventory.json').read_text(encoding='utf-8'))
extra=Path('C:/Users/amiri/.codex/attachments/085a8fe8-323b-4ce6-b91a-d49063616bdb/pasted-text.txt')
if extra.is_file() and not any(r['source']==str(extra) for r in rows):
    b=extra.read_bytes();s=extra.stat()
    rows.append({'path':'reference_documents/initial_project_instructions_pasted.txt','source':str(extra),'bytes':len(b),'mtime_ns':s.st_mtime_ns,'sha256':hashlib.sha256(b).hexdigest()})
(STAGE/'inventory.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
by_source={os.path.normcase(os.path.abspath(r['source'])):r for r in rows}
checks=0;errors=[];count=0;receipt_links=[]
for row in rows:
    p=Path(row['source'])
    if p.name!='SHA256SUMS.txt' or '/experiments/' not in row['path']:continue
    count+=1
    base=p.parent
    if '/linked_take_receipts/' in row['path']:
        # These folders intentionally contain receipt copies, not full takes.
        base=Path('C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/XVF_MEASUREMENT_WORK/experiments')/p.parent.name
        original=by_source.get(os.path.normcase(os.path.abspath(base/'SHA256SUMS.txt')))
        if not original or original['sha256']!=row['sha256']:
            errors.append({'manifest':row['path'],'error':'linked original manifest missing or different'})
        receipt_links.append({'receipt_manifest':row['path'],'resolved_original_run':base.name})
    for line in p.read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        expected,relative=line.split(maxsplit=1)
        target=base/relative.lstrip('*')
        current=by_source.get(os.path.normcase(os.path.abspath(target)))
        checks+=1
        if not current or current['sha256']!=expected.lower():errors.append({'manifest':row['path'],'file':relative,'error':'missing or original digest mismatch'})
report={'manifests_checked':count,'original_hash_entries_checked':checks,'linked_receipts_resolved':receipt_links,'mismatches':errors,'status':'PASS' if not errors else 'REVIEW'}
(STAGE/'ORIGINAL_MANIFEST_AUDIT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unique={r['sha256']:r for r in rows}
summary={'files':len(rows),'logical_bytes':sum(r['bytes'] for r in rows),'unique_files':len(unique),'unique_bytes':sum(r['bytes'] for r in unique.values())}
(STAGE/'inventory_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({'inventory':summary,'original_manifest_audit':{k:v for k,v in report.items() if k!='linked_receipts_resolved'}}),flush=True)
