"""Bounded model-free N4 application-method bank. README_INTEGRATED_HISTORY_V3.md."""
import argparse
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import shutil
import sys
import threading

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import audio_only,bind,freeze,load,verify
from integrated_bank_plan_v3 import SCHEMA,EXPECTED,build_join,code_bindings,exact_jobs,read_component_bank
from component_commands import asr_commands,d0_commands
from application_publication_v3 import replay_d0_publication,replay_d1_publication
from controller_projection_v3 import project_mode_result,forbid_inference
from probe_component_s7 import read_events
from method_artifact_v3 import read_replay,save_private
from evidence_store import safe_path
from integrated_prefix_reuse import load_reuse,reuse_cell,validate_reused
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'supervision'))
from supervisor import atomic,lock

GIB=1024**3
CELL_PEAK=280*1024**2
PENDING_AND_CONTINGENCY=6*GIB+GIB//2
WORKERS={'edge-s6d-policy','n4-cached-d1-activity','proto-caption-consumer'}


def verify_plan(path):
    plan=load(path)
    if plan.get('schema')!=SCHEMA or plan.get('status')!='PREPARED_REVIEWED_COMPONENT_JOIN_ONLY':
        raise ValueError('Require the complete reviewed-component plan')
    c=plan['context']
    if c['code']!=code_bindings():raise ValueError('Plan code changed; preserve and use a fresh derivative')
    for b in (c['source_receipt'],c['gallery_preparation'],c['catalog'],c['manifest'],c['panel'],
              *c['qualification'],*c['reviews'].values(),*c['runtimes'].values()):verify(b)
    source=load(c['source_receipt']['path']);root=Path(source['prototype'])
    for rel,b in source['files'].items():verify(dict(path=str((root/rel).resolve()),**b))
    sys.path[:0]=[str(root),str(root/'vendor')]
    jobs=exact_jobs(load(c['manifest']['path'])['jobs'])
    if plan['jobs']!=list(jobs.values()):raise ValueError('Plan audio manifest differs')
    records=[]
    for kind in EXPECTED:
        records.extend(read_component_bank(kind,c['reviews'][kind],source_binding=c['source_receipt'],
            manifest_binding=c['manifest'],jobs=jobs))
    expected=build_join(list(jobs.values()),load(c['catalog']['path']),records,load(c['gallery_preparation']['path']),c,
        scope=plan['scope'],panel_jobs=load(c['panel']['path'])['jobs'])
    if expected!=plan:raise ValueError('Plan differs from exact reviewed-parent join')
    return plan


def guard(root,allocation,policy,used):
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached; preserve incomplete bank')
    if type(allocation) is not int or not 0<allocation<=8*GIB or used+CELL_PEAK>allocation:
        raise ValueError('Integrated bank allocation unavailable')
    for drive,floor in [('C:/',50),('G:/',75)]:
        if shutil.disk_usage(drive).free<floor*GIB+CELL_PEAK:raise ValueError('Campaign free-space floor reached')
    safe_path(root)


def inventory_bytes(root):
    return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())


def predict_cell(row,job,context,output):
    """Prediction consumes exactly audio + declared mode + sealed component evidence."""
    import soundfile as sf
    audio_only(job)
    if row['job_id']!=job['job_id']:raise ValueError('Different prediction job')
    parents=[]
    for parent in row['parents']:
        verify(parent['result']);cell=load(parent['result']['path'])
        if (cell['status']!='COMPLETE' or cell['job']!=job or cell['cache_key']!=parent['cache_key']
                or cell['events']!=parent['events']):raise ValueError('Prediction parent differs')
        parents.append(cell)
    a,s=parents;contract=row['contract']
    if a['variant']!=contract['variant'] or s['encoder']!=contract['encoder']:
        raise ValueError('Wrong component variant')
    expected_schema='n4-d0-component-cell-v1' if contract['diarization']=='D0' else 'n4-d1-component-cell-v1'
    if s['schema']!=expected_schema:raise ValueError('D0/D1 parent cannot be substituted')
    if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Waveform bytes changed')
    arows=read_events(a);srows=read_events(s);duration=job['frames']/16000
    commands=asr_commands(arows,variant=a['variant'],duration=duration)
    formatting=[r['payload'] for r in arows if r['event_type']=='component_final_punctuation']
    kwargs=dict(preparation=context['gallery_preparation'],backend=contract['backend_key'],mode=contract['mode'],
        tap=job['tap'],namespace=s['namespace'],session_id=job['job_id'],formatting=formatting)
    with forbid_inference():
        if contract['diarization']=='D0':
            publication=replay_d0_publication(commands,d0_commands(srows,duration=duration),duration=duration,**kwargs)
        else:
            wave,rate=sf.read(job['audio_path'],dtype='float32')
            if rate!=16000 or wave.ndim!=1 or len(wave)!=job['frames']:raise ValueError('Waveform geometry differs')
            publication=replay_d1_publication(commands,srows,wave=wave,summary=s['summary'],**kwargs)
        if publication['contract']!=contract:raise ValueError('Actual mode routing differs')
        projection=project_mode_result(publication,tap=job['tap'],preparation=context['gallery_preparation'],
            n2_runtime=context['runtimes']['n2_runtime.json'],n3_runtime=context['runtimes']['n3_runtime.json'],
            data_root=output/'controller')
    if not projection['controller_closed'] or projection['consumer_thread_alive']:
        raise ValueError('Controller did not close')
    if any(t.name in WORKERS for t in threading.enumerate()):raise RuntimeError('Cached policy/Controller worker leaked')
    # These are full lossless artifacts, not summaries substituted for caption evidence.
    outputs={key:save_private(output/(key+'.json.gz'),value) for key,value in
             [('publication',publication),('projection',projection)]}
    return dict(status='COMPLETE_MODELED_APPLICATION_METHODS_ONLY',cell_id=row['cell_id'],job_id=job['job_id'],
        cache_key=row['cache_key'],parents=row['parents'],contract=contract,outputs=outputs,
        closure=projection['actual_consumer_closure'],empty_hypothesis=not publication['presentation']['rows'],
        raw_observations=publication['presentation']['raw_observations'],final_utterances=publication['presentation']['final_utterances'],
        displays=projection['display_inputs'],controller_closed=True,models_loaded=0,physical_widget_observed=False,
        D0_E1_association_qualification=row['D0_E1_association_qualification'],integrated_N4_cells=0)


