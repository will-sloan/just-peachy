"""Independent compact binding review; README_D1_APPLICATION_SAVED_V5.md."""
import hashlib
import json
from pathlib import Path
import psutil


def main():
    psutil.Process().cpu_affinity([14])
    from dispatch_geometry_v2 import remote,PRIVATE
    result=remote(r'''
import os,sys,resource
sys.dont_write_bytecode=True;os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2)
import json,hashlib,fcntl,subprocess
from pathlib import Path
r=Path.home()/'JustPeachy/research/nemotron-20260928/d1-application-saved-v5'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'control/ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'control/LIVE_ENVELOPE.json')
top=out;out={**top,**top['passage']}
assert out['status']=='PASS_INSTALLED_D1_SAVED_SELECTION_START_STOP_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
import struct,math
spec=read(r/'code/D1_APPLICATION_SAVED_INPUT_V5.json');old=r.parent/spec['retained_run']
for name,pin in spec['pins'].items():
 if name!='REVIEW.json':assert (old/name).stat().st_size==pin['bytes'] and sha(old/name)==pin['sha256']
samples_count=out['source_samples'];frames_count=out['output_frames']
assert out['mode']=='delayed' and 340800<=samples_count<352127 and frames_count==(0 if samples_count==0 else samples_count//160+1)
assert sha(r/'code/PRIOR_REVIEW.json')==spec['pins']['REVIEW.json']['sha256']
assert sha(spec['installed_n2_source'])==spec['installed_n2_sha256']
assert all(top[k] for k in ['actual_controller_constructor','actual_ui_constructor','actual_buttons','saved_source_closed','model_worker_joined','controller_closed','command_worker_joined','application_lease_released','Tk_destroyed'])
assert not any(top[k] for k in ['request_is_fixture','live_start_available','capture','ASR','visible_rendering','physical_touch','native_failure_stress','new_speedup_claim','accuracy_claim'])
endpoint=read(r/'passage/ENDPOINT_BINDING.json')
assert endpoint==out['endpoint_contract'] and endpoint['source_object_link_verified'] and out['expected_output_frames']==frames_count
assert endpoint['contract_sha256']==sha(r/'code/D1_ENDPOINT_CONTRACT_V3.json')
assert out['session_id']=='d1-application-saved-v5' and out['source_position']==samples_count and out['stop_requested']
closure=read(r/'passage_closure/MODEL_CLOSURE.json')
assert all(closure[k] for k in ['source_closed','model_created','model_closed','model_pointer_empty','stream_pointer_empty','bundle_diarizer_empty','worker_joined'])
assert closure['worker_error'] is None and closure['session_id']=='d1-application-saved-v5'
assert closure['samples']==samples_count and closure['frames']==frames_count
for name,h in spec['installed_files'].items():assert sha(Path(spec['prototype'])/name)==h
for item in spec['availability'].values():
 assert sha(r/'code'/item['receipt'])==item['sha256'] and read(r/'code'/item['receipt'])['status']==item['status']
gui=read(r/'app_receipts/GUI_STOP.json');app=read(r/'app_receipts/APPLICATION_CLOSURE.json')
assert gui['selection']['selected']['selection']['id']=='delayed' and gui['selection']['start_available']
assert gui['before_stop']['owned'] and not gui['after_stop']['owned'] and gui['after_stop']['phase']=='STOPPED'
assert gui['selection']['selected']['schema']=='d1-saved-mode-selection.v1' and 'reason' not in gui['selection']['selected'] and 'launchable' not in gui['selection']['selected']
assert gui['selection']['admitted_mode']=='delayed' and gui['selection']['live_start_available'] is False
assert 'Delayed' in gui['status_text'] and gui['status_text'].startswith('STOPPED / ')
for item in spec['saved_application_evidence'].values():
 assert sha(r/'code'/item['receipt'])==item['sha256'] and read(r/'code'/item['receipt'])['status']==item['status']
assert gui['application_lease_still_owned'] and gui['model_worker_joined'] and gui['root_withdrawn'] and not gui['physical_touch']
assert all(app[k] for k in ['controller_closed','command_worker_joined','model_worker_joined','application_lease_released','Tk_destroyed'])
assert sorted(q.relative_to(r).as_posix() for q in r.rglob('*') if q.is_dir())==app['directories']
assert not (r/'data/runtime.lock').exists() and read(r/'data/DATA_SCHEMA.json')=={'schema_version':1}
assert not list((r/'data/people').iterdir()) and not list((r/'data/conversations').iterdir())
assert read(r/'app_receipts/last_application.json')['microphone_open'] is False
start=read(r/'passage/START_REQUEST.json')
assert start['schema']=='d1-saved-application-start.v1' and start['scope']=='saved-input-only' and start['capture'] is False
assert start['selected']==gui['selection']['selected']['selection'] and start['session_id']==out['session_id']
assert start['source_sha256']==spec['pins']['source.wav']['sha256'] and start['maximum_samples']==352127
# Independently rederive exact accepted PCM16-to-float32 prefix bytes without importing the model.
import wave,struct
with wave.open(str(old/'source.wav'),'rb') as wav:
 assert wav.getframerate()==16000 and wav.getnchannels()==1 and wav.getsampwidth()==2
 pcm=wav.readframes(samples_count)
raw=b''.join(struct.pack('<f',x[0]/32768.) for x in struct.iter_unpack('<h',pcm))
assert hashlib.sha256(raw).hexdigest()==out['source_prefix_float32_sha256']
calls=[json.loads(x) for x in (r/'passage/CALLS.jsonl').read_bytes().splitlines()]
cursor=0;samples_seen=0
for i,row in enumerate(calls):
 assert row['frame_start']==cursor and row['frame_end']>=cursor
 cursor=row['frame_end'];assert cursor*.01<=row['source_samples']/16000+.011
 if row['kind']=='push':
  assert row['source_samples']-samples_seen==min(1600,samples_count-samples_seen)
  samples_seen=row['source_samples']
 else:assert row['kind']=='finish' and i==len(calls)-1 and row['source_samples']==samples_seen
assert samples_seen==samples_count and cursor==frames_count and len(calls)==(samples_count+1599)//1600+1
before_eof=calls[-1]['frame_start'];assert 0<before_eof<cursor and before_eof==out['pre_eof_frames']
# NumPy .npy parsing via stdlib keeps review free of model/runtime imports.
import ast
from array import array
def npy(path):
 raw=path.read_bytes();assert raw[:8]==b'\x93NUMPY\x01\x00'
 length=int.from_bytes(raw[8:10],'little');header=ast.literal_eval(raw[10:10+length].decode())
 assert header['descr']=='<f4' and header['fortran_order'] is False
 values=array('f');values.frombytes(raw[10+length:]);assert len(values)==math.prod(header['shape'])
 assert all(math.isfinite(v) and 0<=v<=1 for v in values)
 return header['shape'],values
shape,values=npy(r/'passage/PROBABILITIES.npy');prior_shape,prior=npy(old/'saved_full.npy')
assert shape==(frames_count,8) and prior_shape==(4470,8)
error=max(abs(x-y) for x,y in zip(values[:before_eof*8],prior[:before_eof*8]))
assert error<=1e-5 and error==out['pre_eof_max_abs'] and out['eof_frames']==frames_count-before_eof
assert out['eof_tail_matched_reference'] is False
geometry=read(r/'passage/CABI.json');catalog=read(r/'code/D1_MODE_CATALOG_V1.json');mode=next(m for m in catalog['modes'] if m['id']=='delayed')
assert geometry==dict(mode='delayed',observed=mode['geometry'])
assets=read(r/'passage/ASSETS.json');expected={v['name']:dict(bytes=v['bytes'],sha256=v['sha256']) for v in mode['assets']}
assert assets['assets']==expected
mapped=[json.loads(x) for x in (r/'passage/MAPPED.jsonl').read_bytes().splitlines()]
assert len(mapped)==2
allowed={(old/x['name']).resolve() for x in mode['assets'] if x['name'].startswith('nemo-arm64/lib/')}
for row in mapped:
 assert row['mode']=='delayed' and set(Path(x).resolve() for x in row['paths'])<=allowed
 assert 2<=len(row['paths'])<=5
 assert any(Path(x).name.startswith('libnemo_speech_asr_c.so') for x in row['paths']) and any(Path(x).name=='libnemo_speech_asr.so' for x in row['paths'])
assert any(Path(x).name.startswith('libggml-cpu.so') for x in mapped[-1]['paths'])
for group,key in [('passage','passage_limits'),('passage_closure','passage_closure_limits'),('app_receipts','app_receipt_limits'),('app_failure','app_failure_limits')]:
 files=[q for q in (r/group).iterdir() if q.name!='.budget.guard'];limit=a[key]
 assert len(files)<=limit['maximum_files'] and sum(q.stat().st_size for q in files)<=limit['maximum_bytes']
 assert all(q.stat().st_size<=limit['maximum_file_bytes'] for q in files)
for group,limits in a['metadata_limits'].items():
 sizes=[p.stat().st_size for p in (r/group).iterdir() if p.name!='.budget.guard']
 assert sum(sizes)<=limits['maximum_bytes'] and len(sizes)<=limits['maximum_files'] and all(x<=limits['maximum_file_bytes'] for x in sizes)
assert not any((r/n).exists() for n in ['OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','ADMISSION.json'])
assert all((r/'control'/n).exists() for n in ['OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','ADMISSION.json'])
for guard in r.rglob('.budget.guard'):
 assert guard.stat().st_size==0
 with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not list(r.rglob('*.pending')) and not list(r.rglob('*.wav'))
samples=[json.loads(line) for line in (r/'outer/telemetry/resources.jsonl').read_bytes().splitlines()]
assert len(samples)==dispatch['resource_rows']>=1
for sample in samples:
 ids=[tuple(i) for i in sample['aggregate_unique_identities']];assert len(ids)==len(set(ids))
assert dispatch['process_reaped'] and dispatch['pipe_closed']
for role in ['gate','worker']:
 closure=read(r/'outer/closure_reserve'/(role+'-OUTPUT_CLOSURE.json'))
 assert closure['logical_success'] and closure['closure_retained'] and closure['work_complete'] and closure['failure'] is None
 assert closure['raw_retention_complete'] and closure['rejected_bytes']==0
 if role=='gate':assert closure['log_bytes']==(r/'outer/logs/service.log').stat().st_size and closure['resource_rows']==len(samples)
assert not (r/'RESULT.json').exists() and not (r/'DISPATCH_RESULT.json').exists() and not (r/'service.log').exists()
assert sha(r/'control/LIVE_CONFIG_BACKUP.json')==a['live_config_sha256'] and sha(r/'control/INSTALL_BACKUP.json')==a['install_sha256']
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for p in owners:
 o=read(p);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<4*1024**2
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in samples),default=None),resource_rows=len(samples),temperature_range_c=[min(x['temperature_c'] for x in samples),max(x['temperature_c'] for x in samples)],throttle_states=sorted(set(x['throttle'] for x in samples)),minimum_available_ram_bytes=min(x['available_ram_bytes'] for x in samples),independent_pre_eof_max_abs=error)))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'d1-application-saved-v5-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
