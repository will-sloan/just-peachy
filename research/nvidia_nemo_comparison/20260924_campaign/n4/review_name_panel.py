"""Complete stopped-panel name diagnostics; see README_NAME_PANEL.md."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time

from common import bind,fingerprint,freeze,load,verify
from metric_process import exact_process,identity,pin
from naming_reference import EXPECTED_CLASSES,load_qualified_context
from paced_panel_plan_v2 import execution_payload
from review_application_content_panel import add_bindings,compact_content,population,stopped_run
from review_application_labels import review_cell
from review_scoring_bank import OUTPUT_LIMIT,guard,require,shared_allowance
from score_observed_names import KINDS,PANES,STAGES,SUPPORTS,score_cell
from scoring_bank import writer_lock

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('review_name_panel.py','test_name_panel.py','probe_name_panel.py','README_NAME_PANEL.md')
QUALIFICATION='NAME_PANEL_CHECK_V1.json'
SCENARIOS=('observed','all_unknown','constant_name')
CATEGORIES=('AVAILABLE_PROFILE_REFERENCE','OUTSIDE_AVAILABLE_PROFILE_REFERENCE','UNRESOLVED_REFERENCE')
REFERENCE_SUPPORT=tuple(sorted(SUPPORTS-{'NOT_A_LEXICAL_WORD'}))
HEADINGS=tuple(sorted(KINDS|{'MISSING_STAGE'}))
OUTCOMES=tuple(sorted({'MISSING_STAGE','NO_SAME_PANE_VISIBLE_HEADING_AND_CAPTION',
    'VISIBLE_NAME_UNRESOLVED_REFERENCE','KNOWN_NAME_ON_OUTSIDE_AVAILABLE_REFERENCE',
    'ESTIMATED_SUPPORT_CORRECT_AVAILABLE_NAME','ESTIMATED_SUPPORT_WRONG_AVAILABLE_NAME'}
    |{'VISIBLE_'+k for k in KINDS-{'ROSTER_NAME'}}))
AXES=dict(scenarios=SCENARIOS,stages=STAGES,panes=PANES,
    vectors=('reference_category_counts','reference_support_counts','heading_kind_counts','outcome_counts','joint_visible_spans'),
    reference_categories=CATEGORIES,reference_support=REFERENCE_SUPPORT,heading_kinds=HEADINGS,outcomes=OUTCOMES)


def code_bindings():
    entries=[bind(HERE/name) for name in OWN]
    for name,status in (('APPLICATION_CONTENT_PANEL_CHECK_V1.json','PASS_APPLICATION_CONTENT_PANEL_DEVELOPMENT_ONLY'),
                        ('OBSERVED_NAME_SCORING_CHECK_V1.json','PASS_OBSERVED_NAME_DIAGNOSTIC_DEVELOPMENT_ONLY')):
        q=load(HERE/name);require(q['status']==status,'Panel naming prerequisite differs')
        verify(q['private_receipt']);proof=load(q['private_receipt']['path']);verify(proof['admission'])
        require(exact_process(load(proof['admission']['path'])['owner']) is None,'Prerequisite helper remains active')
        entries.extend([bind(HERE/name),*q['code']])
    result={}
    for b in entries:
        require(b['path'] not in result or result[b['path']]==b,'Conflicting naming-panel dependency');result[b['path']]=b
    return list(result.values())


def unpack(value):
    require(type(value) is list and len(value)==5,'Count-vector schema differs')
    axes=(CATEGORIES,REFERENCE_SUPPORT,HEADINGS,OUTCOMES);maps=[]
    for vector,axis in zip(value[:4],axes):
        require(type(vector) is list and len(vector)==len(axis) and all(type(x) is int and x>=0 for x in vector),
            'Noninteger, negative or truncated name count vector')
        maps.append({k:v for k,v in zip(axis,vector) if v})
    refs,support,kinds,outcomes=maps;n=sum(value[0]);visible=value[4]
    require(type(visible) is int and 0<=visible<=n and all(sum(v)==n for v in value[:4]),'Naming populations differ')
    get=lambda key:outcomes.get(key,0)
    missing=get('MISSING_STAGE');hidden=get('NO_SAME_PANE_VISIBLE_HEADING_AND_CAPTION')
    known=refs.get(CATEGORIES[0],0);outside=refs.get(CATEGORIES[1],0);unresolved=refs.get(CATEGORIES[2],0)
    correct=get('ESTIMATED_SUPPORT_CORRECT_AVAILABLE_NAME');wrong=get('ESTIMATED_SUPPORT_WRONG_AVAILABLE_NAME')
    false_known=get('KNOWN_NAME_ON_OUTSIDE_AVAILABLE_REFERENCE');unknown=get('VISIBLE_UNKNOWN')
    require(visible+missing+hidden==n and kinds.get('MISSING_STAGE',0)==missing
        and correct+wrong<=known and false_known<=outside
        and get('VISIBLE_NAME_UNRESOLVED_REFERENCE')<=unresolved
        and sum(v for k,v in outcomes.items() if k not in ('MISSING_STAGE','NO_SAME_PANE_VISIBLE_HEADING_AND_CAPTION'))==visible,
        'Naming opportunity or support denominators differ')
    ratio=lambda a,b:a/b if b else None
    return dict(native_lexical_spans=n,joint_visible_spans=visible,reference_category_counts=refs,
        reference_support_counts=support,heading_kind_counts=kinds,outcome_counts=outcomes,
        single_available_reference_spans=known,single_outside_available_reference_spans=outside,
        unresolved_reference_spans=unresolved,missing_stage=missing,not_jointly_visible=hidden,
        rates=dict(estimated_correct_name_per_single_available_reference_span=ratio(correct,known),
            estimated_wrong_name_per_single_available_reference_span=ratio(wrong,known),
            known_name_per_single_outside_available_reference_span=ratio(false_known,outside),
            visible_Unknown_per_native_lexical_span=ratio(unknown,n),visible_Unknown_per_joint_visible_span=ratio(unknown,visible)))


def pack(summary):
    result=[]
    for field,axis in (('reference_category_counts',CATEGORIES),('reference_support_counts',REFERENCE_SUPPORT),
                       ('heading_kind_counts',HEADINGS),('outcome_counts',OUTCOMES)):
        value=summary[field];require(type(value) is dict and set(value)<=set(axis),'Unexpected name count category')
        result.append([value.get(k,0) for k in axis])
    result.append(summary['joint_visible_spans'])
    require(unpack(result)==summary,'Name counts/rates cannot be compacted losslessly')
    return result


def compact(checked,score,references,row,payload,registry):
    require(checked['status']=='PASS_V2_APPLICATION_RECORDED_GUI_LABELS_ONLY'
        and score['status']=='SCORED_ESTIMATED_SUPPORT_NAME_DIAGNOSTICS_ONLY'
        and score['observed_review_sha256']==fingerprint(checked) and score['job_id']==payload['job']['job_id'],
        'Joined observed-name score required')
    for flag in ('naming_accuracy_qualified','exact_word_identity_established','acquisition_latency_qualified',
                 'continuous_wrong_name_exposure_measured','complete_panel_reviewed','N4_accepted'):
        require(score[flag] is False,'Name scorer improperly promoted '+flag)
    require(score['integrated_N4_cells']==0 and set(score['scenarios'])==set(SCENARIOS),
        'Primary observed and two controlled diagnostic scenarios required')
    base=compact_content(checked['observed']['content'],row,payload,registry)
    require(score['native_spans']==base['content_counts']['native_spans']
        and score['native_lexical_spans']+score['empty_caption_spans_excluded']==score['native_spans'],
        'Content/naming span populations differ')
    add_bindings(registry,checked['evidence']+checked['display_policy_source']+references['evidence'])
    vectors=[[[pack(score['scenarios'][s][stage][pane]) for pane in PANES] for stage in STAGES] for s in SCENARIOS]
    conflicts=[[score['pane_conflicts'][stage][k] for k in
        ('conflicting_visible_roster_names','differing_applied_pane_headings')] for stage in STAGES]
    revisions=[[score['revision_counts'][key][k] for k in
        ('sum_over_native_spans','spans_with_recorded_count','spans_without_recorded_count')]
        for key in ('observed_heading_changes','observed_visible_heading_changes')]
    return dict(base,status='PASS_V2_CELL_NAME_DIAGNOSTICS_ONLY',full_observed_name_review_sha256=fingerprint(checked),
        full_name_score_sha256=fingerprint(score),reference_context_sha256=fingerprint(references),
        reference_class=score['reference_class'],native_lexical_spans=score['native_lexical_spans'],
        empty_caption_spans_excluded=score['empty_caption_spans_excluded'],name_count_vectors=vectors,
        pane_conflicts=conflicts,revision_counts=revisions,constant_control_profile_id=score['constant_control_profile_id'],
        name_count_axes_sha256=fingerprint(AXES),conditional_name_diagnostics_scored=True,naming_accuracy_qualified=False)


def aggregate(summaries):
    require(type(summaries) is list and 1<=len(summaries)<=240,'Bounded naming-panel summaries required')
    ids=set();fixed={};groups={}
    for s in summaries:
        require(s['status']=='PASS_V2_CELL_NAME_DIAGNOSTICS_ONLY' and s['cell_id'] not in ids
            and s['name_count_axes_sha256']==fingerprint(AXES) and s['integrated_N4_cells']==0 and s['N4_accepted'] is False
            and s['naming_accuracy_qualified'] is False and s['conditional_name_diagnostics_scored'] is True,
            'Repeated, foreign or unreviewed naming-panel summary')
        require(s['reference_class'] in EXPECTED_CLASSES and s['tap'] in ('O0','O1')
            and s['kind'] in ('panel','timing_repeat'),'Unknown naming-panel stratum')
        ids.add(s['cell_id']);composition=s['composition'];fixed_value=fingerprint([s['roster'],s['constant_control_profile_id'],s['reference_context_sha256']])
        require(composition not in fixed or fixed[composition]==fixed_value,'Fixed roster/control/reference context changed within composition')
        fixed[composition]=fixed_value;n=s['native_lexical_spans'];empty=s['empty_caption_spans_excluded']
        require(type(n) is int and type(empty) is int and 0<=n<=8192 and 0<=empty<=8192
            and n+empty==s['content_counts']['native_spans'],'Invalid compact naming population')
        vectors=s['name_count_vectors'];require(len(vectors)==3 and all(len(stages)==3 and all(len(panes)==2 for panes in stages) for stages in vectors),
            'Scenario/stage/pane axes differ')
        for stages in vectors:
            for panes in stages:
                for v in panes:require(unpack(v)['native_lexical_spans']==n,'One naming axis dropped native spans')
        require(len(s['pane_conflicts'])==3 and all(len(r)==2 and all(type(x) is int and 0<=x<=n for x in r) for r in s['pane_conflicts']),
            'Invalid pane conflict counts')
        require(len(s['revision_counts'])==2 and all(len(r)==3 and all(type(x) is int and x>=0 for x in r) and r[1]+r[2]==n for r in s['revision_counts']),
            'Invalid revision availability counts')
        key=(composition,s['kind'],s['tap'],s['reference_class'])
        g=groups.setdefault(key,dict(composition=composition,kind=s['kind'],tap=s['tap'],reference_class=s['reference_class'],
            cells=0,native_lexical_spans=0,empty_caption_spans_excluded=0,vectors=[[[[[0]*len(CATEGORIES),[0]*len(REFERENCE_SUPPORT),
                [0]*len(HEADINGS),[0]*len(OUTCOMES),0] for _ in PANES] for _ in STAGES] for _ in SCENARIOS],
            pane_conflicts=[[0,0] for _ in STAGES],revision_counts=[[0,0,0],[0,0,0]]))
        g['cells']+=1;g['native_lexical_spans']+=n;g['empty_caption_spans_excluded']+=empty
        for si,stages in enumerate(vectors):
            for ti,panes in enumerate(stages):
                for pi,v in enumerate(panes):
                    target=g['vectors'][si][ti][pi]
                    for vi in range(4):target[vi]=[a+b for a,b in zip(target[vi],v[vi])]
                    target[4]+=v[4]
        for field in ('pane_conflicts','revision_counts'):
            g[field]=[[a+b for a,b in zip(x,y)] for x,y in zip(g[field],s[field])]
    output=[]
    for key in sorted(groups):
        g=groups[key];vectors=g.pop('vectors')
        g['scenarios']={s:{stage:{pane:unpack(vectors[si][ti][pi]) for pi,pane in enumerate(PANES)}
            for ti,stage in enumerate(STAGES)} for si,s in enumerate(SCENARIOS)}
        output.append(g)
    return dict(cells=len(summaries),groups=output,name_count_axes=AXES,
        rates_from_summed_counts=True,per_cell_rates_averaged=False,
        counting_unit='Cell-native-span observations per pane/stage; composition, tap, repeat kind and reference class remain separate',
        naming_accuracy_qualified=False,source_to_widget_latency_qualified=False,integrated_N4_cells=0,N4_accepted=False)


def run(run_root,output):
    process=pin();started=time.monotonic();sys.path.insert(0,str(HERE.parents[3]))
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private naming-panel output required')
    require(not output.resolve().is_relative_to(run_root.resolve()) and not run_root.resolve().is_relative_to(output.resolve()),
        'Immutable run and review output must be separate')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,3600);inventory=shared_allowance(LOCAL)
        freeze(output/'REVIEW_OWNER.json',dict(owner=identity(process),run=str(run_root.resolve()),utc=datetime.now(timezone.utc).isoformat()))
        last=[0.]
        def checkpoint():
            if time.monotonic()-last[0]>=1:guard(output,LOCAL,started,3600);last[0]=time.monotonic()
        def save(path,value):
            size=len((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
            used=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
            require(used+size<OUTPUT_LIMIT,'Naming-panel output allowance exceeded');freeze(path,value)
        try:
            code=code_bindings();qb=bind(HERE/QUALIFICATION);q=load(qb['path'])
            require(q['status']=='PASS_NAME_PANEL_DEVELOPMENT_ONLY' and q['code']==code,'Naming-panel implementation not qualified')
            for b in code:verify(b)
            context=stopped_run(run_root);plan=context['plan'];cells,collected,progress,census=population(context)
            references=load_qualified_context(checkpoint=checkpoint)
            save(output/'ADMISSION.json',dict(owner=identity(process),run_admission=context['admission'],plan=context['plan_binding'],
                run_records=context['bindings'],progress=progress,population=census,code=code,qualification=qb,inventory=inventory,
                reference_inputs=references['inputs'],reference_context_sha256=fingerprint(references),name_count_axes=AXES))
            summaries=[];outputs=[];registry={}
            for i,row in enumerate(plan['rows']):
                checkpoint();payload=execution_payload(plan,i)
                checked=review_cell(cells/row['cell_id'],payload=payload,plan_sha256=fingerprint(plan),
                    coordinator=context['coordinator'],code=context['code'],executable=context['executable'],
                    coordinator_argv=context['coordinator_argv'],state=context['state'],checkpoint=checkpoint)
                require(checked['observed']['content']['cell']['transport']['collected']==collected[i],'Observed cell changed after panel census')
                score=score_cell(references,checked,payload,checkpoint=checkpoint)
                summary=compact(checked,score,references,row,payload,registry);summaries.append(summary)
                path=output/'cells'/f'{i+1:04d}.json';save(path,summary);outputs.append(bind(path))
            report=aggregate(summaries);require(report['cells']==census['planned_cells'],'Incomplete naming review coverage')
            for b in code+context['bindings']+[context['plan_binding'],qb]+collected+progress+list(registry.values()):verify(b)
            require(exact_process(context['coordinator']) is None,'Exact coordinator unexpectedly active')
            checkpoint();save(output/'INPUT_BINDINGS.json',dict(bindings=sorted(registry.values(),key=lambda b:b['path'])))
            save(output/'REVIEW.json',dict(status='PASS_COMPLETE_V2_PANEL_NAME_DIAGNOSTICS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),population=census,cell_reviews=outputs,input_bindings=bind(output/'INPUT_BINDINGS.json'),
                report=report,complete_planned_name_diagnostic_population_reviewed=True,conditional_name_diagnostics_scored=True,
                naming_accuracy_qualified=False,exact_word_identity_established=False,source_to_widget_latency_qualified=False,
                controlled_resources_qualified=False,continuity_included=False,stop_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('Complete planned conditional naming diagnostics reviewed; no exact naming/timing or stage acceptance',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_NAME_PANEL_REVIEW_PRESERVED',owner=identity(process),
                error_type=type(exc).__name__,integrated_N4_cells=0,N4_accepted=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();run(args.run,args.output)
