"""Bounded S6D operational-width metadata/replay adapter; README_S6D_ANGLE_WIDTH_REPLAY.md."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

SIM=Path(__file__).resolve().parents[1]
S6C=SIM/'reports/S6C/20260910T123540Z'
WIDTHS=(2,5,10,20)
FAMILIES={'C079':'C065','C120':'C119'}
EXOGENOUS=('input','asr','segmentation','embedding','punctuation','runtime')


def utc():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def bind(path):
    path=Path(path).resolve();before=path.stat();h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('File changed while binding')
    return dict(path=str(path),bytes=after.st_size,sha256=h.hexdigest())


def verify(binding):
    actual=bind(binding['path'])
    if actual['sha256']!=binding['sha256'] or ('bytes' in binding and actual['bytes']!=binding['bytes']):raise ValueError('Binding changed: '+actual['path'])
    return actual


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
    return bind(path)


def prediction(binding):
    verify(binding);return json.loads(gzip.decompress(Path(binding['path']).read_bytes()))


def exogenous(profile):
    if profile['embedding']['cadence_policy']!='fixed' or profile['embedding']['cadence_cues_enabled'] or profile['xvf']['mode'] not in ('none','tracking_only'):
        raise ValueError('This bounded adapter forbids state-dependent neural or endpoint schedules')
    return digest({key:profile[key] for key in EXOGENOUS})


def width_profile(parent,candidate,width,tap):
    if candidate not in FAMILIES or width not in WIDTHS or tap not in ('O0','O1'):raise ValueError('Outside exact admitted neighborhood')
    if parent['tracker']['direction_match_deg']!=25. or parent['identity']['mode']!='none' or not parent['tracker']['cues_enabled'] or parent['xvf']['mode']!='tracking_only':
        raise ValueError('Wrong original real-cue anonymous parent')
    value=deepcopy(parent);value['tracker']['direction_match_deg']=float(width)
    value['profile_id']=f'S6D_{candidate}_W{width:02d}_{tap}_{tap}'
    back=deepcopy(value);back['profile_id']=parent['profile_id'];back['tracker']['direction_match_deg']=25.
    if back!=parent or exogenous(value)!=exogenous(parent):raise ValueError('A field beyond profile label/operational tracker width changed')
    return value


def words(value):
    return {key:[(str(row['utterance_index']),row['text']) for row in value[key]] for key in
        ('final_transcripts_first','final_transcripts_latest','final_transcripts_first_display')}


def prepare(output,payload):
    output=Path(output).resolve();payload=Path(payload).resolve()
    if not output.is_relative_to(SIM/'reports/S6D') or not payload.is_relative_to(Path('G:/Just_Peachy_S6D')):raise ValueError('Explicit new S6D roots required')
    if output.exists():raise ValueError('Preserve previous metadata epoch; choose a new child')
    output.mkdir(parents=True)
    authority=read(S6C/'full_n01_anonymous_core_v3/ANALYSIS_RECEIPT.json')
    verify(authority['index']);index=read(authority['index']['path']);verify(index['plan']);old_plan=read(index['plan']['path'])
    epochs=[]
    for b in old_plan['compatible_source_epochs']:
        verify(b);s=read(b['path'])
        if s['execution_digest']!=digest({key:s[key] for key in ('execution_files','assets','versions','state_policy')}):raise ValueError('Epoch graph digest mismatch')
        verify(s['effective_profile_registry'])
        if read(s['effective_profile_registry']['path'])['profiles']!=s['profiles']:raise ValueError('Effective profile registry mismatch')
        epochs.append((b,s))
    spec=next(s for b,s in epochs if Path(b['path']).name=='EPOCH4_EXECUTION_MANIFEST.json')
    app_root=Path(spec['root'])/'app'
    graph=[b for b in spec['execution_files'] if app_root in Path(b['path']).parents or Path(b['path']).name in ('s6c_replay.py','s6c_common.py','s6c_policy_matrix_v4.py')]
    for b in graph:verify(b)
    def app_map(s):
        root=Path(s['root'])/'app'
        return {str(Path(b['path']).relative_to(root)):b['sha256'] for b in s['execution_files'] if root in Path(b['path']).parents}
    for _,other in epochs:
        if app_map(other)!=app_map(spec):raise ValueError('Native source and parent application bytes differ')
        for key in ('assets','versions','python','input_index','scene_manifest','state_policy'):
            if other[key]!=spec[key]:raise ValueError('Cross-epoch authority differs: '+key)
        for name in ('s6c_execution.py','s6c_common.py'):
            get=lambda s:next(b['sha256'] for b in s['execution_files'] if Path(b['path']).name==name)
            if get(other)!=get(spec):raise ValueError('Complete native worker/common bytes differ')
    for b in old_plan['source_indices']:verify(b)
    native_rows=[r for b in old_plan['source_indices'] for r in read(b['path'])['rows']]
    native_bindings={r['receipt']['sha256']:r['receipt'] for r in native_rows if r['status'] in ('COMPLETE','COMPLETE_REUSED')}
    verify(spec['input_index']);inputs={(r['case_id'],r['stream']):r for r in read(spec['input_index']['path'])['rows']}
    cases=sorted({r[0] for r in inputs})
    if len(cases)!=240 or len(inputs)!=480:raise ValueError('Full 240 same-tap population required')
    parent_specs={(p['candidate_id'],p['asr_tap']):p for p in spec['profiles'] if p['candidate_id'] in set(FAMILIES)|set(FAMILIES.values())}
    controls={};sources={};populations={};parent_rows={}
    wanted=[r for r in index['rows'] if r['candidate_id'] in set(FAMILIES)|set(FAMILIES.values())]
    if len(wanted)!=1920:raise ValueError('Each parent and cue-off control requires 480 frozen cells')
    started=time.perf_counter()
    for n,row in enumerate(wanted,1):
        cid,tap,parent=row['case_id'],row['stream'],row['candidate_id'];value=prediction(row['result']);identity=value['identity']
        original=parent_specs[parent,tap];verify(original['profile_binding'])
        if identity['profile']!=original['profile'] or value['status']!='COMPLETE' or value['identity_tap']!=tap or identity['execution_digest']!=spec['execution_digest']:
            raise ValueError('Frozen parent metadata mismatch')
        source=identity['source'];verify(source)
        if source['sha256'] not in native_bindings:raise ValueError('Parent native source absent from original immutable index')
        receipt=read(source['path']);native_identity=receipt['identity']
        if receipt['status']!='COMPLETE' or receipt['job_key']!=digest(native_identity) or native_identity['execution_digest'] not in {s['execution_digest'] for _,s in epochs}:
            raise ValueError('Native receipt/epoch status mismatch')
        if native_identity['asr_audio']!=inputs[cid,tap]['audio'] or native_identity['identity_audio']!=inputs[cid,tap]['audio'] or exogenous(native_identity['profile'])!=exogenous(original['profile']):
            raise ValueError('Frozen waveform or neural dependency differs')
        if identity['gallery'] is not None or identity['gallery_condition']!='NONE' or identity['oracle_like']:raise ValueError('Anonymous real/off control scope only')
        if parent in FAMILIES:
            if identity['cue_condition']!='REAL_ALIGNED_CUES' or identity['telemetry']!=inputs[cid,tap]['telemetry']:raise ValueError('Only original real aligned cue file allowed')
            verify(identity['telemetry'])
            parent_rows[parent,cid,tap]=dict(parent_prediction=row['result'],source=source,telemetry=identity['telemetry'],audio=inputs[cid,tap]['audio'],
                duration_sec=inputs[cid,tap]['duration_sec'],raw_words_digest=digest(words(value)))
        elif identity['cue_condition']!='CUES_OFF' or identity['telemetry'] is not None:raise ValueError('Cue-off control differs')
        score_path=S6C/'full_n01_anonymous_core_v3/scores'/parent/cid/f'{tap}_ASR_{tap}_ID.json'
        score=read(score_path);populations.setdefault(cid,score['population'])
        if populations[cid]!=score['population']:raise ValueError('Population differs across fixed controls')
        controls[parent,cid,tap]=dict(candidate_id=parent,case_id=cid,stream=tap,result=row['result'],score=bind(score_path),population=score['population'],raw_words_digest=digest(words(value)))
        sources.setdefault(source['sha256'],dict(receipt=source,evidence=receipt['evidence'],vectors=receipt['vectors'],events=receipt['events'],summary=receipt['summary'],
            journal_bindings=receipt.get('journals',{}),native_execution_digest=native_identity['execution_digest'],neural_dependency_key=exogenous(native_identity['profile'])))
        if n%240==0:print(json.dumps(dict(status='PREPARING_METADATA_ONLY',verified_controls=n,total=1920,elapsed_sec=time.perf_counter()-started)),flush=True)
    profiles=[];cells=[];jobs=[]
    for parent in FAMILIES:
        for width in WIDTHS:
            candidate=f'S6D_{parent}_W{width:02d}'
            for tap in ('O0','O1'):
                original=parent_specs[parent,tap];profile=width_profile(original['profile'],parent,width,tap)
                pbind=save(output/'profiles'/candidate/f'{tap}_ASR_{tap}_ID.json',profile);job=candidate+'_'+tap
                profiles.append(dict(job_id=job,candidate_id=candidate,parent=parent,width_deg=width,stream=tap,identity_tap=tap,
                    profile=pbind,parent_profile=original['profile_binding'],neural_dependency_key=exogenous(profile),changes=['profile_id','tracker.direction_match_deg']))
                cell_ids=[]
                for cid in cases:
                    cell=job+'__'+cid;cell_ids.append(cell)
                    cells.append(dict(cell_id=cell,job_id=job,candidate_id=candidate,parent=parent,width_deg=width,case_id=cid,stream=tap,identity_tap=tap,
                        profile=pbind,population=populations[cid],**parent_rows[parent,cid,tap],cue_off_prediction=controls[FAMILIES[parent],cid,tap]['result'],
                        output_path=str(payload/candidate/cid/f'{tap}_{tap}.json.gz')))
                jobs.append(dict(job_id=job,cells=cell_ids,count=240))
    diagnostics=bind(S6C/'epoch4/full_n01_followups_v1_PREDICTION_INDEX.json')
    diagnostic_rows=[r for r in read(diagnostics['path'])['rows'] if r['candidate_id'] in {f'C{i}' for i in range(147,155)}]
    if len(diagnostic_rows)!=3840:raise ValueError('Frozen three-shuffle plus nominal controls missing')
    diagnostic_bind=save(output/'REUSED_DIAGNOSTICS.json',dict(index=diagnostics,rows=diagnostic_rows,new_jobs=0,
        mapping={'C079':['C147','C148','C149','C150'],'C120':['C151','C152','C153','C154']},scope='Existing 25-degree diagnostic context only; no new-width null grid'))
    plan=dict(schema='s6d-operational-width-plan.v1',status='PREDECLARED_METADATA_ONLY_NOT_EXECUTED',created_utc=utc(),
        output_root=str(output),payload_root=str(payload),new_conditions=8,new_cells=3840,new_neural_jobs=0,hardware_jobs=0,
        original_manual_reference_uncertainty_deg=5,retained_behavior_requires_native_confirmation=True,
        helper=bind(__file__),readme=bind(Path(__file__).with_name('README_S6D_ANGLE_WIDTH_REPLAY.md')),
        parent_index=authority['index'],parent_plan=index['plan'],parent_analysis=bind(S6C/'full_n01_anonymous_core_v3/ANALYSIS_RECEIPT.json'),
        source_epochs=[b for b,_ in epochs],frozen_application_root=str(app_root),frozen_script_root=str(Path(spec['root'])/'scripts'),executed_graph=graph,
        source_index_bindings=old_plan['source_indices'],model_asset_declarations=spec['assets'],models_loaded=False,
        sources=list(sources.values()),profiles=profiles,cells=cells,jobs=jobs,controls=list(controls.values()),reused_diagnostics=diagnostic_bind,
        population_case_counts=dict(Counter(populations.values())),case_ids=cases,
        scope='Only operational tracker width changes; manual labels and neural/waveform evidence unchanged. No scorer/ref-angle input reaches run_policy.',
        metadata_verification_scope='Parent prediction bytes, original source receipt bytes, profile/source graph and cue bytes verified. Native payload bytes are reverified by original load_evidence only upon separately admitted execution.')
    if len(cells)!=3840 or len({c['cell_id'] for c in cells})!=3840 or len(sources)!=480:raise ValueError('Exact declared matrix/source count mismatch')
    plan_bind=save(output/'PLAN.json',plan)
    return dict(status=plan['status'],plan=plan_bind,jobs=len(jobs),cells=len(cells),profiles=len(profiles),native_sources=len(sources),populations=plan['population_case_counts'],new_neural_jobs=0,hardware_jobs=0)


def execute(plan_path,authorization,jobs):
    plan_binding=bind(plan_path);plan=read(plan_path);auth=read(authorization)
    if plan['schema']!='s6d-operational-width-plan.v1' or auth.get('root_review_passed') is not True or auth.get('plan_sha256')!=plan_binding['sha256']:
        raise ValueError('Exact coordinator-admitted plan required')
    if not jobs or len(set(jobs))!=len(jobs) or not set(jobs)<=set(auth.get('allowed_jobs',[])) or not set(jobs)<={j['job_id'] for j in plan['jobs']}:
        raise ValueError('Only literal predeclared, coordinator-admitted job IDs may execute')
    for b in [plan['helper'],plan['readme']]+plan['executed_graph']+plan['source_epochs']:verify(b)
    if Path(plan['helper']['path']).resolve()!=Path(__file__).resolve():raise ValueError('Invoke exact reviewed helper')
    # Only execution imports the frozen policy API. No native/model worker is called.
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    sys.path.insert(0,plan['frozen_script_root']);sys.path.insert(0,plan['frozen_application_root'])
    from s6c_replay import load_evidence,run_policy,save_prediction
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    rows=sorted((r for r in plan['cells'] if r['job_id'] in jobs),key=lambda r:(r['case_id'],r['stream'],r['job_id']))
    report=Path(plan['output_root'])/'executions'/('jobs_'+digest(jobs)[:16]);report.mkdir(parents=True,exist_ok=False)
    save(report/'ADMISSION.json',dict(plan=plan_binding,authorization=bind(authorization),jobs=jobs,cells=len(rows)))
    output=[];cache={};last_route=None;started=time.perf_counter()
    for row in rows:
        target=Path(row['output_path']);payload_root=Path(plan['payload_root']).resolve()
        if not target.resolve().is_relative_to(payload_root) or target.exists():raise ValueError('Output escapes or overwrites the bound new payload root')
        route=(row['case_id'],row['stream'])
        if route!=last_route:cache={};last_route=route
        verify(row['profile']);profile_dict=read(row['profile']['path']);parent=prediction(row['parent_prediction'])
        expected=width_profile(parent['identity']['profile'],row['parent'],row['width_deg'],row['stream'])
        if profile_dict!=expected:raise ValueError('Unexpected numerical/profile change')
        if row['source']['sha256'] not in cache:
            receipt=read(row['source']['path']);evidence,vectors,_=load_evidence(row['source']['path'],receipt['identity']['execution_digest'],expected_receipt=row['source'])
            if evidence['identity']['asr_audio']!=row['audio'] or evidence['identity']['identity_audio']!=row['audio'] or exogenous(evidence['identity']['profile'])!=exogenous(profile_dict):raise ValueError('Exact frontend/route evidence mismatch')
            cache[row['source']['sha256']]=(evidence,vectors)
        evidence,vectors=cache[row['source']['sha256']];verify(row['telemetry'])
        value=run_policy(ResearchProfile.from_dict(profile_dict),JsonSpatialProvider(Path(row['telemetry']['path'])),evidence,vectors,gallery=None)
        if digest(words(value))!=row['raw_words_digest'] or words(value)!=words(parent):raise ValueError('Width replay changed fixed raw ASR word sequence')
        identity=dict(schema='s6d-operational-width-prediction.v1',plan=plan_binding,cell_id=row['cell_id'],source=row['source'],profile=profile_dict,
            telemetry=row['telemetry'],parent_prediction=row['parent_prediction'],neural_dependency_key=exogenous(profile_dict),gallery=None,oracle_like=False)
        value.update(status='COMPLETE',schema='jp_s6c_prediction.v1',prediction_key=digest(identity),identity=identity,case_id=row['case_id'],stream=row['stream'],
            identity_tap=row['identity_tap'],profile_id=row['candidate_id'],candidate_id=row['candidate_id'],recipe_id='N01',duration_sec=row['duration_sec'],
            execution_mode='FIXED_NATIVE_EVIDENCE_INCREMENTAL_POLICY_ONLY',oracle_like=False,created_utc=utc(),raw_ASR_words_equal_parent=True)
        saved=save_prediction(target,value);output.append(dict(candidate_id=row['candidate_id'],case_id=row['case_id'],stream=row['stream'],identity_tap=row['identity_tap'],status='COMPLETE',result=saved))
        save(report/'cells'/f"{row['cell_id']}.json",dict(cell=row,result=saved,raw_words_invariant=True))
        if len(output)%60==0:print(json.dumps(dict(status='POLICY_REPLAY_RUNNING',completed=len(output),requested=len(rows),new_neural_jobs=0,elapsed_sec=time.perf_counter()-started)),flush=True)
    for b in [plan['helper'],plan['readme']]+plan['executed_graph']:verify(b)
    result=dict(status='COMPLETE_ADMITTED_POLICY_REPLAY_ONLY',rows=output,completed=len(output),requested=len(rows),jobs=jobs,new_neural_jobs=0,hardware_jobs=0,scoring_complete=False,
        source_plan=bind(plan_path),elapsed_sec=time.perf_counter()-started,retained_behavior_requires_native_confirmation=True)
    result_bind=save(report/'PREDICTION_INDEX.json',result)
    return dict(status=result['status'],index=result_bind,completed=len(output),new_neural_jobs=0,hardware_jobs=0,scoring_complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--output',type=Path,required=True);prep.add_argument('--payload-root',type=Path,required=True)
    run=sub.add_parser('execute');run.add_argument('--plan',type=Path,required=True);run.add_argument('--authorization',type=Path,required=True);run.add_argument('--jobs',nargs='+',required=True)
    a=p.parse_args();answer=prepare(a.output,a.payload_root) if a.action=='prepare' else execute(a.plan,a.authorization,a.jobs)
    print(json.dumps(answer,indent=2),flush=True)
