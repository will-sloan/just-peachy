"""Score terminal method banks; never import predictor code. README_SCORING_CLOCK_V2.md."""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone,timedelta
from itertools import product
import json
from pathlib import Path
import shutil
import time

from common import audio_only,bind,fingerprint,freeze,load,verify
from integrated_scoring_adapter_v2 import read_artifact,read_component_events,convert
from metric_process import MetricProcess,MetricProcessError,exact_process,identity,pin
from metrics import canonical
from scoring_report import report

HERE=Path(__file__).resolve().parent
GIB=1024**3
MAX_OUTPUT=512*1024**2
MODES={'anonymous_conversation','enrolled_names','selected_focus','selected_closed','open_with_names'}


@contextmanager
def writer_lock(path):
    """Windows OS lock; a stale file cannot leave an abandoned logical owner."""
    import msvcrt
    with Path(path).open('a+b') as stream:
        if stream.tell()==0:stream.write(b'0');stream.flush()
        stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        try:yield
        finally:
            stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)


def bindings(value):
    if isinstance(value,dict):
        if set(value)=={'path','sha256','bytes'}:yield value
        else:
            for v in value.values():yield from bindings(v)
    elif isinstance(value,list):
        for v in value:yield from bindings(v)


def verify_bindings(value):
    seen=set()
    for b in bindings(value):
        key=(b['path'],b['sha256'],b['bytes'])
        if key not in seen:verify(b);seen.add(key)
    return len(seen)


def validate_plan(plan,manifest,panel):
    """Pure evaluator-side census/key recheck; actual routing stays in frozen plan code."""
    if (plan.get('schema')!='n4-integrated-method-bank-plan-v1' or plan.get('status')!='PREPARED_REVIEWED_COMPONENT_JOIN_ONLY'
            or plan['scope'] not in ('main','modes-panel') or plan['main_mode']!='open_with_names'
            or plan['jobs']!=manifest['jobs']):raise ValueError('Reviewed prediction plan differs')
    jobs={j['job_id']:audio_only(j) for j in plan['jobs']}
    if len(jobs)!=480 or len(plan['jobs'])!=480 or any(sum(j['tap']==t for j in jobs.values())!=240 for t in ('O0','O1')):
        raise ValueError('Exact two-tap bank required')
    panel_ids=[j['job_id'] for j in panel['jobs']]
    if len(set(panel_ids))!=24 or len(panel_ids)!=24 or any(jobs.get(j['job_id'])!=j for j in panel['jobs']):
        raise ValueError('Panel differs')
    if sum(j['tap']=='O0' for j in panel['jobs'])!=12:raise ValueError('Panel tap census differs')
    modes={'open_with_names'} if plan['scope']=='main' else MODES-{'open_with_names'}
    selected=set(jobs) if plan['scope']=='main' else set(panel_ids)
    required={(a,d,e,j,m) for a,d,e,j,m in product(('A0','A1','A2','A3'),('D0','D1'),('E0','E1'),selected,modes)}
    found=set()
    for row in plan['rows']:
        c=row['contract'];key=c['variant'],c['diarization'],c['encoder'],row['job_id'],c['mode']
        if key in found or key not in required:raise ValueError('Foreign or duplicate method cell')
        found.add(key)
        if row['composition']!='_'.join(key[:3]) or row['cell_id']!='_'.join(key):raise ValueError('Method cell identity differs')
        expected=dict(audio=jobs[row['job_id']],contract=c,context=plan['context'],parents=row['parents'],
            clock='MODELED_COMPONENT_AVAILABILITY_AND_100MS_SOURCE_CURSOR')
        if (len(row['parents'])!=2 or fingerprint(expected)!=row['cache_key'] or row['integrated_N4_cells']
                or row['physical_widget_observed']):raise ValueError('Method parent/causal cache identity differs')
    if found!=required or len(found)!=plan['required']:raise ValueError('Full method plan census required even for a partial run')
    return jobs


