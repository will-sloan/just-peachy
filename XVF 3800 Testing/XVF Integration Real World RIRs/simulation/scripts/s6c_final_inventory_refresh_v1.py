"""Explicit final inventory composition; README_S6C_FINAL_INVENTORY_REFRESH_V1.md."""
from __future__ import annotations
import argparse, hashlib, importlib, json, re, types
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = {
 's6c_inventory_refresh_v1':'bc66af0ae233935c5b33c0c5487883d5d0e4c80769d383018bbe0e3d90e66618',
 's6c_controls_recovery_inventory_v1':'e2f6dece6c9062e35f8cdeece73376a670e4ba3d390059a8b04de85548afadf8',
 's6c_b36_v2_inventory_v1':'7741c2207124d03a99327ba86b19cb1cb235aa01445643ba6654202beada234c'}
SCHEMA = 's6c-final-inventory-integration.v1'
RECOVERY_SHA = 'c9a3a0394f19920bb886156d8f7d8ede2773ad509f6338c61c8882e51f0007a4'
LONG_NAMES = ('epoch4_long_c065_o0_fast_v2','epoch4_long_c067_o0_fast_v2',
              'epoch4_long_c088_o0_fast_v2','epoch4_long_c091_o0_fast_v2')

def require(value, message):
 if not value: raise ValueError(message)

def bind(path):
 p=Path(path).resolve(); raw=p.read_bytes()
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def load(name):
 p=HERE/(name+'.py');require(bind(p)['sha256']==PINS[name],'Held integration dependency: '+name)
 m=importlib.import_module(name);require(Path(m.__file__).resolve()==p,'Import origin');return m

def clone_functions(module, updates):
 """Identical function code objects, private globals; original classes retained."""
 ns=dict(vars(module)); ns.update(updates)
 for name,fn in vars(module).items():
  if isinstance(fn,types.FunctionType) and fn.__globals__ is vars(module):
   f=types.FunctionType(fn.__code__,ns,fn.__name__,fn.__defaults__,fn.__closure__)
   f.__kwdefaults__=fn.__kwdefaults__;ns[name]=f
 return ns

def make_context():
 F=load('s6c_inventory_refresh_v1'); C=load('s6c_controls_recovery_inventory_v1'); B36=load('s6c_b36_v2_inventory_v1')
 recovery=dict(path=str(F.REPORT/'runtime_failure_review/external_lease_recovery/controls_cross_volume_v1/RESULT.json'),bytes=36456,sha256=RECOVERY_SHA)
 controls=C.make_inventory(recovery); combined=B36.make_inventory(base_inventory=controls)
 ns=clone_functions(F,dict(V=combined)); old_sources=ns['sources']
 def sources():
  rows=old_sources()+[bind(__file__),bind(HERE/'README_S6C_FINAL_INVENTORY_REFRESH_V1.md')]
  unique={}
  for b in rows:
   key=F.B.canonical(b['path']);require(key not in unique or unique[key]==b,'Conflicting integration source');unique[key]=b
  return list(unique.values())
 ns['sources']=sources
 return F,types.SimpleNamespace(**ns),combined,recovery

def families(F):
 return [F.REPORT/n for n in ('paced_candidates','paced_arrival_sentinel','paced_cross_routes','long_native_epoch4','long_b36')]+[F.PAYLOAD/'paced_controls']

def manifest_list(F):
 """Bounded immediate manifest metadata only; unknown namespaces remain visible."""
 result=[]
 for root in families(F):
  require(root.is_dir(),'Missing manifest family')
  for p in sorted(root.glob('*/MANIFEST.json')):
   require(p.resolve()==p.absolute(),'Reparse manifest path')
   raw=p.read_bytes();require(len(raw)<=4*2**20,'Bounded manifest JSON')
   result.append((json.loads(raw),F.B.binding(p,raw)))
 return result

def required_long(F):
 return [F.REPORT/'long_native_epoch4'/name/'MANIFEST.json' for name in LONG_NAMES]+[F.REPORT/'long_b36/b36_o0_continuous_fast_v1/MANIFEST.json']

