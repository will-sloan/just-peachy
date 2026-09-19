"""Independent V5 metadata review. See README_TEST_S6C_INVENTORY_V5_ROOT_REVIEW.md."""
from pathlib import Path
from copy import deepcopy
import argparse,ast,hashlib,json,tempfile,types
import s6c_execution_inventory_v5 as target
import test_s6c_execution_inventory_v5 as inherited

HELD_SHA='aee67604429f12013058ed94c74c3d3965c1e8e55299c87dfb6760394513aad8'
def binding(path):
 p=Path(path).resolve();raw=p.read_bytes()
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def projection(code):
 def constant(value):
  if isinstance(value,types.CodeType):return projection(value)
  if isinstance(value,(tuple,frozenset)):return (type(value).__name__,tuple(constant(v) for v in value))
  return value
 return dict(bytecode=code.co_code.hex(),constants=tuple(constant(v) for v in code.co_consts),
  names=code.co_names,varnames=code.co_varnames,freevars=code.co_freevars,cellvars=code.co_cellvars,
  argument_counts=(code.co_argcount,code.co_posonlyargcount,code.co_kwonlyargcount))

def run(output):
 before=target.source_bindings();assert binding(target.__file__)['sha256']==HELD_SHA
 untouched={n:getattr(target.v4,n) for n in ('admit_plan','admit_complete_cell','invocation_rows','collect_job')}
 checks=inherited.checks();assert len(checks)==63 and all(r['status']=='PASS' for r in checks)
 verified=[]
 # Build a separate expected AST with a simple tree walk; do not use the
 # adapter's compile_functions or NodeTransformer to establish this oracle.
 names={'expected_worker_argv','validate_launch','native_result_metadata','metadata_chain','admit_complete_cell',
        'admit_paced_index','row_base','collect_job','invocation_rows','paced_adapter'}
 tree=ast.parse(Path(target.v4.__file__).read_bytes())
 selected=[deepcopy(n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 assert len(selected)==10
 changed=[]
 for node in selected:
  for child in ast.walk(node):
   if isinstance(child,ast.Constant) and isinstance(child.value,str) and child.value in target.SENTINEL_REPLACEMENTS:
    old=child.value;child.value=target.SENTINEL_REPLACEMENTS[old];changed.append(dict(function=node.name,before=old,after=child.value))
 namespace=dict(vars(target.v4))
 exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),'independent_literal_oracle','exec'),namespace)
 for name in sorted(names):
  assert projection(getattr(target.S,name).__code__)==projection(namespace[name].__code__),name
  verified.append(name)
 assert all(getattr(target.v4,n) is value for n,value in untouched.items())
 assert target.v4.admit_plan.__globals__['CANONICAL']=='s6c-canonical-paired-paced.v1'
 root=output.parent/'INVENTORY_V5_ROOT_METADATA_SNAPSHOTS_V1'
 assert not root.exists();root.mkdir()
 reader=target.base.MetadataReader(root)
 canonical=target.REPORT/'paced_candidates/gate6_c071_c082_v1/MANIFEST.json'
 sentinel=target.REPORT/'paced_arrival_sentinel/arrival_boundary_v1/MANIFEST.json'
 continuous=target.REPORT/'long_b36/b36_o0_continuous_v1/MANIFEST.json'
 bindings=[binding(p) for p in (canonical,sentinel,continuous)]
 assert bindings[0]['sha256']=='6118c1e029578e150a5ee2f7f0b5db7ce4f368896094408af2e50ce5b01ca614'
 assert bindings[1]['sha256']=='92c5d2a8fa716400d253d0b18a8ff65d901698ef29762c2b07ae19687d5dc00d'
 assert bindings[2]['sha256']=='0421d6479332282194feed991a0aa1759e2c7908197d74507675c91960f7a632'
 a,ab,spec=target.admit_plan(reader,bindings[0]);assert len(a['jobs'])==24 and a['schema']==target.v4.CANONICAL
 b,bb,sspec=target.admit_plan(reader,bindings[1]);assert len(b['jobs'])==12 and b['schema']==target.SENTINEL
 assert [(j['candidate_id'],j['asr_tap'],j['repetition']) for j in b['jobs']]==[
  (candidate,tap,repetition) for repetition in (1,2,3) for tap in ('O0','O1')
  for candidate in (('C088','C105') if repetition%2 else ('C105','C088'))]
 c,cb,authority,guards=target.admit_long(reader,bindings[2])
 assert len(c['jobs'])==1 and c['jobs'][0]['profile_id']=='B36' and c['jobs'][0]['stream']=='O0'
 assert c['actual_execution_epoch']=='S6B_epoch2' and c['source_composition_epoch']=='S6C_epoch2'
 assert c['jobs'][0]['case_id'] is None and c['jobs'][0]['duration_sec']==1827.426625
 assert not (Path(c['report_root'])/'RESULT.json').exists()
 assert not (Path(c['output_root'])/'jobs'/c['jobs'][0]['job_id']/'LAUNCH.json').exists()
 assert all(Path(r['source']['path']).suffix=='.json' for r in reader.sources)
 assert target.source_bindings()==before
 result=dict(status='PASS_INDEPENDENT_METADATA_ADMISSION',helper=binding(__file__),
  readme=binding(Path(__file__).with_name('README_TEST_S6C_INVENTORY_V5_ROOT_REVIEW.md')),
  target=binding(target.__file__),target_sources=before,inherited_checks=checks,
  independently_compared_literal_function_bytecode=verified,literal_substitutions=changed,
  original_v4_globals_unchanged=True,actual_prepared_manifests=bindings,
  actual_grids=dict(canonical_gate_cells=24,arrival_sentinel_cells=12,historical_continuous_prepared_sessions=1),
  metadata_sources=reader.sources,models=0,policy_replays=0,new_native_sessions=0,full_inventory_runs=0,
  scope='Independent source/metadata review including the actual prepared B36 O0 manifest. No actual events, PCM, model bank or trajectories read; no empirical completion claim.')
 with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(binding(output)))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);run(p.parse_args().output)
