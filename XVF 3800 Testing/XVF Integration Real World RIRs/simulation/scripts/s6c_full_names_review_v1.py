"""Independent completed full naming table review; README_S6C_FULL_NAMES_REVIEW_V1.md."""
from __future__ import annotations
import csv,hashlib,io,json,math,os
from collections import Counter,defaultdict
from pathlib import Path

SIM=Path(__file__).resolve().parents[1];REPORT=SIM/'reports/S6C/20260910T123540Z';OUT=REPORT/'full_naming_component_review_v2'
AUTHORITIES=[('original_naming','full_n01_naming_names_v3','7fd6fbecd0cfbdd77e64333e65bb9ea19d5a9e5780f2b763a0d7470307b58bce'),
             ('common_duration','full_n01_common_duration_names_v3','1da2a2dd1c9f50a9aefb89a0e024de03975c629914ecb8aac673cf817366118b')]
DURATION_SHA='6c3d135b01336995ae84a73196c5bcb1ee10f40b4e2c0f2da194d0026655340a'
SAMPLES=('sole_active_samples','correct_name_samples','wrong_known_name_samples','unknown_name_samples')
WAITS=('first_any_name','first_correct_name','first_confirmed_correct_name','first_stable_correct_name')
ROSTERS=('ALL','ENROLLED','INTENDED_BUT_UNAVAILABLE','WITHHELD_OR_UNSELECTED','NO_GALLERY_CONTROL')
IDS={'original_naming':('C088','C091','C105','C106','C111','C114'),'common_duration':tuple('C%d'%i for i in range(141,147))}

def need(ok,message):
    if not ok:raise ValueError(message)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def bind(path,raw=None):
    p=Path(path).resolve();raw=p.read_bytes() if raw is None else raw
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
class Reader:
    def __init__(self):self.bindings={};self.cache={}
    def raw(self,b):
        p=str(Path(b['path']).resolve())
        if p not in self.cache:self.cache[p]=Path(p).read_bytes()
        raw=self.cache[p];actual=bind(p,raw);need(actual['sha256']==b['sha256'] and ('bytes' not in b or len(raw)==b['bytes']),'Changed bound table/metadata '+p)
        self.bindings[p]=actual;return raw
    def json(self,b):return json.loads(self.raw(b))
    def table(self,receipt,name,field='tables'):
        bs=[b for b in receipt[field] if Path(b['path']).name==name];need(len(bs)==1,'Unique table binding '+name)
        rows=list(csv.DictReader(io.StringIO(self.raw(bs[0]).decode('utf-8-sig'))))
        return rows,bs[0]
def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode());f.flush();os.fsync(f.fileno())
    return bind(p)
def num(v):
    if v in ('',None):return None
    n=float(v);need(math.isfinite(n),'Finite source table value required');return n
def integer(v):
    n=num(v);need(n is not None and n>=0 and n==int(n),'Nonnegative sample/count integer required');return int(n)
def occurrence(r):return r['case_id'],int(r['segment_index']),r['source_id'],r['metadata_identity']
def route(r):return r['profile_id'],r['stream'],r['identity_tap']
def corpus(person):return 'CMU ARCTIC' if person.startswith('CMU_ARCTIC_') else 'HiFiTTS' if person.startswith('HIFITTS_') else 'Common Voice' if person.startswith('CV_') else 'INVALID'
def quantiles(values):
    valid=sorted(float(v) for v in values if v is not None)
    def pct(q):
        if not valid:return None
        t=(len(valid)-1)*q;a=math.floor(t);b=math.ceil(t);return valid[a]+(valid[b]-valid[a])*(t-a)
    return dict(count=len(values),observed=len(valid),missing=len(values)-len(valid),p50=pct(.5),p90=pct(.9),p95=pct(.95),maximum=max(valid,default=None))
