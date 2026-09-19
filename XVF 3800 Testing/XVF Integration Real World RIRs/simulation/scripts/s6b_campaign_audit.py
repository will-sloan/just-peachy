"""Compact S6B admission and progress summaries; see README_S6B_CAMPAIGN_AUDIT.md."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json
import statistics
from s6b_common import *


def baseline_parity():
    import csv
    folder=REPORT/'baseline_all_validation_v1'
    rows=list(csv.DictReader((folder/'PROFILE_RESULTS.csv').open(encoding='utf-8')))
    lookup={(r['stream'],r['population']):r for r in rows}
    checks=[]
    for tap,primary,overlap,cp,ambient,empty in [('O0',656,486,3533,202,1),('O1',705,502,3714,205,2)]:
        for population,field,expected in [('PRIMARY_NONOVERLAP','scenes',156),('PRIMARY_NONOVERLAP','word_errors',primary),
            ('PRIMARY_NONOVERLAP','word_reference_words',4560),('COMPLETE_OVERLAP','scenes',47),
            ('COMPLETE_OVERLAP','word_errors',overlap),('COMPLETE_OVERLAP','word_reference_words',1456),
            ('ALL_COMPLETE_NONEMPTY','cp_first_final_errors',cp),('ALL_COMPLETE_NONEMPTY','cp_first_final_reference_words',6016),
            ('INCOMPLETE_REFERENCE','scenes',26),('INCOMPLETE_REFERENCE','word_errors',ambient),
            ('INCOMPLETE_REFERENCE','word_reference_words',683),('STRICT_EMPTY_REFERENCE','scenes',11),
            ('STRICT_EMPTY_REFERENCE','empty_insertions',empty)]:
            actual=int(lookup[tap,population][field]);checks.append(dict(stream=tap,population=population,field=field,expected=expected,actual=actual,passed=actual==expected))
        turns=sum(int(lookup[tap,p]['source_turns']) for p in ('PRIMARY_NONOVERLAP','COMPLETE_OVERLAP','INCOMPLETE_REFERENCE'))
        checks.append(dict(stream=tap,field='all_source_turn_occurrences',expected=777,actual=turns,passed=turns==777))
    if not all(c['passed'] for c in checks):raise ValueError('Accepted baseline arithmetic mismatch')
    result=dict(status='PASS',checks=checks,source=bind(folder/'PROFILE_RESULTS.csv'),analysis_receipt=bind(folder/'ANALYSIS_RECEIPT.json'),
        prediction_index=bind(REPORT/'B00_FULL_PREDICTION_INDEX.json'),new_neural_inference=0,
        scope='Exact accepted S6A B0 word/cp counts reproduced for480 historical outputs. First-display-label final-word cp is a newly separated diagnostic, not the prior first-final measure.')
    save(REPORT/'BASELINE_PARITY_RECEIPT.json',result)
    return dict(status='PASS',checks=len(checks),outputs=480,new_neural_inference=0)


def pilot_admission(epoch):
    spec_path=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json');spec=read(spec_path)
    index_path=REPORT/epoch/'PILOT_NEURAL_INDEX.json';index=read(index_path)
    if index['status']!='COMPLETE' or index['completed']!=64:raise ValueError('Require all64 balanced pilot outputs')
    grouped=defaultdict(list);records=[]
    for row in index['rows']:
        bind(row['receipt']['path'],row['receipt']['sha256']);rec=read(row['receipt']['path'])
        if rec['status']!='COMPLETE':raise ValueError('Failed pilot')
        bind(rec['evidence']['path'],rec['evidence']['sha256']);e=read(rec['evidence']['path'])
        costs=e['costs']['native_full_engine']
        entry=dict(recipe_id=rec['recipe_id'],case_id=rec['case_id'],stream=rec['stream'],audio_sec=rec['audio_duration_sec'],
            native_wall_sec=costs['elapsed_sec'],native_cpu_sec=costs['process_cpu_sec'],
            total_job_wall_sec=rec['full_engine_wall_sec'],load_sec=rec['initial_or_changed_recipe_model_load_sec'],
            calls=rec['actual_neural_counts'],evidence_bytes=rec['evidence']['bytes'],receipt=row['receipt'])
        records.append(entry);grouped[rec['recipe_id']].append(entry)
    summaries=[]
    for rid,rows in sorted(grouped.items()):
        if len(rows)!=8 or Counter(r['stream'] for r in rows)!=Counter(O0=4,O1=4):raise ValueError('Unbalanced family pilot')
        audio=sum(r['audio_sec'] for r in rows)
        summaries.append(dict(recipe_id=rid,outputs=len(rows),audio_sec=audio,
            total_job_wall_sec=sum(r['total_job_wall_sec'] for r in rows),
            total_job_rtf=sum(r['total_job_wall_sec'] for r in rows)/audio,
            native_wall_rtf=sum(r['native_wall_sec'] for r in rows)/audio,
            native_cpu_rtf=sum(r['native_cpu_sec'] for r in rows)/audio,
            embedding_calls=sum(r['calls'].get('research_embedding',0) for r in rows),
            segmentation_calls=sum(r['calls'].get('research_segmentation',0) for r in rows),
            load_sec=sum(r['load_sec'] for r in rows)))
    input_rows=read(spec['input_index']['path'])['rows'];challenge=set(read(spec['challenge_panel']['path'])['case_ids'])
    all_seconds=sum(r['duration_sec'] for r in input_rows)
    challenge_seconds=sum(r['duration_sec'] for r in input_rows if r['case_id'] in challenge)
    rates={r['recipe_id']:r['total_job_rtf'] for r in summaries}
    estimates=[]
    for recipe in spec['recipes']:
        rid=recipe['recipe_id'];family=recipe['recipe_family_id'];rate=rates[family]
        estimates.append(dict(recipe_id=rid,rate_from_pilot_family=family,measured_exact_recipe=rid in rates,
            challenge_outputs=88,all_bank_outputs=480,challenge_worker_wall_sec=rate*challenge_seconds,
            all_bank_worker_wall_sec=rate*all_seconds))
    # Four workers is a research ceiling. Bounds are engineering factors, not confidence intervals.
    challenge_wall=sum(e['challenge_worker_wall_sec'] for e in estimates)/4
    all_wall=sum(e['all_bank_worker_wall_sec'] for e in estimates)/4
    heartbeat=read(REPORT/'HEARTBEAT.json')
    result=dict(status='ADMIT_CHALLENGE_ALL18_RECIPES',created_utc=utc(),epoch=epoch,
        balanced_pilot=bind(index_path),execution_manifest=bind(spec_path),pilot_family_summaries=summaries,
        per_exact_recipe_estimates=estimates,
        admitted_scope=dict(scenes=44,taps=2,neural_recipes=18,neural_outputs=1584,core_profiles=40,limited_diagnostics=4,predictions=3872),
        wall_estimate_sec=dict(challenge_all18_lower=.7*challenge_wall,challenge_all18_upper=2*challenge_wall,
            all240_all18_conservative_envelope_lower=.7*all_wall,all240_all18_conservative_envelope_upper=2*all_wall),
        estimate_limits='Measured four-scene balanced pilot per initial family. Unmeasured exact branches inherit family cost; 0.7x to2x factors are engineering scenarios, not statistical confidence limits. All18 full-bank is a budget envelope, not automatic selection.',
        resources_at_admission=heartbeat['resources'],worker_ceiling=4,
        shortlist_rule='Screen all44 on both taps; retain3-5 structurally distinct general families including simple voice fallback. Require480 outputs per retained profile before exploratory full-bank ranking; compare unknown, mixed, short, returns, word harm, revisions and measured cost without a weighted score.',
        execution_guardrails='No accuracy retries. Preserve failed attempts. Worker reserves and STOP_REQUEST remain enforced. Epoch1 was never executed; epoch2 prospectively fixes duration/cadence confound.')
    save(REPORT/'PILOT_ADMISSION_AND_ETA.json',result)
    return {k:result[k] for k in ('status','admitted_scope','wall_estimate_sec')}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--epoch',default='epoch2');p.add_argument('--mode',choices=('pilot','baseline'),default='pilot');a=p.parse_args()
    print(json.dumps(baseline_parity() if a.mode=='baseline' else pilot_admission(a.epoch),indent=2))
