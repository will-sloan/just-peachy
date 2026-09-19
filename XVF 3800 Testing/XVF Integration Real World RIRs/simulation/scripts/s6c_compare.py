"""Compare explicitly selected completed scores; see README_S6C_COMPARE.md."""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from copy import deepcopy
import csv
import io
import json
import os
from pathlib import Path
import time
from importlib.metadata import version
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_name]='1'
import s6c_analysis_v2 as core

REPORT=core.REPORT
SCHEMA='jp_s6c_completed_score_comparison.v1'
ALLOWED_SCHEMAS={'jp_s6c_core_analysis.v1','jp_s6c_core_analysis.v2'}


def source_bindings():
    names=['s6c_compare.py','README_S6C_COMPARE.md',*core.CODES]
    return [core.bind(Path(__file__).with_name(n)) for n in dict.fromkeys(names)]


def score_key(row):
    return (*core.route_key(row),row['case_id'])


def scientific_payload(score):
    # Exclude only per-analysis provenance/schema. Predictor costs, source
    # bindings, lifecycle, words and every metric remain in exact comparison.
    return {k:v for k,v in score.items() if k not in ('analysis_identity','analysis_key','schema')}


def add_score(selected,key,score,provenance):
    digest=core.digest(scientific_payload(score))
    if key in selected:
        if selected[key]['scientific_digest']!=digest:
            raise ValueError('Conflicting selected duplicate; explicitly choose one source in the input spec: '+str(key))
        selected[key]['provenance'].append(provenance)
    else:selected[key]=dict(score=score,scientific_digest=digest,provenance=[provenance])


def ensure_routes(keys):
    by={}
    for candidate,asr,identity,case in keys:
        prior=by.setdefault((candidate,asr),identity)
        if prior!=identity:raise ValueError('Selected candidate/ASR has more than one identity tap')
    return by


def formula_equivalence():
    old=ast.parse(Path(core.__file__).with_name('s6c_analysis.py').read_text(encoding='utf-8'))
    new=ast.parse(Path(core.__file__).read_text(encoding='utf-8'))
    names=('route_key','expected_grid','numeric','lifecycle_metrics','analyze','tables')
    def functions(tree):return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
    a,b=functions(old),functions(new)
    if any(a[n]!=b[n] for n in names):raise ValueError('V1/V2 scientific adapter functions differ; separate reviewed comparison version required')
    return dict(status='EXACT_FUNCTION_AST_PARITY',functions=list(names),
        scope='V1/V2 registry, schema and payload-digest admission differ; scientific adapters and bound inherited metric code are identical.')


def verify_raw(binding):
    p=Path(binding['path']);raw=p.read_bytes()
    import hashlib
    if hashlib.sha256(raw).hexdigest()!=binding['sha256'] or len(raw)!=binding['bytes']:
        raise ValueError('Changed declared bytes: '+str(p))
    return raw


def unique_table(receipt,name):
    matches=[b for b in receipt['tables'] if Path(b['path']).name==name]
    if len(matches)!=1:raise ValueError('Exactly one bound table required: '+name)
    return matches[0]


def validate_receipt(receipt,bank_binding,input_binding,current_codes,current_packages):
    if receipt.get('schema') not in ALLOWED_SCHEMAS or receipt.get('status')!='COMPLETE_REQUESTED_INDEX':
        raise ValueError('Only completed admitted V1/V2 core receipts are supported')
    if receipt['unscored']!=0 or receipt['requested']!=receipt['scored'] or receipt['tests']['status']!='PASS':
        raise ValueError('Incomplete/failed core analysis cannot become successful comparison')
    if receipt['bank']!=bank_binding or receipt['input_index']!=input_binding:raise ValueError('Core population/support authority differs')
    if receipt['packages']!=current_packages:raise ValueError('Analysis package versions differ')
    wanted=set(core.CODES)
    if receipt['schema'].endswith('.v1'):wanted.remove('s6c_analysis_v2.py')
    actual={Path(b['path']).name:b for b in receipt['codes']}
    if len(actual)!=len(receipt['codes']) or set(actual)!=wanted:raise ValueError('Unexpected scientific code set')
    for name,binding in actual.items():
        if binding!=current_codes[name]:raise ValueError('Scientific code binding differs: '+name)
        verify_raw(binding)
    # Preserve and verify the older registry scope as well as the new combined
    # registry used to generate the current comparisons.
    core.verified(receipt['registry'])
    for binding in receipt.get('registry_sources',[]):core.verified(binding)


