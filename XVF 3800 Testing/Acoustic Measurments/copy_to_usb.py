from pathlib import Path
import json, hashlib, shutil, os, time
from datetime import datetime, timezone
STAGE=Path(__file__).resolve().parent
DRIVE=Path('D:/')
DEST=DRIVE/'XVF_Measurements_2026-09-07'
names=['XVF_DATA.zip','RESTORE_MANIFEST.json','DATA_HANDOFF.md','RECORDINGS_INDEX.csv','DATASET_SUMMARY.json',
       'Restore-XVF.ps1','Restore-XVF.cmd','RESTORE_TEST_RESULT.json','VERIFICATION_REPORT.json','ORIGINAL_MANIFEST_AUDIT.json','inventory_summary.json']
report=json.loads((STAGE/'VERIFICATION_REPORT.json').read_text(encoding='utf-8'))
assert report['status']=='LOCAL_ARCHIVE_VERIFIED'
needed=sum((STAGE/n).stat().st_size for n in names)+1024*1024
free=shutil.disk_usage(DRIVE).free
if needed+16*1024*1024>free:
    print(json.dumps({'status':'NEEDS_MORE_USB_SPACE','package_bytes':needed,'free_bytes':free,'shortfall_bytes':needed+16*1024*1024-free}),flush=True)
    raise SystemExit(2)
assert DEST.resolve().parent==DRIVE.resolve()
DEST.mkdir(exist_ok=False)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
hashes={};copied=0;last=time.monotonic()
for name in names:
    source=STAGE/name;target=DEST/name;h=hashlib.sha256()
    with source.open('rb') as source_stream, target.open('xb') as target_stream:
        for b in iter(lambda:source_stream.read(4*1024*1024),b''):
            target_stream.write(b);h.update(b);copied+=len(b)
            if time.monotonic()-last>15:
                print(json.dumps({'copying':name,'copied_bytes':copied,'package_bytes':needed}),flush=True);last=time.monotonic()
        target_stream.flush();os.fsync(target_stream.fileno())
    expected=h.hexdigest()
    print(json.dumps({'verifying_usb_file':name,'bytes':target.stat().st_size}),flush=True)
    actual=sha(target)
    assert actual==expected and target.stat().st_size==source.stat().st_size,name
    hashes[name]=actual
checksum_text=''.join(f'{digest}  {name}\n' for name,digest in hashes.items())
(STAGE/'SHA256SUMS_TRANSFER.txt').write_text(checksum_text,encoding='utf-8')
with (DEST/'SHA256SUMS_TRANSFER.txt').open('x',encoding='utf-8') as f:f.write(checksum_text);f.flush();os.fsync(f.fileno())
assert sha(DEST/'SHA256SUMS_TRANSFER.txt')==sha(STAGE/'SHA256SUMS_TRANSFER.txt')
result={'status':'COMPLETE','verified_utc':datetime.now(timezone.utc).isoformat(),'usb_folder':str(DEST),
        'package_files_verified':len(hashes)+1,'restorable_original_files':report['files'],'restorable_original_bytes':report['logical_bytes'],
        'all_archived_objects_verified_before_copy':True,'all_copied_files_sha256_verified':True,
        'laptop_originals_retained':True,'existing_usb_files_modified':False,'checksums':hashes}
payload=json.dumps(result,indent=2)+'\n'
with (DEST/'USB_VERIFICATION_REPORT.json').open('x',encoding='utf-8') as f:f.write(payload);f.flush();os.fsync(f.fileno())
assert json.loads((DEST/'USB_VERIFICATION_REPORT.json').read_text())==result
(STAGE/'USB_VERIFICATION_REPORT.json').write_text(payload,encoding='utf-8')
print(json.dumps(result),flush=True)
