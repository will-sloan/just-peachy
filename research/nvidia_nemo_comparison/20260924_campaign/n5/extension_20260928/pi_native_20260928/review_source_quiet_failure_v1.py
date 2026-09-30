"""Independent failed physical startup and no-setter accounting; README_REVIEW_SOURCE_QUIET_FAILURE_V1.md."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path,PurePosixPath
import psutil
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
from dispatch_b01_stack_v2 import SSH


def main():
    psutil.Process().cpu_affinity([14])
    x=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import fcntl,hashlib,json,math,os,resource,signal,struct,subprocess,wave
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2);signal.alarm(110)
root=Path(ROOT)/'source-quiet-v1';d=root/'quiet'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');e=read(root/'LIVE_ENVELOPE.json');di=read(root/'DISPATCH_RESULT.json')
assert r['status']=='COLLECTED_ISOLATED_QUIET_FAILURE_ONLY' and di['exit_code']==0 and not di['log_overflow'] and not di['memory_guard']
assert r['fault']['code']=='LiveAudioError' and 'AEC_MIC_ARRAY_TYPE' in r['fault']['detail']['message']
assert r['capture'] and not r['models_loaded'] and not r['controller_integrated'] and not r['live_B01_qualified']
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active' and e['properties']['MainPID']==str(e['owner']['pid'])
assert e['properties']['RuntimeMaxUSec']=='5min' and e['properties']['TimeoutStopUSec']=='1min' and e['properties']['TasksMax']=='64'
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1024**2]*2 and e['affinity']==[2,3]
assert int(e['properties']['LimitAS'])==768*1024**2 and int(e['properties']['LimitSTACK'])==1024**2 and int(e['properties']['LimitFSIZE'])==8*1024**2
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
assert a['capture'] and a['child_address_space_bytes']==256*1024**2 and a['child_deadline_seconds']==90
assert sha(root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')==a['authority_sha256'] and read(root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')['scheduled_quiet_capture_authorized']
assert sha(root/'alsa_hw_only_v1.conf')==a['alsa_config_sha256']=='d81bc353dcab14d172e78b26c6116bfc8462b96e45e44b1a93ac3f217898564d'
assert sha(root/'LIVE_CONFIG_BACKUP.json')==a['live_config_sha256'] and sha(root/'INSTALL_BACKUP.json')==a['install_sha256']
c=read(d/'CHILD_RESULT.json');owner=read(d/'CHILD_OWNER.json');final=r['final'];failure=read(d/'SOURCE_START_FAILURE.json')
assert c.pop('terminal_sent') and c.pop('terminal_acknowledged') and c==final['terminal']
assert c['fault']==r['fault'] and c['owner']==owner and c['address_space']==[256*1024**2]*2 and c['stack']==[1024**2]*2 and c['affinity']==[2,3]
assert c['high_blocks']==c['high_bytes']==0 and not final['forced_close'] and final['child_exit']==1
assert r['delivered_samples']==r['native_frames']==r['blocks']==c['sent_samples']==c['sent_blocks']==0
assert (d/'AUDIO.f32').stat().st_size==(d/'TRACE.jsonl').stat().st_size==0 and sha(d/'AUDIO.f32')==c['audio_sha256']
with wave.open(str(d/'microphone.wav'),'rb') as w:assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,0)
assert (d/'microphone.wav').stat().st_size==44 and r['pcm']['closed'] and r['pcm']['status']=='SOURCE_FAILURE'
assert r['consumer_pause'] is None and r['stop_requested_ns'] is None
status=failure['status'];assert not status['started'] and status['finished'] and status['raw_frames']==status['converted_samples']==status['pending_raw_blocks']==status['dropped_frames']==0
assert status['priming_frames_discarded_before_route_verified']>0 and status['restoration_frames_discarded_after_stop']>0 and not failure['errors']
assert 'hw:2,1' in failure['metadata']['endpoint']['name'] and failure['metadata']['stream_start_return_perf_counter_ns']>=failure['metadata']['stream_start_perf_counter_ns']
commands=failure['commands'];assert [x['command'] for x in commands]==['VERSION','BLD_MSG','AEC_MIC_ARRAY_TYPE']*2
assert all(not x['arguments'] for x in commands) and all(x['exit_code']==(255 if x['command']=='AEC_MIC_ARRAY_TYPE' else 0) for x in commands)
assert set(failure['route_restoration'])=={'persisted_snapshot_verification'} and failure['route_restoration']['persisted_snapshot_verification'].startswith('FAILED: AEC_MIC_ARRAY_TYPE')
for name in ['SOURCE_START.json','PRE_ROUTE_SNAPSHOT.json','POST_ROUTE_SNAPSHOT.json','BRIDGE_STOP.json','BRIDGE_CLOSE.json']:assert not (d/name).exists()
receipts=list((d/'route_receipts').glob('*.json'));assert len(receipts)==1 and read(receipts[0])==failure
owners=list(root.rglob('*OWNER.json'));assert len(owners)==3
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
for path in owners:
 o=read(path);assert o['boot_id']==boot and ticks(o['pid'])!=o['start_ticks']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
for path in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.rglob('*') if p.is_file()};size=sum(row['bytes'] for row in files.values());assert size<a['target_output_max_bytes']==16*1024**2
review=dict(status='REVIEWED_ACTUAL_ISOLATED_SOURCE_STARTUP_READBACK_FAILURE_ONLY',accepted_samples=0,native_accepted_frames=0,priming_discarded_frames=status['priming_frames_discarded_before_route_verified'],stop_discarded_frames=status['restoration_frames_discarded_after_stop'],control_setters=0,readback_failure='AEC_MIC_ARRAY_TYPE',main_peak_rss_bytes=r['peak_rss_bytes'],child_peak_rss_bytes=c['peak_rss_bytes'],sampled_aggregate_peak_bytes=max(z.get('aggregate_rss_bytes',0) for z in di['samples']),protocol_seconds=r['protocol_seconds'],output_bytes=size,owners_closed=len(owners),capture_stream_opened=True,usable_audio_saved=False,models_loaded=False,baseline_unchanged=True,leases_free=True,route_snapshot_restored=False,route_mutations_observed=False,child_exit=1,parent_exit=0,terminal_failure_acknowledged=True,controller_integrated=False,live_B01_qualified=False)
print(json.dumps(dict(review=review,files=files)))
''')
    out=PRIVATE/'source-quiet-v1-evidence';assert not (out/'target').exists() and not (out/'REVIEW.json').exists()
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/source-quiet-v1 -cf - .'],timeout=90)
    backup=out/'target';backup.mkdir();seen=set()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tar:
        for member in tar:
            if member.isdir():continue
            assert member.isfile() and member.name.startswith('./')
            name=member.name[2:];path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts and name in x['files'] and name not in seen
            raw=tar.extractfile(member).read();assert len(raw)==x['files'][name]['bytes'] and hashlib.sha256(raw).hexdigest()==x['files'][name]['sha256']
            dest=backup.joinpath(*path.parts);dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:f.write(raw)
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==x['files'][name]['sha256'];seen.add(name)
    assert seen==set(x['files'])
    combined=x['review']['output_bytes']+sum(p.stat().st_size for p in out.rglob('*') if p.is_file());assert combined+128*1024<32*1024**2
    x['review'].update(backup_verified=True,backup_files=len(seen),combined_with_backup_bytes=combined)
    for name,value in [('REVIEW.json',x['review']),('BACKUP.json',x['files'])]:
        with (out/name).open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps(x['review']))


if __name__=='__main__':main()
