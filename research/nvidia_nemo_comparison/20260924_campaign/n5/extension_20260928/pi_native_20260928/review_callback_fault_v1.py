"""Independent import-only mapping reader. See README_CALLBACK_FAULT_V1.md."""
import json
import psutil
from dispatch_geometry_v2 import remote, PRIVATE, REMOTE


def main():
    psutil.Process().cpu_affinity([14])
    run='callback-fault-v1';out=PRIVATE/(run+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    x=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(run)+'\n'+r'''
import json,hashlib,subprocess,fcntl,collections,re
from pathlib import Path
root=Path(ROOT);d=root/RUN
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot==a['boot_id'] and not a['capture'] and not a['models_loaded']
for row in a['files']:assert sha(Path(row['path']))==row['sha256']
owners=[]
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/n).read_text());t=ticks(o['pid']);assert o['boot_id']==boot and t!=o['start_ticks'] and o['admission_sha256']==sha(d/'ADMISSION.json')
 owners.append(dict(owner=o,observed_start_ticks=t,exact_alive=False))
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
assert sha(Path.home()/'JustPeachy/data/live_config.json')=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for lock in [root/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with lock.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
u=dict(l.split('=',1) for l in subprocess.check_output(['systemctl','--user','show','jp-'+RUN,'-p','MainPID','-p','Result','-p','ExecMainStatus'],text=True).splitlines());assert u==dict(MainPID='0',Result='success',ExecMainStatus='0')
r=json.loads((d/'RESULT.json').read_text());assert r['status']=='COLLECTED_NATIVE_CALLBACK_FAULT_DETAILS_ONLY' and not r['capture'] and not r['models_loaded'] and not r['stream_constructed'] and not r['integrated']
assert not r['actual_status_from_failed_trial_recovered']
expected=['normal_samples_and_counters_unchanged','input_overflow','input_underflow','other_status_flags','raw_ring_overflow','oversized_callback','priming_behavior_unchanged','unrelated_exception_not_masked']
assert r['cases']==expected and r['count']==8
assert not list(d.rglob('*.wav')) and not list(d.rglob('*.npy'))
bindings={n:sha(d/n) for n in ['ADMISSION.json','RESULT.json','DISPATCH_RESULT.json','OWNER.json','DISPATCH_OWNER.json']}
print(json.dumps(dict(status='PASS_NATIVE_MODEL_FREE_CALLBACK_FAULT_DETAILS_ONLY',bindings=bindings,owners=owners,unit=u,cases=r['cases'],count=r['count'],peak_rss_bytes=r['peak_rss_bytes'],capture=False,models_loaded=False,integrated=False,callback_timing_or_gap_fix_qualified=False,actual_previous_gap_status_unknown=True,upstream_lost_frames_unknown=True,original_app_config_install_unchanged=True)))
''')
    with (out/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
    print(json.dumps({k:v for k,v in x.items() if k not in ['bindings','owners','new_mapping_bytes']}))


if __name__=='__main__':main()
