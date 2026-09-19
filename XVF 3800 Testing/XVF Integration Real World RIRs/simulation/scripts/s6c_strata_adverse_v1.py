"""Fixed-scope existing-score strata synthesis; see README_S6C_STRATA_ADVERSE_V1.md."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tempfile

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
ROOT=REPORT/'strata_adverse_v1'
INDEX=REPORT/'requirement_gap_review_v2/STRATA_AND_STATE_SOURCE_INDEX.json'
INDEX_SHA='bae3ec7011eec5b53ab782c1813ca6107e456db7674fc2f709ca370e045038e5'
INPUT_SHA='97b20d821c671794b24b1f8a4a9d4049fd192767bd0a093309887c279b48e70d'
HIST_SHA='12ee9ccd91a2a924ba2f54b51f622c39c73ed15325073cac5439bad4298dda0f'
METRIC_CODES={'s6b_analysis.py':'1a1df6d92276dcae2f7b71f3463002d566905aef3c799522109287bf85bae754',
              's6a_text_metrics.py':'c7614c33c04cba1f47660c10235198c8cd697963eb42b12a3656b503a8c884cd',
              's4_h2_analysis.py':'0b5d8a227ca87c4dcee48db8118de35444fb32217291bf022feb458f0982d1a0'}
SCHEMA='s6c-strata-adverse-spec.v1'
POPS={'PRIMARY_NONOVERLAP':156,'COMPLETE_OVERLAP':47,'INCOMPLETE_REFERENCE':26,'STRICT_EMPTY_REFERENCE':11}
COMPLETE={'PRIMARY_NONOVERLAP','COMPLETE_OVERLAP'}
ARRAY_DIMS=('corpus','source_quality','source_level_db','noise_category','snr_db','receiver_orientation','obstructed')
DIMS=('room','family','historical_split')+ARRAY_DIMS
SLOT_PROFILES={'anonymous':['C065','C079','C117','C118','C121','C122'],
               'naming':['C088','C091'],'n03':['C067'],'historical':['B00','B01','B36'],
               'n12':['C076'],'cross':['C085','C086']}
SOURCE_NAMES={'anonymous':'full_n01_anonymous_core_v3','naming':'full_n01_naming_core_v3',
              'n03':'full_n03_native_core_v3','historical':'S6B_full_analysis_v1'}
PAIR_PROFILES=[('C065','C067'),('C065','C076'),('C065','C079'),('C065','C121'),
               ('C121','C122'),('C079','C122'),('C117','C118'),('C117','C065'),
               ('C117','C121'),('C118','C079'),('C118','C122'),('B36','C065'),
               ('B36','C067'),('B36','C076')]
METRICS=('word','cp_first_display_label_final_words','cp_latest_revised','unknown_support','inconsistent_returns','empty_insertions')
SELECTION=dict(direction='right minus left; strictly positive is harmful',basis=['rate','count'],
    group='one maximum per contrast/metric/population/basis across all dimension/value groups',
    order='descending exact rational delta, then dimension and value lexically; all tied maxima retained as references',
    narrative='Counts per contrast plus one largest positive rate example per metric/original population; ties use contrast ID, dimension, value. No cross-metric or cross-population ranking.',
    tiny_flags='eligible scenes <5; word/cp words <20; sole support <16000 samples; returns <5; empty exposure <60 seconds. Flags never filter.',
    zero='Zero difference is not harm; no positive group yields an explicit NO_POSITIVE_HARM row.')


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def bind(path,raw=None):
    path=Path(path).resolve();raw=path.read_bytes() if raw is None else raw
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def exact(b,cap=80*1024*1024):
    require(type(b.get('bytes')) is int and 0<=b['bytes']<=cap,'Invalid bounded declaration')
    with Path(b['path']).open('rb') as f:raw=f.read(cap+1)
    require(bind(b['path'],raw)==b and len(raw)<=cap,'Changed exact source buffer: '+b['path'])
    return raw


def unique_pairs(items):
    result={}
    for k,v in items:
        require(k not in result,'Duplicate JSON field');result[k]=v
    return result


def parse(raw):
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,
                      parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))


def doc(b):return parse(exact(b))


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    with path.open('xb') as f:f.write(raw)
    return bind(path,raw)


def fresh(name):
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',name) is not None,'Simple namespace required')
    p=ROOT/name;require(not p.exists(),'Fresh namespace required');return p


def quiet():require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Active quiet lease: defer table streaming')


def routes():
    result=[]
    for slot,profiles in SLOT_PROFILES.items():
        if slot=='cross':items=[('C085','O0','O1'),('C086','O1','O0')]
        else:items=[(p,t,t) for p in profiles for t in ('O0','O1')]
        result.extend(dict(slot=slot,profile_id=p,stream=a,identity_tap=i) for p,a,i in items)
    return result


def contrasts():
    result=[]
    for left,right in PAIR_PROFILES:
        for tap in ('O0','O1'):
            result.append(dict(contrast_id=f'{left}_{right}_{tap}',left=[left,tap,tap],right=[right,tap,tap]))
    for p,a,i in [('C085','O0','O1'),('C086','O1','O0')]:
        result.append(dict(contrast_id=f'C065_{p}_{a}_cross',left=['C065',a,a],right=[p,a,i]))
    return result


def code_bindings():
    p=Path(__file__).resolve();return [bind(p),bind(p.with_name('README_S6C_STRATA_ADVERSE_V1.md'))]


def admit_authority(slot,b):
    a=doc(b)
    require(a['status']=='COMPLETE_REQUESTED_INDEX' and a['requested']==a['scored'] and a['unscored']==0,'Completed full core required')
    require(a['input_index']['sha256']==INPUT_SHA,'Canonical input declaration differs')
    codes={Path(x['path']).name:x['sha256'] for x in a['codes']}
    require(all(codes.get(k)==v for k,v in METRIC_CODES.items()),'Inherited metric/reference/normalizer source differs')
    wanted={(r['profile_id'],r['stream'],r['identity_tap']) for r in routes() if r['slot']==slot}
    if slot=='historical':
        require(b['sha256']==HIST_SHA and a['schema']=='jp_s6b_analysis_v1' and a['scored']==13920,'Exact historical full authority required')
        require(set(SLOT_PROFILES[slot])<=set(a['all240_two_tap_confirmed_profiles']),'Historical full profiles absent')
    else:
        require(a['schema']=='jp_s6c_core_analysis.v3' and len(a['case_ids'])==len(set(a['case_ids']))==240,'Full240 V3 authority required')
        found={(r['profile_id'],r['stream'],r['identity_tap']) for r in a['full240_confirmed_routes'] if r['scenes']==240}
        require(wanted<=found,'Exact full actual routes absent')
        selected={(r['candidate_id'],r['stream'],r['identity_tap']) for r in a['profile_routes'] if r['candidate_id'] in SLOT_PROFILES[slot]}
        require(selected==wanted,'Selected candidate route declaration differs')
    tables={}
    for filename in ('SCENE_RESULTS.csv','STRATA_RESULTS.csv'):
        matched=[(n,t) for n,t in enumerate(a['tables']) if Path(t['path']).name==filename]
        require(len(matched)==1,'Unique original table pointer required');n,t=matched[0]
        require(Path(t['path']).resolve().parent==Path(b['path']).resolve().parent,'Table outside original authority namespace')
        tables[filename]=dict(binding=t,pointer=f'/tables/{n}')
    return dict(slot=slot,status='COMPLETE_AUTHORITY_TABLES_UNREAD',authority=b,schema=a['schema'],tables=tables,
                input_index=a['input_index'],declared_scored_rows=a['scored'],
                case_ids=None if slot=='historical' else a['case_ids'],
                historical_identity_mapping='No original identity_tap column; explicitly admitted original same-tap only' if slot=='historical' else 'Actual profile-route declaration required')


def draft(name):
    quiet();p=fresh(name);raw=INDEX.read_bytes();ib=bind(INDEX,raw);require(ib['sha256']==INDEX_SHA,'Pinned source index differs')
    index=parse(raw);by={x['source_id']:x for x in index['strata_tables']};slots={}
    for slot in SLOT_PROFILES:
        if slot in SOURCE_NAMES:slots[slot]=admit_authority(slot,by[SOURCE_NAMES[slot]]['authority'])
        else:slots[slot]=dict(slot=slot,status='UNRESOLVED_PENDING_COMPLETED_AUTHORITY',authority=None,tables=None,
                              intended_label='full_n12_native_core_v3' if slot=='n12' else 'full_cross_native_core_v3')
    cited=[]
    for rel in ['full_n08_n10_results_v1/RESULT.json','full_n08_n10_results_v1/INTERPRETATION_BINDING_V2.json','full_n08_n10_results_v1/INTERPRETATION_V2.md']:
        cited.append(bind(REPORT/rel))
    specification=dict(schema=SCHEMA,status='DRAFT_UNRESOLVED_NO_ANALYSIS',utc=datetime.now(timezone.utc).isoformat(),
        root_scope='Root-admitted fixed narrative scope, not final operating selection. No N08/N10 extra grid; cite its completed adverse qualifications.',
        source_index=ib,sources=code_bindings(),routes=routes(),contrasts=contrasts(),populations=POPS,dimensions=list(DIMS),
        metrics=list(METRICS),slots=slots,prior_n08_n10_adverse_citations=cited,
        selection=SELECTION,
        limits='Original scored scalar counts and strata only. No new WER/cp/name score, alignment, CI, causality or independent-source claim. Overlapping memberships are not summed.')
    return save(p/'SPEC.json',specification)


def validate_spec(s,resolved=False):
    require(s['schema']==SCHEMA and s['routes']==routes() and s['contrasts']==contrasts(),'Fixed route/contrast scope differs')
    require(s['populations']==POPS and s['dimensions']==list(DIMS) and s['metrics']==list(METRICS),'Fixed population/dimension/metric scope differs')
    require(s['selection']==SELECTION,'Predeclared positive-harm/tiny-support selection differs')
    require(set(s['slots'])==set(SLOT_PROFILES),'Fixed source slots differ')
    for b in s['sources']:exact(b)
    require(s['sources']==code_bindings(),'Current held source/README differs')
    require(s['source_index']['sha256']==INDEX_SHA,'Fixed source authority differs');index=doc(s['source_index'])
    fixed={x['source_id']:x['authority'] for x in index['strata_tables']}
    for slot,entry in s['slots'].items():
        if slot in SOURCE_NAMES:require(entry['authority']==fixed[SOURCE_NAMES[slot]],'Original fixed authority replaced')
        if entry['authority'] is None:
            require(not resolved and slot in ('n12','cross'),'Unresolved source prevents run')
        else:require(admit_authority(slot,entry['authority'])==entry,'Changed source admission')
    cases=set(s['slots']['anonymous']['case_ids'])
    for slot,entry in s['slots'].items():
        if slot!='historical' and entry['authority'] is not None:require(set(entry['case_ids'])==cases,'Full canonical case sets differ')
    for b in s['prior_n08_n10_adverse_citations']:exact(b)
    if resolved:require(s['status']=='RESOLVED_COMPLETE_SOURCES_PENDING_ROOT_RUN_REVIEW','Not a resolved source plan')


def resolve(spec_b,name,replacements):
    quiet();s=doc(spec_b);validate_spec(s);p=fresh(name);seen=set()
    for slot,path,sha in replacements:
        require(slot in ('n12','cross') and slot not in seen and s['slots'][slot]['authority'] is None,'Only distinct pending slots can be filled')
        seen.add(slot);b=bind(path);require(b['sha256']==sha,'Caller-pinned completed receipt differs');s['slots'][slot]=admit_authority(slot,b)
    require(all(x['authority'] is not None for x in s['slots'].values()),'Every pending authority required; no guessed binding')
    s['status']='RESOLVED_COMPLETE_SOURCES_PENDING_ROOT_RUN_REVIEW';s['previous_draft']=spec_b;s['resolved_utc']=datetime.now(timezone.utc).isoformat();validate_spec(s,True)
    return save(p/'SPEC.json',s)


def number(cell,integer=True):
    if cell=='':return None
    if integer:
        require(re.fullmatch(r'[0-9]+',cell) is not None,'Nonnegative integer source count required');return int(cell)
    value=float(cell);require(math.isfinite(value) and value>=0,'Nonnegative finite source value required');return value


def rows_from(raw):
    q=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True);header=q.fieldnames
    require(header and len(header)==len(set(header)),'Unique CSV header required')
    for n,row in enumerate(q,1):
        require(None not in row and None not in row.values(),'Malformed CSV width');yield n,header,row


def memberships(row):
    arrays=parse(row['strata'].encode('utf-8'))
    require(set(arrays)==set(ARRAY_DIMS),'Exactly seven original JSON strata dimensions required')
    result={'room':[row['room']],'family':[row['family_id']],'historical_split':[row['historical_split']]}
    for key,values in arrays.items():
        require(isinstance(values,list) and values and all(isinstance(x,str) for x in values) and len(values)==len(set(values)),'Unique nonempty original stratum memberships required')
        result[key]=values
    return {(dimension,value,row['population']) for dimension,values in result.items() for value in values}


def route_key(row,slot):
    if slot=='historical':
        require('identity_tap' not in row and 'route' not in row,'Historical absence must remain explicit')
        identity=row['stream']
    else:
        identity=row['identity_tap'];require(row['route']==f"{row['stream']}_ASR_{identity}_ID",'Actual route label differs')
    return row['profile_id'],row['stream'],identity


def sums(rows,field):
    values=[number(r[field]) for r in rows];present=[v for v in values if v is not None]
    return sum(present) if present else None


def verify_aggregate(aggregate,chosen):
    require(number(aggregate['scenes'])==len(chosen),'Stratum membership count differs')
    require(math.isclose(number(aggregate['duration_sec'],False),sum(number(r['duration_sec'],False) for r in chosen),rel_tol=0,abs_tol=1e-7),'Stratum source-duration sum differs')
    count_fields=['unknown_samples','sole_active_samples','return_consistent','return_inconsistent','return_unknown','source_turns','supported_turns','unknown_turns']
    for prefix in ('word','cp_first_display_label_final_words','cp_latest_revised'):
        for suffix in ('errors','substitutions','deletions','insertions','reference_words','hypothesis_words'):
            field=prefix+'_'+suffix;require(number(aggregate[field])==sums(chosen,field),'Original aggregate field sum differs: '+field)
        require(number(aggregate[prefix+'_scored_scenes'])==sum(r[prefix+'_errors']!='' for r in chosen),'Scored-scene denominator differs')
    for field in count_fields:
        require(number(aggregate[field])==sum(number(r[field]) or 0 for r in chosen),'Source support/return aggregate differs: '+field)
    if aggregate['population']=='STRICT_EMPTY_REFERENCE':require(number(aggregate['empty_insertions'])==sum(number(r['empty_insertions']) or 0 for r in chosen),'Empty insertion aggregate differs')
    else:require(aggregate['empty_insertions']=='','Empty-only counter leaked outside empty population')


def metric_view(aggregate,chosen,metric):
    pop=aggregate['population'];cases=sorted(r['case_id'] for r in chosen);eligible=[];num=den=None;unit=None;reason=None
    if metric in ('word','cp_first_display_label_final_words','cp_latest_revised'):
        unit='reference_words'
        if pop not in COMPLETE:reason='NO_COMPLETE_NONEMPTY_FULL_REFERENCE_METRIC'
        else:
            eligible=sorted(r['case_id'] for r in chosen if r[metric+'_errors']!='' and r[metric+'_reference_words']!='' and number(r[metric+'_reference_words'])>0)
            num=number(aggregate[metric+'_errors']);den=number(aggregate[metric+'_reference_words'])
    elif metric=='unknown_support':
        unit='sole_active_samples';num=number(aggregate['unknown_samples']);den=number(aggregate['sole_active_samples'])
        eligible=sorted(r['case_id'] for r in chosen if r['unknown_samples']!='' and r['sole_active_samples']!='' and number(r['sole_active_samples'])>0)
    elif metric=='inconsistent_returns':
        unit='classified_return_turns';num=number(aggregate['return_inconsistent'])
        den=sum(number(aggregate[k]) for k in ('return_consistent','return_inconsistent','return_unknown'))
        eligible=sorted(r['case_id'] for r in chosen if all(r[k]!='' for k in ('return_consistent','return_inconsistent','return_unknown')) and sum(number(r[k]) for k in ('return_consistent','return_inconsistent','return_unknown'))>0)
    else:
        unit='source_seconds'
        if pop!='STRICT_EMPTY_REFERENCE':reason='EMPTY_REFERENCE_ONLY'
        else:
            num=number(aggregate['empty_insertions']);den=Fraction(aggregate['duration_sec'])
            eligible=sorted(r['case_id'] for r in chosen if r['empty_insertions']!='')
    if reason is None and (num is None or den is None or den<=0):reason='ZERO_OR_UNAVAILABLE_METRIC_DENOMINATOR'
    rate=None if reason else Fraction(num)/Fraction(den)*(60 if metric=='empty_insertions' else 1)
    tiny=[]
    if len(eligible)<5:tiny.append('fewer_than_5_eligible_scenes')
    threshold={'reference_words':20,'sole_active_samples':16000,'classified_return_turns':5,'source_seconds':60}[unit]
    if den is not None and den<threshold:tiny.append('small_'+unit)
    return dict(numerator=num,denominator=float(den) if isinstance(den,Fraction) else den,
                denominator_exact=None if den is None else str(den),denominator_unit=unit,
                rate=None if rate is None else float(rate),rate_exact=None if rate is None else str(rate),
                rate_unit='insertions_per_source_minute' if metric=='empty_insertions' else 'fraction',
                membership_case_ids=cases,eligible_case_ids=eligible,eligible_scenes=len(eligible),missing_or_ineligible_scenes=len(cases)-len(eligible),
                unavailable_reason=reason,tiny_support_flags=tiny)


def paired_metric(left,right,metric):
    require(left['membership_case_ids']==right['membership_case_ids'],'Equal counts are insufficient: exact stratum cases differ')
    match=left['eligible_case_ids']==right['eligible_case_ids']
    available=match and left['rate_exact'] is not None and right['rate_exact'] is not None
    if available and metric in ('word','cp_first_display_label_final_words','cp_latest_revised'):
        require(Fraction(left['denominator_exact'])==Fraction(right['denominator_exact']),'Paired full-reference word denominators differ')
    rate=Fraction(right['rate_exact'])-Fraction(left['rate_exact']) if available else None
    count=(right['numerator']-left['numerator']) if match and left['numerator'] is not None and right['numerator'] is not None else None
    # Count-only diagnostics retain observed zero-exposure counts, but never masquerade as a rate.
    return dict(metric=metric,eligible_cases_equal=match,left=left,right=right,
                right_minus_left_count=count,right_minus_left_rate=None if rate is None else float(rate),
                rate_delta_exact=None if rate is None else str(rate),
                rate_delta_unavailable_reason=None if available else ('ELIGIBLE_CASE_SETS_DIFFER' if not match else 'ONE_OR_BOTH_METRIC_RATES_UNAVAILABLE'))


def choose_harms(rows):
    chosen=[]
    grouped=defaultdict(list)
    for r in rows:grouped[r['contrast_id'],r['metric'],r['population']].append(r)
    for key,items in sorted(grouped.items()):
        for basis,field in [('rate','rate_delta_exact'),('count','right_minus_left_count')]:
            positive=[r for r in items if r[field] is not None and Fraction(r[field])>0]
            if not positive:
                chosen.append(dict(contrast_id=key[0],metric=key[1],population=key[2],basis=basis,status='NO_POSITIVE_HARM',example=None));continue
            maximum=max(Fraction(r[field]) for r in positive)
            ties=sorted([r for r in positive if Fraction(r[field])==maximum],key=lambda r:(r['dimension'],r['value']))
            chosen.append(dict(contrast_id=key[0],metric=key[1],population=key[2],basis=basis,status='DESCRIPTIVE_POSITIVE_MAXIMUM',
                exact_delta=str(maximum),example=ties[0],all_tied_groups=[dict(dimension=r['dimension'],value=r['value'],pair_row_sha256=digest(r)) for r in ties]))
    return chosen


def csv_save(path,header,rows):
    with path.open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=header);writer.writeheader();writer.writerows(rows)
    return bind(path)


def run(spec_b,name):
    quiet();spec=doc(spec_b);validate_spec(spec,True);out=fresh(name);out.mkdir(parents=True)
    wanted={tuple(r[k] for k in ('profile_id','stream','identity_tap')):r['slot'] for r in routes()}
    scenes={};aggregates={};source_rows=[];admissions=[];canonical_cases=set(spec['slots']['anonymous']['case_ids'])
    require(len(canonical_cases)==240,'Exact240 canonical cases required')
    for slot,entry in spec['slots'].items():
        quiet();scene_b=entry['tables']['SCENE_RESULTS.csv']['binding'];strata_b=entry['tables']['STRATA_RESULTS.csv']['binding']
        seen_table=0;selected={};numbers={}
        for n,header,row in rows_from(exact(scene_b)):
            seen_table+=1
            if row['profile_id'] not in SLOT_PROFILES[slot]:continue
            key=route_key(row,slot);require(key in wanted and wanted[key]==slot,'Unregistered source route')
            rowkey=key+(row['case_id'],);require(rowkey not in selected,'Duplicate scene route key')
            require(row['case_id'] in canonical_cases and row['population'] in POPS,'Unexpected canonical case/population')
            selected[rowkey]=row;numbers[rowkey]=n
        require(seen_table==entry['declared_scored_rows'],'Original scene-table row count differs')
        for route in [k for k,v in wanted.items() if v==slot]:
            selected_rows={k[-1]:v for k,v in selected.items() if k[:3]==route}
            require(set(selected_rows)==canonical_cases,'Full route case set differs')
            require(dict(Counter(r['population'] for r in selected_rows.values()))==POPS,'Four population denominators differ')
            scenes[route]=selected_rows
            groups=defaultdict(set)
            for case,row in selected_rows.items():
                for key in memberships(row):groups[key].add(case)
            aggregates[route]=dict(expected=groups,actual={})
        selected_strata=0
        for n,header,row in rows_from(exact(strata_b)):
            if row['profile_id'] not in SLOT_PROFILES[slot]:continue
            candidates=[key for key in wanted if key[:2]==(row['profile_id'],row['stream']) and wanted[key]==slot]
            require(len(candidates)==1,'Strata lacks identity column: exactly one admitted route per profile/ASR required')
            route=candidates[0];key=(row['stratum_dimension'],row['stratum_value'],row['population']);expected=aggregates[route]['expected'];actual=aggregates[route]['actual']
            require(key in expected and key not in actual,'Unexpected/duplicate stratum membership key')
            members=sorted(expected[key]);chosen=[scenes[route][case] for case in members];verify_aggregate(row,chosen)
            record=dict(slot=slot,profile_id=route[0],stream=route[1],identity_tap=route[2],dimension=key[0],value=key[1],population=key[2],
                original_aggregate_cells=row,aggregate_row=n,aggregate_table=strata_b,scene_table=scene_b,
                member_case_ids=members,member_scene_rows=[numbers[route+(case,)] for case in members],
                member_scene_cell_hashes=[digest(scenes[route][case]) for case in members])
            actual[key]=record;source_rows.append(record);selected_strata+=1
        for route in [k for k,v in wanted.items() if v==slot]:require(set(aggregates[route]['expected'])==set(aggregates[route]['actual']),'Original STRATA must cover every reconstructed membership group')
        admissions.append(dict(slot=slot,authority=entry['authority'],scene=scene_b,strata=strata_b,
                               original_scene_table_rows=seen_table,selected_scene_rows=len(selected),selected_stratum_rows=selected_strata))
    paired=[]
    for contrast in contrasts():
        left_key=tuple(contrast['left']);right_key=tuple(contrast['right']);la=aggregates[left_key]['actual'];ra=aggregates[right_key]['actual']
        require(set(la)==set(ra),'Pair stratum keys differ')
        for key in sorted(la):
            left,right=la[key],ra[key];require(left['member_case_ids']==right['member_case_ids'],'Exact cross-route stratum membership differs')
            if key[2] in COMPLETE:
                for case in left['member_case_ids']:
                    for metric in ('word','cp_first_display_label_final_words','cp_latest_revised'):
                        lv=scenes[left_key][case][metric+'_reference_words'];rv=scenes[right_key][case][metric+'_reference_words']
                        if lv!='' and rv!='':require(number(lv)==number(rv),'Per-scene paired reference-word denominator differs')
            for metric in METRICS:
                views=[metric_view(record['original_aggregate_cells'],[scenes[route][case] for case in record['member_case_ids']],metric) for record,route in [(left,left_key),(right,right_key)]]
                result=paired_metric(*views,metric)
                paired.append(dict(contrast_id=contrast['contrast_id'],left_route=contrast['left'],right_route=contrast['right'],
                    dimension=key[0],value=key[1],population=key[2],left_original_row_sha256=digest(left),right_original_row_sha256=digest(right),**result))
    artifacts=[]
    artifacts.append(save(out/'ORIGINAL_STRATA_AND_MEMBERSHIPS.json',dict(schema='s6c-selected-original-strata.v1',records=source_rows)))
    flat=[]
    for p in paired:
        row={k:v for k,v in p.items() if k not in ('left','right','left_route','right_route')}
        row.update(left_route=json.dumps(p['left_route']),right_route=json.dumps(p['right_route']))
        for side in ('left','right'):
            row.update({side+'_'+k:json.dumps(v) if isinstance(v,list) else v for k,v in p[side].items()})
        flat.append(row)
    artifacts.append(csv_save(out/'PAIRED_STRATA_METRICS.csv',list(flat[0]),flat))
    harms=choose_harms(paired);artifacts.append(save(out/'DESCRIPTIVE_HARM_EXAMPLES.json',dict(selection=spec['selection'],examples=harms)))
    paragraphs=['# Fixed-scope strata/adverse synthesis','',
        'This report compares existing score aggregates after verifying exact per-scene memberships. All four populations and ten dimensions remain separate. Multi-memberships overlap; do not sum them. Core strata do not measure actual known-name accuracy. No confidence interval, new score, reset/timing causality or final operating selection is produced.','',
        f'{len(routes())} routes, {len(contrasts())} explicit contrasts, {len(source_rows)} original selected strata and {len(paired)} paired metric rows are retained.',
        'Full word/first-display/latest cp values are unavailable on incomplete and strict-empty populations. Unknown support, classified returns and empty insertions use their own observed denominators. Primary word errors use serialized WER; complete overlap word errors use the inherited MIMO scope.','',
        'The following compact rate maxima are post-result descriptive examples within this predeclared analysis. Strictly positive differences only; zero is not harm. Tiny-support groups are retained and flagged. Count maxima and all tied groups are in the companion JSON.','']
    paragraphs+=['| Contrast | Positive metric/population rate maxima | Count maxima |','| --- | ---: | ---: |']
    for contrast in contrasts():
        subset=[h for h in harms if h['contrast_id']==contrast['contrast_id'] and h['example'] is not None]
        paragraphs.append(f"| {contrast['contrast_id']} | {sum(h['basis']=='rate' for h in subset)} | {sum(h['basis']=='count' for h in subset)} |")
    paragraphs+=['','These are descriptive flags across overlapping groups, not independent failures or an accuracy ranking. Every per-contrast maximum and all ties are retained in DESCRIPTIVE_HARM_EXAMPLES.json. The brief examples below take the largest positive rate delta per metric and original population across these already-selected per-contrast maxima, then contrast ID/dimension/value lexically; metrics and populations are never compared to one another.','']
    for metric in METRICS:
        for population in POPS:
            candidates=[h for h in harms if h['metric']==metric and h['population']==population and h['basis']=='rate' and h['example'] is not None]
            if not candidates:continue
            h=sorted(candidates,key=lambda h:(-Fraction(h['exact_delta']),h['contrast_id'],h['example']['dimension'],h['example']['value']))[0]
            p=h['example'];l=p['left'];r=p['right']
            paragraphs.append(f"- {h['contrast_id']}, {metric} / {population}: {p['dimension']}={p['value']}; left {l['numerator']}/{l['denominator_exact']}, right {r['numerator']}/{r['denominator_exact']} ({r['rate_unit']}); right-left {float(Fraction(h['exact_delta'])):.6g}. Eligible scenes {l['eligible_scenes']}/{r['eligible_scenes']}; flags {sorted(set(l['tiny_support_flags']+r['tiny_support_flags'])) or 'none'}.")
    paragraphs.append('')
    paragraphs+=['N08/N10 adverse qualifications remain in the separately bound completed report; they are not added to this grid. Future package scope must retain access to every original paired row and unavailable result.']
    narrative=out/'NARRATIVE.md';narrative.write_text('\n'.join(paragraphs)+'\n',encoding='utf-8');artifacts.append(bind(narrative))
    for slot in spec['slots'].values():exact(slot['authority'])
    exact(spec_b)
    return save(out/'RESULT.json',dict(schema='s6c-strata-adverse-result.v1',status='COMPLETE_FIXED_DESCRIPTIVE_SCORE_TABLE_SCOPE',utc=datetime.now(timezone.utc).isoformat(),
        spec=spec_b,sources=code_bindings(),source_admissions=admissions,selected_routes=28,contrasts=30,selected_scene_rows=28*240,
        original_selected_strata=len(source_rows),paired_metric_rows=len(paired),artifacts=artifacts,
        scope='Existing scored values with exact original memberships; no new scoring or inferred known-name accuracy. No pooled overlapping strata or final selection.',models=0,rescoring=0,native_log_reads=0))


def checks():
    done=[]
    def test(name,fn):fn();done.append(name)
    def fails(fn):
        try:fn()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Expected rejection')
    test('exact28routes30contrasts',lambda:require(len(routes())==28 and len(contrasts())==30 and len({x['contrast_id'] for x in contrasts()})==30,'grid'))
    row=dict(room='R',family_id='F',historical_split='D',population='PRIMARY_NONOVERLAP',strata=json.dumps({k:['a','b'] if k=='corpus' else ['a'] for k in ARRAY_DIMS}))
    test('seven_arrays_plus_three_columns',lambda:require(len(memberships(row))==11 and ('family','F','PRIMARY_NONOVERLAP') in memberships(row),'membership'))
    test('duplicate_membership_rejected',lambda:fails(lambda:memberships(dict(row,strata=json.dumps({k:['a','a'] for k in ARRAY_DIMS})))))
    base=dict(numerator=1,denominator=10,denominator_exact='10',rate=0.1,rate_exact='1/10',membership_case_ids=['A'],eligible_case_ids=['A'])
    test('equal_count_wrong_membership_rejected',lambda:fails(lambda:paired_metric(base,dict(base,membership_case_ids=['B']),'word')))
    test('eligible_mismatch_is_unavailable',lambda:require(paired_metric(base,dict(base,eligible_case_ids=[]),'word')['right_minus_left_rate'] is None,'eligibility'))
    test('paired_reference_denominator_mismatch_rejected',lambda:fails(lambda:paired_metric(base,dict(base,denominator_exact='11'),'word')))
    aggregate=dict(population='INCOMPLETE_REFERENCE')
    test('incomplete_fullword_null',lambda:require(metric_view(aggregate,[{'case_id':'A'}],'word')['numerator'] is None,'incomplete'))
    test('historical_same_tap_absence',lambda:require(route_key({'profile_id':'B36','stream':'O1'},'historical')==('B36','O1','O1'),'historical'))
    test('cross_route_not_fabricated',lambda:fails(lambda:route_key({'profile_id':'C085','stream':'O0','identity_tap':'O1','route':'O0_ASR_O0_ID'},'cross')))
    def positive():
        x=dict(contrast_id='x',metric='word',population='PRIMARY_NONOVERLAP',dimension='room',value='z',rate_delta_exact='0',right_minus_left_count=0)
        require(all(h['status']=='NO_POSITIVE_HARM' for h in choose_harms([x])),'zero harm')
        y=dict(x,rate_delta_exact='1/10',right_minus_left_count=1);z=dict(y,value='a')
        require(all(h['example']['value']=='a' and len(h['all_tied_groups'])==2 for h in choose_harms([y,z])),'tie order')
    test('positive_only_exact_rational_ties',positive)
    def tiny():
        a=dict(population='PRIMARY_NONOVERLAP',word_errors='1',word_reference_words='2');v=metric_view(a,[dict(case_id='A',word_errors='1',word_reference_words='2')],'word')
        require(v['rate']==.5 and len(v['tiny_support_flags'])==2,'tiny retained')
    test('tiny_support_retained',tiny)
    def buffer():
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a';p.write_bytes(b'abc');b=bind(p);p.write_bytes(b'abd');fails(lambda:exact(b))
    test('changed_exact_buffer_rejected',buffer)
    test('nonfinite_metric_rejected',lambda:fails(lambda:number('NaN',False)))
    return dict(status='PASS_MODEL_FREE',checks=len(done),names=done,source_tables_read=0,models=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['checks','draft','resolve','run']);p.add_argument('--name',required=True)
    p.add_argument('--spec',type=Path);p.add_argument('--spec-sha256');p.add_argument('--authority',nargs=3,action='append',default=[],metavar=('SLOT','PATH','SHA256'));a=p.parse_args()
    if a.action=='checks':result=save(fresh(a.name)/'CHECKS.json',dict(**checks(),sources=code_bindings()))
    elif a.action=='draft':result=draft(a.name)
    else:
        require(a.spec is not None and a.spec_sha256 is not None,'Explicit source plan binding required');b=bind(a.spec);require(b['sha256']==a.spec_sha256,'Caller-pinned plan differs')
        result=resolve(b,a.name,a.authority) if a.action=='resolve' else run(b,a.name)
    print(json.dumps(result,indent=2))
