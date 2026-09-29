"""Independent model-free receipt/hash reader. See README_ASR_BOUNDED_SHADOW_V2.md."""
import hashlib
import json
import struct
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14]);run='asr-bounded-shadow-v2';out=PRIVATE/(run+'-evidence')
    x=remote('RUN='+repr(run)+'\n'+r'''
import os,json,hashlib,subprocess,fcntl
from pathlib import Path
os.sched_setaffinity(0,{3});r=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928');d=r/RUN
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());assert a['mode']=='model_free' and not a['capture'] and not a['models_loaded']
assert a['cpus']==[2,3] and a['address_space_max_bytes']==768*1024**2
for row in a['files']:assert sha(Path(row['path']))==row['sha256']
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id'];owners=[]
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/n).read_text());t=ticks(o['pid']);assert not(o['boot_id']==boot and t==o['start_ticks'])
 assert o['admission_sha256']==sha(d/'ADMISSION.json');owners.append(dict(owner=o,observed_start_ticks=t,exact_alive=False))
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
assert sha(Path.home()/'JustPeachy/data/live_config.json')=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for lock in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with lock.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
u=dict(l.split('=',1) for l in subprocess.check_output(['systemctl','--user','show','jp-'+RUN,'-p','MainPID','-p','Result','-p','ExecMainStatus'],text=True).splitlines());assert u==dict(MainPID='0',Result='success',ExecMainStatus='0')
assert not list(d.rglob('*.wav')) and not list(d.rglob('*.npy'))
result=json.loads((d/'RESULT.json').read_text());dispatch=json.loads((d/'DISPATCH_RESULT.json').read_text());assert dispatch['exit_code']==0
print(json.dumps(dict(result=result,bindings={n:sha(d/n) for n in ['ADMISSION.json','RESULT.json','DISPATCH_RESULT.json','OWNER.json','DISPATCH_OWNER.json']},owners=owners,unit=u)))
''')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    r=x['result'];assert r['status']=='MODEL_FREE_BOUNDED_SHADOW_COLLECTED_REQUIRES_REVIEW'
    assert not r['capture'] and not r['models_loaded'] and r['actual_skipped_samples']==0
    cases=r['cases'];assert len(cases)==12 and len({c['name'] for c in cases})==12 and all(c['passed'] for c in cases)
    expected={'prior_v1_parity_'+n for n in ['quiet','missing','failed','padded','energy','burst','late']}
    assert expected<={c['name'] for c in cases}
    long=next(c for c in cases if c['name']=='sixty_minute_logical_trace_fixed_collections');s=long['report']
    digest=hashlib.sha256();period=struct.pack('<f',.01)*320*100+bytes(4*320*400)
    for _ in range(360):digest.update(period)
    assert s['ingress_sha256']==s['egress_sha256']==digest.hexdigest()
    assert s['received_samples']==s['completed_samples']==57600000 and sum(s['reason_samples'].values())==57600000
    assert s['actual_skipped_samples']==0 and s['evicted_decisions']==180000-512
    for key,limit in [('maximum_audio_samples',48000),('maximum_pending_entries',256),('maximum_cue_intervals',128),('maximum_energy_intervals',128),('retained_decisions',512),('retained_progress',32)]:assert s[key]<=limit
    assert all(d['actual_action']=='KEEP_ALL_SHADOW' for d in s['recent_decisions'])
    assert not s['model_inference_qualified'] and not s['production_endurance_qualified']
    review=dict(status='PASS_NATIVE_MODEL_FREE_BOUNDED_METADATA_ONLY',bindings=x['bindings'],owners=x['owners'],unit=x['unit'],cases=[{k:v for k,v in c.items() if k not in ['report','sampled_process_peak_rss_bytes']} for c in cases],logical_source_seconds=3600,actual_execution_seconds=r['elapsed_seconds'],long_trace_execution_seconds=long['execution_wall_seconds'],peak_process_rss_bytes=r['peak_rss_bytes'],long_trace_sha256=digest.hexdigest(),bounds={k:s[k] for k in ['maximum_audio_samples','maximum_pending_entries','maximum_cue_intervals','maximum_energy_intervals','retained_decisions','retained_progress']},actual_skipped_samples=0,capture=False,models_loaded=False,integrated=False,real_time_or_endurance_qualified=False,accuracy_scored=False,owner_closure=True)
    for name,data in [('AUDIT_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(data,f,indent=2)
    remote('RUN='+repr(run)+'\nREVIEW='+repr(review)+'\n'+"import json\nfrom pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/RUN/'REVIEW.json'\nwith p.open('x') as f:json.dump(REVIEW,f,indent=2)\nprint(json.dumps({'written':True}))")
    print(json.dumps({k:v for k,v in review.items() if k not in ['bindings','owners','cases']}))


if __name__=='__main__':main()
