"""Closed native176 scoring inputs only; README_S6D_NATIVE176_SCORING_INPUTS_V1.md."""
from __future__ import annotations
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
from types import SimpleNamespace
import wave

SIM=Path('C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation')
R=SIM/'reports/S6D/20260913T195357Z';G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
BASE=R/'runner/native_execution_queue_preparation_v1'
PROSPECTIVE=BASE/'PROSPECTIVE_SCORING_BINDINGS.json'
QUEUE=BASE/'native176/QUEUE.json'
RUNNER=R/'runner/source_epoch_census_v4/s6d_runner_v1.py'
STATE=G/'runner/native_execution_queue_preparation_v1/native176_state'
GALLERY=SIM/'reports/S6C/20260910T123540Z/enrollment/SCORER_GALLERY_MAP.json'
ANALYSIS=SIM/'staging/s5_text_metrics/analysis_env/Scripts/python.exe'
PINS=dict(prospective='ba9657466446a33e233145baada6f7859c76683f8921e09b2381222acd8ed406',queue='7cb1efcf8c80093f189acf8803d1e22f55d2ec74c5f5c3ffe04c06ff3fdeb4a2',runner='fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4',scorer='4260ba5d1ac59f1e5fc057b7fa105fd1f525982ccf546353b5f283c054f092d4',evidence='bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2',gallery='ed13643358be9e5d36a8a093a4b7ccac90108f5b4b5cc208d5f80360f49aea8f')
ROOT_ID='01a0812d-3ff0-7ed0-a06c-4df61b62a459'


def need(value,message):
    if not value:raise ValueError(message)
def finite(value):return type(value) in (int,float) and math.isfinite(value)
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def stamp(path):
    s=Path(path).stat();return s.st_size,s.st_mtime_ns,s.st_dev,s.st_ino


class Cache:
    """Hash each immutable input path once, checking its stat identity at every use."""
    def __init__(self):self.entries={};self.jsons={};self.pcm={};self.hash_reads=0
    def remember(self,path,before,digest):
        p=Path(path).resolve();need(stamp(p)==before,'Input changed while reading: '+str(p))
        ref=dict(path=str(p),bytes=before[0],sha256=digest);self.entries[str(p)]=(before,ref);self.hash_reads+=1;return ref
    def binding(self,path,expected=None):
        p=Path(path).resolve();key=str(p)
        if key not in self.entries:
            before=stamp(p);h=hashlib.sha256();capture=p.suffix.lower() in ('.json','.wav');raw=bytearray()
            if capture:need(before[0]<=64*2**20,'Bounded JSON/WAV input exceeded64MiB')
            with p.open('rb') as f:
                for block in iter(lambda:f.read(2**20),b''):
                    h.update(block)
                    if capture:raw.extend(block)
            self.remember(p,before,h.hexdigest())
            if p.suffix.lower()=='.json':self.jsons[key]=json.loads(raw.decode('utf-8-sig'),parse_constant=lambda x:need(False,'Nonfinite JSON'))
            if p.suffix.lower()=='.wav':
                with wave.open(io.BytesIO(raw),'rb') as f:
                    need((f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getcomptype())==(1,2,16000,'NONE'),'Exact mono PCM16/16k WAV required')
                    frames=f.getnframes();pcm=f.readframes(frames+1);need(len(pcm)==2*frames,'Truncated source WAV')
                self.pcm[key]=dict(source=self.entries[key][1],frames=frames,bytes=len(pcm),sha256=hashlib.sha256(pcm).hexdigest())
        before,ref=self.entries[key];need(stamp(p)==before,'Previously checked input changed: '+key)
        if expected is not None:need(ref['sha256']==expected,'Input SHA differs: '+key)
        return ref
    def check(self,ref):need(self.binding(ref['path'])==ref,'Exact input binding differs: '+ref['path']);return ref
    def load(self,path):
        self.binding(path);key=str(Path(path).resolve())
        need(key in self.jsons,'JSON file required');return deepcopy(self.jsons[key])
    def verified(self,ref):self.check(ref);return self.load(ref['path'])
    def graph(self,value):
        if isinstance(value,dict):
            if set(value)=={'path','bytes','sha256'} and isinstance(value.get('path'),str):self.check(value)
            else:
                for item in value.values():self.graph(item)
        elif isinstance(value,list):
            for item in value:self.graph(item)
    def dispatch(self,path,expected_frames,validator):
        p=Path(path).resolve();need(str(p) not in self.entries,'Dispatch journal must be validated on its first cached read')
        before=stamp(p);need(before[0]<=2**30,'Bounded consumer journal exceeded1GiB');h=hashlib.sha256()
        def events():
            with p.open('rb') as f:
                for index,line in enumerate(f):
                    need(index<1000000 and len(line)<=8*2**20 and line.endswith(b'\n'),'Oversized/partial event journal')
                    h.update(line);row=json.loads(line.decode('utf-8-sig'),parse_constant=lambda x:need(False,'Nonfinite event'))
                    need(isinstance(row,dict),'Event object required');yield row
        proof=validator(events(),expected_frames);self.remember(p,before,h.hexdigest());return proof
    def unchanged(self):
        for path,(before,ref) in self.entries.items():need(stamp(path)==before,'Input changed before commit: '+path)