def validate_terminal(result,plan):
    if result['total']!=plan['required'] or len(result['cells'])!=result['completed']:raise ValueError('Terminal count differs')
    if any(type(result[k]) is not int or result[k]<0 for k in ('completed','failed','not_tested')):
        raise ValueError('Invalid denominator')
    if result['completed']+result['failed']+result['not_tested']!=result['total']:raise ValueError('Missing denominator')
    if result['status']=='COLLECTED_METHOD_BANK_REQUIRES_REVIEW':
        if result['failed'] or result['not_tested']:raise ValueError('False complete terminal')
    elif result['status']=='FAILED_PRESERVED':
        if result['failed'] not in (0,1):raise ValueError('Unexpected partial-run failure count')
        if result['failed'] and (result['completed']>=plan['required'] or result['failed_cell']!=plan['rows'][result['completed']]['cell_id']):
            raise ValueError('Failed cell is not the first unsealed prediction')
        if not result['failed'] and result.get('failed_cell') is not None:raise ValueError('Invented failed prediction')
    else:raise ValueError('Only immutable terminal banks may be scored')
    if len({b['path'] for b in result['cells']})!=len(result['cells']):raise ValueError('Duplicated completed cell')


def admit(run,review_path=None):
    terminal_binding=bind(run/'RESULT.json');terminal=load(terminal_binding['path'])
    if exact_process(terminal['owner']) is not None:raise ValueError('Exact prediction-bank owner is still active')
    for b in (terminal['plan'],terminal['admission']):verify(b)
    admission=load(terminal['admission']['path']);plan=load(terminal['plan']['path']);c=plan['context']
    if admission['plan']!=terminal['plan'] or admission['owner']!=terminal['owner']:raise ValueError('Owner/admission differs')
    verify_bindings(c)
    source=load(c['source_receipt']['path']);root=Path(source['prototype'])
    for rel,b in source['files'].items():verify(dict(path=str((root/rel).resolve()),**b))
    qualification_path=HERE/'INTEGRATED_BANK_CLOCK_CHECK_V2.json'
    qualification=load(qualification_path)
    validate_implementation(c,qualification,bind(qualification_path))
    verify_bindings(qualification)
    jobs=validate_plan(plan,load(c['manifest']['path']),load(c['panel']['path']));validate_terminal(terminal,plan)
    review_binding=bind(review_path) if review_path else None
    if terminal['status']=='COLLECTED_METHOD_BANK_REQUIRES_REVIEW':
        if review_binding is None:raise ValueError('Complete bank requires its passed terminal method review')
        review=load(review_binding['path'])
        if (review.get('status')!='PASS_REVIEWED_MODELED_METHOD_BANK_ONLY' or review['terminal']!=terminal_binding
                or review['plan']!=terminal['plan'] or review['completed']!=plan['required']
                or not review['all_full_artifacts_and_closures_verified']):raise ValueError('Terminal review differs')
    elif review_binding is not None:raise ValueError('Partial failure cannot use a complete-bank review')
    for i,b in enumerate(terminal['cells']):
        if Path(b['path']).resolve()!=run.resolve()/'cells'/f'{i:05d}'/'RESULT.json':raise ValueError('Sealed prefix path differs')
        verify(b);cell=load(b['path']);row=plan['rows'][i]
        if (cell['status']!='COMPLETE_MODELED_APPLICATION_METHODS_ONLY' or cell['plan']!=terminal['plan']
                or any(cell[k]!=row[k] for k in ('cell_id','job_id','cache_key','parents','contract'))
                or not cell['controller_closed'] or cell['models_loaded'] or cell['physical_widget_observed']
                or cell['integrated_N4_cells']):raise ValueError('Sealed method prefix differs')
        # Hash checking here; full gzip/closure validation occurs just before conversion.
        verify_bindings(cell)
    verify(terminal_binding)
    return dict(plan=plan,terminal=terminal,jobs=jobs,terminal_binding=terminal_binding,review=review_binding)