def collect(spec,bank_binding,input_binding,bank,inputs,current_codes,current_packages):
    if spec.get('schema')!='jp_s6c_compare_inputs.v1' or set(spec)-{'schema','sources','historical_sources'} or 'sources' not in spec or not (spec['sources'] or spec.get('historical_sources')):
        raise ValueError('Explicit comparison source specification required')
    selected={};sources=[];seen_receipts=set();all_candidates=set()
    inputrows={(r['case_id'],r['stream']):r for r in inputs['rows']}
    allowed=frozenset(s['case_id'] for s in bank['scenes'])
    registry,_=core.registered_candidates();registered={r['candidate_id'] for r in registry}
    for request in spec['sources']:
        if set(request)!={'receipt','candidate_ids'}:raise ValueError('Each source requires only receipt binding and candidate_ids')
        rb=request['receipt'];resolved=str(Path(rb['path']).resolve())
        if resolved in seen_receipts:raise ValueError('List each receipt once with its explicit candidate subset')
        seen_receipts.add(resolved)
        ids=request['candidate_ids']
        if not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)) or not set(ids)<=registered:
            raise ValueError('Nonempty unique registered candidate subset required')
        receipt=core.verified(rb)
        validate_receipt(receipt,bank_binding,input_binding,current_codes,current_packages)
        index=core.verified(receipt['index']);expected=core.expected_grid(index,allowed)
        if index.get('status')!='COMPLETE' or len(index['rows'])!=len(expected):raise ValueError('Bound source index is not complete')
        lookup={score_key(r):r for r in index['rows']}
        if set(lookup)!=expected or receipt['scored']!=len(expected):raise ValueError('Receipt/index coverage count differs')
        if receipt['case_ids']!=index['case_ids'] or receipt['profile_routes']!=index['profile_routes']:raise ValueError('Receipt/index grid declarations differ')
        coverage_binding=unique_table(receipt,'COVERAGE.csv')
        coverage=list(csv.DictReader(io.StringIO(verify_raw(coverage_binding).decode('utf-8-sig'))))
        coverage_keys=[score_key(row) for row in coverage]
        if len(coverage_keys)!=len(set(coverage_keys)) or set(coverage_keys)!=expected or any(r['status']!='SCORED' for r in coverage):
            raise ValueError('Bound coverage is not the exact successful source grid')
        if not set(ids)<={k[0] for k in expected}:raise ValueError('Selected candidate absent from its declared receipt')
        kept=0
        for row in coverage:
            key=score_key(row)
            if key[0] not in ids:continue
            score_binding=json.loads(row['result']);score=core.verified(score_binding)
            if score_key(score)!=key or score['schema']!=receipt['schema']:raise ValueError('Selected score route/schema differs')
            identity=score['analysis_identity'];pid,asr,itap,case=key
            wanted=dict(prediction=lookup[key]['result'],support=inputrows[case,itap]['support'],bank=bank_binding,
                codes=receipt['codes'],packages=receipt['packages'],metric_schema=receipt['schema'],asr_tap=asr,identity_tap=itap)
            if identity!=wanted or core.digest(identity)!=score['analysis_key']:raise ValueError('Selected score identity is not exact source analysis identity')
            if score['asr_lexical_tap']!=asr or score['evidence_mapping_tap']!=itap or score['route']!=asr+'_ASR_'+itap+'_ID':
                raise ValueError('Scientific score tap semantics differ')
            add_score(selected,key,score,dict(receipt=rb,coverage=coverage_binding,score=score_binding,prediction=identity['prediction'],support=identity['support']))
            kept+=1
        sources.append(dict(receipt=rb,coverage=coverage_binding,prediction_index=receipt['index'],candidate_ids=ids,
            selected_score_rows=kept,unselected_score_rows=len(coverage)-kept))
        all_candidates.update(ids)
    ensure_routes(selected)
    if {k[0] for k in selected}!=all_candidates:raise ValueError('Selected candidate has no scores')
    return selected,sources


def historical_scene(raw):
    """Parse only the metric scalars used by the inherited paired function."""
    row=dict(raw)
    for key,value in raw.items():
        numeric=key.startswith('word_') or key.startswith('cp_') and not key.endswith('_status')
        if numeric:
            if value=='':row[key]=None
            else:
                parsed=json.loads(value)
                if isinstance(parsed,bool) or not isinstance(parsed,(int,float)) or not core.numeric(parsed):
                    raise ValueError('Historical metric must be finite numeric or empty: '+key)
                row[key]=parsed
    row['identity_tap']=row['stream']
    row['route']=row['stream']+'_ASR_'+row['stream']+'_ID'
    row['source_analysis_schema']='jp_s6b_analysis_v1'
    row['adapter_scope']='Historical sealed same-tap scene metrics; native cost/timing fields retain their old scope. No v3 lifecycle or naming fields synthesized.'
    return row


