"""Independent staged-asset reader; README_REVIEW_A2_ASSET_V2.md."""
import json,psutil
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE

def main():
    psutil.Process().cpu_affinity([14]);run='a2-asset-stage-v1';out=PRIVATE/(run+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    x=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(run)+'\n'+r"""
import hashlib,json,subprocess,fcntl
from pathlib import Path
r=Path(ROOT);d=r/RUN
# Read source/asset/admission independently; no model import/load.
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());o=json.loads((d/'OWNER.json').read_text());result=json.loads((d/'RESULT.json').read_text())
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot==a['boot_id']==o['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert o['admission_sha256']==sha(d/'ADMISSION.json')
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
assert sha(d/'stage_a2_asset_v1.py')==a['script_sha256'] and sha(d/'README_STAGE_A2_ASSET_V1.md')==a['readme_sha256']
assert a['address_space_max_bytes']==128*1024**2 and a['stack_bytes']==1024**2 and a['runtime_seconds']==600 and a['stop_timeout_seconds']==10
assert (d/'A2.gguf').stat().st_size==a['asset_bytes']==699872960
assert sha(d/'A2.gguf')==a['asset_sha256']=='d9a01898d2a611c8764e23a1c2f45e70bbd5a425dc4de93692ac951dd603812d'
assert result['status']=='ASSET_STAGED_NOT_MODEL_QUALIFIED' and not result['capture'] and not result['models_loaded']
assert not (d/'A2.gguf.partial').exists() and not (d/'FAILURE.json').exists()
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for path in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
keys=['LoadState','MainPID','Result','ExecMainStatus','LimitAS','LimitSTACK','TasksMax','CPUQuotaPerSecUSec','RuntimeMaxUSec','TimeoutStopUSec']
cmd=['systemctl','--user','show','jp-'+RUN]
for k in keys:cmd+=['-p',k]
u=dict(line.split('=',1) for line in subprocess.check_output(cmd,text=True).splitlines())
assert u['MainPID']=='0' and u['Result']=='success' and u['ExecMainStatus']=='0'
# Transient units can be garbage-collected after the natural exit. Default
# values of a not-found unit must never count as measured resource settings.
assert u['LoadState']=='not-found', u
unit_envelope_verified=False
used=sum(f.stat().st_size for f in d.rglob('*') if f.is_file());assert used<=a['output_max_bytes']
print(json.dumps(dict(status='PASS_PINNED_A2_ASSET_AND_OWNER_CLOSURE_ONLY',unit_envelope_verified=unit_envelope_verified,unit_resource_receipt_missing=True,source_limit_assertions_completed=True,asset_bytes=a['asset_bytes'],asset_sha256=a['asset_sha256'],logical_run_bytes=used,output_max_bytes=a['output_max_bytes'],models_loaded=False,capture=False,original_app_unchanged=True,exact_owner_closed=True,leases_free=True,unit=u,bindings={n:sha(d/n) for n in ['ADMISSION.json','RESULT.json','OWNER.json']})))
""")
    with (out/'REVIEW_V2.json').open('x') as f:json.dump(x,f,indent=2)
    print(json.dumps({k:v for k,v in x.items() if k not in ['bindings','unit']}))
if __name__=='__main__':main()