def run(args):
    import psutil
    from asr_full_bank import payload_inventory
    plan=verify_plan(args.plan);plan_binding=bind(args.plan);context=plan['context']
    local=Path(context['source_receipt']['path']).parents[2];policy_path=local/'supervision/campaign.json';policy=load(policy_path)
    root=safe_path(args.output)
    if not root.is_relative_to((local/'n4').resolve()) or root.exists():raise ValueError('Fresh private N4 output required')
    reuse=load_reuse(plan)
    allocation=int(args.allocation_gib*GIB);guard(root,allocation,policy,0)
    proc=psutil.Process();owner=dict(pid=proc.pid,create_time=proc.create_time())
    with lock(local/'n4/integrated-method-bank.owner.lock'):
        inventory=payload_inventory(local)
        if inventory['errors'] or inventory['total_logical_bytes']+allocation+PENDING_AND_CONTINGENCY>min(50,policy['resource_policy']['new_payload_allowance_gib'])*GIB:
            raise ValueError('Shared payload allowance insufficient, including 6-GiB pending reservations and 0.5-GiB contingency')
        root.mkdir(parents=True,exist_ok=False)
        admission=dict(plan=plan_binding,owner=owner,allocation_bytes=allocation,cell_peak_bytes=CELL_PEAK,inventory=inventory,
            policy=bind(policy_path),cpu_affinity=proc.cpu_affinity(),models_loaded=0,integrated_N4_cells=0,
            reuse_review=context.get('reuse_review'),pending_and_contingency_bytes=PENDING_AND_CONTINGENCY)
        freeze(root/'ADMISSION.json',admission);completed=[];current=None;current_started=False
        jobs={j['job_id']:j for j in plan['jobs']};used=inventory_bytes(root)
        try:
            for i,row in enumerate(plan['rows']):
                current=row['cell_id'];current_started=False;guard(root,allocation,load(policy_path),used)
                cell=root/'cells'/f'{i:05d}';cell.mkdir(parents=True,exist_ok=False)
                current_started=True
                result=(reuse_cell(row,plan_binding,reuse,i) if reuse is not None and i<reuse['completed']
                        else predict_cell(row,jobs[row['job_id']],context,cell))
                freeze(cell/'RESULT.json',dict(result,plan=plan_binding))
                completed.append(bind(cell/'RESULT.json'));used+=inventory_bytes(cell)
                atomic(root/'PROGRESS.json',dict(status='RUNNING',owner=owner,completed=len(completed),total=plan['required'],
                    heartbeat_utc=datetime.now(timezone.utc).isoformat(),current_cell=current,integrated_N4_cells=0))
                if (i+1)%32==0:
                    used=inventory_bytes(root);verify(plan_binding)
                    print(json.dumps(dict(completed=len(completed),total=plan['required'])),flush=True)
                if (i+1)%128==0:
                    fresh=payload_inventory(local);latest=load(policy_path)
                    if (fresh['errors'] or fresh['total_logical_bytes']+max(0,allocation-used)+PENDING_AND_CONTINGENCY
                            >min(50,latest['resource_policy']['new_payload_allowance_gib'])*GIB):
                        current_started=False;current=None
                        raise ValueError('Shared campaign allocation changed; preserve checkpoint')
            verify(plan_binding)
            for b in context['code']:verify(b)
            freeze(root/'RESULT.json',dict(status='COLLECTED_METHOD_BANK_REQUIRES_REVIEW',utc=datetime.now(timezone.utc).isoformat(),
                owner=owner,plan=plan_binding,admission=bind(root/'ADMISSION.json'),completed=len(completed),total=plan['required'],
                failed=0,not_tested=0,cells=completed,integrated_N4_cells=0))
        except BaseException as exc:
            # A cell whose receipt is already sealed is not failed again when a
            # later budget or terminal verification check stops the run.
            current_started=current_started and (not completed or current!=plan['rows'][len(completed)-1]['cell_id'])
            freeze(root/'RESULT.json',dict(status='FAILED_PRESERVED',utc=datetime.now(timezone.utc).isoformat(),owner=owner,
                plan=plan_binding,admission=bind(root/'ADMISSION.json'),completed=len(completed),total=plan['required'],
                failed=int(current_started),not_tested=plan['required']-len(completed)-int(current_started),
                failed_cell=current if current_started else None,blocked_before_cell=None if current_started else current,
                error=repr(exc),cells=completed,
                integrated_N4_cells=0))
            raise
    print(json.dumps(dict(result=bind(root/'RESULT.json'),integrated_N4_cells=0)))


