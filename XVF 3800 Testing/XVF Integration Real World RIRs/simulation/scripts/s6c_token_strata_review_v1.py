"""Bounded compact token/strata result review. See README_S6C_TOKEN_STRATA_REVIEW_V1.md."""
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction
import csv,io,json,hashlib,math,datetime
SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
OUT=REPORT/'independent_review/token_strata_design_v1'
POPS={'PRIMARY_NONOVERLAP':156,'COMPLETE_OVERLAP':47,'INCOMPLETE_REFERENCE':26,'STRICT_EMPTY_REFERENCE':11}
COMPLETE={'PRIMARY_NONOVERLAP','COMPLETE_OVERLAP'}
reads=[];checks=Counter()
def ck(ok,kind):
    if not ok: raise AssertionError(kind)
    checks[kind]+=1
def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def binding(p,raw):
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def read(p,b=None):
    p=Path(p);raw=p.read_bytes();found=binding(p,raw)
    if b: ck(found['bytes']==b['bytes'] and found['sha256']==b['sha256'],'exact_buffer_binding')
    reads.append(found);return raw
def doc(p,b=None):return json.loads(read(p,b))
def result(relative,sha):
    p=REPORT/relative
    raw=read(p);ck(hashlib.sha256(raw).hexdigest()==sha,'held_result_hash')
    v=json.loads(raw); arts={}
    for b in v['artifacts']:
        p=Path(b['path']);arts[p.name]=read(p,b)
    return v,arts
