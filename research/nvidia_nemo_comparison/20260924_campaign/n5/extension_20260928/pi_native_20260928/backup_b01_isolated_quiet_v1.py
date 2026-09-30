"""Private exact closed-run backup; README_REVIEW_B01_ISOLATED_QUIET_V1.md."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import psutil


def main():
    psutil.Process().cpu_affinity([14])
    from dispatch_geometry_v2 import remote, PRIVATE, REMOTE
    from dispatch_b01_stack_v2 import SSH
    run='b01-isolated-quiet-v1'
    out=PRIVATE/(run+'-evidence')
    review=json.loads((out/'REVIEW.json').read_text())
    assert review['status']=='PASS_B01_ISOLATED_QUIET_30S_FUNCTIONAL_PCM_DRAIN_ONLY'
    files=remote('RUN='+repr(run)+'\n'+r'''
import hashlib,json,os,resource
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2)
d=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for p in d.rglob('*OWNER.json'):
 o=json.loads(p.read_text());q=Path('/proc',str(o['pid']),'stat')
 assert not q.exists() or int(q.read_text().rsplit(')',1)[1].split()[19])!=o['start_ticks']
files={p.relative_to(d).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in d.rglob('*') if p.is_file()}
assert sum(x['bytes'] for x in files.values())<32*1024**2
print(json.dumps(files))
''')
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/'+run+' -cf - .'],timeout=90)
    backup=out/'target';backup.mkdir();seen=set()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as archive:
        for member in archive:
            if member.isdir():continue
            assert member.isfile() and member.name.startswith('./')
            name=member.name[2:];path=PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts and name in files and name not in seen
            raw=archive.extractfile(member).read()
            assert len(raw)==files[name]['bytes'] and hashlib.sha256(raw).hexdigest()==files[name]['sha256']
            dest=backup.joinpath(*path.parts);dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:f.write(raw)
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==files[name]['sha256'];seen.add(name)
    assert seen==set(files)
    combined=sum(x['bytes'] for x in files.values())+sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert combined+1024**2<64*1024**2
    receipt=dict(status='EXACT_PRIVATE_TARGET_BACKUP_VERIFIED',files=files,file_count=len(files),target_bytes=sum(x['bytes'] for x in files.values()),combined_bytes=combined,review_sha256=hashlib.sha256((out/'REVIEW.json').read_bytes()).hexdigest())
    with (out/'BACKUP.json').open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'}))


if __name__=='__main__':main()