def review(args):
    import psutil
    root=safe_path(args.run);result=load(root/'RESULT.json');terminal=bind(root/'RESULT.json')
    owner=result['owner']
    try:
        if abs(psutil.Process(owner['pid']).create_time()-owner['create_time'])<.001:raise ValueError('Exact method worker is active')
    except psutil.NoSuchProcess:pass
    verify(result['plan']);verify(result['admission']);plan=verify_plan(result['plan']['path'])
    if (result['status']!='COLLECTED_METHOD_BANK_REQUIRES_REVIEW' or result['completed']!=plan['required']
            or result['total']!=plan['required'] or len(result['cells'])!=plan['required']):raise ValueError('Incomplete bank')
    if len({b['path'] for b in result['cells']})!=plan['required']:raise ValueError('Duplicate result binding')
    reuse=load_reuse(plan)
    counts=dict(empty_hypotheses=0,raw_observations=0,final_utterances=0,displays=0)
    for i,(row,b) in enumerate(zip(plan['rows'],result['cells'])):
        verify(b);cell=load(b['path'])
        if reuse is not None and i<reuse['completed']:validate_reused(cell,row,result['plan'],reuse,i)
        elif 'reused_from' in cell or 'execution_source' in cell:raise ValueError('Foreign reused cell')
        if Path(b['path']).resolve()!=root/'cells'/f'{i:05d}'/'RESULT.json':raise ValueError('Cell path differs')
        if (cell['status']!='COMPLETE_MODELED_APPLICATION_METHODS_ONLY' or cell['cell_id']!=row['cell_id']
                or cell['cache_key']!=row['cache_key'] or cell['parents']!=row['parents'] or cell['plan']!=result['plan']
                or cell['contract']!=row['contract'] or not cell['controller_closed'] or cell['models_loaded']
                or cell['physical_widget_observed'] or cell['integrated_N4_cells']):raise ValueError('Cell receipt differs')
        publication=read_replay(cell['outputs']['publication']);projection=read_replay(cell['outputs']['projection'])
        verify(cell['closure'])
        from controller_projection_v3 import validate_display_history
        validate_display_history(publication)
        if (publication['contract']!=row['contract'] or projection['contract']!=row['contract']
                or projection['display_inputs']!=cell['displays'] or projection['actual_consumer_closure']!=cell['closure']
                or len(publication['display_events'])!=cell['displays']
                or publication['presentation']['raw_observations']!=cell['raw_observations']
                or publication['presentation']['final_utterances']!=cell['final_utterances']
                or (not publication['presentation']['rows'])!=cell['empty_hypothesis']
                or projection['empty_caption_session']!=cell['empty_hypothesis']
                or publication['worker_counts']['thread_alive'] or publication.get('d1_worker_alive')
                or publication['worker_counts']['error'] or not publication['worker_counts']['closed']
                or publication['worker_counts']['accepted']!=publication['worker_counts']['completed']
                or not load(cell['closure']['path'])['full_event_consumer_drained']
                or not projection['controller_closed'] or projection['consumer_thread_alive']):raise ValueError('Artifact closure differs')
        counts['empty_hypotheses']+=cell['empty_hypothesis']
        for key in ('raw_observations','final_utterances','displays'):counts[key]+=cell[key]
    verify(terminal)
    if args.output.exists():raise ValueError('Preserve previous review')
    freeze(args.output,dict(status='PASS_REVIEWED_MODELED_METHOD_BANK_ONLY',utc=datetime.now(timezone.utc).isoformat(),
        terminal=terminal,plan=result['plan'],scope=plan['scope'],completed=plan['required'],counts=counts,
        all_full_artifacts_and_closures_verified=True,models_loaded=0,integrated_N4_cells=0,
        complete_Controller_parity=False,physical_widget_observed=False,
        remaining='Separate scoring, complete source-paced application/GUI/resource qualification and acceptance required'))
    print(json.dumps(dict(review=bind(args.output),integrated_N4_cells=0)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('run');p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allocation-gib',type=float,choices=[i/4 for i in range(1,33)],default=5)
    p=sub.add_parser('review');p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    import psutil
    process=psutil.Process();process.cpu_affinity([14]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    args=parser.parse_args();(run if args.command=='run' else review)(args)
