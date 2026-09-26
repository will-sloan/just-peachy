"""Complete V3 panel conditional naming review. See README_SEMANTIC_PANEL_V3.md."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time

from common import bind,fingerprint,freeze,load,verify
from metric_process import exact_process,identity,pin
from naming_reference import EXPECTED_CLASSES
from paced_child_admission import assert_plain_path
from paced_panel_plan_v3 import execution_payload
from review_application_content_panel import add_bindings
from review_application_panel_v3 import compact_cell,stopped_run,validate_population
from review_application_semantics_v3 import review_labels as review_cell,load_reference_context,score_cell
from review_application_transport_v3 import record
from review_name_panel import AXES,SCENARIOS,CATEGORIES,STAGES,PANES,REFERENCE_SUPPORT,HEADINGS,OUTCOMES,pack,unpack
from review_scoring_bank import OUTPUT_LIMIT,guard,require,shared_allowance
from scoring_bank import writer_lock

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('review_semantic_panel_v3.py','test_semantic_panel_v3.py','probe_semantic_panel_v3.py','README_SEMANTIC_PANEL_V3.md')
QUALIFICATION='SEMANTIC_PANEL_CHECK_V3.json'


def code_bindings():
    entries=[bind(HERE/name) for name in OWN]
    for name,status in (('APPLICATION_PANEL_REVIEW_CHECK_V3.json','PASS_V3_PANEL_CENSUS_REVIEW_DEVELOPMENT_ONLY'),
        ('APPLICATION_SEMANTICS_CHECK_V3.json','PASS_V3_APPLICATION_SEMANTICS_DEVELOPMENT_ONLY'),
        ('NAME_PANEL_CHECK_V1.json','PASS_NAME_PANEL_DEVELOPMENT_ONLY')):
        q=load(HERE/name);require(q['status']==status,'V3 semantic-panel prerequisite differs')
        verify(q['private_receipt']);proof=load(q['private_receipt']['path']);verify(proof['admission'])
        require(exact_process(load(proof['admission']['path'])['owner']) is None,'Prerequisite helper remains active')
        entries.extend([bind(HERE/name),*q['code']])
    result={}
    for b in entries:
        require(b['path'] not in result or result[b['path']]==b,'Conflicting semantic-panel dependency');result[b['path']]=b
    return list(result.values())


def compact_content(checked, row, payload, registry):
    require(checked['status']=='PASS_V3_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY'
        and checked['integrated_N4_cells']==0 and checked['N4_accepted'] is False
        and all(checked[k] is True for k in ('application_owner_and_primary_settings_joined',
            'fixed_display_roster_independently_joined','primary_caption_text_consistency_reviewed')),
        'Complete cell content composition required')
    require(payload['cell_id']==row['cell_id']==checked['cell']['transport']['cell_id']
        and fingerprint(payload['job'])==fingerprint(row['job'])
        and fingerprint(payload['contract'])==fingerprint(row['contract']), 'Content cell differs from planned row')
    for flag in ('exact_consumed_event_attribution','accuracy_qualified','names_independently_scored',
        'source_to_widget_latency_qualified','controlled_resources_qualified','complete_panel_reviewed',
        'physical_scanout_measured','actual_continuity_test','stop_restart_qualified'):
        require(checked[flag] is False,'Cell content reader improperly promoted '+flag)
    base=compact_cell(checked['cell'],row,payload);w=checked['widget'];r=checked['roster']
    require(w['people_sha256']==r['people_sha256'],'Cell roster fingerprint differs')
    counts=dict(native_spans=w['native_span_population'],observed_spans=w['observed_span_population'],
        unobserved_native_spans=len(w['native_spans_not_observed']),never_visible_observed_spans=w['observed_spans_never_visible'],
        observed_spans_without_final_visibility=w['observed_spans_without_final_visibility'],
        missing_caption_revisions=len(w['missing_native_caption_revisions']),ambiguous_state_joins=w['ambiguous_state_joins'],
        native_segment_entries=w['native_segment_history_entries'],changed_rows=len(w['changed_rows']),sampled_states=len(w['states']))
    require(all(type(n) is int and 0<=n<=262144 for n in counts.values())
        and counts['observed_spans']+counts['unobserved_native_spans']==counts['native_spans']
        and max(counts['never_visible_observed_spans'],counts['observed_spans_without_final_visibility'])<=counts['observed_spans']
        and counts['ambiguous_state_joins']<=counts['sampled_states'],'Content denominator census differs')
    entries=base['evidence']+w['evidence']+r['evidence']+[checked['application_qualification'],checked['source_context'],w['source_receipt'],w['casing_source']]
    unique={};add_bindings(unique,entries);add_bindings(registry,list(unique.values()))
    # All binding bytes are retained once in the panel registry. Native text,
    # heading strings and per-span histories can be reconstructed from them.
    base.pop('evidence')
    return dict(base,status='PASS_V3_CELL_CONTENT_COVERAGE_ONLY',
        full_content_review_sha256=fingerprint(checked),content_inputs_sha256=fingerprint(sorted(unique.values(),key=lambda b:b['path'])),
        content_counts=counts,maximum_observation_interval_seconds=w['maximum_observation_interval_seconds'],
        roster={k:r[k] for k in ('people_sha256','available_size','intended_size','unavailable_count','ordering')},
        primary_caption_text_consistency_reviewed=True,exact_consumed_event_attribution=False,names_independently_scored=False)


def population(context):
    folder=context['folder'];plan=context['plan']
    cells=assert_plain_path(folder/'cells',folder);progress_root=assert_plain_path(folder/'progress',folder)
    cell_entries=list(cells.iterdir());progress_entries=list(progress_root.iterdir())
    require(len(cell_entries)<=240 and len(progress_entries)<=240,'Panel directory census exceeds bound')
    for p in cell_entries:require(assert_plain_path(p,folder).is_dir(),'Unexpected non-directory cell entry')
    for p in progress_entries:require(assert_plain_path(p,folder).is_file(),'Unexpected non-file progress entry')
    collected=[];progress=[];bindings=[]
    for i,row in enumerate(plan['rows']):
        b,_=record(cells/row['cell_id']/'COLLECTED.json',folder);collected.append(b)
        b,value=record(progress_root/f'{i+1:04d}.json',folder);bindings.append(b);progress.append(value)
    census=validate_population(plan,context['terminal'],collected,progress,[p.name for p in cell_entries],[p.name for p in progress_entries])
    return cells,collected,bindings,census


def compact(checked,score,references,row,payload,registry):
    require(checked['status']=='PASS_V3_APPLICATION_RECORDED_GUI_LABELS_ONLY'
        and score['status']=='SCORED_ESTIMATED_SUPPORT_NAME_DIAGNOSTICS_ONLY'
        and score['observed_review_sha256']==fingerprint(checked) and score['job_id']==payload['job']['job_id'],
        'Joined observed-name score required')
    require(checked['observed']['status']=='PASS_V3_APPLICATION_RECORDED_ROW_TIMING_ONLY'
        and checked['timing_review_sha256']==fingerprint(checked['observed'])
        and checked['observed']['content_review_sha256']==fingerprint(checked['observed']['content']),
        'V3 semantic reader chain changed')
    for flag in ('naming_accuracy_qualified','exact_word_identity_established','acquisition_latency_qualified',
                 'continuous_wrong_name_exposure_measured','complete_panel_reviewed','N4_accepted'):
        require(score[flag] is False,'Name scorer improperly promoted '+flag)
    require(score['integrated_N4_cells']==0 and set(score['scenarios'])==set(SCENARIOS),
        'Primary observed and two controlled diagnostic scenarios required')
    base=compact_content(checked['observed']['content'],row,payload,registry)
    delivery=base['source_delivery'];envelope=delivery['envelope']
    require(registry.get(envelope['path'])==envelope,'Delivery summary envelope missing from panel registry')
    summary=delivery.pop('summary')
    delivery.update(summary_sha256=fingerprint(summary),summary_storage='bound_envelope.review.summary',
        raw_summary_preserved_in_bound_envelope=True)
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
    return dict(base,status='PASS_V3_CELL_NAME_DIAGNOSTICS_ONLY',full_observed_name_review_sha256=fingerprint(checked),
        full_name_score_sha256=fingerprint(score),reference_context_sha256=fingerprint(references),
        reference_class=score['reference_class'],native_lexical_spans=score['native_lexical_spans'],
        empty_caption_spans_excluded=score['empty_caption_spans_excluded'],name_count_vectors=vectors,
        pane_conflicts=conflicts,revision_counts=revisions,constant_control_profile_id=score['constant_control_profile_id'],
        name_count_axes_sha256=fingerprint(AXES),conditional_name_diagnostics_scored=True,naming_accuracy_qualified=False)


def aggregate(summaries):
    require(type(summaries) is list and 1<=len(summaries)<=240,'Bounded naming-panel summaries required')
    ids=set();fixed={};groups={}
    for s in summaries:
        require(s['status']=='PASS_V3_CELL_NAME_DIAGNOSTICS_ONLY' and s['cell_id'] not in ids
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
            require(q['status']=='PASS_V3_SEMANTIC_PANEL_DEVELOPMENT_ONLY' and q['code']==code,'Naming-panel implementation not qualified')
            for b in code:verify(b)
            context=stopped_run(run_root);plan=context['plan'];cells,collected,progress,census=population(context)
            references=load_reference_context(checkpoint=checkpoint)
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
            save(output/'REVIEW.json',dict(status='PASS_COMPLETE_V3_PANEL_NAME_DIAGNOSTICS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
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