def equal(actual,expected,message):
    if isinstance(expected,dict):
        need(set(actual)==set(expected),message+' dictionary keys')
        for k,v in expected.items():equal(actual[k],v,message+'/'+k)
    elif expected is None:need(actual in ('',None),message+' unavailable')
    elif isinstance(expected,(int,float)):
        n=num(actual);need(n is not None and math.isclose(n,expected,rel_tol=1e-10,abs_tol=1e-9),message+' numeric mismatch')
    else:need(actual==expected,message+' value differs')

def aggregate(rows):
    value=dict(source_occurrences=len(rows),reference_people=len({r['metadata_identity'] for r in rows}),missing_source_support_turns=sum(r['sole_active_samples']=='' for r in rows))
    for k in SAMPLES:value[k]=sum(integer(r[k]) for r in rows)
    for k in WAITS:
        vals=[num(r[k+'_wait_sec']) for r in rows]
        value[k+'_wait_sec_summary']=quantiles(vals);value[k+'_wait_sec_statuses']=dict(Counter(r[k+'_status'] for r in rows))
        value[k+'_wait_sec_observed']=sum(v is not None for v in vals);value[k+'_wait_sec_missing']=sum(v is None for v in vals)
    return value

def groups_and_rosters(reader,label,receipt):
    turns,tb=reader.table(receipt,'TURNS.csv');profile,pb=reader.table(receipt,'PROFILE_NAME_RESULTS.csv');retained,rb=reader.table(receipt,'RETAINED_ROWS.csv');coverage,cb=reader.table(receipt,'COVERAGE.csv')
    q=reader.json(receipt['Q']);qmap={(r['case_id'],r['segment_index']):(r['source_id'],r['identity']) for r in q['rows']}
    need(len(qmap)==len(q['rows'])==777,'Exact777 Q occurrences required')
    bank=reader.json(receipt['bank']);complete={s['case_id']:s['all_speaker_reference_complete'] is True and s['transcript_valid'] is True for s in bank['scenes']}
    scoremap=reader.json(receipt['scorer_map']);maprows=list(scoremap['rows'])
    for extension in receipt['scorer_map_extensions']:maprows.extend(reader.json(extension['scorer_map'])['rows'])
    galleries={}
    for g in maprows:
        k=(g['gallery_condition'],int(g['enrollment_tier']),g.get('case_id'));need(k not in galleries,'Duplicate scorer roster assignment');galleries[k]=g
    expected_routes={(p,t,t) for p in IDS[label] for t in ('O0','O1')};expected_coverage={(*r,c) for r in expected_routes for c in complete}
    cv={(r['profile_id'],r['stream'],r['identity_tap'],r['case_id']):r for r in coverage}
    need(len(coverage)==len(cv)==len(expected_coverage)==2880 and set(cv)==expected_coverage and all(r['status']=='SCORED' for r in coverage),'Exact2880 complete coverage rows required')
    groups=defaultdict(list);line_numbers={};checks=0
    for line,r in enumerate(turns,1):
        k=route(r);need(k in expected_routes,'Unexpected naming route');occ=occurrence(r)
        need(qmap[occ[:2]]==occ[2:],'Wrong Q source/person occurrence');need((*k,*occ) not in line_numbers,'Duplicate source turn');line_numbers[(*k,*occ)]=line
        samples=[integer(r[x]) for x in SAMPLES];need(samples[0]==sum(samples[1:]),'Live correct/wrong/Unknown partition');checks+=1
        expected_status='SCORED_KNOWN_SOURCE_SUPPORT' if complete[r['case_id']] else 'LIMITED_KNOWN_TARGET_SUPPORT'
        need(r['activity_available']=='True' and r['status']==expected_status,'Missing or incorrectly classified mapped source support')
        g=galleries.get((r['gallery_condition'],int(r['enrollment_tier']),r['case_id']),galleries.get((r['gallery_condition'],int(r['enrollment_tier']),None)))
        need(g is not None,'Exact scorer roster missing');who=r['metadata_identity']
        expected='ENROLLED' if who in g['available_identities'] else 'INTENDED_BUT_UNAVAILABLE' if who in g['intended_identities'] else 'WITHHELD_OR_UNSELECTED'
        need(r['roster_status']==expected,'Roster partition differs from exact scorer map');checks+=1
        if expected!='ENROLLED':need(samples[1]==0,'Unavailable/withheld source cannot be correctly enrolled')
        for metric in WAITS:
            wait=num(r[metric+'_wait_sec']);status=r[metric+'_status'];need((wait is not None)==(status=='OBSERVED'),'Observed wait/status mismatch');checks+=1
            if wait is None:need(status=='RIGHT_CENSORED_AT_END_OF_OBSERVED_SUPPORT','Unexpected missing wait disposition')
        stable=num(r['first_stable_correct_name_wait_sec']);onset=num(r['retrospective_stable_interval_onset_wait_sec'])
        need((stable is None)==(onset is None),'Stable causal attainment/onset missingness differs')
        if stable is not None:need(abs(stable-onset-.5)<1e-8 and num(r['stable_name_observation_sec'])>=.5,'Stable0.5s criterion confused with onset')
        groups[k].append(r)
    need(set(groups)==expected_routes and len(turns)==9324,'Exact9324 turn rows required')
    for k,rs in groups.items():
        need(len(rs)==777 and len({occurrence(r) for r in rs})==777,'Every route must retain777 unique turns')
        need(sum(complete[r['case_id']] for r in rs)==693,'Complete-reference known turns must remain693')
    tablekeys={(route(r),r['roster_status']):r for r in profile};need(len(tablekeys)==len(profile)==60,'Exactly60 profile/roster summary rows')
    compact=[];observed_sets=[]
    for k in sorted(groups):
        rs=groups[k]
        for roster in ROSTERS:
            chosen=[r for r in rs if roster=='ALL' or r['roster_status']==roster];out=tablekeys[k,roster];ag=aggregate(chosen)
            equal(out['source_turns'],len(chosen),'profile turn count');equal(out['unmapped_turns'],0,'profile missing support');equal(out['scored_scenes'],240,'profile scenes');checks+=3
            for metric in SAMPLES:equal(out[metric],ag[metric],'profile '+metric);checks+=1
            for metric in WAITS:
                equal(out[metric+'_observed_turns'],ag[metric+'_wait_sec_observed'],'profile observed');equal(out[metric+'_missing_turns'],ag[metric+'_wait_sec_missing'],'profile censored')
                equal(json.loads(out[metric+'_conditional_wait_sec']),ag[metric+'_wait_sec_summary'],'profile conditional wait');checks+=3
        ag=aggregate(rs);partition={status:aggregate([r for r in rs if r['roster_status']==status]) for status in ROSTERS[1:]}
        compact.append(dict(scope=label,profile_id=k[0],stream=k[1],identity_tap=k[2],gallery_condition=rs[0]['gallery_condition'],tier=int(rs[0]['enrollment_tier']),
            source_turns=777,complete_reference_turns=693,incomplete_known_source_turns=84,**{m:ag[m] for m in SAMPLES},
            roster_partition={s:{m:v[m] for m in ('source_occurrences','reference_people',*SAMPLES)} for s,v in partition.items()},
            waits={m:dict(observed=ag[m+'_wait_sec_observed'],censored=ag[m+'_wait_sec_missing'],conditional=ag[m+'_wait_sec_summary']) for m in WAITS}))
        for metric in WAITS[2:]:
            observed=sorted(occurrence(r) for r in rs if r[metric+'_wait_sec']!='');censored=sorted(occurrence(r) for r in rs if r[metric+'_wait_sec']=='')
            observed_sets.append(dict(scope=label,profile_id=k[0],stream=k[1],metric=metric,observed_keys=observed,observed_count=len(observed),censored_count=len(censored),censored_key_sha256=digest(censored),full_key_sha256=digest(sorted(observed+censored)),table=tb))
    return dict(turns=turns,groups=groups,profiles=profile,retained=retained,coverage=cv,turn_binding=tb,profile_binding=pb,retained_binding=rb,coverage_binding=cb,
        galleries=galleries,line_numbers=line_numbers,summary=compact,observed_sets=observed_sets,checks=checks)

