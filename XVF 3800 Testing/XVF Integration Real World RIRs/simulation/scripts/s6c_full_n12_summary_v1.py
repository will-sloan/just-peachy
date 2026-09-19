"""Exact full N12 table summary; see README_S6C_FULL_N12_SUMMARY_V1.md."""
from __future__ import annotations
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
BASE=Path(__file__).with_name('s6c_full_n03_summary_v1.py')
BASE_SHA='2323a76aec103af634eb4857096a1a0eea6a461f5f08d73326865edf27617b98'
if hashlib.sha256(BASE.read_bytes()).hexdigest()!=BASE_SHA:
    raise ValueError('Changed held compact table reader')
spec=importlib.util.spec_from_file_location('held_n03_compact_reader',BASE)
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
SUM_KEYS=('word_errors','word_substitutions','word_deletions','word_insertions','word_reference_words',
          'cp_first_final_errors','cp_latest_revised_errors','cp_first_display_label_final_words_errors',
          'source_turns','sole_active_samples','unknown_samples','false_merge_samples',
          'return_consistent','return_inconsistent','return_unknown','embedding_calls')
SOURCE_ROWS=(
    ('C065','full_n01_anonymous_core_v3','72af65710f4bbc45733bd6f145fbd4eb67ce558b8c3bbdad01b9c2c807c4e094',3840),
    ('C067','full_n03_native_core_v3','10d38193dfa630bc06dd15d582f1d9086493ce104cc5b45535be01844e238517',480),
    ('C076','full_n12_native_core_v3','d980fa246ab444810219961188c0c95ecf71c696d6d7103cf2ac87938b6691db',480))
NAMES=('PROFILE_RESULTS.csv','SHORT_REPLY_RESULTS.csv','TRACK_LIFECYCLE_RESULTS.csv','SCENE_RESULTS.csv','RECIPE_COST_RESULTS.csv')

def extreme_rows(left,right,tap,metric):
    rows=[]
    for key,a in left.items():
        z=right[key]
        if key[1]!=tap or a['population'] not in ('PRIMARY_NONOVERLAP','COMPLETE_OVERLAP'):continue
        denominator='word_reference_words' if metric=='word_errors' else 'cp_latest_revised_reference_words'
        words=b.integer(a,denominator)
        b.require(words>0 and words==b.integer(z,denominator),'Matched extreme denominator')
        rows.append((Fraction(b.integer(z,metric)-b.integer(a,metric),words),key[0],a,z))
    selected=[]
    for label,ordered in (('largest_signed_difference',sorted(rows,key=lambda x:(-x[0],x[1]))[:2]),
                          ('smallest_signed_difference',sorted(rows,key=lambda x:(x[0],x[1]))[:2])):
        for delta,case,a,z in ordered:
            selected.append(dict(selection=label,metric=metric,case_id=case,stream=tap,right_profile=z['profile_id'],
                                 signed_delta_pp=100*float(delta),
                                 left={k:a[k] for k in SUM_KEYS},right={k:z[k] for k in SUM_KEYS}))
    return selected

def test():
    b.require(b.integer({'n':'0'},'n')==0,'Zero count retained')
    for row,key,fn in (({'n':'-1'},'n',b.integer),({'v':'nan'},'v',b.number)):
        try:fn(row,key)
        except ValueError:pass
        else:raise AssertionError('Invalid number accepted')
    a={};z={}
    for case,err in (('A',2),('B',3),('C',2)):
        row={k:'0' for k in SUM_KEYS};row.update(case_id=case,stream='O0',population='PRIMARY_NONOVERLAP',
            cp_latest_revised_reference_words='10',word_reference_words='10',profile_id='LEFT')
        a[(case,'O0')]=row;z[(case,'O0')]=dict(row,profile_id='RIGHT',word_errors=str(err))
    result=extreme_rows(a,z,'O0','word_errors')
    b.require([r['case_id'] for r in result]==['B','A','A','C'],'Deterministic signed extremes and ties')
    b.require(a[('A','O0')]['word_errors']=='0','No mutation of source rows')
    print(json.dumps(dict(status='PASS',listed_checks=5,scope='Pure numeric/selection guards; no empirical input')))

