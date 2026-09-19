"""Audit executed S6B mechanisms; see README_S6B_MECHANISM_AUDIT.md.

Counts actual application lineage and native admission/endpoint observations.
No truth geometry, reference speakers, model session or hardware is used.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json
import math
import time
import numpy as np

import s6b_validation as validation

REPORT=validation.REPORT
EVENTS=('track_create','evidence_admit','track_commit','prototype_update','overlapping_prototype_update_suppressed',
        'track_capacity_rejection','angle_voice_conflict_reject','innovation_accumulate','innovation_change_proposal',
        'sensor_contradiction','sensor_quarantine','sensor_recovery','sensor_stale_anchor_audit',
        'prototype_escrow_hold','prototype_escrow_release','prototype_escrow_reject','prototype_escrow_expire',
        'prototype_rollback_checkpoint','prototype_rollback','prototype_slot_add','track_dormant','track_reactivate',
        'bayes_hypothesis_update','hsmm_duration_update','bounded_global_assignment','delayed_graph_update','label_revision')
ACTIVATION_KEYS={
    'N01_sensor_quarantine':'sensor_quarantine','N01_sensor_recovery':'sensor_recovery',
    'N03_escrow_hold':'prototype_escrow_hold','N03_escrow_release':'prototype_escrow_release',
    'prototype_rollback':'prototype_rollback','graph_path_update':'delayed_graph_update',
    'tracker_label_revision':'label_revision','CUSUM_change_proposal':'innovation_change_proposal',
    'multiprototype_slot_add':'prototype_slot_add','dormant_reactivation':'track_reactivate',
}


def tracker_audit(value,profile):
    decisions=value['decisions'];tracker=value.get('snapshot',{}).get('tracker')
    if tracker is None:return {'status':'NOT_INSTRUMENTED','reason':'Historical control has no S6B tracker snapshot','decision_count':len(decisions)}
    operations=Counter();states=Counter();reasons=Counter();cue_reasons=Counter();revisions=Counter();violations=[];latest={};first={}
    cue_positive=cue_valid_no_credit=cue_unavailable=spatial_nonzero=unknown=0
    for d in decisions:
        identifier=d['decision_id']
        if identifier in first:violations.append('duplicate_decision_id')
        first[identifier]=d;latest[identifier]=d.get('tracker_id')
        states[d['state']]+=1;reasons[d['reason']]+=1
        unknown+=d.get('anonymous_label')=='Unknown'
        cue=d.get('cue')
        if cue is not None:
            cue_reasons[cue['reason']]+=1
            effective=cue.get('qualified_bearing_deg') is not None and cue.get('reliability',0)>0
            cue_positive+=effective
            cue_valid_no_credit+=cue['reason']=='qualified' and not effective
            cue_unavailable+=not effective
            spatial_nonzero+=any(abs(v)>0 for v in cue.get('location_score_contribution',{}).values())
        for event in d.get('lineage',[]):
            name=event.get('event');operations[name]+=1
            if event.get('available_at_sec')!=d['available_at_sec']:violations.append('lineage_not_emitted_at_current_availability')
            if name=='track_commit':
                config=profile['tracker']
                if event['unique_evidence_sec']+1e-9<config['commit_evidence_sec'] or event['disjoint_evidence_count']<config['commit_disjoint_count']:
                    violations.append('commit_below_declared_independent_evidence')
            if name!='label_revision':continue
            target=event['revision_of'];replacement=event.get('replacement_track_id')
            if target not in first:violations.append('revision_target_not_yet_arrived');continue
            if first[target]['available_at_sec']>event['available_at_sec']:violations.append('future_revision_target')
            if latest[target]!=event.get('from_track_id'):violations.append('revision_from_track_disagrees_with_prior_latest')
            if event.get('original_available_at_sec')!=first[target]['available_at_sec']:violations.append('original_revision_time_changed')
            if not event.get('first_decision_preserved'):violations.append('first_decision_not_preserved')
            kind='known_to_unknown' if replacement is None else 'unknown_to_known' if latest[target] is None else 'known_to_known_reassociation'
            revisions[kind]+=1;latest[target]=replacement
            if replacement is None and (event.get('replacement_state')!='unknown' or event.get('replacement_committed')):
                violations.append('unknown_revision_retains_known_state')
    recorded=Counter(tracker['operations'])
    if operations!=recorded:violations.append('lineage_counter_differs_from_actual_snapshot')
    tracks=tracker.get('tracks',[]);config=profile['tracker']
    if len(tracks)>config['max_tracks']:violations.append('track_capacity_exceeded')
    if any(t['prototype_count']>config['max_prototypes'] for t in tracks):violations.append('prototype_capacity_exceeded')
    transcript_counts=Counter(r.get('revision_scope','unscoped') for r in value.get('transcript_events',[]) if r['event_type']=='transcript_label_revision')
    return {'status':'PASS' if not violations else 'FAIL','violations':dict(Counter(violations)),
            'decision_count':len(decisions),'unknown_decisions':unknown,'unknown_observation_fraction':unknown/len(decisions) if decisions else None,
            'decision_states':dict(states),'decision_reasons':dict(reasons),'operations':{k:operations[k] for k in EVENTS},
            'all_actual_operations':dict(operations),'snapshot_counter_parity':operations==recorded,'revision_classes':dict(revisions),
            'transcript_revision_scopes':dict(transcript_counts),'final_track_count':len(tracks),
            'final_committed_tracks':sum(t['committed'] for t in tracks),'final_escrow_pending_tracks':sum(t['escrow_pending'] for t in tracks),
            'per_track_unique_evidence_sec_sum':sum(t['unique_evidence_sec'] for t in tracks),
            'per_track_disjoint_evidence_count_sum':sum(t['disjoint_evidence_count'] for t in tracks),
            'cue_decisions':sum(cue_reasons.values()),'cue_reasons':dict(cue_reasons),
            'cue_effective_positive_credit':cue_positive,'cue_valid_but_zero_credit':cue_valid_no_credit,
            'cue_unavailable_or_zero_credit':cue_unavailable,'nonzero_spatial_score_decisions':spatial_nonzero,
            'activated':{key:operations[event]>0 for key,event in ACTIVATION_KEYS.items()},
            'structural_track_merges':{'capability_implemented':False,'observed':0},
            'structural_track_splits':{'capability_implemented':False,'observed':0},
            'evidence_scope':'Unique/disjoint totals are per anonymous track; overlapping spans across different proposed tracks are not a population speech denominator.',
            'unknown_scope':'Observation count fraction only; not sole-speech-time accuracy or speaker-attributed word error.'}


def upstream_audit(evidence,profile,common):
    b=evidence['native_events'];common.bind(b['path'],b['sha256'])
    counts=Counter();admission_reasons=Counter();windows=Counter();endpoint_reasons=Counter();errors=[]
    for line in Path(b['path']).read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        event=json.loads(line);kind=event['event_type'];p=event['payload']
        if kind=='research_embedding':counts['actual_embedding_calls']+=1
        if kind=='research_embedding_admission':
            counts['admission_opportunities']+=1;admission_reasons[p['reason']]+=1
            admitted=p['admitted'];counts['admitted']+=admitted;counts['rejected']+=not admitted
            windows[str(p['window_sec'])+(':admitted' if admitted else ':rejected')]+=1
            due=p['evidence_debt_due'];counts['N05_debt_due']+=due
            counts['N05_debt_due_admitted']+=due and admitted;counts['N05_debt_due_rejected']+=due and not admitted
            counts['cadence_audio_events']+=p['audio_event'];counts['cadence_cue_events']+=p['cue_event']
            e=profile['embedding'];since=p['since_last_observation_sec']
            can_shorten=e['cadence_policy']=='event_driven' and since is not None and e['frequent_hop_sec']-1e-9<=since<e['sparse_hop_sec']-1e-9
            debt_sole=can_shorten and due and not p['audio_event'] and not p['cue_event']
            cue_sole=can_shorten and p['cue_event'] and not p['audio_event'] and not due
            counts['N05_sole_debt_shorter_cadence_opportunities']+=debt_sole
            counts['N05_sole_debt_shorter_cadence_admissions']+=debt_sole and admitted
            counts['sole_cue_shorter_cadence_admissions']+=cue_sole and admitted
            if admitted and (p['reason']!='admitted' or p['selected_rms'] is None or p['selected_rms']<e['minimum_rms']):errors.append('admission_violates_logged_gate')
        if kind=='research_asr_full_dispatch_cost':
            counts['actual_asr_full_dispatch_records']+=1
            advisor=p.get('advisor')
            if advisor is not None:
                counts['N04_observed_dispatches']+=1;endpoint_reasons[advisor['reason']]+=1
                counts['N04_proposals']+=advisor['proposal'];counts['N04_accepted_proposals']+=advisor['accepted']
        if kind=='research_asr_reset':
            counts['actual_asr_resets']+=1
            counts['native_endpoint_resets']+=p['native_endpoint'];counts['advisory_endpoint_resets']+=p['advisory_endpoint']
            counts['advisory_only_resets']+=p['advisory_endpoint'] and not p['native_endpoint']
            counts['coincident_native_and_advisory_resets']+=p['advisory_endpoint'] and p['native_endpoint']
    if counts['admitted']!=counts['actual_embedding_calls'] or counts['actual_embedding_calls']!=len(evidence['features']):errors.append('admission_embedding_count_mismatch')
    if not counts['actual_asr_full_dispatch_records']:errors.append('missing_actual_full_dispatch_records')
    if counts['N04_accepted_proposals']!=counts['advisory_endpoint_resets']:errors.append('accepted_advisory_reset_count_mismatch')
    return {'status':'PASS' if not errors else 'FAIL','violations':errors,'counts':dict(counts),
            'admission_reasons':dict(admission_reasons),'window_admission_counts':dict(windows),'N04_endpoint_reasons':dict(endpoint_reasons),
            'N04_reset_limiter_activated':endpoint_reasons['rate_limited']>0,
            'N04_burst_breaker_opened':endpoint_reasons['circuit_opened']>0,
            'N05_debt_created_sole_earlier_admission':counts['N05_sole_debt_shorter_cadence_admissions']>0,
            'native_events':b,'neural_job_key':evidence['job_key'],
            'N04_stale_rejection_reason_instrumented':False,
            'caveat':'Endpoint adviser does not expose each internal stale/invalid rejection reason. No_proposal is not counted as stale. Debt due alone is not evidence of an extra observation. Accepted adviser proposals coinciding with native endpoint are not additional resets.'}


def aggregate(rows,upstream):
    groups={}
    for row in rows:
        key=row['profile_id'];g=groups.setdefault(key,{'outputs':0,'decisions':0,'unknown_decisions':0,'operations':Counter(),'cue_reasons':Counter(),
            'revision_classes':Counter(),'transcript_revision_scopes':Counter(),'activation_outputs':Counter(),'neural_job_keys':set(),
            'instrumented_outputs':0,'final_track_count_sum':0,'final_committed_tracks_sum':0})
        g['outputs']+=1;a=row['tracker']
        if row.get('neural_job_key'):g['neural_job_keys'].add(row['neural_job_key'])
        if a['status']=='NOT_INSTRUMENTED':continue
        g['instrumented_outputs']+=1;g['decisions']+=a['decision_count'];g['unknown_decisions']+=a['unknown_decisions']
        g['operations'].update(a['all_actual_operations']);g['cue_reasons'].update(a['cue_reasons']);g['revision_classes'].update(a['revision_classes'])
        g['transcript_revision_scopes'].update(a['transcript_revision_scopes']);g['activation_outputs'].update(k for k,v in a['activated'].items() if v)
        g['final_track_count_sum']+=a['final_track_count'];g['final_committed_tracks_sum']+=a['final_committed_tracks']
    for key,g in groups.items():
        g['neural_job_keys']=sorted(g['neural_job_keys'])
        g['unknown_observation_fraction']=g['unknown_decisions']/g['decisions'] if g['decisions'] else None
        g['activated_any']={name:g['operations'][event]>0 for name,event in ACTIVATION_KEYS.items()}
        for name in ('operations','cue_reasons','revision_classes','transcript_revision_scopes','activation_outputs'):g[name]=dict(g[name])
    native_counts=Counter();native_reasons=Counter()
    for a in upstream.values():native_counts.update(a['counts']);native_reasons.update(a['N04_endpoint_reasons'])
    return {'by_profile':groups,'deduplicated_native_jobs':len(upstream),'deduplicated_native_counts':dict(native_counts),
            'deduplicated_N04_endpoint_reasons':dict(native_reasons),
            'scope':'Per-profile decision counters count actual policy replays. Native admission/endpoint totals deduplicate by neural job key; they are not multiplied by the number of downstream trackers.'}


def write_audit(rows,upstream,index_path,manifest,mode,output_name,extras=None):
    complete=validation.read(index_path).get('status')=='COMPLETE'
    good=all(r['tracker']['status'] in ('PASS','NOT_INSTRUMENTED') for r in rows) and all(r['status']=='PASS' for r in upstream.values())
    result={'schema':'jp_s6b_actual_mechanism_audit_v1','status':'PASS' if good else 'FAIL','created_utc':validation.now(),
            'mode':mode,'index_population_complete':complete,'audited_prediction_or_canonical_outputs':len(rows),
            'summary':aggregate(rows,upstream),'rows':rows,'unique_upstream_jobs':upstream,
            'prediction_or_native_index':validation.binding(index_path),'execution_manifest':validation.binding(manifest),
            'auditor_code':validation.binding(__file__),'neural_calls':0,'hardware_invocations':0,
            'truth_oracle_inputs':False,'inactive_mechanism_rule':'Zero means not activated in this population. It is not proof that the implementation is absent or effective.',
            'contradiction_scope':'Sensor contradiction is an observable voice-prototype/location conflict, not a ground-truth direction or identity error.',
            'graph_scope':'Graph path recomputation and forward association revisions are reported separately. Structural track merge/split is not implemented.',
            'extras':extras or {}}
    if Path(output_name).name!=output_name or not output_name.endswith('.json'):raise ValueError('Report filename must remain within mechanism directory')
    validation.save(REPORT/'mechanisms'/output_name,result)
    return {'status':result['status'],'outputs':len(rows),'unique_upstream_jobs':len(upstream),'complete':complete,'report':str(REPORT/'mechanisms'/output_name)}


def pilot(manifest,index_path,output_name):
    spec,execution,replay,classes,common=validation.load_api(manifest)
    Profile,Provider,_,_=classes;recipes={r['recipe_id']:r for r in spec['recipes']}
    mains={(r['case_id'],r['stream']):r for r in validation.read(spec['input_index']['path'])['rows']}
    alternate={(r['case_id'],r['stream']):r for r in validation.read(spec['gain_index']['path'])['rows']}
    rows=[];upstream={}
    for indexed in validation.read(index_path)['rows']:
        if not indexed['status'].startswith('COMPLETE'):continue
        recipe=recipes[indexed['recipe_id']];main=mains[indexed['case_id'],indexed['stream']]
        job=execution.make_job(spec,recipe,main,alternate)
        if execution.verify_cached(job) is None:raise ValueError('Pilot row lacks actual exact evidence')
        rec=validation.read(Path(job['folder'])/'run_receipt.json');e=validation.read(rec['evidence']['path'])
        with np.load(e['vectors']['path'],allow_pickle=False) as archive:vectors=archive['vectors'].copy()
        p=Profile.from_dict(recipe['profile']);provider=Provider(Path(main['telemetry']['path'])) if p.tracker.cues_enabled else None
        value=replay.run_scheduler(p,provider,e,vectors,classes)
        rows.append({'case_id':indexed['case_id'],'stream':indexed['stream'],'profile_id':'NEURAL_'+indexed['recipe_id'],
                     'recipe_id':indexed['recipe_id'],'neural_job_key':job['job_key'],'tracker':tracker_audit(value,recipe['profile']),
                     'canonical_neural_profile_only':True,'source':validation.binding(Path(job['folder'])/'run_receipt.json')})
        upstream[job['job_key']]=upstream_audit(e,recipe['profile'],common)
    return write_audit(rows,upstream,index_path,manifest,'canonical_native_pilot',output_name,
                       {'population_caveat':'Canonical neural profiles are not the forty main comparison methods; N01/N03 may be disabled here. Main prediction audit is still required.'})


def predictions(manifest,index_path,output_name):
    spec,execution,replay,classes,common=validation.load_api(manifest)
    registry={r['profile_id']:r for r in validation.read(spec['effective_profile_registry']['path'])['profiles']}
    recipes={r['recipe_id']:r for r in spec['recipes']};rows=[];upstream={};sources={};values={}
    for indexed in validation.read(index_path)['rows']:
        b=indexed['result'];common.bind(b['path'],b['sha256']);value=validation.read(b['path']);pid=value['profile_id']
        if value.get('status')!='COMPLETE':raise ValueError('Incomplete prediction included')
        config=registry[pid]['profile']
        if value['identity']['profile']!=config or value['identity']['execution_digest']!=spec['execution_digest']:raise ValueError('Prediction code/profile differs from frozen registry')
        source=value['identity']['source'];job_key=source.get('recipe_job_key')
        row={'case_id':value['case_id'],'stream':value['stream'],'profile_id':pid,'recipe_id':value['recipe_id'],
             'neural_job_key':job_key,'tracker':tracker_audit(value,config),'source':b}
        rows.append(row)
        values[value['case_id'],value['stream'],pid]={
            'cue_enabled':config.get('tracker',{}).get('cues_enabled',False),'neural_job_key':job_key,
            'decisions':[{k:d.get(k) for k in ('decision_id','source_start_sec','source_end_sec','anonymous_label','cue')} for d in value['decisions']]}
        if job_key and job_key not in upstream:
            eb=source['evidence'];common.bind(eb['path'],eb['sha256']);e=validation.read(eb['path'])
            if e['job_key']!=job_key:raise ValueError('Prediction evidence job mismatch')
            upstream[job_key]=upstream_audit(e,recipes[value['recipe_id']]['profile'],common)
    # Descriptive paired outcomes at currently empty cue observations. Earlier
    # cue history can alter state, so this is not a counterfactual parity test.
    paired=defaultdict(Counter)
    for (cid,out,pid),value in values.items():
        parent=registry[pid].get('comparison_parent');other=values.get((cid,out,parent))
        if other is None or not value['cue_enabled']:continue
        if value['neural_job_key']!=other['neural_job_key']:continue
        lookup={d.get('decision_id'):d for d in other['decisions']}
        for d in value['decisions']:
            cue=d.get('cue') or {};mate=lookup.get(d.get('decision_id'))
            if mate is None or mate.get('source_start_sec')!=d.get('source_start_sec') or mate.get('source_end_sec')!=d.get('source_end_sec'):continue
            if cue.get('qualified_bearing_deg') is not None and cue.get('reliability',0)>0:continue
            paired[pid]['current_empty_or_zero_credit_cue_observations']+=1
            paired[pid]['same_first_anonymous_label_as_parent']+=d['anonymous_label']==mate['anonymous_label']
    return write_audit(rows,upstream,index_path,manifest,'actual_main_predictions',output_name,
                       {'current_empty_cue_parent_comparison':{k:dict(v) for k,v in paired.items()},
                        'paired_scope':'Only identical neural job/spans. State can retain earlier cue influence, so differences under a currently missing packet are not violations of disabled-cue parent parity.'})


def self_check(manifest,output_name='EXTRACTOR_CHECKS_V2.json'):
    spec,_,_,classes,_=validation.load_api(manifest)
    from edge_speech_pipeline.research_tracking_v2 import S6BTrackingConfig,S6BTracker
    from types import SimpleNamespace
    def vec(a,b):
        v=np.zeros(192,np.float32);v[0]=a;v[1]=b;return v/np.linalg.norm(v)
    def exercise(config,inputs):
        t=S6BTracker(config);ds=[]
        for i,(v,angle) in enumerate(inputs):
            cue=SimpleNamespace(angle_deg=angle,available_at_sec=i+1.,source_end_sec=i+1.,reliability=1.,energy=1.,valid=True,sequence=i)
            ds.append(t.update(v,i,i+1,i+1,spatial=cue))
        value={'decisions':ds,'transcript_events':[],'snapshot':{'tracker':t.snapshot()}}
        return tracker_audit(value,{'tracker':asdict(config)})
    quarantine=exercise(S6BTrackingConfig(mode='adaptive',cues_enabled=True,sensor_quarantine_enabled=True),
        [(vec(1,0),0),(vec(0,1),180),(vec(1,0),180),(vec(1,0),180),(vec(1,0),0),(vec(1,0),0)])
    escrow=exercise(S6BTrackingConfig(mode='adaptive',cues_enabled=True,update_escrow_enabled=True),[(vec(1,0),20),(vec(1,.1),20),(vec(1,.1),20)])
    import tempfile
    with tempfile.TemporaryDirectory(prefix='s6b_endpoint_extractor_',dir=REPORT/'mechanisms') as folder:
        path=Path(folder)/'events.jsonl'
        fixture=[]
        for native in (False,True):
            fixture.append({'event_type':'research_asr_full_dispatch_cost','payload':{'advisor':{'proposal':True,'accepted':True,'reason':'accepted'}}})
            fixture.append({'event_type':'research_asr_reset','payload':{'native_endpoint':native,'advisory_endpoint':True}})
        fixture.append({'event_type':'research_asr_full_dispatch_cost','payload':{'advisor':{'proposal':True,'accepted':False,'reason':'rate_limited'}}})
        def write_fixture(rows):
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
            return {'native_events':validation.binding(path),'features':[],'job_key':'fixture_only'}
        def guard(p,expected):
            value=validation.binding(p)
            if value['sha256']!=expected:raise ValueError('Fixture source changed')
            return value
        endpoint=upstream_audit(write_fixture(fixture),{'embedding':{}},SimpleNamespace(bind=guard))
        misspelled=[{**row,'event_type':'research_asr_dispatch_cost' if row['event_type']=='research_asr_full_dispatch_cost' else row['event_type']} for row in fixture]
        rejected=upstream_audit(write_fixture(misspelled),{'embedding':{}},SimpleNamespace(bind=guard))
    endpoint_pass=endpoint['status']=='PASS' and endpoint['counts']['N04_accepted_proposals']==2 and endpoint['counts']['advisory_only_resets']==1 and endpoint['counts']['coincident_native_and_advisory_resets']==1 and endpoint['N04_endpoint_reasons']['rate_limited']==1 and rejected['status']=='FAIL'
    passed=quarantine['status']=='PASS' and escrow['status']=='PASS' and quarantine['operations']['sensor_quarantine']==1 and quarantine['operations']['sensor_recovery']==1 and escrow['operations']['prototype_escrow_release']==1 and endpoint_pass
    result={'status':'PASS' if passed else 'FAIL','actual_tracker_generated_fixture':True,'empirical_method_result':False,
            'quarantine':quarantine,'escrow':escrow,'endpoint_schema_fixture':endpoint,'missing_full_dispatch_schema_rejected':rejected['status']=='FAIL',
            'endpoint_fixture_uses_constructed_native_schema_not_empirical_data':True,'auditor_code':validation.binding(__file__),'created_utc':validation.now()}
    if Path(output_name).name!=output_name or not output_name.endswith('.json'):raise ValueError('Fixture output must be a JSON filename')
    validation.save(REPORT/'mechanisms'/output_name,result);return {'status':result['status']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('self-check','pilot','predictions'))
    parser.add_argument('--epoch',default='epoch2');parser.add_argument('--manifest',type=Path);parser.add_argument('--index',type=Path);parser.add_argument('--output-name')
    args=parser.parse_args();manifest=args.manifest or REPORT/(args.epoch.upper()+'_EXECUTION_MANIFEST.json')
    if args.mode=='self-check':result=self_check(manifest,args.output_name or 'EXTRACTOR_CHECKS_V2.json')
    elif args.mode=='pilot':result=pilot(manifest,args.index or REPORT/args.epoch/'PILOT_NEURAL_INDEX.json',args.output_name or 'PILOT_MECHANISM_AUDIT.json')
    else:
        if args.index is None:raise ValueError('Main prediction index must be selected explicitly')
        result=predictions(manifest,args.index,args.output_name or 'CHALLENGE_MECHANISM_AUDIT.json')
    print(json.dumps(result,indent=2));raise SystemExit(1 if result['status']=='FAIL' else 0)


if __name__=='__main__':main()
