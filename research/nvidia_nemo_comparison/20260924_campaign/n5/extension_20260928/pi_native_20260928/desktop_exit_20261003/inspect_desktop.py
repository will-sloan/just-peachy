"""Inspect current prototype/startup without mutation; see README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--label',required=True);a=ap.parse_args()
if not a.label.replace('-','').isalnum():raise ValueError('Unique simple label')
B=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
P=Path('G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928')
D=B/'desktop-exit-20261003';D.mkdir(exist_ok=True)
prep=D/('preparation-'+a.label);prep.mkdir();me=psutil.Process()
def put(n,r):
 with (prep/n).open('xb') as f:f.write(r);f.flush();os.fsync(f.fileno())
 assert (prep/n).read_bytes()==r
def save(n,v):put(n,json.dumps(v,sort_keys=True).encode())
save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
s=(P/'inspect_runtime_session_v10.py').read_text(encoding='utf-8')
s=s.replace("        if now>=datetime(2026,10,2,14,14,20,tzinfo=timezone.utc):raise TimeoutError('User deadline')\n",'')
s=s.replace('Path(__file__).parent','Path('+repr(str(P))+')')
boundary='    from dispatch_b01_stack_v2 import SSH';assert s.count(boundary)==1
s=s.replace(boundary,boundary+"\n    SSH[-1:-1]=['-o','Hostname=192.168.2.57']")
s=s.replace('len(identities)>1024','len(identities)>1088').replace('len(identities)<=1024','len(identities)<=1088')
boundary='    guard()\n    if datetime.now(timezone.utc)+timedelta(seconds=90)';assert s.count(boundary)==1
s=s.replace(boundary,"    paths=list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))+list((a.private/'desktop-exit-20261003').rglob('NATIVE_OWNER.json'))+list(a.private.glob('field-runtime-v*-source-recovery-mounted-v*/NATIVE_OWNER.json'))\n    for path in paths:\n        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v\n    if len(identities)>1088:raise ValueError('Complete prior owner continuation')\n"+boundary)
t=ast.parse(s);node=next(n for n in t.body if isinstance(n,ast.Assign) and any(isinstance(v,ast.Name) and v.id=='NATIVE' for v in n.targets))
native=ast.literal_eval(node.value)
extra="""
value['desktop_startup_files']=[]
paths=set((home/'.config/autostart').glob('*.desktop'))
paths|=set((home/'Desktop').glob('*peachy*.desktop'))
paths|={home/'.config/labwc/autostart',home/'.config/wayfire.ini',home/'.config/lxsession/LXDE-pi/autostart'}
assert len(paths)<=64
for path in sorted(paths):
 if not path.exists():continue
 assert path.is_file() and not path.is_symlink() and path.stat().st_size<=65536
 data=path.read_bytes()
 value['desktop_startup_files'].append(dict(path=str(path),bytes=len(data),sha256=sha(data),text=data.decode()))
"""
assert native.count('raw=json.dumps(value)')==1
native=native.replace('raw=json.dumps(value)',extra+'\nraw=json.dumps(value)')
lines=s.splitlines(True);s=''.join(lines[:node.lineno-1])+'NATIVE='+repr(native)+'\n'+''.join(lines[node.end_lineno:])
raw=s.encode();compile(raw,'<desktop-startup-inspector>','exec')
for n,r in [('SOURCE.py',raw),('runner.py',Path(__file__).read_bytes()),('README.md',Path(__file__).with_name('README.md').read_bytes())]:
 put(n+'.backup',r);put(n+'.restore',r)
now=datetime.now(timezone.utc);save('SCOPE.json',dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),maximum_bytes=16*1024**2))
save('SOURCE_CLOSED.json',dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),independent_restore=True))
sys.path.insert(0,str(P))
sys.argv=['inspect_runtime_session.py','--private',str(B),'--local',str(B.parents[2]),'--prior-closure',str(B/'NATIVE_CLOSURE_V315.json'),'--previous-inspection',str(B/'imu-integration-20261002/shortcuts-v27-v2'),'--scope',str(prep/'SCOPE.json'),'--output',str(D/('inspection-'+a.label)),'--candidate-install',str(B/'field-runtime-v27-install')]
exec(compile(raw,'<desktop-startup-inspector>','exec'),dict(__name__='__main__',__file__=str(P/'inspect_runtime_session_v10.py')))
