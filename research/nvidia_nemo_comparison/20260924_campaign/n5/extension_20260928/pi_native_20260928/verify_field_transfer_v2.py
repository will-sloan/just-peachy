"""Read-only retained compact archive review; README_FIELD_TRANSFER_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from pathlib import Path
import json,sys,hashlib,time,traceback
from datetime import datetime,timezone

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installed-release',required=True,type=Path)
    p.add_argument('--saved-root',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();a.output.mkdir(exist_ok=False)
    owner=dict(pid=psutil.Process().pid,create_time=psutil.Process().create_time(),affinity=[14])
    with (a.output/'REGISTERED_OWNER.json').open('x') as f:json.dump(owner,f)
    began=time.monotonic()
    try:
        base=a.installed_release
        sys.path[:0]=[str(base),str(base/'vendor'),str(base/'native')]
        from field_transfer_v2 import derive,sha,CAPS
        from field_transfer_paths_v2 import project,TARGET_MAX,HOST_MAX,COMBINED_MAX
        from field_live_files_v2 import TOKENS
        raw=(base/'native/field_archive_v3.py').read_bytes()
        release=json.loads((base/'RELEASE_MANIFEST.json').read_bytes())
        pin=next(r for r in release['files'] if r['path']=='native/field_archive_v3.py')
        m=derive(raw,pin['sha256'])
        folder=a.saved_root/'data/conversations/0554ef941c234f2ab77f47685ccaa5e9'
        before={p.relative_to(folder).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in folder.rglob('*') if p.is_file()}
        result=m.validate_folder(folder,folder.name)
        after={p.relative_to(folder).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in folder.rglob('*') if p.is_file()}
        assert before==after and len(before)==7
        rejects=[]
        for label,fn in [
          ('old-source-pin',lambda:derive(raw,'0'*64)),
          ('changed-shape',lambda:derive(raw.replace(b'ZIP_MAX = 8*MIB',b'ZIP_MAX = 7*MIB'),hashlib.sha256(raw.replace(b'ZIP_MAX = 8*MIB',b'ZIP_MAX = 7*MIB')).hexdigest())),
          ('sqlite-member',lambda:m.member_cap('epochs/'+'1'*32+'/captions.sqlite')),
          ('parent-traversal',lambda:m.member_cap('epochs/../events.jsonl')),
          ('overflow-json',lambda:m.strict_json(b'{"v":1e999}')),
          ('duplicate-json',lambda:m.strict_json(b'{"v":1,"v":2}')),
        ]:
            try:fn()
            except ValueError:rejects.append(label)
            else:raise AssertionError('Expected reject '+label)
        projected=project(**TOKENS,code_files={'field_transfer_v2.py':len(Path(__file__).with_name('field_transfer_v2.py').read_bytes())},import_token='3'*32)
        assert projected['maximum_bytes']<=TARGET_MAX and COMBINED_MAX==TARGET_MAX+HOST_MAX
        receipt=dict(status='PASS_READ_ONLY_REAL_COMPACT_ARCHIVE_VALIDATION_ONLY',owner=owner,
            archive=result,members=before,derivation=m.derivation,rejects=rejects,
            projection=projected['transfer'],source_preserved=True,
            transfer_executed=False,delete_executed=False,native_or_gui_executed=False,
            seconds=time.monotonic()-began,ended_utc=datetime.now(timezone.utc).isoformat())
        with (a.output/'REVIEW.json').open('x') as f:json.dump(receipt,f,indent=2,allow_nan=False)
        print(json.dumps({k:receipt[k] for k in ('status','archive','rejects','projection','seconds')}))
    except BaseException:
        with (a.output/'FAILURE.txt').open('x',encoding='utf-8') as f:f.write(traceback.format_exc()[:65536])
        raise

if __name__=='__main__':main()
