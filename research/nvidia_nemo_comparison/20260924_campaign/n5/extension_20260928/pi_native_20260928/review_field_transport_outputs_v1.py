"""Independent compact binding review; README_FIELD_TRANSPORT_OUTPUTS_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-transport-outputs-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_TRANSPORT_OUTPUT_AND_TRACE_ADAPTER_FIXTURES_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
plan=read(r/'FIELD_WHOLE_RUN_ALLOCATION_V2.json');cases=read(r/'TRANSPORT_OUTPUT_CASES.json')
assert len(cases)==9 and len({x['case'] for x in cases})==9
for row in cases:
 assert row==read(r/(row['case']+'-CASE.json'))
 name=row['case'];d=r/'fixtures'/name
 if 'returncode' in row:
  assert row['wire_closed'] and row['watcher_joined']
  cfg=read(d/'config/CONFIG.json');assert cfg['deadline']==row['deadline']
  owner=read(d/'control/REGISTERED_OWNER.json');assert owner['pid']==row['watch']['pid']
  assert row['watch']['returncode']==row['returncode']
  assert row['watch']['reaped_ns']<=row['deadline']['hard_ns']+500_000_000
  assert row['terminal']['sent_blocks']==row['terminal']['sent_samples']==0
  assert row['terminal']['audio_sha256']==hashlib.sha256(b'').hexdigest()
  assert row['terminal']['address_space']==[256*1024**2]*2 and row['terminal']['stack']==[1024**2]*2 and row['terminal']['affinity']==[2,3]
  if name=='parent-blocked':
   assert row['returncode']==-9 and row['watch']['terminate_sent'] and row['watch']['kill_sent']
   assert row['deadline']['hard_ns']<=row['watch']['kill_ns']<=row['deadline']['hard_ns']+500_000_000
   assert row['closure'] is None and not (d/'closure_reserve/TRANSPORT_CLOSURE.json').exists() and not (d/'source/CHILD_RESULT.json').exists()
   assert row['elapsed_ns']>=1500000000 and 'CHILD_CLOSURE_MISSING' in row['errors']
  else:
   closure=read(d/'closure_reserve/TRANSPORT_CLOSURE.json');assert closure==row['closure'] and closure['wire_closed'] and closure['terminal_sent'] and closure['terminal_acknowledged']
   assert closure['deadline']==row['deadline']
   assert closure['logical_success']==(name=='normal')
   assert row['returncode']==(0 if name=='normal' else 1)
   if name=='owner-quota':assert not closure['source_created'] and not (d/'source/CHILD_OWNER.json').exists()
   else:assert closure['source_close']==dict(fixture=True,stops=1,closes=1,no_hardware=True)
   if name=='result-quota':assert row['terminal']['fault'] is None and closure['publication_failure']['name']=='CHILD_RESULT.json'
  for group,limits in cfg['groups'].items():
   sizes=[p.stat().st_size for p in (d/group).iterdir() if p.name!='.budget.guard']
   assert sum(sizes)<=limits['maximum_bytes'] and len(sizes)<=limits['maximum_files'] and all(n<=limits['maximum_file_bytes'] for n in sizes)
 else:
  assert row['original_accept_stub'] and row['retained_error_method']
  assert row['sent']==(4 if name=='trace-append-reject' else 2)
  assert bool(row['error'])==row['stop_requested']==(name!='trace-normal')
  trace=d/'trace/TRACE.jsonl'
  assert trace.exists()==row['trace_exists'] and (trace.stat().st_size if trace.exists() else 0)==row['trace_bytes']
  if name=='trace-first-reject':assert not trace.exists()
  else:
   rows=[json.loads(line) for line in trace.read_text().splitlines()];assert len(rows)==1
   assert rows[0]['samples']==2 and rows[0]['audio_sha256']==hashlib.sha256(bytes(8)).hexdigest()
 for failure in (d/'failure').glob('transport-failure-*.json'):
  v=read(failure);raw=d/'failure'/v['raw_path'];assert v['raw_retained'] and raw.stat().st_size==v['bytes'] and sha(raw)==v['sha256']
for guard in r.rglob('.budget.guard'):
 assert guard.stat().st_size==0
 with guard.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert out['cases']==9 and out['children']==5 and out['expected_child_failures']==4 and out['source_audio_samples']==0
assert not any(out[k] for k in ['models','capture','GUI','controller','whole_run_integrated','policy_changed'])
assert not list(r.rglob('*.pending')) and not list(r.rglob('*.wav')) and not list(r.rglob('epoch.json'))
assert sha(r/'LIVE_CONFIG_BACKUP.json')==a['live_config_sha256'] and sha(r/'INSTALL_BACKUP.json')==a['install_sha256']
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for p in owners:
 o=read(p);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<4*1024**2
print(json.dumps(dict(status=out['status'],result=out,target_bytes=size,owner_count=len(owners),baseline_unchanged=True,capture_closed=True,aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in dispatch['samples']),default=None))))
''')
    result['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/'field-transport-outputs-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
