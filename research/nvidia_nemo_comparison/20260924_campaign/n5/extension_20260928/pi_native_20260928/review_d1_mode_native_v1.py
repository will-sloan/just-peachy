"""Independent compact binding review; README_D1_MODE_NATIVE_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/d1-mode-native-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'control/ADMISSION.json');out=read(r/'outer/receipts/RESULT.json');dispatch=read(r/'outer/receipts/DISPATCH_RESULT.json');env=read(r/'control/LIVE_ENVELOPE.json')
assert out['status']=='PASS_NEW_DELAYED_FACTORY_PASSAGE_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
import struct,math
spec=read(r/'code/D1_MODE_NATIVE_INPUT_V1.json');old=r.parent/spec['retained_run']
for name,pin in spec['pins'].items():
 if name!='REVIEW.json':assert (old/name).stat().st_size==pin['bytes'] and sha(old/name)==pin['sha256']
assert out['mode']=='delayed' and out['source_samples']==352127 and out['output_frames']==2201
assert sha(r/'code/PRIOR_REVIEW.json')==spec['pins']['REVIEW.json']['sha256']
assert out['model_closed'] and not any(out[k] for k in ['capture','audio_saved','ASR','GUI','application_integrated','new_speedup_claim','accuracy_claim','paced'])
closure=read(r/'passage_closure/MODEL_CLOSURE.json')
assert all(closure[k] for k in ['factory_returned','model_closed','model_pointer_empty','stream_pointer_empty','passage_checks_complete'])
assert closure['samples']==352127 and closure['frames']==2201
calls=[json.loads(x) for x in (r/'passage/CALLS.jsonl').read_bytes().splitlines()]
cursor=0;samples_seen=0
for i,row in enumerate(calls):
 assert row['frame_start']==cursor and row['frame_end']>=cursor
 cursor=row['frame_end'];assert cursor*.01<=row['source_samples']/16000+.011
 if row['kind']=='push':
  assert row['source_samples']-samples_seen==min(1600,352127-samples_seen)
  samples_seen=row['source_samples']
 else:assert row['kind']=='finish' and i==len(calls)-1 and row['source_samples']==samples_seen
assert samples_seen==352127 and cursor==2201 and len(calls)==out['calls']==222
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
assert shape==(2201,8) and prior_shape==(4470,8)
error=max(abs(x-y) for x,y in zip(values[:before_eof*8],prior[:before_eof*8]))
assert error<=1e-5 and error==out['pre_eof_max_abs'] and out['eof_frames']==2201-before_eof
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
for group,key in [('passage','passage_limits'),('passage_closure','passage_closure_limits')]:
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
    with (PRIVATE/'d1-mode-native-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