def compile_functions(path,names,namespace):
    tree=ast.parse(Path(path).read_bytes());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    need({n.name for n in nodes}==set(names),'Pinned function inventory differs')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace);return namespace


def pure_apis(cache,prospective):
    cache.binding(RUNNER,PINS['runner'])
    runner=compile_functions(RUNNER,{'identity_matches','validate_completion'},dict(load=cache.load,binding=cache.binding,Path=Path))
    evidence=next(b for b in prospective['dependencies'] if Path(b['path']).name=='s6d_native_evidence_v1.py');cache.check(evidence);need(evidence['sha256']==PINS['evidence'],'Evidence source differs')
    e=compile_functions(evidence['path'],{'need','frame','validate_completion','validate_dispatch','shift_reference_pieces'},dict(math=math,RATE=16000))
    proxy=SimpleNamespace(need=need,frame=e['frame'],binding=cache.binding,shift_reference_pieces=e['shift_reference_pieces'])
    s=compile_functions(prospective['scorer']['path'],{'admit_full_source','validate_reference'},dict(E=proxy,EVIDENCE_SHA=PINS['evidence']))
    return runner,e,s


def matched_queue_rows(rows,queue_jobs):
    """Preserve prospective scoring order and join independently frozen execution order by ID."""
    ids=[r['job_id'] for r in rows];queued=[j['job_id'] for j in queue_jobs]
    need(len(set(ids))==len(ids) and len(set(queued))==len(queued) and set(ids)==set(queued),'Literal scoring/execution membership differs')
    jobs={j['job_id']:j for j in queue_jobs};return [(row,jobs[row['job_id']]) for row in rows]


def static_inputs(cache):
    pr=cache.binding(PROSPECTIVE,PINS['prospective']);qr=cache.binding(QUEUE,PINS['queue']);prospective=cache.load(PROSPECTIVE);queue=cache.load(QUEUE)
    need(prospective['status']=='PROSPECTIVE_CLOSED_OUTPUT_ADMISSION_REQUIRED' and prospective['declared_jobs']==176 and len(prospective['rows'])==176 and len(prospective['comparison_pairs'])==176,'Exact prospective population required')
    need(queue['group']=='native176' and queue['fixture_only'] is False and queue['run_id']=='20260913T195357Z' and queue['owner_thread_id']==queue['owner_session_id']==ROOT_ID and queue['runner_sha256']==PINS['runner'],'Exact production native176 queue required')
    ids=[r['job_id'] for r in prospective['rows']];matched=matched_queue_rows(prospective['rows'],queue['jobs']);need(len(matched)==176,'Literal176 population required')
    need(prospective['scorer']['sha256']==PINS['scorer'],'Accepted scorer differs');cache.graph(prospective['source_files']);cache.check(prospective['scorer']);cache.graph(prospective['dependencies']);cache.binding(RUNNER,PINS['runner']);cache.binding(GALLERY,PINS['gallery'])
    manifests={ref['path']:cache.verified(ref) for ref in prospective['execution_manifests']};declared={}
    for ref in prospective['execution_manifests']:
        manifest=manifests[ref['path']]
        for field in ('execution_files','helper','readme','protocol_sources','protocol_wrapper','evidence_helper'):cache.graph(manifest[field])
        for job in manifest['jobs']:
            need(job['job_id'] not in declared,'Repeated source manifest job');declared[job['job_id']]=(ref,job,manifest)
    need(set(declared)==set(ids),'Original manifests do not declare exactly176 jobs')
    for row,qjob in matched:
        ref,job,manifest=declared[row['job_id']]
        need(row['manifest']==ref and row['audio']==job['audio'] and row['expected_frames']==job['expected_frames'] and row['gallery']==job['gallery'],'Prospective scientific context differs')
        need(row['expected_result_path']==str(Path(job['output'])/'RESULT.json') and row['expected_completion_audit_path']==str(Path(job['output'])/'FULL_SOURCE_AUDIT.json'),'Prospective exact output differs')
        need(qjob['kind']=='offline' and qjob['workload']=='sensitive' and '--native-job-id' in qjob['argv'] and qjob['argv'][qjob['argv'].index('--native-job-id')+1]==job['job_id'],'Foreign queue job')
        cache.graph(qjob['source_bindings'])
    for pair in prospective['comparison_pairs']:
        need(pair['left_job_id'] in declared and pair['right_job_id'] in declared,'Comparison outside exact176')
        need(declared[pair['left_job_id']][1]['audio']==declared[pair['right_job_id']][1]['audio'],'Comparison source differs')
    return dict(prospective=prospective,prospective_ref=pr,queue=queue,queue_ref=qr,declared=declared)


