from pathlib import Path
import json, zipfile, hashlib, time, os

STAGE = Path(__file__).resolve().parent
def digest_file(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def verify():
    rows=json.loads((STAGE/'inventory.json').read_text(encoding='utf-8'))
    manifest=json.loads((STAGE/'RESTORE_MANIFEST.json').read_text(encoding='utf-8'))
    assert [{k:r[k] for k in ('path','bytes','mtime_ns','sha256')} for r in rows] == manifest['files']
    unique={r['sha256']:r for r in rows}; last=time.monotonic()
    with zipfile.ZipFile(STAGE/'XVF_DATA.zip') as z:
        assert set(z.namelist()) == {'objects/'+key for key in unique}
        for i,(key,row) in enumerate(unique.items()):
            h=hashlib.sha256(); n=0
            with z.open('objects/'+key) as f:
                for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b);n+=len(b)
            assert n == row['bytes'] and h.hexdigest() == key, row['path']
            if time.monotonic()-last>15:
                print(json.dumps({'verified_objects':i+1,'total':len(unique)}),flush=True);last=time.monotonic()
    changed=[]
    for r in rows:
        s=Path(r['source']).stat()
        if (s.st_size,s.st_mtime_ns) != (r['bytes'],r['mtime_ns']):changed.append(r['path'])
    assert not changed, changed
    root=Path('C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement')
    current=set()
    def walk_error(error):raise error
    for folder,dirs,files in os.walk(root,onerror=walk_error):
        current.update('project/'+(Path(folder)/name).relative_to(root).as_posix() for name in files)
    expected={r['path'] for r in rows if r['path'].startswith('project/')}
    assert current==expected, {'new':sorted(current-expected),'missing':sorted(expected-current)}
    report={'status':'LOCAL_ARCHIVE_VERIFIED','files':len(rows),'unique_objects':len(unique),'logical_bytes':manifest['logical_bytes'],
            'archive_bytes':(STAGE/'XVF_DATA.zip').stat().st_size,'archive_sha256':digest_file(STAGE/'XVF_DATA.zip'),
            'all_objects_sha256_verified':True,'inventory_matches_restore_manifest':True,'source_file_set_rechecked':True,'sources_changed_since_inventory':changed}
    (STAGE/'VERIFICATION_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__ == '__main__':verify()
