"""Read-only exact native queue review; see README_S6D_NATIVE_QUEUE_REVIEW_V1.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

R=Path(__file__).resolve().parent.parent/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
RUNNER_SHA='fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4'
WRAPPER_SHA='874d55b0449f5cb53d9b6bf476d7a8cf97d1022e1cffd5ef844f71af5f8c5084'
EVIDENCE_SHA='bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2'
OWNER='01a0812d-3ff0-7ed0-a06c-4df61b62a459'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bind(p):
    p=Path(p).resolve();data=p.read_bytes()
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def require(condition, reason):
    if not condition:raise ValueError(reason)

def review(directory, expected_receipt_sha, output):
    directory=Path(directory).resolve();output=Path(output).resolve()
    require(output.is_relative_to(G) and not output.exists(),'Fresh G-only review output required')
    receipt_path=directory/'QUEUE_PREPARATION_RECEIPT.json'
    receipt_binding=bind(receipt_path)
    require(receipt_binding['sha256']==expected_receipt_sha,'Exact queue preparation receipt changed')
    receipt=read(receipt_path);checked={}
    def verify(b):
        key=(b['path'],b['sha256'],b['bytes'])
        if key not in checked:
            require(bind(b['path'])==b,'Binding changed: '+b['path']);checked[key]=b
        return read(b['path']) if b['path'].endswith('.json') else None
    preparation=verify(receipt['preparation']);prior_order=verify(preparation['headless176'])
    original_proposal=verify(prior_order['original_selection'])
    require(prior_order['job_order']==[j['job_id'] for j in original_proposal['literal_jobs']],'Original176 literal order changed')
    require(receipt['runner']['sha256']==RUNNER_SHA and receipt['wrapper']['sha256']==WRAPPER_SHA,'Accepted source pins differ')
    verify(receipt['runner']);verify(receipt['wrapper'])
    require(verify(receipt['runner_acceptance'])['runner']==receipt['runner'],'Runner acceptance differs')
    wrapper_review=verify(receipt['wrapper_review'])
    spec=importlib.util.spec_from_file_location('queue_review_pinned_runner',receipt['runner']['path'])
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    all_jobs={};manifests={};manifest_bindings={};job_origins={};all_output_paths=set()
    for mb in receipt['manifests']:
        m=verify(mb);prepared=verify(m['prior_prepared_manifest'])
        require({k:v for k,v in m.items() if k not in ('protocol_sources','protocol_wrapper','protocol_review','prior_prepared_manifest')}==prepared,'Protocol addition changed scientific manifest')
        require(m['protocol_sources']==dict(runner=receipt['runner'],evidence=m['evidence_helper']),'Per-manifest protocol dependency differs')
        require(m['evidence_helper']['sha256']==EVIDENCE_SHA and m['protocol_wrapper']==receipt['wrapper'],'Evidence/wrapper pin differs')
        require(m['protocol_review']==receipt['wrapper_review'],'Wrapper review binding differs')
        require(m['limits']['cpu_affinity']==[12,13,14,15],'Affinity changed')
        for b in [m['helper'],m['readme'],m['evidence_helper'],*m['execution_files'],*m.get('support_files',[])]:verify(b)
        name=Path(mb['path']).name;manifests[name]=m;manifest_bindings[name]=mb
        # Preparation may alter outputs and admission metadata, never a scientific native/Tk job.
        if name!='HOST2_MANIFEST.json':
            predecl=verify(m['prior_execution_proposal'])
            require(m['execution_files']==predecl['execution_files'] and m['source_root']==predecl['source_root'],'Application epoch changed')
            require(m['helper']==predecl['helper'],'Native helper changed')
            require(len(m['jobs'])==len(predecl['jobs']),'Predeclared population changed')
            for job,original in zip(m['jobs'],predecl['jobs']):
                require({k:v for k,v in job.items() if k!='output'}=={k:v for k,v in original.items() if k!='output'},'Predeclared job changed: '+job['job_id'])
        for job in m['jobs']:
            jid=job['job_id'];require(jid not in all_jobs,'Repeated native ID');all_jobs[jid]=job;job_origins[jid]=mb
            p=Path(job['output']).resolve();require(p.is_relative_to(G) and p not in all_output_paths and not p.exists(),'Output not fresh/unique under G: '+str(p));all_output_paths.add(p)
            require(type(job['expected_frames']) is int and job['expected_frames']>0 and job['expected_identity_frames']==job['expected_frames'],'Full frame proof missing')
            require(re.fullmatch('[0-9a-f]{64}',job['audio_pcm_sha256']) is not None,'Full PCM predeclaration missing')
            require(abs(job['expected_frames']/16000-job['audio_duration_sec'])<1e-9,'Source duration differs')
            require(verify(job['profile_binding'])==job['profile'],'Inline profile differs from original file')
            if job['gallery']:verify(job['gallery'])
            require(all(job['profile']['runtime'][k]==1 for k in ('asr_threads','speaker_threads','punctuation_threads')),'Inner thread pool differs')
    host=manifests['HOST2_MANIFEST.json'];repaired=manifests['REPAIRED_GUIV3_MANIFEST.json']
    require(host['execution_files']==repaired['execution_files'] and host['helper']==repaired['helper'],'HOST execution epoch changed')
    require(host['limits']['cell_timeout_sec']==7200,'HOST timeout differs')
    for job,outline in zip(host['jobs'],original_proposal['host_continuous_outline']):
        for key in ('job_id','candidate','audio','audio_duration_sec','expected_frames','composition'):require(job[key]==outline[key],'HOST outline changed: '+key)
        template=next(j for j in repaired['jobs'] if j['candidate']==job['candidate'] and j['asr_tap']=='O0')
        for key in ('profile','profile_binding','gallery','settings','asr_tap','identity_tap'):require(job[key]==template[key],'HOST fixed configuration differs: '+key)
        require(job['fixed_profile_through_whole_session'] and job['no_truth_resets'],'HOST continuity intent absent')
    require(len(all_jobs)==186,'Total population differs')
    groups=[];seen=set();literal=[]
    for group in receipt['groups']:
        q=verify(group['queue']);proposal=verify(group['approval_proposal']);ids=[j['job_id'] for j in q['jobs']]
        expected={'native176':prior_order['job_order'],'tk8':[j['job_id'] for j in manifests['TK8_MANIFEST.json']['jobs']],'host2':[j['job_id'] for j in host['jobs']]}[group['group']]
        require(ids==expected and len(ids)==group['job_count'],'Exact group order/cardinality differs')
        require(not seen.intersection(ids),'Cross-group duplicate');seen.update(ids)
        require(q['owner_thread_id']==q['owner_session_id']==OWNER and q['fixture_only'] is False,'Production owner/fixture identity differs')
        require(q['campaign']==dict(started_utc='2026-09-13T19:53:57+00:00',deadline_utc='2026-09-16T19:53:57+00:00',closeout_reserve_s=2700),'Campaign changed')
        require(q['payload_policy']['max_new_payload_bytes']==40*1024**3,'Payload cap changed')
        require(proposal['approved_job_sha256']==[] and proposal['proposed_job_sha256']==[runner.digest(j) for j in q['jobs']],'Proposal is approved or proposed hashes differ')
        # This is only an in-memory schema probe. No approval file or authorization is written.
        simulated=deepcopy(proposal);simulated['approved_job_sha256']=simulated['proposed_job_sha256']
        require(runner.validate_queue(q,simulated,group['queue']['sha256']) is True,'Pinned runner schema validation failed')
        try:runner.validate_queue(q,proposal,group['queue']['sha256'])
        except ValueError as exc:require('unapproved job' in str(exc),'Proposal failed for unexpected reason')
        else:raise ValueError('Empty proposed approval was accepted')
        for j in q['jobs']:
            job=all_jobs[j['job_id']];mb=job_origins[j['job_id']];m=manifests[Path(mb['path']).name]
            wanted=[proposal['executable_bindings'][0]['path'],receipt['wrapper']['path'],'--helper',m['helper']['path'],'--helper-sha256',m['helper']['sha256'],'--manifest',mb['path'],'--manifest-sha256',mb['sha256'],'--native-job-id',j['job_id']]
            require(j['argv']==wanted and j['cwd']==m['source_root'],'Literal execution differs')
            require(j['kind']=='offline' and j['workload']=='sensitive' and j['allow_owned_termination'] is True,'Workload/owned stop differs')
            require(j['stop_grace_s']==75 and j['heartbeat_stale_s']==45,'Stop/heartbeat policy differs')
            for path in (j['heartbeat_path'],j['completion_path'],j['stop_request_path']):require(not Path(path).exists() and Path(path).is_relative_to(G),'Protocol output occupied/escaped')
            artifacts={Path(a['path']).name:a for a in j['expected_artifacts']};fields=artifacts['COMPLETION.json']['expected_fields']
            for key,value in dict(status='COMPLETE',failure=None,native_job_id=j['job_id'],protocol_observer_closed=True,protocol_observer_errors=[],native_run_one_same_process=True,subprocess_spawned_by_wrapper=False,stop_requested=False,full_source_evidence_validated=True,affinity_verified=[12,13,14,15]).items():require(fields.get(key)==value,'Missing completion gate: '+key)
            for key,value in {'manifest.sha256':mb['sha256'],'helper.sha256':m['helper']['sha256'],'wrapper.sha256':WRAPPER_SHA,'completion_audit.path':str(Path(job['output'])/'FULL_SOURCE_AUDIT.json')}.items():require(fields.get(key)==value,'Wrong completion binding: '+key)
            audit=artifacts['FULL_SOURCE_AUDIT.json']['expected_fields']
            for key,value in {'status':'PASS_OFFLINE_EVIDENCE','errors':[],'expected_frames_predeclared':True,'source.sha256':EVIDENCE_SHA,'dispatch.frames':job['expected_frames'],'journals.source.frames':job['expected_frames'],'journals.source.sha256':job['audio_pcm_sha256']}.items():require(audit.get(key)==value,'Missing full-source gate: '+key)
            if group['group']=='tk8':
                require(fields.get('tk_view_evidence_validated') is True,'Tk view audit absent')
                closure=artifacts['OWNED_RESOURCE_CLOSURE.json']['expected_fields']
                for key,value in dict(resources_closed=True,setup_or_loop_error=None,cleanup_errors=[],startup_thread_alive=False,observer_thread_alive=False,root_destroyed=True,consumer_closed=True,render_files_closed=True,gallery_spy_restored=True).items():require(closure.get(key)==value,'Missing Tk closure: '+key)
            literal.append(dict(group=group['group'],job_id=j['job_id'],argv=j['argv'],cwd=j['cwd'],manifest=mb,output=job['output']))
        groups.append(dict(group=group['group'],queue=group['queue'],jobs=len(ids),in_memory_schema_probe='PASS',empty_proposal_rejected=True))
    require(literal==receipt['literal_jobs'] and seen==set(all_jobs),'Literal receipt differs from actual queues')
    scoring=verify(receipt['prospective_scoring']);prior_scoring=verify(preparation['scoring_bindings'])
    require(scoring['comparison_pairs']==prior_scoring['comparison_pairs'],'Scorer comparison plan changed')
    require(scoring['scorer']['sha256']=='4260ba5d1ac59f1e5fc057b7fa105fd1f525982ccf546353b5f283c054f092d4','Accepted scorer differs')
    for b in scoring['source_files']:verify(b)
    for row,old in zip(scoring['rows'],prior_scoring['rows']):
        require({k:v for k,v in row.items() if k!='manifest'}=={k:v for k,v in old.items() if k!='manifest'},'Reference/scoring row changed')
        require(row['manifest']==job_origins[row['job_id']],'Scoring manifest remap differs')
        verify(row['reference'])
    require(len(scoring['rows'])==176 and len(scoring['rows'])==len(prior_scoring['rows']),'Reference denominator changed')
    output.mkdir(parents=True)
    result=dict(status='ACCEPTED_EXACT_QUEUE_METADATA_PENDING_ROOT_ADOPTION',utc=datetime.now(timezone.utc).isoformat(),source=bind(__file__),queue_preparation=receipt_binding,groups=groups,checked_unique_bindings=len(checked),checked_unique_bytes=sum(b['bytes'] for b in checked.values()),scientific_jobs=186,native_rows=176,scoring_not_run=True,source_epochs_profiles_galleries_order_preserved=True,full_frame_pcm_predeclared=True,limitations=['No approval file written; schema probe used only in-memory proposed hashes','No current resource-floor, owner, topology or concurrent-work admission; root must perform final admission','No model, native helper, Tk/UI, actual scorer, hardware or subprocess execution','PCM metadata was matched to prior exact preparation; wrapper must hash actual audio and journals at execution','No whole-study completion or GUI scanout claim'])
    with (output/'INDEPENDENT_QUEUE_REVIEW_V1.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(bind(output/'INDEPENDENT_QUEUE_REVIEW_V1.json')))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);p.add_argument('--receipt-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();review(a.directory,a.receipt_sha256,a.output)
