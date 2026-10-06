"""Freeze first-Start diagnostic inputs. README_FIRST_START_REPAIR.md."""
import ctypes,hashlib,json,os,shutil,time,uuid
from pathlib import Path
def main():
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p;h=k.GetCurrentProcess()
 k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
 if not k.SetProcessAffinityMask(h,16384):raise ctypes.WinError(ctypes.get_last_error())
 t=[ctypes.c_ulonglong() for _ in range(4)];k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
 if not k.GetProcessTimes(h,*(ctypes.byref(x) for x in t)):raise ctypes.WinError(ctypes.get_last_error())
 out=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation')/('first-start-inspect-'+uuid.uuid4().hex);out.mkdir()
 def put(name,raw):
  with (out/name).open('xb') as f:
   if f.write(raw)!=len(raw):raise OSError('Short freeze write')
   f.flush();os.fsync(f.fileno())
  if (out/name).read_bytes()!=raw:raise OSError('Independent freeze differs')
 owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,creation_filetime=t[0].value,create_time=(t[0].value-116444736000000000)/10000000)
 put('REGISTERED_OWNER.json',json.dumps(owner,sort_keys=True).encode())
 for drive,gib in (('C:/',50),('G:/',75)):
  if shutil.disk_usage(drive).free<gib*1024**3+2*1024**2:raise OSError('Host floor')
 put('HOST_SCOPE.json',json.dumps(dict(maximum_output_bytes=2097152,maximum_seconds=30,native_action=False,issued_unix=time.time())).encode())
 pins={};used=0;here=Path(__file__).resolve().parent
 for name in ('prepare_first_start_inspection.py','inspect_first_start_failure.py','README_FIRST_START_REPAIR.md','host_first_start_diagnostics.py','normal_current_gui_exit.py','host_current_gui_exit.py'):
  raw=(here/name).read_bytes();used+=3*len(raw)
  if len(raw)>65536 or used>2097152:raise ValueError('Finite freeze')
  for suffix in ('','.backup','.restore'):put(name+suffix,raw)
  if name.endswith('.py'):compile(raw,name,'exec')
  pins[name]=hashlib.sha256(raw).hexdigest()
 put('SOURCE_CLOSED.json',json.dumps(dict(pins=pins,independent_restores=True,closed_unix=time.time())).encode())
 payload=dict(package_manifest_sha256='f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0')
 import sys
 if sys.argv[1:]==['--normal-exit']:
  result=json.loads(Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/operation-first-start-diagnostics-02/dispatch/RESULT.json').read_bytes())
  rows=result['current_project_processes'];inside=[r for r in rows if ' --inside ' in r['cmdline']]
  outer=[r for r in rows if ' --inside ' not in r['cmdline']]
  if len(rows)!=2 or len(inside)!=1 or len(outer)!=1:raise ValueError('Exact inspected idleGUIpair')
  inner=inside[0];cmd=inner['cmdline'].split();owner={k:inner[k] for k in ('boot_id','pid','start_ticks')}
  payload.update(owner=owner,supervisor={k:outer[0][k] for k in owner},unit=cmd[cmd.index('--unit')+1],unit_ownership=cmd[cmd.index('--inside')+1]+'/UNIT_OWNERSHIP.json')
 put('PAYLOAD.json',json.dumps(payload).encode())
 print(str(out))
if __name__=='__main__':main()

