"""Small integration checks; README_S6C_FINAL_INVENTORY_REFRESH_V1.md."""
import argparse,copy,json,types,tempfile
from pathlib import Path
import s6c_final_inventory_refresh_v1 as R

def run(output):
 F,ctx,api,recovery=R.make_context();checks=[]
 def ok(name,value):
  if not value:raise AssertionError(name)
  checks.append(name)
 def bad(name,fn):
  try:fn()
  except (ValueError,KeyError,TypeError):checks.append(name);return
  raise AssertionError(name)
 originals={k:v for k,v in vars(F).items() if isinstance(v,types.FunctionType) and v.__globals__ is vars(F)}
 ok('all_original_refresh_code_objects_identical',all(getattr(ctx,k).__code__ is v.__code__ for k,v in originals.items() if k!='sources'))
 ok('one_private_global_dictionary',len({id(getattr(ctx,k).__globals__) for k in originals if k!='sources'})==1)
 ok('original_refresh_V_not_mutated',F.V is not api and F.collect.__globals__['V'] is F.V)
 ok('private_refresh_uses_combined_inventory',ctx.collect.__globals__['V'] is api and ctx.owned_roots.__globals__['V'] is api)
 ok('original_refresh_filename_preserved',ctx.collect.__globals__['__file__']==F.__file__)
 ok('original_discovery_class_preserved',ctx.Discovery is F.Discovery and ctx.adapted.__code__ is F.adapted.__code__ and ctx.legacy_context.__code__ is F.legacy_context.__code__)
 ok('combined_collect_code_identical',api.collect.__code__ is F.V.collect.__code__)
 ok('combined_collect_calls_layered_interfaces',all(api.collect.__globals__[n] is getattr(api,n) for n in ('admit_observer_index','invocation_rows','collect_job','kind_of')))
 ok('recovery_binding_exact',api.recovery_binding==recovery and recovery['sha256']==R.RECOVERY_SHA)
 ok('B36_schema_explicit_originals_unchanged',api.kind_of({'schema':'s6c-historical-paced-b36-fast.v2'})=='b36' and F.V.kind_of({'schema':'s6c-historical-paced-b36-fast.v2'}) is None)
 ok('other_native_and_long_apis_identical',api.collect_long_c is F.V.collect_long_c and api.admit_long_native is F.V.admit_long_native and api.admit_complete_cell is F.V.admit_complete_cell)
 sources=ctx.sources();ok('all_three_layers_and_recovery_bound',all(any(Path(b['path']).stem==name for b in sources) for name in R.PINS) and recovery in sources)
 with tempfile.TemporaryDirectory(prefix='s6c_final_inventory_') as temp:
  root=Path(temp);p=root/'input.json';p.write_text('{"fixture": true}',encoding='utf-8');expected=R.bind(p)
  value,b=R.read_input([str(p),expected['sha256']]);reader=F.B.MetadataReader(root);original,ob=reader.read(p)
  ok('native_original_reader_same_buffer_binding',value==original and b==expected==ob)
  ok('native_original_helper_binding_identical',R.bind(F.__file__)==F.B.binding(F.__file__,Path(F.__file__).read_bytes()))
 outroot=F.PAYLOAD/'paced_controls/b36_fast_v2';pb=dict(path=(outroot/'MANIFEST.json').as_posix(),bytes=1,sha256='fixture')
 plan=dict(schema='s6c-historical-paced-b36-fast.v2',output_root=str(outroot),payload_root='G:/Just_Peachy_S6C/RUN')
 roots=ctx.owned_roots(plan,pb);ok('historical_only_owned_output_excluded',[r['path'] for r in roots]==[F.B.canonical(outroot)])
 wrong={**plan,'output_root':'G:/Just_Peachy_S6C/RUN'};bad('global_budget_root_rejected',lambda:ctx.owned_roots(wrong,pb))
 discovery=ctx.Discovery(roots,guard=lambda:None);unknown=F.PAYLOAD/'paced_controls/unlisted/MANIFEST.json'
 ok('unknown_namespace_retained',list(discovery.paths([Path(pb['path']),unknown]))==[unknown] and len(discovery.hidden)==1)
 b=lambda name:dict(path=name,bytes=1,sha256='0'*64)
 assembly=dict(recovery=recovery,late_pool_rollup=b('rollup'),fast_manifests=[b('fast')],legacy_manifests=[b('legacy')],automatic_legacy_long_manifests=[b('original_long')],required_continuous_manifests=[b(str(x)) for x in range(5)],sources=sources)
 ab=b('assembly');ob=b('observer');spec=R.spec_document(assembly,ab,ob);sb=b('spec')
 ok('finite_spec_copies_all_lists_without_projection',all(spec[k] is assembly[k] for k in ('fast_manifests','legacy_manifests','automatic_legacy_long_manifests','required_continuous_manifests')))
 bad('unresolved_observer_rejected',lambda:R.spec_document(assembly,ab,None))
 authority=dict(schema='s6c-inventory-refresh-authority.v1',status='AUTHORIZED_POST_CLOSURE_METADATA_CENSUS',spec=sb,helper=R.bind(F.__file__),integration_helper=R.bind(R.__file__),integration_readme=R.bind(R.HERE/'README_S6C_FINAL_INVENTORY_REFRESH_V1.md'),recovery=recovery,integration_sources=sources,all_model_paced_long_work_closed=True,no_concurrent_research_writers=True,completed_continuous_manifests=assembly['required_continuous_manifests'])
 R.authority_gate(F,assembly,spec,sb,authority);ok('explicit_original_and_integration_authority',True)
 for key,value in [('helper',R.bind(R.__file__)),('integration_helper',b('wrong')),('integration_readme',b('wrong')),('recovery',b('wrong')),('integration_sources',[]),('all_model_paced_long_work_closed',False),('no_concurrent_research_writers',False),('completed_continuous_manifests',assembly['required_continuous_manifests'][:4]),('status','DRAFT')]:
  a={**authority,key:value};bad('authority_rejects_'+key,lambda a=a:R.authority_gate(F,assembly,spec,sb,a))
 ok('originals_still_unchanged',F.V.collect.__globals__['admit_observer_index'] is F.V.admit_observer_index and F.collect.__globals__['sources'] is F.sources)
 result=dict(schema='s6c-final-inventory-integration-source-checks.v1',status='PASS_SOURCE_AND_TINY_GUARDS',checks=len(checks),names=checks,sources=sources+[R.bind(__file__)],actual_inventory=False,actual_cell_admission=False,current_owner_reads=False,models=0,scope='Private source contexts and synthetic authority/root fixtures only. No actual observer or runtime/cell metadata admitted; no old fixture suite repeated.')
 return F.B.write_new(Path(output).resolve(),result)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
