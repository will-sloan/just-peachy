"""C-only qualification inputs and finite physical proposals; README_S6D_PHYSICAL_PREPARATION.md."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve
from s6d_capture_transport import PROFILES,timing,quantize,input_qa,mux_arguments
from s6d_capture_supervisor_bridge_v1 import binding,load,save,utc

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
BASE=SIM.parent
CAPTURE_OWNER_SHA='e5f0184f8fef95f173edad70cc666330bdb4da8176f87078fad97dff21c16c66'
RUNNER_SHA='3c0e5f71578f5fc6bbd34bddde42393912d878107f1b07d5c5edc0d2a258b1b3'
OWNER_V4_SHA='be4a03f729a1165e1b7bca66c12e511d710bf7c7ed095d7d4716084e74583524'
RATE=16000


def verify(b):return binding(b['path'],b['sha256'])


def audio(b,channels):
    verify(b);value,rate=sf.read(b['path'],dtype='float64',always_2d=True)
    if rate!=RATE or value.shape[1]!=channels or not np.isfinite(value).all():raise ValueError('Exact finite 16 kHz source channel contract failed')
    return value


def fingerprints(x):
    x=np.asarray(x)
    return [dict(index=i,frames=len(x),float32_pcm_sha256=hashlib.sha256(np.asarray(x[:,i],dtype='<f4').tobytes()).hexdigest(),
        peak_abs=float(np.max(np.abs(x[:,i]))) if len(x) else None,rms=float(np.sqrt(np.mean(x[:,i]**2))) if len(x) else None,
        nonzero_samples=int(np.count_nonzero(x[:,i]))) for i in range(x.shape[1])]


def tagged_input(c_render):
    x=np.zeros((8*RATE,4));rng=np.random.default_rng(38006201)
    # Independent signed even PCM24 codes in each physical MIC input; exact and
    # repeatable. Calibration speech follows at one common three-second origin.
    tags=rng.integers(-100000,100001,size=(RATE,4),dtype=np.int32)*2
    if 3*RATE+len(c_render)>len(x):raise ValueError('Whole C QA vector exceeds fixed source support')
    x[:RATE]=tags/2**23;x[3*RATE:3*RATE+len(c_render)]+=c_render
    return x


def firmware_evidence():
    from pypdf import PdfReader
    rows=[]
    for name in ('xvf3800_datasheet_v3.2.1.pdf','xvf3800_programming_guide_v3.2.1.pdf','xvf3800_user_guide_v3.2.1.pdf'):
        path=BASE/'reference_documents'/name;source=binding(path);hits=[];reader=PdfReader(path)
        for number,page in enumerate(reader.pages,1):
            text=page.extract_text() or ''
            for match in re.finditer(r'evaluat\w*|time.?limit|time.?out|\b\d+\s*(?:minutes?|hours?)\b',text,re.I):
                hits.append(dict(page=number,matched=match.group(),context=text[max(0,match.start()-180):min(len(text),match.end()+420)]))
        rows.append(dict(source=source,pages_searched=len(reader.pages),hits=hits))
    user_guide=rows[-1]
    exact_note=next((h for h in user_guide['hits'] if h['page']==6 and h['matched']=='8 hours' and 'stop processing audio after 8 hours of continuous use' in h['context']),None)
    if exact_note is None:raise ValueError('Reviewed local eight-hour evaluation note changed; do not infer a replacement limit')
    return dict(status='DOCUMENTED_EIGHT_HOUR_EVALUATION_LIMIT',sources=rows,limit_authority=dict(source=user_guide['source'],PDF_page=6,printed_page=2,section='2.1 Introduction',note=exact_note['context']),
        documented_firmware_limit_seconds=28800,continuous_source_seconds=900,continuous_carrier_seconds=904,
        continuous_conservative_playback_charge_seconds=904.3413125,
        playback_duration_below_documented_limit=True,pre_playback_reset_age_must_be_less_than_seconds=28800-904.3413125,
        uninterrupted_DSP_epoch_compliance='PENDING_ACTUAL_RESET_AND_CLOCK_EVIDENCE',admission_requirement='Root binds observed reset and readiness timestamps; entire uninterrupted DSP epoch must stay below28800s. Reset before each independent pass, never within either900s conversation.')


def write_input(directory,name,x,provenance):
    if x.ndim!=2 or x.shape[1]!=4 or not np.isfinite(x).all() or np.max(np.abs(x))>=1:raise ValueError('Candidate input headroom failed; no normalization is authorized')
    quantize(x) # Before writing, ensure the actual unchanged packed input can represent it.
    path=directory/(name+'.wav');sf.write(path,x,RATE,subtype='FLOAT')
    got,rate=sf.read(path,dtype='float32',always_2d=True)
    if rate!=RATE or not np.array_equal(got,x.astype(np.float32)):raise ValueError('FLOAT microphone file differs')
    return dict(input_id=name,audio=binding(path),source_seconds=len(x)/RATE,timing=timing(len(x)/RATE),
        fingerprints=fingerprints(got),provenance=provenance,headroom='PASS_UNITY_INPUT_NO_NORMALIZATION',source_gain=1.)


def prepare(output,payload_root):
    output=Path(output).resolve();payload_root=Path(payload_root).resolve()
    if not output.is_relative_to(R) or not payload_root.is_relative_to(Path('G:/Just_Peachy_S6D/20260913T195357Z')):raise ValueError('Explicit new run children required')
    if output.exists() or payload_root.exists():raise ValueError('Preserve prior preparation; use fresh roots')
    output.mkdir(parents=True);payload_root.mkdir(parents=True);input_dir=payload_root/'qualification_inputs';input_dir.mkdir()
    disk_observation=dict(C_free_bytes=shutil.disk_usage(R).free,G_free_bytes=shutil.disk_usage(payload_root).free,observed_utc=utc())
    disk_observation['hardware_admission_headroom_pass']=disk_observation['C_free_bytes']>=50*2**30 and disk_observation['G_free_bytes']>=75*2**30
    disk_observation['scope']='File-only build writes WAVs on G and small reports on C; frozen physical owner/runner C50/G75 floors remain unchanged and mandatory before hardware.'
    if disk_observation['C_free_bytes']<2**30 or disk_observation['G_free_bytes']<75*2**30:raise ValueError('Insufficient file-only preparation headroom')
    enrollment_path=R/'device_enrollment/DEVICE_ENROLLMENT_INPUT_PLAN_V1.json';enrollment=load(enrollment_path)
    bank_path=R/'listening/HARDWARE_CASE_PREDECLARATION_V1.json';bank=load(bank_path)
    budget_path=R/'device_enrollment/BUDGET_FORECAST_V1.json';budget=load(budget_path)
    material=load(verify(enrollment['authorities']['material'])['path']);sources={s['source_id']:s for s in material['accepted_sources']}
    selected=[]
    for person in enrollment['people']:
        chosen=person['C_calibration_candidates'][0];source=sources[chosen['source_id']]
        if source.get('s6c_role')!='C' or source.get('native_eligibility') is not True or source['identity']!=person['metadata_identity'] or source['decoded_16k_binding']!=chosen['decoded_16k_binding']:
            raise ValueError('Original disjoint C candidate identity/binding mismatch')
        dry=audio(chosen['decoded_16k_binding'],1)[:,0]
        if len(dry)!=chosen['samples']:raise ValueError('Complete C clip sample count differs')
        selected.append(dict(metadata_identity=person['metadata_identity'],roster=person['roster'],source_id=chosen['source_id'],role='C',
            audio=chosen['decoded_16k_binding'],source_samples=len(dry),transcript=source['transcript'],
            quality_disposition=source.get('quality_disposition',source.get('quality',{}).get('disposition')),
            quality=source.get('quality'),prompt_group=source['prompt_group'],native_prompt_key=source.get('native_prompt_key'),dry=dry))
    if len(selected)!=30 or len({s['source_id'] for s in selected})!=30:raise ValueError('One whole C clip per original actual roster person required')
    e_ids={u['source_id'] for person in enrollment['people'] for u in person['utterances']}
    q_ids={s['source_id'] for s in material['accepted_sources'] if s.get('s6c_role')=='Q'}
    if {s['source_id'] for s in selected}&(e_ids|q_ids):raise ValueError('C intersects E or Q source IDs')
    positions={p['position_id']:p for p in enrollment['positions']};rirs={k:audio(p['audio_verified']['binding'],4) for k,p in positions.items()}
    if set(rirs)!={'R04','R12'}:raise ValueError('Exact two compatible measured Library positions required')
    tail=max(len(h) for h in rirs.values())-1
    def render(dry,pos):return np.column_stack([fftconvolve(dry,rirs[pos][:,i],mode='full') for i in range(4)])
    A=next(s for s in selected if s['metadata_identity']=='CMU_ARCTIC_awb');B=next(s for s in selected if s['metadata_identity']=='CMU_ARCTIC_aew')
    rendered={(s['source_id'],pos):render(s['dry'],pos) for s in (A,B) for pos in rirs}
    def scene(seconds,events):
        x=np.zeros((round(seconds*RATE),4));records=[]
        for source,pos,onset in events:
            y=rendered[source['source_id'],pos];start=round(onset*RATE)
            if start+len(y)>len(x):raise ValueError('Full C source/RIR tail exceeds declared control')
            x[start:start+len(y)]+=y;records.append(dict(source_id=source['source_id'],role='C',metadata_identity=source['metadata_identity'],
                input_onset_sample=start,source_samples=source['source_samples'],convolution_stop_sample=start+len(y),position_id=pos,rir=positions[pos]['audio_verified']['binding'],gain=1.))
        return x,records
    scenes=load(verify(enrollment['authorities']['scenes'])['path'])['scenes'];music_scene=next(s for s in scenes if s['case_id']=='S45_12_03')
    if music_scene['cast'] or any(s['kind']!='real_noise' or s.get('speech_content')!='absent_documented' for s in music_scene['segments']):raise ValueError('Instrumental-only source is not documented nonspeech')
    if music_scene['receiver_configuration']!={k:positions['R04']['geometry'][k] for k in ('room_table','recorder_position','orientation','obstructed')}:raise ValueError('Music and C receiver configuration differs')
    music=audio(music_scene['canonical_audio'],4)[2*RATE:14*RATE]
    definitions=[('C_left_R04',12,[(A,'R04',1.)]),('C_right_R12',12,[(B,'R12',1.)]),
        ('same_C_two_paths',12,[(A,'R04',1.),(A,'R12',1.)]),('C_ABA',20,[(A,'R04',1.),(B,'R12',7.),(A,'R04',13.)]),
        ('C_overlap',12,[(A,'R04',1.),(B,'R12',1.)]),('C_overlap_source_swap',12,[(A,'R12',1.),(B,'R04',1.)]),
        ('C_relocate_in_silence',16,[(A,'R04',1.),(A,'R12',10.)]),('instrumental_only',12,[]),
        ('C_then_instrumental',20,[(A,'R04',1.)]),('digital_silence',8,[])]
    built={};control_ids=[]
    for name,seconds,events in definitions:
        x,records=scene(seconds,events)
        if name=='instrumental_only':x[:len(music)]+=music
        if name=='C_then_instrumental':x[5*RATE:5*RATE+len(music)]+=music
        provenance=dict(kind='C_ONLY_DERIVED_QUALIFICATION',events=records,rir_tail_retained=True,common_gain=1.,
            uncertainty='Original manual geometry remains +/-5 degrees; no device fixed-beam steering',
            mixture_limits='same_C_two_paths duplicates one waveform at two paths as an artificial correlated-input diagnostic, not two people')
        if 'instrumental' in name:provenance['music']=dict(canonical_source=music_scene['canonical_audio'],case_id='S45_12_03',copy_samples=[2*RATE,14*RATE],new_common_onset_sample=5*RATE if name=='C_then_instrumental' else 0,original_noise=music_scene['noise_details'])
        built[name]=write_input(input_dir,name,x,provenance);control_ids.append(name)
    sentinel=tagged_input(rendered[A['source_id'],'R04'])
    built['tagged_C_sentinel']=write_input(input_dir,'tagged_C_sentinel',sentinel,dict(kind='EXACT_MIC_TRANSPORT_TAGS_PLUS_WHOLE_C',
        tag_seed=38006201,tag_samples=[0,RATE],tag_definition='Four independent even PCM24 pseudorandom code vectors, common origin',
        C_source=A['audio'],C_source_id=A['source_id'],C_onset_sample=3*RATE,rir=positions['R04']['audio_verified']['binding'],MIC_output_columns=[2,3,4,5]))
    control_ids.append('tagged_C_sentinel')
    dry_parts=[];c_schedule=[];offset=0
    for i,s in enumerate(selected):
        if i:dry_parts.append(np.zeros(RATE//2));offset+=RATE//2
        c_schedule.append(dict(source_id=s['source_id'],role='C',metadata_identity=s['metadata_identity'],start_sample=offset,stop_sample=offset+s['source_samples'],audio=s['audio'],gain=1.))
        dry_parts.append(s['dry']);offset+=s['source_samples']
    dry=np.concatenate(dry_parts)
    for pos in rirs:
        x=render(dry,pos);x=np.pad(x,((0,len(dry)+tail-len(x)),(0,0)))
        built['C30_calibration_'+pos]=write_input(input_dir,'C30_calibration_'+pos,x,dict(kind='DEDICATED_WHOLE_C_GAIN_AND_MULTIBEAM_CALIBRATION',
            sources=c_schedule,position_id=pos,rir=positions[pos]['audio_verified']['binding'],common_tail_samples=tail,
            selection='First already declared C candidate for every original actual A15/B15 person; no E/Q outcome selection',
            model_gain_policy_status='RAW_UNITY_ONLY; host per-tap calibration proposal requires review after capture; original O0+3 adapter remains distinct'))
    raw_controls=[]
    def attempt(aid,case,profile,role='qualification',rates=None):
        value=built[case]
        return dict(attempt_id=aid,case_id=case,profile=profile,role=role,reset_before=True,duration_sec=value['source_seconds'],source_audio=value['audio'],
            payload_expectation='silence' if case=='digital_silence' else 'nonzero',required_nonzero_streams=[] if case=='digital_silence' else ['auto_asr_raw','auto_pp_raw'],
            telemetry_rates=rates or dict(fast_hz=20.,gain_hz=2.,slow_hz=.2),timing=value['timing'],stream_identity_qualification='PENDING_ACTUAL_QUALIFICATION')
    qualification_batches=[]
    for profile in ('P_MAIN6','P_SCAN6'):
        suffix='MAIN' if profile=='P_MAIN6' else 'SCAN';rows=[]
        rows.append(attempt('QA_QUAL_'+suffix+'_PRE','tagged_C_sentinel','P_INPUT_QA6'))
        for i,case in enumerate(control_ids):
            rows.append(attempt(f'QUAL_{suffix}_{i+1:02d}',case,profile))
            if profile=='P_MAIN6' and i==0:
                # First expanded capture above followed by S,S,E => fixed ABBA.
                for j,expanded in enumerate((False,False,True),1):rows.append(attempt(f'OBSERVER_MAIN_{j}',case,profile,
                    rates=dict(fast_hz=20.,gain_hz=2. if expanded else 0.,slow_hz=.2 if expanded else 0.)))
        for pos in rirs:rows.append(attempt(f'C_CAL_{suffix}_{pos}','C30_calibration_'+pos,profile))
        rows.append(attempt('QA_QUAL_'+suffix+'_POST','tagged_C_sentinel','P_INPUT_QA6'))
        raw_controls.extend(rows);qualification_batches.append(dict(batch_id='qualification_'+suffix.lower()+'_v1',profile=profile,attempt_ids=[x['attempt_id'] for x in rows],scope='QUALIFICATION_ONLY_REVIEW_BEFORE_BANK'))
    planned_groups=[]
    for profile,case_ids,size in (('P_MAIN6',bank['P_MAIN6']['case_ids'],30),('P_SCAN6',bank['P_SCAN6']['case_ids'],12)):
        for start in range(0,len(case_ids),size):planned_groups.append(dict(batch_id=profile+'_B'+str(start//size+1),profile=profile,source_case_ids=case_ids[start:start+size],QA_before=1,QA_after=1))
    for i in range(6):planned_groups.append(dict(batch_id='E_MAIN_B'+str(i+1),profile='P_MAIN6',enrollment_pass_ids=[p['planned_pass_id'] for p in enrollment['planned_passes'][i*10:i*10+10]],QA_before=1,QA_after=1))
    continuous=load(R/'device_enrollment/CONTINUOUS_INPUT_PLAN_V1.json')
    for session in continuous['sessions']:planned_groups.append(dict(batch_id=session['session_id'],profile='P_MAIN6',continuous_session_id=session['session_id'],continuous_seconds=900,QA_before=1,QA_after=1))
    # Four same-profile repeat takes are included in the matching scan batch,
    # not four additional profile changes/QA groups.
    for repeat in bank['matched_repeats']:
        group=next(g for g in planned_groups if g['profile']=='P_SCAN6' and repeat['case_id'] in g.get('source_case_ids',[]));group.setdefault('matched_repeat_cases',[]).append(repeat['case_id'])
    scene_by_id={s['case_id']:s for s in scenes}
    for group in planned_groups:
        if 'source_case_ids' in group:group['canonical_source_bindings']=[dict(case_id=case,source_audio=scene_by_id[case]['canonical_audio']) for case in group['source_case_ids']]
    qa_count=2*(len(planned_groups)+len(qualification_batches));qa_seconds=qa_count*timing(8)['charged_playback_seconds']
    extra=[r for r in raw_controls if r['profile']!='P_INPUT_QA6'];extra_seconds=sum(r['timing']['charged_playback_seconds'] for r in extra)
    base=budget['required_total'];total_attempts=base['attempts']+len(extra)+qa_count;total_seconds=base['charged_playback_seconds']+extra_seconds+qa_seconds
    reserve_attempts=24+8;reserve_seconds=24*timing(45)['charged_playback_seconds']+8*timing(8)['charged_playback_seconds']
    if total_attempts+reserve_attempts>480 or total_seconds+reserve_seconds>21600:raise ValueError('Mandatory scope plus explicit hypothesis/QA reserve exceeds authorized budget')
    forecast=dict(schema='s6d-physical-qualification-budget.v1',actual_ledger_present=(R/'physical_ledger.json').exists(),actual_consumed_attempts=0 if not (R/'physical_ledger.json').exists() else len(load(R/'physical_ledger.json')['passes']),
        original_base=base,qualification_acoustic_calibration_observer_attempts=len(extra),qualification_charged_seconds=extra_seconds,
        all_pre_post_QA_attempts=qa_count,all_QA_charged_seconds=qa_seconds,base_and_exact_qualification_QA_attempts=total_attempts,base_and_exact_qualification_QA_seconds=total_seconds,
        optional_hypothesis_reserve=dict(passes=24,maximum_source_seconds_each=45,max_profile_or_recipe_groups=4,additional_QA=8,charged_seconds=reserve_seconds,scheduled=False),
        including_optional_reserve=dict(attempts=total_attempts+reserve_attempts,charged_seconds=total_seconds+reserve_seconds,remaining_attempts=480-total_attempts-reserve_attempts,remaining_seconds=21600-total_seconds-reserve_seconds),
        note='A forecast is not consumption. Every actual failed/partial pass, unexpected setting-change QA or retry must be charged by owner. No automatic retry or optional-job launch.')
    level_path=output/'AUDIO_ACCEPTANCE_POLICY_PROPOSAL.json';save(level_path,dict(schema='s6d-audio-acceptance.v1',raw_gain=1.,max_rail_samples_per_stream=0,rail_exceedance_action='LIMITED',missing_required_payload_action='LIMITED'),True)
    owner=verify(dict(path=str(SIM/'scripts/s6d_capture_owner_v4.py'),sha256=OWNER_V4_SHA));runner=verify(dict(path=str(R/'runner/source_epoch_ready_v3/s6d_runner_v1.py'),sha256=RUNNER_SHA))
    plan=dict(schema='s6d-capture-plan-proposal.v1',status='INPUTS_PREPARED_SAFETY_AND_ROOT_ADMISSION_PENDING',report_root=str(R),payload_root=str(payload_root/'captures'),
        limits=dict(attempts=480,charged_playback_seconds=21600,payload_bytes=40*2**30),safety=None,
        preparation_disk_observation=disk_observation,
        baseline=binding(SIM/'reports/S4_5/20260909T031300Z/HARDWARE_BASELINE.json'),output_level_policy=binding(SIM/'reports/S4_5/20260909T031300Z/OUTPUT_LEVEL_POLICY.json'),
        initialization_policy=binding(SIM/'reports/S4_5/20260909T031300Z/INITIALIZATION_POLICY.json'),audio_acceptance_policy=binding(level_path),
        attempts=raw_controls,qualification_batches=qualification_batches,owner=owner,
        route_contract={name:dict(logical_streams=rows,mux_api_arguments=mux_arguments(name)) for name,rows in PROFILES.items()},
        prerequisites=['Fresh XVF-own analog-output setup acknowledgement','Root creates exact capture v1 plan with that real safety binding','Root reviews qualification source/queue/protocol and creates authorization','No bank launch before actual qualification review'],
        no_execution_authorization_created=True)
    save(output/'CAPTURE_PLAN_PROPOSAL.json',plan,True);save(output/'BUDGET_FORECAST.json',forecast,True)
    save(output/'CAMPAIGN_BATCH_PROPOSAL.json',dict(base_authority=binding(bank_path),enrollment_authority=binding(enrollment_path),continuous_authority=binding(R/'device_enrollment/CONTINUOUS_INPUT_PLAN_V1.json'),
        groups=planned_groups,qualification_groups=qualification_batches,total_profile_groups=len(planned_groups)+len(qualification_batches),QA_per_group=2,
        QA_input=built['tagged_C_sentinel'],QA_semantics='Exact own-pass tagged MIC+whole-C check before/after each profile batch. Does not prove samples in intervening processed-only captures.',
        additional_change_rule='Any added profile/recipe group requires one pre and one post QA, reforecast and charged owner attempts; QA profile itself does not recurse into more QA.'),True)
    save(output/'FIRMWARE_DURATION_EVIDENCE.json',firmware_evidence(),True)
    analysis=dict(schema='s6d-qualification-analysis-contract.v1',status='PREDECLARED_BEFORE_ANY_PHYSICAL_CAPTURE',
        route_checks=dict(profiles=plan['route_contract'],ASR_channel_count=1,readback_matches_exact_mux=True,
            native_framing_errors_allowed=0,callback_status_flags_allowed=0,source_under_or_overflow_allowed=0,
            QA=dict(columns=[2,3,4,5],payload_mismatches_allowed=0,one_common_offset_only=True,all_nonzero_source_required=True,
                unique_tag_required=True,meaning='Exact route/microphone samples in each own QA pass only. MAIN and SCAN contain no exact MIC echoes.'),
            fingerprints='Hash every decoded stream, equality matrix and configuration per same-input MAIN/SCAN controls. Duplicated processed beams may be genuine; tags/mux/source-swap evidence distinguish a failure. No forced eight-channel same-pass reconstruction.',
            physical_duplicate_route_test='NOT_SCHEDULED: frozen V3 accepts exactly three valid profiles; deliberately duplicate-route corruption is exercised in model-free fixtures only.'),
        level_checks=dict(policy=binding(level_path),raw_gain=1.,rails='Any rail marks affected original stream LIMITED, retained unchanged',
            silent_focus='May be true gating; do not label it dropped transport solely for zero payload',
            gain_selection='Dedicated original C30 captures only; raw ASR remains unity, original O0+3 host adapter once remains distinct. Host per-tap scale requires a separately reviewed C-only recipe, no Q-dependent retuning.'),
        latency_tail=dict(source_guard_policy=timing(900),QA_common_offset='Measure from unique common four-MIC anchor including pre-roll; no per-channel alignment',
            processed='Common-lag/source-support and tagged onset/last-active-event diagnostics; no exact processed-source reconstruction claim. Do not shift saved audio or silently trim a tail.',
            acceptance='Root must review measured processed lag and last-source activity against the 3 s post-guard; failed or unidentifiable tails stay explicit. A transport PASS alone is insufficient.',
            continuous='Each original 900 s source remains one 904 s guarded carrier with no internal reset; interrupted/failed long pass consumes its charged attempt and is not a continuous success.'),
        observer=dict(order=['EXPANDED','STANDARD_FAST_ONLY','STANDARD_FAST_ONLY','EXPANDED'],attempt_ids=['QUAL_MAIN_01','OBSERVER_MAIN_1','OBSERVER_MAIN_2','OBSERVER_MAIN_3'],
            identical_input=built['C_left_R04']['audio'],settings='Same frozen recipe, reset before each independent pass, identical guards; only gain/slow telemetry rates differ',
            expanded_rates=dict(fast_hz=20.,gain_hz=2.,slow_hz=.2),standard_rates=dict(fast_hz=20.,gain_hz=0.,slow_hz=0.),
            comparisons=['Both within-condition repeat pairs and all four across-condition pairs, fixed before capture',
                'Exact callback/framing/source-progress and stream rails; per-field valid/null counts, gaps, achieved rates, drain/degradation and pending-read closure',
                'Single shared lag across first four streams, each correlation and RMS ratio; no fitted gain or independent warping'],
            descriptive_review_flags=dict(correlation_below=.90,absolute_rms_difference_db_above=3.,lag_search_boundary_samples=16000,
                fast_rate_below_hz=18.,fast_gap_above_seconds=.20,required_fast_invalid_values_above=0),
            limits='Thresholds trigger explicit root review, not statistical proof of equivalence. Supplemental unavailable/degraded fields remain explicit and must not be silently substituted.'),
        MAIN_SCAN_pairing=dict(control_ids=control_ids,compare_first_four_only=True,source_bindings_exact=True,other_two_streams='Profile-specific logical routes, separate physical passes',
            interpretation='Reset and guards do not establish identical hidden adaptation. Report pair agreement/differences without claiming simultaneous eight-output acquisition.'),
        scientific_acceptance='No bank admission until actual sentinel, stream identity, latency/tail and observer evidence is reviewed. No model/score/angle labels enter this qualification.')
    save(output/'QUALIFICATION_ANALYSIS_CONTRACT.json',analysis,True)
    bridge=binding(SIM/'scripts/s6d_capture_supervisor_bridge_v1.py')
    # A withheld proposal intentionally omits runnable queue/capture authority.
    queue_stages=[]
    for qbatch in qualification_batches:
        chunks=[('pre_QA',[qbatch['attempt_ids'][0]]),('controls_and_C',qbatch['attempt_ids'][1:-1]),('post_QA',[qbatch['attempt_ids'][-1]])]
        for phase,ids in chunks:
            job_id=qbatch['batch_id']+'_'+phase;folder=R/'physical_supervisor'/job_id;selected_rows=[a for a in raw_controls if a['attempt_id'] in ids]
            queue_stages.append(dict(job_id=job_id,fresh_owner_batch=job_id,phase=phase,attempt_ids=ids,kind='hardware',workload='sensitive',allow_owned_termination=False,
                argv_ready_prefix=['C:/Users/amiri/anaconda3/python.exe',bridge['path'],'--owner',owner['path'],'--owner-sha256',owner['sha256']],
                argv_missing_root_bound_arguments=['--plan','--plan-sha256','--authorization','--authorization-sha256'],
                argv_ready_suffix=['--batch',job_id,'--attempt-ids']+ids,cwd=str(SIM),source_bindings=[bridge,owner],
                heartbeat_path=str(folder/'HEARTBEAT.json'),completion_path=str(folder/'COMPLETE.json'),stop_request_path=str(folder/'STOP_REQUEST.json'),restoration_path=str(folder/'RESTORATION.json'),
                timeout_s=math.ceil(sum(a['timing']['charged_playback_seconds']+120 for a in selected_rows)+180),stall_after_s=120,heartbeat_stale_s=30,stop_grace_s=90,
                expected_artifacts=[dict(path=str(folder/'COMPLETE.json'),format='json',min_bytes=1,expected_fields={'status':'COMPLETE','capture_same_process':True,'protocol_observer_closed':True,'semantic_checks.attempt_count':len(ids)}),
                    dict(path=str(folder/'RESTORATION.json'),format='json',min_bytes=1,expected_fields={'status':'RESTORED','verified':True})],
                root_review_before_next_stage=True,charged_playback_seconds=sum(a['timing']['charged_playback_seconds'] for a in selected_rows)))
    save(output/'SUPERVISOR_QUEUE_PROPOSAL.json',dict(schema='s6d-hardware-queue-proposal.v1',status='WITHHELD_NO_EXECUTION_AUTHORITY',reviewed_runner=runner,
        owner=owner,bridge=bridge,proposed_stages=queue_stages,first_admission='Only first pre-QA sentinel, after root safety/firmware/plan/queue review',
        repeated_source_checks='Root includes complete V3 frozen source graph plus bridge and adopted small input documents in each literal queue job, within existing runner size caps',
        global_payload_monitor_root='G:/Just_Peachy_S6D/20260913T195357Z',no_execution_authorization_created=True),True)
    save(output/'ADMISSION_REQUIREMENTS.json',dict(status='PENDING_REAL_SAFETY_AND_ROOT_REVIEW',requirements=[
        'Actual fresh XVF-own analog output acknowledgement; PC playback/monitor devices are outside that wording',
        'Root resolves local firmware duration audit and documents any remaining unknown limitation before long-pass admission',
        'Root adopts exact schema s6d-capture-plan.v1 with real safety binding and explicit unchanged accepted DSP recipe; source/headroom bindings rechecked',
        'Fresh literal batch IDs, exact source graph, inherited baseline/init/output policy and audio-level policy; no unresolved prior STARTED/restoration ownership',
        'Root creates separate capture authorization and reviewed hardware queue/approval only after pure validation; proposals are never authorization',
        'Global remaining480 attempts/21600 charged seconds and all-new-payload40 GiB headroom incl prepared inputs, failed work and optional QA; fresh C>=50/G>=75 GiB required before physical admission',
        'Runner cooperative stop/heartbeat/completion path predicates; no owned hardware process termination; restoration must be actual and bound',
        'Stage first pre-QA, review actual integrity, then admit named qualification/observer/C controls; review before canonical/enrollment/continuous batches'],
        preparation_disk_observation=disk_observation,actual_hardware_calls=0,no_execution_authorization_created=True),True)
    source_epoch=output/'source_epoch';source_epoch.mkdir()
    small=[Path(__file__),SIM/'scripts/s6d_capture_supervisor_bridge_v1.py',SIM/'scripts/s6d_qualification_diagnostics_v1.py',SIM/'scripts/s6d_physical_prepare_checks_v1.py',SIM/'scripts/README_S6D_PHYSICAL_PREPARATION.md',
        SIM/'scripts/s6d_capture_owner_v4.py',SIM/'scripts/s6d_capture_checks_v4.py',SIM/'scripts/README_S6D_CAPTURE_V4.md']
    for path in small:shutil.copy2(path,source_epoch/path.name)
    source_bindings=[binding(p) for p in small]+[owner,runner,binding(SIM/'scripts/s6d_capture_transport.py')]
    save(output/'PREPARATION_RESULT.json',dict(status='PREPARED_NOT_EXECUTED',inputs=list(built.values()),C_sources=[{k:v for k,v in s.items() if k!='dry'} for s in selected],
        authorities=dict(enrollment=binding(enrollment_path),bank=binding(bank_path),material=enrollment['authorities']['material'],geometry_positions=enrollment['positions'],capture_freeze=binding(R/'capture_implementation/review_v3/SOURCE_FREEZE.json')),
        source_bindings=source_bindings,forecast=forecast,input_payload_bytes=sum(p.stat().st_size for p in input_dir.iterdir()),hardware_calls=0,model_calls=0,audio_streams_opened=0),True)
    return dict(status='PREPARED_NOT_EXECUTED',output=str(output),microphone_input_files=len(built),qualification_plan_attempts=len(raw_controls),all_QA_attempts=qa_count,
        budget_including_optional_reserve=forecast['including_optional_reserve'],hardware_calls=0,model_calls=0,audio_streams_opened=0)


def freeze_review(preparation,output,checks_path):
    """Additive reviewed bridge epoch; never regenerate or change prepared WAVs."""
    preparation=Path(preparation).resolve();output=Path(output).resolve()
    if not preparation.is_relative_to(R) or not output.is_relative_to(R) or output.exists():raise ValueError('Existing run preparation and fresh review child required')
    result_path=preparation/'PREPARATION_RESULT.json';result=load(result_path);checks=load(checks_path)
    if checks.get('status')!='PASS_MODEL_FREE' or checks.get('prepared_file_checks',{}).get('prepared_result')!=binding(result_path):raise ValueError('Checks must bind these actual prepared inputs')
    if not all(checks['checks'].values()) or not all(checks['prepared_file_checks']['checks'].values()):raise ValueError('Unresolved fixture failure')
    for row in result['inputs']:verify(row['audio'])
    material=load(verify(result['authorities']['material'])['path']);q_binding=verify(material['query_manifest']);q_rows=load(q_binding['path'])['rows']
    c_ids={r['source_id'] for r in result['C_sources']};c_rows=[r for r in material['accepted_sources'] if r['source_id'] in c_ids];e_rows=[r for r in material['accepted_sources'] if r['s6c_role']=='E']
    if len(c_rows)!=30 or any(r['s6c_role']!='C' for r in c_rows):raise ValueError('Original C partition identity mismatch')
    dimensions={'source_id':lambda r:r['source_id'],'original_sha256':lambda r:r['source_binding']['sha256'],
        'decoded_pcm_sha256':lambda r:r['decoded_pcm_sha256'],'prompt_group':lambda r:r['prompt_group'],'native_prompt_key':lambda r:r.get('native_prompt_key')}
    intersections={}
    for name,key in dimensions.items():
        c={key(r) for r in c_rows if key(r)}
        for label,other in (('E',e_rows),('Q',q_rows)):intersections['C_'+label+'_'+name]=sorted(c&{key(r) for r in other if key(r)})
    if any(intersections.values()):raise ValueError('Selected calibration source/bytes/prompt partition overlaps E or Q')
    output.mkdir(parents=True);source_epoch=output/'source_epoch';source_epoch.mkdir()
    small=[Path(__file__),SIM/'scripts/s6d_capture_supervisor_bridge_v1.py',SIM/'scripts/s6d_qualification_diagnostics_v1.py',SIM/'scripts/s6d_physical_prepare_checks_v1.py',SIM/'scripts/README_S6D_PHYSICAL_PREPARATION.md',
        SIM/'scripts/s6d_capture_owner_v4.py',SIM/'scripts/s6d_capture_checks_v4.py',SIM/'scripts/README_S6D_CAPTURE_V4.md']
    for p in small:shutil.copy2(p,source_epoch/p.name)
    bridge=binding(small[1]);owner=verify(dict(path=str(SIM/'scripts/s6d_capture_owner_v4.py'),sha256=OWNER_V4_SHA))
    runner=verify(dict(path=str(R/'runner/source_epoch_ready_v3/s6d_runner_v1.py'),sha256=RUNNER_SHA))
    runner_review=verify(dict(path=str(R/'runner/independent_runner_write_review_v1/INDEPENDENT_RUNNER_WRITE_REVIEW_V3_FINAL.json'),sha256='2c99fe91cf43709bff2826241bf53fce9df9cf0c45d562e4db0a6938b91968be'))
    owner_checks_path=R/'capture_owner_v4_checks_v2.json';owner_checks=load(owner_checks_path)
    if owner_checks['passed']!=48 or not all(owner_checks['checks'].values()):raise ValueError('V4 source/event fixtures required')
    for b in owner_checks['sources']:verify(b)
    queue=load(preparation/'SUPERVISOR_QUEUE_PROPOSAL.json');queue.update(bridge=bridge,owner=owner,reviewed_runner=runner,runner_source_review=runner_review)
    for stage in queue['proposed_stages']:
        stage['argv_ready_prefix'][1]=bridge['path'];stage['argv_ready_prefix'][3]=owner['path'];stage['argv_ready_prefix'][5]=owner['sha256'];stage['source_bindings']=[bridge,owner]
    queue['supersedes_proposal']=binding(preparation/'SUPERVISOR_QUEUE_PROPOSAL.json');queue['change']='Reviewed runnerV3 plus pending-root-review additive ownerV4 explicit stop event, atomic bridge retry/final STOP checks. Original captureV3 and input WAVs unchanged.'
    save(output/'SUPERVISOR_QUEUE_PROPOSAL.json',queue,True)
    capture_proposal=load(preparation/'CAPTURE_PLAN_PROPOSAL.json');capture_proposal.update(owner=owner,supervisor_bridge=bridge,owner_V4_source_review='PENDING_ROOT_REVIEW',supersedes_proposal=binding(preparation/'CAPTURE_PLAN_PROPOSAL.json'))
    save(output/'CAPTURE_PLAN_PROPOSAL.json',capture_proposal,True)
    calibration_inputs=[r for r in result['inputs'] if r['input_id'].startswith('C30_calibration_')]
    partition=dict(schema_version='edge-s6d-beam-calibration-partition.v1',status='PARTITION_BOUND_SCORING_PENDING',partition='C',Q_used=False,disjoint_from_E_Q_verified=True,
        preparation=binding(result_path),material=result['authorities']['material'],Q_occurrence_authority=q_binding,C_source_ids=sorted(c_ids),
        original_E_source_count=len(e_rows),Q_occurrence_count=len(q_rows),checked_intersections=intersections,
        inherited_leakage_audit=material['leakage_audit'],sources=c_rows,
        calibration_input_cases=[dict(case_id=r['input_id'],source_audio=r['audio'],source_seconds=r['source_seconds'],C_source_spans=r['provenance']['sources'],
            profile_attempts=[dict(profile=profile,attempt_id='C_CAL_'+('MAIN' if profile=='P_MAIN6' else 'SCAN')+'_'+r['provenance']['position_id']) for profile in ('P_MAIN6','P_SCAN6')],
            guard=r['timing'],acquired_streams=None) for r in calibration_inputs],
        acquisition_status='NOT_CAPTURED',accepted_case_results=[],physical_attempts=4,charged_playback_seconds=sum(r['timing']['charged_playback_seconds']*2 for r in calibration_inputs),
        additional_already_budgeted_C_control_panel=[dict(case_id=r['input_id'],source_audio=r['audio'],events=r['provenance']['events'],profiles=['P_MAIN6','P_SCAN6'],
            capture_status='NOT_CAPTURED',scope='Narrow2person/same-waveform C-only control; not population efficacy and no new scheduled passes') for r in result['inputs'] if r['input_id'] in ('same_C_two_paths','C_ABA','C_overlap','C_overlap_source_swap')],
        duplicate_resolution=dict(enabled=False,admission='Default disabled; requires adequate actual C competition/duplicate evidence and independently bound duplicate-specific thresholds before enablement'),
        later_calibration_receipt=dict(schema_version='edge-s6d-beam-calibration.v1',required_status='ACCEPTED_C_ONLY',
            must_bind=['Original exact gallery manifest for actual roster/tap mapping from RESEARCH_GALLERY_INDEX','Exact v3 application profile/model/window digest','capture_profile','identity_streams','selected_profile_ids','This partition proof','Actual captured stream hashes'],
            required_thresholds=['minimum_selected_score','minimum_selected_margin','minimum_beam_margin','minimum_auto_correlation','minimum_auto_margin','duplicate_waveform_correlation','duplicate_voice_cosine','continuity_bonus'],
            continuity_bonus_must_not_exceed='minimum_beam_margin',threshold_values=None),
        scoring_constraints=['Fixed separately admitted model/galleries; no new weights or Q-dependent selection','One continuous auto tap plus at most focus0/focus1 identity streams; bind opportunity count',
            'Waveform comparison uses same source span with no alignment search; qualification common-lag diagnostic is never a selector calibration input',
            'Duplicate requires same profile/span/waveform/voice evidence; no missing C evidence imputation; abstain when positive/negative/duplicate support is absent'],
        scope='One whole C clip/person at two measured positions is a narrow calibration set, not population efficacy. No score/model call or accepted thresholds produced.')
    save(output/'C_CALIBRATION_PARTITION.json',partition,True)
    source_bindings=[dict(**binding(p),snapshot=binding(source_epoch/p.name)) for p in small]
    stable=load(R/'capture_implementation/review_v3/SOURCE_FREEZE.json')
    for source in stable['sources']:verify(source)
    freeze=dict(schema='s6d-physical-preparation-review-freeze.v1',status='CODE_AND_INPUTS_READY_FOR_ROOT_REVIEW_NO_HARDWARE_AUTHORITY',
        preparation=binding(result_path),frozen_capture_v3=binding(R/'capture_implementation/review_v3/SOURCE_FREEZE.json'),historical_capture_owner_V3=verify(dict(path=str(SIM/'scripts/s6d_capture_owner.py'),sha256=CAPTURE_OWNER_SHA)),capture_owner_V4=owner,
        owner_V4_fixtures=binding(owner_checks_path),owner_V4_checks_passed=owner_checks['passed'],reviewed_runner=runner,runner_review=runner_review,
        additive_sources=source_bindings,fixtures=binding(checks_path),synthetic_checks_passed=checks['passed'],actual_prepared_file_checks_passed=checks['prepared_file_checks']['passed'],
        proposal_queue=binding(output/'SUPERVISOR_QUEUE_PROPOSAL.json'),capture_proposal=binding(output/'CAPTURE_PLAN_PROPOSAL.json'),C_partition=binding(output/'C_CALIBRATION_PARTITION.json'),
        plans=[binding(preparation/name) for name in ('CAPTURE_PLAN_PROPOSAL.json','CAMPAIGN_BATCH_PROPOSAL.json','BUDGET_FORECAST.json','QUALIFICATION_ANALYSIS_CONTRACT.json','ADMISSION_REQUIREMENTS.json','FIRMWARE_DURATION_EVIDENCE.json')],
        original_inputs_unchanged=True,hardware_calls=0,vendor_DLL_calls=0,model_calls=0,audio_streams_opened=0,no_execution_authorization_created=True,
        supersession='Prepared-input source epoch and V3 preserved. Latest withheld proposals use source-reviewed runnerV3 and pending-root-reviewed additive ownerV4/bridge. Existing inputs, profiles, budgets, telemetry/native and transport unchanged.')
    save(output/'SOURCE_FREEZE.json',freeze,True)
    return dict(status=freeze['status'],source_freeze=binding(output/'SOURCE_FREEZE.json'),checks=checks['passed']+checks['prepared_file_checks']['passed'],C_source_partition_count=len(c_ids),hardware_calls=0,model_calls=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--payload-root',type=Path);p.add_argument('--review-preparation',type=Path);p.add_argument('--checks',type=Path);a=p.parse_args()
    if a.review_preparation:
        if not a.checks:p.error('Review freeze requires --checks')
        result=freeze_review(a.review_preparation,a.output,a.checks)
    else:
        if not a.payload_root:p.error('Input preparation requires --payload-root')
        result=prepare(a.output,a.payload_root)
    print(json.dumps(result,indent=2),flush=True)
