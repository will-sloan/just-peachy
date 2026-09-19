"""Focused immutable heartbeat checks; README_S6C_PACED_DISPATCH_V3.md."""
import argparse,ast,copy,ctypes,hashlib,json,os,tempfile
from pathlib import Path
from unittest.mock import patch
import s6c_paced_dispatch_v3 as D

V2_SHA='a327cd602c043acbeec3b08857ed0b257f96126e5e0f184ddd40c6c1b5ce3251'

def run(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=False);names=[];observations={}
 def ck(name,truth=True):
  if not truth:raise AssertionError(name)
  names.append(name)
 def reject(name,call,kind=ValueError):
  try:call()
  except kind:ck(name)
  else:raise AssertionError(name)
 prior=D.HERE/'s6c_paced_dispatch_v2.py';oldraw=prior.read_bytes()
 ck('exact_preserved_v2',hashlib.sha256(oldraw).hexdigest()==V2_SHA)
 old=ast.parse(oldraw);new=ast.parse(Path(D.__file__).read_bytes())
 of={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)}
 nf={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
 oldcall=next(n for n in ast.walk(of['run']) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='save' and n.keywords and any(k.arg=='replace' for k in n.keywords))
 class Reverse(ast.NodeTransformer):
  def visit_Constant(self,n):
   if n.value=='README_S6C_PACED_DISPATCH_V3.md':n.value='README_S6C_PACED_DISPATCH_V2.md'
   return n
  def visit_Assign(self,n):
   if len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='heartbeat_sequence':
    ck('counter_initializes_zero',isinstance(n.value,ast.Constant) and n.value.value==0);return None
   return self.generic_visit(n)
  def visit_AugAssign(self,n):
   if isinstance(n.target,ast.Name) and n.target.id=='heartbeat_sequence':
    ck('counter_increments_one',isinstance(n.op,ast.Add) and isinstance(n.value,ast.Constant) and n.value.value==1);return None
   return self.generic_visit(n)
  def visit_Call(self,n):
   if isinstance(n.func,ast.Name) and n.func.id=='save_heartbeat':
    ck('snapshot_call_retains_identical_payload',len(n.args)==3 and not n.keywords and ast.dump(n.args[1])==ast.dump(oldcall.args[1]) and ast.dump(n.args[0])=="Name(id='out', ctx=Load())" and ast.dump(n.args[2])=="Name(id='heartbeat_sequence', ctx=Load())")
    return copy.deepcopy(oldcall)
   return self.generic_visit(n)
 for name,node in of.items():
  other=Reverse().visit(copy.deepcopy(nf[name])) if name=='run' else nf[name]
  ck('unchanged_function_'+name,ast.dump(node)==ast.dump(other))
 ck('single_added_function',set(nf)-set(of)=={'save_heartbeat'})
 def globals_ast(tree):
  return [ast.dump(n) for n in tree.body[1:] if not isinstance(n,ast.FunctionDef) and not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('HEARTBEAT_SNAPSHOT_') for t in n.targets))]
 ck('unchanged_import_constants_entrypoint',globals_ast(old)==globals_ast(new))
 ck('snapshot_bounds_exact',(D.HEARTBEAT_SNAPSHOT_LIMIT,D.HEARTBEAT_SNAPSHOT_MAX_BYTES,D.HEARTBEAT_SNAPSHOT_BLOCK_SIZE)==(20000,16384,1000))
 snapshot_ast=nf['save_heartbeat']
 ck('snapshot_has_no_exception_suppression',not any(isinstance(n,ast.Try) for n in ast.walk(snapshot_ast)))
 with tempfile.TemporaryDirectory(prefix='s6c_dispatch_v3_') as tmp:
  root=Path(tmp);value={'status':'RUNNING','child':{'pid':123,'creation_time':1.},'sample':'a'}
  wanted=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
  # A reader may indefinitely deny replacement of an old path. V3 never calls it.
  for winerror in (5,32,33):
   err=PermissionError('persistent private replacement denial');err.winerror=winerror
   with patch.object(D.os,'replace',side_effect=err) as replacement:
    rows=[D.save_heartbeat(root/str(winerror),value,i) for i in range(1,5)]
   ck('repeated_replacement_denial_irrelevant_'+str(winerror),replacement.call_count==0 and all(Path(b['path']).read_bytes()==wanted for b in rows))
  observations['persistent_replace_denial']={'winerrors':[5,32,33],'snapshots_per_error':4,'replace_calls':0}
  one=D.save_heartbeat(root/'numbered',value,1);first=Path(one['path'])
  reject('collision_preserves_first_snapshot',lambda:D.save_heartbeat(root/'numbered',{'other':True},1),FileExistsError)
  ck('collision_bytes_unchanged',first.read_bytes()==wanted)
  for seq in (0,-1,True,1.,20001):
   reject('invalid_sequence_'+repr(seq),lambda seq=seq:D.save_heartbeat(root/'invalid',value,seq))
  ck('invalid_sequence_creates_no_tree',not (root/'invalid').exists())
  reject('oversize_rejected_before_write',lambda:D.save_heartbeat(root/'oversize',{'data':'x'*16384},1))
  ck('oversize_creates_no_tree',not (root/'oversize').exists())
  reject('nonfinite_payload_rejected',lambda:D.save_heartbeat(root/'nan',{'number':float('nan')},1))
  last0=D.save_heartbeat(root/'numbered',value,1000);first1=D.save_heartbeat(root/'numbered',value,1001);last=D.save_heartbeat(root/'numbered',value,20000)
  ck('bounded_numbered_blocks',[Path(x['path']).parent.name for x in (one,last0,first1,last)]==['000','000','001','019'] and Path(last['path']).name=='HEARTBEAT_20000.json')
  denial=PermissionError('private snapshot creation denied');denial.winerror=5
  with patch.object(Path,'open',side_effect=denial):
   try:D.save_heartbeat(root/'open_denied',value,1)
   except PermissionError as got:ck('create_access_denial_not_suppressed',got is denial)
   else:raise AssertionError('creation must fail')
  write_error=OSError('injected fsync storage failure')
  with patch.object(D.os,'fsync',side_effect=write_error):
   try:D.save_heartbeat(root/'fsync_failed',value,1)
   except OSError as got:ck('fsync_error_not_suppressed_and_file_preserved',got is write_error and (root/'fsync_failed/heartbeats/000/HEARTBEAT_00001.json').exists())
   else:raise AssertionError('fsync must fail')
  # Real Windows reader denies delete/write sharing on the prior immutable file.
  if os.name!='nt':raise RuntimeError('Required Windows sharing fixture unavailable')
  from ctypes import wintypes
  kernel=ctypes.WinDLL('kernel32',use_last_error=True)
  create=kernel.CreateFileW;create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];create.restype=wintypes.HANDLE
  close=kernel.CloseHandle;close.argtypes=[wintypes.HANDLE];close.restype=wintypes.BOOL
  actual=root/'windows';prior_b=D.save_heartbeat(actual,value,1);prior_path=Path(prior_b['path']);handle=create(str(prior_path),0x80000000,0x1,None,3,0x80,None)
  if handle==wintypes.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
  errors=[];probe=actual/'owned_probe.tmp';probe.write_bytes(b'private replacement probe')
  try:
   for _ in range(3):
    try:os.replace(probe,prior_path)
    except PermissionError as exc:errors.append(exc.winerror)
    else:raise AssertionError('Real reader should deny replacing prior snapshot')
   second=D.save_heartbeat(actual,value,2);third=D.save_heartbeat(actual,{'state':'next'},3)
   ck('real_repeated_windows_access_denial_with_new_snapshots',len(errors)==3 and set(errors)<={5,32,33} and prior_path.read_bytes()==wanted and Path(second['path']).read_bytes()==wanted and json.loads(Path(third['path']).read_bytes())=={'state':'next'})
  finally:
   if not close(handle):raise ctypes.WinError(ctypes.get_last_error())
  observations['real_windows_read_lock']={'replacement_error_codes':errors,'new_snapshots_created_while_prior_locked':2,'prior_snapshot_unchanged':True,'private_tempfile_only':True}
  ck('latest_lookup_bounded_blocks',sorted(p.name for p in (root/'numbered/heartbeats').iterdir())==['000','001','019'])
 return D.save(output/'SOURCE_CHECKS.json',dict(schema='s6c-dispatch-v3-checks.v1',status='PASS_SOURCE_AND_PRIVATE_FIXTURES_ONLY',checks=len(names),names=names,observations=observations,sources=[D.binding(prior),D.binding(D.__file__),D.binding(__file__),D.binding(D.HERE/'README_S6C_PACED_DISPATCH_V3.md')],actual_dispatcher_runs=0,native_calls=0,scope='No actual coordinator, queue, lease, runtime evidence, assets, audio or census access. Windows handles and injected failures touch private temporary files only.'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))

