"""Private immutable status-reader fixtures; README_S6C_SERIAL_LONG_STATUS_V1.md."""
import argparse,ctypes,hashlib,json,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def binding(p):
 p=Path(p).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(p,d):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d),encoding='utf-8');return binding(p)
def run(output):
 output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);checks=[]
 script=HERE/'s6c_serial_long_status_v1.ps1'
 def ck(n,v):
  if not v:raise AssertionError(n)
  checks.append(n)
 with tempfile.TemporaryDirectory(prefix='s6c_long_status_') as temp:
  root=Path(temp).resolve();queue_path=root/'serial_long_dispatcher/preparation_v1/QUEUE.json';namespace='five_prepared_long_v1'
  queue=dict(schema='s6c-serial-long-queue.v1',status='REGISTERED_FINITE_QUEUE',namespace=namespace,total_sessions=5,items=[dict(candidate_id=c,item_id=c,output_root=str(root/c)) for c in ['C065','C067','C088','C091','B36']]);qb=write(queue_path,queue)
  def execute(expect_ok=True):
   p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),'-ReportRoot',str(root)],capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=20)
   if expect_ok:
    if p.returncode:raise AssertionError(p.stderr)
    return json.loads(p.stdout)
   return p.returncode!=0
  value=execute();ck('prepared_not_started',value['status']=='PREPARED_NOT_STARTED' and value['completed_sessions'] is None)
  d=root/'serial_long_dispatcher'/namespace;owner=dict(pid=1900000000,creation_time=1.);child=dict(pid=1900000001,creation_time=2.)
  write(d/'ADMISSION.json',dict(status='DISPATCHER_STARTED',queue=qb,owner=owner));value=execute();ck('admitted_no_observation',value['status']=='ADMITTED_AWAITING_FIRST_OBSERVATION')
  first=dict(status='RUNNING',owner=owner,child=child,completed_batches=0,requested_batches=5,completed_cells=0,active_item='C065',created_utc='2026-09-12T13:00:00Z')
  f1=d/'heartbeats/000/HEARTBEAT_00001.json';write(f1,first)
  # A malformed native heartbeat must never be opened by this reader.
  native=root/'C065';native.mkdir();(native/'HEARTBEAT.json').write_text('THIS IS NOT JSON');(native/'RESOURCE_HEARTBEAT.json').write_text('THIS IS NOT JSON')
  value=execute();ck('one_immutable_snapshot_no_native_heartbeat',value['status']=='RUNNING' and value['snapshot_path']==str(f1) and value['requested_sessions']==5 and value['completed_sessions']==0)
  f2=f1.with_name('HEARTBEAT_00002.json');f2.write_text('{partial')
  value=execute();ck('partial_latest_falls_back',value['snapshot_path']==str(f1) and value['skipped_unreadable_snapshots']==1)
  newer={**first,'created_utc':'2026-09-12T13:00:15Z'};write(f2,newer)
  kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CreateFileW.restype=ctypes.c_void_p;kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
  handle=kernel.CreateFileW(str(f2),0x80000000,0,None,3,0,None)
  if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
  try:value=execute();ck('actual_Windows_denied_latest_falls_back',value['snapshot_path']==str(f1) and value['skipped_unreadable_snapshots']==1)
  finally:kernel.CloseHandle(handle)
  value=execute();ck('newest_readable_snapshot_selected',value['snapshot_path']==str(f2) and value['heartbeat_utc']==newer['created_utc'])
  (d/'RESULT.json').write_text('{partial');value=execute();ck('partial_result_retains_snapshot',value['status']=='RUNNING' and len(value['result_read_errors'])==1)
  result=dict(schema='s6c-serial-long-dispatch-result.v1',status='DISPATCH_QUEUE_COMPLETE',queue=qb,owner=owner,completed_batches=5,requested_batches=5,completed_cells=5,active_item='B36',possible_child=None,ended_utc='2026-09-12T20:00:00Z',error=None)
  write(d/'RESULT.json',result);value=execute();ck('complete_result_sessions_semantics',value['status']=='DISPATCH_QUEUE_COMPLETE' and value['completed_sessions']==5 and value['snapshot_path']==str(d/'RESULT.json'))
  wrong={**queue,'total_sessions':4};write(queue_path,wrong);ck('wrong_finite_queue_rejected',execute(False));write(queue_path,queue)
  write(d/'ADMISSION.json',dict(status='DISPATCHER_STARTED',queue={**qb,'sha256':'wrong'},owner=owner));ck('admission_binding_mismatch_rejected',execute(False))
 result=dict(status='PASS_PRIVATE_STATUS_FIXTURES',checks=len(checks),names=checks,sources=[binding(script),binding(__file__),binding(HERE/'README_S6C_SERIAL_LONG_STATUS_V1.md'),binding(HERE/'s6c_paced_status_v3.ps1')],native_calls=0,actual_runtime_reads=0,scope='Private temporary JSON,10 hidden PowerShell reader invocations and one actual private Windows sharing denial. No original wrapper heartbeat, native/source/audio/event read or launch.')
 return write(output/'SOURCE_CHECKS.json',result)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
