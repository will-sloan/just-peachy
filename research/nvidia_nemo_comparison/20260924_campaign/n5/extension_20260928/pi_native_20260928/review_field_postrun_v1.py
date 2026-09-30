"""Independent native package review and private backup; README_FIELD_POSTRUN_V1.md."""
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
    p=argparse.ArgumentParser();p.add_argument('--run',choices=['field-postrun-v1'],default='field-postrun-v1');args=p.parse_args()
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
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');dispatch=read(root/'DISPATCH_RESULT.json');env=read(root/'LIVE_ENVELOPE.json')
for row in a['files']:assert sha(row['path'])==row['sha256']
assert not a['capture'] and not a['models_loaded'] and not a['audio_saved']
assert env['affinity']==[2,3] and env['address_space']==[768*1024**2]*2 and env['stack']==[1048576]*2
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==8*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
owners=list(root.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for path in owners:
 o=read(path);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for path in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
installed=Path(a['installed_release']);source=Path(a['archive_source'])
cache_additions={}
for folder,key in [(installed,'installed_files'),(source,'archive_files')]:
 assert {p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}==a[key]
passed=r['status']=='PASS_INSTALLED_COPIED_QUIET_ARCHIVE_SAVE_OPEN_AND_UI_STATES_ONLY'
if not passed:
 assert r['status']=='FAILED_PRESERVED' and dispatch['exit_code']==1
 summary=dict(status='REVIEWED_COPIED_POSTRUN_FAILURE_ONLY',natural_exit=1,error=r['error'],GUI_opened=bool(list(root.glob('*.png'))),scope='Failure preserved; no new postrun acceptance')
else:
 assert dispatch['exit_code']==0 and r['controller_closed'] and r['model_loads']==0 and not r['capture_opened'] and not r['physical_touch']
 assert r['source_unchanged'] and r['prior_release_unchanged'] and r['samples']==448320 and r['reopened_rows']==0
 candidate=Path(r['installed_release']);manifest=read(candidate/'RELEASE_MANIFEST.json')
 assert manifest['version']=='b01-offline-20260930-v6'
 for item in manifest['files']:assert sha(candidate/item['path'])==item['sha256']
 assert sha(candidate/'app/field_caption_state_v1.py')==sha(root/'field_caption_state_v1.py')
 assert sha(candidate/'native/field_entry_v5.py')==sha(installed/'native/field_entry_v5.py')
 assert {p.relative_to(candidate).as_posix():sha(p) for p in candidate.rglob('*') if p.is_file()}==r['installed_hashes']
 folder=root/'data/conversations'/source.name
 after={p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}
 assert after==r['copied_files'] and set(after)==set(a['archive_files'])
 assert [n for n in after if after[n]!=a['archive_files'][n]]==['conversation.json']
 old=read(source/'conversation.json');new=read(folder/'conversation.json')
 assert new['pinned'] is True
 assert {k:v for k,v in old.items() if k not in ['pinned','updated_utc','state']}=={k:v for k,v in new.items() if k not in ['pinned','updated_utc','state']}
 epochs=list((folder/'epochs').glob('*/epoch.json'));assert len(epochs)==1
 ep=read(epochs[0]);assert ep['source_samples']==ep['recorded_samples']==448320 and ep['closed'] and ep['pipeline_terminal_state']=='COMPLETED'
 assert Path(ep['native_session_path']).resolve().parent==Path(a['original_session_parent']).resolve()
 assert r['durable_original_session']==str(Path(ep['native_session_path']).resolve())
 import wave
 wav=epochs[0].parent/'model_input.wav'
 with wave.open(str(wav),'rb') as f:assert f.getnframes()==448320 and f.getnchannels()==1 and f.getsampwidth()==2 and f.getframerate()==16000
 assert sha(wav)=='6cf4b9588a1235cfade46e23bdf26abc4985aa3550e6ad5501b9b2529db60b7a'
 assert sha(epochs[0].parent/'model_input.f32le')=='eef67382a3588bb83022e8cb179396603e17eb4fd2a37a09f2311195ad58ebb5'
 before=read(root/'FIRST_OPEN_SNAPSHOT.json');opened=read(root/'OPENED_SNAPSHOT.json')
 assert before['rows']==opened['rows']==[] and before['sessions']['caption_links']==opened['sessions']['caption_links']==[]
 assert opened['state']=='STOPPED' and opened['sessions']['opened_id']==source.name and len(opened['sessions']['library'])==1
 assert opened['sessions']['library'][0]['pinned'] is True
 counts=read(root/'MODEL_COUNTERS.json');assert counts==r['optional_counters']
 assert counts==dict(asr_loads=dict(available=True,value=0),speaker_loads=dict(available=True,value=0),punctuation_loads=dict(available=False,value=None))
 rejected=read(root/'REPORTING_REJECTIONS.json');assert rejected==r['diagnostic_rejections'] and len(rejected)==5 and all(x['error'] for x in rejected)
 actions=[read(p) for p in sorted(root.glob('ACTION_*.json'))];assert actions==r['actions'] and len(actions)==12 and all(x['complete'] for x in actions)
 assert not (root/'data/source_receipts').exists() and not any((root/'data/sessions').glob('*'))
 assert (root/'data/private-preservation-canary').read_bytes()==b'PRIVATE_SYNTHETIC_CANARY\n'
 expected={'stopped-saved':'No captions in this saved conversation.','fixture-starting':'Starting microphone…','fixture-running':'Listening for speech…','fixture-stopping':'Finishing this recording…','stopped-final':'No captions in this saved conversation.'}
 assert {x['name'] for x in r['observations']}==set(expected)
 for obs in r['observations']:
  assert (obs['width'],obs['height'])==(480,800) and sha(root/(obs['name']+'.png'))==obs['sha256']
  assert expected[obs['name']] in obs['text'] and obs['no_capture_fixture']==obs['name'].startswith('fixture-')
 summary=dict(status='PASS_INSTALLED_COPIED_ARCHIVE_SAVE_OPEN_AND_UI_STATES_PENDING_VISUAL_REVIEW',GUI_opened=True,display_rows=0,saved_samples=448320,actions=actions,observations=r['observations'],natural_exit=0,release_version=manifest['version'],release_manifest_sha256=sha(candidate/'RELEASE_MANIFEST.json'),optional_counters=counts,diagnostic_rejections=rejected)
links={}
assert not any(p.is_symlink() for p in root.rglob('*'))
files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
size=sum(x['bytes'] for x in files.values());assert size<a['target_output_max_bytes']==32*1024**2
summary.update(owners_closed=len(owners),peak_rss_bytes=r['peak_rss_bytes'],sampled_aggregate_peak_bytes=max(x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),target_bytes=size,baseline_unchanged=True,capture_closed=True,leases_free=True,field_release_accepted=False,model_inference=False)
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
    assert combined+1024**2<64*1024**2
    x['summary'].update(review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),private_backup_verified=True,backup_files=len(seen),backup_links=len(seen_links),combined_bytes=combined)
    for name,value in [('REVIEW.json',x['summary']),('BACKUP.json',dict(files=x['files'],links=x['links'])),('SYMLINKS.json',x['links'])]:
        with (out/name).open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps({k:v for k,v in x['summary'].items() if k not in ['observations','negatives','actions']}))


if __name__=='__main__':main()
