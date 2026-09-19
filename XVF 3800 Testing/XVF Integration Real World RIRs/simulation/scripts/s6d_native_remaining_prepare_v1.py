"""Prepare conditional full-bank native data only; see README_S6D_NATIVE_REMAINING_PREPARE_V1.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def bind(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def verify(b):
    if bind(b['path'])!=b:raise ValueError('Changed authority: '+b['path'])
    return b


def pinned(path,sha):
    b=bind(path)
    if b['sha256']!=sha:raise ValueError('Pinned authority differs: '+str(path))
    return b


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def write(path,obj):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
    return bind(path)


def unique(rows):
    result={}
    for b in rows:
        if b['path'] in result and result[b['path']]!=b:raise ValueError('Conflicting binding')
        result[b['path']]=b
    return list(result.values())


def prepare(output,payload):
    output=output.resolve();payload=payload.resolve()
    if output.parent!=R/'runner' or payload.parent!=G/'runner':raise ValueError('Fresh bounded R/G preparation roots required')
    if output.exists() or payload.exists():raise ValueError('Fresh preparation roots required')
    audit_b=pinned(R/'cache_equivalence_scope_v1/CACHE_SCOPE_AUDIT_V1.json','5d8d76d8b614e3d8d1fe1ddb18b8e4fef46677362a46c4f5afa9382943933276')
    audit=read(audit_b['path']);authorities=audit['authorities']
    for key in ('input_index','repaired_active_manifest','active176_queue','s6c_epoch4','anonymous_analysis'):
        verify(authorities[key])
    base=read(authorities['repaired_active_manifest']['path']);queue=read(authorities['active176_queue']['path'])
    old_proposal_b=bind(Path(authorities['active176_queue']['path']).parent/'APPROVAL_PROPOSAL.json')
    old_proposal=read(old_proposal_b['path'])
    inputs=read(authorities['input_index']['path']);inputmap={(i['case_id'],i['stream']):i for i in inputs['rows']}
    analysis=read(authorities['anonymous_analysis']['path']);bank_b=verify(analysis['bank']);bank=read(bank_b['path'])
    scenes={s['case_id']:s for s in bank['scenes']}
    runner=verify(base['protocol_sources']['runner']);wrapper=verify(base['protocol_wrapper']);evidence=verify(base['evidence_helper'])
    verify(base['helper']);verify(base['readme']);verify(base['protocol_review'])
    for b in old_proposal['executable_bindings']:verify(b)
    if base['limits']['cpu_affinity']!=[12,13,14,15] or base['limits']['cell_timeout_sec']!=180.:
        raise ValueError('Accepted affinity/timeout changed')
    if queue['owner_thread_id']!='01a0812d-3ff0-7ed0-a06c-4df61b62a459':raise ValueError('Wrong root owner')
    pair_order=[('C065','O0'),('C065','O1'),('C088','O0'),('C088','O1')]
    controls={(r['candidate'],r['case_id'],r['tap']):r for r in audit['rows']}
    if len(controls)!=960:raise ValueError('Full historical controls missing')
    original_jobs=[j for j in base['jobs'] if j['candidate'] in ('C065','C088')]
    credit_routes={}
    for j in sorted(original_jobs,key=lambda j:(j['repeat_index'],j['job_id'])):
        credit_routes.setdefault((j['candidate'],j['scene_id'],j['asr_tap']),[]).append(j)
    if len(credit_routes)!=68:raise ValueError('Expected68 conditional native176 routes')
    remaining=sorted(set(controls)-set(credit_routes))
    if len(remaining)!=892:raise ValueError('Expected892 disjoint remaining routes')
    case_sets=[{case for c,case,t in remaining if (c,t)==pair} for pair in pair_order]
    if any(len(s)!=223 or s!=case_sets[0] for s in case_sets):raise ValueError('Expected223 common remaining cases per profile/tap')
    common=case_sets[0]
    criteria=[('F03','short',lambda s:any(x.get('kind')=='utterance' and 0<(x['source_stop_sample']-x['source_start_sample'])/16000<=2 for x in s['segments'])),
        ('F04','overlap',lambda s:bool(s['overlap_intervals'])),
        ('F11','ambience_overlap',lambda s:bool(s['overlap_intervals'])),
        ('F12','instrumental_nonspeech',lambda s:any(x.get('category')=='instrumental_music' and x.get('strict_nonspeech_eligible') is True for x in s['segments']))]
    pilot_cases=[];selection=[]
    for family,label,predicate in criteria:
        eligible=sorted(c for c in common if scenes[c]['family_id']==family and predicate(scenes[c]))
        if not eligible:raise ValueError('Missing metadata-selected pilot stratum: '+label)
        case=eligible[0];pilot_cases.append(case);s=scenes[case]
        selection.append(dict(case_id=case,family_id=family,family=s['family'],stratum=label,selection='lexicographically first remaining case satisfying predeclared metadata predicate; no outcome inspection',
            scheduled_overlap_count=len(s['overlap_intervals']),short_whole_utterance_count=sum(x.get('kind')=='utterance' and 0<(x['source_stop_sample']-x['source_start_sample'])/16000<=2 for x in s['segments']),timing_scope='whole-source schedule; not phonetic timing'))
    output.mkdir(parents=True);payload.mkdir(parents=True)
    data=payload/'data';data.mkdir();manifests=data/'manifests';manifests.mkdir();queues=data/'queues';queues.mkdir()
    native=payload/'native_outputs';protocol=payload/'protocol';states=payload/'states'
    # No runtime-output directories are created here; only data proposals exist.
    prerequisites=['Root explicitly retains exact C065/C088 GUIv3 T0/V0 after matched native176 analysis.',
        'All68 exact native176 credit routes are independently accepted, including full-source audit, protocol closure and owner exit; no credit is accepted here.',
        'Serial176, Tk and HOST controlled timing allocation has closed or root explicitly separated it without overlap.',
        'Root admits at most4 TOTAL active NN workers across these and beam-calibration/accuracy queues, never4+4.',
        'First16 (four4-cell queues) must pass full-input/closure and root throughput/memory/failure review before any219-cell continuation.',
        'Current C>=50GiB/G>=75GiB and shared40GiB campaign payload budget cover future outputs; deadline/reserve unchanged.',
        'Exact executable/environment and full source/audio/model/gallery bindings are revalidated by unchanged runtime guards before actual execution.']
    credits=[]
    for key,js in sorted(credit_routes.items()):
        preferred=js[0]
        credits.append(dict(candidate=key[0],case_id=key[1],tap=key[2],status='PENDING_ROOT_NATIVE176_ACCEPTANCE',
            preferred_predeclared_job=preferred['job_id'],all_predeclared_repeats=[j['job_id'] for j in js],
            source_manifest=authorities['repaired_active_manifest'],result_path=str(Path(preferred['output'])/'RESULT.json'),
            audit_path=str(Path(preferred['output'])/'FULL_SOURCE_AUDIT.json'),root_acceptance=None,
            policy='Do not select a successful repeat after seeing outcomes; all declared repeats/adverse results remain in native176 analysis. Replan missing/rejected credit under new root-reviewed metadata.'))
    matrix_rows=[];worker_jobs={}
    templates={pair:next(j for j in original_jobs if (j['candidate'],j['asr_tap'])==pair) for pair in pair_order}
    for number,pair in enumerate(pair_order,1):
        ids=pilot_cases+sorted(common-set(pilot_cases));jobs=[]
        for index,case in enumerate(ids):
            old=templates[pair];job=deepcopy(old);inp=inputmap[case,pair[1]];control=controls[pair[0],case,pair[1]]
            if inp['audio']!=control['audio'] or inp['audio_pcm_sha256']!=control['audio_pcm_sha256'] or job['profile_binding']!=control['profile'] or job['gallery']!=control['gallery']:
                raise ValueError('Exact input/profile/gallery differs from audited historical route')
            frames=round(inp['duration_sec']*16000)
            if frames/16000!=inp['duration_sec']:raise ValueError('Noninteger input frame count')
            identifier=f'{pair[0]}_{case}_{pair[1]}_delivery_repair_full_r1';phase='pilot' if index<4 else 'continuation'
            job.update(job_id=identifier,scene_id=case,audio=inp['audio'],audio_pcm_sha256=inp['audio_pcm_sha256'],audio_duration_sec=inp['duration_sec'],
                expected_frames=frames,expected_identity_frames=frames,repeat_index=1,scientific_role='FULL_BANK_NATIVE_CONFIRMATION_SHARED_CPU_NO_SERIAL_TIMING_CLAIM',
                output=str(native/f'worker_{number}'/identifier))
            jobs.append(job)
            matrix_rows.append(dict(job_id=identifier,worker=number,phase=phase,candidate=pair[0],case_id=case,tap=pair[1],family_id=scenes[case]['family_id'],
                audio=inp['audio'],audio_pcm_sha256=inp['audio_pcm_sha256'],expected_frames=frames,profile=job['profile_binding'],gallery=job['gallery'],
                original_control_prediction=control['prediction'],historical_control_is_not_reference_truth=True,output=job['output']))
        worker_jobs[number]=jobs
    matrix_b=write(data/'CONDITIONAL_MATRIX.json',dict(schema='s6d-native-remaining-full-bank.v1',status='CONDITIONAL_PROPOSAL_NOT_ADMITTED',
        source_audit=audit_b,source_native176_queue=authorities['active176_queue'],source_manifest=authorities['repaired_active_manifest'],input_index=authorities['input_index'],
        scene_metadata=bank_b,prerequisites=prerequisites,full_scope=960,conditional_credits=credits,accepted_credits=0,new_jobs=892,pilot_jobs=16,continuation_jobs=876,
        partition='worker1=C065/O0,worker2=C065/O1,worker3=C088/O0,worker4=C088/O1; same223 remaining cases per worker; first4 metadata-selected then lexical remainder',
        pilot_selection=selection,rows=matrix_rows,no_outcome_selection=True,no_original_NN_repeats=True,reference_truth_not_supplied_to_runtime=True))
    groups=[];manifest_bounds=[]
    base_queue_job=next(j for j in queue['jobs'] if '_delivery_repair_' in j['job_id'] and j['job_id'].startswith('C065'))
    for number,jobs in worker_jobs.items():
        m=deepcopy(base)
        m.update(jobs=jobs,job_count=223,source_audio_total_sec=sum(j['audio_duration_sec'] for j in jobs),payload_root=str(native/f'worker_{number}'),
            status='CONDITIONAL_REMAINING_FULL_BANK_ROOT_ADOPTION_REQUIRED',approved=False,model_jobs_started=0,created_utc=datetime.now(timezone.utc).isoformat(),
            prior_prepared_manifest=authorities['repaired_active_manifest'],conditional_matrix=matrix_b,
            concurrency_scope=dict(serial_within_this_worker=True,maximum_total_NN_workers_across_all_studies=4,shared_logical_cpu_affinity=[12,13,14,15],physical_core_isolation=False,CM5_benchmark=False))
        mb=write(manifests/f'WORKER_{number}_MANIFEST.json',m);manifest_bounds.append(mb)
        for phase,phasejobs in [('pilot',jobs[:4]),('continuation',jobs[4:])]:
            group=f'worker_{number}_{phase}';folder=queues/group;folder.mkdir();qjobs=[]
            for job in phasejobs:
                qj=deepcopy(base_queue_job);identifier=job['job_id'];pp=protocol/group/identifier;op=Path(job['output']);auditpath=op/'FULL_SOURCE_AUDIT.json'
                qj.update(job_id=identifier,cwd=m['source_root'],heartbeat_path=str(pp/'HEARTBEAT.json'),completion_path=str(pp/'COMPLETION.json'),stop_request_path=str(pp/'STOP_REQUEST.json'),
                    native_input_seconds=job['audio_duration_sec'],scientific_role=job['scientific_role'])
                qj['argv']=[old_proposal['executable_bindings'][0]['path'],wrapper['path'],'--helper',m['helper']['path'],'--helper-sha256',m['helper']['sha256'],'--manifest',mb['path'],'--manifest-sha256',mb['sha256'],'--native-job-id',identifier]
                qj['source_bindings']=unique([runner,wrapper,mb,m['helper'],m['readme'],evidence,*m['execution_files'],*m.get('support_files',[]),job['profile_binding'],*([job['gallery']] if job['gallery'] else []),matrix_b])
                arts=qj['expected_artifacts'];arts[0]['path']=qj['completion_path'];arts[1]['path']=str(op/'RESULT.json');arts[2]['path']=str(auditpath)
                for art in arts:art['expected_fields']['manifest.sha256']=mb['sha256']
                arts[0]['expected_fields'].update(native_job_id=identifier,**{'completion_audit.path':str(auditpath)})
                arts[1]['expected_fields']['job.job_id']=identifier
                arts[2]['expected_fields'].update(job_id=identifier,**{'dispatch.frames':job['expected_frames'],'journals.source.frames':job['expected_frames'],'journals.source.sha256':job['audio_pcm_sha256']})
                # All stop/timeout/heartbeat/full-source semantics are inherited unchanged.
                qjobs.append(qj)
            q={k:deepcopy(queue[k]) for k in ('schema','run_id','owner_thread_id','owner_session_id','fixture_only','campaign','disk_policy','payload_policy','runner_sha256','protocol_wrapper','protocol_review')}
            q.update(created_utc=datetime.now(timezone.utc).isoformat(),production_status='CONDITIONAL_PROPOSAL_NOT_ADMITTED',preparation=matrix_b,group=group,jobs=qjobs)
            qb=write(folder/'QUEUE.json',q)
            approval=deepcopy(old_proposal)
            approval.update(queue_sha256=qb['sha256'],authorization_ref=str(folder/'ROOT_ADMISSION.json'),approved_job_sha256=[],proposed_job_sha256=[digest(j) for j in qjobs],
                allowed_working_directories=[m['source_root']],approval_state='NOT_APPROVED_CONDITIONAL_ROOT_REVIEW_REQUIRED')
            ab=write(folder/'APPROVAL_PROPOSAL.json',approval)
            rb=write(folder/'ROOT_ADMISSION_PROPOSAL.json',dict(schema='s6d-native-full-bank-root-admission-proposal.v1',status='NOT_ADMITTED',queue=qb,manifest=mb,matrix=matrix_b,
                prerequisite_status={p:'PENDING' for p in prerequisites},accepted_native176_credit_count=0,root_review_passed=False,
                pilot_acceptance_required=phase=='continuation',corresponding_pilot_group=f'worker_{number}_pilot',maximum_total_NN_workers_across_all_studies=4,
                no_authority_to_launch=True,deadline_not_extended=True))
            groups.append(dict(group=group,worker=number,phase=phase,queue=qb,manifest=mb,approval_proposal=ab,root_admission_proposal=rb,
                job_count=len(qjobs),source_seconds=sum(j['audio_duration_sec'] for j in phasejobs),state_dir=str(states/group),
                approval_path=str(folder/'APPROVAL.json'),admission_path=str(folder/'ROOT_ADMISSION.json')))
    all_ids=[row['job_id'] for row in matrix_rows]
    if len(set(all_ids))!=892 or sum(g['job_count'] for g in groups)!=892 or sorted(g['job_count'] for g in groups)!=[4]*4+[219]*4:
        raise ValueError('Pilot/continuation partition does not cover exactly892 once')
    forecast_b=bind(R/'application/native_execution_preparation_v1/PILOT_PAYLOAD_FORECAST.json');forecast=read(forecast_b['path'])
    findings_b=bind(R/'application/NATIVE_PILOT_FINDINGS_V2.md')
    total_sec=sum(j['audio_duration_sec'] for js in worker_jobs.values() for j in js)
    model=forecast['actual_bytes_per_cell_max'];scaled=sum(model*j['audio_duration_sec']/44.6954375 for js in worker_jobs.values() for j in js)
    projection=dict(status='ARITHMETIC_FORECAST_NOT_MEASURED_FOUR_WORKER_PERFORMANCE',pilot_payload_authority=forecast_b,pilot_runtime_memory_authority=findings_b,
        historical_source_seconds_per_cell=44.6954375,historical_native_cell_wall_seconds_approx=[77,83],historical_max_process_tree_rss_bytes=498827264,
        historical_max_process_tree_uss_bytes=435093504,four_stack_sum_of_historical_rss_bytes=4*498827264,four_stack_sum_of_historical_uss_bytes=4*435093504,
        memory_scope='Sum of historical single-cell maxima, not measured concurrent peak; add four supervisor/observer/Python overheads and other campaign jobs.',
        new_source_seconds=total_sec,serial_wall_hours_cell_scaled=[892*77/3600,892*83/3600],ideal_four_way_hours_same_cell_cost=[223*77/3600,223*83/3600],
        first16_serial_equivalent_minutes=[16*77/60,16*83/60],first16_ideal_four_way_minutes=[4*77/60,4*83/60],
        throughput_scope='No measured speedup; four ASR/speaker/punctuation lane sets contend on the same four logical CPUs. Supervisor census costs and I/O are additional. Pilot must measure healthy completion, aggregate throughput, process-tree memory, failures and unchanged watchdog limits before continuations.',
        new_payload_max_observed_cell_scaled_bytes=scaled,new_payload_max_observed_cell_scaled_gib=scaled/1024**3,
        first16_max_observed_cell_scaled_gib=sum(model*j['audio_duration_sec']/44.6954375 for js in worker_jobs.values() for j in js[:4])/1024**3,
        payload_scope='Historical13-file cell maximum scaled by source duration; not a hard upper bound. Queue/source metadata, longer resource logs, scoring and remaining physical/beam work share the unchanged40GiB cap.',
        concurrency_maximum=4,logical_cpu_affinity=[12,13,14,15],physical_core_isolation=False,CM5_result=False,
        actual_parallel_measurements=None,source_timeout_seconds=180,supervisor_timeout_seconds=360,stall_seconds=180,heartbeat_stale_seconds=45,stop_grace_seconds=75,
        global_cap_scope='Root-admitted allocation across these AND beam queues; no code-level inter-queue semaphore is added. Four here leaves zero NN slots elsewhere.',
        no_timeout_extensions=True)
    fb=write(output/'FORECAST.json',projection)
    result=dict(schema='s6d-native-remaining-preparation.v1',status='CONDITIONAL_DATA_ONLY_PREPARED_NOT_ADMITTED',source=bind(__file__),source_readme=bind(Path(__file__).with_name('README_S6D_NATIVE_REMAINING_PREPARE_V1.md')),
        matrix=matrix_b,manifests=manifest_bounds,groups=groups,forecast=fb,runner=runner,wrapper=wrapper,evidence=evidence,original_native176_queue=authorities['active176_queue'],
        native176_accepted_credit_count=0,proposed_credit_count=68,new_jobs=892,pilot_jobs=16,continuation_jobs=876,source_audit=audit_b,pilot_selection=selection,
        prerequisites=prerequisites,created_utc=datetime.now(timezone.utc).isoformat(),no_launches=True,no_models=True,no_hardware=True,no_audio_opened=True,no_active_outputs_read=True,
        no_production_authorization_files_created=True,source_protocol_unchanged=True,metadata_payload_root=str(payload),payload_or_runtime_directories_created=False)
    receipt=write(output/'PREPARATION_RESULT.json',result)
    print(json.dumps(dict(status=result['status'],receipt=receipt,pilot_cases=pilot_cases,groups=[(g['group'],g['job_count']) for g in groups],new_payload_forecast_gib=projection['new_payload_max_observed_cell_scaled_gib'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--payload',type=Path,required=True)
    a=p.parse_args();prepare(a.output,a.payload)