def historical_collect(requests,bank,current_codes,current_packages):
    selected={};sources=[]
    if not requests:return selected,sources
    authority=core.bind(core.S6B/'LOCAL_ARTIFACT_INDEX.json','2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e')
    sealed=core.verified(authority)
    scenes={r['case_id']:r for r in bank['scenes']}
    registry,_=core.registered_candidates();known={r['candidate_id'] for r in registry}
    seen=set()
    for request in requests:
        if set(request)!={'receipt','candidate_ids','case_ids'}:raise ValueError('Historical source requires receipt, candidate_ids and explicit case_ids')
        rb=request['receipt'];matches=[r for r in sealed['artifacts'] if Path(r['path']).resolve()==Path(rb['path']).resolve()]
        if len(matches)!=1 or any(matches[0][k]!=rb[k] for k in ('path','bytes','sha256')):raise ValueError('Historical receipt must match sealed S6B authority')
        if rb['sha256']!='12ee9ccd91a2a924ba2f54b51f622c39c73ed15325073cac5439bad4298dda0f':raise ValueError('Only exact completed S6B full analysis is admitted')
        if rb['path'] in seen:raise ValueError('Select one explicit historical subset per receipt')
        seen.add(rb['path']);receipt=core.verified(rb)
        if receipt['schema']!='jp_s6b_analysis_v1' or receipt['status']!='COMPLETE_REQUESTED_INDEX' or receipt['requested']!=13920 or receipt['scored']!=13920 or receipt['unscored']!=0:
            raise ValueError('Historical analysis completion differs')
        if receipt['packages']!=current_packages:raise ValueError('Historical metric package versions differ')
        wanted=set(core.CODES)-{'s6c_analysis.py','s6c_analysis_v2.py'}
        actual={Path(b['path']).name:b for b in receipt['codes']}
        if len(actual)!=len(receipt['codes']) or set(actual)!=wanted:raise ValueError('Historical scientific code set differs')
        for name,binding in actual.items():
            if binding!=current_codes[name]:raise ValueError('Historical inherited metric code differs')
            verify_raw(binding)
        ids=request['candidate_ids'];cases=request['case_ids']
        if not ids or len(ids)!=len(set(ids)) or not set(ids)<=known or not cases or len(cases)!=len(set(cases)) or not set(cases)<=set(scenes):
            raise ValueError('Explicit unique registered historical candidates/cases required')
        index=core.verified(receipt['index'])
        if index['status']!='COMPLETE':raise ValueError('Historical prediction index incomplete')
        expected={(r.get('candidate_id',r.get('profile_id')),r['stream'],r['case_id']) for r in index['rows']}
        table=unique_table(receipt,'SCENE_RESULTS.csv');raw=verify_raw(table)
        table_rows=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        allkeys=set();kept=0
        for number,item in enumerate(table_rows,start=2):
            base=(item['profile_id'],item['stream'],item['case_id'])
            if base in allkeys:raise ValueError('Duplicate historical scene table row')
            allkeys.add(base)
            if item['profile_id'] not in ids or item['case_id'] not in cases:continue
            if item['family_id']!=scenes[item['case_id']]['family_id']:raise ValueError('Historical scene family identity differs')
            row=historical_scene(item);key=score_key(row)
            selected[key]=dict(scene=row,scientific_digest=core.digest(item),provenance=[dict(authority=authority,receipt=rb,scene_table=table,csv_line=number,raw_row_digest=core.digest(item))])
            kept+=1
        if allkeys!=expected or len(allkeys)!=13920:raise ValueError('Historical scene table does not match complete source index')
        wanted_keys={(pid,tap,tap,case) for pid in ids for tap in ('O0','O1') for case in cases}
        if set(selected)!=wanted_keys:raise ValueError('Historical selected subset is incomplete')
        sources.append(dict(authority=authority,receipt=rb,scene_table=table,prediction_index=receipt['index'],candidate_ids=ids,case_ids=cases,selected_rows=kept,
            scope='Original S6B table rows, exact code and sealed source authority. Same-tap identity adapter only; original resource/timing fields remain historical.'))
    return selected,sources


