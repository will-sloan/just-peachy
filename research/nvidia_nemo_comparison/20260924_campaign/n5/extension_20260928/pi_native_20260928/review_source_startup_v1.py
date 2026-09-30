"""Independent startup/interface lifecycle, FIR and backup; README_REVIEW_SOURCE_STARTUP_V1.md."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path,PurePosixPath
import psutil
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
from dispatch_b01_stack_v2 import SSH


def main():
    psutil.Process().cpu_affinity([14])
    x=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import ast,fcntl,hashlib,json,math,os,resource,signal,struct,subprocess,wave
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2);signal.alarm(110)
root=Path(ROOT)/'source-startup-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');e=read(root/'LIVE_ENVELOPE.json');di=read(root/'DISPATCH_RESULT.json')
assert r['status']=='COLLECTED_NATIVE_SOURCE_STARTUP_FACADE_FAKE_HARDWARE_ONLY' and di['exit_code']==0 and not di['log_overflow'] and not di['memory_guard']
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active' and e['properties']['MainPID']==str(e['owner']['pid'])
assert e['properties']['RuntimeMaxUSec']=='5min' and e['properties']['TimeoutStopUSec']=='10s' and e['properties']['TasksMax']=='64'
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1024**2]*2 and e['affinity']==[2,3]
assert int(e['properties']['LimitAS'])==768*1024**2 and int(e['properties']['LimitSTACK'])==1024**2 and int(e['properties']['LimitFSIZE'])==8*1024**2
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
with wave.open(a['source_wav'],'rb') as wav:pcm=[x[0]/32768 for x in struct.iter_unpack('<h',wav.readframes(15360))]
tree=ast.parse((Path(a['prototype'])/'app/_fir97_v1.py').read_text());taps=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TAPS' for t in n.targets));assert len(taps)==97
expected={'stop_pending':None,'empty_stop':None,'callback_fault':'LIVE_SOURCE_GAP','restore_failure':'SOURCE_CLOSE_FAILED','start_failure':'LiveAudioError'}
assert [row['case'] for row in r['cases']]==list(expected)
calls=['pa_terminate','pa_initialize','check_input_settings','construct_input_stream','stream_start','construct_control','route_apply_with_clock_and_lease']
metrics=[];child_peaks=[]
for row in r['cases']:
 name=row['case'];d=root/name;c=read(d/'CHILD_RESULT.json');owner=read(d/'CHILD_OWNER.json');final=row['final']
 assert read(d/'CASE_RESULT.json')==row and c.pop('terminal_sent') and c.pop('terminal_acknowledged') and c==final['terminal']
 assert c['owner']==owner and c['address_space']==[128*1024**2]*2 and c['stack']==[1024**2]*2 and c['affinity']==[2,3]
 assert c['high_blocks']<=64 and c['high_bytes']<=65536 and not final['forced_close'] and final['child_exit']==int(expected[name] is not None)
 assert (row['observed_fault']['code'] if row['observed_fault'] else None)==expected[name]
 assert row['invalid_calls_rejected']==(4 if name=='start_failure' else 6)
 expected_calls=calls+([] if name=='start_failure' else ['beam_start','beam_stop'])+['route_restore_with_clock_and_lease','stream_stop','stream_close']
 assert read(d/'STARTUP_CALLS.json')==expected_calls
 with (d/'fake-device.lock').open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if name=='start_failure':
  failure=read(d/'SOURCE_START_FAILURE.json');assert failure['status']['finished'] and not failure['errors'] and failure['route_restoration']=={'AEC_ASROUTONOFF':'RESTORED'}
  assert c['sent_samples']==row['delivered_samples']==0 and not (d/'SOURCE_START.json').exists()
  metrics.append(dict(case=name,samples=0,fault=expected[name],fake_cleanup_order_verified=True));child_peaks.append(c['peak_rss_bytes']);continue
 setup=read(d/'RAW_SETUP.json');close=read(d/'BRIDGE_CLOSE.json');metadata=read(d/'SOURCE_START.json')
 blocks=0 if name=='empty_stop' else (6 if name=='callback_fault' else 96);samples=blocks*160
 assert setup['blocks']==blocks and setup['native_frames']==blocks*480 and metadata['endpoint']['name']=='XMOS_FAKE_ONLY (hw:7,1)'
 assert metadata['actual_stream_rate']==48000 and metadata['raw_ring_capacity_seconds']==2 and not metadata['timestamps_calibrated_to_acoustic_arrival']
 assert metadata['stream_start_perf_counter_ns']<=metadata['stream_start_return_perf_counter_ns']
 assert row['blocks']==c['sent_blocks']==blocks and row['delivered_samples']==c['sent_samples']==final['delivered_samples']==samples
 assert row['native_frames']==final['native_frames']==blocks*480
 data=(d/'AUDIO.f32').read_bytes();assert len(data)==samples*4 and sha(d/'AUDIO.f32')==c['audio_sha256']
 values=[v[0] for v in struct.iter_unpack('<f',data)];gain=f32(10**(3/20));ref=[f32(f32(math.fsum(pcm[(n-k)//3]*taps[k] for k in range(min(97,n+1))))*gain) for n in range(0,blocks*480,3)]
 error=max((abs(x-y) for x,y in zip(values,ref)),default=0.);assert error<=1e-7 and all(math.isfinite(v) for v in values)
 trace=[json.loads(line) for line in (d/'TRACE.jsonl').read_text().splitlines()];assert len(trace)==blocks
 epoch=None
 for i,item in enumerate(trace):
  m=item['metadata'];assert m['model_start_sample']==i*160 and m['native_start_frame']==i*480 and m['native_frames']==480 and item['samples']==160
  assert m['priming_native_frames']==480 and m['resampler_delay_seconds']==.001 and m['adc_time_seconds']==10+i*.01 and m['callback_current_time_seconds']==10.02+i*.01
  assert m['callback_monotonic_ns']<=m['delivery_monotonic_ns']<=item['ipc']['published_ns']<=item['ipc']['received_ns']
  if epoch is None:epoch=m['epoch']
  assert m['epoch']==epoch and item['audio_sha256']==hashlib.sha256(data[i*640:(i+1)*640]).hexdigest()
 status=close['final_status'];assert status['finished'] and status['pending_raw_blocks']==0 and status['raw_frames']==blocks*480 and status['converted_samples']==samples
 assert status['priming_frames_discarded_before_route_verified']==480 and close['stream_closed'] and close['lease_released'] and not close['errors']
 assert close['original_stop_status']==read(d/'BRIDGE_STOP.json')['status']
 assert close['route_restoration']=={'AEC_ASROUTONOFF':'MISMATCH' if name=='restore_failure' else 'RESTORED'}
 if name=='stop_pending':assert close['original_stop_status']['pending_raw_blocks']>0
 if name=='callback_fault':assert status['callback_fault_detail']['raw_status_bits']==2 and status['callback_fault_detail']['upstream_lost_frames'] is None
 metrics.append(dict(case=name,samples=samples,native_frames=blocks*480,priming_frames=480,fault=expected[name],independent_fir_maxabs=error,pending_at_stop=close['original_stop_status']['pending_raw_blocks'],final_pending=0,fake_cleanup_order_verified=True))
 child_peaks.append(c['peak_rss_bytes'])
owners=list(root.rglob('*OWNER.json'));assert len(owners)==7 and r['capture'] is False and r['models_loaded'] is False
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
for path in owners:
 o=read(path);assert o['boot_id']==boot and ticks(o['pid'])!=o['start_ticks']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
for path in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.rglob('*') if p.is_file()};size=sum(row['bytes'] for row in files.values());assert size<a['target_output_max_bytes']==16*1024**2
review=dict(status='PASS_NATIVE_ACTUAL_STARTUP_AND_FACADE_FIVE_FAKE_DEVICE_CASES_ONLY',cases=metrics,main_peak_rss_bytes=r['peak_rss_bytes'],maximum_child_peak_rss_bytes=max(child_peaks),elapsed_seconds=r['elapsed_seconds'],output_bytes=size,owners_closed=len(owners),capture=False,models_loaded=False,baseline_unchanged=True,leases_free=True,hardware_startup_qualified=False,physical_restoration_qualified=False,controller_integrated=False,live_B01_qualified=False)
print(json.dumps(dict(review=review,files=files)))
''')
    out=PRIVATE/'source-startup-v1-evidence';assert not (out/'target').exists() and not (out/'REVIEW.json').exists()
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/source-startup-v1 -cf - .'],timeout=90)
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