def prediction(cell,row,job):
    for p in row['parents']:verify(p['result'])
    a,s=[load(p['result']['path']) for p in row['parents']]
    if (a['job']!=job or s['job']!=job or a['variant']!=row['contract']['variant']
            or s['encoder']!=row['contract']['encoder'] or a['status']!='COMPLETE' or s['status']!='COMPLETE'
            or s['schema']!=('n4-d0-component-cell-v1' if row['contract']['diarization']=='D0' else 'n4-d1-component-cell-v1')):
        raise ValueError('Method/component audio or architecture join differs')
    for p,v in zip(row['parents'],(a,s)):
        if p['events']!=v['events'] or p['cache_key']!=v['cache_key']:raise ValueError('Parent component binding differs')
    pub=read_artifact(cell['outputs']['publication']);proj=read_artifact(cell['outputs']['projection']);verify(cell['closure'])
    counts=pub['worker_counts']
    if (pub['contract']!=row['contract'] or proj['contract']!=row['contract']
            or proj['actual_consumer_closure']!=cell['closure'] or not load(cell['closure']['path'])['full_event_consumer_drained']
            or counts['thread_alive'] or counts['error'] or not counts['closed'] or counts['accepted']!=counts['completed']
            or pub.get('d1_worker_alive') or len(pub['display_events'])!=cell['displays']
            or proj['display_inputs']!=cell['displays'] or pub['presentation']['raw_observations']!=cell['raw_observations']
            or pub['presentation']['final_utterances']!=cell['final_utterances']
            or (not pub['presentation']['rows'])!=cell['empty_hypothesis']
            or proj['empty_caption_session']!=cell['empty_hypothesis']):raise ValueError('Lossless method closure differs')
    return convert(pub,proj,read_component_events(s),job,row['contract']['diarization'])


def unavailable(truth,execution,reason):
    # Do not tell score_cell that a successful prediction failed just because a
    # metric timed out. Keep both status axes and their original denominators.
    return dict(job_id=truth['job_id'],reference_class=truth['reference_class'],execution_status=execution,
        metric_status=reason,scoring_status='NOT_SCORED_'+reason,
        reference_words=sum(len(canonical(t['transcript']).split()) for t in truth['turns']),
        audio_seconds=truth['frames']/16000,primary_wer=None,raw_wer=None,cpwer=None,mimo=None,activity=None,
        naming_metrics_status='UNAVAILABLE_ACTUAL_WIDGET_VISIBILITY_NOT_RECORDED',integrated_N4_cells=0)


def guard(output,policy,started,seconds):
    if time.monotonic()-started>=seconds:raise TimeoutError('Scoring run budget reached')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    for drive,floor in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<floor*GIB+MAX_OUTPUT:raise ValueError('Scoring drive floor unavailable')
    if output.exists() and sum(p.stat().st_size for p in output.rglob('*') if p.is_file())>MAX_OUTPUT-32*1024**2:
        raise ValueError('Scoring output budget reached')


def validate_implementation(context, qualification, qualification_binding):
    code=context.get('code',[])
    if (qualification.get('status')!='PASS_INTEGRATED_BANK_NATIVE_CLOCK_DERIVATIVE_ONLY'
            or qualification.get('artifact_cap_bytes')!=64*1024**2
            or not code or code!=qualification.get('code')
            or len({b['path'] for b in code})!=len(code)
            or qualification_binding not in context.get('qualification',[])):
        raise ValueError('V2 method implementation has not been qualified')
    names={Path(b['path']).name for b in code}
    if not {'integrated_bank_v2.py','integrated_bank_plan_v2.py','method_artifact_v2.py'} <= names:
        raise ValueError('V2 method implementation entrypoints missing')


def code_bindings():
    from scoring_bank import code_bindings as original_code
    return original_code()+[bind(HERE/n) for n in ('integrated_scoring_adapter_v2.py',
        'scoring_bank_v2.py','review_scoring_bank_v2.py','test_scoring_bank_v2.py',
        'test_scoring_review_v2.py','test_scoring_clock_v2.py','probe_scoring_clock_v2.py',
        'README_SCORING_CLOCK_V2.md','paced_slot.py')]


def qualification():
    path=HERE/'SCORING_CLOCK_CHECK_V2.json';value=load(path)
    if value.get('status')!='PASS_SCORING_CLOCK_DERIVATIVE_DEVELOPMENT_ONLY' or value.get('scoring_code')!=code_bindings():
        raise ValueError('V2 scoring implementation is not qualified')
    verify_bindings(value)
    return bind(path)


