"""Independent closed artifact review; README_REVIEW_FIELD_ARTIFACT_LIMITS_V1.md."""
import argparse
import hashlib
import json
from pathlib import Path
import psutil


def main():
    psutil.Process().cpu_affinity([14])
    parser=argparse.ArgumentParser();parser.add_argument('--run',choices=['field-artifact-limits-v1','field-artifact-limits-v2'],required=True)
    args=parser.parse_args()
    from dispatch_geometry_v2 import remote, PRIVATE
    result=remote('RUN='+repr(args.run)+'\n'+r'''
import os,sys,resource
sys.dont_write_bytecode=True
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
import json,hashlib,subprocess,fcntl,wave,struct
from pathlib import Path
r=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');result=read(r/'RESULT.json');d=read(r/'DISPATCH_RESULT.json');e=read(r/'LIVE_ENVELOPE.json')
for row in a['files']:assert sha(row['path'])==row['sha256']
installed=Path(a['installed_release'])
assert {p.relative_to(installed).as_posix():sha(p) for p in installed.rglob('*') if p.is_file()}==a['installed_files']
assert not any(a[k] for k in ['capture','models_loaded','audio_saved']) and a['synthetic_artifacts']
assert e['affinity']==[2,3] and e['address_space']==[768*1024**2]*2 and e['stack']==[1024**2]*2
assert e['properties']['TasksMax']=='64' and e['properties']['RuntimeMaxUSec']=='5min' and e['properties']['TimeoutStopUSec']=='1min'
assert int(e['properties']['LimitFSIZE'])==32*1024**2 and int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
assert not d['log_overflow'] and not d['memory_guard']
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for path in owners:
 o=read(path);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for path in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
summary=dict(status='REVIEWED_ARTIFACT_PROTOCOL_FAILURE_ONLY',natural_exit=d['exit_code'],result=result,
 owner_count=len(owners),capture_closed=True,baseline_unchanged=True,
 aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in d['samples']),default=None))
if result['status']=='FAILED_PRESERVED':
 assert d['exit_code']==1 and result['error'] and result['traceback']
 summary['synthetic_artifacts_started']=(r/'native-events.jsonl').exists()
else:
 assert result['status']=='PASS_EXPLICIT_ARTIFACT_WRITERS_AND_JOINED_PARTIAL_FINALIZATION' and d['exit_code']==0
 limits=read(r/'ARTIFACT_LIMITS_V1.json')
 assert limits['native_journal_bytes']==limits['conversation_journal_bytes']==16*1024**2 and limits['pcm_max_frames']==2080000
 def journal(path,status,count):
  with path.open('rb') as f:
   index=0
   while True:
    line=f.readline(1024**2+1);assert line and len(line)<=1024**2 and line.endswith(b'\n')
    row=json.loads(line)
    if row['format']=='footer':
     assert row['count']==index==count and row['status']==status and not f.read(1);return
    assert row['format']=='event' and row['seq']==index
    if path.name=='native-events.jsonl':assert row['value']==dict(kind='synthetic_boundary',index=index,payload='x'*32768)
    index+=1
 journal(r/'native-events.jsonl','COMPLETE',272)
 assert 8*1024**2<(r/'native-events.jsonl').stat().st_size<16*1024**2
 c=read(r/'native-extended.json');assert c['clean'] and c['physical_sink_closed'] and not c['worker_alive'] and c['uncompleted']==0
 for name,samples,state in [('extended-archive',2080000,'CLOSED'),('archive-byte-failure',160,'PARTIAL'),('archive-frame-failure',160,'PARTIAL')]:
  folder=r/name;m=read(folder/'epoch.json')
  assert m['state']==state and m['closed'] and not m['worker_alive'] and m['recorded_samples']==samples
  assert m['queue_items']==m['queue_bytes']==0
  assert (folder/'model_input.f32le').stat().st_size==samples*4 and (folder/'model_input.wav').stat().st_size==44+samples*2
  assert sha(folder/'model_input.f32le')==m['audio_sha256']
  with wave.open(str(folder/'model_input.wav'),'rb') as wav,(folder/'model_input.f32le').open('rb') as f:
   assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())==(1,2,16000,samples)
   for start in range(0,samples,16000):
    n=min(16000,samples-start)
    values=[((i%257)-128)/256 if name=='extended-archive' else 0.0 for i in range(start,start+n)]
    assert f.read(n*4)==struct.pack('<'+'f'*n,*values)
    assert wav.readframes(n)==struct.pack('<'+'h'*n,*[round(v*32768) for v in values])
   assert not f.read(1) and not wav.readframes(1)
  if state=='CLOSED':
   assert m['accepted_items']==m['completed_items']==260 and m['source_samples']==samples and not m['archive_error']
   journal(folder/'events.jsonl','COMPLETE',130)
  else:assert m['accepted_items']>m['completed_items'] and m['archive_error']
 f=read(r/'native-byte-failure-closure.json');assert not f['clean'] and f['physical_sink_closed'] and not f['worker_alive'] and f['accepted']==4 and f['uncompleted']>0
 journal(r/'native-byte-failure.jsonl','BYTE_LIMIT',f['completed'])
 assert read(r/'native-failed-close.json')['rejected'] and read(r/'native-repeated-failed-close.json')['rejected']
 b=read(r/'archive-byte-failure/epoch.json');assert 'BYTE_LIMIT' in b['archive_error']
 journal(r/'archive-byte-failure/events.jsonl','BYTE_LIMIT',b['artifact_metrics']['events']['events'])
 f=read(r/'archive-frame-failure/epoch.json');assert 'FRAME_LIMIT' in f['archive_error'] and f['source_samples']==480 and f['recorded_samples']==160
 assert not list(r.glob('must-not-exist*'))
 assert len(list(r.glob('invalid-contract-*.json')))==8
 assert result['rejected']==16 and result['cases']==21
 summary.update(status='PASS_NATIVE_EXPLICIT_ARTIFACT_LIMITS_AND_PARTIAL_CLOSURE_ONLY',
  extended_synthetic_frames=2080000,native_journal_bytes=(r/'native-events.jsonl').stat().st_size,
  no_installed_entry_or_live_claim=True,pipeline_wiring_executed=False,models_loaded=False,capture=False)
summary['target_bytes']=sum(p.stat().st_size for p in r.rglob('*') if p.is_file())
assert summary['target_bytes']<a['target_output_max_bytes']==32*1024**2
print(json.dumps(summary))
''')
    out=PRIVATE/(args.run+'-evidence')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (out/'REVIEW.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))


if __name__=='__main__':main()
