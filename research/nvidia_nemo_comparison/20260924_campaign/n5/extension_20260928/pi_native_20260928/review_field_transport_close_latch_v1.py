"""Independent compact binding review; README_FIELD_TRANSPORT_CLOSE_LATCH_V1.md."""
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
r=Path.home()/'JustPeachy/research/nemotron-20260928/field-transport-close-latch-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');out=read(r/'RESULT.json');dispatch=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
assert out['status']=='PASS_REPEATED_CLOSE_FAILURE_PERSISTENCE_ONLY' and dispatch['exit_code']==0
assert not dispatch['log_overflow'] and not dispatch['memory_guard']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
for path,h in a['retained_adapter_files'].items():assert sha(path)==h
cases=read(r/'CLOSE_LATCH_CASES.json')
assert len(cases)==9 and len({x['case'] for x in cases})==9
prior=Path(a['retained_run'])
for row in cases[:4]:
 saved=read(prior/(row['case']+'-CASE.json'))
 expected='CHILD_CLOSURE_MISSING' if row['case']=='parent-blocked' else 'CHILD_OUTPUT_OR_FINALIZATION_FAILED'
 assert row['outcome']==dict(code=expected,detail=saved['closure'] or {})
 assert row['calls']==3 and row['physical_close_calls']==row['watcher_join_calls']==1
 assert sha(prior/(row['case']+'-CASE.json'))==row['retained_case_sha256']
assert cases[4]['case']=='concurrent-failed-close' and cases[4]['calls']==2 and cases[4]['attempts']==1 and cases[4]['threads_joined']
assert cases[5]['outcome']['code']=='CLOSE_FINALIZATION_EXCEPTION' and cases[5]['attempts']==1
assert cases[6]['outcome']['code']=='CLOSE_FAILURE_DETAIL_UNSERIALIZABLE' and cases[6]['attempts']==1
assert cases[7]['interrupt_propagated'] and cases[7]['attempts']==1
assert cases[8]['physical_attempts']==0 and cases[8]['outcome']['code']=='CLOSE_OUTCOME_UNAVAILABLE'
assert out['cases']==9 and out['saved_failure_cases']==4 and out['child_processes']==out['transport_constructors']==out['source_audio_samples']==0
assert not any(out[k] for k in ['models','capture','GUI','controller','whole_run_integrated','policy_changed','retained_evidence_modified'])
assert not list(r.rglob('*.pending')) and not list(r.rglob('*.wav')) and not list(r.rglob('epoch.json'))
for sample in dispatch['samples']:
 ids=[tuple(i) for i in sample.get('aggregate_unique_identities',[])]
 assert len(ids)==len(set(ids))
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
    with (PRIVATE/'field-transport-close-latch-v1-evidence/REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='result'}))

if __name__=='__main__':main()
