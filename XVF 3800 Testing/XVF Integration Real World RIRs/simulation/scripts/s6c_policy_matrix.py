"""Shared v3 policy matrix over compatible genuine S6C neural evidence. README_S6C_POLICY_MATRIX.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
import time
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
from s6c_common import *

def exogenous_key(profile):
    """Conservative dependency boundary: no cache substitution for state-driven dispatch."""
    if profile['embedding']['cadence_policy']=='uncertainty' or profile['embedding']['cadence_cues_enabled'] or profile['xvf']['mode'] in ('endpoint_only','both'):
        return digest(dict(full=profile))
    return digest({k:deepcopy(profile[k]) for k in ('input','asr','segmentation','embedding','punctuation','runtime')})

def run(epoch,indices,label,panel='challenge',candidates=None):
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in label):raise ValueError('Simple output label required')
    spec_path=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json');spec=read(spec_path)
    for b in spec['execution_files']+spec['assets']:bind(b['path'],b['sha256'])
    sys.path.insert(0,str(Path(spec['root'])/'scripts'));sys.path.insert(0,str(Path(spec['root'])/'app'))
    from s6c_replay import load_evidence,run_policy,save_prediction,read_prediction
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    from edge_speech_pipeline.research_identity_v3 import ResearchGallery
    sources=[bind(p) for p in indices];source_map={};source_counts={}
    for source_index in sources:
        rows=verified(source_index)['rows']
        for row in rows:
            if row['status'] not in ('COMPLETE','COMPLETE_REUSED'):continue
            receipt=verified(row['receipt']);identity=receipt['identity']
            if receipt['status']!='COMPLETE' or identity['execution_digest']!=spec['execution_digest']:raise ValueError('Wrong native epoch/status')
            key=(receipt['case_id'],receipt['asr_tap'],receipt['identity_tap'],exogenous_key(identity['profile']))
            source_counts[key]=source_counts.get(key,0)+1
            # Deterministic supplied index order; no selection using predictions.
            source_map.setdefault(key,row['receipt'])
    inputs={(r['case_id'],r['stream']):r for r in verified(spec['input_index'])['rows']}
    case_ids=sorted(verified(spec['panel'])['case_ids']) if panel=='challenge' else sorted({r[0] for r in inputs})
    selected=[p for p in spec['profiles'] if p['recipe_id']!='N00' and (not candidates or p['candidate_id'] in candidates)]
    if not selected:raise ValueError('No selected profiles')
    if candidates and set(candidates)!={p['candidate_id'] for p in selected}:raise ValueError('Unknown/unsupported requested profile')
    gallery_rows=verified(spec['gallery_index'])['rows'] if spec.get('gallery_index') else []
    variants={(r['case_id'],r['stream'],r['condition']):r['telemetry'] for r in verified(spec['cue_variant_index'])['rows']} if spec.get('cue_variant_index') else {}
    planned=[]
    for cid in case_ids:
        for p in selected:
            source_key=(cid,p['asr_tap'],p['identity_tap'],exogenous_key(p['profile']))
            if source_key not in source_map:raise ValueError('Missing compatible actual neural source '+str(source_key[:3])+' '+p['candidate_id'])
            gal=None
            if p['gallery_condition']!='NONE':
                match=[r for r in gallery_rows if r['gallery_condition']==p['gallery_condition'] and r['enrollment_tier']==p['enrollment_tier'] and r.get('case_id') in (None,cid)]
                if len(match)!=1:raise ValueError('Exact registered gallery assignment missing or ambiguous')
                gal=match[0]['manifest']
            cue=None
            if p['cue_condition']=='REAL_ALIGNED_CUES':cue=inputs[cid,p['asr_tap']]['telemetry']
            elif p['cue_condition']!='CUES_OFF':cue=variants[cid,p['asr_tap'],p['cue_condition']]
            planned.append((cid,p,source_map[source_key],gal,cue,source_counts[source_key]))
    target_index=REPORT/epoch/(label+'_PREDICTION_INDEX.json')
    previous=read(target_index) if target_index.exists() else None
    previous_map={(r['candidate_id'],r['case_id'],r['stream'],r['identity_tap']):r['result'] for r in previous['rows']} if previous else {}
    rows=[];gallery_cache={};evidence_cache={};last_case=None;started=time.perf_counter();last_heartbeat=0.
    plan_binding=save(REPORT/epoch/(label+'_POLICY_PLAN.json'),dict(status='REGISTERED_EXACT_POLICY_ROWS',epoch=epoch,source_indices=sources,
        helper=bind(__file__),execution_manifest=bind(spec_path),panel=panel,candidate_ids=sorted({p['candidate_id'] for p in selected}),case_ids=case_ids,
        rows=[dict(case_id=cid,candidate_id=p['candidate_id'],stream=p['asr_tap'],identity_tap=p['identity_tap'],source=s,gallery=g,telemetry=c,
            compatible_source_count=n,selection='First supplied immutable index row; no outcome selection') for cid,p,s,g,c,n in planned]),immutable=True)
    for cid,p,source,gal_binding,cue_binding,n in planned:
        admit_work(False)
        if cid!=last_case:evidence_cache={};last_case=cid
        if source['sha256'] not in evidence_cache:
            evidence,vectors,_=load_evidence(source['path'],spec['execution_digest'],expected_receipt=source)
            native_identity=evidence['identity']
            if native_identity['asr_audio']!=inputs[cid,p['asr_tap']]['audio'] or native_identity['identity_audio']!=inputs[cid,p['identity_tap']]['audio']:raise ValueError('Source route does not bind exact canonical input pair')
            for b in (native_identity['asr_audio'],native_identity['identity_audio']):bind(b['path'],b['sha256'])
            evidence_cache[source['sha256']]=(evidence,vectors)
        evidence,vectors=evidence_cache[source['sha256']]
        if exogenous_key(p['profile'])!=exogenous_key(evidence['identity']['profile']):raise ValueError('Changed real frontend requires fresh inference')
        full_dependent=p['neural_dependency']=='FULL_PROFILE_AND_CUES'
        if full_dependent and (p['profile']!=evidence['identity']['profile'] or cue_binding!=evidence['identity']['telemetry'] or gal_binding!=evidence['identity']['gallery']):
            raise ValueError('State-dependent native schedule requires exact original full policy/cues/gallery')
        profile=ResearchProfile.from_dict(p['profile']);gallery=None;provider=None
        if gal_binding:
            manifest=verified(gal_binding)
            if len(manifest['profiles'])>profile.identity.max_gallery_profiles:raise ValueError('Cached gallery exceeds requesting profile capacity')
            if gal_binding['sha256'] not in gallery_cache:
                gallery_cache[gal_binding['sha256']]=ResearchGallery(Path(gal_binding['path']),manifest['backend_sha256'],profile.identity.max_gallery_profiles)
            gallery=gallery_cache[gal_binding['sha256']]
        if cue_binding:
            bind(cue_binding['path'],cue_binding['sha256']);provider=JsonSpatialProvider(Path(cue_binding['path']))
        identity=dict(schema='jp_s6c_policy_prediction.v1',execution_digest=spec['execution_digest'],profile=p['profile'],source=source,
            telemetry=cue_binding,cue_condition=p['cue_condition'],gallery=gal_binding,gallery_condition=p['gallery_condition'],enrollment_tier=p['enrollment_tier'],
            evidence_support='Exact native v3 observations and waveform supports; unchanged dependency-checked neural frontend',
            native_profile_may_differ_only_in_exogenous_policy=not full_dependent,neural_dependency_key=exogenous_key(p['profile']),
            oracle_like=p['cue_condition']=='NOMINAL_GEOMETRY_DIAGNOSTIC',orchestrator=bind(__file__))
        metadata=dict(status='COMPLETE',schema='jp_s6c_prediction.v1',prediction_key=digest(identity),identity=identity,
            case_id=cid,stream=p['asr_tap'],identity_tap=p['identity_tap'],profile_id=p['candidate_id'],candidate_id=p['candidate_id'],
            recipe_id=p['recipe_id'],duration_sec=inputs[cid,p['asr_tap']]['duration_sec'])
        target=PAYLOAD/epoch/'policy_predictions'/label/p['candidate_id']/cid/(p['asr_tap']+'_'+p['identity_tap']+'.json.gz')
        key=(p['candidate_id'],cid,p['asr_tap'],p['identity_tap'])
        if target.exists():
            if key in previous_map:bind(target,previous_map[key]['sha256'])
            old=read_prediction(target)
            if any(old.get(k)!=v for k,v in metadata.items()):raise ValueError('Existing output dependency/metadata mismatch')
            if key not in previous_map:
                from s6c_native_replay_v3 import canonical,differences
                fresh=run_policy(profile,provider,evidence,vectors,gallery)
                semantic={k:v for k,v in fresh.items() if k!='policy_wall_sec'}
                mismatch=differences(canonical(semantic),canonical({k:old.get(k) for k in semantic}),'/resumed_payload')
                if mismatch:raise ValueError('Interrupted-resume semantic payload differs from fresh shared replay')
            status='COMPLETE_REUSED'
        else:
            value=run_policy(profile,provider,evidence,vectors,gallery)
            value.update(**metadata,execution_mode='VERIFIED_NATIVE_CACHE_PLUS_INCREMENTAL_REPLAY',oracle_like=identity['oracle_like'],created_utc=utc())
            save_prediction(target,value);status='COMPLETE'
        rows.append(dict(candidate_id=p['candidate_id'],case_id=cid,stream=p['asr_tap'],identity_tap=p['identity_tap'],recipe_id=p['recipe_id'],status=status,result=bind(target)))
        if time.monotonic()-last_heartbeat>20:
            progress=dict(status='RUNNING',requested=len(planned),completed=len(rows),current_candidate=p['candidate_id'],current_case=cid,
                elapsed_sec=time.perf_counter()-started,new_native_jobs=0,utc=utc())
            save(REPORT/epoch/(label+'_PROGRESS.json'),progress);print(json.dumps(progress),flush=True);last_heartbeat=time.monotonic()
    result=dict(status='COMPLETE',requested=len(planned),completed=len(rows),rows=rows,case_ids=case_ids,plan=plan_binding,
        profile_routes=[dict(candidate_id=p['candidate_id'],stream=p['asr_tap'],identity_tap=p['identity_tap']) for p in selected],
        source_indices=sources,helper=bind(__file__),elapsed_sec=time.perf_counter()-started,utc=utc())
    save(target_index,result);return {k:v for k,v in result.items() if k not in ('rows','profile_routes','source_indices')}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--epoch',default='epoch1');p.add_argument('--indices',nargs='+',required=True)
    p.add_argument('--label',required=True);p.add_argument('--panel',choices=('challenge','all'),default='challenge');p.add_argument('--candidates',nargs='*')
    a=p.parse_args();print(json.dumps(run(a.epoch,a.indices,a.label,a.panel,a.candidates),indent=2))
