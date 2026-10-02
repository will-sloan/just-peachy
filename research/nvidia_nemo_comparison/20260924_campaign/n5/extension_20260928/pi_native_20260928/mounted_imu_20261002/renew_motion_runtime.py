"""Plan or renew a completed batch while retaining the mounted IMU integration; README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--previous-version',type=int,required=True);ap.add_argument('--version',type=int,required=True)
ap.add_argument('--last-receipt',type=Path,required=True);ap.add_argument('--plan',action='store_true')
a=ap.parse_args()
if not 27<=a.previous_version<a.version<=999:raise ValueError('Fresh increasing runtime version required')
B=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928');I=B/'imu-integration-20261002';H=Path(__file__).parent
install=B/('field-runtime-v%d-install'%a.version);preserve=B/('field-runtime-v%d-preservation-motion-to-v%d'%(a.previous_version,a.version))
inspection=I/('operator-inspection-v%d'%a.version)
if a.plan:
 print(json.dumps(dict(action='preserve completed batch; inspect restored baseline; provision fresh motion batch',version=a.version,previous_version=a.previous_version,capsule='runtime-capsule-v3',capsule_sha256='3383fa869e7357cfa7f9ef410be6dcb40972feb40cea7aebee9d71dd526e4d80',outputs=list(map(str,(preserve,inspection,install))),native_contact=False)))
 raise SystemExit(0)
for p in (install,preserve,inspection):
 if p.exists():raise ValueError('Never reuse an existing output: '+str(p))
if not (a.last_receipt/'NATIVE_OWNER.json').is_file():raise ValueError('Exact latest native utility receipt required')
folder=H/'operator-tools-v1';pins=json.loads((folder/'DERIVATION.json').read_bytes())
for phase,name in (('preserve','preserve_runtime_batch_v1.py'),('inspect','inspect_deployment.py'),('install','install_mounted_runtime.py')):
 prep=I/('operator-v%d-%s'%(a.version,phase));prep.mkdir();me=psutil.Process()
 def put(n,r):
  if len(r)>1048576:raise ValueError('Original source ceiling')
  with (prep/n).open('xb') as f:f.write(r);f.flush();os.fsync(f.fileno())
  assert (prep/n).read_bytes()==r
 def save(n,v):put(n,json.dumps(v,sort_keys=True).encode())
 save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
 for n,pin in pins.items():
  r=(folder/n).read_bytes()
  if r!=(folder/(n+'.restore')).read_bytes() or pin!=dict(bytes=len(r),sha256=hashlib.sha256(r).hexdigest()):raise ValueError('Backed operator source changed')
  put(n+'.backup',r);put(n+'.restore',r)
 for n in ('renew_motion_runtime.py','README.md'):
  r=(H/n).read_bytes();put(n+'.backup',r);put(n+'.restore',r)
 now=datetime.now(timezone.utc);save('SCOPE.json',dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),maximum_bytes=16*1024**2,purpose='EXPLICIT_OPERATOR_MOTION_BATCH_RENEWAL'))
 save('SOURCE_CLOSED.json',dict(independent_restore=True,files=pins))
 args=['--private',str(B),'--local',str(B.parents[2]),'--prior-closure',str(B/'NATIVE_CLOSURE_V315.json'),'--scope',str(prep/'SCOPE.json')]
 old=B/('field-runtime-v%d-install'%a.previous_version)
 if phase=='preserve':args+=['--candidate-install',str(old),'--previous-inspection',str(a.last_receipt),'--output',str(preserve)]
 elif phase=='inspect':args+=['--previous-install',str(old),'--previous-preservation',str(preserve),'--previous-inspection',str(preserve),'--output',str(inspection)]
 else:args+=['--previous-install',str(old),'--previous-preservation',str(preserve),'--inspection',str(inspection),'--output',str(install),'--version',str(a.version),'--assets',str(B/'runtime-titanet-v1-install/assets-restore'),'--inputs',str(B/'deployable-runtime-resume-v1/boot-launch-inputs-v1')]
 sys.argv=[name,*args];exec(compile((folder/name).read_bytes(),str(folder/name),'exec'),dict(__name__='__main__',__file__=str(folder/name)))
