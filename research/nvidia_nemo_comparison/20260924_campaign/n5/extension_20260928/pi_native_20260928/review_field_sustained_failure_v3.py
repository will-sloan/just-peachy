"""Independent native package review and private backup; README_FIELD_SUSTAINED_FAILURE_V3.md."""
import argparse
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import subprocess
import tarfile
import psutil


def main():
    psutil.Process().cpu_affinity([14])
    p=argparse.ArgumentParser();p.add_argument('--run',choices=['field-sustained-v2'],default='field-sustained-v2');args=p.parse_args()
    from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
    from dispatch_b01_stack_v2 import SSH
    x=remote('RUN='+repr(args.run)+'\n'+r'''
import os,json,hashlib,resource,subprocess,fcntl,zipfile,sys,base64
sys.dont_write_bytecode=True
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2)
root=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');dispatch=read(root/'DISPATCH_RESULT.json')
for row in a['files']:assert sha(row['path'])==row['sha256']
assert r['status']=='FAILED_BEFORE_PROTOCOL_RECEIPT' and r['error']=='ValueError: Dependency contract mismatch' and dispatch['exit_code']==1
assert 'field_sustained_build_v1.py' in r['traceback'] and 'Dependency contract mismatch' in r['traceback']
assert (root/'CANDIDATE_BUILD.json').exists() and (root/'LIVE_ENVELOPE.json').exists()
env=read(root/'LIVE_ENVELOPE.json');assert env['address_space']==[768*1024**2]*2 and int(env['properties']['LimitFSIZE'])==32*1024**2
assert not (root/'candidate/state.json').exists() and not (root/'data/runtime.lock').exists()
built=read(root/'CANDIDATE_BUILD.json');installed=Path(built['staged']['path']);assert sha(installed/'RELEASE_MANIFEST.json')==built['manifest_sha256']
for item in read(installed/'RELEASE_MANIFEST.json')['files']:assert sha(installed/item['path'])==item['sha256']
assert not (root/'data/source_receipts').exists() and not list((root/'data').rglob('*.wav'))
assert not dispatch['memory_guard'] and not dispatch['log_overflow']
owners=list(root.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for path in owners:
 o=read(path);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for path in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
source=Path(a['installed_release'])
assert {q.relative_to(source).as_posix():sha(q) for q in source.rglob('*') if q.is_file()}==a['installed_files']
assert sha(root/'data/live_config.json')==a['live_config_sha256'] and sha(root/'data/n2_runtime.json')==a['n2_runtime_sha256']
cache_additions={}
summary=dict(status='REVIEWED_SUSTAINED_PRE_GUI_DEPENDENCY_CONTRACT_FAILURE_ONLY',natural_exit=1,error=r['error'],traceback=r['traceback'],models_loaded=False,capture_opened=False,GUI_opened=False,installed_build_started=True,baseline_unchanged=True,capture_closed=True,leases_free=True,actual_live_envelope_receipt=True,scope='Fresh code package built and actual768MiB envelope passes; old dependency contract binding rejects new duration/reservation contract before candidate publication/GUI/controller/models/capture')
links={}
assert not any(p.is_symlink() for p in root.rglob('*'))
files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
size=sum(x['bytes'] for x in files.values());assert size<a['target_output_max_bytes']==64*1024**2
summary.update(owners_closed=len(owners),peak_rss_bytes=None,sampled_aggregate_peak_bytes=max((x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),default=None),target_bytes=size,baseline_unchanged=True,capture_closed=True,leases_free=True,field_release_accepted=False,model_inference=False)
summary['reader_generated_cache_additions']={k:v['sha256'] for k,v in cache_additions.items()}
print(json.dumps(dict(summary=summary,files=files,links=links,cache_additions=cache_additions)))
''')
    out=PRIVATE/(args.run+'-evidence');backup=out/'target';backup.mkdir();seen=set();seen_links=set()
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/'+args.run+' -cf - .'],timeout=90)
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as archive:
        for member in archive:
            if member.isdir():continue
            assert member.name.startswith('./');name=member.name[2:];path=PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts
            if member.issym():
                assert name in x['links'] and name not in seen_links and member.linkname==x['links'][name];seen_links.add(name);continue
            assert member.isfile() and name in x['files'] and name not in seen
            raw=archive.extractfile(member).read();assert len(raw)==x['files'][name]['bytes'] and hashlib.sha256(raw).hexdigest()==x['files'][name]['sha256']
            target=backup.joinpath(*path.parts);target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(raw)
            assert hashlib.sha256(target.read_bytes()).hexdigest()==x['files'][name]['sha256'];seen.add(name)
    assert seen==set(x['files']) and seen_links==set(x['links'])
    import base64
    for name,row in x['cache_additions'].items():
        raw=base64.b64decode(row['data']);assert hashlib.sha256(raw).hexdigest()==row['sha256']
        target=out/'reader-generated-caches'/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(raw)
    combined=x['summary']['target_bytes']+sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert combined+1024**2<128*1024**2
    x['summary'].update(review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),private_backup_verified=True,backup_files=len(seen),backup_links=len(seen_links),combined_bytes=combined)
    for name,value in [('REVIEW.json',x['summary']),('BACKUP.json',dict(files=x['files'],links=x['links'])),('SYMLINKS.json',x['links'])]:
        with (out/name).open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps({k:v for k,v in x['summary'].items() if k not in ['observations','negatives','actions']}))


if __name__=='__main__':main()
