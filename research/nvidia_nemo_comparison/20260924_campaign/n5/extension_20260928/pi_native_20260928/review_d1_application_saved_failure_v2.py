"""Independent compact binding review; README_REVIEW_D1_APPLICATION_SAVED_FAILURE_V2.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/d1-application-saved-v2'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'control/ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'control/LIVE_ENVELOPE.json')
assert out['status']=='FAILED_PRESERVED' and out['error']=='AssertionError: '
assert "after['phase'] == 'STOPPED'" in out['traceback']
assert dispatch['exit_code']==1 and not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
assert env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
for row in a['files']:assert sha(row['path'])==row['sha256']
spec=read(r/'code/D1_APPLICATION_SAVED_INPUT_V2.json');old=r.parent/spec['retained_run']
for name,h in spec['installed_files'].items():assert sha(Path(spec['prototype'])/name)==h
for name,pin in spec['pins'].items():
 if name!='REVIEW.json':assert (old/name).stat().st_size==pin['bytes'] and sha(old/name)==pin['sha256']
raw_failure=(r/'app_failure/WORKER_FAILURE.txt').read_text()
assert 'assert array.shape == ((samples+159)//160, 8)' in raw_failure and raw_failure.endswith('AssertionError\n')
close=read(r/'passage_closure/MODEL_CLOSURE.json')
assert all(close[k] for k in ['source_closed','model_closed','model_pointer_empty','stream_pointer_empty','bundle_diarizer_empty','worker_joined','model_created'])
assert close['samples']==19200 and close['frames']==121 and close['worker_error']=='AssertionError: '
assert close['session_id']=='d1-application-saved-v2'
assert not (r/'app_receipts/GUI_STOP.json').exists() and not (r/'app_receipts/APPLICATION_CLOSURE.json').exists()
assert not (r/'data/runtime.lock').exists()
assert not list((r/'data/people').iterdir()) and not list((r/'data/conversations').iterdir())
last=read(r/'app_receipts/last_application.json')
assert last['microphone_open'] is False and last['metrics']['completed_sessions']==0 and last['metrics']['events_consumed']==0
assert [x['stage'] for x in last['output_defaults']]==['application_open','application_exit']
with (r/'data/.runtime.guard').open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
start=read(r/'passage/START_REQUEST.json')
assert start['schema']=='d1-saved-application-start.v1' and start['selected']['id']=='streaming' and start['capture'] is False
assert start['source_sha256']==spec['pins']['source.wav']['sha256'] and start['session_id']==close['session_id']
calls=[json.loads(x) for x in (r/'passage/CALLS.jsonl').read_bytes().splitlines()]
assert len(calls)==13 and [x['source_samples'] for x in calls[:-1]]==list(range(1600,19201,1600))
cursor=0
for i,row in enumerate(calls):
 assert row['frame_start']==cursor and row['frame_end']>=cursor
 cursor=row['frame_end'];assert cursor*.01<=row['source_samples']/16000+.011
 assert row['kind']==('finish' if i==12 else 'push')
assert cursor==121 and calls[-1]['frame_start']==104 and calls[-1]['source_samples']==19200
import ast,math
from array import array
def npy(path):
 raw=path.read_bytes();assert raw[:8]==b'\x93NUMPY\x01\x00'
 length=int.from_bytes(raw[8:10],'little');header=ast.literal_eval(raw[10:10+length].decode())
 assert header['descr']=='<f4' and header['fortran_order'] is False
 values=array('f');values.frombytes(raw[10+length:]);assert len(values)==math.prod(header['shape'])
 assert all(math.isfinite(v) and 0<=v<=1 for v in values)
 return header['shape'],values
shape,values=npy(r/'passage/PROBABILITIES.npy');prior_shape,prior=npy(old/'saved_full.npy')
assert shape==(121,8) and prior_shape==(4470,8)
error=max(abs(x-y) for x,y in zip(values[:104*8],prior[:104*8]));assert error<=1e-5
catalog=read(r/'code/D1_MODE_CATALOG_V1.json');mode=next(m for m in catalog['modes'] if m['id']=='streaming')
assert read(r/'passage/CABI.json')==dict(mode='streaming',observed=mode['geometry'])
assert read(r/'passage/ASSETS.json')['assets']=={v['name']:dict(bytes=v['bytes'],sha256=v['sha256']) for v in mode['assets']}
mapped=[json.loads(x) for x in (r/'passage/MAPPED.jsonl').read_bytes().splitlines()];assert len(mapped)==2
allowed={(old/x['name']).resolve() for x in mode['assets'] if x['name'].startswith('nemo-arm64/lib/')}
for row in mapped:
 assert row['mode']=='streaming' and set(Path(x).resolve() for x in row['paths'])<=allowed
 assert any(Path(x).name=='libnemo_speech_asr.so' for x in row['paths'])
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
 assert closure['logical_success'] is False and closure['exit_code']==1 and closure['closure_retained'] and closure['work_complete'] and closure['failure'] is None
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
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in samples),default=None),resource_rows=len(samples),temperature_range_c=[min(x['temperature_c'] for x in samples),max(x['temperature_c'] for x in samples)],throttle_states=sorted(set(x['throttle'] for x in samples)),minimum_available_ram_bytes=min(x['available_ram_bytes'] for x in samples),expected_failure_preserved=True,model_start_reached=True,source_samples=19200,frames=121,pre_eof_frames=104,independent_pre_eof_max_abs=error,eof_frames=17,eof_tail_matched_reference=False,actual_source_model_worker_closed=True,application_runtime_lock_absent_and_free=True)))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'d1-application-saved-v2-evidence/FAILURE_REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