def compare_common(reader,duration,data):
    groups={(p,t):rs for (p,t,i),rs in data['groups'].items()};checks=0;tables={}
    for b in duration['artifacts']:
        rows,tb=reader.table(duration,Path(b['path']).name,'artifacts');tables[Path(b['path']).name]=rows
    # Independently reproduce summaries and paired tables from the original
    # complete turn rows rather than rerunning the descriptive collector.
    for filename in ('TIER_PROFILE_RESULTS.csv','CORPUS_TIER_RESULTS.csv'):
        for out in tables[filename]:
            rs=groups[out['profile_id'],out['stream']];chosen=[r for r in rs if out['roster_status']=='ALL' or r['roster_status']==out['roster_status']]
            if 'corpus' in out:chosen=[r for r in chosen if corpus(r['metadata_identity'])==out['corpus']]
            ag=aggregate(chosen)
            for k,v in ag.items():equal(json.loads(out[k]) if isinstance(v,dict) else out[k],v,filename+'/'+k);checks+=1
    stable=[];fixed=[]
    for side,pids in (('A',('C141','C142','C143')),('B',('C144','C145','C146'))):
        rosters=[]
        for pid,tier in zip(pids,(5,15,30)):
            g=data['galleries']['COMMON30_FIXED_ROSTER_'+side,tier,None];who=set(g['available_identities'])
            need(who==set(g['intended_identities']) and len(who)==g['loaded_count']==14 and not g['unavailable_identities'],'Common fixed14 actual map differs')
            need(Counter(corpus(x) for x in who)=={'CMU ARCTIC':9,'HiFiTTS':5},'Common fixed roster corpus composition differs');rosters.append(who);checks+=1
        need(rosters[0]==rosters[1]==rosters[2],'Common identities change across tiers')
        fixed.append(dict(rotation=side,identities=sorted(rosters[0]),tier_counts=[14,14,14],corpus_counts={'CMU ARCTIC':9,'HiFiTTS':5}))
        for tap in ('O0','O1'):
            allkeys=[{occurrence(r):r for r in groups[p,tap]} for p in pids]
            need(set(allkeys[0])==set(allkeys[1])==set(allkeys[2]),'Tier source-key sets differ')
            for key in allkeys[0]:need(len({(a[key]['roster_status'],a[key]['sole_active_samples']) for a in allkeys})==1,'Tier roster/support substitution');checks+=1
            for metric in WAITS[2:]:
                sets=[{occurrence(r) for r in groups[p,tap] if r[metric+'_wait_sec']!=''} for p in pids]
                stable.append(dict(rotation=side,stream=tap,metric=metric,profiles=list(pids),counts=list(map(len,sets)),same_observed_set_across_tiers=sets[0]==sets[1]==sets[2],observed_set_hashes=[digest(sorted(s)) for s in sets]))
    for filename in ('POOLED_TIER_DELTA.csv','WITHIN_PERSON_TIER_DELTA.csv'):
        for out in tables[filename]:
            a=groups[out['left_profile'],out['stream']];b=groups[out['right_profile'],out['stream']]
            if filename.startswith('WITHIN'):
                a=[r for r in a if r['metadata_identity']==out['metadata_identity']];b=[r for r in b if r['metadata_identity']==out['metadata_identity']]
            elif out['roster_status']!='ALL':
                a=[r for r in a if r['roster_status']==out['roster_status']];b=[r for r in b if r['roster_status']==out['roster_status']]
            need({occurrence(r) for r in a}=={occurrence(r) for r in b},'Paired occurrence substitution');equal(out['paired_occurrences'],len(a),'paired denominator');equal(out['paired_people'],len({r['metadata_identity'] for r in a}),'paired people');checks+=2
            for k in SAMPLES:
                av=sum(integer(r[k]) for r in a);bv=sum(integer(r[k]) for r in b)
                for f,v in (('left_'+k,av),('right_'+k,bv),('right_minus_left_'+k,bv-av)):equal(out[f],v,'paired sample '+f);checks+=1
    for out in tables['PAIRED_NAME_DELAY_RESULTS.csv']:
        a={occurrence(r):r for r in groups[out['left_profile'],out['stream']] if out['roster_status']=='ALL' or r['roster_status']==out['roster_status']}
        b={occurrence(r):r for r in groups[out['right_profile'],out['stream']] if out['roster_status']=='ALL' or r['roster_status']==out['roster_status']};need(set(a)==set(b),'Paired wait source set differs')
        metric=out['metric'];left={k for k in a if a[k][metric]!=''};right={k for k in b if b[k][metric]!=''};both=left&right
        counts=dict(paired_occurrences=len(a),both_observed=len(both),left_only_observed=len(left-right),right_only_observed=len(right-left),neither_observed=len(set(a)-(left|right)))
        for k,v in counts.items():equal(out[k],v,'paired delay '+k);checks+=1
        equal(json.loads(out['conditional_right_minus_left_wait_sec']),quantiles([num(b[k][metric])-num(a[k][metric]) for k in both]),'conditional paired delay quantiles');checks+=1
    retained=[]
    for out in tables['RETAINED_ROW_EXPOSURE.csv']:
        rs=[r for r in data['retained'] if (r['profile_id'],r['stream'])==(out['profile_id'],out['stream'])]
        equal(out['retained_rows'],len(rs),'retained row count');equal(out['exposure_available_rows'],sum(r['exposure_available']=='True' for r in rs),'retained availability');equal(out['exposure_missing_rows'],sum(r['exposure_available']!='True' for r in rs),'retained missingness');checks+=3
        fields=('retained_row_sec','correct_name_row_sec','wrong_known_name_row_sec','unknown_name_row_sec','unidentifiable_reference_row_sec','empty_reference_assigned_name_row_sec')
        sums={k:sum(num(r[k]) or 0 for r in rs) for k in fields}
        for k,v in sums.items():equal(out[k],v,'retained '+k);checks+=1
        need(abs(sums['retained_row_sec']-sum(sums[k] for k in fields[1:5]))<1e-6,'Retained partition differs')
        retained.append(dict(profile_id=out['profile_id'],stream=out['stream'],rows=len(rs),**sums))
    return dict(checks=checks,fixed_rosters=fixed,observed_set_comparisons=stable,retained=retained,tables=tables)

