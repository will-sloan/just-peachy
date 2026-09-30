"""Independent native IPC reader; README_REVIEW_ISOLATED_SOURCE_V1.md."""
import json
from pathlib import Path
import psutil
from dispatch_geometry_v2 import remote, PRIVATE, REMOTE


def main():
    psutil.Process().cpu_affinity([14])
    run='isolated-source-v1'
    review=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(run)+'\n'+r'''
import os,resource,signal,hashlib,json,struct,wave,subprocess,fcntl
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2);signal.alarm(45)
root=Path(ROOT)/RUN
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(n):return json.loads((root/n).read_text())
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read('ADMISSION.json');r=read('RESULT.json');d=read('DISPATCH_RESULT.json');e=read('LIVE_ENVELOPE.json')
assert r['status']=='COLLECTED_NATIVE_ISOLATED_SOURCE_FIXTURE_ONLY' and d['exit_code']==0 and not d['log_overflow'] and not d['memory_guard']
assert not a['capture'] and not r['capture'] and not r['models_loaded'] and not r['application_integrated'] and not r['live_fault_repaired']
assert a['child_address_space_bytes']==128*1024**2 and a['maximum_active_children']==1
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1048576]*2 and e['affinity']==[2,3]
assert e['properties']['RuntimeMaxUSec']=='5min' and e['properties']['TasksMax']=='64' and e['properties']['TimeoutStopUSec']=='10s'
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active' and int(e['properties']['MainPID'])==e['owner']['pid']
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
with wave.open(a['source_wav'],'rb') as wav:
 assert wav.getframerate()==16000 and wav.getnchannels()==1 and wav.getsampwidth()==2
 pcm=wav.readframes(wav.getnframes())
expected=b''.join(struct.pack('<f',v[0]/32768) for v in struct.iter_unpack('<h',pcm))
assert len(expected)==715127*4
faults={'full':None,'repeat':None,'empty':None,'tail':None,'paced_parent_stall':None,'stop':None,'backpressure':'BACKPRESSURE_TIMEOUT','source_fault':'INPUT_STATUS_GAP','discontinuity':'SOURCE_DISCONTINUITY','malformed_bytes':'MALFORMED_AUDIO_BYTES','metadata_quota':'METADATA_QUOTA','startup_failure':'FIXTURE_STARTUP_FAILURE','child_abrupt':'CHILD_EOF_WITHOUT_TERMINAL'}
assert [v['case'] for v in r['cases']]==list(faults)
rows=[];child_peaks=[]
for index,item in enumerate(r['cases']):
 name=item['case'];case=root/name;cfg=json.loads((case/'CONFIG.json').read_text())
 assert json.loads((case/'CASE_RESULT.json').read_text())==item
 assert (item['observed_fault']['code'] if item['observed_fault'] else None)==faults[name]==item['expected_fault']
 assert not item['forced_close'] and item['post_close_rejected']
 offset=count=0;prior_time=None;max_gap=0;delays=[]
 with (case/'TRACE.jsonl').open() as f:
  for line in f:
   v=json.loads(line);assert v['sequence']==count and v['offset']==offset and 0<v['samples']<=160
   audio=expected[offset*4:(offset+v['samples'])*4];assert hashlib.sha256(audio).hexdigest()==v['audio_sha256']
   m=v['metadata'];assert m['model_start_sample']==offset and m['native_start_frame']==offset*3 and m['native_frames']==v['samples']*3 and m['epoch']==index+1
   assert m['source_kind']=='SAVED_FIXTURE_NOT_CAPTURE' and m['source_read_monotonic_ns']<=v['published_ns']<=v['received_ns']
   if prior_time is not None:max_gap=max(max_gap,m['source_read_monotonic_ns']-prior_time)
   prior_time=m['source_read_monotonic_ns'];delays.append(v['received_ns']-v['published_ns']);offset+=v['samples'];count+=1
 assert offset==item['accepted_samples'] and count==item['blocks'] and max_gap==item['max_source_read_gap_ns']
 assert hashlib.sha256(expected[:offset*4]).hexdigest()==item['audio_sha256']
 if name=='child_abrupt':
  assert item['process_exit']==7 and item['terminal'] is None and not (case/'CHILD_RESULT.json').exists()
 else:
  terminal=item['terminal'];saved=json.loads((case/'CHILD_RESULT.json').read_text());assert saved.pop('terminal_sent') and saved==terminal
  assert terminal['sent_samples']==offset and terminal['sent_blocks']==count and terminal['audio_sha256']==item['audio_sha256']
  assert terminal['high_blocks']<=64 and terminal['high_bytes']<=65536
  assert terminal['address_space']==[128*1024**2]*2 and terminal['stack']==[1048576]*2 and terminal['affinity']==[2,3]
  assert item['process_exit']==(1 if faults[name] else 0)
  if name!='startup_failure':assert terminal['source_close']['closed'] and not terminal['source_close']['capture']
  child_peaks.append(terminal['peak_rss_bytes'])
 if name in ['full','repeat','empty','tail','paced_parent_stall']:assert offset==cfg['limit_samples']
 if name=='stop':assert 3200<=offset<715127 and item['terminal']['stopped']
 if name=='source_fault':
  detail=item['observed_fault']['detail'];assert detail==dict(raw_status_bits=2,rejected_callback_frames=480,upstream_lost_frames=None,loss_extent='UNKNOWN',input_buffer_adc_time_seconds=10.25,callback_current_time_seconds=10.282)
 rows.append(dict(case=name,accepted_samples=offset,blocks=count,fault=faults[name],process_exit=item['process_exit'],maximum_ipc_delay_ns=max(delays,default=0),max_source_read_gap_ns=max_gap,elapsed_ns=item['elapsed_ns'],high_blocks=item['terminal']['high_blocks'] if item['terminal'] else None,high_bytes=item['terminal']['high_bytes'] if item['terminal'] else None))
assert r['cases'][0]['audio_sha256']==r['cases'][1]['audio_sha256']
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
owners=list(root.rglob('*OWNER.json'));assert len(owners)==15
for path in owners:
 o=json.loads(path.read_text());assert o['boot_id']==boot and ticks(o['pid'])!=o['start_ticks']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
for lock in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with lock.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file());assert size<a['target_output_max_bytes']
print(json.dumps(dict(status='PASS_NATIVE_ISOLATED_SOURCE_13_FIXTURE_CASES_ONLY',cases=rows,source_bytes_exact=True,ordered_prefixes_exact=True,owner_count=len(owners),all_owners_closed=True,baseline_unchanged=True,capture_closed=True,leases_free=True,models_loaded=False,application_integrated=False,live_fault_repaired=False,output_bytes=size,main_peak_rss_bytes=r['peak_rss_bytes'],maximum_child_peak_rss_bytes=max(child_peaks),sum_of_process_peaks_not_simultaneous=r['peak_rss_bytes']+max(child_peaks),elapsed_seconds=r['elapsed_seconds'],hashes={n:sha(root/n) for n in ['ADMISSION.json','RESULT.json','DISPATCH_RESULT.json','LIVE_ENVELOPE.json']})))
''')
    out=PRIVATE/(run+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    with (out/'REVIEW.json').open('x') as f:json.dump(review,f,indent=2)
    remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(run)+'\nV='+repr(review)+'\n'+'import json\nfrom pathlib import Path\nwith (Path(ROOT)/RUN/"REVIEW.json").open("x") as f:json.dump(V,f,indent=2)\nprint(json.dumps({"written":True}))')
    print(json.dumps({k:v for k,v in review.items() if k not in ['hashes','cases']}))


if __name__=='__main__':main()