def main(args):
    out=REPORT/'full_n12_results_v1'
    b.require(not out.exists(),'Fresh output namespace')
    scope,sb=b.obj(REPORT/'design/FULL_N12_COMPARISON_SCOPE_V1.json')
    b.require(sb['sha256']=='39dc0a6d5983eccdf15a176bc68952376813d3909a6b1d9bc1c68f0490fd4bbe','Held 11-pair/extreme scope')
    cache={};receipts={};tables={}
    for pid,folder,sha,count in SOURCE_ROWS:
        if folder not in cache:
            receipt,rb=b.obj(REPORT/folder/'ANALYSIS_RECEIPT.json')
            b.require(rb['sha256']==sha,'Exact completed core')
            b.require((receipt['status'],receipt['requested'],receipt['scored'],receipt['unscored'])==
                      ('COMPLETE_REQUESTED_INDEX',count,count,0),'Complete core grid')
            cache[folder]=(rb,{name:b.table(receipt,name) for name in NAMES})
        rb,original=cache[folder];receipts[pid]=rb;tables[pid]={}
        for name,rows in original.items():
            tables[pid][name]=[r for r in rows if (pid in json.loads(r['profile_reusers']) if name=='RECIPE_COST_RESULTS.csv' else r['profile_id']==pid)]
        scenes=tables[pid]['SCENE_RESULTS.csv']
        b.require(len(scenes)==480 and len({(r['case_id'],r['stream'],r['identity_tap']) for r in scenes})==480,'Exact 480 per candidate')
        b.require(all(r['stream']==r['identity_tap'] for r in scenes),'Exact same-tap routes')
    comparison,cb=b.obj(REPORT/'full_n12_comparisons_v1/COMPARISON_RECEIPT.json')
    b.require(cb['sha256']==args.comparison_sha,'Pinned completed comparison receipt')
    pairs=b.table(comparison,'PAIRED_COMPARISONS.csv')
    b.require({r['comparison_id'] for r in pairs}=={r['comparison_id'] for r in scope['comparisons']},'Exactly declared 11 comparisons')
    ub=[x for x in comparison['artifacts'] if Path(x['path']).name=='PAIRED_UNCERTAINTY.json']
    b.require(len(ub)==1,'One bound uncertainty')
    uncertainty,_=b.obj(ub[0]['path'],ub[0])
    b.require(len(uncertainty['comparisons'])==11,'11 uncertainty records')
    headlines=[];short=[];life=[];costs=[];all_populations=[];word_changes=[];examples=[]
    for pid,ts in tables.items():
        all_populations.extend(ts['PROFILE_RESULTS.csv'])
        for tap in ('O0','O1'):
            scenes=[r for r in ts['SCENE_RESULTS.csv'] if r['stream']==tap]
            h=[r for r in ts['PROFILE_RESULTS.csv'] if r['stream']==tap and r['population']=='ALL_COMPLETE_NONEMPTY']
            b.require(len(h)==1,'One complete population row');h=h[0]
            complete=[r for r in scenes if r['population'] in ('PRIMARY_NONOVERLAP','COMPLETE_OVERLAP')]
            b.require(len(complete)==203 and b.integer(h,'scenes')==203,'203 complete scenes')
            row=dict(profile_id=pid,stream=tap,scenes=203)
            for key in SUM_KEYS:
                n=b.integer(h,key);b.require(n==sum(b.integer(r,key) for r in complete),'Aggregate '+key);row[key]=n
            b.require((row['word_reference_words'],row['source_turns'],row['sole_active_samples'])==(6016,693,25304912),'Complete population support')
            b.require(sum(row[k] for k in ('return_consistent','return_inconsistent','return_unknown'))==292,'292 complete returns')
            row['unknown_percent']=100*row['unknown_samples']/row['sole_active_samples']
            row['mixed_percent_all_sole']=100*row['false_merge_samples']/row['sole_active_samples']
            headlines.append(row)
            for duration,n in (('<1s',40),('1-<2s',34)):
                q=[r for r in ts['SHORT_REPLY_RESULTS.csv'] if r['stream']==tap and r['population']=='ALL_COMPLETE_NONEMPTY' and r['duration_bin']==duration]
                b.require(len(q)==1 and b.integer(q[0],'source_turns')==n,'Exact short population')
                short.append(q[0])
            ls=[r for r in ts['TRACK_LIFECYCLE_RESULTS.csv'] if r['stream']==tap]
            b.require(len(ls)==240,'240 lifecycle cells')
            counts={}
            for field in ('activation_counts','lineage_counts'):
                c=Counter()
                for r in ls:
                    payload=json.loads(r[field])
                    for key,value in payload.items():
                        b.require(type(value) is int and value>=0,'Integer logged activation/lineage count')
                        c[key]+=value
                counts[field]=dict(sorted(c.items()))
            life.append(dict(profile_id=pid,stream=tap,scenes=240,
                maximum_peak_live=max(b.integer(r,'peak_live') for r in ls),
                maximum_peak_archive=max(b.integer(r,'peak_archive') for r in ls),
                blocked_unique_evidence_sec=sum(b.number(r,'blocked_unique_evidence_sec') for r in ls),
                cumulative_retirements_sum=sum(b.integer(r,'final_cumulative_retirements') for r in ls),
                lifetime_external_ids_sum=sum(b.integer(r,'final_lifetime_external_ids') for r in ls),**counts))
            cr=[r for r in ts['RECIPE_COST_RESULTS.csv'] if r['stream']==tap]
            b.require(len(cr)==240 and len({r['neural_source_key'] for r in cr})==240,'240 distinct native source cost rows')
            record=dict(profile_id=pid,stream=tap,source_cells=240,
                        source_duration_sec=sum(b.number(r,'duration_sec') for r in cr))
            for section,field in (('research_embedding','calls'),('research_embedding','compute_sec'),
                    ('research_embedding','model_api_elapsed_sec'),('research_speaker_dispatch_cost','full_dispatch_elapsed_sec'),
                    ('research_segmentation','compute_sec'),('research_asr_full_dispatch_cost','full_dispatch_elapsed_sec')):
                values=[json.loads(r['recipe_costs']).get(section,{}).get(field) for r in cr]
                present=[float(x) for x in values if x is not None]
                b.require(all(math.isfinite(x) and x>=0 for x in present),'Finite nested observed costs')
                record[section+'.'+field]=dict(sum=sum(present),observed_cells=len(present),unavailable_cells=240-len(present))
            costs.append(record)
    left={(r['case_id'],r['stream']):r for r in tables['C065']['SCENE_RESULTS.csv']}
    for pid in ('C076',):
        right={(r['case_id'],r['stream']):r for r in tables[pid]['SCENE_RESULTS.csv']}
        b.require(left.keys()==right.keys(),'Matched full routes')
        for key,a in left.items():
            z=right[key]
            b.require(all(a[k]==z[k] for k in ('population','room','family_id','duration_sec','identity_tap')),'Matched source population/duration')
        for tap in ('O0','O1'):
            aa=[(a,right[key]) for key,a in left.items() if key[1]==tap]
            wc=dict(profile_id=pid,stream=tap,cases=240,
                    normalized_final_text_equal_cells=sum(a['normalized_final_text']==z['normalized_final_text'] for a,z in aa),
                    normalized_final_text_changed_cells=sum(a['normalized_final_text']!=z['normalized_final_text'] for a,z in aa))
            empty=[(a,z) for a,z in aa if a['population']=='STRICT_EMPTY_REFERENCE']
            b.require(len(empty)==11,'All 11 strict-empty cases')
            wc['strict_empty']=dict(cases=11,left_insertions=sum(b.integer(a,'empty_insertions') for a,z in empty),
                right_insertions=sum(b.integer(z,'empty_insertions') for a,z in empty),
                left_nonempty_final_text_cases=sum(bool(a['normalized_final_text'].strip()) for a,z in empty),
                right_nonempty_final_text_cases=sum(bool(z['normalized_final_text'].strip()) for a,z in empty))
            word_changes.append(wc)
            for metric in ('cp_latest_revised_errors','word_errors'):
                examples.extend(extreme_rows(left,right,tap,metric))
    us=[]
    for row in uncertainty['comparisons']:
        b.require(row['included_primary_scenes']==156 and row['matched_block_count']==116,'Full primary conditional blocks')
        us.append({k:row[k] for k in ('comparison_id','replicates','included_primary_scenes','matched_block_count','observed_rooms','paired_O1_minus_O0_wer_pp_percentile95')})
    for path in (Path(__file__),Path(__file__).with_name('README_S6C_FULL_N12_SUMMARY_V1.md'),BASE):
        b.read(path)
    out.mkdir()
    result=dict(status='COMPLETE_EXACT_TABLE_SUMMARY',scope=sb,source_receipts=receipts,comparison_receipt=cb,
        check_count=b.CHECKS,sources=b.SOURCES,complete_population=headlines,all_profile_population_rows=all_populations,
        short_turns=short,lifecycle_all240=life,native_nested_cost_all240=costs,
        word_and_empty_changes=word_changes,matched_comparisons=pairs,primary_word_conditional_uncertainty=us,
        selected_extreme_case_examples=examples,
        limits=['Exact completed table aggregation only; native receipts/observations/words remain transitively bound.',
                'All240 confirmation after panel-informed selection is not independent holdout.',
                'First-display cp uses finalized words with first-displayed labels; no partial-word or actual-wall latency claim.',
                'cp combines word and anonymous attribution errors; changed endpoint-associated words prevent isolated attribution conclusions.',
                'Strict-empty insertions retain 11 zero-reference cases separately; no WER on zero denominator.',
                'Complete word errors combine primary serialized WER with overlap MIMO edit counts, not a single serialized alignment.',
                'Complete203/6016/693/292 support differs from incomplete26 and strict-empty11; all rows retained separately.',
                'Observed native nested model/API/full dispatch sums overlap and do not add to whole-pipeline wall cost.',
                'Native sources include different execution batches and reused panel cells; no source-paced/CM5 timing claim.',
                'Activation summaries reflect only logged counters, not proof every potential branch was exercised.',
                'Two largest/smallest signed differences per metric/tap are descriptive extremes; zero is a tie, not an observed harm/benefit.',
                'Primary-word2000-resample intervals are not cp intervals.',
                'C067 versus C076 changes mature embedding and endpoint settings together; a complete-condition tradeoff, not an isolated mechanism.'])
    print(json.dumps(b.save(out/'RESULT.json',result),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--test',action='store_true');p.add_argument('--comparison-sha')
    a=p.parse_args()
    if a.test:test()
    else:
        if not a.comparison_sha:p.error('--comparison-sha is required')
        main(a)

