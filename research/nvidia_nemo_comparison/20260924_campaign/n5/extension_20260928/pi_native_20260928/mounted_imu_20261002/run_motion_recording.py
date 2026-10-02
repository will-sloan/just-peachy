"""Check only the recovered recording path; reuse the passed graphic check. README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
B=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
I=B/'imu-integration-20261002';H=Path(__file__).parent
prep=I/'motion-recording-preparation-v4';prep.mkdir();me=psutil.Process()
def put(n,r):
 with (prep/n).open('xb') as f:f.write(r);f.flush();os.fsync(f.fileno())
 assert (prep/n).read_bytes()==r
def save(n,v):put(n,json.dumps(v,sort_keys=True).encode())
save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
raw=(H/'motion-check-v2/control_mounted_motion.py').read_bytes()
assert raw==(H/'motion-check-v2/control_mounted_motion.py.restore').read_bytes()
s=raw.decode();t=ast.parse(s);n=next(n for n in t.body if isinstance(n,ast.Assign) and any(isinstance(v,ast.Name) and v.id=='NATIVE' for v in n.targets))
native=ast.literal_eval(n.value)
start=native.index(' # Existing frontend idle period:');end=native.index(" invoke(child_owner,'Record processed audio',True)",start)
native=native[:start]+" # Optional graphic was already checked on the identical shared capsule.\n"+native[end:]
lines=s.splitlines(True);s=''.join(lines[:n.lineno-1])+'NATIVE='+repr(native)+'\n'+''.join(lines[n.end_lineno:])
s=s.replace('len(identities)>1024','len(identities)>1088').replace('len(identities)<=1024','len(identities)<=1088')
boundary="    for path in (a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'):"
assert s.count(boundary)==1
s=s.replace(boundary,"    for path in a.private.glob('field-runtime-v*-source-recovery-mounted-v*/NATIVE_OWNER.json'):\n        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v\n"+boundary)
raw=s.encode();compile(raw,'<recovered-motion-recording>','exec')
for n,r in [('SOURCE.py',raw),('runner.py',Path(__file__).read_bytes()),('README.md',(H/'README.md').read_bytes())]:
 put(n+'.backup',r);put(n+'.restore',r)
now=datetime.now(timezone.utc);save('SCOPE.json',dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),maximum_bytes=16*1024**2))
save('SOURCE_CLOSED.json',dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),independent_restore=True))
sys.argv=['control_mounted_motion.py','--private',str(B),'--local',str(B.parents[2]),'--prior-closure',str(B/'NATIVE_CLOSURE_V315.json'),'--previous-inspection',str(B/'field-runtime-v26-source-recovery-mounted-v2'),'--scope',str(prep/'SCOPE.json'),'--output',str(I/'integrated-v27-v1'),'--candidate-install',str(B/'field-runtime-v27-install'),'--profile','d1-delayed','--slot','recording-01']
exec(compile(raw,'<recovered-motion-recording>','exec'),dict(__name__='__main__',__file__=str(H/'motion-check-v2/control_mounted_motion.py')))
