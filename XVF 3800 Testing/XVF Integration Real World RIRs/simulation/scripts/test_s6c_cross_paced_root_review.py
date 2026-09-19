"""Independent cross-route source review; README_TEST_S6C_CROSS_PACED_ROOT_REVIEW.md."""
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace,FunctionType
from datetime import datetime,timezone,timedelta
import argparse,ast,hashlib,importlib,json,tempfile
HERE=Path(__file__).resolve().parent
EXPECTED='0989758d797b5308573d5546114cb170b2b0b4e7e50a0fc507698c571f7992d3'
def b(p):
 p=Path(p).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def save(p,v,immutable=False):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
 return b(p)
def run(output):
 assert b(HERE/'s6c_paced_cross_routes_v1.py')['sha256']==EXPECTED
 m=importlib.import_module('s6c_paced_cross_routes_v1')
 owner=m.checks();assert len(owner['checks'])==21 and owner['inherited_canonical_checks']==72
 checks=[]
 def ok(name,value):assert value,name;checks.append(name)
 original={n.name:n for n in ast.parse((HERE/'s6c_paced_epoch4.py').read_bytes()).body if isinstance(n,ast.FunctionDef)}
 class WorkerProjection(ast.NodeTransformer):
  def visit_Constant(self,node):
   if node.value=='s6c-canonical-paced-cell-result.v1':return ast.copy_location(ast.Constant('s6c-cross-route-paced-cell-result.v1'),node)
   if node.value=='S6C_CANONICAL_PACED_EPOCH4':return ast.copy_location(ast.Constant('S6C_CROSS_ROUTE_PACED_EPOCH4'),node)
   return node
 expected=WorkerProjection().visit(deepcopy(original['worker']))
 sha=hashlib.sha256(ast.dump(expected,include_attributes=False).encode()).hexdigest()
 ok('Worker differs only in separate result schema and quiet lease kind',sha==m.ADAPTATION['function_ast_sha256']['worker'])
 for name in m.ADAPTATION['ast_identical_functions']:
  ok('Exact original function '+name,hashlib.sha256(ast.dump(original[name],include_attributes=False).encode()).hexdigest()==m.ADAPTATION['function_ast_sha256'][name])
 spec,eb=m.L.read_bound(m.REPORT/'EPOCH4_EXECUTION_MANIFEST.json')
 ok('Actual epoch4 source binding',eb['sha256']==m.EPOCH_SHA)
 panel,pb=m.PRIVATE['panel']();routes=m.candidate_routes(spec,m.PAIR);selected=m.selected_panel(panel,'cross16_plus4',m.PAIR)
 grid=m.grid(m.PAIR,selected)
 ok('Actual exact40 main/repeat cells',len(grid)==len(set(grid))==40 and sum(r[3]==1 for r in grid)==32 and sum(r[3]==2 for r in grid)==8)
 ok('Actual routes preserve original C085/C086 identities',set(routes)=={('C085','O0'),('C086','O1')} and {(r['asr_tap'],r['identity_tap']) for r in routes.values()}=={('O0','O1'),('O1','O0')})
 with tempfile.TemporaryDirectory(prefix='root_cross_launch_fault_') as td:
  root=Path(td);folder=root/'cell';manifest=root/'MANIFEST.json';mb=save(manifest,dict(fixture=True));admission=root/'ADMISSION.json'
  deadline=datetime.now(timezone.utc)+timedelta(hours=1)
  q=dict(status='AUTHORIZED_FOR_QUIET_PACED',manifest_sha256=mb['sha256'],all_other_model_hil_work_stopped=True,all_heavy_analysis_stopped=True,expires_utc=deadline.isoformat())
  qb=save(admission,q)
  plan=dict(report_root=str(root/'experiment'),jobs=[dict(report_root=str(folder),job_id='test_cell',job_key='test_key',timeout_sec=1.,candidate_id='C085',asr_tap='O0',identity_tap='O1')],deadline_utc=deadline.isoformat())
  class Child:
   pid=990002
   def __init__(self):self.done=False;self.terminations=0
   def poll(self):return 0 if self.done else None
   def terminate(self):self.terminations+=1;self.done=True
   def kill(self):self.done=True
   def wait(self,timeout):return self.poll()
  child=Child();called=[]
  def popen(*args,**kwargs):called.append(args[0]);return child
  class Me:
   pid=990001
   def create_time(self):return 1.
   def cmdline(self):return ['synthetic-root-review']
  def process(pid=None):
   if pid is None:return Me()
   assert pid==child.pid and (folder/'SPAWNED_PROCESS.json').is_file()
   raise RuntimeError('SYNTHETIC_CREATION_QUERY_FAILURE_AFTER_DURABLE_SPAWN')
  fake_l=SimpleNamespace(read_bound=lambda p:(q,qb),dt=m.L.dt,DEADLINE=deadline,check_headroom=lambda *a:None,utc=m.L.utc,bind=b,verify=lambda *a:None)
  ns=dict(m.PRIVATE);ns.update(REPORT=root,L=fake_l,source_bindings=lambda:[],admit=lambda p:(plan,mb,None,SimpleNamespace(admit_work=lambda **kw:{},save=save),{}),quiet=lambda *a:None,psutil=SimpleNamespace(Process=process),subprocess=SimpleNamespace(Popen=popen,CREATE_NO_WINDOW=0,STDOUT=-2))
  isolated=FunctionType(m.PRIVATE['run'].__code__,ns)
  try:isolated(SimpleNamespace(manifest=manifest,quiet_admission=admission))
  except RuntimeError as exc:ok('Actual adapted failure path retains unverified quiet lease','Quiet lease release failed or unverified' in str(exc))
  else:raise AssertionError('Synthetic launch fault did not fail')
  outcomes=list((root/'experiment/invocations').glob('*/OUTCOME.json'));closures=list((root/'experiment/invocations').glob('*/CLOSURE.json'))
  assert len(outcomes)==len(closures)==1
  outcome=json.loads(outcomes[0].read_bytes());closure=json.loads(closures[0].read_bytes());spawn=json.loads((folder/'SPAWNED_PROCESS.json').read_bytes())
  ok('Actual adapted run recorded successful Popen before failed query',len(called)==1 and spawn['pid']==child.pid and spawn['creation_time'] is None and not (folder/'LAUNCH.json').exists())
  ok('Actual adapted run closes only supplied owned handle',child.terminations==1 and child.done and outcome['launch_cleanup']['unregistered_child_handle']['process_handle_exited'] is True)
  ok('Actual adapted outcome retains unknown creation and original failure',outcome['status']=='PARTIAL' and outcome['remaining_owned'][0]['creation_time'] is None and outcome['remaining_owned'][0]['alive'] is None and 'SYNTHETIC_CREATION_QUERY_FAILURE' in outcome['error'])
  ok('Actual adapted closure cannot report success',closure['status']=='LEASE_RETAINED_OWNED_CLOSURE_UNVERIFIED' and (root/'PACED_QUIET_OWNER.json').exists() and not (root/'experiment/PACED_INDEX.json').exists())
  failure_projection=dict(spawn=spawn,outcome=outcome,closure=closure)
 value=dict(status='PASS_ROOT_SOURCE_REVIEW',helper=b(HERE/'s6c_paced_cross_routes_v1.py'),readme=b(HERE/'README_S6C_PACED_CROSS_ROUTES_V1.md'),test=b(__file__),test_readme=b(HERE/'README_TEST_S6C_CROSS_PACED_ROOT_REVIEW.md'),reproduced_owner_checks=21,inherited_canonical_checks=72,independent_checks=checks,epoch=eb,panel=pb,actual_metadata_grid=grid,synthetic_adapted_run_failure=failure_projection,model_calls=0,physical_processes_spawned=0,actual_native_calls=0,actual_pcm_reads=0,scope='Original function and exact actual route/panel metadata checks plus isolated adapted-coordinator fault using only synthetic Popen/psutil handles and temporary files. No actual prepare, native run or finalist selection.')
 receipt=save(output,value);print(json.dumps(receipt))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)

