"""Replay exact S6C native observations and verify logical event parity. See README_S6C_NATIVE_REPLAY_V2.md."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import time
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
from s6c_common import *

# These are measured execution/release facts, not policy results. Actual native
# values remain in bound source events and are used for native timing analysis.
EXECUTION_FIELDS={'identity_compute_sec','policy_compute_sec','tracker_compute_sec',
    'scheduler_state_overhead_sec','release_watermark_lower_bound_sec',
    'release_after_all_lanes_closed','compute_finished_elapsed_sec','modeled_available_at_sec'}

def canonical(value):
    if isinstance(value,dict):return {k:canonical(v) for k,v in value.items() if k not in EXECUTION_FIELDS}
    if isinstance(value,list):return [canonical(v) for v in value]
    return value

def differences(expected,actual,path='',subset=False):
    if isinstance(expected,dict) and isinstance(actual,dict):
        if (set(expected)-set(actual)) or (not subset and set(expected)!=set(actual)):
            return [dict(path=path,expected_keys=sorted(expected),actual_keys=sorted(actual))]
        return [d for k in expected for d in differences(expected[k],actual[k],path+'/'+k,subset)]
    if isinstance(expected,list) and isinstance(actual,list):
        if len(expected)!=len(actual):return [dict(path=path,expected_length=len(expected),actual_length=len(actual))]
        return [d for i,(a,b) in enumerate(zip(expected,actual)) for d in differences(a,b,path+'/'+str(i),subset)]
    return [] if expected==actual else [dict(path=path,expected=expected,actual=actual)]

def run(epoch,results_paths,label):
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in label):raise ValueError('Simple output label required')
    spec_path=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json');spec=read(spec_path)
    for b in spec['execution_files']+spec['assets']:bind(b['path'],b['sha256'])
    sys.path.insert(0,str(Path(spec['root'])/'scripts'));sys.path.insert(0,str(Path(spec['root'])/'app'))
    from s6c_replay import load_evidence,run_policy,save_prediction,read_prediction
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    from edge_speech_pipeline.research_identity_v3 import ResearchGallery
    from s6c_execution import verify_job
    source_bindings=[bind(p) for p in results_paths]
    source_documents=[verified(b) for b in source_bindings]
    all_rows=[r for doc in source_documents for r in doc['rows']]
    declared_jobs=[j for doc in source_documents for j in verified(doc['jobs'])['jobs']]
    declared_grid={(j['candidate_id'],j['case_id'],j['asr_tap'],j['identity_tap']):j for j in declared_jobs}
    if len(declared_grid)!=len(declared_jobs):raise ValueError('Declared native source grid has duplicate cells; separate repeat indices')
    observed_grid={(r['candidate_id'],r['case_id'],r['asr_tap'],r['identity_tap']):r for r in all_rows}
    if len(observed_grid)!=len(all_rows) or not set(observed_grid)<=set(declared_grid):raise ValueError('Native result has duplicate/outside declared grid rows')
    declared_requested=sum(doc['requested'] for doc in source_documents)
    if declared_requested!=len(declared_jobs):raise ValueError('Declared requested count disagrees with frozen jobs')
    native_rows=[r for r in all_rows if r['status'] in ('COMPLETE','COMPLETE_REUSED')]
    failed_rows=[r for r in all_rows if r['status'] not in ('COMPLETE','COMPLETE_REUSED')]
    source_grid_complete=all(doc['status']=='COMPLETE' and doc['completed']==doc['requested']==len(doc['rows']) for doc in source_documents)
    seen=set();rows=[];checks=[];started=time.perf_counter();gallery_cache={}
    index_path=REPORT/epoch/(label+'_PREDICTION_INDEX.json')
    prior=read(index_path) if index_path.exists() else None
    prior_bindings={(r['candidate_id'],r['case_id'],r['stream'],r['identity_tap']):r['result'] for r in prior['rows']} if prior else {}
    for native in native_rows:
        admit_work(False)
        source=bind(native['receipt']['path'],native['receipt']['sha256']);receipt=verified(source)
        key_tuple=(receipt['candidate_id'],receipt['case_id'],receipt['asr_tap'],receipt['identity_tap'])
        if key_tuple in seen:raise ValueError('Duplicate candidate/case/route; repeat indices must remain separate')
        seen.add(key_tuple)
        evidence,vectors,_=load_evidence(source['path'],spec['execution_digest'],expected_receipt=source)
        profile_data=receipt['identity']['profile']
        if not any(p['profile']==profile_data for p in spec['profiles']):raise ValueError('Unregistered effective native profile')
        profile=ResearchProfile.from_dict(profile_data)
        telemetry=receipt['identity']['telemetry'];provider=None
        if telemetry:
            bind(telemetry['path'],telemetry['sha256']);provider=JsonSpatialProvider(Path(telemetry['path']))
        gallery_binding=receipt['identity']['gallery'];gallery=None
        if gallery_binding:
            manifest=verified(gallery_binding)
            if gallery_binding['sha256'] not in gallery_cache:
                gallery_cache[gallery_binding['sha256']]=ResearchGallery(Path(gallery_binding['path']),manifest['backend_sha256'],profile.identity.max_gallery_profiles)
            gallery=gallery_cache[gallery_binding['sha256']]
        value=run_policy(profile,provider,evidence,vectors,gallery)
        events=[json.loads(line) for line in Path(receipt['events']['path']).read_text(encoding='utf-8').splitlines()]
        native_decisions=[r['payload']['decision'] for r in events if r['event_type']=='speaker_decision']
        native_transcripts=[r['payload'] for r in events if r['event_type'].startswith('transcript_')]
        native_identity=[r['payload'] for r in events if r['event_type']=='identity_decision']
        mismatches=differences(canonical(value['decisions']),canonical(native_decisions),'/decisions')
        mismatches+=differences(canonical(value['transcript_events']),canonical(native_transcripts),'/transcript_events',subset=True)
        mismatches+=differences(canonical(value['identity_events']),canonical(native_identity),'/identity_events',subset=True)
        check=dict(candidate_id=receipt['candidate_id'],case_id=receipt['case_id'],asr_tap=receipt['asr_tap'],identity_tap=receipt['identity_tap'],
            source=source,status='PASS' if not mismatches else 'FAIL',decision_count=len(native_decisions),transcript_event_count=len(native_transcripts),
            identity_event_count=len(native_identity),mismatch_count=len(mismatches),mismatches=mismatches[:50])
        checks.append(check)
        save(REPORT/epoch/(label+'_NATIVE_REPLAY_PARITY.json'),dict(status='RUNNING' if not mismatches else 'FAIL',checks=checks,
            compared='All nested speaker-decision fields and every shared transcript/identity event field in exact sequence',
            excluded_execution_fields=sorted(EXECUTION_FIELDS),source_indices=source_bindings,helper=bind(__file__),utc=utc()))
        if mismatches:raise ValueError('Actual native/shared replay parity failed; preserved differences')
        identity=dict(schema='jp_s6c_policy_prediction.v1',execution_digest=spec['execution_digest'],profile=profile_data,
            source=source,telemetry=telemetry,cue_condition=receipt['identity']['cue_condition'],gallery=gallery_binding,
            gallery_condition=receipt['identity']['gallery_condition'],enrollment_tier=receipt['identity']['enrollment_tier'],
            evidence_support='Exact native v3 observations; measured logical policy parity',oracle_like=receipt['identity']['cue_condition']=='NOMINAL_GEOMETRY_DIAGNOSTIC',
            orchestrator=bind(__file__))
        metadata=dict(status='COMPLETE',schema='jp_s6c_prediction.v1',prediction_key=digest(identity),identity=identity,
            case_id=receipt['case_id'],stream=receipt['asr_tap'],identity_tap=receipt['identity_tap'],profile_id=receipt['candidate_id'],
            candidate_id=receipt['candidate_id'],recipe_id=receipt['recipe_id'],duration_sec=receipt['audio_duration_sec'])
        target=PAYLOAD/epoch/'native_predictions'/label/receipt['candidate_id']/receipt['case_id']/(receipt['asr_tap']+'_'+receipt['identity_tap']+'.json.gz')
        if target.exists():
            if key_tuple in prior_bindings:bind(target,prior_bindings[key_tuple]['sha256'])
            old=read_prediction(target)
            if any(old.get(k)!=v for k,v in metadata.items()):raise ValueError('Existing prediction metadata differs; new namespace required')
            semantic={k:v for k,v in value.items() if k!='policy_wall_sec'}
            prior_semantic={k:old.get(k) for k in semantic}
            mismatch=differences(canonical(semantic),canonical(prior_semantic),'/resumed_payload')
            if mismatch:raise ValueError('Existing prediction differs from fresh exact replay: '+str(mismatch[:3]))
            state='COMPLETE_REUSED'
        else:
            value.update(**metadata,execution_mode='NEW_NATIVE_INFERENCE_WITH_EXACT_SHARED_REPLAY_PARITY',
                oracle_like=identity['oracle_like'],created_utc=utc())
            save_prediction(target,value);state='COMPLETE'
        rows.append(dict(candidate_id=receipt['candidate_id'],case_id=receipt['case_id'],stream=receipt['asr_tap'],identity_tap=receipt['identity_tap'],
            recipe_id=receipt['recipe_id'],status=state,result=bind(target)))
        if len(rows)%24==0:print(json.dumps(dict(completed=len(rows),requested=len(native_rows),elapsed_sec=time.perf_counter()-started)),flush=True)
    completed_count=len(rows)
    for key,job in declared_grid.items():
        if key in seen:continue
        source_failure=observed_grid.get(key)
        rows.append(dict(candidate_id=job['candidate_id'],case_id=job['case_id'],stream=job['asr_tap'],identity_tap=job['identity_tap'],
            recipe_id=job['recipe_id'],status=source_failure['status'] if source_failure else 'MISSING_NATIVE_SOURCE',
            error=source_failure.get('error') if source_failure else 'Declared native job has no source result row',source_row=source_failure))
    result=dict(status='COMPLETE' if source_grid_complete and completed_count==declared_requested else 'PARTIAL_RESUMABLE',requested=declared_requested,completed=completed_count,rows=rows,
        failed_source_rows=failed_rows,source_grid_complete=source_grid_complete,source_declared_grid=[{k:doc.get(k) for k in ('requested','completed','status','jobs','case_ids','profile_routes')} for doc in source_documents],
        missing_source_rows=declared_requested-len(all_rows),case_ids=sorted({j['case_id'] for j in declared_jobs}),
        profile_routes=[dict(candidate_id=c,stream=a,identity_tap=i) for c,a,i in sorted({(j['candidate_id'],j['asr_tap'],j['identity_tap']) for j in declared_jobs})],
        source_indices=source_bindings,helper=bind(__file__),execution_manifest=bind(spec_path),elapsed_sec=time.perf_counter()-started,utc=utc())
    save(index_path,result)
    save(REPORT/epoch/(label+'_NATIVE_REPLAY_PARITY.json'),dict(status='PASS' if result['status']=='COMPLETE' else 'PARTIAL_SOURCE_GRID',checks=checks,prediction_index=bind(index_path),
        compared='All nested speaker-decision fields and every shared transcript/identity event field in exact sequence',
        excluded_execution_fields=sorted(EXECUTION_FIELDS),source_indices=source_bindings,helper=bind(__file__),utc=utc()))
    return {k:v for k,v in result.items() if k not in ('rows','profile_routes','source_indices')}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--epoch',default='epoch1');p.add_argument('--results',nargs='+',required=True);p.add_argument('--label',required=True)
    a=p.parse_args();print(json.dumps(run(a.epoch,a.results,a.label),indent=2))