def route(x,stream='asr_tap'):return x['profile_id'],x[stream],x['identity_tap']
def num(x):return None if x in ('',None) else int(x)
def frac(x):return None if x in ('',None) else Fraction(x)
def near(a,b):return a==b if a is None or b is None else math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-12)
def run():
    ck(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'no_active_quiet_lease')
    ck(not OUT.exists(),'fresh_review_namespace')
    t,ta=result('full_token_boundaries_v1/results_v1/RESULT.json','6215372f68e75ac3e919c2a90284b33158fc5f4f33e9dcb1b20caafd0a3e39ca')
    plan=doc(t['plan']['path'],t['plan'])
    read(t['helper']['path'],t['helper'])
    cells=json.loads(ta['CELLS.json']);aggs=json.loads(ta['ROUTE_POPULATIONS.json']);pairs=json.loads(ta['PAIRED_SCENES.json'])
    ck((len(cells),len(aggs),len(pairs))==(4320,72,3840),'token_output_grid')
    expected={(x,'O0','O0') for x in ['B00','B01','B36','C065','C067','C072','C074','C076']}|{(x,'O1','O1') for x in ['B00','B01','B36','C065','C067','C072','C074','C076']}|{('C085','O0','O1'),('C086','O1','O0')}
    by={};groups=defaultdict(list);rt=defaultdict(list)
    for c in cells:
        k=(*route(c),c['case_id']);ck(k not in by,'unique_token_cell');by[k]=c
        groups[(*route(c),c['population'])].append(c);rt[route(c)].append(c)
        a=c['token_alignment'];p=c['population']
        ck((a is None)==(p=='INCOMPLETE_REFERENCE'),'token_incomplete_null')
        if a is not None:
            ck(a['errors']==a['substitutions']+a['deletions']+a['insertions'],'token_edit_partition')
            ck(a['reference_words']==c['available_reference_words'] and a['hypothesis_words']==c['hypothesis_words'],'token_word_denominators')
            ck(a['hypothesis_words']==a['reference_words']-a['deletions']+a['insertions'],'token_length_reconciliation')
            for f,n in [('deleted_reference_positions','deletions'),('substituted_reference_positions','substitutions'),('insertion_hypothesis_positions','insertions')]:
                ck(len(a[f])==a[n] and len(set(a[f]))==a[n],'token_operation_positions')
            ck(len(a['insertion_reference_boundaries'])==a['insertions'],'token_insertion_boundaries')
            for side in ('first','last'):
                value=c[side+'_reference_token_deleted']
                ck(value==(a[side+'_reference_token_operation']=='deletion') if a['reference_words'] else value is None,'token_boundary_status')
    ck(set(rt)==expected,'token_declared_routes')
    for r,cc in rt.items():
        ck(Counter(c['population'] for c in cc)==POPS,'token_route_populations')
        ck({c['case_id'] for c in cc}==set(plan['case_ids']),'token_route_all240')
    for a in aggs:
        g=groups[(*route(a),a['population'])];scored=[c for c in g if c['token_alignment'] is not None];eligible=[c for c in scored if c['available_reference_words']]
        calc={'requested_scenes':len(g),'alignment_available_scenes':len(scored),'alignment_unavailable_scenes':len(g)-len(scored),'boundary_eligible_scenes':len(eligible),'hypothesis_words_all_scenes':sum(c['hypothesis_words'] for c in g)}
        for f in ('reference_words','errors','substitutions','deletions','insertions'):
            calc[f]=sum(c['token_alignment'][f] for c in scored) if scored else None
        for side in ('first','last'):
            calc[side+'_token_deletion_scenes']=sum(c[side+'_reference_token_deleted'] for c in eligible) if eligible else None
            calc[side+'_token_operation_counts']=dict(Counter(c['token_alignment'][side+'_reference_token_operation'] for c in eligible))
        for k,v in calc.items():ck(a[k]==v,'token_aggregate_field')
    pairset={(tuple(p['left']),tuple(p['right'])) for p in plan['pairs']}
    seen=set()
    for p in pairs:
        l,r=tuple(p['left']),tuple(p['right']);cid=p['case_id'];pk=(l,r,cid)
        ck((l,r) in pairset and pk not in seen,'token_pair_grid');seen.add(pk)
        a,b=by[(*l,cid)],by[(*r,cid)];aa,bb=a['token_alignment'],b['token_alignment']
        ck(p['population']==a['population']==b['population'],'token_pair_population')
        ck(a['available_reference_words']==b['available_reference_words'] and a['duration_sec']==b['duration_sec'],'token_pair_support')
        ck(p['normalized_final_text_changed']==(a['normalized_final_text_sha256']!=b['normalized_final_text_sha256']),'token_pair_text')
        ck(p['alignment_available']==(aa is not None and bb is not None),'token_pair_availability')
        delta=None if aa is None or bb is None else {k:bb[k]-aa[k] for k in ('errors','substitutions','deletions','insertions','hypothesis_words')}
        ck(p['right_minus_left']==delta,'token_pair_delta')
        for side in ('first','last'):
            field=side+'_reference_token_operation'
            ck(p[field]==({'left':aa[field],'right':bb[field]} if aa is not None and bb is not None else None),'token_pair_boundary')
    ck(len(seen)==len(pairset)*240==3840,'token_complete_pairs')
    s,sa=result('strata_adverse_v1/actual_v1/RESULT.json','446e3598bf9d267cae1ea739277994b579c83e40a9c017d253612152c255fcff')
    spec=doc(s['spec']['path'],s['spec'])
    for b in s['sources']:read(b['path'],b)
    originals=json.loads(sa['ORIGINAL_STRATA_AND_MEMBERSHIPS.json'])['records']
    harms=json.loads(sa['DESCRIPTIVE_HARM_EXAMPLES.json'])['examples'];rows=list(csv.DictReader(io.StringIO(sa['PAIRED_STRATA_METRICS.csv'].decode('utf-8-sig'))))
    ck((len(originals),len(rows),len(harms))==(2912,18720,1440),'strata_output_grid')
    omap={};members=defaultdict(set)
    for o in originals:
        k=(*route(o,'stream'),o['dimension'],o['value'],o['population']);ck(k not in omap,'unique_original_stratum');omap[k]=o
        ids=o['member_case_ids'];ck(ids==sorted(set(ids)),'stratum_member_uniqueness')
        ck(len(ids)==int(o['original_aggregate_cells']['scenes'])==len(o['member_scene_rows'])==len(o['member_scene_cell_hashes']),'stratum_member_counts')
        for cid in ids:members[(route(o,'stream'),o['population'])].add(cid)
    expected_routes={route(x,'stream') for x in spec['routes']}
    ck({k[:3] for k in omap}==expected_routes and len(expected_routes)==28,'strata_declared_routes')
    for r in expected_routes:
        for p,n in POPS.items():ck(len(members[(r,p)])==n,'strata_route_population_union')
    comparisons={c['contrast_id']:c for c in spec['contrasts']};parsed=[];seen=set()
    for p in rows:
        cid,met,pop=p['contrast_id'],p['metric'],p['population'];decl=comparisons[cid]
        key=(cid,p['dimension'],p['value'],pop,met);ck(key not in seen,'unique_paired_stratum_metric');seen.add(key)
        obj={k:p[k] for k in ('contrast_id','dimension','value','population','left_original_row_sha256','right_original_row_sha256','metric')}
        views=[]
        for side in ('left','right'):
            r=json.loads(p[side+'_route']);ck(r==decl[side],'paired_declared_route')
            obj[side+'_route']=r
            o=omap[(*r,p['dimension'],p['value'],pop)];a=o['original_aggregate_cells']
            ck(hashlib.sha256(canonical(o)).hexdigest()==p[side+'_original_row_sha256'],'paired_original_row_hash')
            v={}
            for f in ('numerator','eligible_scenes','missing_or_ineligible_scenes'):v[f]=num(p[side+'_'+f])
            for f in ('membership_case_ids','eligible_case_ids','tiny_support_flags'):v[f]=json.loads(p[side+'_'+f])
            for f in ('denominator_exact','denominator_unit','rate_exact','rate_unit','unavailable_reason'):v[f]=p[side+'_'+f] or None
            v['rate']=float(p[side+'_rate']) if p[side+'_rate'] else None
            v['denominator']=float(p[side+'_denominator']) if v['denominator_unit']=='source_seconds' and p[side+'_denominator'] else num(p[side+'_denominator'])
            ck(v['membership_case_ids']==o['member_case_ids'],'paired_original_memberships')
            ck(set(v['eligible_case_ids'])<=set(v['membership_case_ids']) and v['eligible_scenes']==len(v['eligible_case_ids']) and v['missing_or_ineligible_scenes']==len(o['member_case_ids'])-v['eligible_scenes'],'paired_eligible_memberships')
            if met in ('word','cp_first_display_label_final_words','cp_latest_revised'):
                n,d=(num(a[met+'_errors']),num(a[met+'_reference_words'])) if pop in COMPLETE else (None,None)
            elif met=='unknown_support':n,d=num(a['unknown_samples']),num(a['sole_active_samples'])
            elif met=='inconsistent_returns':n,d=num(a['return_inconsistent']),sum(num(a[k]) for k in ('return_consistent','return_inconsistent','return_unknown'))
            else:n,d=(num(a['empty_insertions']),Fraction(a['duration_sec'])) if pop=='STRICT_EMPTY_REFERENCE' else (None,None)
            ck(v['numerator']==n and frac(v['denominator_exact'])==(None if d is None else Fraction(d)),'paired_aggregate_numerator_denominator')
            expected_rate=Fraction(n)/Fraction(d)*(60 if met=='empty_insertions' else 1) if n is not None and d is not None and d>0 else None
            ck(frac(v['rate_exact'])==expected_rate and near(v['rate'],expected_rate),'paired_metric_rate')
            tiny=[]
            if v['eligible_scenes']<5:tiny.append('fewer_than_5_eligible_scenes')
            threshold={'reference_words':20,'sole_active_samples':16000,'classified_return_turns':5,'source_seconds':60}[v['denominator_unit']]
            if d is not None and d<threshold:tiny.append('small_'+v['denominator_unit'])
            ck(v['tiny_support_flags']==tiny,'paired_tiny_flags')
            views.append(v);obj[side]=v
        l,r=views;match=l['eligible_case_ids']==r['eligible_case_ids'];ld,rd=frac(l['rate_exact']),frac(r['rate_exact'])
        delta=rd-ld if match and ld is not None and rd is not None else None
        count=r['numerator']-l['numerator'] if match and l['numerator'] is not None and r['numerator'] is not None else None
        ck((p['eligible_cases_equal']=='True')==match and frac(p['rate_delta_exact'])==delta and num(p['right_minus_left_count'])==count,'paired_difference')
        ck(near(float(p['right_minus_left_rate']) if p['right_minus_left_rate'] else None,delta),'paired_float_delta')
        obj.update(eligible_cases_equal=match,right_minus_left_count=count,right_minus_left_rate=float(p['right_minus_left_rate']) if p['right_minus_left_rate'] else None,rate_delta_exact=p['rate_delta_exact'] or None,rate_delta_unavailable_reason=p['rate_delta_unavailable_reason'] or None)
        parsed.append(obj)
    grouped=defaultdict(list)
    for p in parsed:grouped[(p['contrast_id'],p['metric'],p['population'])].append(p)
    counts=Counter()
    for h in harms:
        group=grouped[(h['contrast_id'],h['metric'],h['population'])];field='rate_delta_exact' if h['basis']=='rate' else 'right_minus_left_count'
        pos=[p for p in group if p[field] is not None and Fraction(p[field])>0]
        ck((h['status']=='NO_POSITIVE_HARM')==(not pos),'positive_maximum_status')
        if not pos:ck(h['example'] is None,'no_positive_example');continue
        maximum=max(Fraction(p[field]) for p in pos);ties=sorted([p for p in pos if Fraction(p[field])==maximum],key=lambda p:(p['dimension'],p['value']))
        ck(frac(h['exact_delta'])==maximum and h['example']==ties[0],'positive_maximum_value_and_example')
        expected_ties=[dict(dimension=p['dimension'],value=p['value'],pair_row_sha256=hashlib.sha256(canonical(p)).hexdigest()) for p in ties]
        ck(h['all_tied_groups']==expected_ties,'positive_maximum_all_ties')
        counts[(h['contrast_id'],h['basis'])]+=1
    narrative=sa['NARRATIVE.md'].decode('utf-8')
    for cid in comparisons:
        ck(f"| {cid} | {counts[(cid,'rate')]} | {counts[(cid,'count')]} |" in narrative,'narrative_maximum_counts')
    token_summary=[{k:a[k] for k in ('profile_id','asr_tap','identity_tap','population','requested_scenes','reference_words','errors','first_token_deletion_scenes','last_token_deletion_scenes')} for a in aggs]
    conclusions=[
      'Token: 18 exact routes, 4320 unique cells, 72 population aggregates and 3840 matched rows reconcile from compact cells. Each route retains 156 primary, 47 complete-overlap, 26 incomplete and 11 empty scenes.',
      'Token boundary eligibility is primary156 or overlap47; incomplete has null full-reference alignment and empty has no boundary token. Complete-overlap serialized diagnostic edits are not the core MIMO word score. A positional deletion is not phonetic clipping or reset evidence.',
      'Strata: 28 declared routes, 2912 selected original strata and 18720 paired metric rows reconcile against retained aggregate/membership records. All rational rates, own denominators, direction, tiny flags and 1440 maxima/status rows including ties reproduce.',
      'The narrative count table is exact. Its selected adverse examples retain original populations and small-support flags. Maxima across overlapping strata are descriptive examples, not independent failures, tests, a ranking or final selection.',
      'B36 comparisons concern the complete historical pipeline. C085 has only O0-ASR/O1-identity and C086 only O1-ASR/O0-identity. C088/C091 strata are anonymous core outcomes, not known-name correctness.',
      'Review did not reread original score tables, references, predictions, logs, audio or models, did not rerun token alignment, scoring, policy, scanner or source fixtures. Per-scene eligible-set membership and original score-table admission remain inherited from held reviewed helpers; this review checks the exact exported compact representation.'
    ]
    OUT.mkdir(parents=True)
    md=OUT/'REVIEW.md';md.write_text('# Compact token and strata review\n\n'+'\n\n'.join(conclusions)+'\n',encoding='utf-8')
    receipt={'schema':'s6c-token-strata-design-review.v1','status':'PASS_COMPACT_NUMERICAL_AND_SCOPE_REVIEW','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':dict(checks),'check_count':sum(checks.values()),'exact_buffers':reads,'reviewer_source':binding(Path(__file__),Path(__file__).read_bytes()),'reviewer_readme':binding(Path(__file__).with_name('README_S6C_TOKEN_STRATA_REVIEW_V1.md'),Path(__file__).with_name('README_S6C_TOKEN_STRATA_REVIEW_V1.md').read_bytes()),'conclusions':conclusions,'token_population_summary':token_summary,'narrative':binding(md,md.read_bytes()),'models':0,'policy_replays':0,'original_score_table_reads':0,'native_log_reads':0,'storage_scans':0}
    p=OUT/'REVIEW_RECEIPT.json';p.write_text(json.dumps(receipt,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(binding(p,p.read_bytes())));print('PASS',sum(checks.values()))
if __name__=='__main__':run()

