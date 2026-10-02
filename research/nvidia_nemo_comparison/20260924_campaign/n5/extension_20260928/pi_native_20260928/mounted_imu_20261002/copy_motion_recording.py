"""Copy the closed original or its independent local backup without deletion; README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,hashlib,json,os,sys
from pathlib import Path
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root-kind',choices=['original','local'],required=True);a=ap.parse_args()
B=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928');I=B/'imu-integration-20261002'
P=Path('G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928')
prep=I/('offload-v27-'+a.root_kind+'-preparation');prep.mkdir();me=psutil.Process()
def put(n,r):
 with (prep/n).open('xb') as f:f.write(r);f.flush();os.fsync(f.fileno())
 assert (prep/n).read_bytes()==r
put('REGISTERED_OWNER.json',json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode())
s=(P/'export_runtime_recording_v4.py').read_text(encoding='utf-8')
s=s.replace('Path(__file__).parent','Path('+repr(str(P))+')')
before='    from dispatch_b01_stack_v2 import SSH';assert s.count(before)==1;s=s.replace(before,before+"\n    SSH[-1:-1]=['-o','Hostname=192.168.2.57']")
s=s.replace('len(identities)>1024','len(identities)>1088').replace('len(identities)<=1024','len(identities)<=1088')
boundary='    guard()\n    if datetime.now(timezone.utc)+timedelta(seconds=90)'
assert s.count(boundary)==1
s=s.replace(boundary,"    paths=list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))+list(a.private.glob('field-runtime-v*-source-recovery-mounted-v*/NATIVE_OWNER.json'))\n    for path in paths:\n        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v\n    if len(identities)>1088:raise ValueError('Bounded complete owner continuation')\n"+boundary)
raw=s.encode();compile(raw,'<complete-mounted-recording-copy>','exec')
for n,r in [('SOURCE.py',raw),('runner.py',Path(__file__).read_bytes()),('README.md',Path(__file__).with_name('README.md').read_bytes())]:
 put(n+'.backup',r);put(n+'.restore',r)
put('SOURCE_CLOSED.json',json.dumps(dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),independent_restore=True)).encode())
previous=I/('integrated-v27-v1' if a.root_kind=='original' else 'offload-v27-original')
sys.path.insert(0,str(P));sys.argv=['export_runtime_recording.py','--private',str(B),'--local',str(B.parents[2]),'--prior-closure',str(B/'NATIVE_CLOSURE_V315.json'),'--previous-inspection',str(previous),'--candidate-install',str(B/'field-runtime-v27-install'),'--active-install',str(B/'field-runtime-v27-install'),'--slot','recording-01','--root-kind',a.root_kind,'--output',str(I/('offload-v27-'+a.root_kind))]
exec(compile(raw,'<complete-mounted-recording-copy>','exec'),dict(__name__='__main__',__file__=str(P/'export_runtime_recording_v4.py')))
