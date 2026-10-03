"""Check one fresh shortcut launch and acknowledged normal Exit; README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
E=Path(__file__).parent
B=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928');D=B/'desktop-exit-20261003'
P=Path('G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928')
prep=D/'reopen-preparation-v2';prep.mkdir();me=psutil.Process()
def put(n,r):
 with (prep/n).open('xb') as f:f.write(r);f.flush();os.fsync(f.fileno())
 assert (prep/n).read_bytes()==r
def save(n,v):put(n,json.dumps(v,sort_keys=True).encode())
save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
s=(P/'inspect_runtime_session_v10.py').read_text()
s=s.replace('Path(__file__).parent','Path('+repr(str(P))+')')
s=s.replace("        if now>=datetime(2026,10,2,14,14,20,tzinfo=timezone.utc):raise TimeoutError('User deadline')\n",'')
boundary='    from dispatch_b01_stack_v2 import SSH';assert s.count(boundary)==1
s=s.replace(boundary,boundary+"\n    SSH[-1:-1]=['-o','Hostname=192.168.2.57']")
s=s.replace('len(identities)>1024','len(identities)>1088').replace('len(identities)<=1024','len(identities)<=1088')
boundary='    guard()\n    if datetime.now(timezone.utc)+timedelta(seconds=90)';assert s.count(boundary)==1
s=s.replace(boundary,"    paths=list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))+list((a.private/'desktop-exit-20261003').rglob('NATIVE_OWNER.json'))+list(a.private.glob('field-runtime-v*-source-recovery-mounted-v*/NATIVE_OWNER.json'))\n    for path in paths:\n        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v\n    if len(identities)>1088:raise ValueError('Bounded complete owner continuation')\n"+boundary)
node=next(n for n in ast.parse(s).body if isinstance(n,ast.Assign) and any(isinstance(v,ast.Name) and v.id=='NATIVE' for v in n.targets));n=ast.literal_eval(node.value)
fragment=(E/'native_smoke.py').read_text()
fragment=fragment.replace("assert RID=='field-runtime-v28' and len(alive_candidate)==1 and not current_operations","assert RID=='field-runtime-v28' and not alive_candidate and not current_operations\nprofiles=root/(RID+'-profiles')\nmanager=identity(strict((root/RID/'launches/launch-01/OWNER.json').read_bytes())['owner'])\nassert not(manager['boot_id']==boot and ticks(manager['pid'])==manager['start_ticks'])\nold_exit=strict((root/RID/'launches/launch-01/EXIT.json').read_bytes())\nassert old_exit['owner']==manager and old_exit['status']=='IDLE_CAPTURE_OFF'")
fragment=fragment.replace("control.tk.call('send','-async',app,(buttons[0][0],'invoke'))","control.tk.call('send',app,(buttons[0][0],'invoke'))")
fragment=fragment.replace(' first_exit=close_idle(manager)'," first_exit=dict(owner=manager,exact_owner_dead=True,exit=old_exit,verification='Fresh inspection after previous asynchronous observer timed out')")
fragment+="\nvalue['desktop_exit']=smoke_result\nvalue['status']='DESKTOP_FIRST_EXIT_REOPEN_CLOSED'\nvalue['native_writes']='ONE_MANUAL_SHORTCUT_START_AND_NORMAL_EXIT'\n"
assert n.count('raw=json.dumps(value)')==1;n=n.replace('raw=json.dumps(value)',fragment+'\nraw=json.dumps(value)')
compile(n,'<acknowledged-shortcut-reopen>','exec')
lines=s.splitlines(True);s=''.join(lines[:node.lineno-1])+'NATIVE='+repr(n)+'\n'+''.join(lines[node.end_lineno:])
s=s.replace('native_writes=False,capture=False,precheck_sha256=',"native_writes='ONE_MANUAL_SHORTCUT_START_AND_NORMAL_EXIT',capture=False,precheck_sha256=")
raw=s.encode();compile(raw,'<desktop-reopen>','exec')
for n,r in [('source.py',raw),('check_reopen.py',Path(__file__).read_bytes()),('README.md',(E/'README.md').read_bytes())]:put(n+'.backup',r);put(n+'.restore',r)
now=datetime.now(timezone.utc);save('SCOPE.json',dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),maximum_bytes=16*1024**2))
save('SOURCE_CLOSED.json',dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),utc=now.isoformat()))
sys.path.insert(0,str(P));sys.argv=['check_reopen.py','--private',str(B),'--local',str(B.parents[2]),'--prior-closure',str(B/'NATIVE_CLOSURE_V315.json'),'--previous-inspection',str(D/'inspection-after-exit-v1'),'--scope',str(prep/'SCOPE.json'),'--candidate-install',str(B/'field-runtime-v28-install'),'--output',str(D/'reopen-v2')]
exec(compile(raw,'<desktop-reopen>','exec'),dict(__name__='__main__',__file__=str(P/'inspect_runtime_session_v10.py')))
