"""Future held serial core96 V5/80 queue; see README_S6D_BEAM_CORE80_V1.md."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import s6d_beam_native_run_core80_v1 as N
import s6d_beam_execution_prepare_v1 as P

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def prepare(manifest_path,manifest_sha,output):
    mb=N.bind(manifest_path);N.need(mb['sha256']==manifest_sha,'Exact reviewed execution manifest required');m=N.verified(mb)
    N.need(m['schema']=='s6d-beam-execution.v1' and m['runner_helper']==N.bind(N.__file__),'Exact new core-only wrapper required')
    N.core_scope(m);authorities=payload_sources(m)
    out=Path(output).resolve();N.need(out.parent==P.R/'runner' and not out.exists(),'Fresh runner proposal directory required')
    runner=authorities['runner']
    original=N.verified(N.bind(P.R/'runner/native_pilot_proposed_v1/PROPOSED_QUEUE.json'))
    q={k:deepcopy(original[k]) for k in ('schema','run_id','owner_thread_id','owner_session_id','fixture_only','campaign','disk_policy','payload_policy')}
    q['payload_policy']=payload_policy(q['payload_policy'],authorities)
    q.update(runner_sha256=runner['sha256'],status='PROPOSED_NOT_APPROVED',stage=m['stage'],manifest=mb,jobs=[])
    python=N.bind(P.SIM.parents[2]/'.edge-speech-env/python.exe')
    for job in m['jobs']:
        protocol=P.G/'runner'/out.name/job['job_id'];target=Path(job['output'])
        N.need(not protocol.exists() and not target.exists(),'Existing outputs cannot be admitted')
        sources=[runner,mb,m['runner_helper'],*m['source_files'],*m['support'].values(),m['assets'],job['profile_binding'],job['gallery'],job['admission'],job['s6d_settings'],*authorities['guards'],N.bind(__file__),N.bind(Path(__file__).with_name('README_S6D_BEAM_CORE80_V1.md'))]
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
        artifacts=[dict(path=str(completion),format='json',min_bytes=1,expected_fields=fields),dict(path=str(audit),format='json',min_bytes=1,expected_fields=audit_fields),dict(path=str(target/'RESULT.json'),format='json',min_bytes=1,expected_fields={'status':'COMPLETE','failure':None,'manifest.sha256':mb['sha256'],'job.job_id':job['job_id'],'resource_observer_closed':True,'observer_errors':[],'completion_errors':[],'event_consumer_drained':True})]
        q['jobs'].append(dict(job_id=job['job_id'],kind='offline',workload='sensitive',argv=[python['path'],m['runner_helper']['path'],'--manifest',mb['path'],'--manifest-sha256',mb['sha256'],'--job-id',job['job_id']],cwd=m['source_root'],source_bindings=sources,heartbeat_path=str(protocol/'HEARTBEAT.json'),completion_path=str(completion),stop_request_path=str(protocol/'STOP_REQUEST.json'),timeout_s=960,stall_after_s=300,heartbeat_stale_s=45,stop_grace_s=75,allow_owned_termination=True,expected_artifacts=artifacts))
    out.mkdir();N.save(out/'QUEUE.json',q);qb=N.bind(out/'QUEUE.json')
    proposal=dict(schema='s6d_queue_approval_v1',run_id=q['run_id'],queue_sha256=qb['sha256'],authorization_ref=str(out/'ROOT_ADMISSION.json'),approved_job_sha256=[],proposed_job_sha256=[digest(j) for j in q['jobs']],executable_bindings=[python],allowed_working_directories=[m['source_root']],allowed_output_roots=q['payload_policy']['new_payload_roots'],status='UNAPPROVED_ROOT_ADOPTION_REQUIRED',payload_cap_exception=authorities['exception'])
    N.save(out/'APPROVAL_PROPOSAL.json',proposal)
    N.save(out/'QUEUE_RECEIPT.json',dict(status='PROPOSED_NOT_APPROVED',source=N.bind(__file__),manifest=mb,queue=qb,approval_proposal=N.bind(out/'APPROVAL_PROPOSAL.json'),runner=runner,job_count=len(q['jobs']),state_dir=str(P.G/'runner'/out.name/'supervisor_state'),models_started=0,processes_started=0,hardware_calls=0,limits='Root must independently approve exact source/queue, C/input gates, current resource floors and nonoverlap with active176 before validate/launch'))
    print(json.dumps(N.bind(out/'QUEUE_RECEIPT.json')))


def payload_sources(manifest):
    """Read exact accepted future-only authority; no current state, models or processes."""
    def pinned(path,sha):
        b=N.bind(path);N.need(b['sha256']==sha,'Accepted payload source changed');return b
    acceptance=pinned(P.R/'runner/source_epoch_payload_v5/ROOT_SOURCE_ACCEPTANCE.json','585c3db4729d7b75ce42cc2cf7b0fc619d89afd096730c3215538ac1b48d4c34')
    accepted=N.verified(acceptance)
    N.need(accepted['status']=='ROOT_ACCEPTED_FUTURE_OFFLINE_PAYLOAD_V5_AND_WRAPPER_V3_SOURCE_ONLY' and accepted['run_id']=='20260913T195357Z' and accepted['owner_thread_id']=='01a0812d-3ff0-7ed0-a06c-4df61b62a459','Exact root future-source acceptance required')
    runner_freeze=accepted['runner_source_freeze'];wrapper_freeze=accepted['wrapper_source_freeze']
    N.need(runner_freeze['sha256']=='ad06ac96a795c298f7602e314846fe7ef4505c0688f7b0902364d2e9245a4ad6' and wrapper_freeze['sha256']=='f1a4cf4505187311f3025075ff86cf3eeb0a872ea25db4707a2fab111e7435d7','Exact accepted source freezes required')
    frozen=N.verified(runner_freeze);wrapper_data=N.verified(wrapper_freeze)
    runner=wrapper_data['runner'];wrapper=wrapper_data['wrapper']
    N.need(N.bind(runner['path'])==runner and runner['sha256']=='57fb87aaba12495f724adbcc78a2609f82a897dd5d3877e6a2cabd54a68a7978','Accepted V5 runner required')
    N.need(N.bind(wrapper['path'])==wrapper and wrapper['sha256']==N.PINS['protocol'],'Accepted V3 protocol required')
    exception=accepted['exception'];N.need(exception['sha256']=='079900e58493e18c3a995754ba7ac16ff680e4697ba8dc6521e0b6fe1eb3a54c','Exact justified80 exception required');value=N.verified(exception)
    guards=[exception]+[value[key] for key in ('contract','forecast','prior_runner')]+[acceptance,runner_freeze,wrapper_freeze]
    for b in guards+frozen['sources']:N.need(N.bind(b['path'])==b,'Payload authority/source changed')
    N.need(manifest.get('payload_cap_exception')==exception and manifest.get('payload_source_acceptance')==acceptance,'Manifest future payload authority differs')
    N.need(manifest['support'].get('runner')==runner and manifest['support']['protocol']==wrapper,'Manifest must bind exact V5/V3 support graph')
    N.core_scope(manifest)
    N.need(manifest['declaration']['sha256']=='01d2387be4c4fc7d1856cfe104f71a3c942b4df63b467b017782d07c4774e012','Exact original core declaration required')
    declaration=N.verified(manifest['declaration']);N.need(declaration['schema']=='s6d-beam-prospective-execution.v1','Original core declaration required')
    N.need(all(manifest[k]==declaration[k] for k in ('run_id','source_root','source_files','assets')),'Original application source/asset graph changed')
    N.need(all(manifest['support'][k]==declaration['support'][k] for k in ('evidence','native_loop')),'Original evidence/native loop changed')
    N.need(manifest['limits']=={**declaration['execution_limits'],'max_new_payload_gib':80},'Only exact80 limit addition allowed')
    tasks=[t for t in declaration['tasks'] if t['stage']=='main_core']
    keys=('job_id','stage','case_id','capture_profile','mode','asr_raw_stream')
    N.need([[j[k] for k in keys] for j in manifest['jobs']]==[[t[k] for k in keys] for t in tasks],'Original ordered core96 cells changed')
    for job in manifest['jobs']:
        N.need(job['profile_binding']==declaration['profile_binding'] and job['gallery']==declaration['gallery'] and job['settings']==declaration['settings'],'Core profile/gallery/settings changed')
    forecast=N.verified(value['forecast'])
    return dict(runner=runner,wrapper=wrapper,exception=exception,guards=guards,census_roots=forecast['census_roots'],source_acceptance=acceptance)


def payload_policy(original,authorities):
    N.need(original['max_new_payload_bytes']==40*2**30 and [str(Path(x).resolve()) for x in original['new_payload_roots']]==[str(Path(x).resolve()) for x in authorities['census_roots']],'Original40 shared payload roots must remain unchanged')
    return {**deepcopy(original),'max_new_payload_bytes':80*2**30,'cap_exception':authorities['exception']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prepare(a.manifest,a.manifest_sha256,a.output)