def select_examples(data):
    examples=[]
    for pid in IDS['original_naming']:
        d=data['original_naming'];rows=[r for r in d['turns'] if r['profile_id']==pid and integer(r['wrong_known_name_samples'])>0]
        if not rows:continue
        r=sorted(rows,key=lambda r:(-integer(r['wrong_known_name_samples']),r['stream'],occurrence(r)))[0]
        examples.append(dict(scope='original_naming',selection='Maximum wrong-known source samples per candidate across both taps; deterministic route/source-key tie order',
            row=r,source_table=d['turn_binding'],source_row_1based=d['line_numbers'][(*route(r),*occurrence(r))],source_row_sha256=digest(r),
            score_binding_not_reopened=json.loads(d['coverage'][(*route(r),r['case_id'])]['result'])))
    d=data['common_duration']
    for left,right in (('C141','C143'),('C144','C146')):
        for tap in ('O0','O1'):
            a={occurrence(r):r for r in d['groups'][left,tap,tap]};b={occurrence(r):r for r in d['groups'][right,tap,tap]}
            chosen=sorted(a,key=lambda k:(-(integer(b[k]['wrong_known_name_samples'])-integer(a[k]['wrong_known_name_samples'])),k))[0]
            delta=integer(b[chosen]['wrong_known_name_samples'])-integer(a[chosen]['wrong_known_name_samples'])
            if delta<=0:continue
            examples.append(dict(scope='common_duration',selection='Maximum positive 30s-minus-5s wrong-known source-sample delta per rotation/tap; deterministic source-key tie',
                left_profile=left,right_profile=right,stream=tap,wrong_known_delta=delta,left=a[chosen],right=b[chosen],source_table=d['turn_binding'],
                left_source_row_1based=d['line_numbers'][(*route(a[chosen]),*chosen)],right_source_row_1based=d['line_numbers'][(*route(b[chosen]),*chosen)],
                left_row_sha256=digest(a[chosen]),right_row_sha256=digest(b[chosen]),
                score_bindings_not_reopened=[json.loads(d['coverage'][(*route(x),x['case_id'])]['result']) for x in (a[chosen],b[chosen])]))
    return examples

