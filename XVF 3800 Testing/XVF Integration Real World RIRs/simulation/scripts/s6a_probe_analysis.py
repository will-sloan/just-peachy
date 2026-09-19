"""Analyze real profile outputs against fixed input-only denominators. README_S6A_PROBES.md."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
import json
import math
import os
from pathlib import Path
import time
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import numpy as np
from s6a_common import *
from s6a_text_metrics import score_scene
from s6a_cue_score import tracking_metrics
from s6a_support_metrics import union,intersection,samples,contained,mapped_ranges

def csv_write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(rows)

def native_details(job,scene,support,receipt):
    events=[json.loads(line) for line in Path(receipt['events_binding']['path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    duration=receipt['audio_duration_s'];length=round(duration*16000);profile=read(job['profile']['path'])
    embeddings=[e['payload'] for e in events if e['event_type']=='research_embedding']
    segs=[e['payload'] for e in events if e['event_type']=='research_segmentation']
    dispatch=[e['payload'] for e in events if e['event_type']=='research_asr_dispatch']
    tails=[e['payload'] for e in events if e['event_type']=='research_asr_tail_dispatch']
    drains=[e['payload'] for e in events if e['event_type']=='research_asr_drain']
    loading=[e['payload'] for e in events if e['event_type']=='research_models_ready']
    assert len(drains)==1 and len(loading)==1, 'Complete v2 native run must log EOF drain and model loading'
    decisions=[e['decision'] for e in embeddings]
    track=tracking_metrics(support,job['stream'],decisions,length)
    windows=[[round(e['source_start_sec']*16000),round(e['source_end_sec']*16000)] for e in embeddings]
    for e in embeddings:
        assert e['source_end_sec']<=duration and e['modeled_available_at_sec']>=e['receptive_end_sec']
        assert abs(e['source_end_sec']-e['source_start_sec']-profile['embedding']['window_sec'])<1e-6
    for e in segs:assert e['modeled_available_at_sec']>=e['receptive_end_sec']
    short=[];regions={};purity=Counter();shift=support['output_mappings'][job['stream']]['source_with_rir_to_output_offset_samples']
    if shift is not None:
        turns=[]
        for source in support['turns']:
            row=dict(source)
            row['active_ranges']=mapped_ranges(source['active_ranges'],shift,length)
            row['file_support']=mapped_ranges(source['file_support'],shift,length)
            row['support_ranges']=mapped_ranges(source['support_ranges'],shift,length);turns.append(row)
        speech_flags=union([[round(e['source_start_sec']*16000),round(e['source_end_sec']*16000)] for e in segs if e['speech']])
        overlap_flags=union([[round(e['source_start_sec']*16000),round(e['source_end_sec']*16000)] for e in segs if e['overlap']])
        observed=union([[round(e['source_start_sec']*16000),round(e['source_end_sec']*16000)] for e in segs])
        for name,source_ranges in support['regions_source_with_rir_samples'].items():
            ranges=mapped_ranges(source_ranges,shift,length)
            regions[name]={'support_samples':samples(ranges),'observed_samples':samples(intersection(ranges,observed)),
                'speech_flag_samples':samples(intersection(ranges,speech_flags)),'overlap_flag_samples':samples(intersection(ranges,overlap_flags))}
        for turn in turns:
            other=union([r for t in turns if t['segment_index']!=turn['segment_index'] for r in t['file_support']])
            eligible=support['all_speaker_reference_complete'] and not samples(intersection(turn['file_support'],other))
            containing=[i for i,w in enumerate(windows) if contained(w,turn['file_support']) and not samples(intersection([w],other))]
            short.append({'segment_index':turn['segment_index'],'whole_clip_bin':turn['whole_clip_bin'],'active_duration_bin':turn['active_duration_bin'],
                'whole_clip_duration_s':turn['whole_clip_duration_s'],'source_specific_eligible':eligible,
                'support_samples':samples(turn['support_ranges']),'speech_flag_samples':samples(intersection(turn['support_ranges'],speech_flags)),
                'contained_embedding_count':len(containing),'first_contained_embedding_modeled_wait_s':
                    min((embeddings[i]['modeled_available_at_sec']-turn['file_support'][0][0]/16000 for i in containing),default=None)})
        for window in windows:
            intersecting={t['speaker_key'] for t in turns if samples(intersection([window],t['file_support']))}
            pure=[t for t in turns if contained(window,t['file_support'])]
            if len(intersecting)>1:purity['cross_person_windows']+=1
            elif len(intersecting)==1 and pure:purity['single_complete_file_envelope_windows']+=1
            elif len(intersecting)==1:purity['single_partial_boundary_windows']+=1
            else:purity['outside_annotated_source_windows']+=1
    lineage=Counter(event['event'] for d in decisions for event in d.get('lineage',[]))
    partials=[e for e in events if e['event_type']=='transcript_partial' and str(e['payload'].get('text','')).strip()]
    finals=[e for e in events if e['event_type']=='transcript_final']
    lexical=score_scene(scene,read(receipt['metrics_binding']['path']),events,allowed_ids=manifest_ids(),duration_s=duration)
    resource=read(receipt['resources_binding']['path'])['rows']
    memory={}
    for name in ('uss','rss','private_commit'):
        valid=[sum(p[name] for p in r['processes']) for r in resource
               if r['processes'] and all(p.get(name) is not None for p in r['processes'])]
        memory[name]={'peak_bytes':max(valid,default=None),'valid_samples':len(valid),
                      'unavailable_samples':len(resource)-len(valid)}
    peak_uss=memory['uss']['peak_bytes'];peak_rss=memory['rss']['peak_bytes'];peak_commit=memory['private_commit']['peak_bytes']
    return {'text_metrics':lexical,'tracking_metrics':track,'embedding_calls':len(embeddings),'embedding_total_window_s':sum(b-a for a,b in windows)/16000,
        'embedding_union_s':samples(windows)/16000,'embedding_compute_s':sum(e['compute_ms'] for e in embeddings)/1000,
        'segmentation_calls':len(segs),'segmentation_compute_s':sum(e['compute_ms'] for e in segs)/1000,
        'asr_dispatch_calls':len(dispatch),'asr_tail_dispatch_calls':len(tails),'asr_drain_calls':len(drains),
        'asr_regular_dispatch_compute_s':sum(e.get('compute_ms',0) for e in dispatch)/1000,
        'asr_tail_dispatch_compute_s':sum(e.get('compute_ms',0) for e in tails)/1000,
        'asr_drain_compute_s':sum(e.get('compute_ms',0) for e in drains)/1000,
        'asr_compute_s':sum(e.get('compute_ms',0) for e in dispatch+tails+drains)/1000,
        'punctuation_compute_s':sum(e['payload'].get('punctuation',{}).get('compute_ms',0) for e in finals)/1000,
        'model_load_elapsed_s':loading[0]['model_load_elapsed_sec'],
        'native_endpoint_count':sum(bool(e.get('native_endpoint')) for e in dispatch),'advisory_endpoint_count':sum(bool(e.get('advisory_endpoint')) for e in dispatch),
        'speech_assisted_segmentation_calls':sum(e.get('speech_assist_delta',0)>0 for e in segs),
        'partial_count':len(partials),'final_count':len(finals),'first_readable_partial_modeled_s':partials[0]['payload'].get('modeled_available_at_sec') if partials else None,
        'first_readable_partial_actual_elapsed_s':partials[0]['payload'].get('compute_finished_elapsed_sec') if partials else None,
        'last_final_modeled_s':finals[-1]['payload'].get('modeled_available_at_sec') if finals else None,
        'lineage_counts':dict(lineage),'embedding_purity_file_envelopes':dict(purity),'short_turns':short,'regions':regions,
        'peak_private_resident_uss_bytes':peak_uss,'peak_rss_upper_bound_bytes':peak_rss,'peak_windows_private_commit_bytes':peak_commit,
        'memory_sampling':memory,
        'timing_scope':'Source-support estimates; modeled warm-resident serial component availability with measured compute excludes model loading. Native first labels also depend on concurrent desktop worker scheduling. Actual elapsed is accelerated desktop, not calibrated live latency.',
        'segmentation_scope':'Full trailing10s receptive context charged; coarse tail-output intervals, not exact phonetic/word timings.'}

_IDS=None
def manifest_ids():
    global _IDS
    if _IDS is None:_IDS=frozenset(s['case_id'] for s in manifest()['scenes'])
    return _IDS

def aggregate(records,expected,complete):
    groups=defaultdict(list)
    for row in records:groups[(row['profile_id'],row['stream'])].append(row)
    result=[]
    for (pid,stream),rows in sorted(groups.items()):
        detail={'profile_id':pid,'stream':stream,'scenes':len(rows),'expected_scenes':36,'complete_panel':len(rows)==36}
        for population,metric in [('primary_nonoverlap','text'),('overlap_complete','overlap_mimo'),('ambient_incomplete','target_only_text')]:
            vals=[r['metrics']['text_metrics'].get(metric,{}) for r in rows if r['population']==population]
            counts=Counter()
            for value in vals:counts.update(value.get('word_counts',{}))
            prefix={'primary_nonoverlap':'primary','overlap_complete':'overlap','ambient_incomplete':'ambient_target_only'}[population]
            for key in ('reference_words','errors','substitutions','deletions','insertions'):detail[prefix+'_'+key]=counts[key]
            detail[prefix+'_wer']=counts['errors']/counts['reference_words'] if counts['reference_words'] else None
        cps=[r['metrics']['text_metrics']['attributed_cpwer'] for r in rows if r['population'] in ('primary_nonoverlap','overlap_complete')]
        cpcounts=Counter()
        for v in cps:cpcounts.update(v.get('word_counts',{}))
        detail.update(cpwer_errors=cpcounts['errors'],cpwer_reference_words=cpcounts['reference_words'],cpwer=cpcounts['errors']/cpcounts['reference_words'] if cpcounts['reference_words'] else None)
        for key in ('embedding_calls','embedding_total_window_s','embedding_union_s','embedding_compute_s','segmentation_calls','segmentation_compute_s','asr_dispatch_calls','asr_compute_s','asr_tail_dispatch_calls','asr_drain_calls','asr_regular_dispatch_compute_s','asr_tail_dispatch_compute_s','asr_drain_compute_s','punctuation_compute_s','model_load_elapsed_s','native_endpoint_count','advisory_endpoint_count','speech_assisted_segmentation_calls','partial_count','final_count'):
            detail[key]=sum(r['metrics'][key] for r in rows)
        for key in ('peak_private_resident_uss_bytes','peak_rss_upper_bound_bytes','peak_windows_private_commit_bytes'):
            detail[key]=max((r['metrics'][key] for r in rows if r['metrics'][key] is not None),default=None)
            detail[key+'_unavailable_outputs']=sum(r['metrics'][key] is None for r in rows)
        # Pool counts first. Never add per-scene ratios.
        tracking=Counter()
        additive=('source_turns','supported_turns','unknown_turns','sole_active_samples','false_merge_samples',
                  'known_samples','unknown_samples','excess_labels_per_reference_identity','turn_multilabel_count',
                  'return_consistent','return_inconsistent','return_unknown')
        for row in rows:
            if row['population']=='ambient_incomplete':continue
            for key,value in row['metrics']['tracking_metrics'].items():
                if key in additive and value is not None:tracking[key]+=value
        for key,value in tracking.items():detail['tracking_'+key]=value
        detail['tracking_unknown_fraction']=tracking['unknown_samples']/tracking['sole_active_samples'] if tracking['sole_active_samples'] else None
        detail['tracking_false_merge_fraction_of_known']=tracking['false_merge_samples']/tracking['known_samples'] if tracking['known_samples'] else None
        detail['tracking_unassigned_or_conflated_fraction']=(tracking['unknown_samples']+tracking['false_merge_samples'])/tracking['sole_active_samples'] if tracking['sole_active_samples'] else None
        short=[s for r in rows for s in r['metrics']['short_turns'] if s['source_specific_eligible']]
        for bin_name,prefix in [('<1s','short_lt1'),('1-<2s','short_1to2'),('>=2s','long_ge2')]:
            selected=[s for s in short if s['whole_clip_bin']==bin_name]
            detail[prefix+'_turns']=len(selected);detail[prefix+'_without_contained_embedding']=sum(s['contained_embedding_count']==0 for s in selected)
        detail['model_wall_s']=sum(r['model_wall_s'] for r in rows)
        result.append(detail)
    csv_write(REPORT/'COMPONENT_PROBE_RESULTS.csv',result)
    factorial=[];lookup={(r['profile_id'],r['stream']):r for r in result}
    for stream in (('O0','O1') if complete==expected else ()):
        if not all((pid,stream) in lookup for pid in ('P0X0','P0X1','P1X0','P1X1')):continue
        for metric in ('primary_wer','overlap_wer','cpwer','embedding_calls','embedding_union_s','asr_compute_s','segmentation_compute_s','embedding_compute_s','advisory_endpoint_count'):
            values={pid:lookup[(pid,stream)].get(metric) for pid in ('P0X0','P0X1','P1X0','P1X1')}
            if any(v is None for v in values.values()):continue
            factorial.append({'stream':stream,'metric':metric,**values,'original_cue_increment':values['P0X1']-values['P0X0'],
                'tuned_cue_increment':values['P1X1']-values['P1X0'],
                'interaction_tuned_minus_original_cue_increment':(values['P1X1']-values['P1X0'])-(values['P0X1']-values['P0X0']),
                'all_four_complete':all(lookup[(pid,stream)]['complete_panel'] for pid in values),'scope':'Withinfixed36screeningpanel; no population causal claim'})
    csv_write(REPORT/'JOINT_FACTORIAL_RESULTS.csv',factorial)
    save(REPORT/'COMPONENT_PROBE_SUMMARY.json',{'status':'COMPLETE' if complete==expected else 'PARTIAL','requested':expected,'complete':complete,
        'panel_only':True,'profiles':result,'factorial':factorial,'metrics_scope':'Anonymous tracking and final-snapshot cpWER; no enrolled-name/DER/exactwordlatency claim',
        'interpretation':'Words/counts are redecoded real component branches; positives/rejections retain input-only short/overlap/noise denominators.'})

def run(interim=False):
    spec=read(REPORT/'PROBE_JOB_MANIFEST_V2.json');scenes={s['case_id']:s for s in manifest()['scenes']}
    index={r['case_id']:r for r in read(REPORT/'support/FROZEN_SUPPORT_INDEX.json')['scenes']}
    codes=[bind(__file__)]+[bind(Path(__file__).with_name(name)) for name in
        ('s6a_cue_score.py','s6a_text_metrics.py','s6a_support_metrics.py','s6a_common.py')]
    records=[];rows=[]
    with Progress('PROBE_SCORING',len(spec['jobs'])) as progress:
        for job in spec['jobs']:
            cid,out,pid=job['case_id'],job['stream'],job['profile_id'];rp=Path(job['report_dir'])/'run_receipt.json'
            if not rp.exists() or read(rp).get('status')!='COMPLETE':
                rows.append({'case_id':cid,'stream':out,'profile_id':pid,'status':'PENDING_OR_FAILED'})
                progress.detail['pending_or_failed']=progress.detail.get('pending_or_failed',0)+1
                continue
            receipt=read(rp);assert receipt['job_key']==job['job_key']
            for key in ('events_binding','metrics_binding','session_summary_binding','resources_binding'):bind(receipt[key]['path'],receipt[key]['sha256'])
            bind(index[cid]['support']['path'],index[cid]['support']['sha256'])
            identity={'receipt':bind(rp),'support':index[cid]['support'],'code':codes}
            target=REPORT/'probe_metrics_v4'/pid/cid/(out+'.json')
            if target.exists():
                value=read(target);assert value['analysis_identity']==identity,'Changed probe metric inputs'
            else:
                source=read(index[cid]['support']['path'])['support']
                metrics=native_details(job,scenes[cid],source,receipt)
                value={'case_id':cid,'stream':out,'profile_id':pid,'population':population(scenes[cid]),'analysis_identity':identity,
                    'metrics':metrics,'model_wall_s':receipt['model_wall_s']};save(target,value)
            records.append(value);rows.append({'case_id':cid,'stream':out,'profile_id':pid,'status':'COMPLETE','result':bind(target)})
            progress.done+=1
    save(REPORT/'PROBE_ANALYSIS_RECEIPT.json',{'status':'COMPLETE' if len(records)==720 else 'PARTIAL','utc':now(),'requested':720,'complete':len(records),'rows':rows,'codes':codes})
    if len(records)!=720 and not interim:raise ValueError('720 complete outputs needed for final aggregation; use --interim for diagnostic snapshot')
    aggregate(records,720,len(records))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--interim',action='store_true')
    run(parser.parse_args().interim)
