"""Reproduce a preserved inventory. README_S6C_INVENTORY_SNAPSHOT_REVIEW.md."""
from collections import Counter,defaultdict
from pathlib import Path
import argparse,hashlib,json,math,importlib.util

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
ROOT=REPORT/'execution_inventory/snapshot_v2'
INVENTORY_SHA='29deb7969df3c57de02493c9f4f8e1d9055d91f1e3d8afd24b6b5fa4470d0a8a'

def bind(path):
    p=Path(path);raw=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def exact(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('Snapshot buffer differs')
    return raw
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def canon(path):return str(Path(path).resolve())

def run(output):
    checks=0
    def yes(condition):
        nonlocal checks
        if not condition:raise AssertionError('Inventory independent check '+str(checks+1))
        checks+=1
    ib=bind(ROOT/'EXECUTION_INVENTORY.json');yes(ib['sha256']==INVENTORY_SHA);inv=json.loads(exact(ib))
    for b in inv['outputs'].values():exact(b);checks+=1
    metadata=json.loads(exact(inv['outputs']['metadata_sources']))
    resolved={};bysha={};metadata_bytes=0
    for item in metadata['read_sources']:
        source=item['source'];saved=item['preserved'];yes(saved['sha256']==source['sha256'] and saved['bytes']==source['bytes'])
        if saved['sha256'] not in bysha:
            raw=exact(saved);bysha[saved['sha256']]=json.loads(raw.decode('utf-8-sig'));metadata_bytes+=len(raw)
        resolved[canon(source['path']),source['sha256']]=bysha[source['sha256']]
    def lookup(b):return resolved[canon(b['path']),b['sha256']]
    for b in inv['source_snapshots']:exact(b['snapshot']);checks+=1
    code=next(b['snapshot'] for b in inv['source_snapshots'] if Path(b['snapshot']['path']).suffix=='.py')
    yes(code['sha256']=='655476f9ca94df06ed9df30c38191bef63e02d9323b9474ad26a79171d51b8ac')
    module_spec=importlib.util.spec_from_file_location('preserved_inventory_pure_checks',code['path']);module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
    module.STAGING=SIM/'staging/s6c/20260910T123540Z'
    pure=module.checks();yes(pure=={'status':'PASS','checks':34,'model_calls':0})
    rows=json.loads(exact(inv['outputs']['physical_json']));yes(len(rows)==inv['unique_physical_attempts_observed']==1451)
    yes(len({r['physical_id'] for r in rows})==len(rows))
    native=[r for r in rows if r['branch']=='S6C_EPOCH_NATIVE'];prefix=[r for r in rows if r['branch']=='ACTUAL_NATIVE_PREFIX_DIAGNOSTIC']
    yes(len(native)==1449 and sum(r['status']=='COMPLETE' for r in native)==1448 and len(prefix)==2)
    rawgroups=defaultdict(list)
    for (path,sha),value in resolved.items():
        if Path(path).name not in ('run_receipt.json','attempt_receipt.json'):continue
        physical=digest([value['pid'],value['creation_time'],value['started_utc'],value['job_key']])
        yes(digest(value['identity'])==value['job_key'])
        yes(type(value['pid']) is int and value['pid']>0 and type(value['creation_time']) in (int,float) and math.isfinite(value['creation_time']) and value['creation_time']>0)
        rawgroups[physical].append((value,dict(path=path,sha256=sha)))
    yes(set(rawgroups)=={r['physical_id'] for r in native})
    rank={'STARTED':0,'RUNNING':1,'FAILED':2,'COMPLETE':3}
    for row in native:
        raw=max((v for v,b in rawgroups[row['physical_id']]),key=lambda v:rank[v['status']])
        yes(raw['status']==row['status'] and raw['job_key']==row['job_key'] and raw['identity']['execution_digest']==row['execution_digest'])
        yes({(b['path'],b['sha256']) for v,b in rawgroups[row['physical_id']]}=={(canon(b['path']),b['sha256']) for b in row['receipt_bindings']})
        for name in ('candidate_id','case_id','recipe_id','asr_tap','identity_tap','actual_counts','worker_model_bundle_loads'):
            yes(raw.get(name)==row.get(name))
    sessions={canon(r['session_dir']) for r in rows if r['status']=='COMPLETE' and r.get('session_dir')}
    yes(len(sessions)==inv['complete_native_sessions_observed']==1450)
    yes(sum(not r.get('session_dir') for r in rows)==1)
    loads={}
    for r in rows:
        if r.get('worker_model_bundle_loads') is not None:
            key=str(r['pid'])+':'+str(r['creation_time']);loads[key]=max(loads.get(key,0),r['worker_model_bundle_loads'])
    yes(loads==inv['observed_worker_bundle_load_maxima']);yes(sum(loads.values())==45 and len(loads)==13)
    repeated=defaultdict(list)
    for row in rows:
        if row.get('job_key'):repeated[row['job_key']].append(row['physical_id'])
    yes({x['job_key']:x['physical_attempts'] for x in inv['repeated_exact_job_identities']}=={k:v for k,v in repeated.items() if len(v)>1})
    for branch,summary in inv['branch_summaries'].items():
        selected=[r for r in rows if r['branch']==branch];events=Counter()
        for r in selected:events.update(r.get('actual_counts') or {})
        yes(summary['physical_attempts']==len(selected) and summary['observed_event_counts']==dict(events))
        for output_name,key in [('elapsed_sec','elapsed_sec'),('native_elapsed_sec','native_elapsed_sec'),('process_cpu_sec','process_cpu_sec'),
            ('audio_duration_sec','audio_duration_sec'),('nested_bundle_admission_sec','bundle_admission_sec'),('nested_gallery_admission_sec','gallery_admission_sec')]:
            values=[r[key] for r in selected if r.get(key) is not None];actual=summary[output_name]
            yes(actual['observed_rows']==len(values) and actual['unavailable_rows']==len(selected)-len(values))
            yes(actual['total'] is None if not values else abs(actual['total']-sum(values))<1e-8)
    refs=set();status_counts=Counter()
    for item in inv['native_invocations']:
        records=lookup(item['rows_source']) if item['rows_source'] else {'rows':[]}
        rr=records.get('rows',[]);yes(len(rr)==item['recorded_row_references'])
        status_counts.update(r.get('status','UNSPECIFIED') for r in rr)
        refs.update((canon(r['receipt']['path']),r['receipt']['sha256']) for r in rr if r.get('receipt'))
    yes(dict(status_counts)==inv['native_index_row_references'])
    observed={(canon(b['path']),b['sha256']) for r in rows for b in r['receipt_bindings']}
    yes(len(refs)==1457 and len(refs&observed)==1444 and len(refs-observed)==13)
    yes(refs-observed=={(r['path'],r['sha256']) for r in inv['native_index_reference_coverage']['not_in_receipt_snapshot']})
    predrefs=0;predunique={}
    for item in inv['prediction_indexes']:
        index=lookup(item['binding']);yes(len(index['rows'])==item['rows'])
        for row in index['rows']:
            if not row.get('result'):continue
            b=row['result'];key=canon(b['path']),b['sha256'];predrefs+=1
            # Descriptive output-path namespaces, without opening predictions.
            parts=Path(b['path']).parts
            route='POLICY_ONLY_FROM_S6C_NATIVE_EVIDENCE' if 'policy_predictions' in parts else 'NATIVE_OBSERVATION_PROJECTION_NO_NEW_INFERENCE' if 'native_predictions' in parts else 'POLICY_ONLY_FROM_HISTORICAL_S6B_FEATURES' if row.get('recipe_id')=='N00' and 'predictions' in parts else 'UNCLASSIFIED_INDEXED_OUTPUT'
            if key in predunique:yes(predunique[key]==route)
            predunique[key]=route
    yes(predrefs==inv['prediction_index_output_references']==22552 and len(predunique)==inv['unique_indexed_prediction_outputs']==22552)
    yes(dict(Counter(predunique.values()))==inv['unique_prediction_outputs_by_route'])
    for owner in inv['owner_identity_summary']:
        yes(type(owner['pid']) is int and owner['pid']>0 and type(owner['creation_time']) in (int,float) and math.isfinite(owner['creation_time']) and owner['creation_time']>0)
        yes(owner['process_state']['alive'] in (True,False,None))
    yes(sum(r['process_state']['alive'] is True for r in inv['owner_identity_summary'])==5)
    yes(inv['status']=='PARTIAL_ACTIVE_STUDY_SNAPSHOT' and inv['audit_status']=='INCOMPLETE_WITH_FLAGS')
    yes(inv['process_closure']['flags']==[{'kind':'NATIVE_INDEX_REFERENCES_OUTSIDE_RECEIPT_ENUMERATION','count':13}])
    yes(inv['auxiliary']['enrollment']['actual_embedding_calls']==1976 and inv['auxiliary']['enrollment']['Q_embedding_calls']==0)
    yes(sum(x['neural_sessions'] for x in inv['auxiliary']['native_prefix'])==2)
    yes(inv['auxiliary']['long_native']['status']=='NOT_OBSERVED_YET')
    result=dict(status='PASS_SAVED_SNAPSHOT_ACCOUNTING',schema='s6c_inventory_snapshot_independent_review.v1',checks=checks,pure_fixtures=34,
        snapshot=ib,source=code,reviewer=bind(__file__),readme=bind(Path(__file__).with_name('README_S6C_INVENTORY_SNAPSHOT_REVIEW.md')),
        metadata_resolver=inv['outputs']['metadata_sources'],preserved_metadata_sources=len(metadata['read_sources']),unique_metadata_buffers=len(bysha),unique_metadata_bytes=metadata_bytes,
        physical_attempts=1451,completed_epoch_native=1448,completed_prefix=2,started_without_session=1,unique_epoch_job_keys=1442,
        observed_epoch_worker_bundle_loads=45,worker_identities_with_counters=13,prediction_references=22552,not_enumerated_native_index_references=13,
        scope='Reproduced using exact preserved metadata buffers and saved owner observations. No current receipt/status reread, current process census, waveform/vector/model/prediction/event-log read, or new inventory collection.',
        limitations=['The saved snapshot is an active partial interval, not completion or present-time status.','Counted API events are not hidden neural forward steps; cumulative loads use per-worker maxima and nested costs are not added to elapsed runtime.',
            'Prospective process_state guard accepts nonfinite/bool creation_time; all actual saved attempt and compact owner identities reviewed here are positive finite numbers. Preserve this source; future version should reject malformed identities before classifying closure.',
            'Generic future adapters for B36/additive long/HIL need separate source admission. Prepared cells do not count as physical execution.'])
    if Path(output).exists():raise ValueError('Preserve existing review')
    Path(output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8');return bind(output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    print(json.dumps(run(p.parse_args().output),indent=2))
