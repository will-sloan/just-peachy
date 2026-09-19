"""Exact S6D width scoring namespace adapter; README_S6D_ANGLE_WIDTH_SCORE.md."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import sys
import time
from s6d_angle_width_replay import bind,verify,read,digest,save,words,prediction,width_profile

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
VIEWS=('word_','cp_first_final_','cp_latest_revised_','cp_first_display_label_final_words_')
POPS={'PRIMARY_NONOVERLAP':156,'COMPLETE_OVERLAP':47,'INCOMPLETE_REFERENCE':26,'STRICT_EMPTY_REFERENCE':11}
COUNTS=('source_turns','supported_turns','unknown_turns','sole_active_samples','known_samples','unknown_samples','false_merge_samples','return_consistent','return_inconsistent','return_unknown')


def bound_read(b):verify(b);return read(b['path'])


def load_context(predeclaration):
    decl_binding=bind(predeclaration);decl=read(predeclaration)
    if decl['schema']!='s6d-width-analysis-predeclaration.v1' or decl['population_counts']!=POPS:raise ValueError('Exact original analysis predeclaration required')
    width=bound_read(decl['source_plan']);bank=bound_read(decl['bank']);inputs=bound_read(decl['input_index']);bound_read(decl['parent_analysis'])
    for b in decl['scorer_codes']:verify(b)
    if len(width['cells'])!=3840 or len(width['controls'])!=1920 or len(width['jobs'])!=16:raise ValueError('Exact bounded width matrix required')
    scenes={s['case_id']:s for s in bank['scenes']};inputrows={(r['case_id'],r['stream']):r for r in inputs['rows']}
    if len(scenes)!=240 or len(inputrows)!=480 or set(width['case_ids'])!=set(scenes):raise ValueError('Original full physical bank/route counts differ')
    return decl_binding,decl,width,bank,scenes,inputrows


def validate_control_score(row,score,decl,support_binding):
    identity=score['analysis_identity']
    if score['analysis_key']!=digest(identity) or identity['prediction']!=row['result'] or identity['support']!=support_binding or identity['bank']!=decl['bank'] or identity['codes']!=decl['scorer_codes']:
        raise ValueError('Frozen control score lacks exact prediction/support/bank/scorer binding')
    if (score['profile_id'],score['case_id'],score['stream'],score['identity_tap'],score['population'])!=(row['candidate_id'],row['case_id'],row['stream'],row['stream'],row['population']):raise ValueError('Control score identity/population differs')
    return True


def prepare(predeclaration,output,score_payload,analysis_report):
    output=Path(output).resolve();score_payload=Path(score_payload).resolve();analysis_report=Path(analysis_report).resolve()
    if output.exists() or not output.is_relative_to(R) or not analysis_report.is_relative_to(R) or not score_payload.is_relative_to(Path('G:/Just_Peachy_S6D/20260913T195357Z')):raise ValueError('Fresh bounded S6D metadata/output roots required')
    decl_binding,decl,width,bank,scenes,inputrows=load_context(predeclaration)
    supports={};verified_controls=[];started=time.perf_counter();original_packages=None
    for n,row in enumerate(width['controls'],1):
        verify(row['result']);score=bound_read(row['score']);sb=inputrows[row['case_id'],row['stream']]['support']
        if row['case_id'] not in supports:
            support_doc=bound_read(sb);supports[row['case_id']]=sb
        elif supports[row['case_id']]!=sb:raise ValueError('Same-scene support differs by tap')
        validate_control_score(row,score,decl,sb)
        packages=score['analysis_identity']['packages']
        if original_packages is None:original_packages=packages
        elif packages!=original_packages:raise ValueError('Control scorer package versions differ')
        verified_controls.append(dict(candidate_id=row['candidate_id'],case_id=row['case_id'],stream=row['stream'],population=row['population'],prediction=row['result'],score=row['score'],support=sb))
        if n%240==0:print(json.dumps(dict(phase='CONTROL_SCORE_BINDING_AUDIT_ONLY',verified=n,requested=1920,elapsed_seconds=time.perf_counter()-started)),flush=True)
    if Counter(r['population'] for r in verified_controls)!=Counter({k:v*8 for k,v in POPS.items()}):raise ValueError('Fixed control denominator populations changed')
    packages={n:version(n) for n in ('numpy','scipy','meeteval')}
    if packages['meeteval']!='0.4.3' or packages!=original_packages:raise ValueError('Exact inherited scorer package versions required')
    expected=[dict(cell_id=c['cell_id'],candidate_id=c['candidate_id'],case_id=c['case_id'],stream=c['stream'],identity_tap=c['identity_tap'],parent=c['parent'],width_deg=c['width_deg'],
        population=c['population'],expected_prediction_path=c['output_path'],support=inputrows[c['case_id'],c['identity_tap']]['support']) for c in width['cells']]
    output.mkdir(parents=True);epoch=output/'source_epoch';epoch.mkdir()
    local=[Path(__file__),Path(__file__).with_name('README_S6D_ANGLE_WIDTH_SCORE.md')]
    for path in local:shutil.copy2(path,epoch/path.name)
    adapter=dict(schema='s6d-width-score-adapter-plan.v1',status='PREPARED_NO_SCORING_EXECUTION',predeclaration=decl_binding,width_plan=decl['source_plan'],bank=decl['bank'],input_index=decl['input_index'],
        parent_analysis=decl['parent_analysis'],scorer_codes=decl['scorer_codes'],adapter_sources=[bind(p) for p in local]+[bind(Path(__file__).with_name('s6d_angle_width_replay.py'))],
        packages=packages,controls=verified_controls,new_cells=expected,expected_jobs=[j['job_id'] for j in width['jobs']],source_supports=list(supports.values()),
        total_requested_scored_cells=5760,new_prediction_cells=3840,reused_exact_control_score_cells=1920,populations_per_route=POPS,
        comparisons=decl['comparisons'],bulk_score_payload_root=str(score_payload),analysis_report_root=str(analysis_report),
        diagnostics_context=decl['paired_controls'],diagnostic_score_policy='Reuse source-bound frozen width25 diagnostic context only; no new-width shuffled/null inference',
        metric_API='Unchanged s6c_analysis_v3.analyze/tables; no call to run or registered_candidates and no global namespace reassignment',
        uncertainty=dict(raw_word='Inherited paired_comparisons bootstrap',cp_views='Inherited conditional_uncertainty on each actual cp errors/reference-count pair, primary matched blocks only',replicates=2000,seed=20260909),
        no_execution_authorization_created=True,hardware_calls=0,model_calls=0,new_scoring_calls=0)
    plan_binding=save(output/'ADAPTER_PLAN.json',adapter)
    return dict(status=adapter['status'],adapter_plan=plan_binding,controls_bound=len(verified_controls),new_cells=len(expected),hardware_calls=0,model_calls=0,new_scoring_calls=0)


def new_prediction(row,cell,width_binding,core):
    value=prediction(row['result']);core.validate_payload(value,row)
    identity=value['identity']
    if identity.get('schema')!='s6d-operational-width-prediction.v1' or identity.get('plan')!=width_binding or identity.get('cell_id')!=cell['cell_id']:
        raise ValueError('Prediction not bound to exact S6D width cell')
    if identity['source']!=cell['source'] or identity['telemetry']!=cell['telemetry'] or identity['parent_prediction']!=cell['parent_prediction']:
        raise ValueError('Prediction changed fixed native/cue/parent evidence')
    parent=prediction(cell['parent_prediction']);expected=width_profile(parent['identity']['profile'],cell['parent'],cell['width_deg'],cell['stream'])
    if identity['profile']!=expected or identity.get('gallery') is not None or identity.get('oracle_like') is not False:raise ValueError('Unexpected profile or gallery/reference consumer')
    if digest(words(value))!=cell['raw_words_digest'] or words(value)!=words(parent):raise ValueError('Raw ASR words changed')
    return value


def paired_adverse(scene_rows,comparisons):
    by={(r['profile_id'],r['stream'],r['case_id']):r for r in scene_rows};out=[]
    for parent,condition in comparisons.items():
        for width in condition['widths']:
            candidate=f'S6D_{parent}_W{width:02d}'
            for tap in ('O0','O1'):
                for control in (parent,condition['cue_off']):
                    for key,b in sorted(by.items()):
                        if key[:2]!=(candidate,tap):continue
                        a=by.get((control,tap,key[2]))
                        if a is None:raise ValueError('Paired exact control missing')
                        if a['population']!=b['population']:raise ValueError('Paired populations changed')
                        row=dict(left_profile=control,right_profile=candidate,stream=tap,case_id=key[2],population=b['population'],metrics={})
                        for prefix in VIEWS:
                            for kind in ('errors','reference_words'):
                                if kind=='reference_words' and a.get(prefix+kind)!=b.get(prefix+kind):raise ValueError('Fixed text denominator changed')
                            x,y=a.get(prefix+'errors'),b.get(prefix+'errors')
                            row['metrics'][prefix.rstrip('_')]=dict(left_errors=x,right_errors=y,right_minus_left_errors=y-x if isinstance(x,(int,float)) and isinstance(y,(int,float)) else None,reference_words=a.get(prefix+'reference_words'))
                        for field in COUNTS:
                            x,y=a.get(field),b.get(field);row[field]=dict(left=x,right=y,right_minus_left=y-x if isinstance(x,(int,float)) and isinstance(y,(int,float)) else None)
                        out.append(row)
    return out


def cp_uncertainty(scene_rows,comparisons,dependency,inherited):
    by={(r['profile_id'],r['stream'],r['case_id']):r for r in scene_rows};results=[]
    for parent,condition in comparisons.items():
        for width in condition['widths']:
            candidate=f'S6D_{parent}_W{width:02d}'
            for tap in ('O0','O1'):
                for control in (parent,condition['cue_off']):
                    for prefix in VIEWS[1:]:
                        rows=[]
                        for key,b in sorted(by.items()):
                            if key[:2]!=(candidate,tap) or b['population']!='PRIMARY_NONOVERLAP':continue
                            a=by.get((control,tap,key[2]))
                            if a is None:continue
                            def lane(r):return dict(text=dict(word_counts={k:r.get(prefix+k) for k in ('errors','reference_words','substitutions','deletions','insertions','hypothesis_words')}))
                            rows.append(dict(case_id=key[2],room=b['room'],O0=lane(a),O1=lane(b)))
                        value=inherited.conditional_uncertainty(rows,dependency,replicates=2000,seed=20260909);value.pop('bootstrap_delta_pp',None)
                        results.append(dict(left_profile=control,right_profile=candidate,stream=tap,metric=prefix.rstrip('_'),population='PRIMARY_NONOVERLAP',uncertainty=value,
                            interpretation='Inherited generic count-ratio bootstrap uses O0=left/O1=right and word_counts field names internally. Here counts are actual named cpWER view counts; no fabricated word boundaries. Whole primary blocks, same rooms and dependency exclusions.'))
    return results


def execute(adapter_plan,authorization,prediction_indices):
    plan_binding=bind(adapter_plan);plan=read(adapter_plan);auth=read(authorization)
    if plan['schema']!='s6d-width-score-adapter-plan.v1' or auth.get('root_review_passed') is not True or auth.get('adapter_plan_sha256')!=plan_binding['sha256']:raise ValueError('Exact root scorer admission required')
    indices=[bind(p) for p in prediction_indices]
    if indices!=auth.get('prediction_indices'):raise ValueError('Literal hash-bound complete prediction indices required')
    for b in plan['adapter_sources']+plan['scorer_codes']:verify(b)
    if Path(plan['adapter_sources'][0]['path']).resolve()!=Path(__file__).resolve():raise ValueError('Invoke the exact source-bound adapter entry point')
    if {n:version(n) for n in plan['packages']}!=plan['packages']:raise ValueError('Scorer package versions changed')
    decl_binding,decl,width,bank,scenes,inputrows=load_context(plan['predeclaration']['path'])
    if decl_binding!=plan['predeclaration'] or decl['source_plan']!=plan['width_plan']:raise ValueError('Changed analysis declaration')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    import s6c_analysis_v3 as core
    from s6a_support_metrics import validate_support
    from s6a_baseline_results import dependency_plan
    new_rows=[];jobs=[]
    for b in indices:
        index=bound_read(b)
        if index.get('status')!='COMPLETE_ADMITTED_POLICY_REPLAY_ONLY' or index.get('source_plan')!=plan['width_plan'] or index.get('new_neural_jobs')!=0 or index.get('hardware_jobs')!=0:raise ValueError('Replay index incomplete or outside exact source plan')
        new_rows.extend(index['rows']);jobs.extend(index['jobs'])
    if any(r.get('status') not in ('COMPLETE','COMPLETE_REUSED') for r in new_rows):raise ValueError('Declared failed or missing replay rows remain unscored; never reinterpret as successful empty output')
    expected={(c['candidate_id'],c['stream'],c['case_id']):c for c in width['cells']};actual=[(r['candidate_id'],r['stream'],r['case_id']) for r in new_rows]
    if len(actual)!=3840 or len(set(actual))!=3840 or set(actual)!=set(expected) or sorted(jobs)!=sorted(plan['expected_jobs']):raise ValueError('All16 jobs/3840 unique cells required; missing is not zero')
    report=Path(plan['analysis_report_root']);payload=Path(plan['bulk_score_payload_root'])
    if report.exists() or payload.exists():raise ValueError('Fresh complete scoring epoch required; preserve interrupted outputs and request a reviewed new epoch')
    report.mkdir(parents=True);payload.mkdir(parents=True);save(report/'ADMISSION.json',dict(adapter_plan=plan_binding,authorization=bind(authorization),prediction_indices=indices))
    records=[];coverage=[];supports={};start=time.perf_counter()
    for item in plan['controls']:
        score=bound_read(item['score']);legacy=dict(candidate_id=item['candidate_id'],case_id=item['case_id'],stream=item['stream'],population=item['population'],result=item['prediction'])
        validate_control_score(legacy,score,decl,item['support'])
        if score['analysis_identity']['packages']!=plan['packages']:raise ValueError('Control score package binding differs')
        records.append(score)
        coverage.append(dict(candidate_id=item['candidate_id'],case_id=item['case_id'],stream=item['stream'],status='REUSED_EXACT_BOUND_SCORER_RESULT',result=item['score']))
    for n,row in enumerate(sorted(new_rows,key=lambda r:(r['case_id'],r['stream'],r['candidate_id'])),1):
        cell=expected[row['candidate_id'],row['stream'],row['case_id']]
        if Path(row['result']['path']).resolve()!=Path(cell['output_path']).resolve():raise ValueError('Index points to another width output path')
        value=new_prediction(row,cell,plan['width_plan'],core);sb=inputrows[cell['case_id'],cell['identity_tap']]['support']
        if cell['case_id'] not in supports:supports[cell['case_id']]=bound_read(sb)['support'];validate_support(scenes[cell['case_id']],supports[cell['case_id']])
        identity=dict(schema='s6d-width-score-identity.v1',adapter_plan=plan_binding,prediction=row['result'],support=sb,bank=plan['bank'],codes=plan['scorer_codes'],adapter_sources=plan['adapter_sources'],packages=plan['packages'])
        result=core.analyze(value,scenes[cell['case_id']],supports[cell['case_id']],frozenset(scenes))
        if result['population']!=cell['population']:raise ValueError('New score changed fixed population')
        result.update(analysis_key=digest(identity),analysis_identity=identity);target=payload/cell['candidate_id']/cell['case_id']/(cell['stream']+'.json');result_binding=save(target,result)
        records.append(result);coverage.append(dict(candidate_id=cell['candidate_id'],case_id=cell['case_id'],stream=cell['stream'],status='SCORED',result=result_binding,raw_words_invariant=True))
        if n%60==0:print(json.dumps(dict(phase='S6D_WIDTH_SCORING',completed=n,requested=3840,elapsed_seconds=time.perf_counter()-start,model_calls=0)),flush=True)
    scene_rows,turn_rows,summary,short,regions,lifecycle,resources,strata=core.tables(records);dependency=dependency_plan(scenes,bank['selected_sources'])
    paired=[];uncertainty=[]
    for mode in ('parent','cue_off'):
        registry=[dict(profile_id=f'S6D_{parent}_W{width:02d}',parent=parent if mode=='parent' else condition['cue_off']) for parent,condition in plan['comparisons'].items() for width in condition['widths']]
        rows,intervals=core.inherited.paired_comparisons(scene_rows,registry,dependency,bootstrap=True)
        paired.extend(r for r in rows if mode=='parent' or r['comparison']=='candidate_minus_parent')
        uncertainty.extend(dict(control_mode=mode,**u) for u in intervals if mode=='parent' or u['left_profile']!=u['right_profile'])
    adverse=paired_adverse(scene_rows,plan['comparisons']);cp_intervals=cp_uncertainty(scene_rows,plan['comparisons'],dependency,core.inherited)
    tables={'SCENE_RESULTS.csv':scene_rows,'TURN_RESULTS.csv':turn_rows,'PROFILE_RESULTS.csv':summary,'SHORT_REPLY_RESULTS.csv':short,'REGION_RESULTS.csv':regions,
        'TRACK_LIFECYCLE_RESULTS.csv':lifecycle,'RECIPE_COST_RESULTS.csv':resources,'STRATA_RESULTS.csv':strata,'PAIRED_COMPARISONS.csv':paired,'COVERAGE.csv':coverage}
    for name,rows in tables.items():core.csv_write(report/name,rows)
    for name,value in (('PROFILE_RESULTS.json',summary),('PAIRED_UNCERTAINTY_LEXICAL.json',uncertainty),('PAIRED_UNCERTAINTY_CP_VIEWS.json',cp_intervals),('PER_CASE_ADVERSE_DELTAS.json',adverse),('DEPENDENCY_PLAN.json',dependency)):
        save(report/name,value)
    for b in plan['adapter_sources']+plan['scorer_codes']+[plan['bank'],plan['input_index']]+indices:verify(b)
    for item in plan['controls']:verify(item['prediction']);verify(item['score'])
    for row in new_rows:verify(row['result'])
    for b in plan['source_supports']:verify(b)
    receipt=dict(schema='s6d-width-scoring-receipt.v1',status='COMPLETE_BOUNDED_MATRIX_SCORING',adapter_plan=plan_binding,prediction_indices=indices,scored_new_cells=3840,reused_exact_control_cells=1920,
        total_scored_cells=len(records),population_counts_per_route=POPS,raw_word_invariance_cells=3840,scorer_codes=plan['scorer_codes'],tables=[bind(report/name) for name in tables],
        other_artifacts=[bind(report/name) for name in ('PROFILE_RESULTS.json','PAIRED_UNCERTAINTY_LEXICAL.json','PAIRED_UNCERTAINTY_CP_VIEWS.json','PER_CASE_ADVERSE_DELTAS.json','DEPENDENCY_PLAN.json')],
        diagnostic_context=plan['diagnostics_context'],diagnostics_are_only_width25=True,hardware_calls=0,model_calls=0,native_confirmation_required_before_retention=True,
        scope='Actual frozen words and label views under evaluator-only support; complete/incomplete/strict-empty populations separate. No default promotion, new neural inference, GUI latency, CM5/runtime or aggregate S6D completion claim.')
    save(report/'SCORING_RECEIPT.json',receipt);return dict(status=receipt['status'],receipt=bind(report/'SCORING_RECEIPT.json'),scored=5760,hardware_calls=0,model_calls=0)


def fixtures():
    a=dict(profile_id='C079',stream='O0',case_id='X',population='INCOMPLETE_REFERENCE',word_errors=None,word_reference_words=None,unknown_samples=12)
    b=dict(a,profile_id='S6D_C079_W02',unknown_samples=21)
    rows=paired_adverse([a,b,dict(a,profile_id='C065')],{'C079':dict(widths=[2],cue_off='C065')})
    tests=dict(missing_not_zero=all(r['metrics']['word']['right_minus_left_errors'] is None for r in rows),adverse_unknown_counts_retained=all(r['unknown_samples']['right_minus_left']==9 for r in rows),population_not_pooled=all(r['population']=='INCOMPLETE_REFERENCE' for r in rows))
    bad=dict(b,word_reference_words=1)
    try:paired_adverse([a,bad,dict(a,profile_id='C065')],{'C079':dict(widths=[2],cue_off='C065')})
    except ValueError:tests['changed_denominator_rejected']=True
    else:tests['changed_denominator_rejected']=False
    try:paired_adverse([a,b],{'C079':dict(widths=[2],cue_off='C065')})
    except ValueError:tests['missing_control_rejected']=True
    else:tests['missing_control_rejected']=False
    identity=dict(prediction={'path':'p'},support={'path':'s'},bank={'path':'b'},codes=[])
    score=dict(analysis_identity=identity,analysis_key=digest(identity),profile_id='C079',case_id='X',stream='O0',identity_tap='O0',population='INCOMPLETE_REFERENCE')
    row=dict(candidate_id='C079',case_id='X',stream='O0',population='INCOMPLETE_REFERENCE',result={'path':'p'});decl=dict(bank={'path':'b'},scorer_codes=[])
    tests['exact_bound_control_accepted']=validate_control_score(row,score,decl,{'path':'s'})
    try:validate_control_score(row,score,dict(decl,scorer_codes=[{'sha256':'changed'}]),{'path':'s'})
    except ValueError:tests['changed_scorer_control_rejected']=True
    else:tests['changed_scorer_control_rejected']=False
    # Actual inherited numerical API on synthetic count rows only.
    from s6a_baseline_results import conditional_uncertainty
    from types import SimpleNamespace
    fake=[]
    for tap in ('O0','O1'):
        for candidate,error in (('C079',1),('C065',1),('S6D_C079_W02',2)):
            r=dict(profile_id=candidate,stream=tap,case_id='X',population='PRIMARY_NONOVERLAP',room='synthetic_room')
            for prefix in VIEWS[1:]:
                r.update({prefix+k:v for k,v in dict(errors=error,reference_words=10,substitutions=error,deletions=0,insertions=0,hypothesis_words=10).items()})
            fake.append(r)
    dep=dict(blocks=[dict(block_id='synthetic_block',room_table='synthetic_room',primary_scene_ids=['X'])],dependency_diagnostics={},all_dependencies_primary_component_sizes=[1])
    intervals=cp_uncertainty(fake,{'C079':dict(widths=[2],cue_off='C065')},dep,SimpleNamespace(conditional_uncertainty=conditional_uncertainty))
    tests['cp_count_adapter_real_inherited_API']=len(intervals)==12 and all(r['uncertainty']['paired_O1_minus_O0_wer_pp_percentile95']==[10.,10.] for r in intervals)
    tests['cp_adapter_fixed_seed_and_replicates']=all(r['uncertainty']['replicates']==2000 and r['uncertainty']['seed']==20260909 for r in intervals)
    assert all(tests.values()),tests
    return dict(status='PASS_MODEL_FREE',checks=tests,hardware_calls=0,model_calls=0,new_scoring_calls=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--predeclaration',type=Path,required=True);prep.add_argument('--output',type=Path,required=True);prep.add_argument('--score-payload',type=Path,required=True);prep.add_argument('--analysis-report',type=Path,required=True)
    run=sub.add_parser('execute');run.add_argument('--adapter-plan',type=Path,required=True);run.add_argument('--authorization',type=Path,required=True);run.add_argument('--prediction-indices',nargs='+',type=Path,required=True)
    test=sub.add_parser('check');test.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.action=='prepare':answer=prepare(a.predeclaration,a.output,a.score_payload,a.analysis_report)
    elif a.action=='execute':answer=execute(a.adapter_plan,a.authorization,a.prediction_indices)
    else:answer=fixtures();save(a.output,answer)
    print(json.dumps(answer,indent=2),flush=True)
