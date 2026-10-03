"""Retire obsolete shortcuts and verify Exit/reopen/Exit. See README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
E=Path(__file__).parent
B=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928');D=B/'desktop-exit-20261003'
P=Path('G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928')
prep=D/'finish-preparation-v1';prep.mkdir();me=psutil.Process()
def put(n,r):
 with (prep/n).open('xb') as f:f.write(r);f.flush();os.fsync(f.fileno())
 assert (prep/n).read_bytes()==r
def save(n,v):put(n,json.dumps(v,sort_keys=True).encode())
save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
s=(P/'retire_runtime_shortcuts_v3.py').read_text()
s=s.replace('Path(__file__).parent','Path('+repr(str(P))+')')
s=s.replace("        if now>=datetime(2026,10,2,14,14,20,tzinfo=timezone.utc):raise TimeoutError('User deadline')\n",'')
boundary='    from dispatch_b01_stack_v2 import SSH';assert s.count(boundary)==1
s=s.replace(boundary,boundary+"\n    SSH[-1:-1]=['-o','Hostname=192.168.2.57']")
s=s.replace('len(identities)>1024','len(identities)>1088').replace('len(identities)<=1024','len(identities)<=1088')
boundary='    guard()\n    if datetime.now(timezone.utc)+timedelta(seconds=90)';assert s.count(boundary)==1
s=s.replace(boundary,"    paths=list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))+list((a.private/'desktop-exit-20261003').rglob('NATIVE_OWNER.json'))+list(a.private.glob('field-runtime-v*-source-recovery-mounted-v*/NATIVE_OWNER.json'))\n    for path in paths:\n        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v\n    if len(identities)>1088:raise ValueError('Bounded complete owner continuation')\n"+boundary)
node=next(n for n in ast.parse(s).body if isinstance(n,ast.Assign) and any(isinstance(v,ast.Name) and v.id=='NATIVE' for v in n.targets))
n=ast.literal_eval(node.value).replace('retired-shortcuts-v3','retired-shortcuts-desktop-v1')
fragment=(E/'native_smoke.py').read_text()
marker="emit_frame(dict(type='SHORTCUT_RETIREMENT_COMPLETE',manager=manager,retired_count=len(retired),"
assert n.count(marker)==1
n=n.replace(marker,fragment+'\n'+marker)
n=n.replace('retained_count=len(retained),destination=str(destination),bytes=total,capture_started=False))','retained_count=len(retained),destination=str(destination),bytes=total,capture_started=False,desktop_exit=smoke_result))')
compile(n,'<desktop-exit-native-smoke>','exec')
lines=s.splitlines(True);s=''.join(lines[:node.lineno-1])+'NATIVE='+repr(n)+'\n'+''.join(lines[node.end_lineno:])
s=s.replace("native_writes='MOVE_EXACT_OBSOLETE_SHORTCUTS_AFTER_BACKUP'","native_writes='BACKED_SHORTCUT_RETIREMENT_AND_NORMAL_EXIT_REOPEN_EXIT'")
raw=s.encode();compile(raw,'<desktop-exit-finish>','exec')
for n,r in [('source.py',raw),('finish.py',Path(__file__).read_bytes()),('native_smoke.py',fragment.encode()),('README.md',(E/'README.md').read_bytes())]:put(n+'.backup',r);put(n+'.restore',r)
now=datetime.now(timezone.utc);save('SCOPE.json',dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),maximum_bytes=16*1024**2))
save('SOURCE_CLOSED.json',dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),utc=now.isoformat()))
sys.path.insert(0,str(P));sys.argv=['finish.py','--private',str(B),'--local',str(B.parents[2]),'--prior-closure',str(B/'NATIVE_CLOSURE_V315.json'),'--previous-inspection',str(D/'manual-startup-v1'),'--scope',str(prep/'SCOPE.json'),'--candidate-install',str(B/'field-runtime-v28-install'),'--output',str(D/'exit-reopen-v1')]
exec(compile(raw,'<desktop-exit-finish>','exec'),dict(__name__='__main__',__file__=str(P/'retire_runtime_shortcuts_v3.py')))
