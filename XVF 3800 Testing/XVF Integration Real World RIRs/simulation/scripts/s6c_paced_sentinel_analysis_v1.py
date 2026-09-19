"""Explicit sentinel post-closure adapter. README_S6C_PACED_SENTINEL_ANALYSIS_V1.md."""
from pathlib import Path
import argparse,ast,hashlib,importlib,json,types
import s6c_paced_analysis_v1 as core

CORE_SHA='936b5973091d677b4eb24847e7e3e2d84df614340d3984f10ff31283096b880a'
INVENTORY_SHA='aee67604429f12013058ed94c74c3d3965c1e8e55299c87dfb6760394513aad8'
SCHEMA='jp_s6c_paced_arrival_sentinel_analysis.v1'
HERE=Path(__file__).resolve().parent
core_binding=core.file_binding(core.__file__)
if core_binding['sha256']!=CORE_SHA or Path(core.__file__).resolve()!=HERE/'s6c_paced_analysis_v1.py':
 raise ValueError('Reviewed canonical converter changed')
inventory_path=HERE/'s6c_execution_inventory_v5.py'
if core.file_binding(inventory_path)['sha256']!=INVENTORY_SHA:
 raise ValueError('Reviewed V5 inventory changed')
inventory=importlib.import_module('s6c_execution_inventory_v5')
if Path(inventory.__file__).resolve()!=inventory_path:
 raise ValueError('Wrong V5 import origin')

def inventory_module():
 # Canonical single-scene source semantics remain; only the explicitly
 # registered one-scene/repetition selection and closure schema differ.
 return types.SimpleNamespace(base=inventory.base,CANONICAL=inventory.SENTINEL,
  admit_plan=inventory.S.admit_plan,admit_complete_cell=inventory.S.admit_complete_cell,
  admit_paced_index=inventory.S.admit_paced_index,invocation_rows=inventory.S.invocation_rows)

def source_bindings():
 rows=core.source_bindings()+inventory.source_bindings()+[
  core.file_binding(__file__),core.file_binding(HERE/'README_S6C_PACED_SENTINEL_ANALYSIS_V1.md')]
 result={}
 for b in rows:
  key=str(Path(b['path']).resolve()).casefold()
  if key in result and result[key]!=b:raise ValueError('Conflicting source binding')
  result[key]=b
 return list(result.values())

def make_adapter():
 source=ast.parse(Path(core.__file__).read_bytes())
 names={'safe_output','prepare','run'}
 nodes=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in names]
 if len(nodes)!=3:raise ValueError('Exact reviewed orchestration functions required')
 changed=[]
 # Only the output namespace literal changes. Admission is supplied through
 # explicit V5 sentinel API; all source/event/policy/name transformations stay.
 for node in nodes:
  for value in ast.walk(node):
   if isinstance(value,ast.Constant) and value.value=='paced_analysis':
    value.value='paced_arrival_analysis';changed.append(node.name)
 if sorted(changed)!=['run','safe_output']:
  raise ValueError('Unexpected namespace adaptation')
 namespace={**vars(core),'SCHEMA':SCHEMA,'inventory_module':inventory_module,
  'source_bindings':source_bindings}
 exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(__file__),'exec'),namespace)
 return types.SimpleNamespace(**{n:namespace[n] for n in names})

adapter=make_adapter()

def checks():
 inherited=core.checks()
 assert len(inherited['checks'])==34
 assert adapter.safe_output('prospective_sentinel_analysis_fixture')==core.REPORT/'paced_arrival_analysis/prospective_sentinel_analysis_fixture'
 assert core.safe_output('prospective_canonical_analysis_fixture')==core.REPORT/'paced_analysis/prospective_canonical_analysis_fixture'
 assert core.SCHEMA=='jp_s6c_paced_observation_analysis.v1'
 assert core.inventory_module().CANONICAL=='s6c-canonical-paired-paced.v1'
 assert inventory_module().CANONICAL=='s6c-paced-arrival-sentinel.v1'
 assert adapter.run.__globals__['convert_closed_cell'] is core.convert_closed_cell
 assert adapter.run.__globals__['name_context'] is core.name_context
 assert adapter.run.__globals__['closed_coordinators'] is core.closed_coordinators
 return dict(status='PASS_SOURCE_ADAPTER_ONLY',inherited_checks=inherited,
  exact_core=core_binding,sources=source_bindings(),changed_literals=['paced_analysis -> paced_arrival_analysis in safe_output and run'],
  separate_global_scope=True,native_transformations_unchanged=True,
  models=0,policy_replays=0,actual_paced_cells=0,
  scope='Source checks only. Real sentinel PACED_INDEX and original closed native cells are required by prepare/run. All three repetitions retained separately.')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
 sub.add_parser('checks')
 a=sub.add_parser('prepare');a.add_argument('--manifest',required=True,type=Path);a.add_argument('--index',required=True,type=Path);a.add_argument('--namespace',required=True)
 a=sub.add_parser('run');a.add_argument('--plan',required=True,type=Path)
 args=p.parse_args()
 result=checks() if args.action=='checks' else adapter.prepare(args) if args.action=='prepare' else adapter.run(args)
 print(json.dumps(result,indent=2,allow_nan=False))

