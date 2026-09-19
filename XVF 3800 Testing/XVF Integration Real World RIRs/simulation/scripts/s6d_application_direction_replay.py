"""All240/both-tap direction availability replay. See README_S6D_APPLICATION_DIRECTION.md."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
import json
import math
from pathlib import Path
import sys
import time

SIM=Path(__file__).resolve().parents[1]
APP=SIM.parents[2]/'Software Validation from Datasets/Evaluation Tool/app'
sys.path.insert(0,str(APP))
from edge_speech_pipeline.research_s6d import S6DSettings,PresentationState
import s6c_name_analysis_v3 as names
from s6a_support_metrics import union,intersection,samples,validate_support


def run(output,focus_plan_path):
    core=names.core;output.mkdir(parents=True,exist_ok=False)
    focus=core.read(focus_plan_path)
    if core.bind(focus_plan_path)['sha256']!='5a39ef5b596c343ecb99278303d5232fa0d004faeb2e9e8cafa9e3bcfc16749d':
        raise ValueError('Exact predeclared original A15/B15 focus selections required')
    authority=core.read(core.REPORT/'full_n01_naming_names_v3/NAME_ANALYSIS_RECEIPT.json')
    index=core.verified(authority['index'])['rows']
    index=[r for r in index if r['candidate_id'] in {'C088','C091'}]
    if len(index)!=960 or len({(r['candidate_id'],r['case_id'],r['stream']) for r in index})!=960:
        raise ValueError('Exact all240/both-tap/original A15+B15 grid required')
    modes=['V0','V1','V2_single','V2_set','V2_all','V3']
    plan={'schema':'s6d-direction-replay-plan.v1','focus_selection_plan':core.bind(focus_plan_path),
        'prediction_index':authority['index'],'galleries':focus['galleries'],'selected_profile_ids':focus['selected_profile_ids'],
        'modes':modes,'prediction_cells':960,'physical_input_cells':480,'evaluation_step_sec':.1,
        'code':core.bind(__file__),'app_policy':core.bind(APP/'edge_speech_pipeline/research_s6d.py'),
        'telemetry_authority':core.bind(core.S6B/'INPUT_INDEX.json',core.INPUT_SHA),
        'contract':'Do not invent source support, beam/voice association or route IDs. Missing independent association stays unavailable, never a zero-error pass.',
        'scope':'Saved prediction/telemetry replay with host-aligned0.1sec ticks; not native, GUI, DSP or physical latency.',
        'truth_separation':'Runtime receives prediction and sanitized telemetry only. Support truth is read separately to score diagnostic exposure.',
        'missing_evidence_limit':'V0 arrow exposure is raw recent direction, not proof of current speaker or music rejection. V1 global mono gate needs real observation support. V2/V3 require independent matching stream/capture/route and speech/voice evidence links.'}
    core.save(output/'PLAN.json',plan)
    inputs=core.verified(plan['telemetry_authority'])['rows'];inputmap={(r['case_id'],r['stream']):r for r in inputs}
    scoremap=core.verified(authority['scorer_map']);qrows=core.verified(authority['Q'])['rows'];q={(r['case_id'],r['segment_index']):r for r in qrows}
    scenes={r['case_id']:r for r in core.verified(authority['bank'])['scenes']}
    rows=[];bindings={};started=time.perf_counter();telemetry_cache={}
    for i,item in enumerate(index):
        case=item['case_id'];tap=item['stream'];candidate=item['candidate_id'];inp=inputmap[case,tap]
        value=core.verified(item['result']);core.validate_payload(value,item)
        gallery=names.gallery_for(value,scoremap)
        if gallery['manifest']!=focus['galleries'][candidate]:raise ValueError('Original15 gallery substituted')
        if (case,tap) not in telemetry_cache:
            if core.bind(inp['telemetry']['path'])!=inp['telemetry']:raise ValueError('Sanitized telemetry changed')
            telemetry_cache[case,tap]=[json.loads(x) for x in Path(inp['telemetry']['path']).read_text().splitlines() if x.strip()]
        telemetry=sorted(telemetry_cache[case,tap],key=lambda r:(r['available_at_sec'],r.get('sequence',0)))
        bindings[case+'_'+tap]=inp['telemetry']
        support=core.verified(inp['support'])['support'];validate_support(scenes[case],support)
        turns=names.mapped_turns(value,support,q);profiles={r['profile_id']:r for r in gallery['profiles']}
        true_speech=union([r for t in turns for r in (t['active_ranges'] or [])])
        settings={m:S6DSettings(text_delivery=False,boundary_repair=False,direction_mode=m.split('_')[0],
            selected_profile_ids=tuple(focus['selected_profile_ids'][candidate][m.split('_')[1]]) if m.startswith('V2_') else ()) for m in modes}
        states={m:PresentationState(s) for m,s in settings.items()}
        counters={m:Counter() for m in modes};visible={m:[] for m in modes};reasons={m:Counter() for m in modes}
        segs=sorted(value['segmentation'],key=lambda r:r['available_at_sec'])
        identities=sorted([{**d,**d.get('identity',{}),'evidence_id':d.get('evidence_id')} for d in value['decisions']],key=lambda r:r['available_at_sec'])
        ti=si=ii=0;current=None;speech=[];voices=[];duration=inp['duration_sec']
        for step in range(math.ceil(duration/.1)):
            now=round(step*.1,8);end=min(duration,now+.1)
            while ti<len(telemetry) and telemetry[ti]['available_at_sec']<=now:
                current=telemetry[ti];ti+=1
            while si<len(segs) and segs[si]['available_at_sec']<=now:
                speech.append(segs[si]);si+=1
            while ii<len(identities) and identities[ii]['available_at_sec']<=now:
                voices.append(identities[ii]);ii+=1
            speech=[r for r in speech if now-r['available_at_sec']<=.75]
            voices=[r for r in voices if now-r['available_at_sec']<=2.]
            for mode,state in states.items():
                result=state.directions([current] if current else [],speech,voices,now)
                counters[mode]['ticks']+=1;counters[mode]['arrows']+=len(result['arrows'])
                if result['arrows']:
                    counters[mode]['ticks_with_arrow']+=1
                    visible[mode].append([round(now*16000),round(end*16000)])
                reasons[mode].update(r['reason'] for r in result['suppressed'])
        required=('source_start_sec','source_end_sec','capture_source_id','route_id','stream_id','speech_evidence_id','voice_evidence_id','association_verified','association_confidence')
        missing={k:sum(k not in r for r in telemetry) for k in required}
        association_available=bool(telemetry) and any(all(k in r for k in required) for r in telemetry)
        for mode in modes:
            spans=union(visible[mode]);on_speech=samples(intersection(spans,true_speech));allvisible=samples(spans)
            selected=settings[mode].selected_profile_ids
            target_people={profiles[pid]['metadata_identity'] for pid in selected}
            targets=union([r for t in turns if t['metadata_identity'] in target_people for r in (t['active_ranges'] or [])])
            rows.append({'candidate':candidate,'tap':tap,'case':case,'mode':mode,'duration_sec':duration,
                'telemetry_rows':len(telemetry),'telemetry_valid_angle_rows':sum(r.get('valid') is True and isinstance(r.get('angle_deg'),(int,float)) for r in telemetry),
                'independent_association_evidence_available':association_available,'missing_fields_json':json.dumps(missing,sort_keys=True),
                **dict(counters[mode]),'ticks_with_arrow':counters[mode]['ticks_with_arrow'],
                'suppression_reasons_json':json.dumps(reasons[mode],sort_keys=True),'reference_complete':support['all_speaker_reference_complete'],
                'arrow_exposure_sec':allvisible/16000,'arrow_exposure_during_referenced_speech_sec':on_speech/16000,
                'arrow_exposure_outside_referenced_speech_sec':(allvisible-on_speech)/16000,
                'outside_speech_classification':'non-speech by complete active-support reference' if support['all_speaker_reference_complete'] else 'unclassified: incomplete references',
                'selected_target_active_sec':samples(targets)/16000 if selected else None,
                'right_name_right_direction_coverage':None,'named_arrow_error_rate':None,
                'gate_status':'DIAGNOSTIC_ONLY' if mode=='V0' else 'UNAVAILABLE_ASSOCIATION_OR_SOURCE_SUPPORT' if not association_available else 'REPLAY_ONLY'})
        if (i+1)%120==0:print(json.dumps({'prediction_cells_completed':i+1,'elapsed_sec':time.perf_counter()-started}),flush=True)
    with (output/'PER_CASE.csv').open('x',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,list(rows[0]));writer.writeheader();writer.writerows(rows)
    groups=defaultdict(list)
    for row in rows:groups[row['candidate'],row['tap'],row['mode']].append(row)
    aggregate=[]
    for (candidate,tap,mode),group in sorted(groups.items()):
        aggregate.append({'candidate':candidate,'tap':tap,'mode':mode,'cases':len(group),
            'independent_association_available_cases':sum(r['independent_association_evidence_available'] for r in group),
            'ticks':sum(r['ticks'] for r in group),'ticks_with_arrow':sum(r['ticks_with_arrow'] for r in group),
            'arrow_exposure_sec':sum(r['arrow_exposure_sec'] for r in group),
            'outside_referenced_speech_complete_cases_sec':sum(r['arrow_exposure_outside_referenced_speech_sec'] for r in group if r['reference_complete']),
            'outside_reference_incomplete_cases_unclassified_sec':sum(r['arrow_exposure_outside_referenced_speech_sec'] for r in group if not r['reference_complete']),
            'named_direction_coverage':None,'named_direction_error_rate':None,'unavailable_is_not_pass':True})
    result={'schema':'s6d-direction-replay.v1','status':'COMPLETE_REPLAY_MISSING_ASSOCIATION_EVIDENCE','plan':core.bind(output/'PLAN.json'),
        'prediction_cells':len(index),'policy_cells':len(rows),'physical_input_cells':len(bindings),'telemetry_bindings':list(bindings.values()),
        'aggregate':aggregate,'per_case':core.bind(output/'PER_CASE.csv'),'elapsed_sec':time.perf_counter()-started,
        'neural_calls':0,'native_tested':False,'gui_tested':False,'physical_tested':False,'cm5_tested':False,
        'not_claimed':['No association = unavailable, not successful suppression accuracy.','No named beam coverage or music/overlap rejection qualification.','No measured GUI, hardware, DSP source timestamps or physical angular accuracy.']}
    core.save(output/'RESULT.json',result);print(json.dumps({'status':result['status'],'result':core.bind(output/'RESULT.json'),'elapsed_sec':result['elapsed_sec']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--focus-plan',type=Path,required=True)
    args=p.parse_args();run(args.output,args.focus_plan)