def validate_closed(queue,queue_ref,checkpoint,closed_lock,closure,launch):
    """Pure closure semantics; callers separately bind exact files and prove PID absence."""
    ids=[j['job_id'] for j in queue['jobs']]
    need(checkpoint.get('run_id')==queue['run_id'] and checkpoint.get('queue_sha256')==queue_ref['sha256'] and checkpoint.get('status')=='FINISH' and checkpoint.get('active') is None and set(checkpoint.get('completed',{}))==set(ids),'Not an exact fully closed FINISH checkpoint')
    need(closed_lock.get('run_id')==queue['run_id'] and closed_lock.get('queue_sha256')==queue_ref['sha256'] and isinstance(closed_lock.get('owner_nonce'),str) and len(closed_lock['owner_nonce'])==32 and not closed_lock.get('unresolved_hardware'),'Immutable owner lock differs/unresolved')
    need(launch.get('pid')==closed_lock['pid'] and launch.get('creation_time')==closed_lock['creation_time'],'Original supervisor launch identity differs')
    result=closure.get('result') or {};awake=closure.get('keep_awake') or {};census=closure.get('payload_census_closure') or {};snapshot=census.get('snapshot') or {}
    need(closure.get('run_id')==queue['run_id'] and result.get('run_id')==queue['run_id'] and result.get('action')=='FINISH' and result.get('done')==result.get('total')==len(ids),'Supervisor result is not exact FINISH')
    need(closure.get('owner_lock')=='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT' and closure.get('hardware_restoration_unresolved') is False,'Supervisor lease not closed')
    need(awake.get('requested') is True and awake.get('owned') is True and awake.get('restored') is True and awake.get('status')=='RESTORED','Owned keep-awake closure absent')
    need(census.get('closed') is True and snapshot.get('running') is False and snapshot.get('has_complete') is True and snapshot.get('pending') is False and snapshot.get('error') is None and snapshot.get('violation_latched') is False,'Payload census not successfully closed')
    processes=[dict(role='supervisor',pid=closed_lock['pid'],creation_time=closed_lock['creation_time'])]
    for job_id in ids:
        saved=checkpoint['completed'][job_id];identity=saved['identity']
        need(saved.get('status')=='DECLARED_ARTIFACTS_VERIFIED' and type(saved.get('exit_code')) is int and saved['exit_code']==0 and identity.get('run_id')==queue['run_id'] and identity.get('job_id')==job_id and isinstance(identity.get('child_run_id'),str) and identity['child_run_id'],'Completed job identity/status differs')
        processes.append(dict(role=job_id,pid=identity['pid'],creation_time=identity['creation_time']))
    for item in processes:need(type(item['pid']) is int and item['pid']>0 and finite(item['creation_time']) and item['creation_time']>0,'Finite exact PID+creation identity required')
    return processes


