"""Tiny refresh checks; README_S6C_INVENTORY_REFRESH_V1.md gives both shell commands."""
import argparse, ast, json, tempfile, types
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import s6c_inventory_refresh_v1 as M

def run(output):
    names=[]
    def check(label,value):
        if not value: raise AssertionError(label)
        names.append(label)
    def reject(label,call):
        try:call()
        except (ValueError,KeyError,OSError): names.append(label)
        else:raise AssertionError('Expected rejection: '+label)
    with tempfile.TemporaryDirectory(prefix='s6c_refresh_') as tmp:
        root=Path(tmp);report=root/'report';payload=root/'payload'
        with patch.object(M,'REPORT',report),patch.object(M,'PAYLOAD',payload):
            for kind in M.V.FAST:
                family=M.V.FAST[kind]['family'];name='test_fast_v1';rr=report/family/name;pp=payload/family/name
                p=dict(schema=M.V.FAST[kind]['schema'],namespace=name,output_root=str(pp),payload_root=str(pp),report_root=str(rr),observer_policy={})
                if kind=='long_c':p.update(report_root=str(report/'long_session'/name),payload_root=str(payload/'long_session'/name))
                if kind in ('controls','b36'):p['payload_root']=str(payload)
                pb=dict(path=str((pp if kind in ('controls','b36') else rr)/'MANIFEST.json'))
                roots=M.owned_roots(p,pb)
                check(kind+'_exact_owned_root_count',len(roots)==(1 if kind in ('controls','b36') else 3 if kind=='long_c' else 2))
                check(kind+'_global_budget_not_excluded',str(payload) not in [r['path'] for r in roots])
                bad=deepcopy(p);bad['output_root']=str(payload)
                if kind in ('controls','b36','long_b36'):reject(kind+'_reject_global_output',lambda:M.owned_roots(bad,pb))
        owned=payload/'paced_controls'/'test_fast_v1';unknown=payload/'paced_controls'/'unknown_fast_v1'
        for p in (owned/'nested',unknown,payload/'epoch2'/'jobs',payload/'enrollment'):
            p.mkdir(parents=True);(p/'marker.json').write_text('{}')
        events=[];d=M.Discovery([dict(path=str(owned))],guard=lambda:events.append('guard'))
        walked=list(d.walk(payload));parents={Path(r[0]) for r in walked}
        check('owned_subtree_pruned',owned not in parents and owned/'nested' not in parents)
        check('unknown_fast_namespace_preserved',unknown in parents)
        check('offline_epoch_not_pruned',payload/'epoch2'/'jobs' in parents)
        check('enrollment_unchanged_by_wrapper',payload/'enrollment' in parents)
        check('only_exact_owned_glob_filtered',list(d.paths([owned/'MANIFEST.json',unknown/'MANIFEST.json']))==[unknown/'MANIFEST.json'])
        check('explicit_filtered_path_ledger',len(d.hidden)==2)
        check('quiet_guard_runs_during_walk',len(events)>=len(walked)+1)
        reject('duplicate_roots',lambda:M.Discovery([dict(path=str(owned))]*2))
        reject('overlapping_roots',lambda:M.Discovery([dict(path=str(owned)),dict(path=str(owned/'nested'))]))
        def failwalk(*a,**kw):kw['onerror'](OSError('injected metadata enumeration failure'));yield None
        with patch.object(M.os,'walk',failwalk):reject('walk_errors_fail_closed',lambda:list(d.walk(payload)))
        active=M.Discovery([],guard=lambda:(_ for _ in ()).throw(ValueError('active lease')))
        reject('active_lease_prevents_walk',lambda:list(active.walk(payload)))
        before=(M.B.collect_auxiliary,M.B.process_state,M.B.validate_native,M.V4.paced_adapter,M.V5.additive,M.V6.additive)
        collector=M.legacy_context(d,[])
        check('original_module_globals_unchanged',before==(M.B.collect_auxiliary,M.B.process_state,M.B.validate_native,M.V4.paced_adapter,M.V5.additive,M.V6.additive))
        check('private_collector_globals',collector.__globals__ is not M.B.__dict__)
        check('private_finite_owner_state',collector.__globals__['process_state'] is M.V3.process_state)
        check('original_receipt_normalizer_code_exact',collector.__globals__['normalize_native'].__code__ is M.B.normalize_native.__code__)
        check('normalizer_sees_private_finite_state',collector.__globals__['normalize_native'].__globals__['process_state'] is M.V3.process_state)
        reject('wrong_discovery_pattern_stops_compilation',lambda:M.adapted(M.V4,'paced_adapter',d,'not-a-real-pattern'))
        # Reverse the one discovery call and independently compare full AST.
        tree=ast.parse(Path(M.B.__file__).read_bytes());original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='collect')
        code_names=collector.__code__.co_names
        check('base_collect_only_walk_name_added','_discovery_walk' in code_names and set(code_names)-set(M.B.collect.__code__.co_names)=={'_discovery_walk'})
        check('base_collect_all_epoch_glob_patterns_exact',all(s in collector.__code__.co_consts for s in ('EPOCH*_EXECUTION_MANIFEST.json','epoch*/workers/*.json','epoch*/invocations/*/owner.json','epoch*/*PREDICTION_INDEX.json')))
    # In-memory exact-bound late pool schemas; no original result/index files read.
    data={}
    def add(name,value):
        raw=json.dumps(value).encode();b=M.B.binding(Path(tempfile.gettempdir())/name,raw);data[b['path']]=(value,b);return b
    receipt=add('synthetic_native_receipt.json',{});rb=add('synthetic_review.json',dict(status='PASS_COMPLETE_NATIVE_GRID_AND_OWNERS_CLOSED',orchestration='fixture'))
    jb=add('synthetic_results.json',dict(status='COMPLETE',requested=2,completed=2,worker_pool_joined=True,error=None,rows=[dict(receipt=receipt),dict(receipt=receipt)]))
    ib=add('synthetic_prediction_index.json',dict(status='COMPLETE',rows=[{},{}]))
    pool=dict(name='fixture',review=rb,results=jb,prediction_index=ib,parity={},requested=2,new_native_jobs=1,verified_reused_jobs=1)
    class Reader:
        def read(self,path,expected=None):
            d,b=data[M.B.canonical(path)]
            if expected is not None:M.require(b==expected,'Exact synthetic metadata binding')
            return d,b
    reader=Reader();inventory=dict(prediction_indexes=[dict(binding=ib)]);physical=[dict(receipt_bindings=[receipt])]
    rows,gaps=M.pool_coverage(reader,dict(rows=[pool]),inventory,physical)
    check('reused_receipt_is_one_reference_not_execution',not gaps and rows[0]['unique_receipt_references']==1 and rows[0]['adds_physical_attempts']==0)
    _,gaps=M.pool_coverage(reader,dict(rows=[pool]),inventory,[])
    check('missing_native_receipts_preserved_as_gap',gaps[0]['error']=='LATE_POOL_RECEIPTS_NOT_ENUMERATED')
    _,gaps=M.pool_coverage(reader,dict(rows=[pool]),dict(prediction_indexes=[]),physical)
    check('missing_late_index_preserved_as_gap',gaps[0]['error']=='LATE_POOL_INDEX_NOT_ENUMERATED')
    original=deepcopy(data[jb['path']][0])
    for label,change in [('partial',dict(status='PARTIAL_RESUMABLE')),('not_joined',dict(worker_pool_joined=False)),('error',dict(error='native failed')),('missing_rows',dict(rows=[]))]:
        data[jb['path']]=(original|change,jb)
        reject('late_pool_'+label,lambda:M.pool_coverage(reader,dict(rows=[pool]),inventory,physical))
    data[jb['path']]=(original,jb)
    # Only the already-authorized 13,120-byte rollup is admitted from the study.
    raw=M.ROLLUP.read_bytes();actual=json.loads(raw)
    check('actual_exact_six_pool_rollup_hash',M.hashlib.sha256(raw).hexdigest()==M.ROLLUP_SHA and len(raw)==13120)
    check('actual_six_pool_names',len(actual['rows'])==6 and {r['name'] for r in actual['rows']}==set(M.POOLS))
    check('actual_new_reuse_declared_totals',actual['counts']==dict(requested=3072,new_native_jobs=2512,verified_reused_jobs=560))
    b=M.B.write_new(output,dict(schema='s6c-inventory-refresh-source-checks.v1',status='PASS_SOURCE_AND_TINY_METADATA_ONLY',checks=len(names),names=names,sources=M.sources()+[M.B.binding(__file__,Path(__file__).read_bytes())],actual_rollup=M.B.binding(M.ROLLUP,raw),actual_collections=0,models=0,scope='Synthetic directories and in-memory metadata only, plus exact13KiB closed rollup. No real output tree/index/result/native/payload scan. No actual refresh spec or closure authorization created.'))
    return b

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args().output),indent=2))