def fixtures():
    checks=[]
    def passes(name):checks.append(name)
    a=dict(profile_id='C',stream='O0',identity_tap='O1',case_id='x',word_errors=1,schema='v1',analysis_identity={'source':1},analysis_key='a')
    key=score_key(a);selected={};add_score(selected,key,a,{'source':1})
    b={**a,'schema':'v2','analysis_identity':{'source':2},'analysis_key':'b'}
    add_score(selected,key,b,{'source':2});assert len(selected)==1 and len(selected[key]['provenance'])==2;passes('exact scientific duplicate retains both provenances without pooling')
    try:add_score(selected,key,{**b,'word_errors':2},{})
    except ValueError:passes('conflicting metric duplicate rejected')
    else:raise AssertionError('Changed metrics pooled')
    try:add_score(selected,key,{**b,'recipe_costs':{'asr':2}}, {})
    except ValueError:passes('different cost/scientific payload duplicate rejected')
    else:raise AssertionError('Changed costs pooled')
    assert ensure_routes([key])=={('C','O0'):'O1'};passes('explicit split route retained')
    try:ensure_routes([key,('C','O0','O0','y')])
    except ValueError:passes('same candidate ASR cannot pool identity taps')
    else:raise AssertionError('Conflicting identity routes pooled')
    formula_equivalence();passes('scientific V1/V2 adapter AST parity')
    rows=[dict(profile_id=p,stream='O0',case_id='x',population='PRIMARY_NONOVERLAP',room='r',word_errors=e,
        word_reference_words=10,normalized_final_text=t) for p,e,t in (('P',1,'a'),('C',2,'b'))]
    pairs,_=core.inherited.paired_comparisons(rows,[dict(profile_id='C',parent='P')],{},bootstrap=False)
    pair=next(r for r in pairs if r['comparison']=='candidate_minus_parent' and r['population']=='PRIMARY_NONOVERLAP')
    assert pair['reference_words']==10 and pair['right_minus_left_pp']==10;passes('actual inherited paired denominator and right-minus-left sign')
    rows[1]['word_reference_words']=11
    try:core.inherited.paired_comparisons(rows,[dict(profile_id='C',parent='P')],{},bootstrap=False)
    except ValueError:passes('actual inherited unequal denominator rejected')
    else:raise AssertionError('Unequal denominators accepted')
    historical=historical_scene(dict(profile_id='B00',stream='O1',case_id='x',word_errors='2',word_reference_words='10',cp_first_final_errors='',normalized_final_text='null',policy_wall_sec='1.2'))
    assert historical['identity_tap']=='O1' and historical['word_errors']==2 and historical['cp_first_final_errors'] is None and historical['normalized_final_text']=='null' and historical['policy_wall_sec']=='1.2'
    passes('historical numeric metric parsing preserves words and old timing strings')
    try:historical_scene(dict(stream='O0',word_errors='NaN'))
    except ValueError:passes('historical nonfinite metric rejected')
    else:raise AssertionError('Nonfinite historical metric accepted')
    return dict(status='PASS',checks=checks)