def prove_absent(identities,provider):
    """Fresh read-only exact-instance checks. AccessDenied or unknown state never means absent."""
    rows=[];seen={}
    for item in identities:
        key=(item['pid'],item['creation_time'])
        if key not in seen:
            try:
                process=provider.Process(item['pid']);current=process.create_time()
                need(finite(current) and current>0,'Current process creation unavailable')
                need(abs(current-item['creation_time'])>=.001,'Recorded native/supervisor instance remains alive')
                state=dict(status='ORIGINAL_INSTANCE_ABSENT_PID_REUSED',current_creation_time=current)
            except provider.NoSuchProcess:state=dict(status='ORIGINAL_INSTANCE_ABSENT_PID_NOT_FOUND')
            seen[key]=state
        rows.append(dict(item,**seen[key]))
    return dict(status='ALL_RECORDED_INSTANCES_ABSENT',observed_utc=utc(),rows=rows,unique_instances=len(seen),processes_terminated=0,access_denied_is_absent=False)


def gallery_row(gallery_ref,rows):
    if gallery_ref is None:return dict(gallery_condition='NONE',manifest=None,profiles=[],available_identities=[],intended_identities=[])
    matches=[r for r in rows if r.get('manifest')==gallery_ref];need(len(matches)==1,'Exactly one original gallery-map row required');return deepcopy(matches[0])


def prepare(output):
    need(output.resolve().is_relative_to(R) and not output.exists(),'Fresh compact R preparation required');cache=Cache();data=static_inputs(cache);output.mkdir(parents=True)
    proposal=dict(schema='s6d-native176-scoring-build-proposal.v1',status='PREPARED_ONLY_NOT_APPROVED',builder=cache.binding(__file__),readme=cache.binding(Path(__file__).with_name('README_S6D_NATIVE176_SCORING_INPUTS_V1.md')),prospective=data['prospective_ref'],queue=data['queue_ref'],runner=cache.binding(RUNNER),state_dir=str(STATE),gallery_map=cache.binding(GALLERY),analysis_executable=cache.binding(ANALYSIS),declared_jobs=176,comparison_pairs=176,actual_outputs_inspected=False,actual_scoring=False,owner_exit_verified=False,root_admission_created=False,required_future_input=dict(schema='s6d-native176-scoring-build-admission.v1',status='ROOT_ACCEPTED_NATIVE176_CLOSED_INPUT_BUILDER_V1',allow_closed_input_construction=True,fields=['builder binding','readme binding','proposal binding','queue approval binding','supervisor_launch binding','checkpoint binding','closed_lock binding','supervisor_closure binding','output_root fresh G epoch','score_output_root fresh nested G directory']),unavailable_policy='All176 must close successfully and validate; this builder emits all176 jobs and no invented unavailable native outcomes. A changed/failed/active/missing input blocks construction. Existing reference-level unavailable populations remain untouched.',source_graph_unique_files=len(cache.entries))
    cache.unchanged();save(output/'PROPOSAL.json',proposal);return cache.binding(output/'PROPOSAL.json')


