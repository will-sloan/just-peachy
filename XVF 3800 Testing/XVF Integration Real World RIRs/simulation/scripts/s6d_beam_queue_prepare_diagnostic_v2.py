"""Held diagnostic-only dual-journal queue; see README_S6D_BEAM_DIAGNOSTIC_V2.md."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import s6d_beam_native_run_diagnostic_v2 as N
import s6d_beam_execution_prepare_v1 as P

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def prepare(manifest_path,manifest_sha,output):
    mb=N.bind(manifest_path);N.need(mb['sha256']==manifest_sha,'Exact reviewed execution manifest required');m=N.verified(mb)
    N.need(m['schema']=='s6d-beam-execution.v1' and m['jobs'] and m['stage']=='stream_diagnostics' and all(j['mode']=='stream_diagnostic' for j in m['jobs']),'Bound nonempty diagnostic-only stage required')
    N.need(m['runner_helper']==N.bind(N.__file__),'Manifest must bind exact reviewed diagnostic dual-journal wrapper')
    out=Path(output).resolve();N.need(out.parent==P.R/'runner' and not out.exists(),'Fresh runner proposal directory required')
    runner=N.bind(P.R/'runner/source_epoch_census_v4/s6d_runner_v1.py');N.need(runner['sha256']=='fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4','Accepted V4 changed')
    original=N.verified(N.bind(P.R/'runner/native_pilot_proposed_v1/PROPOSED_QUEUE.json'))
    q={k:deepcopy(original[k]) for k in ('schema','run_id','owner_thread_id','owner_session_id','fixture_only','campaign','disk_policy','payload_policy')}
    q.update(runner_sha256=runner['sha256'],status='PROPOSED_NOT_APPROVED',stage=m['stage'],manifest=mb,jobs=[])
    python=N.bind(P.SIM.parents[2]/'.edge-speech-env/python.exe')
    for job in m['jobs']:
        protocol=P.G/'runner'/out.name/job['job_id'];target=Path(job['output'])
        N.need(not protocol.exists() and not target.exists(),'Existing outputs cannot be admitted')
        sources=[runner,mb,m['runner_helper'],*m['source_files'],*m['support'].values(),m['assets'],job['profile_binding'],job['gallery'],job['admission'],job['s6d_settings']]
        if job['beam_settings']:sources.append(job['beam_settings'])
        admission=N.verified(job['admission'])
        for key in ('case_result','qualification','original_case_result','original_qualification','configuration','calibration_partition'):
            if admission.get(key):sources.append(admission[key])
        if admission.get('calibration_partition'):
            cp=N.verified(admission['calibration_partition']);sources.append(cp['original_partition'])
        by_path={}
        for b in sources:
            N.need(N.bind(b['path'])==b,'Changed source before queue preparation')
            N.need(b['path'] not in by_path or by_path[b['path']]==b,'Conflicting source binding');by_path[b['path']]=b
        sources=list(by_path.values());N.need(all(b['bytes']<=16*1024**2 for b in sources) and sum(b['bytes'] for b in sources)<=64*1024**2,'Small-code/source check budget exceeded')
        completion=protocol/'COMPLETION.json';audit=target/'FULL_MULTISTREAM_AUDIT.json'
        fields={'status':'COMPLETE','failure':None,'native_job_id':job['job_id'],'manifest.sha256':mb['sha256'],'helper.sha256':m['runner_helper']['sha256'],'full_multistream_evidence_validated':True,'affinity_verified':[12,13,14,15],'protocol_observer_closed':True,'protocol_observer_errors':[],'stop_requested':False,'native_run_one_same_process':True,'subprocess_spawned_by_wrapper':False,'gui_tested':False,'completion_audit.path':str(audit)}
        audit_fields={'status':'PASS_FULL_MULTISTREAM_EVIDENCE','errors':[],'job_id':job['job_id'],'manifest.sha256':mb['sha256'],'dispatch.frames':job['expected_frames']}
        for name,proof in job['stream_proofs'].items():
            audit_fields['journals.'+name+'.sha256']=proof['sha256'];audit_fields['journals.'+name+'.bytes']=proof['bytes']
        fields['diagnostic_dual_journal_evidence_validated']=True
        audit_fields.update(diagnostic_expected_fields(job))
        artifacts=[dict(path=str(completion),format='json',min_bytes=1,expected_fields=fields),dict(path=str(audit),format='json',min_bytes=1,expected_fields=audit_fields),dict(path=str(target/'RESULT.json'),format='json',min_bytes=1,expected_fields={'status':'COMPLETE','failure':None,'manifest.sha256':mb['sha256'],'job.job_id':job['job_id'],'resource_observer_closed':True,'observer_errors':[],'completion_errors':[],'event_consumer_drained':True})]
        q['jobs'].append(dict(job_id=job['job_id'],kind='offline',workload='sensitive',argv=[python['path'],m['runner_helper']['path'],'--manifest',mb['path'],'--manifest-sha256',mb['sha256'],'--job-id',job['job_id']],cwd=m['source_root'],source_bindings=sources,heartbeat_path=str(protocol/'HEARTBEAT.json'),completion_path=str(completion),stop_request_path=str(protocol/'STOP_REQUEST.json'),timeout_s=960,stall_after_s=300,heartbeat_stale_s=45,stop_grace_s=75,allow_owned_termination=True,expected_artifacts=artifacts))
    out.mkdir();N.save(out/'QUEUE.json',q);qb=N.bind(out/'QUEUE.json')
    proposal=dict(schema='s6d_queue_approval_v1',run_id=q['run_id'],queue_sha256=qb['sha256'],authorization_ref=str(out/'ROOT_ADMISSION.json'),approved_job_sha256=[],proposed_job_sha256=[digest(j) for j in q['jobs']],executable_bindings=[python],allowed_working_directories=[m['source_root']],allowed_output_roots=q['payload_policy']['new_payload_roots'],status='UNAPPROVED_ROOT_ADOPTION_REQUIRED')
    N.save(out/'APPROVAL_PROPOSAL.json',proposal)
    N.save(out/'QUEUE_RECEIPT.json',dict(status='PROPOSED_NOT_APPROVED',source=N.bind(__file__),manifest=mb,queue=qb,approval_proposal=N.bind(out/'APPROVAL_PROPOSAL.json'),runner=runner,job_count=len(q['jobs']),state_dir=str(P.G/'runner'/out.name/'supervisor_state'),models_started=0,processes_started=0,hardware_calls=0,limits='Root must independently approve exact source/queue, C/input gates, current resource floors and nonoverlap with active176 before validate/launch'))
    print(json.dumps(N.bind(out/'QUEUE_RECEIPT.json')))

def diagnostic_expected_fields(job):
    """Literal supervisor predicates for both spools; paths bind to RESULT's session via wrapper."""
    N.need(set(job['stream_proofs'])=={job['asr_raw_stream']},'Exactly one declared diagnostic stream')
    proof=job['stream_proofs'][job['asr_raw_stream']]
    N.need(job['audio']==proof['audio'] and job['audio_pcm_sha256']==proof['sha256'] and job['expected_identity_frames']==job['expected_frames']==proof['frames'],'Diagnostic source/frame declarations disagree')
    result={'diagnostic_pair.stream_name':job['asr_raw_stream'],'diagnostic_pair.source_audio.path':job['audio']['path'],'diagnostic_pair.source_audio.sha256':job['audio']['sha256'],'diagnostic_pair.source_audio.bytes':job['audio']['bytes'],'diagnostic_pair.expected_frames':job['expected_frames'],'diagnostic_pair.source_pcm_sha256':proof['sha256']}
    for lane in ('asr','identity'):
        result['diagnostic_pair.'+lane+'.sha256']=proof['sha256'];result['diagnostic_pair.'+lane+'.bytes']=proof['bytes']
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prepare(a.manifest,a.manifest_sha256,a.output)
