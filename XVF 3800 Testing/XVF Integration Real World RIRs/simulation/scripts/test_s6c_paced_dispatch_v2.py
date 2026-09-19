"""Heartbeat-only V2 checks; README_S6C_PACED_DISPATCH_V2.md."""
import argparse,ast,ctypes,hashlib,json,os,tempfile,threading,time
from pathlib import Path
from unittest.mock import patch
import s6c_paced_dispatch_v2 as D

V1_SHA='c6a241b4f9f611ceae073a7948cb80051ac4474c2f4464d5c441a948e5e4cecd'

def run(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=False);checks=[];observations={}
 def ck(name,value=True):
  if not value:raise AssertionError(name)
  checks.append(name)
 def failure(code,kind=PermissionError):
  e=kind('injected');e.winerror=code;return e
 old=D.HERE/'s6c_paced_dispatch_v1.py';raw=old.read_bytes();ck('preserved_v1_sha',hashlib.sha256(raw).hexdigest()==V1_SHA)
 a=ast.parse(raw);b=ast.parse(Path(D.__file__).read_bytes())
 # Reverse only the admitted README literal and save replacement, then require
 # every existing function and all original module statements to be exact.
 funcs_a={n.name:n for n in a.body if isinstance(n,ast.FunctionDef)}
 funcs_b={n.name:n for n in b.body if isinstance(n,ast.FunctionDef)}
 class Readme(ast.NodeTransformer):
  def visit_Constant(self,node):
   if node.value=='README_S6C_PACED_DISPATCH_V2.md':node.value='README_S6C_PACED_DISPATCH_V1.md'
   return node
 for name,node in funcs_a.items():
  if name=='save':continue
  ck('original_function_'+name,ast.dump(node)==ast.dump(Readme().visit(funcs_b[name])))
 def globals_ast(tree):
  return [ast.dump(n) for n in tree.body[1:] if not isinstance(n,ast.FunctionDef) and not (isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id.startswith('HEARTBEAT_REPLACE_') for x in n.targets))]
 ck('original_import_constants_entrypoint_exact',globals_ast(a)==globals_ast(b))
 ck('one_added_retry_function',set(funcs_b)-set(funcs_a)=={'replace_heartbeat'})
 with tempfile.TemporaryDirectory(prefix='s6c_dispatch_v2_') as tmp:
  root=Path(tmp);target=root/'HEARTBEAT.json';temporary=root/'HEARTBEAT.json.tmp';value={'state':'same \u03b1 bytes','sequence':2}
  wanted=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();real_replace=os.replace
  for winerror in (5,32,33):
   target.write_bytes(b'old');clock=[0.];seen=[]
   def replace(t,p):
    seen.append((t,p,t.read_bytes()))
    if len(seen)<3:raise failure(winerror)
    return real_replace(t,p)
   with patch.object(D.os,'replace',replace),patch.object(D.time,'monotonic',lambda:clock[0]),patch.object(D.time,'sleep',lambda n:clock.__setitem__(0,clock[0]+n)):
    result=D.save(target,value,replace=True)
   ck('transient_success_'+str(winerror),len(seen)==3 and all(x==(temporary,target,wanted) for x in seen) and target.read_bytes()==wanted and not temporary.exists() and result['sha256']==hashlib.sha256(wanted).hexdigest())
  for name,exc in [('other_permission',failure(87)),('permission_without_winerror',PermissionError('plain')),('non_permission_with_transient_number',failure(5,OSError))]:
   target.write_bytes(b'old');seen=[]
   def fail(t,p):seen.append((t,p));raise exc
   with patch.object(D.os,'replace',fail),patch.object(D.time,'sleep',side_effect=AssertionError('permanent must not sleep')):
    try:D.save(target,value,replace=True)
    except type(exc) as got:ck(name,got is exc and len(seen)==1 and temporary.read_bytes()==wanted and target.read_bytes()==b'old')
    else:raise AssertionError(name)
   temporary.unlink()
  target.write_bytes(b'old');clock=[0.];waits=[];seen=[];exc=failure(32)
  def always(t,p):seen.append((t,p,t.read_bytes()));raise exc
  def sleep(n):waits.append(n);clock[0]+=n
  with patch.object(D.os,'replace',always),patch.object(D.time,'monotonic',lambda:clock[0]),patch.object(D.time,'sleep',sleep):
   try:D.save(target,value,replace=True)
   except PermissionError as got:ck('deadline_exhaustion_preserves_original_and_tmp',got is exc and clock[0]<=2.0000000001 and len(seen)<=41 and temporary.read_bytes()==wanted and target.read_bytes()==b'old' and all(x==(temporary,target,wanted) for x in seen))
   else:raise AssertionError('deadline missing')
  observations['mock_timeout']={'attempts':len(seen),'slept_sec':sum(waits)}
  temporary.unlink();seen=[]
  with patch.object(D.os,'replace',always),patch.object(D.time,'monotonic',lambda:0.),patch.object(D.time,'sleep',lambda n:None):
   try:D.save(target,value,replace=True)
   except PermissionError:ck('attempt_ceiling_even_if_clock_stalls',len(seen)==41 and temporary.read_bytes()==wanted)
   else:raise AssertionError('attempt ceiling missing')
  temporary.unlink();temporary.write_bytes(b'preserved prior tmp')
  with patch.object(D.os,'replace',side_effect=AssertionError('must not replace existing tmp')):
   try:D.save(target,value,replace=True)
   except ValueError:ck('existing_tmp_never_overwritten',temporary.read_bytes()==b'preserved prior tmp')
   else:raise AssertionError('tmp guard missing')
  temporary.unlink()
  other=root/'OTHER.json';seen=[]
  with patch.object(D.os,'replace',always),patch.object(D.time,'sleep',side_effect=AssertionError('nonheartbeat must not sleep')):
   try:D.save(other,value,replace=True)
   except PermissionError:ck('nonheartbeat_replacement_not_retried',len(seen)==1 and other.with_name('OTHER.json.tmp').read_bytes()==wanted)
   else:raise AssertionError('other replacement')
  for t,p in [(root/'foreign.tmp',target),(temporary,root/'OTHER.json')]:
   try:D.replace_heartbeat(t,p)
   except ValueError:ck('reject_mismatched_heartbeat_paths')
   else:raise AssertionError('path guard')
  frozen=root/'IMMUTABLE.json';D.save(frozen,value)
  try:D.save(frozen,{'different':True})
  except FileExistsError:ck('immutable_save_stays_exclusive',frozen.read_bytes()==wanted)
  else:raise AssertionError('immutable overwrite')
  if os.name!='nt':raise RuntimeError('Required real Windows sharing test unavailable')
  from ctypes import wintypes
  kernel=ctypes.WinDLL('kernel32',use_last_error=True)
  create=kernel.CreateFileW;create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];create.restype=wintypes.HANDLE
  close=kernel.CloseHandle;close.argtypes=[wintypes.HANDLE];close.restype=wintypes.BOOL
  target.write_bytes(b'old native-file-independent fixture')
  handle=create(str(target),0x80000000,0x1,None,3,0x80,None)
  if handle==wintypes.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
  encountered=threading.Event();errors=[];released=[];calls=[];close_errors=[]
  def unlock():
   try:
    if not encountered.wait(1.):raise AssertionError('sharing failure was not observed')
    time.sleep(.08)
   except BaseException as e:close_errors.append(repr(e))
   finally:
    if not close(handle):close_errors.append('CloseHandle failed')
    released.append(True)
  def observed_replace(t,p):
   calls.append((t,p,t.read_bytes()))
   try:return real_replace(t,p)
   except PermissionError as e:errors.append(e.winerror);encountered.set();raise
  thread=threading.Thread(target=unlock);thread.start();started=time.monotonic()
  try:
   with patch.object(D.os,'replace',observed_replace):D.save(target,value,replace=True)
  finally:thread.join(2.)
  ck('real_windows_reader_sharing_lock_then_atomic_success',not thread.is_alive() and not close_errors and released and errors and set(errors)<={5,32,33} and target.read_bytes()==wanted and not temporary.exists() and all(x==(temporary,target,wanted) for x in calls))
  observations['windows_sharing_lock']={'error_codes':errors,'attempts':len(calls),'elapsed_sec':time.monotonic()-started,'exact_target_bytes':True,'same_temporary_path_and_bytes':True,'private_tempfile_only':True}
 return D.save(output/'SOURCE_CHECKS.json',dict(schema='s6c-paced-dispatch-v2-checks.v1',status='PASS_SOURCE_AND_PRIVATE_FIXTURES_ONLY',checks=len(checks),names=checks,observations=observations,sources=[D.binding(old),D.binding(D.__file__),D.binding(__file__),D.binding(D.HERE/'README_S6C_PACED_DISPATCH_V2.md')],native_calls=0,dispatcher_runs=0,scope='No real queue, coordinator, lease, model, audio, runtime data or census inspected. Real sharing lock uses only a private temporary target and owned handle.'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))

