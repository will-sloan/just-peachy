"""Bounded additive contexts; README_S6C_EXECUTION_INVENTORY_V7.md."""
import argparse,ast,json,tempfile,types
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import s6c_execution_inventory_v7 as A
import test_s6c_execution_inventory_v7 as T

def run(output):
 done=[]
 def good(name,value=True):assert value,name;done.append(name)
 def reject(name,fn):
  try:fn()
  except (ValueError,KeyError,TypeError,OSError):good(name);return
  raise AssertionError('Invalid admission: '+name)
 output.mkdir(parents=True,exist_ok=False);r=A.base.MetadataReader(output)
 before=A.source_bindings();ctx=A.v2_context();g=ctx.admit_complete_cell.__globals__
 old={n:id(v) for n,v in vars(A.v4).items()};policy=A.protected_policy_v2()
 previous,pb=r.read(A.REPORT/'execution_inventory/v7_checks_v4/SOURCE_CHECKS.json')
 good('exact_78_prior_source_and_failure_checks',pb['sha256']=='1b7e7a75bc19ee78452cf8c0d28d69d24ddfe19de0b5e13e746e7a5960371341' and previous['checks']==78)
 good('prior_v1_context_source_exact',A.F.bind(A.CONTEXT_PATH)['sha256']=='55e8cff6f3803196e11e7387e3a458c8630cd8c198f5884e9d53bc7e7b209827')
 good('context_is_private',g is not vars(A) and g['FAST'] is not A.FAST)
 good('context_preserves_v1_wrapper',A.FAST['canonical']['wrapper']=='s6c_paced_epoch4_fast_v1.py' and g['FAST']['canonical']['wrapper']=='s6c_paced_epoch4_fast_v2.py')
 good('exact_v2_policy',policy['schema']=='s6c-protected-native-guard.v2' and policy['algorithm_source']==A.F.bind(A.HERE/A.V2_WRAPPERS['long_c']))
 good('policy_stable_after_path_calls',policy==A.protected_policy_v2())
 actual=[]
 for rel in ('paced_candidates/c065_main_fast_v2/MANIFEST.json','long_native_epoch4/epoch4_long_c065_o0_fast_v2/MANIFEST.json'):
  p,b=r.read(A.REPORT/rel);p,b,spec=A.admit_plan(r,b);kind=A.kind_of(p)
  good(kind+'_actual_v2_prepared_metadata',A.fast_version(p)==2);actual.append(dict(manifest=b,kind=kind,requested=len(p['jobs']) if 'jobs' in p else 1,status='PREPARATION_METADATA_ONLY'))
  for change in ('missing_policy','changed_policy','wrong_wrapper_source','v2_policy_in_v1','wrong_algorithm_source'):
   bad=deepcopy(p)
   if change=='missing_policy':bad.pop('protected_guard_policy')
   elif change=='changed_policy':bad['protected_guard_policy']['original_structural_code_sha256']['native']='0'*64
   elif change=='wrong_wrapper_source':bad['dependencies' if kind=='long_c' else 'sources']=[x for x in bad['dependencies' if kind=='long_c' else 'sources'] if Path(x['path']).name!=A.V2_WRAPPERS[kind]]
   elif change=='v2_policy_in_v1':bad['namespace']=bad['namespace'].replace('_fast_v2','_fast_v1')
   else:bad['protected_guard_policy']['algorithm_source']['sha256']='1'*64
   if change=='v2_policy_in_v1':reject(kind+'_'+change,lambda:A.fast_version(bad))
   else:reject(kind+'_'+change,lambda:g['validate_fast_sources'](bad,kind))
 # Compile the held tiny metadata fixture with the actual new context, never a worker.
 proxy=types.SimpleNamespace(**{**vars(A),**g})
 ns=dict(A=proxy,Path=Path,deepcopy=deepcopy,types=types,json=json,patch=patch,replace=T.replace)
 A.v5.compile_functions(A.HERE/'test_s6c_execution_inventory_v7.py',{'fixture'},ns,{'observer_fast_v1/attempts':'observer_fast_v2/attempts'})
 for kind in ('canonical','sentinel','cross'):
  for fault in (None,'v1_worker_argv','v1_observer_directory','missing_observer','retained_observer','wrong_guard'):
   with tempfile.TemporaryDirectory(prefix='s6c_v7_v2_') as tmp,patch.object(A.v3,'process_state',lambda *a:dict(alive=False,state='SYNTHETIC_CLOSED')):
    reader,j,p,b,spec,complete=ns['fixture'](Path(tmp),kind);p['namespace']='synthetic_fast_v2';p['protected_guard_policy']=policy
    docs=reader.fast_observer_receipts
    if fault=='v1_worker_argv':docs[0][0]['owner']['argv']=[x.replace('_fast_v2.py','_fast_v1.py') for x in docs[0][0]['owner']['argv']]
    elif fault=='v1_observer_directory':docs[0][1]['path']=docs[0][1]['path'].replace('observer_fast_v2','observer_fast_v1')
    elif fault=='missing_observer':del reader.fast_observer_receipts
    elif fault=='retained_observer':docs[1][0]['installations'][0]['restored']=False
    elif fault=='wrong_guard':p['protected_guard_policy']={};reject(kind+'_wrong_guard',lambda:g['validate_fast_sources'](p,kind));continue
    original=g['bound']
    def bound(reader,b):return (spec,b) if b=={} else original(reader,b)
    with patch.dict(g,{'bound':bound}):
     call=lambda:A.admit_complete_cell(reader,j,p,b,spec,state=lambda *a:dict(alive=False))
     if fault:reject(kind+'_'+fault,call)
     else:
      proof=call();good(kind+'_v2_exact_cell_context',proof['complete_binding']==complete and A.kind_of(p)==kind)
      row=A.collect_job(reader,j,p,b,spec);good(kind+'_one_physical_native_complete',row['status']=='COMPLETE' and row['native_session_complete'])
 good('old_module_globals_untouched',old=={n:id(v) for n,v in vars(A.v4).items()})
 # Validate the isolated function transforms independently of execution.
 tree=ast.parse(A.CONTEXT_PATH.read_bytes());transformed=[]
 for n in tree.body:
  if isinstance(n,ast.FunctionDef):transformed.append(n.name)
 good('every_context_function_accounted',set(transformed)=={n for n in vars(ctx) if n!='validate_fast_sources'}|{'validate_fast_sources'})
 good('same_shared_scanner',g['F'] is A.F)
 good('no_observer_default_bypass',not hasattr(A.base.MetadataReader(output),'fast_observer_receipts'))
 good('sources_unchanged',before==A.source_bindings())
 result=dict(schema='s6c-inventory-v7-additive-context-checks.v1',status='PASS_MODEL_FREE',checks=len(done),names=done,prior_checks=pb,prior_check_count=78,actual_prepared=actual,metadata_sources=r.sources,source_bindings=before+[A.F.bind(__file__),A.F.bind(A.HERE/'test_s6c_execution_inventory_v7.py')],scope='Tiny metadata fixtures and two already prepared v2 manifest declarations only. Prior78 and actual failed v1 metadata proof reused by exact receipt; not rerun. No full inventory, current runtime metadata, native events, model, PCM, assets, trajectories or storage scan.',models=0)
 return A.base.write_new(output/'SOURCE_CHECKS.json',result)

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(json.dumps(run(a.output),indent=2))
if __name__=='__main__':main()
