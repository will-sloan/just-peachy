"""One bounded desktop-first operation; see README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
E=Path(__file__).parent
B=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
P=Path('G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928')
D=B/'desktop-exit-20261003'
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('phase',choices=['preserve','disable','install']);ap.add_argument('--label',required=True);a=ap.parse_args()
prep=D/('operation-'+a.label);prep.mkdir()
def put(n,r):
    with (prep/n).open('xb') as f:f.write(r);f.flush();os.fsync(f.fileno())
    assert (prep/n).read_bytes()==r
def save(n,v):put(n,json.dumps(v,sort_keys=True).encode())
me=psutil.Process();save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
now=datetime.now(timezone.utc);save('SCOPE.json',dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),maximum_bytes=16*1024**2))
preserved=B/'field-runtime-v27-preservation-desktop-v1'
common=['--private',str(B),'--local',str(B.parents[2]),'--prior-closure',str(B/'NATIVE_CLOSURE_V315.json'),'--scope',str(prep/'SCOPE.json')]
if a.phase=='preserve':
    name='preserve_interrupted.py';s=(E/name).read_text()
    args=common+['--candidate-install',str(B/'field-runtime-v27-install'),'--previous-inspection',str(D/'inspection-initial-v1'),'--output',str(preserved)]
elif a.phase=='disable':
    name='inspect_deployment.py';s=(E/name).read_text()
    node=next(n for n in ast.parse(s).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NATIVE' for t in n.targets))
    native=ast.literal_eval(node.value)
    initial=json.loads((D/'inspection-initial-v1/RESULT.json').read_bytes())
    row=next(r for r in initial['desktop_startup_files'] if r['path']=='/home/peachyprototype/.config/autostart/just-peachy.desktop')
    old=row['text'].encode();assert hashlib.sha256(old).hexdigest()==row['sha256']=='e9314c653bf2247c0c15441276bf092cde585fbbcebc7431abaff33e1923c625'
    new=old.replace(b'X-GNOME-Autostart-enabled=true',b'X-GNOME-Autostart-enabled=false')+b'Hidden=true\n'
    for n,r in [('autostart-original',old),('autostart-manual',new)]:put(n+'.backup',r);put(n+'.restore',r)
    native=native.replace('(resource.RLIMIT_FSIZE,0)','(resource.RLIMIT_FSIZE,65536)')
    block="""
# User-requested one-file startup preference; exact PC backup and independent restore precede this code.
assert boot=='a75acc8d-2b2f-4d04-ba69-d60a54f78bb3'
assert ticks(1007)==478 and ticks(1114)==513
path=home/'.config/autostart/just-peachy.desktop'
before=path.read_bytes();assert before==OLD_STARTUP
assert not path.is_symlink() and path.stat().st_nlink==1
pending=path.with_name('.just-peachy.desktop.manual-start-20261003.pending')
with pending.open('xb') as f:
 assert f.write(NEW_STARTUP)==len(NEW_STARTUP);f.flush();os.fsync(f.fileno())
os.chmod(pending,path.stat().st_mode & 0o777)
assert pending.read_bytes()==NEW_STARTUP and path.read_bytes()==before
os.replace(pending,path)
fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
try:os.fsync(fd)
finally:os.close(fd)
assert path.read_bytes()==NEW_STARTUP
value['desktop_startup_change']=dict(path=str(path),old_sha256=sha(before),new_sha256=sha(NEW_STARTUP),manual_only=True)
for r in value['startup_files']:
 if r['path']==str(path):r.update(bytes=len(NEW_STARTUP),sha256=sha(NEW_STARTUP),base64=base64.b64encode(NEW_STARTUP).decode())
value['native_writes']='USER_REQUESTED_MANUAL_LOGIN_STARTUP_ONLY'
"""
    native='OLD_STARTUP='+repr(old)+'\nNEW_STARTUP='+repr(new)+'\n'+native
    assert native.count('raw=json.dumps(value)')==1
    native=native.replace('raw=json.dumps(value)',block+'\nraw=json.dumps(value)')
    compile(native,'<manual-startup>','exec')
    lines=s.splitlines(True);s=''.join(lines[:node.lineno-1])+'NATIVE='+repr(native)+'\n'+''.join(lines[node.end_lineno:])
    s=s.replace("native_writes=False,capture=False,precheck_sha256=","native_writes='ONE_BACKED_AUTOSTART_FILE',capture=False,precheck_sha256=")
    args=common+['--previous-install',str(B/'field-runtime-v27-install'),'--previous-preservation',str(preserved),'--previous-inspection',str(preserved),'--output',str(D/'manual-startup-v1')]
else:
    name='install_mounted_runtime.py';s=(E/name).read_text()
    args=common+['--assets',str(B/'runtime-titanet-v1-install/assets-restore'),'--inspection',str(D/'manual-startup-v1'),'--inputs',str(B/'deployable-runtime-resume-v1/boot-launch-inputs-v1'),'--previous-install',str(B/'field-runtime-v27-install'),'--previous-preservation',str(preserved),'--version','28','--output',str(B/'field-runtime-v28-install')]
# All new helper identities, including this task's earlier native utilities, remain explicit.
needle="    for path in (a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'):"
if needle in s:s=s.replace(needle,"    for path in list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))+list((a.private/'desktop-exit-20261003').rglob('NATIVE_OWNER.json')):")
raw=s.encode();compile(raw,name,'exec')
for n,r in [('source.py',raw),('run.py',Path(__file__).read_bytes()),('README.md',(E/'README.md').read_bytes()),('bind_previous_mounted.py',(E/'bind_previous_mounted.py').read_bytes())]:put(n+'.backup',r);put(n+'.restore',r)
save('SOURCE_CLOSED.json',dict(utc=datetime.now(timezone.utc).isoformat(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
sys.path.insert(0,str(P));sys.path.insert(0,str(E));sys.argv=[name]+args
exec(compile(raw,name,'exec'),dict(__name__='__main__',__file__=str(E/name)))
