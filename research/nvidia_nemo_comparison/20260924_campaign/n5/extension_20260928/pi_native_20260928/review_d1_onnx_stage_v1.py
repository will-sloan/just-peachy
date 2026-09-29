"""Read-only transfer review; README_REVIEW_STAGE_D1_ONNX_V1.md."""
import json
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE


def main():
    x=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import json,hashlib,subprocess,fcntl
from pathlib import Path
r=Path(ROOT);d=r/'d1-onnx-stage-v1'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
docs={n:json.loads((d/n).read_text()) for n in ['ADMISSION.json','OWNER.json','LIVE_ENVELOPE.json','RESULT.json']}
a=docs['ADMISSION.json'];o=docs['OWNER.json'];e=docs['LIVE_ENVELOPE.json'];v=docs['RESULT.json']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==o['boot_id']==a['boot_id']
assert ticks(o['pid'])!=o['start_ticks'] and ticks(1013)==569 and ticks(1130)==607
assert o==e['owner']==v['owner'] and o['admission_sha256']==sha(d/'ADMISSION.json')
assert v['status']=='ASSET_STAGED_NOT_MODEL_QUALIFIED' and v['bytes']==400460515 and not v['models_loaded'] and not v['capture']
assert (d/'D1_fp32.onnx').stat().st_size==v['bytes'] and sha(d/'D1_fp32.onnx')==v['sha256']==a['asset_sha256']
assert sha(d/'stage_d1_onnx_v1.py')==a['script_sha256'] and sha(d/'README_STAGE_D1_ONNX_V1.md')==a['readme_sha256']
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active' and int(e['properties']['MainPID'])==o['pid']
assert e['properties']['RuntimeMaxUSec']=='10min' and e['properties']['TasksMax']=='64' and e['properties']['CPUQuotaPerSecUSec']=='2s'
assert e['affinity']==[2,3] and e['address_space']==[128*1024**2]*2 and e['stack']==[1024**2]*2
assert int(e['properties']['LimitAS'])==128*1024**2 and int(e['properties']['LimitSTACK'])==1024**2
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for p in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in d.rglob('*') if p.is_file());assert size<a['output_max_bytes']
print(json.dumps(dict(docs=docs,review=dict(status='PASS_D1_GRAPH_BYTES_ENVELOPE_AND_CLOSURE_ONLY',graph_sha256=v['sha256'],graph_bytes=v['bytes'],output_bytes=size,actual_live_envelope_verified=True,exact_owner_closed=True,baseline_unchanged=True,capture_closed=True,leases_free=True,model_ran=False,hashes={n:sha(d/n) for n in docs}))))
''')
    out=PRIVATE/'d1-onnx-stage-v1-evidence'
    launch=json.loads((out/'LAUNCH_RESULT.json').read_text());assert launch['exit_code']==0 and launch['bytes_sent']==400460515
    x['review']['natural_exit_code']=0
    for n,v in x['docs'].items():
        with (out/n).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
    with (out/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(x['review'],f,indent=2)
    print(json.dumps(x['review']))


if __name__=='__main__':main()