def assemble(output):
 F,context,api,recovery=make_context(); before=context.sources()
 fast=[];legacy=[];automatic=[];documents=manifest_list(F)
 for plan,b in documents:
  if api.kind_of(plan) is not None: fast.append(b)
  elif plan.get('schema')=='s6c-epoch4-long-native-admission.v1': automatic.append(b)
  else: legacy.append(b)
 bypath={F.B.canonical(b['path']):(p,b) for p,b in documents}
 long=[]
 for p in required_long(F):
  plan,b=bypath[F.B.canonical(p)];require(b in fast,'Required continuous manifest not fast')
  long.append(b)
 require(len(long)==5 and len({b['path'] for b in long})==5,'Exact five continuous manifests')
 result=dict(schema=SCHEMA,status='DRAFT_PENDING_CONTINUOUS_CLOSURE',sources=before,recovery=recovery,
  fast_manifests=fast,legacy_manifests=legacy,automatic_legacy_long_manifests=automatic,
  required_continuous_manifests=long,late_pool_rollup=bind(F.ROLLUP),observer_index=None,root_authority=None,
  counts=dict(fast=len(fast),explicit_legacy=len(legacy),automatic_legacy_long=len(automatic),all_manifests=len(documents)),
  scope='Manifest metadata only. All prepared versions and failed attempts remain eligible for later discovery; preparation is not execution. Three original C-long namespaces remain in original V3 admission discovery. No census or final acceptance.',models=0)
 require(context.sources()==before,'Source changed during assembly')
 return F.B.write_new(Path(output).resolve(),result)

def read_input(pair):
 p=Path(pair[0]).resolve();raw=p.read_bytes();require(len(raw)<=8*2**20,'Bounded explicit JSON input')
 b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 require(b['sha256']==pair[1],'Explicit input SHA');return json.loads(raw),b

def validate_assembly(F,context,api,recovery,assembly):
 require(assembly['schema']==SCHEMA and assembly['status']=='DRAFT_PENDING_CONTINUOUS_CLOSURE','Exact registered assembly schema')
 require(assembly['sources']==context.sources() and assembly['recovery']==recovery,'Assembly source/recovery differs')
 require(assembly['observer_index'] is None and assembly['root_authority'] is None,'Draft cannot imply closure')
 rows=manifest_list(F); actual={F.B.canonical(b['path']):(p,b) for p,b in rows}
 declared=assembly['fast_manifests']+assembly['legacy_manifests']+assembly['automatic_legacy_long_manifests']
 require(len(declared)==len(actual)==len({F.B.canonical(b['path']) for b in declared}),'Manifest count/duplicate differs; preserve and update assembly')
 for b in declared:require(actual[F.B.canonical(b['path'])][1]==b,'Current manifest differs')
 for b in assembly['fast_manifests']:require(api.kind_of(actual[F.B.canonical(b['path'])][0]) is not None,'Fast classification differs')
 for b in assembly['legacy_manifests']:
  p=actual[F.B.canonical(b['path'])][0];require(api.kind_of(p) is None and p.get('schema')!='s6c-epoch4-long-native-admission.v1','Explicit legacy classification differs')
 for b in assembly['automatic_legacy_long_manifests']:
  p=actual[F.B.canonical(b['path'])][0];require(api.kind_of(p) is None and p.get('schema')=='s6c-epoch4-long-native-admission.v1','Automatic original long classification differs')
 require(assembly['required_continuous_manifests']==[actual[F.B.canonical(p)][1] for p in required_long(F)],'Required five continuous bindings differ')
 require(assembly['late_pool_rollup']==bind(F.ROLLUP) and assembly['late_pool_rollup']['sha256']==F.ROLLUP_SHA,'Held six-pool authority differs')
 expected=dict(fast=len(assembly['fast_manifests']),explicit_legacy=len(assembly['legacy_manifests']),automatic_legacy_long=len(assembly['automatic_legacy_long_manifests']),all_manifests=len(actual))
 require(assembly['counts']==expected,'Assembly counts differ')

def spec_document(assembly,ab,observer):
 require(isinstance(observer,dict) and set(observer)=={'path','bytes','sha256'},'Actual observer index binding required')
 return dict(schema='s6c-inventory-refresh-spec.v1',status='REGISTERED_FINITE_REFRESH',assembly=ab,
  recovery=assembly['recovery'],late_pool_rollup=assembly['late_pool_rollup'],
  fast_manifests=assembly['fast_manifests'],legacy_manifests=assembly['legacy_manifests'],
  automatic_legacy_long_manifests=assembly['automatic_legacy_long_manifests'],
  required_continuous_manifests=assembly['required_continuous_manifests'],observer_index=observer,
  integration_sources=assembly['sources'])

