"""Private normalization context checks; README_S6C_CONTROLS_RECOVERY_NORMALIZER_V1.md."""
import argparse,json,types
from pathlib import Path
import s6c_controls_recovery_normalizer_v1 as R

def run(out):
 N=R.load('s6c_runtime_metadata_normalizer_v1',R.NORMALIZER_SHA);A=N.module('s6c_fast_observer_analysis_v1');V=N.module('s6c_execution_inventory_v7')
 C=R.load('s6c_controls_recovery_analysis_v1',R.ANALYSIS_SHA);reproduced=C.checks();assert reproduced['check_count']==23
 checks=[]
 def ok(n,v):assert v,n;checks.append(n)
 def bad(n,f):
  try:f()
  except (ValueError,KeyError,TypeError):checks.append(n);return
  raise AssertionError(n)
 rb=dict(path='UNREAD_SYNTHETIC_RECOVERY.json',sha256='r',bytes=1)
 analysis=C.build_context(A,V,rb)
 adapter=R.build_context(N,A,analysis,V,rb)
 ok('identical_original_run_code',adapter.run.__code__ is N.run.__code__)
 ok('private_globals',adapter.run.__globals__ is not N.run.__globals__)
 ok('original_module_loader_unchanged',N.run.__globals__['module'] is N.module)
 for name in ('historical_rows','analysis_chain','runtime_row','historical_tail','historical_condition','owners_closed','require_distinct_runtime_sessions'):
  ok('original_'+name,adapter.namespace[name] is getattr(N,name))
 facade=adapter.namespace['module']('s6c_fast_observer_analysis_v1')
 ok('analysis_metadata_facade',facade.sources is analysis.sources and facade.make_adapter is analysis.make_adapter and facade.write_new is A.write_new)
 ok('strict_inventory_facade',adapter.namespace['module']('s6c_execution_inventory_v7') is V)
 mb=dict(sha256='manifest',path='UNREAD_MANIFEST.json',bytes=1)
 rows=[dict(kind='historical',generation=g,manifest=mb) for g in ('baseline','research')];spec=dict(external_recovery=rb,requests=rows)
 R.finite_spec(spec,rb,'manifest');ok('separate_B00_B01_generations',True)
 bad('different_recovery',lambda:R.finite_spec(dict(spec,external_recovery={}),rb,'manifest'))
 bad('no_physical_inventory_reinterpretation',lambda:R.finite_spec(dict(spec,physical_inventories=[{}]),rb,'manifest'))
 bad('both_generations_required',lambda:R.finite_spec(dict(spec,requests=rows[:1]),rb,'manifest'))
 bad('no_other_manifest',lambda:R.finite_spec(spec,rb,'wrong'))
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
 sources=[N.exact(p)[1] for p in (Path(R.__file__),Path(__file__),R.HERE/'README_S6C_CONTROLS_RECOVERY_NORMALIZER_V1.md',Path(N.__file__),Path(C.__file__),R.HERE/C.README)]
 return A.write_new(out/'SOURCE_CHECKS.json',dict(status='PASS_PRIVATE_METADATA_CONTEXT_ONLY',checks=len(checks),names=checks,analysis_owner_checks=23,analysis_owner_receipt=reproduced,analysis_source_review='Complete helper and prior private-source context inspected; fixed controls manifest/generation, same original source/reader admission and no scientific-function mutation. No blocker.',sources=sources,actual_recovery_read=False,actual_normalization=False,models=0))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