def review_interpretation(common,summaries,text):
    lookup={(r['profile_id'],r['stream']):r for r in summaries if r['scope']=='common_duration'};checks=0
    for line in text.splitlines():
        if not line.startswith('| C14'):continue
        cols=[v.strip() for v in line.split('|')[1:-1]];pid=cols[0].split()[0]
        for column,metric,withheld in ((1,'correct_name_samples',False),(2,'wrong_known_name_samples',False),(3,'wrong_known_name_samples',True)):
            values=[int(v.strip().replace(',','')) for v in cols[column].split('/')];need(len(values)==2,'Interpretation paired tap table shape')
            for tap,v in zip(('O0','O1'),values):
                row=lookup[pid,tap];actual=row['roster_partition']['WITHHELD_OR_UNSELECTED'][metric] if withheld else row[metric]
                need(v==actual,'Interpretation numeric table differs');checks+=1
    need(checks==36,'All six interpretation table rows checked')
    expected={('A','O0'):([54,57,59],[16,16,16]),('A','O1'):([58,58,59],[18,18,18]),('B','O0'):([63,63,63],[21,21,21]),('B','O1'):([56,56,57],[26,26,26])}
    for row in common['observed_set_comparisons']:
        index=0 if row['metric']=='first_confirmed_correct_name' else 1
        need(row['counts']==expected[row['rotation'],row['stream']][index],'Interpretation observed counts differ');checks+=1
        if index:need(row['same_observed_set_across_tiers'],'Stable sets claimed unchanged actually differ');checks+=1
    for row in common['tables']['PAIRED_NAME_DELAY_RESULTS.csv']:
        if row['metric'] in ('first_confirmed_correct_name_wait_sec','first_stable_correct_name_wait_sec'):
            q=json.loads(row['conditional_right_minus_left_wait_sec'])
            if q['observed']:need(q['p50']==0,'Claimed zero conditional wait median differs');checks+=1
    person=[]
    for left,right,tap,wanted in (('C141','C142','O0',(9,1,4)),('C141','C143','O0',(10,1,3)),('C142','C143','O1',(5,1,8)),('C145','C146','O1',(8,2,4))):
        rows=[r for r in common['tables']['WITHIN_PERSON_TIER_DELTA.csv'] if (r['left_profile'],r['right_profile'],r['stream'],r['roster_status'])==(left,right,tap,'ENROLLED')]
        vals=[num(r['right_minus_left_correct_name_samples']) for r in rows];counts=(sum(v>0 for v in vals),sum(v<0 for v in vals),sum(v==0 for v in vals))
        need(len(rows)==14 and counts==wanted,'Interpretation per-person nonuniformity counts differ');checks+=1
        person.append(dict(left=left,right=right,stream=tap,correct_sample_person_increases_decreases_ties=counts))
    for side,left,right,correct,wrong in (('A','C141','C143',(372359,284065),(27284,77772)),('B','C144','C146',(299408,296731),(17655,4800))):
        for n,tap in enumerate(('O0','O1')):
            a,b=lookup[left,tap],lookup[right,tap]
            need(b['correct_name_samples']-a['correct_name_samples']==correct[n] and b['wrong_known_name_samples']-a['wrong_known_name_samples']==wrong[n],'Interpretation correct/false-known tradeoff delta differs');checks+=1
    return dict(status='PASS_NUMERICAL_TABLE_AND_SPECIFIC_PROSE_CLAIMS',checks=checks,person_nonuniformity=person,
        scope='Six displayed sample-count rows, confirmed/stable counts and stable-set equality, all reported conditional median wait claims, four person-count examples and5-to30 pooled tradeoff deltas verified. Remaining prose is reviewed for population/domain/causality meaning; no new source-domain inference.')

