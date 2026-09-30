"""Independent real-source bridge reader; README_REVIEW_LIVE_SOURCE_BRIDGE_V1.md."""
import json
from pathlib import Path
import psutil
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE


def main():
    psutil.Process().cpu_affinity([14])
    run='live-source-bridge-v1'
    review=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(run)+'\n'+r'''
import ast,fcntl,hashlib,json,math,os,resource,signal,struct,subprocess,wave
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2);signal.alarm(45)
root=Path(ROOT)/RUN
def read(path):return json.loads(Path(path).read_text())
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');d=read(root/'DISPATCH_RESULT.json');e=read(root/'LIVE_ENVELOPE.json')
assert r['status']=='COLLECTED_NATIVE_REAL_SOURCE_FAKE_CALLBACK_IPC_ONLY' and d['exit_code']==0 and not d['log_overflow'] and not d['memory_guard']
assert not a['capture'] and not r['capture'] and not r['models_loaded'] and not r['hardware_startup_qualified'] and not r['physical_restoration_qualified'] and not r['combined_B01_qualified']
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1048576]*2 and e['affinity']==[2,3]
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active' and int(e['properties']['MainPID'])==e['owner']['pid']
assert e['properties']['TasksMax']=='64' and e['properties']['RuntimeMaxUSec']=='5min' and e['properties']['TimeoutStopUSec']=='10s'
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
with wave.open(a['source_wav'],'rb') as wav:
 assert wav.getnchannels()==1 and wav.getframerate()==16000 and wav.getsampwidth()==2
 pcm=[x[0]/32768 for x in struct.iter_unpack('<h',wav.readframes(20000))]
tree=ast.parse((Path(a['prototype'])/'app/_fir97_v1.py').read_text())
taps=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TAPS' for t in n.targets));assert len(taps)==97
cases={'drain_after_stop':None,'stop_pending':None,'callback_fault':'LIVE_SOURCE_GAP','raw_ring_overflow':'LIVE_SOURCE_GAP','oversized_callback':'LIVE_SOURCE_GAP','restore_mismatch':'SOURCE_CLOSE_FAILED','cancel_empty':None,'short_tail':None,'tap_o1':None}
assert [x['case'] for x in r['cases']]==list(cases)
metrics=[];peaks=[]
for index,item in enumerate(r['cases']):
 name=item['case'];case=root/name;cfg=read(case/'CONFIG.json');raw=read(case/'RAW_SETUP.json');close=read(case/'BRIDGE_CLOSE.json');child=read(case/'CHILD_RESULT.json')
 assert read(case/'CASE_RESULT.json')==item and child.pop('terminal_sent') and child.pop('terminal_acknowledged') and child==item['terminal']
 assert item['process_exit']==(1 if cases[name] else 0) and not item['forced_close']
 assert (item['observed_fault']['code'] if item['observed_fault'] else None)==cases[name]
 frames=raw['accepted_frames'];native=sum(frames);samples=native//3
 assert native%3==0 and item['accepted_native_frames']==native and item['accepted_model_samples']==samples
 assert child['sent_samples']==samples and child['sent_blocks']==len(frames)==item['blocks']
 assert child['address_space']==[128*1024**2]*2 and child['stack']==[1048576]*2 and child['affinity']==[2,3]
 assert child['high_blocks']<=64 and child['high_bytes']<=65536
 data=(case/'AUDIO.f32').read_bytes();assert len(data)==samples*4 and hashlib.sha256(data).hexdigest()==item['audio_sha256']==child['audio_sha256']
 values=[v[0] for v in struct.iter_unpack('<f',data)];gain=f32(10**(3/20)) if cfg['tap']=='O0' else 1.
 sign=1 if cfg['tap']=='O0' else -1
 expected=[f32(f32(math.fsum(sign*pcm[(n-k)//3]*taps[k] for k in range(min(97,n+1))))*gain) for n in range(0,native,3)]
 error=max((abs(x-y) for x,y in zip(values,expected)),default=0.);assert error<=1e-7 and all(math.isfinite(x) for x in values)
 offset=origin=count=0;max_ipc=0
 for line in (case/'TRACE.jsonl').read_text().splitlines():
  v=json.loads(line);m=v['metadata'];assert v['sequence']==count and v['offset']==offset
  assert hashlib.sha256(data[offset*4:(offset+v['samples'])*4]).hexdigest()==v['audio_sha256']
  assert m['model_start_sample']==offset and m['native_start_frame']==origin and m['native_frames']==frames[count] and m['epoch']==index+1
  assert m['adc_time_seconds']==100+origin/48000 and m['callback_current_time_seconds']==100.032+origin/48000
  assert m['priming_native_frames']==0 and m['resampler_delay_seconds']==.001
  assert m['callback_monotonic_ns']<=m['delivery_monotonic_ns']<=v['published_ns']<=v['received_ns']
  assert m['source_lag_seconds']==max(0.,(m['delivery_monotonic_ns']-m['callback_monotonic_ns'])/1e9)
  max_ipc=max(max_ipc,v['received_ns']-v['published_ns']);offset+=v['samples'];origin+=frames[count];count+=1
 assert offset==samples and origin==native and count==len(frames)
 final=close['final_status'];assert final==item['final_status'] and final['finished'] and final['pending_raw_blocks']==0 and final['raw_frames']==native and final['converted_samples']==samples
 assert close['bridge_native_frames']==native and close['bridge_model_samples']==samples and close['stream_closed'] and close['lease_released'] and not close['errors']
 assert close['original_stop_status']==read(case/'BRIDGE_STOP.json')['status']==item['original_stop_status']
 assert read(case/'CLEANUP_CALLS.json')==['route_restore_with_clock_and_lease','stream_stop','stream_close']
 with (case/'fake-device.lock').open('r+b') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if name=='restore_mismatch':
  assert close['route_restoration']=={'AEC_ASROUTONOFF':'MISMATCH'} and child['fault']['detail']['message']=='SOURCE_RESTORATION_FAILED'
 else:assert close['route_restoration']=={'AEC_ASROUTONOFF':'RESTORED'}
 if name in ['callback_fault','raw_ring_overflow','oversized_callback']:
  detail=final['callback_fault_detail'];assert detail['raw_status_bits']==(2 if name=='callback_fault' else 0) and detail['upstream_lost_frames'] is None and detail['loss_extent']=='UNKNOWN'
  assert detail['rejected_callback_frames']==final['dropped_frames']==(960 if name=='oversized_callback' else 480)
  assert child['fault']['detail']['status']['pending_raw_blocks']==0
 else:assert final['dropped_frames']==0 and final['fault'] is None
 peaks.append(child['peak_rss_bytes']);metrics.append(dict(case=name,native_frames=native,model_samples=samples,blocks=count,fault=cases[name],independent_fir_maxabs=error,stop_pending_blocks=close['original_stop_status']['pending_raw_blocks'],final_pending_blocks=0,maximum_ipc_delay_ns=max_ipc,process_exit=item['process_exit']))
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
owners=list(root.rglob('*OWNER.json'));assert len(owners)==11
for path in owners:
 o=read(path);assert o['boot_id']==boot and ticks(o['pid'])!=o['start_ticks']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
for path in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file());assert size<a['target_output_max_bytes']
print(json.dumps(dict(status='PASS_NATIVE_REAL_SOURCE_NINE_FAKE_CALLBACK_IPC_CASES_ONLY',cases=metrics,main_peak_rss_bytes=r['peak_rss_bytes'],maximum_child_peak_rss_bytes=max(peaks),elapsed_seconds=r['elapsed_seconds'],output_bytes=size,owner_count=len(owners),owners_closed=True,capture=False,models_loaded=False,baseline_unchanged=True,leases_free=True,hardware_startup_qualified=False,physical_restoration_qualified=False,combined_B01_qualified=False,hashes={n:sha(root/n) for n in ['ADMISSION.json','RESULT.json','DISPATCH_RESULT.json','LIVE_ENVELOPE.json']})))
''')
    out=PRIVATE/(run+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    with (out/'REVIEW.json').open('x') as f:json.dump(review,f,indent=2)
    remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(run)+'\nV='+repr(review)+'\n'+'import json\nfrom pathlib import Path\nwith (Path(ROOT)/RUN/"REVIEW.json").open("x") as f:json.dump(V,f,indent=2)\nprint(json.dumps({"written":True}))')
    print(json.dumps({k:v for k,v in review.items() if k!='hashes'}))


if __name__=='__main__':main()
