"""Review the preview dispatch lease/envelope. See README_B05_PREVIEW_GUARD_REVIEW_V1.md."""
import json
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    out=PRIVATE/'b05-preview-guard-v1-evidence'
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    x=remote(r'''
import json,hashlib,fcntl,subprocess,os
from pathlib import Path
os.sched_setaffinity(0,{3});d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b05-preview-guard-v1')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
names=['DISPATCH_OWNER.json','PROBE_OWNER.json','DISPATCH_RESULT.json','PROBE_RESULT.json']
docs={n:json.loads((d/n).read_text()) for n in names}
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for name in names[:2]:
 o=docs[name];p=Path('/proc',str(o['pid']),'stat')
 ticks=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
 assert not(o['boot_id']==boot and ticks==o['start_ticks'])
assert docs['DISPATCH_OWNER.json']['admission_sha256']==sha(d/'ADMISSION.json')
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
with (d.parent/'B05_PREVIEW_DISPATCH.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not list((d/'data/sessions').glob('*'))
print(json.dumps(dict(admission=a,documents=docs,owners_closed=True,lease_released=True,bindings={n:sha(d/n) for n in names+['ADMISSION.json']})))
''')
    a=x['admission'];d=x['documents'];dispatch=d['DISPATCH_RESULT.json'];probe=d['PROBE_RESULT.json']
    assert a['ui_mode']=='guard_probe' and a['address_space_max_bytes']==768*1024**2
    assert dispatch['status']=='SERVICE_CLOSED_REQUIRES_REVIEW' and dispatch['exit_code']==0
    assert dispatch['simultaneous_dispatch_rejected'] and dispatch['lock_held_through_service']
    assert dispatch['owner']==d['DISPATCH_OWNER.json'] and probe['owner']==d['PROBE_OWNER.json']
    assert probe['status']=='PASS_SERVICE_ENVELOPE'
    assert probe['cpu_affinity']==[2,3] and probe['address_space']==[768*1024**2]*2
    assert probe['stack']==[1048576]*2 and probe['quota_ratio']==2
    review=dict(status='PASS_PREVIEW_DISPATCH_LEASE_AND_ENVELOPE_ONLY',bindings=x['bindings'],
                competing_dispatch_rejected=True,dispatch_and_service_owners_closed=True,
                lease_released=True,natural_service_exit=True,cpu_affinity=probe['cpu_affinity'],
                cpu_quota=2,address_space_bytes=768*1024**2,stack_bytes=1048576,
                model_inference=False,GUI=False,capture=False,stage_acceptance=False)
    for name,doc in [('AUDIT_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as stream:json.dump(doc,stream,indent=2)
    remote("from pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b05-preview-guard-v1/REVIEW.json')\nwith p.open('x') as f:f.write("+repr(json.dumps(review,indent=2))+")\nprint('{}')")
    print(json.dumps({k:v for k,v in review.items() if k!='bindings'},indent=2))


if __name__=='__main__':main()