def main():
    need(not OUT.exists(),'New review namespace required');OUT.mkdir(parents=True)
    authorities=[dict(scope=label,receipt=dict(path=str(REPORT/folder/'NAME_ANALYSIS_RECEIPT.json'),sha256=sha)) for label,folder,sha in AUTHORITIES]
    plan=save(OUT/'PLAN.json',dict(status='REGISTERED_COMPACT_TABLE_REVIEW',sources=authorities,
        duration=dict(path=str(REPORT/'full_common_duration_results_v2/DURATION_RESULTS_RECEIPT.json'),sha256=DURATION_SHA),
        example_selection='At most10: largest wrong-known sample turn per original six candidate across both taps; largest positive 30s-minus-5s wrong-known turn delta per common rotation/tap. Tie route then canonical occurrence key. Selection is adverse and unrepresentative; no new prediction inspection.',
        scope='Exact completed compact scorer CSVs and scorer-only Q/roster/bank metadata. No event, vector, audio, score payload or model reads; two scientific condition groups remain distinct.',
        source=bind(__file__),readme=bind(Path(__file__).with_name('README_S6C_FULL_NAMES_REVIEW_V1.md'))))
    reader=Reader();data={};checks=0
    for authority in authorities:
        receipt=reader.json(authority['receipt']);need(receipt['status']=='COMPLETE_REQUESTED_NAME_INDEX' and receipt['requested']==receipt['scored']==2880 and receipt['failed_or_missing']==0 and receipt['source_occurrence_outputs']==9324,'Completed full naming source required')
        data[authority['scope']]=groups_and_rosters(reader,authority['scope'],receipt);checks+=data[authority['scope']]['checks']
    duration=reader.json(dict(path=str(REPORT/'full_common_duration_results_v2/DURATION_RESULTS_RECEIPT.json'),sha256=DURATION_SHA))
    need(duration['status']=='COMPLETE_SOURCE_BOUND_DESCRIPTIVE_COMPARISON' and duration['names']['sha256']==AUTHORITIES[1][2],'Exact common duration/name authority')
    common=compare_common(reader,duration,data['common_duration']);checks+=common['checks']
    ib=bind(REPORT/'full_common_duration_results_v2/INTERPRETATION_BINDING_V1.json');interpretation=reader.json(ib)
    need(interpretation['source_receipt']['sha256']==DURATION_SHA,'Interpretation source receipt differs');text=reader.raw(interpretation['document']).decode()
    need(interpretation['document']['sha256']=='25def9c706811c0b3cfade5a7b24706ed63e9604faa4f759368db7ea2434ff76','Held interpretation bytes differ')
    for b in interpretation['source_tables']:reader.raw(b)
    examples=select_examples(data);summaries=[row for v in data.values() for row in v['summary']]
    interpretation_review=review_interpretation(common,summaries,text);checks+=interpretation_review['checks']
    observed=save(OUT/'OBSERVED_NAME_SETS.json',dict(rows=[row for v in data.values() for row in v['observed_sets']],scope='Full observed confirmed/stable occurrence sets; censored sets have exact counts and hashes and remain reconstructible from the bound full TURNS tables.'))
    exb=save(OUT/'COUNTEREXAMPLES.json',dict(rows=examples,selection_scope='Adverse deterministic examples, not typical performance. True metadata source and wrong-known samples are visible; assigned false-name identities require separate prediction/event analysis and are not inferred.'))
    result=dict(status='PASS_COMPLETED_FULL_NAMING_TABLE_NUMERICAL_REVIEW',plan=plan,compared_fields=checks,condition_groups=2,prediction_outputs_per_group=2880,
        source_occurrence_rows_per_group=9324,source_occurrences_per_route=777,complete_reference_turns_per_route=693,incomplete_known_source_turns_per_route=84,
        route_summaries=summaries,fixed_common_rosters=common['fixed_rosters'],common_observed_set_comparisons=common['observed_set_comparisons'],common_retained_row_exposure=common['retained'],
        observed_sets=observed,counterexamples=exb,all_read_bindings=list(reader.bindings.values()),interpretation_binding=ib,interpretation_review=interpretation_review,
        scope='Independent arithmetic/source-key/roster/observed-set review of completed tables only; frozen scorer/sample integration trusted transitively. No model, raw log, embedding, prediction rescoring or expanded metric population.',
        caveats=['All777 known source occurrences include84 from incomplete-reference scenes; live name coverage is not the203-scene cpWER population.',
            'Observed delays condition on available names; censored turns are not zero waits. Stable attainment is onset plus0.5s, not retrospective onset.',
            'The common roster is14 available identities (9 CMU ARCTIC/5 HiFiTTS) at each tier per rotation. Original variable-availability rosters remain separate.',
            'Longer enrollment changes selected source material/templates alongside duration; no independent duration-only physical effect or holdout claim.',
            'Live speech-sample exposure and retained transcript row-seconds use different denominators and cannot replace each other.'],
        no_model_calls=True,no_prediction_or_native_event_reads=True,
        prior_audit_attempt=dict(status='GUARD_FAILURE_NO_FINAL_REVIEW',reason='Initial reviewer guard required full-reference status for all777 turns. Actual84 known-target turns correctly carry LIMITED_KNOWN_TARGET_SUPPORT; the repaired guard checks status against canonical reference completeness.',
            preserved_sources=[bind(SIM/'staging/s6c/20260910T123540Z/full_names_review/before_known_target_status_guard_v1'/n) for n in ('s6c_full_names_review_v1.py','README_S6C_FULL_NAMES_REVIEW_V1.md','PLAN.json')],
            original_plan=bind(REPORT/'full_naming_component_review_v1/PLAN.json')))
    resultb=save(OUT/'RESULT.json',result)
    lines=['# Independent full naming and duration review','',f'PASS: {checks:,} table fields/checks across two separate2,880-output groups. Each of24 routes retains777 source occurrences, including693 from complete-reference scenes and84 known-source turns from incomplete-reference scenes.','',
        '| Scope | Candidate/tap | Correct samples | Wrong-known samples | Unknown samples | Confirmed observed | Stable observed |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in summaries:lines.append(f"| {r['scope']} | {r['profile_id']} {r['stream']} | {r['correct_name_samples']:,} | {r['wrong_known_name_samples']:,} | {r['unknown_name_samples']:,} | {r['waits']['first_confirmed_correct_name']['observed']} | {r['waits']['first_stable_correct_name']['observed']} |")
    lines+=['','Common-roster identity membership, per-turn support, observed/censored partitions, pooled/person/corpus sample changes, conditional wait statistics and retained-row exposure reconcile with the exact source tables. Every route partitions28,612,432 live source-support samples into correct, wrong-known and Unknown.','',
        'The common roster contains the same14 people within each rotation at5/15/30 seconds:9 CMU ARCTIC and5 HiFiTTS; no Common Voice enrollment-duration effect is established. The original naming conditions retain their own available/intended-but-unavailable/withheld partitions.','',
        'The bound counterexamples deliberately select maxima. They illustrate wrong-known exposure or adverse longer-tier changes; they are not average performance or proof of a causal acoustic mechanism. Full keys, table-row locations and source score bindings are preserved without reopening score/prediction payloads.','',
        'Stable observed sets and censoring remain explicit. An unchanged conditional median among both-observed turns does not establish timely names on censored turns. Live support-sample exposure differs from retained-row modeled seconds.','',
        f'Result binding: {resultb["sha256"]}. Original common-duration interpretation is retained unchanged and is reviewed against the reconciled numerical tables; no new uncertainty interval or winner is declared.','']
    md=OUT/'REVIEW.md'
    with md.open('x',encoding='utf-8') as f:f.write('\n'.join(lines))
    print(json.dumps(dict(result=resultb,readme=bind(md),counterexamples=len(examples),compared_fields=checks)))

if __name__=='__main__':main()
