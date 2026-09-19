"""Bounded C065 actual review; README_S6C_REVIEW_C065_PACED_ACTUAL_V1.md."""
import argparse, hashlib, json, math, statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import s6c_execution_inventory_v7 as V

R=V.REPORT;B=V.base
AUTH={
 'result':('paced_analysis/c065_main_analysis_fast_v2/RESULT.json','560a750b273ea7d4aa71fcbdcc058979a66953d57b60c8bab71af2cbbde2a683'),
 'request':('fast_post_analysis_admission/canonical/c065_main_analysis_fast_v2/REQUEST.json','fd3c5dafc0eb4fdbb934e9007b09b398f114755e4f2e6ddb0afa9c3284f73b1c'),
 'observer':('fast_post_analysis/observer_indices/C065_MAIN_FAST_V2_OBSERVER_INDEX_V1.json','240ba9353dae54845f709f0b9be849edd6430da7dce39c08a6bdc108bfe9a563')}

def review(output):
    V.require(not (R/'PACED_QUIET_OWNER.json').exists(),'Quiet lease blocks actual review')
    V.require(not output.exists(),'Fresh review output required');output.mkdir(parents=True)
    reader=B.MetadataReader(output);checks=0
    def ck(value,label):
        nonlocal checks
        V.require(value,label);checks+=1
    def same(a,b,label):ck(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-7),label)
    def read(b):return V.bound(reader,b)[0]
    docs={};bindings={}
    for k,(p,h) in AUTH.items():
        d,b=reader.read(R/p);ck(b['sha256']==h,'Exact '+k);docs[k]=d;bindings[k]=b
    result=docs['result'];request=docs['request'];observer=docs['observer']
    ck(result['status']=='COMPLETE' and result['requested']==result['completed']==40 and result['failed']==0,'Complete40 denominator')
    ck(result['new_neural_calls']==0 and result['policy_replay_performed'] is True,'Post-analysis scope')
    ck(request['observer_index']==bindings['observer'],'Request observer authority')
    ck(len(observer['receipts'])==41,'Forty worker and one parent observer exit')
    V.admit_observer_index(reader,bindings['observer'])
    plan,pb,spec=V.admit_plan(reader,result['manifest'])
    ck(pb['sha256']=='f96b1efc02205ce66f16004a4c92cd1a68c7b8b06de4b9b27cefc4a9668cbab1','Actual prepared C065 manifest')
    index,ib=V.admit_paced_index(reader,result['paced_index'],plan,pb)
    ck(ib['sha256']=='9918c5c2e918878ec6912bdc1cb3fc6cd075d11b6c9254a61c24c44099c76de8','Actual closed index')
    inv,owners=V.invocation_rows(reader,plan,pb);V.ensure_invocations_closed(inv,owners)
    ck(len(inv)==1 and inv==result['metadata_admission']['invocations'],'Exact admitted invocation chain')
    ck(inv[0]['row_reference_counts']=={'COMPLETE':40},'No resumed/reused successful cells in this batch')
    ck(all(o['process_state']['alive'] is False for o in owners),'Current coordinator owners closed')
    ck(plan['candidates']==['C065'] and plan['panel_mode']=='full16_plus4','Exact ordinary panel scope')
    measures={}
    for b in result['cell_measurements']:
        m=read(b);ck(m['job_id'] not in measures,'Unique cell measurement');measures[m['job_id']]=(m,b)
    parities={p['job_id']:p for p in result['parity']}; refs={r['job_id']:r for r in index['rows']}
    jobs={j['job_id']:j for j in plan['jobs']}
    ck(set(measures)==set(parities)==set(refs)==set(jobs) and len(jobs)==40,'All exact job keys once')
    produced={};repetition_rows=[]
    for b in result['indices']:
        d=read(b);rep=d['repetition'];wanted={k for k,j in jobs.items() if j['repetition']==rep}
        ck(d['status']=='COMPLETE' and d['requested']==d['completed']==len(d['rows'])==len(wanted),'Separate repetition denominator')
        got=set()
        for r in d['rows']:
            key=(r['candidate_id'],r['case_id'],r['stream'],r['identity_tap'],r['repetition'])
            matches=[j for j in jobs.values() if (j['candidate_id'],j['case_id'],j['asr_tap'],j['identity_tap'],j['repetition'])==key]
            ck(len(matches)==1,'Produced exact route/repetition');jid=matches[0]['job_id'];got.add(jid)
            ck(jid not in produced and r['measurement']==measures[jid][1] and r['native_completion']==refs[jid]['completion'],'Prediction index joins exact measurement/completion')
            produced[jid]=r
        ck(got==wanted,'No flattened repetition grid');repetition_rows.append(dict(repetition=rep,cells=len(got),unique_cases=len(d['case_ids']),binding=b))
    ck(set(produced)==set(jobs),'All40 converted prediction bindings retained')
    grouped=defaultdict(list); totals=Counter();turnstatuses=Counter();decisionstatuses=Counter();sourcecells=[];examples=[];nativeids=set();owners_seen=set();clock_reversals=[]
    def percentile(values,q):
        v=sorted(values);x=(len(v)-1)*q;i=int(x);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(x-i)
    for jid,job in jobs.items():
        V.require(not (R/'PACED_QUIET_OWNER.json').exists(),'New quiet lease stops review at cell boundary')
        m,mb=measures[jid];chain=V.admit_complete_cell(reader,job,plan,pb,spec)
        native=chain['native'];complete=chain['complete'];cell=chain['cell'];measurement=m['measured_cell'];parity=m['parity']
        ck(m['completion']==refs[jid]['completion']==chain['complete_binding'] and m['native_result']==chain['native_binding'] and m['cell_result']==chain['cell_binding'],'Exact closed cell/native chain')
        ck(m['status']=='COMPLETE' and m['candidate_id']=='C065' and m['asr_tap']==m['identity_tap']==job['asr_tap'],'Same-tap C065 output')
        ck(cell['source_kind']=='CANONICAL_SINGLE_SCENE_PAIR' and cell['source_offset_samples']==cell['inserted_gap_samples']==0 and cell['actual_execution_epoch']=='epoch4','Single scene source/epoch scope')
        ck(native['resident_bundle_loads']==native['resident_sessions_created']==1 and native['hardware_invocations']==0 and native['live_owned_lanes']==[],'One actual host bundle/session and joined lanes')
        ck(native['status']=='COMPLETE' and complete['all_owned_processes_closed'] is True,'Actual native plus outer closure')
        session=native['final_telemetry']['session_dir'];ck(session not in nativeids,'Distinct native sessions');nativeids.add(session)
        for o in complete['owned_processes']:
            ck(V.process_state(o['pid'],o['creation_time'])['alive'] is False,'Actual recorded child owner closed');owners_seen.add((o['pid'],o['creation_time']))
        ck(measurement==complete['measurement'],'Exact measured cell copy')
        same(measurement['source_sec'],native['source_duration_sec'],'Exact source duration')
        for a,b in [('native_elapsed_sec','native_elapsed_sec'),('model_startup_sec','model_load_sec'),('original_observed_worker_sec','total_observed_worker_sec')]:same(measurement[a],native[b],'Exact nested '+a)
        ck(measurement['completed_cell_wall_sec']>=measurement['original_observed_worker_sec']>=measurement['native_elapsed_sec']>0,'Nested wall scopes')
        phase=measurement['phase_observations'];tr=m['trajectory'];n=tr['samples']
        ck(n==native['process_sample_count']==phase['process_samples'],'Native sample denominator')
        ck(phase['exact_eof_drain_sec'] is None,'Exact EOF drain unavailable')
        same(phase['terminal_after_finalization_observed_sec'],tr['terminal']['elapsed_from_native_launch_sec'],'Terminal phase time')
        same(phase['max_sample_gap_sec'],tr['max_sample_gap_sec'],'Exact native sample gap copy')
        ck(tr['terminal']['phase']=='terminal_after_finalization' and tr['terminal']['state']=='COMPLETED','Terminal post-finalization observation')
        same(tr['terminal']['telemetry']['source_duration_sec'],measurement['source_sec'],'Full observed source cursor')
        ck(m['external_process_samples']==complete['external_process_samples'],'External sample denominator')
        for stats in list(tr['process'].values())+list(tr['telemetry'].values())+[tr['event_queue_backlog']]:
            ck(stats['observed']+stats['missing']==n,'Observed/missing native sample partition')
        for stats in m['external_process_statistics'].values():ck(stats['observed']+stats['missing']==m['external_process_samples'],'Observed/missing external sample partition')
        for stats in tr['process'].values():
            if stats['first_observed'] is not None and stats['last_observed'] is not None and stats['observed']>1:
                same(stats['sampled_first_to_last_delta'],stats['last_observed'][1]-stats['first_observed'][1],'Native sampled counter delta')
                same(stats['sampled_interval_sec'],stats['last_observed'][0]-stats['first_observed'][0],'Native sampled counter interval')
        counts=m['actual_events']['event_counts'];ck(counts==native['event_counts'],'Actual event counts equal native joined result')
        ck(parity=={k:v for k,v in parities[jid].items() if k!='job_id'} and parity['status']=='PASS' and parity['mismatch_count']==0,'Exact held logical parity result')
        for a,b in [('embedding_calls','research_embedding'),('segmentation_calls','research_segmentation'),('asr_observations','research_asr_observation'),('decision_events','speaker_decision'),('identity_events','identity_decision')]:ck(parity[a]==counts.get(b,0),'Actual parity event denominator '+a)
        ck(parity['transcript_events']==sum(v for k,v in counts.items() if k.startswith('transcript_')),'All emitted transcript events')
        emission_groups=defaultdict(list);origin=datetime.fromisoformat(m['actual_events']['source_started']['wall_time_utc'])
        for e in m['actual_events']['emissions']:
            t=(datetime.fromisoformat(e['emitted_wall_time_utc'])-origin).total_seconds()
            ck(abs(t-e['emitted_from_source_started_sec'])<=5e-7,'UTC epoch-float versus datetime subtraction within0.5microsecond')
            ck(abs(t-e['source_time_sec']-e['emission_minus_source_cursor_sec'])<=5e-7,'Emission/source cursor epoch-float precision')
            emission_groups[e['event_type']].append(e)
        for kind,es in emission_groups.items():
            summary=m['actual_events']['summary'][kind];ck(summary['count']==len(es)==counts[kind],'Emission count copied exactly')
            for field,key in [('elapsed_from_source_started_sec','emitted_from_source_started_sec'),('emission_minus_source_cursor_sec','emission_minus_source_cursor_sec')]:
                values=[e[key] for e in es];st=summary[field];ck(st['observed']==len(es) and st['missing']==0,'Emission observed denominator')
                for stat,value in [('min',min(values)),('max',max(values)),('mean',statistics.mean(values)),('p50',percentile(values,.5)),('p95',percentile(values,.95))]:same(st[stat],value,'Independent emission summary '+stat)
        scheduler=m['native_scheduler'];ck(scheduler==native['final_telemetry']['scheduler'],'Exact final scheduler copy')
        ck(scheduler['closed'] is True and scheduler['pending_events']==0 and scheduler['watermarks']=={'speaker':'closed','asr':'closed'},'All scheduler lanes drained')
        identity=scheduler['identity'];ck(identity['mode']=='none' and identity['gallery'] is None and identity['query_calls']==identity['comparisons']==0,'Disabled naming means zero queries/comparisons')
        loads=m['native_gallery_load_events'];ck(len(loads)==1 and loads[0]['mode']=='none' and loads[0]['loaded_count']==0 and loads[0]['private_gallery_accessed'] is False,'One none-mode admission event, zero loaded profiles')
        names=m['actual_name_emissions'];ck(names['gallery_condition']=='NONE' and names['enrollment_tier'] is None,'Actual no-gallery naming scope')
        ck(names['source_occurrences']==len(names['turns']),'Every original occurrence retained')
        ck(names['clock']['valid'] is True and names['clock']['reversals']==[],'Valid relevant naming-emission UTC ordering')
        if m['actual_events']['wall_timestamp_reversals']:clock_reversals.append(dict(job_id=jid,measurement=mb,reversals=m['actual_events']['wall_timestamp_reversals']))
        ck(names['qualified_decision_emissions']+names['unqualified_decision_emissions']==len(names['decisions'])==counts.get('speaker_decision',0),'Naming emission denominator')
        for d in names['decisions']:
            ck(d['assigned_state']['identity'] is None and d['assigned_state']['confirmed'] is False and d['query_executed'] is False,'No invented assigned identity/query')
            decisionstatuses[d['name_status']]+=1
        for t in names['turns']:
            turnstatuses[t['reference_status']]+=1;ck(t['correct_name_attainable_in_actual_gallery'] is False,'No enrolled identity attainable')
            for key in ('first_correct_decision_delay_sec','first_confirmed_correct_decision_delay_sec','first_stable_retained_row_delay_sec'):ck(t[key] is None,'No naming delay invented')
        ck(names['stable_retained_runs']==[],'No stable known-name success in none mode')
        for row in names['retained_rows']:
            intervals=[x for x in names['intervals'] if x['utterance_id']==row['utterance_id']]
            if row['status']=='SCORED_NATIVE_EMISSION_ROW':
                same(sum(x['end_sec']-x['start_sec'] for x in intervals),row['retained_row_sec'],'Retained row lifetime partition')
                same(sum(row['exposure_row_sec'].values()),row['retained_row_sec'],'Retained exposure partition')
                ck(row['correct_name_attainable_row_sec']==0,'No-gallery retained attainable duration')
        for key in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):ck(native['final_telemetry'][key]==0,'No final recorded '+key)
        totals.update(dict(cells=1,bundles=1,sessions=1,none_mode_gallery_admission_events=1,loaded_profiles=0,native_samples=n,external_samples=m['external_process_samples'],occurrence_rows=len(names['turns']),naming_decision_emissions=len(names['decisions']),retained_rows=len(names['retained_rows']),stable_known_name_runs=0))
        grouped[(job['asr_tap'],job['repetition'])].append(dict(job_id=jid,source_sec=measurement['source_sec'],outer_wall_sec=measurement['completed_cell_wall_sec'],model_startup_sec=measurement['model_startup_sec'],native_sec=measurement['native_elapsed_sec'],native_sample_gap_sec=tr['max_sample_gap_sec'],native_rss_sample_max=tr['process']['rss_sum_upper_bound_bytes']['max'],external_rss_sample_max=m['external_process_statistics']['rss_sum_upper_bound_bytes']['max'],observed_event_queue_max=tr['event_queue_backlog']['max'],scheduler_pending_max=scheduler['max_pending_events']))
        sourcecells.append(dict(job_id=jid,measurement=mb,completion=chain['complete_binding'],cell=chain['cell_binding'],native=chain['native_binding']))
    groups=[]
    for (tap,rep),rows in sorted(grouped.items()):
        summaries={}
        for field in rows[0]:
            if field=='job_id':continue
            values=[x[field] for x in rows if x[field] is not None]
            summaries[field]=dict(observed=len(values),missing=len(rows)-len(values),min=min(values) if values else None,max=max(values) if values else None,mean=statistics.mean(values) if values else None,total=sum(values) if field in ('source_sec','outer_wall_sec','native_sec','model_startup_sec') else None)
        groups.append(dict(asr_tap=tap,identity_tap=tap,repetition=rep,cells=len(rows),summaries=summaries))
        examples.append(max(rows,key=lambda x:(x['outer_wall_sec'],x['job_id'])))
    metadata=B.write_new(output/'METADATA_SOURCES.json',reader.sources)
    receipt=dict(schema='s6c-c065-actual-paced-independent-review.v1',status='PASS_BOUNDED_ACTUAL_REVIEW',checks=checks,authorities=bindings,manifest=pb,paced_index=ib,repetition_indices=repetition_rows,counts=dict(totals),distinct_native_sessions=len(nativeids),distinct_recorded_child_identities=len(owners_seen),turn_reference_status_counts=dict(turnstatuses),decision_name_status_counts=dict(decisionstatuses),timing_groups=groups,full_native_log_utc_reversals=clock_reversals,largest_outer_wall_example_per_route_repetition=examples,cells=sourcecells,metadata_sources=metadata,source=B.binding(__file__,Path(__file__).read_bytes()),readme=B.binding(Path(__file__).with_name('README_S6C_REVIEW_C065_PACED_ACTUAL_V1.md'),Path(__file__).with_name('README_S6C_REVIEW_C065_PACED_ACTUAL_V1.md').read_bytes()),new_models=0,new_policy_replays=0,scope='Actual40 cells only; excludes preserved failed fast_v1 attempt from this batch denominator. Exact closed metadata and compact emitted measurements checked, without reopening original event/process streams or prediction payloads. Native inherited continuous schema/scope is overridden for classification by exact CELL_RESULT canonical single-scene lineage. Parity excludes the held execution-only fields; no WER or independent payload parity recomputation. Timing differences are observed scopes, not causes, GUI/phonetic latency, guaranteed peaks or CM5 claims.')
    return B.write_new(output/'REVIEW_RECEIPT.json',receipt)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(review(p.parse_args().output),indent=2))
