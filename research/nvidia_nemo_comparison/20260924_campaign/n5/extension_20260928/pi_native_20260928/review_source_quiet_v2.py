"""Independent actual isolated quiet source verification/backup; README_REVIEW_SOURCE_QUIET_V2.md."""
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
root=Path(ROOT)/'source-quiet-v2';d=root/'quiet'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');e=read(root/'LIVE_ENVELOPE.json');di=read(root/'DISPATCH_RESULT.json')
assert r['status']=='COLLECTED_ISOLATED_ACTUAL_QUIET_SOURCE_ONLY' and di['exit_code']==0 and not di['log_overflow'] and not di['memory_guard']
assert r['capture'] and not r['models_loaded'] and not r['controller_integrated'] and not r['live_B01_qualified'] and r['fault'] is None
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active' and e['properties']['MainPID']==str(e['owner']['pid'])
assert e['properties']['RuntimeMaxUSec']=='5min' and e['properties']['TimeoutStopUSec']=='1min' and e['properties']['TasksMax']=='64'
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1024**2]*2 and e['affinity']==[2,3]
assert int(e['properties']['LimitAS'])==768*1024**2 and int(e['properties']['LimitSTACK'])==1024**2 and int(e['properties']['LimitFSIZE'])==8*1024**2
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
recovery=read(root/'RECOVERY_REVIEW.json');assert sha(root/'RECOVERY_REVIEW.json')==a['recovery_review_sha256'] and recovery['status']=='PASS_CONDITIONAL_SINGLE_MAINTENANCE_SEND_FIRMWARE_READBACK_ONLY' and recovery['backup_verified']
for row in a['recovery_bindings']:assert sha(row['path'])==row['sha256']
assert a['capture'] and a['child_address_space_bytes']==256*1024**2 and a['child_deadline_seconds']==90
assert sha(root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')==a['authority_sha256'] and read(root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')['scheduled_quiet_capture_authorized']
assert sha(root/'alsa_hw_only_v1.conf')==a['alsa_config_sha256']=='d81bc353dcab14d172e78b26c6116bfc8462b96e45e44b1a93ac3f217898564d'
assert sha(root/'LIVE_CONFIG_BACKUP.json')==a['live_config_sha256'] and sha(root/'INSTALL_BACKUP.json')==a['install_sha256']
assert read(d/'PRE_ROUTE_SNAPSHOT.json')==read(d/'POST_ROUTE_SNAPSHOT.json')
c=read(d/'CHILD_RESULT.json');owner=read(d/'CHILD_OWNER.json');final=r['final'];close=read(d/'BRIDGE_CLOSE.json');metadata=read(d/'SOURCE_START.json')
assert c.pop('terminal_sent') and c.pop('terminal_acknowledged') and c==final['terminal'] and c['fault'] is None
assert c['owner']==owner and c['address_space']==[256*1024**2]*2 and c['stack']==[1024**2]*2 and c['affinity']==[2,3]
assert c['high_blocks']<=64 and c['high_bytes']<=65536 and not final['forced_close'] and final['child_exit']==0 and c['stopped']
assert 'hw:2,1' in metadata['endpoint']['name'] and metadata['actual_stream_rate']==48000 and not metadata['timestamps_calibrated_to_acoustic_arrival']
assert metadata['stream_start_perf_counter_ns']<=metadata['stream_start_return_perf_counter_ns']
n=r['delivered_samples'];assert 192000<=n<=320000 and n==c['sent_samples']==final['delivered_samples']
assert r['native_frames']==final['native_frames']==n*3 and r['blocks']==c['sent_blocks']
data=(d/'AUDIO.f32').read_bytes();assert len(data)==n*4 and sha(d/'AUDIO.f32')==c['audio_sha256']
values=[v[0] for v in struct.iter_unpack('<f',data)];assert all(math.isfinite(v) for v in values)
expected=b''.join(struct.pack('<h',round(min(32767/32768,max(-1,v))*32768)) for v in values)
with wave.open(str(d/'microphone.wav'),'rb') as w:
 assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,n)
 assert w.readframes(n)==expected and not w.readframes(1)
assert (d/'microphone.wav').stat().st_size==44+2*n and r['pcm']['closed'] and r['pcm']['frames']==n and r['pcm']['status']=='COMPLETE'
assert r['pcm']['clipped_samples']==sum(v< -1 or v>32767/32768 for v in values)
trace=[json.loads(line) for line in (d/'TRACE.jsonl').read_text().splitlines()];assert len(trace)==r['blocks']
epoch=None;offset=0;native=0;max_ipc=0;previous_adc=None;pause_packets=0
pause=r['consumer_pause'];assert pause['end_ns']-pause['begin_ns']>=200_000_000
for item in trace:
 m=item['metadata'];count=item['samples'];assert m['model_start_sample']==offset and m['native_start_frame']==native and m['native_frames']==480 and count==160
 assert m['resampler_delay_seconds']==.001 and m['callback_monotonic_ns']<=m['delivery_monotonic_ns']<=item['ipc']['published_ns']<=item['ipc']['received_ns']
 if epoch is None:epoch=m['epoch']
 assert m['epoch']==epoch and item['audio_sha256']==hashlib.sha256(data[offset*4:(offset+count)*4]).hexdigest()
 if previous_adc is not None:assert m['adc_time_seconds']>=previous_adc
 previous_adc=m['adc_time_seconds'];max_ipc=max(max_ipc,item['ipc']['received_ns']-item['ipc']['published_ns'])
 if pause['begin_ns']<=item['ipc']['published_ns']<=pause['end_ns']:pause_packets+=1
 offset+=count;native+=m['native_frames']
assert offset==n and native==n*3 and pause_packets>0
s=close['final_status'];assert s['finished'] and not s['fault'] and s['dropped_frames']==0 and s['pending_raw_blocks']==0 and s['raw_frames']==n*3 and s['converted_samples']==n
assert close['stream_closed'] and close['lease_released'] and not close['errors'] and close==c['source_close']
assert close['original_stop_status']==read(d/'BRIDGE_STOP.json')['status']
assert all(v in ('RESTORED','ALREADY_RESTORED') for v in close['route_restoration'].values()) and close['route_restoration']['persisted_snapshot_verification']=='RESTORED'
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
review=dict(status='PASS_ACTUAL_ISOLATED_QUIET_SOURCE_PCM_DRAIN_AND_RESTORATION_ONLY',samples=n,native_frames=n*3,blocks=r['blocks'],pause_published_blocks=pause_packets,maximum_observed_ipc_seconds=max_ipc/1e9,pending_raw_at_stop=close['original_stop_status']['pending_raw_blocks'],final_pending_raw=0,main_peak_rss_bytes=r['peak_rss_bytes'],child_reported_ru_maxrss_bytes=c['peak_rss_bytes'],sampled_aggregate_peak_bytes=max(z.get('aggregate_rss_bytes',0) for z in di['samples']),protocol_seconds=r['protocol_seconds'],output_bytes=size,owners_closed=len(owners),capture=True,models_loaded=False,baseline_unchanged=True,leases_free=True,route_snapshot_restored=True,controller_integrated=False,live_B01_qualified=False,post_recovery_receipt_bound=True,restoration_target='readable post-restart snapshot',pre_restart_volatile_state_restored=False)
print(json.dumps(dict(review=review,files=files)))
''')
    out=PRIVATE/'source-quiet-v2-evidence';assert not (out/'target').exists() and not (out/'REVIEW.json').exists()
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/source-quiet-v2 -cf - .'],timeout=90)
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
