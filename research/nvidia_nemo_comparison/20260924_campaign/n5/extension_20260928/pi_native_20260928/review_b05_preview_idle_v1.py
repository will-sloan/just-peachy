"""Read the bounded preview idle-loop evidence. See README_B05_PREVIEW_IDLE_REVIEW_V1.md."""
import hashlib
import json
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    out = PRIVATE/'b05-preview-idle-v1-evidence'
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code'] == 0
    x = remote(r'''
import os,json,hashlib,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3})
d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b05-preview-idle-v1')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
o=json.loads((d/'OWNER.json').read_text());r=json.loads((d/'RESULT.json').read_text())
assert o==r['owner'] and o['admission_sha256']==sha(d/'ADMISSION.json')
p=Path('/proc',str(o['pid']),'stat')
ticks=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
assert not(o['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and ticks==o['start_ticks'])
units=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True)
assert not units.strip()
assert not list((d/'data/sessions').glob('*'))
assert not list((d/'data/conversations').glob('*'))
print(json.dumps(dict(result=r,admission=a,final=json.loads((d/'FINAL_SNAPSHOT.json').read_text()),
 bindings={n:sha(d/n) for n in ['ADMISSION.json','RESULT.json','OWNER.json','FINAL_SNAPSHOT.json']},owner_closed=True)))
''')
    r=x['result'];a=x['admission'];f=x['final']
    assert a['ui_mode']=='withdrawn_idle' and a['address_space_max_bytes']==768*1024**2
    assert r['status']=='USER_PREVIEW_CLOSED_REQUIRES_REVIEW'
    assert r['preview_starts']==r['row_count']==0
    assert r['controller_closed'] and r['Tk_destroyed'] and not r['callback_errors']
    assert not r['visible_user_requested'] and not r['microphone_opened']
    assert r['final_state']=='CLOSED' and f['state']=='CLOSED' and not f['error']
    assert f['settings'].get('microphone_preapproved') is not True
    assert f['settings'].get('auto_start_listening') is not True
    assert 145 <= r['idle_loop_elapsed_seconds'] < 170
    assert r['idle_probe_samples'] >= 280
    assert r['startup_stack_rlimit_bytes']==[1048576,1048576]
    assert r['native_default_thread_stack_bytes']==1048576
    review=dict(status='PASS_B05_WITHDRAWN_IDLE_TIMER_ONLY',bindings=x['bindings'],
                idle_loop_elapsed_seconds=r['idle_loop_elapsed_seconds'],idle_probes=r['idle_probe_samples'],
                peak_rss_bytes=r['peak_rss_bytes'],starts=0,session_archives=0,model_inference=False,
                root_withdrawn=True,natural_process_exit=True,owner_closed=True,controller_Tk_closed=True,
                physical_layout_qualified=False,accuracy_scored=False,stage_acceptance=False)
    for name,doc in [('AUDIT_INPUTS.json',x),('RESULT.json',r),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as stream:json.dump(doc,stream,indent=2)
    remote("from pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b05-preview-idle-v1/REVIEW.json')\nwith p.open('x') as f:f.write("+repr(json.dumps(review,indent=2))+")\nprint('{}')")
    print(json.dumps({k:v for k,v in review.items() if k!='bindings'},indent=2))


if __name__=='__main__':main()