def run(args):
    p=pin();terminal=load(args.run/'RESULT.json');verify(terminal['plan'])
    plan=load(terminal['plan']['path']);local=Path(plan['context']['source_receipt']['path']).parents[2]
    with writer_lock(local/'n4/metric-scoring.owner.lock'):_run(args,p)


def _run(args,p):
    qualified=qualification();started=time.monotonic();bundle=admit(args.run,args.review);plan=bundle['plan'];terminal=bundle['terminal']
    local=Path(plan['context']['source_receipt']['path']).parents[2];policy_path=local/'supervision/campaign.json';policy=load(policy_path)
    if args.output.exists() or not args.output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private N4 output required')
    from probe_integrated_scoring import verify_environment,private_bytes
    environment=load(HERE/'METRIC_ENVIRONMENT.json')['environment'];environment_files=verify_environment(environment)
    guard(args.output,policy,started,args.max_seconds);size=private_bytes(local)
    if size+6*GIB+MAX_OUTPUT>min(50,policy['resource_policy']['new_payload_allowance_gib'])*GIB:
        raise ValueError('Shared campaign allowance unavailable with 6-GiB existing reservations')
    prep_binding=load(HERE/'PREPARATION_V2_CHECK.json')['preparation'];verify(prep_binding);prep=load(prep_binding['path'])
    truth_binding=next(b for b in prep['inputs'] if Path(b['path']).name=='EVALUATOR_TRUTH.json')
    strata_binding=next(b for b in prep['outputs'] if Path(b['path']).name=='EVALUATOR_STRATA.json')
    for b in (truth_binding,strata_binding):verify(b)
    if plan['context']['manifest']!=next(b for b in prep['outputs'] if Path(b['path']).name=='AUDIO_ONLY_480.json'):
        raise ValueError('Prediction/evaluator preparation differs')
    truth_doc=load(truth_binding['path']);strata_doc=load(strata_binding['path'])
    if truth_doc['NEVER_PASS_TO_RUNTIME'] is not True or strata_doc['NEVER_PASS_TO_RUNTIME'] is not True:
        raise ValueError('Evaluator-only boundary marker required')
    truths={r['job_id']:r for r in truth_doc['cells']};strata={r['case_id']:r for r in strata_doc['scenes']}
    if len(truths)!=480 or len(truth_doc['cells'])!=480 or len(strata)!=240:raise ValueError('Reference census differs')
    for jid,job in bundle['jobs'].items():
        if truths[jid]['frames']!=job['frames'] or truths[jid]['tap']!=job['tap']:raise ValueError('Reference/audio join differs')
    code=code_bindings();args.output.mkdir(parents=True,exist_ok=False)
    freeze(args.output/'ADMISSION.json',dict(owner=identity(p),terminal=bundle['terminal_binding'],review=bundle['review'],
        plan=terminal['plan'],code=code,qualification=qualified,environment=environment,environment_files_verified=environment_files,
        truth=truth_binding,strata=strata_binding,policy=bind(policy_path),private_bytes_at_start=size,
        cpu_affinity=p.cpu_affinity(),cell_timeout_seconds=args.cell_timeout,max_seconds=args.max_seconds,
        maximum_output_bytes=MAX_OUTPUT,existing_reservations_gib=6,integrated_N4_cells=0))
    client=None;closures=[];rows=[];score_bindings=[];stop_reason=None;consecutive_errors=0
    try:
        for i,row in enumerate(plan['rows']):
            job=bundle['jobs'][row['job_id']];truth=truths[row['job_id']];metric_input=None;seconds=None
            execution='COMPLETE' if i<terminal['completed'] else 'FAILED' if i==terminal['completed'] and terminal['failed'] else 'NOT_TESTED'
            cell_binding=terminal['cells'][i] if execution=='COMPLETE' else None
            if execution!='COMPLETE':score=unavailable(truth,execution,'EXECUTION_'+execution)
            elif stop_reason:score=unavailable(truth,execution,stop_reason)
            else:
                try:
                    guard(args.output,load(policy_path),started,args.max_seconds)
                    if i%128==0 and private_bytes(local)+6*GIB+MAX_OUTPUT>min(50,policy['resource_policy']['new_payload_allowance_gib'])*GIB:
                        raise ValueError('Shared payload allowance changed')
                except (ValueError,TimeoutError) as exc:
                    stop_reason='RESOURCE_OR_TIME_STOP';score=unavailable(truth,execution,stop_reason)
                else:
                    before=time.monotonic()
                    try:
                        verify(cell_binding);pred=prediction(load(cell_binding['path']),row,job)
                        if client is None:client=MetricProcess();client.start()
                        reserve=(datetime.fromisoformat(load(policy_path)['target_utc'])-timedelta(hours=12)-datetime.now(timezone.utc)).total_seconds()
                        budget=min(args.cell_timeout,args.max_seconds-(time.monotonic()-started),reserve)
                        if budget<=0:raise MetricProcessError('TIME_BUDGET','Scoring cutoff reached')
                        response=client.score(truth,pred,timeout_seconds=budget);score=response['score'];metric_input=response['input_sha256']
                        score['metric_status']='SCORED';consecutive_errors=0
                    except (ValueError,KeyError,OSError,MetricProcessError) as exc:
                        reason=exc.status if isinstance(exc,MetricProcessError) else 'INPUT_VALIDATION_ERROR'
                        score=unavailable(truth,execution,reason);consecutive_errors+=1
                        if client is not None:closures.append(client.close());client=None
                        if consecutive_errors>=3:stop_reason='STOPPED_AFTER_THREE_CONSECUTIVE_METRIC_ERRORS'
                    seconds=time.monotonic()-before
            result=dict(cell_id=row['cell_id'],job_id=job['job_id'],case_id=truth['case_id'],tap=job['tap'],
                composition=row['composition'],mode=row['contract']['mode'],score=score,method_result=cell_binding,
                metric_input_sha256=metric_input,metric_seconds=seconds,integrated_N4_cells=0)
            path=args.output/'cells'/f'{i:05d}.json';freeze(path,result);score_bindings.append(bind(path));rows.append(result)
            if (i+1)%128==0:print(json.dumps(dict(accounted=i+1,required=plan['required'],stop_reason=stop_reason)),flush=True)
        if client is not None:closures.append(client.close());client=None
        for b in code+[bundle['terminal_binding'],truth_binding,strata_binding]:verify(b)
        summary=report(rows,strata,scope=plan['scope'])
        encoded=len(json.dumps(summary,ensure_ascii=False,allow_nan=False,indent=2).encode())+1
        if sum(p.stat().st_size for p in args.output.rglob('*') if p.is_file())+encoded+8*1024**2>MAX_OUTPUT:
            raise ValueError('Final report would exceed the admitted output bound')
        freeze(args.output/'REPORT.json',summary)
        missing=sum(r['score']['execution_status']=='COMPLETE' and r['score']['metric_status']!='SCORED' for r in rows)
        freeze(args.output/'RESULT.json',dict(status='SCORED_MODELED_BANK_REQUIRES_REVIEW' if not missing and not terminal['failed'] and not terminal['not_tested']
            else 'PARTIAL_MODELED_BANK_SCORING',utc=datetime.now(timezone.utc).isoformat(),admission=bind(args.output/'ADMISSION.json'),
            scores=score_bindings,report=bind(args.output/'REPORT.json'),required=plan['required'],
            prediction_completed=terminal['completed'],prediction_failed=terminal['failed'],prediction_not_tested=terminal['not_tested'],
            metrics_unavailable_for_complete_predictions=missing,workers=closures,stop_reason=stop_reason,integrated_N4_cells=0))
        print(json.dumps(dict(result=bind(args.output/'RESULT.json'),integrated_N4_cells=0)))
    except BaseException as exc:
        if client is not None:closures.append(client.close())
        freeze(args.output/'FAILED.json',dict(status='FAILED_SCORING_PRESERVED',error_type=type(exc).__name__,accounted=len(rows),
            required=plan['required'],unaccounted=plan['required']-len(rows),scores=score_bindings,workers=closures,integrated_N4_cells=0))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('run','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--review',type=Path);parser.add_argument('--cell-timeout',type=int,choices=range(1,121),default=60)
    parser.add_argument('--max-seconds',type=int,choices=range(60,14401),default=4*3600)
    run(parser.parse_args())
