"""Compact exact-table N03 interpretation; see README_S6C_FULL_N03_SUMMARY_V1.md."""
from __future__ import annotations
import csv
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
SOURCES=[]
CHECKS=0

def require(value,message):
    global CHECKS
    if not value:raise ValueError(message)
    CHECKS+=1

def read(path,binding=None):
    path=Path(path); raw=path.read_bytes()
    actual=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if binding is not None:require(actual==binding,'Changed exact source '+str(path))
    SOURCES.append(actual)
    return raw,actual

def obj(path,binding=None):
    raw,b=read(path,binding); return json.loads(raw),b

def table(receipt,name):
    bindings=receipt['tables'] if 'tables' in receipt else receipt['artifacts']
    matches=[b for b in bindings if Path(b['path']).name==name]
    require(len(matches)==1,'Unique table '+name)
    raw,_=read(matches[0]['path'],matches[0])
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))

def integer(row,key):
    value=int(row[key]);require(value>=0,key+' negative');return value

def number(row,key):
    value=float(row[key]);require(math.isfinite(value),key+' nonfinite');return value

def save(path,value):
    raw=((json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode('utf-8') if not isinstance(value,str) else value.encode('utf-8'))
    with path.open('xb') as handle:handle.write(raw)
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def main():
    out=REPORT/'full_n03_results_v1'
    require(not out.exists(),'Fresh namespace required')
    receipts={}
    all_tables={}
    for pid,subdir,expected_sha,expected_n in (
        ('C065','full_n01_anonymous_core_v3','72af65710f4bbc45733bd6f145fbd4eb67ce558b8c3bbdad01b9c2c807c4e094',3840),
        ('C067','full_n03_native_core_v3','10d38193dfa630bc06dd15d582f1d9086493ce104cc5b45535be01844e238517',480)):
        receipt,b=obj(REPORT/subdir/'ANALYSIS_RECEIPT.json')
        require(b['sha256']==expected_sha,'Pinned completed scorer')
        require((receipt['status'],receipt['requested'],receipt['scored'],receipt['unscored'])==('COMPLETE_REQUESTED_INDEX',expected_n,expected_n,0),'Complete scorer')
        receipts[pid]=b
        all_tables[pid]={}
        for name in ('PROFILE_RESULTS.csv','SHORT_REPLY_RESULTS.csv','TRACK_LIFECYCLE_RESULTS.csv','SCENE_RESULTS.csv','RECIPE_COST_RESULTS.csv'):
            rows=table(receipt,name)
            if name=='RECIPE_COST_RESULTS.csv':rows=[r for r in rows if pid in json.loads(r['profile_reusers'])]
            else:rows=[r for r in rows if r['profile_id']==pid]
            all_tables[pid][name]=rows
        scenes=all_tables[pid]['SCENE_RESULTS.csv']
        require(len(scenes)==480 and len({(r['case_id'],r['stream'],r['identity_tap']) for r in scenes})==480,'Exact 480 score rows')
        require(all(r['identity_tap']==r['stream'] for r in scenes),'Same-tap N01/N03')
    comparison,cb=obj(REPORT/'full_n03_comparisons_v1/COMPARISON_RECEIPT.json')
    require(cb['sha256']=='6b23a862569c3f9f25cf85a7301f2aeb08009e08a15374d6c883dddc6fd2fe14','Exact nine comparisons')
    pairs=table(comparison,'PAIRED_COMPARISONS.csv')
    ub=[b for b in comparison['artifacts'] if Path(b['path']).name=='PAIRED_UNCERTAINTY.json']
    require(len(ub)==1,'Exact uncertainty artifact')
    uncertainty,_=obj(ub[0]['path'],ub[0])
    require(len(uncertainty['comparisons'])==9,'Nine uncertainty records')
    headline=[];short=[];lifecycle=[];cost=[];case_results=[]
    sum_keys=('word_errors','word_reference_words','cp_first_final_errors','cp_latest_revised_errors',
              'cp_first_display_label_final_words_errors','source_turns','sole_active_samples','unknown_samples',
              'false_merge_samples','return_consistent','return_inconsistent','return_unknown','embedding_calls')
    for pid,tables in all_tables.items():
        for tap in ('O0','O1'):
            profile=[r for r in tables['PROFILE_RESULTS.csv'] if r['stream']==tap and r['population']=='ALL_COMPLETE_NONEMPTY']
            require(len(profile)==1,'Unique headline')
            h=profile[0]
            scenes=[r for r in tables['SCENE_RESULTS.csv'] if r['stream']==tap]
            complete=[r for r in scenes if r['population'] in ('PRIMARY_NONOVERLAP','COMPLETE_OVERLAP')]
            require(len(complete)==203 and integer(h,'scenes')==203,'203 complete scenes')
            record=dict(profile_id=pid,stream=tap,scenes=203)
            for key in sum_keys:
                value=integer(h,key)
                require(value==sum(integer(r,key) for r in complete),'Scene aggregate '+key)
                record[key]=value
            require(record['word_reference_words']==6016 and record['source_turns']==693 and record['sole_active_samples']==25304912,'Complete support denominators')
            require(sum(record[k] for k in ('return_consistent','return_inconsistent','return_unknown'))==292,'292 returns')
            record['unknown_percent']=100*record['unknown_samples']/record['sole_active_samples']
            record['mixed_percent_all_sole']=100*record['false_merge_samples']/record['sole_active_samples']
            record['embedding_total_window_sec']=number(h,'embedding_total_window_sec')
            headline.append(record)
            for duration in ('<1s','1-<2s'):
                rows=[r for r in tables['SHORT_REPLY_RESULTS.csv'] if r['stream']==tap and r['population']=='ALL_COMPLETE_NONEMPTY' and r['duration_bin']==duration]
                require(len(rows)==1,'Unique short bin')
                row=rows[0];require(integer(row,'source_turns')==(40 if duration=='<1s' else 34),'Short denominator')
                short.append({k:row[k] for k in ('profile_id','stream','duration_bin','source_turns','contained_embedding_turns','any_known_support_turns','duration_mapped_correct_modal_turns','duration_mapped_correct_samples','unknown_samples')})
            life=[r for r in tables['TRACK_LIFECYCLE_RESULTS.csv'] if r['stream']==tap]
            require(len(life)==240,'240 lifecycle rows')
            lifecycle.append(dict(profile_id=pid,stream=tap,scenes=240,maximum_peak_live=max(integer(r,'peak_live') for r in life),
                maximum_peak_archive=max(integer(r,'peak_archive') for r in life),blocked_unique_evidence_sec=sum(number(r,'blocked_unique_evidence_sec') for r in life),
                cumulative_retirements_sum=sum(integer(r,'final_cumulative_retirements') for r in life),
                lifetime_external_ids_sum=sum(integer(r,'final_lifetime_external_ids') for r in life)))
            costs=[r for r in tables['RECIPE_COST_RESULTS.csv'] if r['stream']==tap]
            require(len(costs)==240 and len({r['neural_source_key'] for r in costs})==240,'240 unique native cost sources')
            entry=dict(profile_id=pid,stream=tap,source_cells=240,source_duration_sec=sum(number(r,'duration_sec') for r in costs))
            for section,field in (('research_embedding','calls'),('research_embedding','compute_sec'),('research_embedding','model_api_elapsed_sec'),
                                  ('research_speaker_dispatch_cost','full_dispatch_elapsed_sec'),('research_segmentation','compute_sec'),
                                  ('research_asr_full_dispatch_cost','full_dispatch_elapsed_sec')):
                values=[json.loads(r['recipe_costs']).get(section,{}).get(field) for r in costs]
                present=[float(x) for x in values if x is not None]
                require(all(math.isfinite(x) and x>=0 for x in present),'Valid native cost')
                entry[section+'.'+field]=dict(sum=sum(present),observed_cells=len(present),unavailable_cells=240-len(present))
            cost.append(entry)
    a={(r['case_id'],r['stream']):r for r in all_tables['C065']['SCENE_RESULTS.csv']}
    b={(r['case_id'],r['stream']):r for r in all_tables['C067']['SCENE_RESULTS.csv']}
    require(a.keys()==b.keys(),'Matched case/tap grid')
    for key in a:
        require(a[key]['normalized_final_text']==b[key]['normalized_final_text'],'Actual final words equal')
        require(a[key]['word_errors']==b[key]['word_errors'],'Actual raw word errors equal')
    for tap in ('O0','O1'):
        candidates=[]
        for key,left in a.items():
            right=b[key]
            if key[1]!=tap or left['population'] not in ('PRIMARY_NONOVERLAP','COMPLETE_OVERLAP'):continue
            words=integer(left,'cp_latest_revised_reference_words'); require(words==integer(right,'cp_latest_revised_reference_words') and words>0,'Matched cp denominator')
            delta=integer(right,'cp_latest_revised_errors')-integer(left,'cp_latest_revised_errors')
            candidates.append((Fraction(delta,words),key[0],left,right))
        for label,subset in (('largest_observed_harm',sorted(candidates,key=lambda x:(-x[0],x[1]))[:2]),
                             ('largest_observed_benefit',sorted(candidates,key=lambda x:(x[0],x[1]))[:2])):
            for frac,case,left,right in subset:
                case_results.append(dict(selection=label,case_id=case,stream=tap,delta_pp=100*float(frac),
                    left={k:left[k] for k in sum_keys},right={k:right[k] for k in sum_keys}))
    pair_summary=[{k:r[k] for k in ('comparison_id','population','metric','paired_scenes','reference_words','left_errors','right_errors','right_minus_left_errors','right_minus_left_pp','matched_scene_count')} for r in pairs if r['population']=='ALL_COMPLETE_NONEMPTY']
    uncertainty_summary=[]
    for row in uncertainty['comparisons']:
        uncertainty_summary.append({k:row[k] for k in ('comparison_id','replicates','included_primary_scenes','matched_block_count','observed_rooms','paired_O1_minus_O0_wer_pp_percentile95')})
        require(row['included_primary_scenes']==156 and row['matched_block_count']==116,'Full primary blocks')
    out.mkdir()
    codes=[]
    for path in (Path(__file__),Path(__file__).with_name('README_S6C_FULL_N03_SUMMARY_V1.md')):
        _,binding=read(path);codes.append(binding)
    prior_attempt,pab=obj(SIM/'staging/s6c/20260910T123540Z/full_n03_summary/before_comparison_schema_fix_v1/SOURCE_INDEX.json')
    for binding in prior_attempt['sources']:read(binding['path'],binding)
    result=dict(status='COMPLETE_EXACT_TABLE_SUMMARY',source_receipts=receipts,comparison_receipt=cb,prior_failed_attempt=pab,
        check_count=CHECKS,sources=SOURCES,codes=codes,complete_population=headline,short_turns=short,lifecycle_all240=lifecycle,
        native_nested_cost_all240=cost,matched_complete_pairs=pair_summary,primary_word_conditional_uncertainty=uncertainty_summary,
        selected_extreme_case_examples=case_results,
        limits=['All full cases follow outcome-informed panel selection, not independent holdout.',
                'Live tracking support and anonymous permutation scores are distinct from actual known-name correctness.',
                'Short-turn contained evidence, any-known support and retrospectively mapped modal correctness are separate.',
                'Model/API/full dispatch costs are nested inclusive costs and concurrent lanes are not additive; native cells span separate batches and reused panel sources.',
                'Source receipt bindings are transitive; this collector reads only already completed scorer tables, not native receipts, events, predictions or PCM.',
                'Selected maximum case differences are descriptive extremes, not typical cases or a predeclared selection criterion.',
                'Primary-word bootstrap does not provide cp confidence intervals or prove equivalence.'])
    binding=save(out/'RESULT.json',result)
    print(json.dumps(binding,indent=2))

if __name__=='__main__':main()
