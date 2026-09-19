"""Independent private-context review; README_S6C_B36_POST_ANALYSIS_COMPONENT_V1.md."""
import argparse,json,types
from pathlib import Path
from unittest.mock import patch
import s6c_b36_v2_post_analysis_v1 as P

def run(out):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
 bindings=[P.A.exact(P.HERE/P.HELPER,'7dee44e452a72344dcefc53a39713cd2ba20409a99054b86b8c17b70c5099045')[1],P.A.exact(P.HERE/P.README,'542a46e884dda55543ab6da891986a576721b4d863248d32a032924b033c7ecb')[1]]
 reproduced=P.checks();assert reproduced['check_count']==23;checks=[]
 def ok(n,v):assert v,n;checks.append(n)
 inv,N=P.runtime();ctx=P.analysis_context(inv)
 b=dict(path=str(P.MANIFEST.resolve()),bytes=553498,sha256=P.MANIFEST_SHA)
 adapter,old=ctx.make_adapter('historical',b,b,[])
 ok('new_schema_in_actual_private_inventory','s6c-historical-paced-b36-fast.v2' in adapter.inventory.HISTORICAL)
 ok('strict_B36_collector_routed',adapter.inventory.collect_job is inv.collect_job)
 ok('exact_historical_scientific_objects',all(adapter.namespace[n] is old.run.__globals__[n] for n in P.A.SCIENCE['historical']))
 ok('old_historical_globals_unchanged',old.run.__globals__['inventory'] is old.inventory)
 ok('explicit_new_source_provenance',all(x in ctx.sources() for x in bindings) and any(Path(x['path']).name=='s6c_b36_v2_inventory_v1.py' for x in ctx.sources()))
 norm=P.normalization_context(N,ctx,inv)
 ok('normalization_private_facade_uses_same_inventory',norm.namespace['module']('s6c_execution_inventory_v7') is inv)
 ok('all_tail_condition_formulas_original',all(norm.namespace[n] is getattr(N,n) for n in ('historical_tail','historical_condition','runtime_row','owners_closed')))
 captured=[]
 with patch.object(Path,'exists',return_value=False),patch.object(P.A,'input_binding',return_value=b),patch.object(P,'runtime',return_value=(inv,N)),patch.object(P,'analysis_context',return_value=types.SimpleNamespace(prepare=lambda args:captured.append(vars(args)) or {'test':'no run'})):
  value=P.prepare(types.SimpleNamespace(manifest=[b['path'],b['sha256']],observer_index=['UNREAD_INDEX','unread']))
 ok('outer_prepare_routes_only_research_fixed_namespace',value=={'test':'no run'} and captured==[dict(kind='historical',namespace=P.NAME,observer_index=['UNREAD_INDEX','unread'],manifest=[b['path'],b['sha256']],index=None,admission=None,generation='research')])
 ok('old_fast_adapter_globals_preserved',P.A.prepare.__globals__['make_adapter'] is P.A.make_adapter and N.run.__globals__['module'] is N.module)
 source=P.A.write_new(out/'REPRODUCED_OWNER_CHECKS.json',reproduced)
 result=dict(status='PASS_SOURCE_AND_PRIVATE_CONTEXT_ONLY',source_review='Full held helper/README read. Fixed B36V2 manifest/research-only selection, explicit observer context and original A/N code retained. No blocker.',owner_checks=23,independent_checks=len(checks),names=checks,reproduced=source,sources=bindings+[P.A.bind(__file__),P.A.bind(P.HERE/'README_S6C_B36_POST_ANALYSIS_COMPONENT_V1.md')],actual_prepare=False,actual_closed_metadata=False,actual_analysis=False,models=0)
 return P.A.write_new(out/'REVIEW_RECEIPT.json',result)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
