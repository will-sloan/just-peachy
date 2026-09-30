"""Independent native package review and private backup; README_REVIEW_FIELD_DEPENDENCY_FAILURE_V2.md."""
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
    p=argparse.ArgumentParser();p.add_argument('--census',type=Path,required=True);p.add_argument('--run',choices=['field-dependency-v1'],default='field-dependency-v1');args=p.parse_args()
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
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json') if (root/'RESULT.json').exists() else dict(status='RESULT_ABSENT');dispatch=read(root/'DISPATCH_RESULT.json');env=read(root/'LIVE_ENVELOPE.json')
for row in a['files']:assert sha(row['path'])==row['sha256']
assert not a['capture'] and not a['models_loaded'] and not a['audio_saved']
assert env['affinity']==[2,3] and env['address_space']==[768*1024**2]*2 and env['stack']==[1048576]*2
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==8*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
assert dispatch['log_overflow'] and not dispatch['memory_guard'] and not (root/'RESULT.json').exists()
owners=list(root.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for path in owners:
 o=read(path);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for path in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
installed=Path(a['installed_release']);source=Path(a['rollback_release'])
cache_additions={}
for folder,key in [(installed,'installed_files'),(source,'rollback_files')]:
 assert {p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}==a[key]
assert r['status']=='RESULT_ABSENT' and dispatch['exit_code']==0
log=(root/'service.log').read_text();assert 'code=killed/status=TERM' in log
assert dispatch['output_bytes']>a['target_output_max_bytes']
probe=read(root/'PROBE.json');assert probe['capture_closed'] and not probe['models_loaded'] and not probe['Tk_root_created']
assert read(root/'PROBE_COMMAND.json')['exit_code']==0
pins=read(root/'DEPENDENCIES.json');mapped=set(probe['mapped_elf']);assert mapped<={x['resolved'] for x in pins['entries']}
current=read(root/'deployment/current.json');prior=read(root/'deployment/previous.json')
assert current['version']=='b01-offline-20260930-v7' and prior['version']=='b01-offline-20260930-v5'
assert len(list((root/'deployment/history').glob('*.json')))==2
assert not (root/'POINTER_SEQUENCE.json').exists() and not (root/'REJECTIONS.json').exists()
summary=dict(status='REVIEWED_DEPENDENCY_OUTPUT_GUARD_TERM_NO_RESULT',natural_exit=False,collector_exit_code=0,process_termination='TERM',
 output_guard_exceeded=True,admitted_target_bytes=a['target_output_max_bytes'],observed_dispatch_output_bytes=dispatch['output_bytes'],
 protocol_seconds=dispatch['seconds'],partial_dependency_entries=len(pins['entries']),partial_unique_files=pins['unique_files'],partial_unique_bytes=pins['unique_logical_bytes'],
 partial_ELF_roots=len(pins['elf']),import_link_mapped_ELFs=len(mapped),import_link_child_exit=0,
 rollback_reached=False,final_negative_receipts_absent=True,candidate_pointer=current['version'],previous_candidate_pointer=prior['version'],
 original_baseline_activation=False,scope='Partial collection/import and candidate activation observations only; whole protocol rejected; no new model/capture/GUI')
links={}
assert not any(p.is_symlink() for p in root.rglob('*'))
files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
size=sum(x['bytes'] for x in files.values());assert 16*1024**2<size<24*1024**2
summary.update(owners_closed=len(owners),peak_rss_bytes=max(x.get('VmRSS',0)*1024 for x in dispatch['samples']),sampled_aggregate_peak_bytes=max(x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),target_bytes=size,baseline_unchanged=True,capture_closed=True,leases_free=True,field_release_accepted=False,model_inference=False)
summary['reader_generated_cache_additions']={k:v['sha256'] for k,v in cache_additions.items()}
print(json.dumps(dict(summary=summary,files=files,links=links,cache_additions=cache_additions,target_total_bytes=int(subprocess.check_output(['du','-sb',str(root.parent)],text=True).split()[0]),source_admission_sha256=sha(root/'ADMISSION.json'))))
''')
    import sys,time,shutil
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    from window_guard_v5 import budget,payload_inventory
    from dispatch_geometry_v2 import LOCAL
    assert time.time()-args.census.stat().st_mtime<900
    c=json.loads(args.census.read_text());used=0
    for rel in ['n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928']:
        inv=payload_inventory(LOCAL/rel);assert not inv['errors'] and not inv['reparse_not_traversed'];used+=inv['total_logical_bytes']
    delta=used-c['calculation']['window_used_bytes'];assert delta>=0
    calculation=budget(c['calculation']['existing_bytes']+delta+x['target_total_bytes'],used+x['target_total_bytes'],24*1024**2,{d:shutil.disk_usage(d+'/').free for d in ['C:','G:']},52)
    out=PRIVATE/(args.run+'-evidence')
    admission=dict(purpose='New bounded private backup of preserved target output overshoot; original run admission remains failed/unchanged',requested_host_backup_bytes=24*1024**2,target_bytes_to_preserve=x['summary']['target_bytes'],source_admission_sha256=x['source_admission_sha256'],reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),census_sha256=hashlib.sha256(args.census.read_bytes()).hexdigest(),calculation=calculation)
    with (out/'FAILURE_BACKUP_ADMISSION_V1.json').open('x') as f:json.dump(admission,f,indent=2)
    backup=out/'target';backup.mkdir();seen=set();seen_links=set()
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
    assert combined-x['summary']['target_bytes']+1024**2<24*1024**2
    x['summary'].update(review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),private_backup_verified=True,backup_files=len(seen),backup_links=len(seen_links),combined_bytes=combined)
    for name,value in [('REVIEW.json',x['summary']),('BACKUP.json',dict(files=x['files'],links=x['links'])),('SYMLINKS.json',x['links'])]:
        with (out/name).open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps({k:v for k,v in x['summary'].items() if k not in ['observations','negatives','actions']}))


if __name__=='__main__':main()