def build(admission_path,sha):
    cache=Cache();admission_ref=cache.binding(admission_path,sha);admission=cache.load(admission_path)
    need(admission.get('schema')=='s6d-native176-scoring-build-admission.v1' and admission.get('status')=='ROOT_ACCEPTED_NATIVE176_CLOSED_INPUT_BUILDER_V1' and admission.get('allow_closed_input_construction') is True,'Explicit reviewed closed-input construction required')
    need(admission['builder']==cache.binding(__file__) and admission['readme']==cache.binding(Path(__file__).with_name('README_S6D_NATIVE176_SCORING_INPUTS_V1.md')),'Builder source/README differs')
    proposal=cache.verified(admission['proposal']);need(proposal['status']=='PREPARED_ONLY_NOT_APPROVED' and proposal['builder']==admission['builder'],'Prepared builder graph differs')
    data=static_inputs(cache);prospective=data['prospective'];queue=data['queue'];qr=data['queue_ref']
    need(proposal['prospective']==data['prospective_ref'] and proposal['queue']==qr,'Prepared queue/prospective changed')
    checkpoint=cache.verified(admission['checkpoint']);closed=cache.verified(admission['closed_lock']);closure=cache.verified(admission['supervisor_closure']);launch=cache.verified(admission['supervisor_launch']);approval=cache.verified(admission['approval'])
    nonce=closed.get('owner_nonce');need(Path(admission['checkpoint']['path']).resolve()==STATE/'CHECKPOINT.json' and Path(admission['closed_lock']['path']).resolve()==STATE/('CLOSED_LOCK_'+str(nonce)+'.json') and Path(admission['supervisor_closure']['path']).resolve()==STATE/('SUPERVISOR_CLOSURE_'+str(nonce)+'.json'),'Exact state/immutable closure paths required')
    need(not (STATE/'SUPERVISOR_LOCK.json').exists(),'Supervisor lock still active')
    need(approval.get('schema')=='s6d_queue_approval_v1' and approval.get('run_id')==queue['run_id'] and approval.get('queue_sha256')==qr['sha256'] and approval.get('authorization_ref'),'Exact actually approved native queue required')
    digests=[hashlib.sha256(json.dumps(j,sort_keys=True,separators=(',',':')).encode()).hexdigest() for j in queue['jobs']]
    need(len(approval['approved_job_sha256'])==176 and set(approval['approved_job_sha256'])==set(digests),'Literal176 approved argv digests differ')
    identities=validate_closed(queue,qr,checkpoint,closed,closure,launch)
    import psutil
    absence=prove_absent(identities,psutil)
    need(shutil.disk_usage('C:/').free>=50*2**30 and shutil.disk_usage('G:/').free>=75*2**30,'C50/G75 floor unmet')
    out=Path(admission['output_root']).resolve();score_out=Path(admission['score_output_root']).resolve()
    need(out.is_relative_to(G) and score_out.is_relative_to(out) and out!=score_out and not out.exists() and not score_out.exists(),'Fresh bounded G input/scoring epoch required')
    r,e,s=pure_apis(cache,prospective);gallery_map=cache.load(GALLERY);items=[];gallery_values={};validations=[]
    for row,qjob in matched_queue_rows(prospective['rows'],queue['jobs']):
        job_id=row['job_id'];saved=checkpoint['completed'][job_id]
        validation=r['validate_completion'](qjob,saved['identity']);need(validation==saved['validation'],'Saved native completion artifacts changed')
        completion=cache.load(qjob['completion_path']);manifest_ref,job,manifest=data['declared'][job_id]
        need(completion['pid']==saved['identity']['pid'] and completion['creation_time']==saved['identity']['creation_time'] and completion['declared_model_assets']==manifest['assets'],'Actual protocol owner or declared model assets differ')
        result_ref=cache.binding(row['expected_result_path']);result=cache.load(row['expected_result_path']);audit_ref=cache.binding(row['expected_completion_audit_path']);audit=cache.load(row['expected_completion_audit_path'])
        need(completion['manifest']==manifest_ref and completion['completion_audit']==audit_ref and completion['native_result']==result_ref and result['manifest']==manifest_ref and result['helper']==manifest['helper'] and result['job']==job,'Exact native protocol/result/audit join differs')
        need(result['pid']==saved['identity']['pid'] and result['process_create_time']==saved['identity']['creation_time'],'Actual native PID+creation differs from saved owner')
        need(audit['status']=='PASS_OFFLINE_EVIDENCE' and audit['errors']==[] and audit['manifest']==manifest_ref and audit['result']==result_ref and audit['job_id']==job_id and audit['expected_frames_predeclared'] is True,'Accepted full-source audit differs')
        cache.check(job['audio']);need(cache.pcm[str(Path(job['audio']['path']).resolve())]==audit['journals']['source'],'Actual source PCM differs from admitted audit')
        for lane in ('asr','identity'):cache.check(audit['journals'][lane])
        finalization=cache.verified(audit['finalization']);consumer_closure=cache.verified(audit['consumer_closure']) if audit['consumer_closure'] else None
        s['admit_full_source'](job,audit);need(e['validate_completion'](result,job,finalization,audit['journals'],consumer_closure)==[],'Whole-source/native/finalizer/consumer guard failed')
        dispatch=cache.dispatch(audit['consumer_events']['path'],job['expected_frames'],e['validate_dispatch']);cache.check(audit['consumer_events']);need(dispatch==audit['dispatch'],'Actual full event dispatch differs')
        session=Path(result['session_dir']).resolve();need(session.is_relative_to(Path(job['output']).resolve()/'sessions'),'Foreign session output')
        need(Path(audit['finalization']['path']).resolve()==session/'session_finalization_v3.json' and Path(audit['consumer_events']['path']).resolve()==Path(job['output']).resolve()/'consumer_events.jsonl','Foreign finalizer/consumer event path')
        latest=cache.binding(session/'latest_labelled_transcript.jsonl')
        reference=cache.verified(row['reference']);cache.graph(reference);need(reference['input_audio']==job['audio'] and reference['composition_frames']==job['expected_frames'],'Reference source/frame binding differs');s['validate_reference'](reference)
        gallery=gallery_row(job['gallery'],gallery_map['rows']);gkey='NONE' if job['gallery'] is None else job['gallery']['sha256'];gallery_values[gkey]=gallery
        if job['gallery'] is not None:
            actual=cache.verified(job['gallery']);need({(p['profile_id'],p['display_name']) for p in actual['profiles']}=={(p['profile_id'],p['display_name']) for p in gallery['profiles']},'Actual gallery-map identities differ')
            loaded=result['telemetry']['scheduler']['identity']['gallery'];need(loaded['manifest']==job['gallery'] and loaded['loaded_count']==len(gallery['profiles']),'Actual native loaded gallery differs')
        items.append(dict(job_id=job_id,manifest=manifest_ref,result=result_ref,completion_audit=audit_ref,consumer_events=audit['consumer_events'],latest=latest,reference=row['reference'],gallery_key=gkey))
        validations.append(dict(job_id=job_id,identity=saved['identity'],validation=validation,dispatch=dispatch))
    need(len(items)==176 and not (STATE/'SUPERVISOR_LOCK.json').exists(),'Matrix incomplete or supervisor restarted');cache.unchanged()
    out.mkdir(parents=True,exist_ok=False);gallery_refs={}
    for key,value in gallery_values.items():
        path=out/('GALLERY_'+key+'.json');save(path,value);gallery_refs[key]=cache.binding(path)
    for item in items:item['gallery_row']=gallery_refs[item.pop('gallery_key')]
    proof=dict(schema='s6d-native176-closed-input-validation.v1',status='ALL176_CLOSED_INPUTS_VERIFIED',admission=admission_ref,prospective=data['prospective_ref'],queue=qr,checkpoint=admission['checkpoint'],closed_lock=admission['closed_lock'],supervisor_closure=admission['supervisor_closure'],owner_exit=absence,completion_validations=validations,unique_hashed_paths=len(cache.entries),hash_reads=cache.hash_reads,models_started=0,actual_scoring=False)
    save(out/'VALIDATION.json',proof)
    spec=dict(schema='s6d-native-scoring-inputs.v1',status='APPROVED_CLOSED_NATIVE_INPUTS',owner_exit_verified=True,source_graph_verified=True,scorer=prospective['scorer'],dependencies=prospective['dependencies'],gallery_map=cache.binding(GALLERY),execution_manifests=prospective['execution_manifests'],jobs=items,unavailable_jobs=[],comparison_pairs=prospective['comparison_pairs'],output_root=str(score_out),closed_input_validation=cache.binding(out/'VALIDATION.json'),builder=admission['builder'],root_build_admission=admission_ref,source_scope='Headless native consumer; GUI render/scanout not measured. Original complete/incomplete/disallowed reference populations retained.')
    cache.unchanged();need(not (STATE/'SUPERVISOR_LOCK.json').exists(),'Supervisor restarted before input commit');save(out/'SCORING_INPUTS.json',spec);spec_ref=cache.binding(out/'SCORING_INPUTS.json')
    save(out/'SCORER_COMMAND_PROPOSED.json',dict(status='PREPARED_NOT_LAUNCHED',argv=[str(ANALYSIS),'-B',prospective['scorer']['path'],'--spec',spec_ref['path'],'--sha256',spec_ref['sha256']],analysis_executable=cache.check(proposal['analysis_executable']),required_meeteval_version='0.4.3',separate_root_execution_review_required=True,models_started=0))
    return spec_ref


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare');a.add_argument('--output',type=Path,required=True)
    b=sub.add_parser('build');b.add_argument('--admission',type=Path,required=True);b.add_argument('--sha256',required=True)
    args=p.parse_args();print(json.dumps(prepare(args.output) if args.action=='prepare' else build(args.admission,args.sha256)))
