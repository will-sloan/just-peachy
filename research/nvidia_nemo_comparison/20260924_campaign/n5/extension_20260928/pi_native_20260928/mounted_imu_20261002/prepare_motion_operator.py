"""Prepare reusable operator tools that retain the motion capsule; README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import json,hashlib,os
from pathlib import Path
H=Path(__file__).parent;out=H/'operator-tools-v1';out.mkdir();me=psutil.Process()
(out/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
P=Path('G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928')
def put(n,s):
 r=s.encode();compile(r,n,'exec')
 for suffix in ('','.restore'):
  with (out/(n+suffix)).open('xb') as f:f.write(r);f.flush();os.fsync(f.fileno())
 return dict(bytes=len(r),sha256=hashlib.sha256(r).hexdigest())
pins={}
extra="    paths=list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))+list(a.private.glob('field-runtime-v*-source-recovery-mounted-v*/NATIVE_OWNER.json'))\n    for path in paths:\n        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v\n    if len(identities)>1088:raise ValueError('Bounded complete owner continuation')\n"
for name in ('preserve_runtime_batch_v1.py','export_runtime_recording_v4.py'):
 s=(P/name).read_text(encoding='utf-8')
 s=s.replace('Path(__file__).parent.parent','Path('+repr(str(P.parent))+')').replace('Path(__file__).parent','Path('+repr(str(P))+')')
 a="    save('REGISTERED_OWNER.json',owner)";assert s.count(a)==1;s=s.replace(a,a+'\n    sys.path.insert(0,'+repr(str(P))+')')
 a='    from dispatch_b01_stack_v2 import SSH';assert s.count(a)==1;s=s.replace(a,a+"\n    SSH[-1:-1]=['-o','Hostname=192.168.2.57']")
 a='    guard()\n    if datetime.now(timezone.utc)+timedelta(seconds=90)';assert s.count(a)==1;s=s.replace(a,extra+a)
 s=s.replace('len(identities)>1024','len(identities)>1088').replace('len(identities)<=1024','len(identities)<=1088')
 pins[name]=put(name,s)
for name in ('bind_previous_mounted.py','inspect_deployment.py','install_mounted_runtime.py'):
 s=(H/'deployment-tools-v5'/name).read_text(encoding='utf-8')
 pins[name]=put(name,s)
(out/'DERIVATION.json').write_text(json.dumps(pins,sort_keys=True))
print(json.dumps(pins))
