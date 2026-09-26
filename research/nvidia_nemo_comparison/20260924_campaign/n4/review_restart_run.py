"""Review the exact stopped selected restart population. README_RESTART_REVIEW.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

from common import audio_only, bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_child_admission import assert_plain_path
from paced_panel_plan import BASELINE, COMPOSITIONS
from restart_application_plan import admit_plan, execution_payload, SCHEMA as PLAN_SCHEMA, STATUS as PLAN_STATUS
from restart_plan_policy import JOBS, POLICY, stop_after_samples
from restart_application_runner import RUN_SCHEMA, PREPARED, qualified_runner
from review_restart_transport import record, review_cell
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
QUALIFICATION='RESTART_REVIEW_CHECK_V1.json'
OWN=('review_restart_transport.py','review_restart_run.py','test_restart_transport.py',
     'test_restart_run_review.py','probe_restart_review.py','README_RESTART_REVIEW.md')


def code_bindings():
    qb,q=record(HERE/'RESTART_RUNNER_CHECK_V1.json',HERE)
    require(q['status']=='PASS_RESTART_RUNNER_DEVELOPMENT_ONLY','Restart runner qualification differs')
    verify(q['private_receipt']);verify(q['private_admission'])
    require(exact_process(load(q['private_admission']['path'])['owner']) is None,'Runner probe still active')
    result={}
    for b in q['code']+[qb]+[bind(HERE/n) for n in OWN]:
        verify(b);require(b['path'] not in result or result[b['path']]==b,'Conflicting review dependency');result[b['path']]=b
    return [b for _,b in sorted(result.items())]


def validate_population(plan, terminal, collected, progress, cell_names, progress_names):
    required=plan['required'];candidates=plan['candidates'];rows=plan['rows']
    require(plan['schema']==PLAN_SCHEMA and plan['status']==PLAN_STATUS and plan['restart']==POLICY
        and type(required) is int and 2<=required<=12 and len(rows)==required
        and type(plan['required_sessions']) is int and plan['required_sessions']==2*required
        and 1<=len(candidates)<=6 and candidates[0]==BASELINE and len(set(candidates))==len(candidates)
        and set(candidates)<=COMPOSITIONS and required==2*len(candidates),'Reconstructed restart census differs')
    require(plan['actual_restart_qualified'] is False and plan['source_execution_authorized'] is False
        and plan['N4_accepted'] is False and plan['integrated_N4_cells']==0,'Plan cannot grant acceptance')
    ids=[];jobs={}
    for index,row in enumerate(rows):
        job=audio_only(row['job']);candidate=candidates[index//2];jid=JOBS[index%2]
        expected='restart_0_'+jid+'_'+candidate
        require(row['cell_id']==expected and row['composition']==candidate and job['job_id']==jid
            and row['kind']=='restart_pair' and type(row['repeat']) is int and row['repeat']==0
            and type(row['collection_credit']) is int and row['collection_credit']==0
            and type(row['stop_after_samples']) is int and row['stop_after_samples']==stop_after_samples(job),
            'Restart row order, fixed anchor or stop threshold differs')
        require(jid not in jobs or jobs[jid]==job,'Same saved tap job differs between candidates');jobs[jid]=job;ids.append(expected)
    require(len(set(ids))==required and len(cell_names)==required and set(cell_names)==set(ids),
        'Missing, extra or duplicate cell directories')
    require(len(progress_names)==required and set(progress_names)=={f'{i+1:04d}.json' for i in range(required)},
        'Missing, extra or duplicate progress entries')
    require(terminal['schema']==RUN_SCHEMA and terminal['status']=='COLLECTED_SELECTED_RESTART_PAIRS_REQUIRES_REVIEW'
        and all(type(terminal[k]) is int for k in ('completed','required','required_sessions','integrated_N4_cells'))
        and terminal['completed']==terminal['required']==required and terminal['required_sessions']==2*required
        and terminal['error'] is None and terminal['actual_restart_qualified'] is False
        and terminal['independent_complete_transport_reviewed'] is False
        and terminal['integrated_N4_cells']==0 and terminal['N4_accepted'] is False,'Terminal run is partial, failed or promoted')
    require(len(collected)==len(progress)==required and terminal['collected']==collected,'Terminal collected sequence differs')
    for index,(binding,value) in enumerate(zip(collected,progress)):
        require(fingerprint(value)==fingerprint(dict(completed=index+1,total=required,cell=binding,
            actual_restart_qualified=False,integrated_N4_cells=0)),'Progress receipt differs from exact planned order')
    return dict(planned_pairs=required,reviewed_pairs=required,planned_sessions=required*2,candidates=candidates,
        fixed_jobs=list(JOBS),additional_or_missing_pairs=0,population_origin='Reconstructed qualified selected restart plan')


def stopped_run(folder):
    folder=assert_plain_path(folder,LOCAL/'n4');bindings=[]
    def read(name):
        b,v=record(folder/name,folder);bindings.append(b);return b,v
    ab,a=read('ADMISSION.json');_,terminal=read('RESULT.json');_,owner=read('RUN_OWNER.json');_,worker=read('worker.json')
    require(a['schema']==RUN_SCHEMA and a['status']==PREPARED and a['actual_application_started'] is False,
        'Prepared restart run required')
    require(owner['admission']==ab==terminal['admission'] and owner['owner']==terminal['owner']
        and exact_process(a['owner']) is None and exact_process(owner['owner']) is None,'Run/preparer active or identity differs')
    require(Path(a['output']).resolve()==folder and Path(a['state']).resolve()==LOCAL/'supervision','Run output/state escaped campaign')
    parent,child,executable,script,qualification=qualified_runner()
    require(a['code']==parent and a['child_code']==child and a['executable']==executable
        and a['child_script']==script and a['qualification']==qualification,'Qualified split manifests or interpreter differ')
    verify(a['plan']);pb,plan=admit_plan(Path(a['plan']['path']))
    require(pb==a['plan'] and type(a['required']) is int and type(a['required_sessions']) is int
        and a['required']==plan['required'] and a['required_sessions']==plan['required_sessions'],'Run plan or census differs')
    argv=[executable['path'],'-B',str(HERE/'restart_application_runner.py'),'run','--admission',str(folder/'ADMISSION.json')]
    require(worker==dict(argv=argv,cwd=str(HERE)),'Fixed coordinator command differs')
    for b in bindings+parent+[qualification,pb]:verify(b)
    return dict(folder=folder,admission=ab,plan_binding=pb,plan=plan,terminal=terminal,coordinator=owner['owner'],
        code=child,parent_code=parent,executable=executable,coordinator_argv=argv,state=Path(a['state']),bindings=bindings)


def directory_names(folder):
    cells=assert_plain_path(folder/'cells',folder);progress=assert_plain_path(folder/'progress',folder)
    entries=list(cells.iterdir());records=list(progress.iterdir())
    require(len(entries)<=12 and len(records)<=12,'Restart directory census exceeds bound')
    for p in entries:require(assert_plain_path(p,folder).is_dir(),'Unexpected non-directory cell entry')
    for p in records:require(assert_plain_path(p,folder).is_file(),'Unexpected non-file progress entry')
    return sorted(p.name for p in entries),sorted(p.name for p in records)


def run(run_root,output):
    process=pin();started=time.monotonic();output=assert_plain_path(output,LOCAL/'n4')
    require(not output.exists() and not output.is_relative_to(run_root.resolve())
        and not run_root.resolve().is_relative_to(output),'Fresh review output separate from immutable run required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,LOCAL,started,3600)
        check();inventory=shared_allowance(LOCAL)
        freeze(output/'REVIEW_OWNER.json',dict(owner=identity(process),run=str(run_root.resolve()),utc=datetime.now(timezone.utc).isoformat()))
        try:
            code=code_bindings();qb,q=record(HERE/QUALIFICATION,HERE)
            require(q['status']=='PASS_RESTART_REVIEW_DEVELOPMENT_ONLY' and q['code']==code,'Restart reviewer is not qualified')
            verify(q['private_receipt'])
            context=stopped_run(run_root);folder=context['folder'];plan=context['plan'];names=directory_names(folder)
            collected=[];progress=[];progress_bindings=[]
            for index,row in enumerate(plan['rows']):
                cb,_=record(folder/'cells'/row['cell_id']/'COLLECTED.json',folder);collected.append(cb)
                pb,value=record(folder/'progress'/f'{index+1:04d}.json',folder);progress.append(value);progress_bindings.append(pb)
            population=validate_population(plan,context['terminal'],collected,progress,*names)
            freeze(output/'ADMISSION.json',dict(owner=identity(process),run_admission=context['admission'],plan=context['plan_binding'],
                run_records=context['bindings'],progress=progress_bindings,population=population,code=code,qualification=qb,inventory=inventory))
            reviewed=[]
            for index,row in enumerate(plan['rows']):
                check();payload=execution_payload(plan,index)
                value=review_cell(folder/'cells'/row['cell_id'],payload=payload,plan_sha256=fingerprint(plan),
                    coordinator=context['coordinator'],code=context['code'],parent_code=context['parent_code'],
                    executable=context['executable'],coordinator_argv=context['coordinator_argv'],state=context['state'],checkpoint=check)
                require(value['status']=='PASS_RESTART_TRANSPORT_AND_PAIR_JOINS_ONLY' and value['collected']==collected[index]
                    and value['actual_restart_qualified'] is False and value['N4_accepted'] is False,'Cell changed or improperly accepted')
                freeze(output/'cells'/f'{index+1:04d}.json',value);reviewed.append(bind(output/'cells'/f'{index+1:04d}.json'))
            for b in code+context['bindings']+[context['plan_binding'],qb]+collected+progress_bindings:verify(b)
            require(directory_names(folder)==names and exact_process(context['coordinator']) is None,'Run census/owner changed during review')
            check()
            freeze(output/'REVIEW.json',dict(status='PASS_COMPLETE_RESTART_EVIDENCE_COVERAGE_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),population=population,pair_reviews=reviewed,
                complete_planned_evidence_population_reviewed=True,full_lease_history_available=False,complete_process_history_available=False,
                viewport_rows_reviewed=False,resource_samples_reviewed=False,actual_restart_qualified=False,
                source_to_widget_latency_qualified=False,controlled_resources_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('Complete selected restart evidence checked; viewport/resource/timing and functional acceptance remain separate',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RESTART_REVIEW_PRESERVED',owner=identity(process),
                error_type=type(exc).__name__,error=str(exc)[:2000],actual_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();run(args.run,args.output)