def resolve_spec(args):
 F,context,api,recovery=make_context();F.quiet()
 assembly,ab=read_input(args.assembly);validate_assembly(F,context,api,recovery,assembly)
 observer,ob=read_input(args.observer_index)
 require(observer['schema']=='s6c-fast-observer-index.v1' and observer['status']=='COMPLETE_METADATA_ENUMERATION','Completed explicit observer index required')
 # This writes a finite input only. The held collect path admits every indexed
 # exit and the recovery chain later; no owner/cell enumeration happens here.
 return F.B.write_new(Path(args.output).resolve(),spec_document(assembly,ab,ob))

def authority_gate(F,assembly,spec,sb,authority):
 require(authority['schema']=='s6c-inventory-refresh-authority.v1' and authority['status']=='AUTHORIZED_POST_CLOSURE_METADATA_CENSUS','Explicit root census authority required')
 require(authority['spec']==sb and authority['helper']==bind(F.__file__),'Original refresh helper/spec authority')
 require(authority['integration_helper']==bind(__file__) and authority['integration_readme']==bind(HERE/'README_S6C_FINAL_INVENTORY_REFRESH_V1.md'),'Explicit integration authority')
 require(authority['recovery']==assembly['recovery'] and authority['integration_sources']==assembly['sources'],'Explicit layered source/recovery authority')
 require(authority['all_model_paced_long_work_closed'] is True and authority['no_concurrent_research_writers'] is True,'Root closure/writer scope required')
 require(authority['completed_continuous_manifests']==assembly['required_continuous_manifests'],'All five exact continuous sessions must be declared closed by root')

def collect(args):
 F,context,api,recovery=make_context();F.quiet();before=context.sources()
 assembly,ab=read_input(args.assembly);validate_assembly(F,context,api,recovery,assembly)
 spec,sb=read_input(args.spec);authority,authority_binding=read_input(args.authority)
 require(spec==spec_document(assembly,ab,spec['observer_index']),'Exact resolved finite specification required')
 authority_gate(F,assembly,spec,sb,authority)
 require(re.fullmatch(r'[A-Za-z0-9_-]{1,45}',args.version or ''),'Fresh short namespace')
 out=F.REPORT/'execution_inventory'/(args.version+'_integration');require(not out.exists(),'Preserve prior integration');out.mkdir(parents=True)
 admission=F.B.write_new(out/'ADMISSION.json',dict(schema=SCHEMA,status='ROOT_AUTHORIZED_METADATA_REFRESH_NOT_COMPLETE',assembly=ab,spec=sb,authority=authority_binding,sources=before,recovery=recovery,scope='Original held refresh functions execute with explicit controls-recovery then B36 V2 callbacks in private globals.'))
 try:
  result=context.collect(types.SimpleNamespace(version=args.version,spec=args.spec,authority=args.authority))
  require(context.sources()==before,'Source changed during integration');F.quiet()
  return F.B.write_new(out/'RESULT.json',dict(schema=SCHEMA,status='REFRESH_RETURNED_INSPECT_BOUND_FLAGS',admission=admission,refresh_receipt=result,sources=before,recovery=recovery,models=0,scope='Consume bound refresh, fresh legacy, and appended inventory statuses together. This result is not final scientific acceptance; original failed controls/scanner and failed C065 V1 remain separate history.'))
 except Exception as exc:
  F.B.write_new(out/'FAILURE.json',dict(schema=SCHEMA,status='FAILED_NO_FINAL_CENSUS',admission=admission,error=repr(exc),models=0));raise

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);s=p.add_subparsers(dest='action',required=True)
 a=s.add_parser('assemble',allow_abbrev=False);a.add_argument('--output',required=True)
 r=s.add_parser('resolve-spec',allow_abbrev=False);r.add_argument('--assembly',nargs=2,required=True);r.add_argument('--observer-index',nargs=2,required=True);r.add_argument('--output',required=True)
 c=s.add_parser('collect',allow_abbrev=False);c.add_argument('--assembly',nargs=2,required=True);c.add_argument('--spec',nargs=2,required=True);c.add_argument('--authority',nargs=2,required=True);c.add_argument('--version',required=True)
 a=p.parse_args();result=assemble(a.output) if a.action=='assemble' else resolve_spec(a) if a.action=='resolve-spec' else collect(a);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
