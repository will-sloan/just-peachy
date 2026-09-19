"""Migrate serial892 metadata to accepted V5/V3; see README_S6D_NATIVE_SERIAL892_PREPARE_V2.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
PRIOR=R/'runner/native_serial892_preparation_v1/PREPARATION_RESULT.json'
PRIOR_SHA='60c14d0ac094e334d2fd06a49063eaaae3932fb18bdc0ab7149595c3ae187cbc'
ACCEPTANCE=R/'runner/source_epoch_payload_v5/ROOT_SOURCE_ACCEPTANCE.json'
ACCEPTANCE_SHA='585c3db4729d7b75ce42cc2cf7b0fc619d89afd096730c3215538ac1b48d4c34'
LEGACY=SIM/'scripts/s6d_native_serial892_prepare_v1.py'
if hashlib.sha256(LEGACY.read_bytes()).hexdigest()!='1ec230bd4e6edaf0486108330ff80485c2f975a36f1bc4ca51c3dcbe3c8291d9':
    raise ValueError('Pinned metadata-only helper differs')
spec=importlib.util.spec_from_file_location('s6d_serial_metadata_legacy',LEGACY)
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
read,bind,verify,pinned,digest,write,unique,excluded=(getattr(A,n) for n in ('read','bind','verify','pinned','digest','write','unique','excluded'))

def need(value,message):
    if not value:raise ValueError(message)

def utc():return datetime.now(timezone.utc).isoformat()

def compare(prior,new,oldq,newq,oldms,newms,oldmx,newmx,payload,runner,wrapper,exception,guards):
    """Compare saved metadata; no source transformations or runtime imports here."""
    oldjobs=[j for m in oldms for j in m['jobs']];jobs=[j for m in newms for j in m['jobs']]
    ids=[j['job_id'] for j in oldjobs]
    need(len(ids)==len(set(ids))==892,'Exact892 original IDs required')
    need(ids==[j['job_id'] for j in jobs]==[j['job_id'] for j in newq['jobs']]==[r['job_id'] for r in newmx['rows']],'Literal ordered892 membership differs')
    need(oldmx['conditional_credits']==newmx['conditional_credits'] and len(newmx['conditional_credits'])==68 and newmx['accepted_credits']==0,'Conditional credits must remain unaccepted and identical')
    mxmutable={'rows','status','prerequisites','prior_serial_matrix','source_preparation','payload_cap_exception','payload_source_acceptance'}
    need(excluded(oldmx,mxmutable)==excluded(newmx,mxmutable),'Matrix population, controls, labels or allocation scope changed')
    qmutable={'runner_sha256','protocol_wrapper','protocol_review','created_utc','production_status','preparation','jobs','payload_policy','prior_serial_queue','prior_protocol_review'}
    need(excluded(oldq,qmutable)==excluded(newq,qmutable),'Queue allocation, identity, floors, deadlines or other policy changed')
    need(newq['runner_sha256']==runner['sha256'] and newq['protocol_wrapper']==wrapper,'Active queue protocol source not rebound')
    need(newq['payload_policy']=={**oldq['payload_policy'],'max_new_payload_bytes':80*2**30,'cap_exception':exception},'Only exact payload80/exception delta allowed')
    need(newmx['maximum_total_neural_workers_during_queue']==1 and newq['allocation_constraint']==oldq['allocation_constraint'],'Controlled serial allocation changed')
    mmutable={'payload_root','jobs','limits','status','created_utc','protocol_sources','protocol_wrapper','protocol_review','conditional_matrix','payload_cap_exception','support_files','prior_serial_manifest','prior_protocol_review','payload_source_acceptance'}
    used_outputs=set();used_protocols=set()
    for index,(oldm,m) in enumerate(zip(oldms,newms),1):
        need(excluded(oldm,mmutable)==excluded(m,mmutable),'Scientific manifest/source/assets/gallery or other inherited fields changed')
        need(m['limits']=={**oldm['limits'],'max_new_payload_gib':80},'Any timing, affinity, pool, floor or source policy changed')
        need(m['limits']['cpu_affinity']==[12,13,14,15] and m['limits']['cpu_threads_each']==1 and m['concurrency_scope']==oldm['concurrency_scope'],'One-worker allocation changed')
        need(m['protocol_wrapper']==wrapper and m['protocol_sources']=={**oldm['protocol_sources'],'runner':runner},'Manifest protocol graph differs')
        need(m['protocol_review']==m['payload_source_acceptance']==newq['protocol_review'],'Active protocol review not consistently rebound')
        need(m['payload_cap_exception']==exception and all(b in m['support_files'] for b in guards),'Manifest exception/support guards incomplete')
        need(Path(m['payload_root'])==payload/'native_outputs'/f'profile_{index}','Fresh manifest output root differs')
    for oldjob,job,oldjq,jq,oldrow,row in zip(oldjobs,jobs,oldq['jobs'],newq['jobs'],oldmx['rows'],newmx['rows']):
        need(excluded(oldjob,{'output'})==excluded(job,{'output'}),'Native scientific job changed beyond output path')
        need(excluded(oldrow,{'output'})==excluded(row,{'output'}),'Matrix scientific row changed beyond output path')
        expected_output=payload/'native_outputs'/f"profile_{row['source_worker']}"/job['job_id']
        need(Path(job['output'])==expected_output and row['output']==job['output'],'Exact fresh native output mapping differs')
        need(job['output'] not in used_outputs and not expected_output.exists(),'Native output is reused or already present');used_outputs.add(job['output'])
        mutable={'argv','heartbeat_path','completion_path','stop_request_path','source_bindings','expected_artifacts'}
        need(excluded(oldjq,mutable)==excluded(jq,mutable),'Supervisor waits, timeout, STOP, role or other policy changed')
        oldargv=oldjq['argv'];argv=jq['argv']
        need(len(argv)==len(oldargv)==12 and [v for i,v in enumerate(argv) if i not in (1,7,9)]==[v for i,v in enumerate(oldargv) if i not in (1,7,9)],'Executable/helper/native-job literal arguments changed')
        mb=new['manifests'][row['source_worker']-1]
        need(argv[1]==wrapper['path'] and argv[7]==mb['path'] and argv[9]==mb['sha256'],'Literal entry/manifest binding differs')
        for key,name in (('heartbeat_path','HEARTBEAT.json'),('completion_path','COMPLETION.json'),('stop_request_path','STOP_REQUEST.json')):
            p=payload/'protocol'/job['job_id']/name
            need(jq[key]==str(p) and str(p) not in used_protocols and not p.exists(),'Fresh unique protocol path differs');used_protocols.add(str(p))
        need(len(jq['expected_artifacts'])==len(oldjq['expected_artifacts'])==3,'Artifact guard count differs')
        expected_paths=[jq['completion_path'],str(expected_output/'RESULT.json'),str(expected_output/'FULL_SOURCE_AUDIT.json')]
        for a,b,expected_path in zip(oldjq['expected_artifacts'],jq['expected_artifacts'],expected_paths):
            need(b['path']==expected_path and excluded(a,{'path','expected_fields'})==excluded(b,{'path','expected_fields'}),'Artifact format/path policy changed')
            need(excluded(a['expected_fields'],{'manifest.sha256','wrapper.sha256','completion_audit.path'})==excluded(b['expected_fields'],{'manifest.sha256','wrapper.sha256','completion_audit.path'}),'Scientific completion/source predicate changed')
            need(b['expected_fields']['manifest.sha256']==mb['sha256'],'Artifact manifest hash stale')
            if 'wrapper.sha256' in a['expected_fields']:need(b['expected_fields']['wrapper.sha256']==wrapper['sha256'],'Artifact wrapper hash stale')
            if 'completion_audit.path' in a['expected_fields']:need(b['expected_fields']['completion_audit.path']==expected_paths[2],'Artifact audit path stale')
        need(all(b in jq['source_bindings'] for b in guards+[runner,wrapper,mb,new['matrix']]),'Every current source/exception authority must be guarded')
        removed={prior['wrapper']['path'],prior['matrix']['path'],*[b['path'] for b in prior['manifests']]}
        need(not any(b['path'] in removed for b in jq['source_bindings']),'Stale active wrapper/matrix/manifest source reference')
        need(all(b in jq['source_bindings'] for b in oldjq['source_bindings'] if b['path'] not in removed),'Inherited source guard lost')
        need(max(b['bytes'] for b in jq['source_bindings'])<=16*2**20 and sum(b['bytes'] for b in jq['source_bindings'])<=64*2**20,'Source guard size exceeds unchanged runner limits')
    need(all(not (payload/p).exists() for p in ('native_outputs','protocol','state','data/APPROVAL.json','data/ROOT_ADMISSION.json')),'Preparation created runtime outputs or authority')
    return dict(status='PASS_SAVED_METADATA_COMPARISON_ONLY',jobs=892,conditional_credits=68,accepted_credits=0,
        one_serial_queue=True,scientific_native_fields_unchanged_except_output=True,ordered_matrix_scientific_fields_unchanged_except_output=True,
        exact_profiles_audio_PCM_frames_galleries_settings_assets=True,all_timing_affinity_wait_STOP_and_artifact_predicates_unchanged=True,
        exact80_exception_and_same_roots_floors_deadline=True,all892_small_authority_guard_sets_complete=True,
        old_active_manifest_wrapper_output_references_absent=True,fresh_runtime_and_authorization_paths_absent=True)

def prepare(output,payload):
    output,payload=output.resolve(),payload.resolve()
    need(output.parent==R/'runner' and payload.parent==G/'runner' and not output.exists() and not payload.exists(),'Fresh bounded report/G metadata roots required')
    prior_b=pinned(PRIOR,PRIOR_SHA);prior=read(PRIOR)
    accepted_b=pinned(ACCEPTANCE,ACCEPTANCE_SHA);accepted=read(ACCEPTANCE)
    need(accepted['status']=='ROOT_ACCEPTED_FUTURE_OFFLINE_PAYLOAD_V5_AND_WRAPPER_V3_SOURCE_ONLY' and accepted['run_id']=='20260913T195357Z' and accepted['owner_thread_id']=='01a0812d-3ff0-7ed0-a06c-4df61b62a459','Exact root source acceptance required')
    source_freeze=verify(accepted['runner_source_freeze']);wrapper_freeze=verify(accepted['wrapper_source_freeze'])
    closure=read(source_freeze['path']);wf=read(wrapper_freeze['path'])
    runner=verify(wf['runner']);wrapper=verify(wf['wrapper']);exception=verify(accepted['exception']);exception_data=read(exception['path'])
    need(runner['sha256']=='57fb87aaba12495f724adbcc78a2609f82a897dd5d3877e6a2cabd54a68a7978' and wrapper['sha256']=='bdb9896cc3cdfefe85ea1602b904373ceb24de0de52965b0a66b3c56ecd1fe12','Accepted V5/V3 exact source required')
    need(exception['sha256']=='079900e58493e18c3a995754ba7ac16ff680e4697ba8dc6521e0b6fe1eb3a54c','Exact documented80 exception required')
    guards=[exception]+[verify(exception_data[k]) for k in ('contract','forecast','prior_runner')]
    guards=unique(guards+[accepted_b,source_freeze,wrapper_freeze])
    for b in closure['sources']:verify(b)
    docs=[prior[k] for k in ('matrix','queue','approval_proposal','root_admission_proposal','forecast','source_concurrency_constraint')]+prior['manifests']
    for b in docs:verify(b)
    oldq=read(prior['queue']['path']);oldms=[read(b['path']) for b in prior['manifests']];oldmx=read(prior['matrix']['path'])
    need(len(oldms)==4 and all(len(m['jobs'])==223 for m in oldms) and prior['worker_count']==1 and prior['new_jobs']==892 and prior['accepted_credits']==0,'Exact prior serial892 shape required')
    core=unique([b for j in oldq['jobs'] for b in j['source_bindings']])
    for b in core:verify(b)
    oldapproval=read(prior['approval_proposal']['path'])
    for b in oldapproval['executable_bindings']:verify(b)
    need(oldapproval['approved_job_sha256']==[] and oldmx['accepted_credits']==0,'Old proposal must remain unapproved')
    need(shutil.disk_usage('C:/').free>=50*2**30 and shutil.disk_usage('G:/').free>=75*2**30,'Unchanged preparation storage floors')
    source=bind(__file__);readme=bind(Path(__file__).with_name('README_S6D_NATIVE_SERIAL892_PREPARE_V2.md'))
    extra=unique(guards+[source,readme,bind(LEGACY)]+[b for b in closure['sources'] if b['path'].endswith('.md')])
    prerequisites=[
        'Root retains exact C065/C088 GUIv3 T0/V0 after controlled native176 scientific analysis; no favorable selection or scientific PASS is imputed here.',
        'All68 exact native176 credits need separate root acceptance with full-source audit, protocol closure and owned-process exit; accepted credits remain0.',
        'Root closes controlled native176, C12, Tk and HOST2 serial allocations before892. Exactly one NN worker and no other neural session may overlap this queue.',
        'Root admits the exact future V5/V3/80GiB graph and all892 literal jobs; old parallel892 proposals remain unapproved and scientifically ineligible as replacements.',
        'All3 shared payload roots, C50/G75 floors, documented80GiB exception,480 physical attempts/21600 charged seconds, original deadline and45-minute reserve remain fixed.',
        'Root rechecks current census, disk space and remaining wall-time feasibility. Historical19.399–20.910h arithmetic is not a new timing measurement or deadline extension.',
        'Every failure or incomplete prefix stays adverse; no sample dropping, source truncation, timeout expansion, repaired result reuse or silent replacement.']
    output.mkdir(parents=True);payload.mkdir(parents=True);data=payload/'data';data.mkdir()
    mx=deepcopy(oldmx)
    for row in mx['rows']:row['output']=str(payload/'native_outputs'/f"profile_{row['source_worker']}"/row['job_id'])
    mx.update(status='CONDITIONAL_SERIAL_V5_V3_80_PROPOSAL_NOT_ADMITTED',prerequisites=prerequisites,prior_serial_matrix=prior['matrix'],source_preparation=prior_b,payload_cap_exception=exception,payload_source_acceptance=accepted_b)
    matrix_b=write(data/'CONDITIONAL_MATRIX.json',mx)
    manifests=[]
    for i,oldm in enumerate(oldms,1):
        m=deepcopy(oldm)
        m['limits']['max_new_payload_gib']=80
        m['protocol_sources']['runner']=runner
        m.update(protocol_wrapper=wrapper,protocol_review=accepted_b,prior_protocol_review=oldm['protocol_review'],
            conditional_matrix=matrix_b,payload_cap_exception=exception,payload_source_acceptance=accepted_b,
            support_files=unique(oldm.get('support_files',[])+extra),prior_serial_manifest=prior['manifests'][i-1],
            payload_root=str(payload/'native_outputs'/f'profile_{i}'),created_utc=utc(),status='CONDITIONAL_SERIAL_V5_V3_80_ROOT_ADOPTION_REQUIRED')
        for j in m['jobs']:j['output']=str(Path(m['payload_root'])/j['job_id'])
        manifests.append(write(data/f'SERIAL_PROFILE_{i}_MANIFEST.json',m))
    q=deepcopy(oldq)
    q.update(runner_sha256=runner['sha256'],protocol_wrapper=wrapper,protocol_review=accepted_b,prior_protocol_review=oldq['protocol_review'],
        created_utc=utc(),production_status='CONDITIONAL_SERIAL_V5_V3_80_PROPOSAL_NOT_ADMITTED',preparation=matrix_b,prior_serial_queue=prior['queue'])
    q['payload_policy'].update(max_new_payload_bytes=80*2**30,cap_exception=exception)
    for pos,j in enumerate(q['jobs']):
        mb=manifests[pos//223];native=payload/'native_outputs'/f'profile_{pos//223+1}'/j['job_id'];protocol=payload/'protocol'/j['job_id']
        j['argv'][1]=wrapper['path'];j['argv'][7]=mb['path'];j['argv'][9]=mb['sha256']
        j.update(heartbeat_path=str(protocol/'HEARTBEAT.json'),completion_path=str(protocol/'COMPLETION.json'),stop_request_path=str(protocol/'STOP_REQUEST.json'))
        remove={prior['wrapper']['path'],prior['matrix']['path'],prior['manifests'][pos//223]['path']}
        j['source_bindings']=unique([b for b in j['source_bindings'] if b['path'] not in remove]+extra+[runner,wrapper,mb,matrix_b])
        for a,p in zip(j['expected_artifacts'],[Path(j['completion_path']),native/'RESULT.json',native/'FULL_SOURCE_AUDIT.json']):
            a['path']=str(p);a['expected_fields']['manifest.sha256']=mb['sha256']
            if 'wrapper.sha256' in a['expected_fields']:a['expected_fields']['wrapper.sha256']=wrapper['sha256']
            if 'completion_audit.path' in a['expected_fields']:a['expected_fields']['completion_audit.path']=str(native/'FULL_SOURCE_AUDIT.json')
    qb=write(data/'QUEUE.json',q)
    approval=deepcopy(oldapproval)
    approval.update(queue_sha256=qb['sha256'],authorization_ref=str(data/'ROOT_ADMISSION.json'),payload_cap_exception=exception,
        approved_job_sha256=[],proposed_job_sha256=[digest(j) for j in q['jobs']],approval_state='NOT_APPROVED_CONDITIONAL_SERIAL_V5_V3_80_ROOT_REVIEW_REQUIRED')
    ab=write(data/'APPROVAL_PROPOSAL.json',approval)
    admission=write(data/'ROOT_ADMISSION_PROPOSAL.json',dict(schema='s6d-native-serial-root-admission-proposal.v2',status='NOT_ADMITTED',queue=qb,manifests=manifests,matrix=matrix_b,
        runner=runner,wrapper=wrapper,source_acceptance=accepted_b,payload_cap_exception=exception,
        prerequisite_status={p:'PENDING' for p in prerequisites},accepted_native176_credit_count=0,proposed_native176_credit_count=68,exact_new_jobs=892,
        root_review_passed=False,maximum_total_NN_workers_across_all_studies=1,no_other_neural_sessions_during_queue=True,no_authority_to_launch=True,deadline_not_extended=True))
    new=dict(manifests=manifests,matrix=matrix_b)
    comparison=compare(prior,new,oldq,read(qb['path']),oldms,[read(b['path']) for b in manifests],oldmx,read(matrix_b['path']),payload,runner,wrapper,exception,guards)
    need(read(ab['path'])['approved_job_sha256']==[] and read(admission['path'])['root_review_passed'] is False,'Accidental approval')
    all_sources=unique([b for j in q['jobs'] for b in j['source_bindings']])
    for b in all_sources:verify(b)
    comparison.update(queue=qb,manifests=manifests,matrix=matrix_b,prior=prior_b,source_acceptance=accepted_b,unique_small_guard_bindings_verified=len(all_sources),no_PCM_or_models_opened=True)
    review_b=write(output/'DATA_READBACK_REVIEW_V2.json',comparison)
    forecast=read(prior['forecast']['path'])
    forecast.update(prior_serial_forecast=prior['forecast'],payload_cap_exception=exception,whole_study_forecast=exception_data['forecast'],source_and_wall_time_arithmetic_unchanged=True,new_timing_measurements=0)
    fb=write(output/'FORECAST.json',forecast)
    metadata_bytes=sum(p.stat().st_size for p in data.iterdir() if p.is_file())
    need(metadata_bytes<64*2**20,'Bounded small metadata preparation exceeded64MiB')
    result=dict(schema='s6d-native-serial892-preparation.v2',status='CONDITIONAL_SERIAL_V5_V3_80_DATA_PREPARED_NOT_ADMITTED',source=source,source_readme=readme,
        source_dependency=bind(LEGACY),prior_preparation=prior_b,source_concurrency_constraint=prior['source_concurrency_constraint'],source_acceptance=accepted_b,
        matrix=matrix_b,manifests=manifests,queue=qb,approval_proposal=ab,root_admission_proposal=admission,forecast=fb,readback_review=review_b,
        runner=runner,wrapper=wrapper,evidence=prior['evidence'],payload_cap_exception=exception,original_native176_queue=prior['original_native176_queue'],
        conditional_credits=68,accepted_credits=0,new_jobs=892,worker_count=1,group='serial892',state_dir=str(payload/'state'),
        approval_path=str(data/'APPROVAL.json'),admission_path=str(data/'ROOT_ADMISSION.json'),prerequisites=prerequisites,
        no_launches=True,no_models=True,no_hardware=True,no_audio_or_active_results_opened=True,no_production_authorization_created=True,
        scientific_protocol_unchanged=True,only_accepted_protocol_budget_metadata_and_paths_changed=True,G_metadata_bytes=metadata_bytes,created_utc=utc())
    rb=write(output/'PREPARATION_RESULT.json',result)
    print(json.dumps(dict(status=result['status'],result=rb,queue=qb,readback=review_b,jobs=892,workers=1,accepted_credits=0,metadata_bytes=metadata_bytes)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--payload',type=Path,required=True)
    args=parser.parse_args();prepare(args.output,args.payload)