def run(args):
    started=time.perf_counter();spec_path=args.spec if args.spec.is_absolute() else REPORT/args.spec
    spec_binding=core.bind(spec_path);spec=core.verified(spec_binding)
    output=REPORT/args.output_subdir
    if Path(args.output_subdir).is_absolute() or REPORT.resolve() not in output.resolve().parents or output.exists():
        raise ValueError('A fresh comparison child of the current report is required')
    current_sources=source_bindings();codes={Path(b['path']).name:b for b in current_sources}
    packages={n:version(n) for n in ('numpy','scipy','meeteval')}
    equivalence=formula_equivalence();tests=fixtures()
    bank_binding=core.bind(core.BANK,core.BANK_SHA);bank=core.verified(bank_binding)
    input_binding=core.bind(core.S6B/'INPUT_INDEX.json',core.INPUT_SHA);inputs=core.verified(input_binding)
    selected,sources=collect(spec,bank_binding,input_binding,bank,inputs,codes,packages)
    historical,historical_sources=historical_collect(spec.get('historical_sources',[]),bank,codes,packages)
    if set(selected)&set(historical):raise ValueError('Do not select the same scene key through full-score and historical-table adapters; choose one explicitly')
    routes=ensure_routes([*selected,*historical]);records=[v['score'] for k,v in sorted(selected.items())]
    scene_rows=[{**core.inherited.scene_row(r),**{k:r[k] for k in ('identity_tap','route','oracle_like')}} for r in records]
    scene_rows.extend(v['scene'] for k,v in sorted(historical.items()))
    registry,registry_bindings=core.registered_candidates();parents={r['candidate_id']:r.get('parent') for r in registry}
    dependency=core.dependency_plan({s['case_id']:s for s in bank['scenes']},bank['selected_sources'])
    comparisons,uncertainty=core.inherited.paired_comparisons(scene_rows,
        [dict(profile_id=r['candidate_id'],parent=r.get('parent')) for r in registry],dependency,bootstrap=not args.no_bootstrap)
    for row in [*comparisons,*uncertainty]:
        row['left_identity_tap']=routes.get((row['left_profile'],row['left_stream']))
        row['right_identity_tap']=routes.get((row['right_profile'],row['right_stream']))
    coverage=[dict(candidate_id=k[0],asr_tap=k[1],identity_tap=k[2],case_id=k[3],scientific_digest=v['scientific_digest'],provenance=v['provenance']) for k,v in sorted(selected.items())]
    coverage.extend(dict(candidate_id=k[0],asr_tap=k[1],identity_tap=k[2],case_id=k[3],scientific_digest=v['scientific_digest'],provenance=v['provenance']) for k,v in sorted(historical.items()))
    # Every declared source is fully admitted before any new output is created.
    output.mkdir(parents=True)
    core.csv_write(output/'PAIRED_COMPARISONS.csv',comparisons)
    core.csv_write(output/'SELECTED_SCENE_RESULTS.csv',scene_rows)
    core.save(output/'PAIRED_UNCERTAINTY.json',dict(schema=SCHEMA,comparisons=uncertainty,dependency=dependency,
        scope='Unchanged inherited 2000-resample conditional primary-word uncertainty. cp metrics have paired point deltas here; this file does not add cp-specific bootstrap.'))
    core.save(output/'SELECTED_SCORE_PROVENANCE.json',dict(schema=SCHEMA,rows=coverage))
    allkeys={*selected,*historical};present={k[0] for k in allkeys}
    receipt=dict(schema=SCHEMA,status='COMPLETE_SELECTED_SCORES',input_spec=spec_binding,sources=sources,
        historical_sources=historical_sources,historical_scene_rows=len(historical),
        registry_sources=registry_bindings,bank=bank_binding,input_index=input_binding,codes=current_sources,packages=packages,
        formula_equivalence=equivalence,tests=tests,selected_candidates=sorted(present),unique_scores=len(allkeys),
        admitted_selected_score_references=sum(len(v['provenance']) for v in selected.values()),
        exact_scientific_duplicates=sum(len(v['provenance'])-1 for v in selected.values()),
        missing_selected_parents=[dict(candidate_id=p,parent=parents.get(p)) for p in sorted(present) if parents.get(p) and parents[p] not in present],
        route_counts=[dict(candidate_id=p,asr_tap=a,identity_tap=i,scenes=sum(k[:3]==(p,a,i) for k in allkeys)) for (p,a),i in sorted(routes.items())],
        paired_rows=len(comparisons),uncertainty_comparisons=len(uncertainty),neural_invocations=0,rescored_predictions=0,
        elapsed_sec=time.perf_counter()-started,artifacts=[core.bind(output/n) for n in ('PAIRED_COMPARISONS.csv','SELECTED_SCENE_RESULTS.csv','PAIRED_UNCERTAINTY.json','SELECTED_SCORE_PROVENANCE.json')],
        scope='Explicit completed score subsets only. Exact scientific duplicate parity excludes analysis schema/key/provenance alone, retains all source chains, and never averages duplicates. Input prediction/support bytes are transitively bound through completed scores/indexes, not reopened or rescored. Inherited comparisons use matched case intersections and their reported denominators; exploratory selection remains descriptive.')
    core.save(output/'COMPARISON_RECEIPT.json',receipt)
    return core.bind(output/'COMPARISON_RECEIPT.json')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec',type=Path);p.add_argument('--output-subdir',default='paired_comparison_v1')
    p.add_argument('--no-bootstrap',action='store_true');p.add_argument('--test',action='store_true')
    args=p.parse_args()
    if not args.test and args.spec is None:p.error('--spec is required outside --test')
    print(json.dumps(fixtures() if args.test else run(args),indent=2,allow_nan=False),flush=True)


if __name__=='__main__':main()
